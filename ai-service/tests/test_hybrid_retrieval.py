from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.models.documents import DocumentChunk
from app.retrieval.bm25 import BM25Retriever
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.models import FusedChunk, RankedChunk
from app.retrieval.query import normalize_query
from app.retrieval.reranker import LocalCoverageReranker

SAMPLE_PDF = (
    Path(__file__).resolve().parents[2] / "sample-data" / "documents" / "synapse-policy.pdf"
)


def _chunk(chunk_id: str, text: str, chunk_index: int) -> DocumentChunk:
    return DocumentChunk(
        document_id="doc_ranking",
        filename="ranking.pdf",
        page_number=chunk_index + 1,
        chunk_id=chunk_id,
        chunk_index=chunk_index,
        text=text,
        token_estimate=len(text.split()),
        checksum="a" * 64,
        created_at=datetime(2026, 9, 2, tzinfo=UTC),
    )


def test_query_rewrite_removes_request_scaffolding_and_source_suffix() -> None:
    assert normalize_query("  Please find the ORION-30 policy in my documents. ") == (
        "the orion-30 policy"
    )


def test_bm25_ranks_exact_identifier_above_generic_content() -> None:
    chunks = [
        _chunk("generic", "Refund requests need standard approval.", 0),
        _chunk("exact", "Approved refunds use the exact reference ORION-30.", 1),
        _chunk("unrelated", "Commuter enrollment starts next month.", 2),
    ]

    results = BM25Retriever().search("ORION-30 approval reference", chunks, top_k=3)

    assert [item.chunk.chunk_id for item in results] == ["exact", "generic"]
    assert results[0].score > results[1].score


def test_reciprocal_rank_fusion_rewards_candidates_present_in_both_lists() -> None:
    vector_only = _chunk("vector_only", "Dense-only candidate", 0)
    shared = _chunk("shared", "Candidate found by both retrievers", 1)
    lexical_only = _chunk("lexical_only", "Lexical-only candidate", 2)
    vector = [
        RankedChunk(chunk=vector_only, score=0.9, rank=1),
        RankedChunk(chunk=shared, score=0.8, rank=2),
    ]
    lexical = [
        RankedChunk(chunk=lexical_only, score=4.0, rank=1),
        RankedChunk(chunk=shared, score=3.0, rank=2),
    ]

    fused = reciprocal_rank_fusion(vector, lexical)

    assert fused[0].chunk.chunk_id == "shared"
    assert fused[0].vector_rank == 2
    assert fused[0].bm25_rank == 2
    assert fused[0].score > fused[1].score


def test_local_reranker_promotes_exact_identifier_coverage() -> None:
    generic = _chunk("generic", "Refund approval policies and standard forms.", 0)
    exact = _chunk("exact", "Use reference ORION-30 for approved refunds.", 1)
    candidates = [
        FusedChunk(chunk=generic, score=0.04, vector_rank=1, bm25_rank=1),
        FusedChunk(chunk=exact, score=0.02, vector_rank=4, bm25_rank=2),
    ]

    reranked = LocalCoverageReranker().rerank(
        "refund approval reference ORION-30",
        candidates,
        top_k=2,
    )

    assert reranked[0].chunk.chunk_id == "exact"
    assert reranked[0].score > reranked[1].score


def test_retrieval_debug_route_exists_only_when_enabled() -> None:
    disabled_app = create_app(Settings(app_env="test", ai_provider="mock", debug=False))
    enabled_app = create_app(
        Settings(
            app_env="test",
            ai_provider="mock",
            debug=True,
            document_chunk_max_tokens=80,
            document_chunk_min_tokens=10,
            document_chunk_overlap_tokens=8,
        )
    )

    with TestClient(disabled_app) as disabled_client:
        disabled = disabled_client.post(
            "/api/v1/debug/retrieval/documents",
            json={"query": "refund policy"},
        )
        assert (
            "/api/v1/debug/retrieval/documents"
            not in disabled_client.get("/openapi.json").json()["paths"]
        )

    with TestClient(enabled_app) as enabled_client:
        uploaded = enabled_client.post(
            "/api/v1/documents",
            files={"file": ("synapse-policy.pdf", SAMPLE_PDF.read_bytes(), "application/pdf")},
        )
        debug = enabled_client.post(
            "/api/v1/debug/retrieval/documents",
            json={"query": "Find the refund policy in my documents.", "top_k": 3},
        )
        public = enabled_client.post(
            "/api/v1/search/documents",
            json={"query": "Find the refund policy in my documents.", "top_k": 3},
        )

    assert disabled.status_code == 404
    assert uploaded.status_code == 201
    assert debug.status_code == 200
    payload = debug.json()
    assert payload["normalized_query"] == "the refund policy"
    assert payload["mode"] == "hybrid"
    assert payload["vector_candidates"]
    assert payload["bm25_candidates"]
    assert payload["fused_candidates"]
    assert payload["reranked_candidates"]
    assert payload["final_context"][0]["page"] == 2
    assert set(public.json()) == {"results", "inference_metadata"}
