from uuid import uuid4

from app.core.config import Settings
from app.providers.base import LLMProvider
from app.repositories.documents import InMemoryDocumentRepository, JsonDocumentRepository
from app.services.document_rag import DocumentRAGService
from app.services.pdf_parser import PdfParser
from app.services.semantic_chunker import SemanticChunker
from app.vectorstores.chroma import ChromaDocumentVectorStore


def create_document_rag_service(
    settings: Settings,
    provider: LLMProvider,
) -> DocumentRAGService:
    if settings.app_env == "test":
        repository = InMemoryDocumentRepository()
        persist_path = None
        collection_name = f"phase4_test_{uuid4().hex}"
    else:
        repository = JsonDocumentRepository(settings.document_metadata_path)
        persist_path = settings.chroma_persist_path
        collection_name = settings.chroma_document_collection

    service = DocumentRAGService(
        provider=provider,
        repository=repository,
        vector_store=ChromaDocumentVectorStore(
            collection_name=collection_name,
            persist_path=persist_path,
        ),
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
    service.rebuild_index_if_needed()
    return service
