from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import unquote, urlparse

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.core.config import settings
from app.core.copy import PERSONAL_DATA_UNAVAILABLE
from app.core.errors import ProviderUnavailableError

logger = logging.getLogger("cura.supershyft")

_engine: Engine | None = None

_URL_RE = re.compile(r"(?:postgres(?:ql)?(?:\+\w+)?|https?)://[^\s'\"<>]+", re.I)
_USERINFO_RE = re.compile(r"[^\s/:]+:[^@\s]+@")
_IPV4_RE = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")
_HOST_PORT_RE = re.compile(r"\b[\w.-]+:\d{2,5}\b")

STATUS_MISSING = "missing"
STATUS_UNREACHABLE = "unreachable"
STATUS_QUERY_FAILURE = "query_failure"
STATUS_REACHABLE = "reachable"

DB_NOT_CONFIGURED = "db_not_configured"
DB_CONNECTION_FAILED = "db_connection_failed"
DB_AUTH_FAILED = "db_authentication_failed"
DB_QUERY_FAILED = "db_query_failed"
DB_SCHEMA_ERROR = "db_schema_error"
DB_NO_RECORDS = "db_no_records"
DB_PROVIDER_NOT_CALLED = "db_provider_not_called"

_WRITE_PREFIXES = ("INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP", "TRUNCATE", "GRANT", "REVOKE")


def normalize_sync_url(url: str) -> str:
    value = url.strip()
    if value.startswith("postgresql+asyncpg://"):
        return "postgresql+psycopg://" + value.split("://", 1)[1]
    if value.startswith("postgres://"):
        return "postgresql+psycopg://" + value.split("://", 1)[1]
    if value.startswith("postgresql://"):
        return "postgresql+psycopg://" + value.split("://", 1)[1]
    return value


def sanitize_db_error(exc: BaseException) -> str:
    """Short, credential-free classification for logs and diagnostics."""
    raw = " ".join(str(part) for part in [exc, getattr(exc, "__cause__", None)] if part)
    lowered = raw.lower()
    if "timeout" in lowered or "timed out" in lowered or "time out" in lowered:
        return "connection timeout"
    if "refused" in lowered:
        return "connection refused"
    if "password authentication" in lowered or "authentication failed" in lowered or "invalid authorization" in lowered:
        return "authentication failed"
    if "ssl" in lowered:
        return "tls handshake failed"
    if "undefined column" in lowered or "undefinedcolumn" in lowered:
        return "schema mismatch"
    if "column" in lowered and "does not exist" in lowered:
        return "schema mismatch"
    if "does not exist" in lowered and "database" in lowered:
        return "query failed"
    if "syntax" in lowered or "undefined" in lowered or "permission" in lowered:
        return "query failed"
    if "no module named" in lowered or "psycopg" in lowered and "import" in lowered:
        return "driver missing"
    return "connection failed"


def db_reason_from_classified(classified: str) -> str:
    if classified == "authentication failed":
        return DB_AUTH_FAILED
    if classified == "schema mismatch":
        return DB_SCHEMA_ERROR
    if classified in {"connection timeout", "connection refused", "tls handshake failed", "connection failed"}:
        return DB_CONNECTION_FAILED
    return DB_QUERY_FAILED


def redact_text(value: str) -> str:
    text_value = value or ""
    text_value = _URL_RE.sub("[redacted-url]", text_value)
    text_value = _USERINFO_RE.sub("[redacted]@", text_value)
    text_value = _IPV4_RE.sub("[redacted-host]", text_value)
    text_value = _HOST_PORT_RE.sub("[redacted-host]", text_value)
    return text_value


def _assert_readonly(statement: Any) -> None:
    raw = str(getattr(statement, "text", statement)).strip()
    sql = raw.rstrip(";").strip().lstrip("(").upper()
    if ";" in raw.rstrip(";") or not sql.startswith("SELECT") or sql.startswith(_WRITE_PREFIXES):
        raise ProviderUnavailableError(PERSONAL_DATA_UNAVAILABLE, reason=DB_QUERY_FAILED)


def sanitized_db_target(url: str) -> dict[str, Any]:
    parsed = urlparse(normalize_sync_url(url or ""))
    return {
        "host": parsed.hostname,
        "port": parsed.port or 5432,
        "database": (parsed.path or "").lstrip("/") or None,
        "username": unquote(parsed.username or "") or None,
        "driver": (parsed.scheme or "").split("+")[-1] or None,
    }


def get_supershyft_engine() -> Engine:
    global _engine
    if _engine is not None:
        return _engine
    raw = settings.supershyft_database_url.strip()
    if not raw:
        raise ProviderUnavailableError(PERSONAL_DATA_UNAVAILABLE, reason=DB_NOT_CONFIGURED)
    try:
        import psycopg  # noqa: F401
    except ImportError as exc:
        logger.warning(
            "supershyft_db operation=engine status=unavailable error=driver missing "
            "target=%s",
            sanitized_db_target(raw),
        )
        raise ProviderUnavailableError(PERSONAL_DATA_UNAVAILABLE, reason=DB_CONNECTION_FAILED) from exc
    url = normalize_sync_url(raw)
    timeout = max(1, int(settings.supershyft_db_connect_timeout))
    logger.info(
        "supershyft_db operation=engine status=creating target=%s",
        sanitized_db_target(raw),
    )
    _engine = create_engine(
        url,
        pool_pre_ping=True,
        pool_size=max(1, int(settings.supershyft_pool_size)),
        max_overflow=max(0, int(settings.supershyft_max_overflow)),
        connect_args={"connect_timeout": timeout},
    )
    return _engine


def run_readonly(statement, params: dict | None = None, *, fetch: str = "all"):
    _assert_readonly(statement)
    started = time.perf_counter()
    try:
        engine = get_supershyft_engine()
        with engine.connect() as conn:
            result = conn.execute(statement, params or {})
            if fetch == "one":
                row = result.mappings().first()
                data = dict(row) if row else None
                logger.debug(
                    "supershyft_db operation=readonly_query status=ok fetch=one rows=%s",
                    0 if data is None else 1,
                )
                return data
            rows = [dict(r) for r in result.mappings().all()]
            logger.debug("supershyft_db operation=readonly_query status=ok fetch=all rows=%s", len(rows))
            return rows
    except ProviderUnavailableError:
        raise
    except Exception as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        classified = sanitize_db_error(exc)
        logger.warning(
            "supershyft_db operation=readonly_query status=unavailable provider=supershyft "
            "error=%s reason=%s latency_ms=%s target=%s fallback=personal_data_unavailable",
            classified,
            db_reason_from_classified(classified),
            latency_ms,
            sanitized_db_target(settings.supershyft_database_url),
        )
        raise ProviderUnavailableError(
            PERSONAL_DATA_UNAVAILABLE, reason=db_reason_from_classified(classified)
        ) from exc


@dataclass
class SuperShyftDiagnostic:
    configured: bool
    reachable: bool
    query_ok: bool
    status: str
    error: str | None
    latency_ms: int

    def public_dict(self) -> dict:
        return {
            "configured": self.configured,
            "reachable": self.reachable,
            "query_ok": self.query_ok,
            "status": self.status,
            "error": self.error,
        }


def probe_supershyft() -> SuperShyftDiagnostic:
    started = time.perf_counter()
    raw = (settings.supershyft_database_url or "").strip()
    if not raw:
        diagnostic = SuperShyftDiagnostic(
            configured=False,
            reachable=False,
            query_ok=False,
            status=STATUS_MISSING,
            error="not configured",
            latency_ms=0,
        )
        logger.info(
            "supershyft_db operation=probe status=%s configured=false reachable=false latency_ms=0",
            diagnostic.status,
        )
        return diagnostic

    timeout = max(1, min(int(settings.supershyft_db_connect_timeout), 5))
    engine = None
    try:
        engine = create_engine(
            normalize_sync_url(raw),
            pool_pre_ping=False,
            pool_size=1,
            max_overflow=0,
            connect_args={"connect_timeout": timeout},
        )
        with engine.connect() as conn:
            try:
                conn.execute(text("SELECT 1"))
            except Exception as exc:
                classified = sanitize_db_error(exc)
                latency_ms = int((time.perf_counter() - started) * 1000)
                logger.warning(
                    "supershyft_db operation=probe status=%s error=%s latency_ms=%s",
                    STATUS_QUERY_FAILURE,
                    classified,
                    latency_ms,
                )
                return SuperShyftDiagnostic(
                    configured=True,
                    reachable=True,
                    query_ok=False,
                    status=STATUS_QUERY_FAILURE,
                    error=classified,
                    latency_ms=latency_ms,
                )
        latency_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "supershyft_db operation=probe status=%s configured=true reachable=true latency_ms=%s",
            STATUS_REACHABLE,
            latency_ms,
        )
        return SuperShyftDiagnostic(
            configured=True,
            reachable=True,
            query_ok=True,
            status=STATUS_REACHABLE,
            error=None,
            latency_ms=latency_ms,
        )
    except Exception as exc:
        classified = sanitize_db_error(exc)
        latency_ms = int((time.perf_counter() - started) * 1000)
        logger.warning(
            "supershyft_db operation=probe status=%s error=%s latency_ms=%s",
            STATUS_UNREACHABLE,
            classified,
            latency_ms,
        )
        return SuperShyftDiagnostic(
            configured=True,
            reachable=False,
            query_ok=False,
            status=STATUS_UNREACHABLE,
            error=classified,
            latency_ms=latency_ms,
        )
    finally:
        if engine is not None:
            engine.dispose()


def reset_engine() -> None:
    global _engine
    if _engine is not None:
        _engine.dispose()
    _engine = None
