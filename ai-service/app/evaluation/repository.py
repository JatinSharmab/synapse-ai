import os
from abc import ABC, abstractmethod
from pathlib import Path
from threading import RLock
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from pymongo import DESCENDING, MongoClient
from pymongo.collection import Collection

from app.core.config import Settings
from app.evaluation.models import EvaluationSummary


class EvaluationSummaryRepository(ABC):
    @abstractmethod
    def save(self, summary: EvaluationSummary) -> None: ...

    @abstractmethod
    def recent(self, limit: int) -> list[EvaluationSummary]: ...


class InMemoryEvaluationSummaryRepository(EvaluationSummaryRepository):
    def __init__(self) -> None:
        self._summaries: dict[str, EvaluationSummary] = {}
        self._lock = RLock()

    def save(self, summary: EvaluationSummary) -> None:
        with self._lock:
            if summary.run_id in self._summaries:
                raise ValueError("evaluation run identifier already exists")
            self._summaries[summary.run_id] = summary

    def recent(self, limit: int) -> list[EvaluationSummary]:
        with self._lock:
            return sorted(
                self._summaries.values(),
                key=lambda item: (item.timestamp, item.run_id),
                reverse=True,
            )[:limit]


class _EvaluationSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summaries: list[EvaluationSummary] = Field(default_factory=list)


class JsonEvaluationSummaryRepository(InMemoryEvaluationSummaryRepository):
    """Atomic local JSON storage used when MongoDB is not configured."""

    def __init__(self, path: Path) -> None:
        self._path = path
        super().__init__()
        self._load()

    def save(self, summary: EvaluationSummary) -> None:
        with self._lock:
            super().save(summary)
            try:
                self._flush()
            except Exception:
                self._summaries.pop(summary.run_id, None)
                raise

    def _load(self) -> None:
        if not self._path.exists():
            return
        snapshot = _EvaluationSnapshot.model_validate_json(
            self._path.read_text(encoding="utf-8")
        )
        self._summaries = {item.run_id: item for item in snapshot.summaries}

    def _flush(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        snapshot = _EvaluationSnapshot(summaries=list(self._summaries.values()))
        temporary_path = self._path.with_suffix(f"{self._path.suffix}.tmp")
        temporary_path.write_text(snapshot.model_dump_json(indent=2), encoding="utf-8")
        os.replace(temporary_path, self._path)


class MongoEvaluationSummaryRepository(EvaluationSummaryRepository):
    """MongoDB-backed evaluation summary storage; raw prompts and answers are not persisted."""

    def __init__(
        self,
        *,
        uri: str,
        database_name: str,
        connect_timeout_ms: int = 5_000,
        client: Any | None = None,
    ) -> None:
        self._client = client or MongoClient(
            uri,
            connect=False,
            connectTimeoutMS=connect_timeout_ms,
            serverSelectionTimeoutMS=connect_timeout_ms,
        )
        self._records: Collection[dict[str, Any]] = self._client[database_name][
            "evaluation_summaries"
        ]
        self._indexes_ready = False
        self._lock = RLock()

    def _ensure_indexes(self) -> None:
        with self._lock:
            if self._indexes_ready:
                return
            self._records.create_index("run_id", unique=True, name="run_id_unique")
            self._records.create_index(
                [("timestamp", DESCENDING)], name="evaluation_timestamp_desc"
            )
            self._indexes_ready = True

    def save(self, summary: EvaluationSummary) -> None:
        self._ensure_indexes()
        self._records.insert_one(summary.model_dump(mode="python"))

    def recent(self, limit: int) -> list[EvaluationSummary]:
        self._ensure_indexes()
        cursor = self._records.find({}, {"_id": 0}).sort("timestamp", DESCENDING).limit(limit)
        return [EvaluationSummary.model_validate(item) for item in cursor]


def create_evaluation_repository(settings: Settings) -> EvaluationSummaryRepository:
    if settings.app_env == "test":
        return InMemoryEvaluationSummaryRepository()
    if settings.metadata_backend == "mongo":
        assert settings.mongodb_uri is not None
        return MongoEvaluationSummaryRepository(
            uri=settings.mongodb_uri.get_secret_value(),
            database_name=settings.mongodb_database,
            connect_timeout_ms=int(settings.mongodb_connect_timeout_seconds * 1_000),
        )
    return JsonEvaluationSummaryRepository(settings.evaluation_summary_path)
