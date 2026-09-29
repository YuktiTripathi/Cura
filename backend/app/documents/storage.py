from __future__ import annotations

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


def get_document_store() -> LocalDocumentStore:
    backend = (settings.document_storage_backend or "local").strip().lower()
    if backend != "local":
        logger.warning("unknown_document_storage_backend backend=%s falling_back=local", backend)
    return LocalDocumentStore(settings.document_storage_path)
