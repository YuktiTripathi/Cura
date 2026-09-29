"""Sanitized SuperShyft Postgres diagnostic. Never prints credentials or full reports."""

from __future__ import annotations

import socket
from urllib.parse import urlparse

from sqlalchemy import create_engine, text

from app.core.config import settings
from integrations.supershyft.db import normalize_sync_url, sanitize_db_error, sanitized_db_target

DATABASE_CONFIG_MISSING = "DATABASE_CONFIG_MISSING"
DATABASE_URL_INVALID = "DATABASE_URL_INVALID"
HOST_UNREACHABLE = "HOST_UNREACHABLE"
PORT_UNREACHABLE = "PORT_UNREACHABLE"
AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
DATABASE_NOT_FOUND = "DATABASE_NOT_FOUND"
TABLE_NOT_FOUND = "TABLE_NOT_FOUND"
SCHEMA_ERROR = "SCHEMA_ERROR"
QUERY_ERROR = "QUERY_ERROR"
SUCCESS = "SUCCESS"

_EXPECTED_COLS = {
    "report_id",
    "user_id",
    "assessment_instance_id",
    "engagement_id",
    "reports",
    "created_at",
    "report_url",
}


def diagnose_supershyft(user_id: int | None = None) -> dict:
    raw = (settings.supershyft_database_url or "").strip()
    result: dict = {
        "code": DATABASE_CONFIG_MISSING,
        "configured": bool(raw),
        "target": sanitized_db_target(raw) if raw else None,
        "tcp_ok": False,
        "auth_ok": False,
        "table_ok": False,
        "columns": [],
        "user_report_count": None,
        "error": None,
    }
    if not raw:
        result["error"] = "SUPERSHYFT_DATABASE_URL is not set"
        return result
    parsed = urlparse(normalize_sync_url(raw))
    if not parsed.hostname or not parsed.path.lstrip("/"):
        result["code"] = DATABASE_URL_INVALID
        result["error"] = "URL is missing host or database name"
        return result
    host = parsed.hostname
    port = parsed.port or 5432
    sock = socket.socket()
    sock.settimeout(5)
    try:
        sock.connect((host, port))
        result["tcp_ok"] = True
    except OSError as exc:
        classified = sanitize_db_error(exc)
        result["error"] = classified
        result["code"] = PORT_UNREACHABLE if "refused" in classified or "timeout" in classified else HOST_UNREACHABLE
        return result
    finally:
        sock.close()

    engine = None
    try:
        engine = create_engine(
            normalize_sync_url(raw),
            pool_pre_ping=True,
            pool_size=1,
            max_overflow=0,
            connect_args={"connect_timeout": 8},
        )
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            result["auth_ok"] = True
            tables = conn.execute(
                text(
                    """
                    SELECT table_schema
                    FROM information_schema.tables
                    WHERE table_name = 'individual_health_report'
                    """
                )
            ).all()
            if not tables:
                result["code"] = TABLE_NOT_FOUND
                result["error"] = "individual_health_report not found"
                return result
            result["table_ok"] = True
            cols = conn.execute(
                text(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'individual_health_report'
                    """
                )
            ).scalars().all()
            result["columns"] = list(cols)
            missing = sorted(_EXPECTED_COLS - set(cols))
            if missing:
                result["code"] = SCHEMA_ERROR
                result["error"] = "missing columns"
                result["missing_columns"] = missing
                return result
            if user_id is not None:
                count = conn.execute(
                    text("SELECT count(*) FROM individual_health_report WHERE user_id = :uid"),
                    {"uid": user_id},
                ).scalar_one()
                result["user_report_count"] = int(count)
            result["code"] = SUCCESS
            return result
    except Exception as exc:
        classified = sanitize_db_error(exc)
        result["error"] = classified
        lowered = classified.lower()
        if "authentication" in lowered:
            result["code"] = AUTHENTICATION_FAILED
        elif "does not exist" in str(exc).lower() and "database" in str(exc).lower():
            result["code"] = DATABASE_NOT_FOUND
        else:
            result["code"] = QUERY_ERROR
        return result
    finally:
        if engine is not None:
            engine.dispose()
