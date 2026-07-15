from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from app.models.persistence import AssetType
from app.services.filenames import safe_upload_filename


class PresignUploadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_type: AssetType
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=100)
    size_bytes: int = Field(gt=0)

    @field_validator("filename")
    @classmethod
    def filename_must_be_plain(cls, value: str) -> str:
        return safe_upload_filename(value, require_plain=True)


class PresignUploadResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    signed_upload_url: HttpUrl
    object_path: str
    expires_at: datetime


class StoredObjectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    object_path: str = Field(
        min_length=3,
        max_length=512,
        pattern=r"^(documents|videos)/[a-f0-9]{32}/[^/]+$",
    )

    @field_validator("object_path")
    @classmethod
    def object_path_must_be_plain(cls, value: str) -> str:
        filename = value.rsplit("/", maxsplit=1)[-1]
        safe_upload_filename(filename, require_plain=True)
        return value
