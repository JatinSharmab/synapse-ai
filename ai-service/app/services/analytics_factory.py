from app.core.config import Settings
from app.providers.base import LLMProvider
from app.repositories.datasets import (
    DatasetRepository,
    InMemoryDatasetRepository,
    JsonDatasetRepository,
)
from app.services.analytics_executor import AnalyticsExecutor
from app.services.analytics_service import AnalyticsService
from app.services.csv_parser import CsvParser


def create_analytics_service(
    settings: Settings,
    provider: LLMProvider,
    *,
    repository: DatasetRepository | None = None,
) -> AnalyticsService:
    active_repository = repository or (
        InMemoryDatasetRepository()
        if settings.app_env == "test"
        else JsonDatasetRepository(settings.dataset_metadata_path)
    )
    return AnalyticsService(
        provider=provider,
        repository=active_repository,
        parser=CsvParser(
            max_rows=settings.dataset_max_rows,
            max_columns=settings.dataset_max_columns,
        ),
        executor=AnalyticsExecutor(max_result_rows=settings.analytics_max_result_rows),
        max_upload_bytes=settings.dataset_max_upload_bytes,
        max_result_rows=settings.analytics_max_result_rows,
    )
