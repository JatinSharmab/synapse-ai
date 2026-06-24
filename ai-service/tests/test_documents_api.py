from pathlib import Path
from typing import cast

import pymupdf
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.document_rag import DocumentRAGService

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
        document_min_similarity_score=0.25,
    )


def _upload_sample(client: TestClient) -> dict[str, object]:
    response = client.post(
        "/api/v1/documents",
        files={"file": ("synapse-policy.pdf", SAMPLE_PDF.read_bytes(), "application/pdf")},
    )
    assert response.status_code == 201
    return cast(dict[str, object], response.json())


def _blank_pdf() -> bytes:
    document = pymupdf.open()  # type: ignore[no-untyped-call]
    document.new_page()
    data = document.tobytes()  # type: ignore[no-untyped-call]
    document.close()  # type: ignore[no-untyped-call]
    return cast(bytes, data)


def test_valid_pdf_is_ingested_and_listed() -> None:
    app = create_app(_settings())

    with TestClient(app) as client:
        uploaded = _upload_sample(client)
        listed = client.get("/api/v1/documents")

    assert uploaded["filename"] == "synapse-policy.pdf"
    assert uploaded["page_count"] == 3
    assert uploaded["chunk_count"] == 3
    assert uploaded["ocr_required"] is False
    assert listed.status_code == 200
    assert listed.json()["documents"] == [uploaded]


def test_invalid_and_masquerading_files_are_rejected() -> None:
    app = create_app(_settings())

    with TestClient(app) as client:
        invalid_pdf = client.post(
            "/api/v1/documents",
            files={
                "file": (
                    "broken.pdf",
                    b"%PDF-1.7\nnot a structurally valid document\n%%EOF",
                    "application/pdf",
                )
            },
        )
        masquerading = client.post(
            "/api/v1/documents",
            files={"file": ("pretend.pdf", b"plain text", "application/pdf")},
        )
        wrong_extension = client.post(
            "/api/v1/documents",
            files={"file": ("notes.txt", SAMPLE_PDF.read_bytes(), "text/plain")},
        )

    assert invalid_pdf.status_code == 422
    assert invalid_pdf.json()["error"]["code"] == "INVALID_PDF"
    assert masquerading.status_code == 415
    assert masquerading.json()["error"]["code"] == "INVALID_PDF_MEDIA_TYPE"
    assert wrong_extension.status_code == 415


def test_chunk_metadata_and_page_provenance_are_complete() -> None:
    app = create_app(_settings())

    with TestClient(app) as client:
        uploaded = _upload_sample(client)

    service = cast(DocumentRAGService, app.state.document_service)
    document_id = cast(str, uploaded["document_id"])
    chunks = service.get_chunks(document_id)

    assert [chunk.chunk_index for chunk in chunks] == [0, 1, 2]
    assert {chunk.page_number for chunk in chunks} == {1, 2, 3}
    assert all(chunk.document_id == document_id for chunk in chunks)
    assert all(chunk.filename == "synapse-policy.pdf" for chunk in chunks)
    assert all(chunk.text and chunk.token_estimate > 0 for chunk in chunks)
    assert all(len(chunk.checksum) == 64 for chunk in chunks)
    assert all(chunk.created_at == chunks[0].created_at for chunk in chunks)
    assert "ORION-30" in next(chunk.text for chunk in chunks if chunk.page_number == 2)


def test_pdf_without_extractable_text_requires_ocr_without_running_it() -> None:
    app = create_app(_settings())

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/documents",
            files={"file": ("scan.pdf", _blank_pdf(), "application/pdf")},
        )

    assert response.status_code == 201
    assert response.json()["ocr_required"] is True
    assert response.json()["chunk_count"] == 0


def test_document_search_returns_page_two_with_trusted_provenance() -> None:
    app = create_app(_settings())

    with TestClient(app) as client:
        uploaded = _upload_sample(client)
        response = client.post(
            "/api/v1/search/documents",
            json={
                "query": "What is the refund window and approval reference code?",
                "top_k": 3,
            },
        )

    assert response.status_code == 200
    result = response.json()["results"][0]
    assert result["document_id"] == uploaded["document_id"]
    assert result["filename"] == "synapse-policy.pdf"
    assert result["page"] == 2
    assert result["chunk_id"]
    assert "30 calendar days" in result["text"]
    assert "ORION-30" in result["text"]
    assert 0 <= result["similarity_score"] <= 1


def test_graph_citations_are_resolved_from_retrieved_chunk_metadata() -> None:
    app = create_app(_settings())

    with TestClient(app) as client:
        uploaded = _upload_sample(client)
        response = client.post(
            "/api/v1/chat/invoke",
            json={
                "message": "Find the refund policy in my documents.",
                "thread_id": "citation-provenance",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert "30 calendar days" in payload["final_response"]
    assert len(payload["citations"]) == 1
    citation = payload["citations"][0]
    assert citation["document_id"] == uploaded["document_id"]
    assert citation["filename"] == uploaded["filename"]
    assert citation["page"] == 2

    service = cast(DocumentRAGService, app.state.document_service)
    trusted_chunks = {
        chunk.chunk_id: chunk for chunk in service.get_chunks(cast(str, uploaded["document_id"]))
    }
    trusted = trusted_chunks[citation["chunk_id"]]
    assert trusted.document_id == citation["document_id"]
    assert trusted.filename == citation["filename"]
    assert trusted.page_number == citation["page"]


def test_delete_removes_document_and_searchable_chunks() -> None:
    app: FastAPI = create_app(_settings())

    with TestClient(app) as client:
        uploaded = _upload_sample(client)
        document_id = cast(str, uploaded["document_id"])
        deleted = client.delete(f"/api/v1/documents/{document_id}")
        listed = client.get("/api/v1/documents")
        searched = client.post(
            "/api/v1/search/documents",
            json={"query": "ORION-30"},
        )

    assert deleted.status_code == 204
    assert listed.json() == {"documents": []}
    assert searched.json()["results"] == []
