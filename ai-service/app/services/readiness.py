from collections.abc import Callable
from datetime import UTC, datetime
from threading import RLock, Thread
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.services.document_rag import DocumentRAGService, IndexSyncResult
from app.services.video_rag import VideoRAGService

ReadinessState = Literal["starting", "rebuilding", "ready", "failed"]


class IndexReadiness(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    state: ReadinessState
    durable_records: int = 0
    indexed_records: int = 0
    rebuilt: bool = False
    error: str | None = None


class ReadinessSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    service: str = "synapse-ai-service"
    status: Literal["ready", "not_ready"]
    documents: IndexReadiness
    videos: IndexReadiness
    checked_at: datetime


class RetrievalReadiness:
    """Runs durable-to-active index reconciliation without blocking liveness."""

    def __init__(self, documents: DocumentRAGService, videos: VideoRAGService) -> None:
        initial = IndexReadiness(state="starting")
        self._documents = documents
        self._videos = videos
        self._document_state = initial
        self._video_state = initial
        self._lock = RLock()
        self._thread: Thread | None = None

    def start(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._document_state = IndexReadiness(state="rebuilding")
            self._video_state = IndexReadiness(state="rebuilding")
            self._thread = Thread(target=self._reconcile, daemon=True, name="index-rebuild")
            self._thread.start()

    def snapshot(self) -> ReadinessSnapshot:
        with self._lock:
            documents = self._document_state
            videos = self._video_state
        return ReadinessSnapshot(
            status=(
                "ready" if documents.state == "ready" and videos.state == "ready" else "not_ready"
            ),
            documents=documents,
            videos=videos,
            checked_at=datetime.now(UTC),
        )

    def wait(self, timeout: float = 2) -> None:
        thread = self._thread
        if thread:
            thread.join(timeout)

    def _reconcile(self) -> None:
        self._set_result("documents", self._sync(self._documents.rebuild_index_if_needed))
        self._set_result("videos", self._sync(self._videos.rebuild_index_if_needed))

    @staticmethod
    def _sync(operation: Callable[[], IndexSyncResult]) -> IndexReadiness:
        try:
            result = operation()
            return IndexReadiness(
                state="ready",
                durable_records=result.durable_count,
                indexed_records=result.indexed_count,
                rebuilt=result.rebuilt,
            )
        except Exception:
            return IndexReadiness(
                state="failed",
                error="Index reconciliation failed; inspect server logs.",
            )

    def _set_result(self, target: Literal["documents", "videos"], result: IndexReadiness) -> None:
        with self._lock:
            if target == "documents":
                self._document_state = result
            else:
                self._video_state = result
