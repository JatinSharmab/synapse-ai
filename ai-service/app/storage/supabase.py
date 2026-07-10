from datetime import UTC, datetime, timedelta
from urllib.parse import quote, urljoin, urlparse

import httpx

from app.storage.base import ObjectStorageError, ObjectStorageProvider, SignedUpload


class SupabaseObjectStorage(ObjectStorageProvider):
    """Private-bucket Supabase Storage adapter using server-only authorization."""

    def __init__(
        self,
        *,
        project_url: str,
        service_role_key: str,
        bucket: str = "synapse-assets",
        timeout_seconds: float = 30,
        signed_url_ttl_seconds: int = 7200,
        client: httpx.Client | None = None,
    ) -> None:
        self._project_url = project_url.rstrip("/")
        self._storage_url = f"{self._project_url}/storage/v1"
        self._bucket = bucket
        self._ttl = signed_url_ttl_seconds
        self._headers = {
            "Authorization": f"Bearer {service_role_key}",
            "apikey": service_role_key,
        }
        self._client = client or httpx.Client(timeout=timeout_seconds)

    def create_signed_upload(self, object_path: str) -> SignedUpload:
        encoded = self._encoded_path(object_path)
        try:
            response = self._client.post(
                f"{self._storage_url}/object/upload/sign/{self._bucket}/{encoded}",
                headers=self._headers,
            )
            response.raise_for_status()
            relative_url = str(response.json()["url"])
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
            raise ObjectStorageError("Supabase could not create a signed upload URL.") from error
        signed_url = urljoin(f"{self._project_url}/", relative_url.lstrip("/"))
        if urlparse(signed_url).netloc != urlparse(self._project_url).netloc:
            raise ObjectStorageError("Supabase returned an invalid signed upload URL.")
        return SignedUpload(
            url=signed_url,
            expires_at=datetime.now(UTC) + timedelta(seconds=self._ttl),
        )

    def download(self, object_path: str, *, max_bytes: int) -> bytes:
        encoded = self._encoded_path(object_path)
        try:
            with self._client.stream(
                "GET",
                f"{self._storage_url}/object/{self._bucket}/{encoded}",
                headers=self._headers,
            ) as response:
                response.raise_for_status()
                content_length = int(response.headers.get("content-length", "0"))
                if content_length > max_bytes:
                    raise ObjectStorageError("The stored object exceeds the permitted size.")
                data = bytearray()
                for part in response.iter_bytes():
                    data.extend(part)
                    if len(data) > max_bytes:
                        raise ObjectStorageError("The stored object exceeds the permitted size.")
                return bytes(data)
        except ObjectStorageError:
            raise
        except (httpx.HTTPError, ValueError) as error:
            raise ObjectStorageError("The stored object could not be downloaded.") from error

    @staticmethod
    def _encoded_path(object_path: str) -> str:
        if object_path.startswith("/") or ".." in object_path.split("/"):
            raise ObjectStorageError("The object path is invalid.")
        return "/".join(quote(part, safe="") for part in object_path.split("/") if part)
