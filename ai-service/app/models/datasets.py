from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class StrictDatasetModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DatasetColumnType(StrEnum):
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"


class DatasetColumn(StrictDatasetModel):
    name: str = Field(min_length=1, max_length=128)
    data_type: DatasetColumnType
    nullable: bool


class DatasetRecord(StrictDatasetModel):
    dataset_id: str
    filename: str = Field(min_length=1, max_length=255)
    columns: list[DatasetColumn] = Field(min_length=1)
    row_count: int = Field(ge=1)
    checksum: str = Field(min_length=64, max_length=64)
    created_at: datetime


class StoredDataset(StrictDatasetModel):
    dataset: DatasetRecord
    rows: list[dict[str, str | None]] = Field(min_length=1)
