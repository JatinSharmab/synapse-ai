from app.retrieval.models import FusedChunk, RerankedChunk
from app.retrieval.query import normalized_phrase, tokenize


class LocalCoverageReranker:
    """CPU-only reranker using term coverage, identifiers, phrase match, and RRF position."""

    def rerank(
        self,
        query: str,
        candidates: list[FusedChunk],
        *,
        top_k: int,
    ) -> list[RerankedChunk]:
        if not candidates:
            return []
        query_tokens = set(tokenize(query))
        query_identifiers = {
            token for token in query_tokens if any(char.isdigit() for char in token)
        }
        query_phrase = normalized_phrase(query)
        maximum_rrf = max(candidate.score for candidate in candidates)
        results: list[RerankedChunk] = []
        for candidate in candidates:
            document_tokens = set(tokenize(candidate.chunk.text))
            matched = query_tokens.intersection(document_tokens)
            coverage = len(matched) / len(query_tokens) if query_tokens else 0.0
            identifier_coverage = (
                len(query_identifiers.intersection(document_tokens)) / len(query_identifiers)
                if query_identifiers
                else coverage
            )
            exact_phrase = bool(
                query_phrase and query_phrase in normalized_phrase(candidate.chunk.text)
            )
            normalized_rrf = candidate.score / maximum_rrf if maximum_rrf else 0.0
            score = min(
                1.0,
                0.55 * coverage
                + 0.20 * identifier_coverage
                + 0.15 * float(exact_phrase)
                + 0.10 * normalized_rrf,
            )
            results.append(
                RerankedChunk(
                    chunk=candidate.chunk,
                    score=score,
                    rrf_score=candidate.score,
                    query_coverage=coverage,
                    exact_phrase=exact_phrase,
                )
            )
        results.sort(key=lambda item: (-item.score, -item.rrf_score, item.chunk.chunk_id))
        return results[:top_k]
