from app.retrieval.models import RerankedChunk


class ContextSelector:
    """Select a bounded, provenance-complete, de-duplicated final context."""

    def select(
        self,
        candidates: list[RerankedChunk],
        *,
        top_k: int,
    ) -> list[RerankedChunk]:
        selected: list[RerankedChunk] = []
        seen: set[str] = set()
        for candidate in candidates:
            chunk = candidate.chunk
            if chunk.chunk_id in seen:
                continue
            if (
                not all((chunk.document_id, chunk.filename, chunk.chunk_id))
                or chunk.page_number < 1
            ):
                continue
            seen.add(chunk.chunk_id)
            selected.append(candidate)
            if len(selected) == top_k:
                break
        return selected
