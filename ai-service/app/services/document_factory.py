from app.core.config import Settings
from app.providers.base import LLMProvider
from app.repositories.documents import DocumentRepository, InMemoryDocumentRepository
from app.services.document_rag import DocumentRAGService
from app.services.pdf_parser import PdfParser
from app.services.semantic_chunker import SemanticChunker
from app.vectorstores.adapters import DocumentVectorStoreAdapter
from app.vectorstores.base import DocumentVectorStore, InMemoryVectorStore


def create_document_rag_service(
    settings: Settings,
    provider: LLMProvider,
    *,
    repository: DocumentRepository | None = None,
    vector_store: DocumentVectorStore | None = None,
) -> DocumentRAGService:
    service = DocumentRAGService(
        provider=provider,
        repository=repository or InMemoryDocumentRepository(),
        vector_store=vector_store or DocumentVectorStoreAdapter(InMemoryVectorStore()),
        parser=PdfParser(
            max_upload_bytes=settings.document_max_upload_bytes,
            max_pages=settings.document_max_pages,
        ),
        chunker=SemanticChunker(
            maximum_tokens=settings.document_chunk_max_tokens,
            minimum_tokens=settings.document_chunk_min_tokens,
            overlap_tokens=settings.document_chunk_overlap_tokens,
        ),
        minimum_extractable_characters=settings.document_min_extractable_chars,
        minimum_similarity_score=settings.document_min_similarity_score,
        vector_top_k=settings.vector_top_k,
        bm25_top_k=settings.bm25_top_k,
        rerank_top_k=settings.rerank_top_k,
        final_context_k=settings.final_context_k,
    )
    return service
