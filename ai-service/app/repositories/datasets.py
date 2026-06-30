import os
from abc import ABC, abstractmethod
from pathlib import Path
from threading import RLock

from pydantic import BaseModel, ConfigDict, Field

from app.models.datasets import DatasetRecord, StoredDataset


class DatasetRepository(ABC):
    @abstractmethod
    def save(self, dataset: StoredDataset) -> None:
        """Persist an authoritative CSV dataset."""

    @abstractmethod
    def list_datasets(self) -> list[DatasetRecord]:
        """Return dataset metadata in stable newest-first order."""

    @abstractmethod
    def get(self, dataset_id: str) -> StoredDataset | None:
        """Return trusted metadata and rows for an opaque identifier."""

    @abstractmethod
    def delete(self, dataset_id: str) -> bool:
        """Delete a dataset, returning whether it existed."""


class InMemoryDatasetRepository(DatasetRepository):
    def __init__(self) -> None:
        self._datasets: dict[str, StoredDataset] = {}
        self._lock = RLock()

    def save(self, dataset: StoredDataset) -> None:
        with self._lock:
            if dataset.dataset.dataset_id in self._datasets:
                raise ValueError("dataset identifier already exists")
            self._datasets[dataset.dataset.dataset_id] = dataset

    def list_datasets(self) -> list[DatasetRecord]:
        with self._lock:
            return sorted(
                (item.dataset for item in self._datasets.values()),
                key=lambda item: (item.created_at, item.dataset_id),
                reverse=True,
            )

    def get(self, dataset_id: str) -> StoredDataset | None:
        with self._lock:
            return self._datasets.get(dataset_id)

    def delete(self, dataset_id: str) -> bool:
        with self._lock:
            return self._datasets.pop(dataset_id, None) is not None


class _DatasetSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    datasets: list[StoredDataset] = Field(default_factory=list)


class JsonDatasetRepository(InMemoryDatasetRepository):
    """Atomic JSON persistence for bounded local-development CSV datasets."""

    def __init__(self, path: Path) -> None:
        self._path = path
        super().__init__()
        self._load()

    def save(self, dataset: StoredDataset) -> None:
        with self._lock:
            super().save(dataset)
            try:
                self._flush()
            except Exception:
                super().delete(dataset.dataset.dataset_id)
                raise

    def delete(self, dataset_id: str) -> bool:
        with self._lock:
            current = self._datasets.get(dataset_id)
            if not super().delete(dataset_id):
                return False
            try:
                self._flush()
            except Exception:
                if current is not None:
                    self._datasets[dataset_id] = current
                raise
            return True

    def _load(self) -> None:
        if not self._path.exists():
            return
        snapshot = _DatasetSnapshot.model_validate_json(self._path.read_text(encoding="utf-8"))
        self._datasets = {item.dataset.dataset_id: item for item in snapshot.datasets}

    def _flush(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        snapshot = _DatasetSnapshot(datasets=list(self._datasets.values()))
        temporary_path = self._path.with_suffix(f"{self._path.suffix}.tmp")
        temporary_path.write_text(snapshot.model_dump_json(indent=2), encoding="utf-8")
        os.replace(temporary_path, self._path)
