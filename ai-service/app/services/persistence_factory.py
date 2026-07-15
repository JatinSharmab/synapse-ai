from dataclasses import dataclass

from app.core.config import Settings
from app.repositories.metadata import LocalMetadataRepository, MetadataRepository
from app.repositories.mongo import MongoMetadataRepository
from app.storage.base import FakeObjectStorage, ObjectStorageProvider
from app.storage.local import LocalObjectStorage
from app.storage.supabase import SupabaseObjectStorage
from app.vectorstores.base import InMemoryVectorStore, VectorStore
from app.vectorstores.provider import ChromaVectorStore


@dataclass(frozen=True)
class PersistenceBundle:
    metadata: MetadataRepository
    objects: ObjectStorageProvider
    vectors: VectorStore


def create_persistence_bundle(settings: Settings) -> PersistenceBundle:
    if settings.app_env == "test":
        return PersistenceBundle(
            metadata=LocalMetadataRepository.in_memory(),
            objects=FakeObjectStorage(),
            vectors=InMemoryVectorStore(),
        )

    if settings.metadata_backend == "mongo":
        assert settings.mongodb_uri is not None
        metadata: MetadataRepository = MongoMetadataRepository(
            uri=settings.mongodb_uri.get_secret_value(),
            database_name=settings.mongodb_database,
            connect_timeout_ms=int(settings.mongodb_connect_timeout_seconds * 1000),
        )
    else:
        metadata = LocalMetadataRepository.json(
            document_path=settings.document_metadata_path,
            video_path=settings.video_metadata_path,
            dataset_path=settings.dataset_metadata_path,
        )

    if settings.object_storage_provider == "supabase":
        assert settings.supabase_url is not None
        assert settings.supabase_service_role_key is not None
        objects: ObjectStorageProvider = SupabaseObjectStorage(
            project_url=settings.supabase_url,
            service_role_key=settings.supabase_service_role_key.get_secret_value(),
            bucket=settings.supabase_storage_bucket,
            timeout_seconds=settings.supabase_request_timeout_seconds,
            signed_url_ttl_seconds=settings.upload_intent_ttl_seconds,
        )
    else:
        objects = LocalObjectStorage(settings.local_object_storage_path)

    vectors: VectorStore = ChromaVectorStore(
        collection_names={
            "documents": settings.chroma_document_collection,
            "videos": settings.chroma_video_collection,
        },
        persist_path=settings.chroma_persist_path,
    )
    return PersistenceBundle(metadata=metadata, objects=objects, vectors=vectors)
