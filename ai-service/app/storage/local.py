from pathlib import Path

from app.storage.base import ObjectStorageError, ObjectStorageProvider, SignedUpload


class LocalObjectStorage(ObjectStorageProvider):
    """Filesystem-backed development adapter; never treated as production durability."""

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def create_signed_upload(self, object_path: str) -> SignedUpload:
        del object_path
        raise ObjectStorageError("Signed uploads require Supabase object storage.")

    def download(self, object_path: str, *, max_bytes: int) -> bytes:
        path = self._resolve(object_path)
        try:
            if path.stat().st_size > max_bytes:
                raise ObjectStorageError("The stored object exceeds the permitted size.")
            return path.read_bytes()
        except FileNotFoundError as error:
            raise ObjectStorageError("The stored object does not exist.") from error

    def put(self, object_path: str, data: bytes) -> None:
        path = self._resolve(object_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def _resolve(self, object_path: str) -> Path:
        candidate = (self._root / object_path).resolve()
        if not candidate.is_relative_to(self._root):
            raise ObjectStorageError("The object path is invalid.")
        return candidate
