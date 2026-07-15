from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class AssetType(StrEnum):
    DOCUMENT = "document"
    VIDEO = "video"


class UploadIntent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    upload_id: str = Field(min_length=1, max_length=128)
    asset_type: AssetType
    object_path: str = Field(min_length=1, max_length=1_024)
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=128)
    size_bytes: int = Field(ge=1)
    created_at: datetime
    expires_at: datetime
    consumed_at: datetime | None = None
