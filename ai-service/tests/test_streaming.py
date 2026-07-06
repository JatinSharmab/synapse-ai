import asyncio
import json
from collections.abc import Iterator
from pathlib import Path
from threading import Event
from time import sleep
from typing import cast

from fastapi.testclient import TestClient
from pydantic import TypeAdapter

from app.core.config import Settings
from app.main import create_app
from app.models.state import SynapseState
from app.schemas.streaming import StreamEvent
from app.services.streaming import SSEStreamService

EVENT_ADAPTER: TypeAdapter[StreamEvent] = TypeAdapter(StreamEvent)
SAMPLE_CSV = (
    Path(__file__).resolve().parents[2] / "sample-data" / "datasets" / "regional-revenue.csv"
)


def _events(body: str) -> list[StreamEvent]:
    events: list[StreamEvent] = []
    for frame in body.split("\n\n"):
        data_line = next((line for line in frame.splitlines() if line.startswith("data: ")), None)
        if data_line is not None:
            events.append(EVENT_ADAPTER.validate_python(json.loads(data_line[6:])))
    return events


def test_fastapi_stream_emits_typed_safe_events_with_request_ids() -> None:
    app = create_app(Settings(app_env="test", ai_provider="mock"))

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/chat/stream",
            headers={
                "X-Request-ID": "request-stream-test",
                "X-Correlation-ID": "correlation-stream-test",
            },
            json={
                "message": "Explain what RAG means.",
                "thread_id": "thread-stream",
            },
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache, no-transform"
    assert response.headers["x-request-id"] == "request-stream-test"
    assert response.headers["x-correlation-id"] == "correlation-stream-test"
    events = _events(response.text)
    event_types = [event.type for event in events]
    assert event_types[0:3] == [
        "request.started",
        "route.selected",
        "generation.started",
    ]
    assert "guardrail.completed" in event_types
    assert "generation.token" in event_types
    assert event_types[-1] == "response.completed"
    assert [event.sequence for event in events] == list(range(1, len(events) + 1))
    assert all(event.request_id == "request-stream-test" for event in events)
    assert "trace" not in response.text
    assert "system_prompt" not in response.text
    assert "draft_response" not in response.text


def test_document_stream_emits_retrieval_lifecycle_and_candidate_count() -> None:
    app = create_app(Settings(app_env="test", ai_provider="mock"))

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/chat/stream",
            json={
                "message": "Find the refund policy in my documents.",
                "thread_id": "thread-retrieval-stream",
            },
        )

    events = _events(response.text)
    event_types = [event.type for event in events]
    assert event_types.index("retrieval.started") < event_types.index("retrieval.completed")
    completed = next(event for event in events if event.type == "retrieval.completed")
    assert completed.tool == "document_search"
    assert completed.candidate_count == 0
    assert completed.latency_ms >= 0


def test_analytics_stream_emits_validated_genui_after_guardrails(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            app_env="test",
            ai_provider="mock",
            dataset_metadata_path=tmp_path / "datasets.json",
            dataset_max_upload_bytes=100_000,
            dataset_max_rows=100,
            dataset_max_columns=10,
            analytics_max_result_rows=20,
        )
    )

    with TestClient(app) as client:
        uploaded = client.post(
            "/api/v1/datasets",
            files={"file": ("regional-revenue.csv", SAMPLE_CSV.read_bytes(), "text/csv")},
        )
        assert uploaded.status_code == 201
        response = client.post(
            "/api/v1/chat/stream",
            json={
                "message": "Compare revenue across regions.",
                "thread_id": "thread-genui-stream",
            },
        )

    events = _events(response.text)
    event_types = [event.type for event in events]
    assert event_types.index("guardrail.completed") < event_types.index("genui.created")
    assert event_types[-1] == "response.completed"
    genui = next(event for event in events if event.type == "genui.created")
    assert genui.components[0].type == "bar_chart"


class _FailingStreamer:
    def stream_states(
        self,
        *,
        message: str,
        thread_id: str,
        request_id: str,
    ) -> Iterator[SynapseState]:
        del message, thread_id, request_id
        raise RuntimeError("private upstream detail")
        yield cast(SynapseState, {})  # pragma: no cover


def test_stream_failure_is_normalized_without_private_exception_text() -> None:
    app = create_app(Settings(app_env="test", ai_provider="mock"))
    app.state.orchestrator = _FailingStreamer()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/chat/stream",
            json={"message": "Hello there", "thread_id": "thread-error"},
        )

    events = _events(response.text)
    assert [event.type for event in events] == ["request.started", "error"]
    error = events[-1]
    assert error.type == "error"
    assert error.code == "STREAM_FAILED"
    assert "private upstream detail" not in response.text


class _SlowStreamer:
    def stream_states(
        self,
        *,
        message: str,
        thread_id: str,
        request_id: str,
    ) -> Iterator[SynapseState]:
        del message, thread_id, request_id
        sleep(0.1)
        if False:
            yield cast(SynapseState, {})  # pragma: no cover


def test_stream_timeout_emits_error_and_heartbeat_without_hanging() -> None:
    service = SSEStreamService(
        _SlowStreamer(),
        timeout_seconds=0.04,
        heartbeat_seconds=0.01,
    )

    async def collect() -> str:
        async def connected() -> bool:
            return False

        chunks = [
            chunk
            async for chunk in service.stream(
                message="Hello",
                thread_id="thread-timeout",
                request_id="request-timeout",
                correlation_id="correlation-timeout",
                is_disconnected=connected,
            )
        ]
        return "".join(chunks)

    body = asyncio.run(collect())
    events = _events(body)
    assert body.count(": heartbeat") >= 1
    assert events[-1].type == "error"
    assert events[-1].code == "STREAM_TIMEOUT"


def test_client_disconnect_stops_and_closes_the_graph_iterator() -> None:
    closed = Event()

    class DisconnectStreamer:
        def stream_states(
            self,
            *,
            message: str,
            thread_id: str,
            request_id: str,
        ) -> Iterator[SynapseState]:
            del message, thread_id, request_id
            try:
                sleep(0.02)
                if False:
                    yield cast(SynapseState, {})  # pragma: no cover
            finally:
                closed.set()

    service = SSEStreamService(
        DisconnectStreamer(),
        timeout_seconds=1,
        heartbeat_seconds=0.1,
    )

    async def collect_until_disconnect() -> list[str]:
        checks = 0

        async def disconnected() -> bool:
            nonlocal checks
            checks += 1
            return checks >= 1

        return [
            chunk
            async for chunk in service.stream(
                message="Hello",
                thread_id="thread-disconnect",
                request_id="request-disconnect",
                correlation_id="correlation-disconnect",
                is_disconnected=disconnected,
            )
        ]

    chunks = asyncio.run(collect_until_disconnect())
    assert len(chunks) == 1
    assert "request.started" in chunks[0]
    assert closed.wait(timeout=0.2)
