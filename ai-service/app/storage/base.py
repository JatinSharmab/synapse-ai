from abc import ABC, abstractmethod
from datetime import datetime
from threading import RLock

from pydantic import BaseModel, ConfigDict, HttpUrl


class ObjectStorageError(RuntimeError):
    """A safe object-storage failure without credential details."""


class SignedUpload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    url: HttpUrl
    expires_at: datetime


class ObjectStorageProvider(ABC):
    @abstractmethod
    def create_signed_upload(self, object_path: str) -> SignedUpload: ...

    @abstractmethod
    def download(self, object_path: str, *, max_bytes: int) -> bytes: ...


class FakeObjectStorage(ObjectStorageProvider):
    def __init__(self) -> None:
        self._objects: dict[str, bytes] = {}
        self._lock = RLock()

    def create_signed_upload(self, object_path: str) -> SignedUpload:
        from datetime import UTC, timedelta

        return SignedUpload(
            url=f"https://storage.test/upload/{object_path}?token=fake",
            expires_at=datetime.now(UTC) + timedelta(hours=2),
        )

    def download(self, object_path: str, *, max_bytes: int) -> bytes:
        with self._lock:
            try:
                data = self._objects[object_path]
            except KeyError as error:
                raise ObjectStorageError("The stored object does not exist.") from error
        if len(data) > max_bytes:
            raise ObjectStorageError("The stored object exceeds the permitted size.")
        return data

    def put(self, object_path: str, data: bytes) -> None:
        with self._lock:
            self._objects[object_path] = data
