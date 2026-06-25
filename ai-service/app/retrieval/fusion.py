from collections.abc import Sequence

from app.retrieval.models import FusedChunk, RankedChunk

DEFAULT_RRF_K = 60


def reciprocal_rank_fusion(
    vector_candidates: Sequence[RankedChunk],
    bm25_candidates: Sequence[RankedChunk],
    *,
    rrf_k: int = DEFAULT_RRF_K,
) -> list[FusedChunk]:
    if rrf_k < 1:
        raise ValueError("RRF rank constant must be positive")

    chunks = {item.chunk.chunk_id: item.chunk for item in [*vector_candidates, *bm25_candidates]}
    vector_ranks = {item.chunk.chunk_id: item.rank for item in vector_candidates}
    bm25_ranks = {item.chunk.chunk_id: item.rank for item in bm25_candidates}
    fused: list[FusedChunk] = []
    for chunk_id, chunk in chunks.items():
        vector_rank = vector_ranks.get(chunk_id)
        bm25_rank = bm25_ranks.get(chunk_id)
        score = sum(1.0 / (rrf_k + rank) for rank in (vector_rank, bm25_rank) if rank is not None)
        fused.append(
            FusedChunk(
                chunk=chunk,
                score=score,
                vector_rank=vector_rank,
                bm25_rank=bm25_rank,
            )
        )
    return sorted(
        fused,
        key=lambda item: (
            -item.score,
            min(item.vector_rank or 10**9, item.bm25_rank or 10**9),
            item.chunk.chunk_id,
        ),
    )
