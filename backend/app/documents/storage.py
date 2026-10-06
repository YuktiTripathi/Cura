from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from app.core.config import settings
from app.core.errors import InternalError

logger = logging.getLogger("cura.documents")


def _safe_user_segment(user_id: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in user_id.strip())
    return cleaned or "user"


class LocalDocumentStore:
    """Filesystem backend. Storage keys are never original filenames."""

    def __init__(self, root: str | Path | None = None):
        self.root = Path(root or settings.document_storage_path).resolve()

    def save(self, user_id: str, document_id: str, data: bytes, suffix: str = ".pdf") -> str:
        if ".." in document_id or "/" in document_id or "\\" in document_id:
            raise InternalError("Invalid document identifier")
        user_seg = _safe_user_segment(user_id)
        rel = f"{user_seg}/{document_id}{suffix}"
        dest = self.root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            dest.write_bytes(data)
        except OSError:
            logger.warning("document_store_save_failed document_id=%s", document_id)
            if dest.exists():
                dest.unlink(missing_ok=True)
            raise
        return rel.replace("\\", "/")

    def _resolve(self, storage_key: str) -> Path:
        key = storage_key.replace("\\", "/").lstrip("/")
        if ".." in key.split("/"):
            raise InternalError("Invalid storage key")
        path = (self.root / key).resolve()
        try:
            path.relative_to(self.root)
        except ValueError as exc:
            raise InternalError("Invalid storage key") from exc
        return path

    def read(self, storage_key: str) -> bytes:
        path = self._resolve(storage_key)
        return path.read_bytes()

    def delete(self, storage_key: str) -> None:
        path = self._resolve(storage_key)
        path.unlink(missing_ok=True)

    def exists(self, storage_key: str) -> bool:
        return self._resolve(storage_key).is_file()


class S3DocumentStore:
    """S3-compatible object storage (readiness plan 5.2). Encrypted at rest with KMS.

    Object keys use a hash of the member id, never the id or the original filename, so
    keys carry no personal data. Use a bucket in an India region (for example ap-south-1).
    """

    def __init__(self, bucket: str | None = None, prefix: str | None = None, client=None):
        self.bucket = (bucket or settings.document_s3_bucket).strip()
        if not self.bucket:
            raise InternalError("DOCUMENT_S3_BUCKET is not configured")
        self.prefix = (prefix if prefix is not None else settings.document_s3_prefix).strip("/")
        self._client = client

    @property
    def client(self):
        if self._client is None:
            import boto3

            self._client = boto3.client(
                "s3",
                region_name=settings.document_s3_region or None,
                endpoint_url=settings.document_s3_endpoint_url or None,
            )
        return self._client

    def _key(self, storage_key: str) -> str:
        key = storage_key.replace("\\", "/").lstrip("/")
        if ".." in key.split("/"):
            raise InternalError("Invalid storage key")
        return f"{self.prefix}/{key}" if self.prefix else key

    def save(self, user_id: str, document_id: str, data: bytes, suffix: str = ".pdf") -> str:
        if ".." in document_id or "/" in document_id or "\\" in document_id:
            raise InternalError("Invalid document identifier")
        user_seg = hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:32]
        rel = f"{user_seg}/{document_id}{suffix}"
        extra = {"ServerSideEncryption": "aws:kms"}
        if settings.document_s3_kms_key_id:
            extra["SSEKMSKeyId"] = settings.document_s3_kms_key_id
        try:
            self.client.put_object(Bucket=self.bucket, Key=self._key(rel), Body=data, **extra)
        except Exception:
            logger.warning("document_store_save_failed backend=s3 document_id=%s", document_id)
            raise
        return rel

    def read(self, storage_key: str) -> bytes:
        return self.client.get_object(Bucket=self.bucket, Key=self._key(storage_key))["Body"].read()

    def delete(self, storage_key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=self._key(storage_key))

    def exists(self, storage_key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=self._key(storage_key))
            return True
        except Exception:
            return False


def get_document_store() -> LocalDocumentStore | S3DocumentStore:
    backend = (settings.document_storage_backend or "local").strip().lower()
    if backend == "s3":
        return S3DocumentStore()
    if backend != "local":
        # Never fall back silently: uploads would land on an ephemeral container disk.
        raise InternalError(f"Unknown DOCUMENT_STORAGE_BACKEND: {backend}")
    return LocalDocumentStore(settings.document_storage_path)
