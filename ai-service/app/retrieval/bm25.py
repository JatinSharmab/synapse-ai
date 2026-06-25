from rank_bm25 import BM25Okapi

from app.models.documents import DocumentChunk
from app.retrieval.models import RankedChunk
from app.retrieval.query import tokenize


class BM25Retriever:
    """Build a small in-process lexical index over authoritative stored chunks."""

    def search(
        self,
        query: str,
        chunks: list[DocumentChunk],
        *,
        top_k: int,
    ) -> list[RankedChunk]:
        query_tokens = tokenize(query)
        if not query_tokens or not chunks:
            return []

        tokenized_corpus = [tokenize(chunk.text) for chunk in chunks]
        index = BM25Okapi(tokenized_corpus)
        scores = index.get_scores(query_tokens)
        query_terms = set(query_tokens)
        scored = [
            (chunk, float(scores[position]))
            for position, chunk in enumerate(chunks)
            if query_terms.intersection(tokenized_corpus[position])
        ]
        scored.sort(key=lambda item: (-item[1], item[0].chunk_id))
        return [
            RankedChunk(chunk=chunk, score=score, rank=rank)
            for rank, (chunk, score) in enumerate(scored[:top_k], start=1)
        ]
