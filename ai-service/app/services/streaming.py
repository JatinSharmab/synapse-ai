import asyncio
import re
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from contextlib import suppress
from dataclasses import dataclass
from threading import Event, Thread
from time import monotonic
from typing import Literal, Protocol

from app.models.domain import GuardrailDecision, Route
from app.models.state import SynapseState
from app.schemas.streaming import (
    GenerationStartedEvent,
    GenerationTokenEvent,
    GenUICreatedEvent,
    GuardrailCompletedEvent,
    RequestStartedEvent,
    ResponseCompletedEvent,
    RetrievalCompletedEvent,
    RetrievalStartedEvent,
    RouteSelectedEvent,
    StreamErrorEvent,
    StreamEvent,
)

TOKEN_CHUNK_PATTERN = re.compile(r"\S+\s*")
RETRIEVAL_ROUTES = {Route.DOCUMENT_SEARCH, Route.VIDEO_SEARCH}


class StateStreamer(Protocol):
    def stream_states(
        self,
        *,
        message: str,
        thread_id: str,
        request_id: str,
    ) -> Iterator[SynapseState]: ...


@dataclass(frozen=True)
class WorkerMessage:
    kind: Literal["state", "error", "done"]
    state: SynapseState | None = None


class SSEStreamService:
    def __init__(
        self,
        orchestrator: StateStreamer,
        *,
        timeout_seconds: float,
        heartbeat_seconds: float,
    ) -> None:
        self._orchestrator = orchestrator
        self._timeout_seconds = timeout_seconds
        self._heartbeat_seconds = heartbeat_seconds

    async def stream(
        self,
        *,
        message: str,
        thread_id: str,
        request_id: str,
        correlation_id: str,
        is_disconnected: Callable[[], Awaitable[bool]],
    ) -> AsyncIterator[str]:
        sequence = 0
        started_at = monotonic()

        def event_frame(event: StreamEvent) -> str:
            return f"id: {event.sequence}\nevent: {event.type}\ndata: {event.model_dump_json()}\n\n"

        def event_fields() -> dict[str, str | int]:
            nonlocal sequence
            sequence += 1
            return {
                "request_id": request_id,
                "correlation_id": correlation_id,
                "sequence": sequence,
            }

        yield event_frame(
            RequestStartedEvent(
                **event_fields(),
                thread_id=thread_id,
            )
        )

        queue: asyncio.Queue[WorkerMessage] = asyncio.Queue()
        stop_requested = Event()
        loop = asyncio.get_running_loop()

        def publish(worker_message: WorkerMessage) -> None:
            with suppress(RuntimeError):
                loop.call_soon_threadsafe(queue.put_nowait, worker_message)

        def run_graph() -> None:
            try:
                snapshots = self._orchestrator.stream_states(
                    message=message,
                    thread_id=thread_id,
                    request_id=request_id,
                )
                try:
                    for snapshot in snapshots:
                        if stop_requested.is_set():
                            break
                        publish(WorkerMessage(kind="state", state=snapshot))
                finally:
                    close = getattr(snapshots, "close", None)
                    if callable(close):
                        close()
            except Exception:  # normalized below; never stream provider internals
                publish(WorkerMessage(kind="error"))
            finally:
                publish(WorkerMessage(kind="done"))

        worker = Thread(target=run_graph, name=f"synapse-stream-{request_id}", daemon=True)
        worker.start()
        final_state: SynapseState | None = None
        emitted_route = False
        emitted_retrieval_started = False
        emitted_retrieval_completed = False
        emitted_generation_started = False
        retrieval_started_at = started_at
        last_heartbeat_at = started_at

        try:
            while True:
                if await is_disconnected():
                    return
                elapsed = monotonic() - started_at
                if elapsed >= self._timeout_seconds:
                    yield event_frame(
                        StreamErrorEvent(
                            **event_fields(),
                            code="STREAM_TIMEOUT",
                            message="The AI stream exceeded its configured time limit.",
                            retryable=True,
                        )
                    )
                    return

                heartbeat_remaining = self._heartbeat_seconds - (monotonic() - last_heartbeat_at)
                wait_seconds = min(
                    1.0,
                    max(0.01, heartbeat_remaining),
                    self._timeout_seconds - elapsed,
                )
                try:
                    worker_message = await asyncio.wait_for(queue.get(), timeout=wait_seconds)
                except TimeoutError:
                    if monotonic() - last_heartbeat_at >= self._heartbeat_seconds:
                        yield ": heartbeat\n\n"
                        last_heartbeat_at = monotonic()
                    continue

                if worker_message.kind == "error":
                    yield event_frame(
                        StreamErrorEvent(
                            **event_fields(),
                            code="STREAM_FAILED",
                            message="The AI service could not complete the streamed request.",
                            retryable=False,
                        )
                    )
                    return
                if worker_message.kind == "done":
                    break

                state = worker_message.state
                if state is None:
                    continue
                route = state["route"]
                if route is not None and not emitted_route:
                    emitted_route = True
                    yield event_frame(RouteSelectedEvent(**event_fields(), route=route))
                    if route in RETRIEVAL_ROUTES:
                        emitted_retrieval_started = True
                        retrieval_started_at = monotonic()
                        yield event_frame(
                            RetrievalStartedEvent(
                                **event_fields(),
                                tool=route.value,
                            )
                        )

                if route is not None and state["tool_results"] and not emitted_generation_started:
                    if emitted_retrieval_started and not emitted_retrieval_completed:
                        emitted_retrieval_completed = True
                        yield event_frame(
                            RetrievalCompletedEvent(
                                **event_fields(),
                                tool=route.value,
                                candidate_count=len(state["retrieved_context"]),
                                latency_ms=_elapsed_ms(retrieval_started_at),
                            )
                        )
                    emitted_generation_started = True
                    yield event_frame(GenerationStartedEvent(**event_fields(), route=route))

                guardrail = state["guardrail_result"]
                if (
                    state["final_response"] is not None
                    and guardrail is not None
                    and guardrail.decision != GuardrailDecision.REWRITE
                ):
                    final_state = state

            if final_state is None:
                yield event_frame(
                    StreamErrorEvent(
                        **event_fields(),
                        code="STREAM_FAILED",
                        message="The AI stream ended before producing a safe response.",
                        retryable=False,
                    )
                )
                return

            guardrail = final_state["guardrail_result"]
            final_response = final_state["final_response"]
            if guardrail is None or final_response is None:
                return
            yield event_frame(
                GuardrailCompletedEvent(
                    **event_fields(),
                    result=guardrail,
                    rewrite_count=final_state["rewrite_count"],
                )
            )
            for index, token in enumerate(TOKEN_CHUNK_PATTERN.findall(final_response)):
                if await is_disconnected():
                    return
                yield event_frame(
                    GenerationTokenEvent(
                        **event_fields(),
                        token=token,
                        index=index,
                    )
                )
            if final_state["genui"]:
                yield event_frame(
                    GenUICreatedEvent(
                        **event_fields(),
                        components=final_state["genui"],
                    )
                )
            yield event_frame(
                ResponseCompletedEvent(
                    **event_fields(),
                    final_response=final_response,
                    citations=final_state["citations"],
                    citation_count=len(final_state["citations"]),
                    latency_ms=_elapsed_ms(started_at),
                    rewrite_count=final_state["rewrite_count"],
                )
            )
        finally:
            stop_requested.set()
            await asyncio.to_thread(worker.join, 0.25)


def _elapsed_ms(started_at: float) -> int:
    return max(0, round((monotonic() - started_at) * 1_000))
