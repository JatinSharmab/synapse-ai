from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Protocol
from uuid import uuid4

from app.models.datasets import DatasetRecord, StoredDataset
from app.prompts.analytics import ANALYTICS_SYSTEM_PROMPT, build_analytics_user_prompt
from app.providers.base import LLMProvider
from app.repositories.datasets import DatasetRepository
from app.schemas.analytics import AnalyticsOperation, AnalyticsPlan, AnalyticsResult
from app.schemas.inference import InferenceMetadata
from app.services.analytics_errors import (
    AnalyticsOperationError,
    AnalyticsStorageError,
    DatasetNotFoundError,
    DatasetTooLargeError,
)
from app.services.analytics_executor import AnalyticsExecutor
from app.services.csv_parser import CsvParser


@dataclass(frozen=True)
class AnalyticsExecution:
    result: AnalyticsResult
    inference_metadata: InferenceMetadata | None = None


class AnalyticsTool(Protocol):
    def plan_and_execute(self, query: str) -> AnalyticsExecution: ...


class EmptyAnalyticsTool:
    def plan_and_execute(self, query: str) -> AnalyticsExecution:
        del query
        raise DatasetNotFoundError("No CSV dataset has been uploaded.")


class AnalyticsService:
    def __init__(
        self,
        *,
        provider: LLMProvider,
        repository: DatasetRepository,
        parser: CsvParser,
        executor: AnalyticsExecutor,
        max_upload_bytes: int,
        max_result_rows: int,
    ) -> None:
        self._provider = provider
        self._repository = repository
        self._parser = parser
        self._executor = executor
        self._max_upload_bytes = max_upload_bytes
        self._max_result_rows = max_result_rows

    def ingest_csv(self, *, filename: str, content_type: str | None, data: bytes) -> DatasetRecord:
        if len(data) > self._max_upload_bytes:
            raise DatasetTooLargeError("The uploaded CSV exceeds the configured size limit.")
        parsed = self._parser.parse(filename=filename, content_type=content_type, data=data)
        dataset = DatasetRecord(
            dataset_id=f"dataset_{uuid4().hex}",
            filename=parsed.filename,
            columns=parsed.columns,
            row_count=len(parsed.rows),
            checksum=sha256(data).hexdigest(),
            created_at=datetime.now(UTC),
        )
        try:
            self._repository.save(StoredDataset(dataset=dataset, rows=parsed.rows))
        except Exception as error:
            raise AnalyticsStorageError("Dataset metadata could not be persisted.") from error
        return dataset

    def list_datasets(self) -> list[DatasetRecord]:
        return self._repository.list_datasets()

    def delete_dataset(self, dataset_id: str) -> None:
        if not self._repository.delete(dataset_id):
            raise DatasetNotFoundError("The requested dataset does not exist.")

    def execute(self, dataset_id: str, operation: AnalyticsOperation) -> AnalyticsResult:
        dataset = self._repository.get(dataset_id)
        if dataset is None:
            raise DatasetNotFoundError("The requested dataset does not exist.")
        return self._executor.execute(dataset, operation)

    def plan_and_execute(self, query: str) -> AnalyticsExecution:
        datasets = self.list_datasets()
        if not datasets:
            raise DatasetNotFoundError("No CSV dataset has been uploaded.")
        planned = self._provider.generate_structured(
            system_prompt=ANALYTICS_SYSTEM_PROMPT,
            user_prompt=build_analytics_user_prompt(query, datasets, self._max_result_rows),
            response_model=AnalyticsPlan,
        )
        if planned.value.dataset_id not in {item.dataset_id for item in datasets}:
            raise AnalyticsOperationError("The analytics plan selected an unknown dataset.")
        result = self.execute(planned.value.dataset_id, planned.value.operation)
        return AnalyticsExecution(result=result, inference_metadata=planned.metadata)
