from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.inference import InferenceMetadata


class StrictDocumentModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DocumentRecord(StrictDocumentModel):
    document_id: str = Field(min_length=1)
    filename: str = Field(min_length=1, max_length=255)
    page_count: int = Field(ge=1)
    chunk_count: int = Field(ge=0)
    checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    created_at: datetime
    ocr_required: bool


class DocumentChunk(StrictDocumentModel):
    document_id: str = Field(min_length=1)
    filename: str = Field(min_length=1, max_length=255)
    page_number: int = Field(ge=1)
    chunk_id: str = Field(min_length=1)
    chunk_index: int = Field(ge=0)
    text: str = Field(min_length=1)
    token_estimate: int = Field(ge=1)
    checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    created_at: datetime


class StoredDocumentChunk(StrictDocumentModel):
    chunk: DocumentChunk
    embedding: list[float] = Field(min_length=1)
    embedding_metadata: InferenceMetadata | None = None


class DocumentSearchResult(StrictDocumentModel):
    text: str
    document_id: str
    filename: str
    page: int = Field(ge=1)
    chunk_id: str
    similarity_score: float = Field(ge=0, le=1)
