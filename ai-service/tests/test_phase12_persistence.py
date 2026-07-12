from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

import httpx
import mongomock
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.models.documents import DocumentChunk, DocumentRecord, StoredDocumentChunk
from app.providers.mock import MockProvider
from app.repositories.metadata import LocalMetadataRepository
from app.repositories.mongo import MongoMetadataRepository
from app.schemas.inference import InferenceMetadata
from app.services.persistence_factory import PersistenceBundle
from app.storage.base import FakeObjectStorage
from app.storage.supabase import SupabaseObjectStorage
from app.vectorstores.base import InMemoryVectorStore

SAMPLE_PDF = (
    Path(__file__).resolve().parents[2] / "sample-data" / "documents" / "synapse-policy.pdf"
)


def _settings() -> Settings:
    return Settings(
        app_env="test",
        ai_provider="mock",
        document_chunk_max_tokens=80,
        document_chunk_min_tokens=10,
        document_chunk_overlap_tokens=8,
    )


def _stored_chunk() -> tuple[DocumentRecord, StoredDocumentChunk]:
    now = datetime.now(UTC)
    text = "Durable embeddings rebuild an ephemeral active index."
    document = DocumentRecord(
        document_id="doc_durable",
        filename="durable.pdf",
        page_count=1,
        chunk_count=1,
        checksum="a" * 64,
        created_at=now,
        ocr_required=False,
    )
    chunk = DocumentChunk(
        document_id=document.document_id,
        filename=document.filename,
        page_number=1,
        chunk_id="chunk_durable",
        chunk_index=0,
        text=text,
        token_estimate=8,
        checksum=sha256(text.encode()).hexdigest(),
        created_at=now,
    )
    return document, StoredDocumentChunk(
        chunk=chunk,
        embedding=[0.1, 0.2, 0.3],
        embedding_metadata=InferenceMetadata(
            provider="mock",
            operation="embed",
            model="mock-embed-v1",
            latency_ms=1,
            retry_count=0,
        ),
    )


def test_startup_rebuilds_missing_index_from_durable_vectors() -> None:
    metadata = LocalMetadataRepository.in_memory()
    vectors = InMemoryVectorStore()
    objects = FakeObjectStorage()
    document, chunk = _stored_chunk()
    metadata.save_document(document, [chunk])
    app = create_app(
        _settings(),
        MockProvider(),
        persistence=PersistenceBundle(metadata=metadata, objects=objects, vectors=vectors),
    )

    with TestClient(app) as client:
        app.state.readiness.wait()
        health = client.get("/health")
        ready = client.get("/ready")

    assert health.status_code == 200
    assert ready.status_code == 200
    payload = ready.json()
    assert payload["status"] == "ready"
    assert payload["documents"] == {
        "state": "ready",
        "durable_records": 1,
        "indexed_records": 1,
        "rebuilt": True,
        "error": None,
    }
    assert vectors.list_ids("documents") == {"chunk_durable"}


def test_signed_pdf_upload_is_direct_and_authorization_is_one_time() -> None:
    metadata = LocalMetadataRepository.in_memory()
    vectors = InMemoryVectorStore()
    objects = FakeObjectStorage()
    app = create_app(
        _settings(),
        MockProvider(),
        persistence=PersistenceBundle(metadata=metadata, objects=objects, vectors=vectors),
    )
    pdf = SAMPLE_PDF.read_bytes()

    with TestClient(app) as client:
        presign = client.post(
            "/api/v1/uploads/presign",
            json={
                "asset_type": "document",
                "filename": "policy.pdf",
                "content_type": "application/pdf",
                "size_bytes": len(pdf),
            },
        )
        assert presign.status_code == 200
        payload = presign.json()
        assert "service" not in payload["signed_upload_url"]
        objects.put(payload["object_path"], pdf)
        ingested = client.post(
            "/api/v1/documents/from-storage",
            json={"object_path": payload["object_path"]},
        )
        replay = client.post(
            "/api/v1/documents/from-storage",
            json={"object_path": payload["object_path"]},
        )

    assert ingested.status_code == 201
    assert ingested.json()["filename"] == "policy.pdf"
    assert replay.status_code == 409


def test_mongo_records_retain_embedding_rebuild_fields_without_cloud() -> None:
    client = mongomock.MongoClient()
    repository = MongoMetadataRepository(
        uri="mongodb://unused",
        database_name="test",
        client=client,
    )
    document, chunk = _stored_chunk()
    repository.save_document(document, [chunk])

    raw = client["test"]["metadata_records"].find_one({"kind": "document_chunk"})

    assert raw is not None
    assert raw["embedding"] == [0.1, 0.2, 0.3]
    assert raw["embedding_model"] == "mock-embed-v1"
    assert raw["checksum"] == chunk.chunk.checksum
    restored = repository.list_document_chunks()[0]
    assert restored.chunk.chunk_id == chunk.chunk.chunk_id
    assert restored.embedding == chunk.embedding
    assert restored.embedding_metadata == chunk.embedding_metadata


def test_supabase_presign_uses_server_credential_but_never_returns_it() -> None:
    observed: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["authorization"] = request.headers["authorization"]
        signed_path = "/".join(
            [
                "storage/v1/object/upload/sign/synapse-assets",
                "documents/id/a.pdf?token=signed",
            ]
        )
        return httpx.Response(
            200,
            json={"url": f"/{signed_path}"},
        )

    storage = SupabaseObjectStorage(
        project_url="https://project.supabase.co",
        service_role_key="service-secret",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    result = storage.create_signed_upload("documents/id/a.pdf")

    assert observed["authorization"] == "Bearer service-secret"
    assert "service-secret" not in str(result.url)
    assert "token=signed" in str(result.url)
