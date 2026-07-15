from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Protocol
from uuid import uuid4

from app.models.documents import (
    DocumentChunk,
    DocumentRecord,
    DocumentSearchResult,
    StoredDocumentChunk,
)
from app.providers.base import LLMProvider
from app.repositories.documents import DocumentRepository, public_chunks
from app.retrieval.bm25 import BM25Retriever
from app.retrieval.context import ContextSelector
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.models import (
    RankedChunk,
    RetrievalDebug,
    RetrievalDebugCandidate,
    RetrievalMode,
)
from app.retrieval.query import normalize_query
from app.retrieval.reranker import LocalCoverageReranker
from app.schemas.inference import InferenceMetadata
from app.services.document_errors import DocumentNotFoundError, DocumentStorageError
from app.services.pdf_parser import PdfParser
from app.services.semantic_chunker import SemanticChunker
from app.vectorstores.base import DocumentVectorStore


@dataclass(frozen=True)
class DocumentSearchExecution:
    results: list[DocumentSearchResult]
    inference_metadata: InferenceMetadata | None
    debug: RetrievalDebug | None = None


@dataclass(frozen=True)
class IndexSyncResult:
    durable_count: int
    indexed_count: int
    rebuilt: bool


class DocumentRetriever(Protocol):
    def search(
        self,
        query: str,
        *,
        top_k: int,
        document_ids: list[str] | None = None,
        mode: RetrievalMode = "hybrid",
        include_debug: bool = False,
    ) -> DocumentSearchExecution: ...


class EmptyDocumentRetriever:
    def search(
        self,
        query: str,
        *,
        top_k: int,
        document_ids: list[str] | None = None,
        mode: RetrievalMode = "hybrid",
        include_debug: bool = False,
    ) -> DocumentSearchExecution:
        del query, top_k, document_ids, mode, include_debug
        return DocumentSearchExecution(results=[], inference_metadata=None)


class DocumentRAGService:
    def __init__(
        self,
        *,
        provider: LLMProvider,
        repository: DocumentRepository,
        vector_store: DocumentVectorStore,
        parser: PdfParser,
        chunker: SemanticChunker,
        minimum_extractable_characters: int,
        minimum_similarity_score: float,
        vector_top_k: int,
        bm25_top_k: int,
        rerank_top_k: int,
        final_context_k: int,
    ) -> None:
        self._provider = provider
        self._repository = repository
        self._vector_store = vector_store
        self._parser = parser
        self._chunker = chunker
        self._minimum_extractable_characters = minimum_extractable_characters
        self._minimum_similarity_score = minimum_similarity_score
        self._vector_top_k = vector_top_k
        self._bm25_top_k = bm25_top_k
        self._rerank_top_k = rerank_top_k
        self._final_context_k = final_context_k
        self._bm25 = BM25Retriever()
        self._reranker = LocalCoverageReranker()
        self._context_selector = ContextSelector()

    def ingest_pdf(self, *, filename: str, content_type: str | None, data: bytes) -> DocumentRecord:
        parsed = self._parser.parse(filename=filename, content_type=content_type, data=data)
        document_id = f"doc_{uuid4().hex}"
        created_at = datetime.now(UTC)
        document_checksum = sha256(data).hexdigest()
        ocr_required = parsed.extractable_character_count < self._minimum_extractable_characters
        drafts = [] if ocr_required else self._chunker.chunk_pages(parsed.pages)

        chunks = [
            DocumentChunk(
                document_id=document_id,
                filename=parsed.filename,
                page_number=draft.page_number,
                chunk_id=self._chunk_id(
                    document_id=document_id,
                    page_number=draft.page_number,
                    chunk_index=index,
                    text=draft.text,
                ),
                chunk_index=index,
                text=draft.text,
                token_estimate=draft.token_estimate,
                checksum=sha256(draft.text.encode("utf-8")).hexdigest(),
                created_at=created_at,
            )
            for index, draft in enumerate(drafts)
        ]
        document = DocumentRecord(
            document_id=document_id,
            filename=parsed.filename,
            page_count=parsed.page_count,
            chunk_count=len(chunks),
            checksum=document_checksum,
            created_at=created_at,
            ocr_required=ocr_required,
        )

        embeddings: list[list[float]] = []
        if chunks:
            embedding_result = self._provider.embed(texts=[chunk.text for chunk in chunks])
            embeddings = embedding_result.vectors
            if len(embeddings) != len(chunks) or any(not vector for vector in embeddings):
                raise DocumentStorageError("The embedding provider returned an invalid batch.")
            self._vector_store.upsert(chunks, embeddings)

        stored_chunks = [
            StoredDocumentChunk(
                chunk=chunk,
                embedding=embedding,
                embedding_metadata=embedding_result.metadata,
            )
            for chunk, embedding in zip(chunks, embeddings, strict=True)
        ]
        try:
            self._repository.save(document, stored_chunks)
        except Exception as error:
            if chunks:
                self._vector_store.delete_document(document_id)
            raise DocumentStorageError("Document metadata could not be persisted.") from error
        return document

    def list_documents(self) -> list[DocumentRecord]:
        return self._repository.list_documents()

    def get_chunks(self, document_id: str) -> list[DocumentChunk]:
        return public_chunks(self._repository.get_chunks(document_id))

    def delete_document(self, document_id: str) -> None:
        if self._repository.get_document(document_id) is None:
            raise DocumentNotFoundError("The requested document does not exist.")
        try:
            self._repository.delete(document_id)
            self._vector_store.delete_document(document_id)
        except Exception as error:
            raise DocumentStorageError("The document could not be deleted completely.") from error

    def search(
        self,
        query: str,
        *,
        top_k: int,
        document_ids: list[str] | None = None,
        mode: RetrievalMode = "hybrid",
        include_debug: bool = False,
    ) -> DocumentSearchExecution:
        normalized_query = normalize_query(query)
        stored_chunks = self._repository.list_chunks(document_ids)
        trusted_chunks = {item.chunk.chunk_id: item.chunk for item in stored_chunks}
        vector_candidates: list[RankedChunk] = []
        inference_metadata: InferenceMetadata | None = None

        if trusted_chunks and self._vector_store.count() > 0:
            embedding_result = self._provider.embed(texts=[normalized_query])
            inference_metadata = embedding_result.metadata
            if len(embedding_result.vectors) != 1 or not embedding_result.vectors[0]:
                raise DocumentStorageError(
                    "The embedding provider returned an invalid query vector."
                )
            matches = self._vector_store.query(
                embedding_result.vectors[0],
                top_k=self._vector_top_k,
                document_ids=document_ids,
            )
            for match in matches:
                chunk = trusted_chunks.get(match.chunk_id)
                if chunk is None:
                    continue
                similarity_score = max(0.0, min(1.0, 1.0 - match.distance))
                if similarity_score < self._minimum_similarity_score:
                    continue
                vector_candidates.append(
                    RankedChunk(
                        chunk=chunk,
                        score=similarity_score,
                        rank=len(vector_candidates) + 1,
                    )
                )

        final_limit = min(top_k, self._final_context_k)
        if mode == "vector_only":
            selected_vectors = vector_candidates[:final_limit]
            results = [self._vector_result(item) for item in selected_vectors]
            debug = (
                self._build_debug(
                    query=query,
                    normalized_query=normalized_query,
                    mode=mode,
                    vector_candidates=vector_candidates,
                    final_context=selected_vectors,
                )
                if include_debug
                else None
            )
            return DocumentSearchExecution(
                results=results,
                inference_metadata=inference_metadata,
                debug=debug,
            )

        bm25_candidates = self._bm25.search(
            normalized_query,
            [item.chunk for item in stored_chunks],
            top_k=self._bm25_top_k,
        )
        fused_candidates = reciprocal_rank_fusion(vector_candidates, bm25_candidates)
        reranked_candidates = self._reranker.rerank(
            normalized_query,
            fused_candidates,
            top_k=self._rerank_top_k,
        )
        final_context = self._context_selector.select(
            reranked_candidates,
            top_k=final_limit,
        )
        results = [
            DocumentSearchResult(
                text=item.chunk.text,
                document_id=item.chunk.document_id,
                filename=item.chunk.filename,
                page=item.chunk.page_number,
                chunk_id=item.chunk.chunk_id,
                similarity_score=item.score,
            )
            for item in final_context
        ]
        debug = None
        if include_debug:
            debug = RetrievalDebug(
                query=query,
                normalized_query=normalized_query,
                mode=mode,
                vector_candidates=self._debug_ranked(vector_candidates),
                bm25_candidates=self._debug_ranked(bm25_candidates),
                fused_candidates=self._debug_pairs(
                    [(item.chunk, item.score) for item in fused_candidates]
                ),
                reranked_candidates=self._debug_pairs(
                    [(item.chunk, item.score) for item in reranked_candidates]
                ),
                final_context=self._debug_pairs(
                    [(item.chunk, item.score) for item in final_context]
                ),
            )
        return DocumentSearchExecution(
            results=results,
            inference_metadata=inference_metadata,
            debug=debug,
        )

    @staticmethod
    def _vector_result(item: RankedChunk) -> DocumentSearchResult:
        return DocumentSearchResult(
            text=item.chunk.text,
            document_id=item.chunk.document_id,
            filename=item.chunk.filename,
            page=item.chunk.page_number,
            chunk_id=item.chunk.chunk_id,
            similarity_score=item.score,
        )

    @classmethod
    def _build_debug(
        cls,
        *,
        query: str,
        normalized_query: str,
        mode: RetrievalMode,
        vector_candidates: list[RankedChunk],
        final_context: list[RankedChunk],
    ) -> RetrievalDebug:
        return RetrievalDebug(
            query=query,
            normalized_query=normalized_query,
            mode=mode,
            vector_candidates=cls._debug_ranked(vector_candidates),
            bm25_candidates=[],
            fused_candidates=[],
            reranked_candidates=[],
            final_context=cls._debug_ranked(final_context),
        )

    @staticmethod
    def _debug_ranked(candidates: list[RankedChunk]) -> list[RetrievalDebugCandidate]:
        return [
            RetrievalDebugCandidate(
                rank=item.rank,
                chunk_id=item.chunk.chunk_id,
                document_id=item.chunk.document_id,
                filename=item.chunk.filename,
                page=item.chunk.page_number,
                chunk_index=item.chunk.chunk_index,
                score=item.score,
                text=item.chunk.text,
            )
            for item in candidates
        ]

    @staticmethod
    def _debug_pairs(
        candidates: list[tuple[DocumentChunk, float]],
    ) -> list[RetrievalDebugCandidate]:
        return [
            RetrievalDebugCandidate(
                rank=rank,
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                filename=chunk.filename,
                page=chunk.page_number,
                chunk_index=chunk.chunk_index,
                score=score,
                text=chunk.text,
            )
            for rank, (chunk, score) in enumerate(candidates, start=1)
        ]

    def rebuild_index_if_needed(self) -> IndexSyncResult:
        stored_chunks = [
            chunk
            for document in self._repository.list_documents()
            for chunk in self._repository.get_chunks(document.document_id)
        ]
        durable_ids = {item.chunk.chunk_id for item in stored_chunks}
        if self._vector_store.list_ids() == durable_ids:
            return IndexSyncResult(len(stored_chunks), len(durable_ids), False)
        self._vector_store.clear()
        self._vector_store.upsert(
            [item.chunk for item in stored_chunks],
            [item.embedding for item in stored_chunks],
        )
        return IndexSyncResult(len(stored_chunks), self._vector_store.count(), True)

    @staticmethod
    def _chunk_id(
        *,
        document_id: str,
        page_number: int,
        chunk_index: int,
        text: str,
    ) -> str:
        digest = sha256(f"{document_id}:{page_number}:{chunk_index}:{text}".encode()).hexdigest()
        return f"chunk_{digest[:24]}"
