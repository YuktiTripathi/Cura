import json

from sqlalchemy import text

from app.core.config import settings
from app.core.copy import PERSONAL_DATA_UNAVAILABLE
from app.core.errors import ProviderUnavailableError
from integrations.supershyft import db as ssdb
from integrations.supershyft.db import (
    DB_AUTH_FAILED,
    STATUS_MISSING,
    STATUS_QUERY_FAILURE,
    STATUS_REACHABLE,
    STATUS_UNREACHABLE,
    db_reason_from_classified,
    probe_supershyft,
    redact_text,
    reset_engine,
    run_readonly,
    sanitize_db_error,
)


class _Conn:
    def __init__(self, execute_exc=None):
        self._execute_exc = execute_exc

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, *args, **kwargs):
        if self._execute_exc:
            raise self._execute_exc
        return None


class _Engine:
    def __init__(self, connect_exc=None, execute_exc=None):
        self._connect_exc = connect_exc
        self._execute_exc = execute_exc

    def connect(self):
        if self._connect_exc:
            raise self._connect_exc
        return _Conn(self._execute_exc)

    def dispose(self):
        return None


def test_sanitize_timeout_hides_credentials():
    exc = Exception(
        "connection timed out postgresql+asyncpg://secret_user:SuperSecretPass@187.77.185.240:5432/Supershyft_new"
    )
    classified = sanitize_db_error(exc)
    assert classified == "connection timeout"
    assert "SuperSecretPass" not in classified
    assert "secret_user" not in classified
    assert "187.77" not in classified


def test_redact_url_and_password():
    leaked = redact_text(
        "failed postgresql+asyncpg://secret_user:SuperSecretPass@db.internal:5432/Supershyft_new"
    )
    assert "SuperSecretPass" not in leaked
    assert "secret_user" not in leaked


def test_probe_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "supershyft_database_url", "")
    reset_engine()
    result = probe_supershyft()
    assert result.status == STATUS_MISSING
    assert result.configured is False
    assert result.reachable is False
    assert result.query_ok is False
    assert result.error == "not configured"


def test_probe_configured_unreachable(monkeypatch):
    monkeypatch.setattr(
        settings,
        "supershyft_database_url",
        "postgresql+asyncpg://secret_user:SuperSecretPass@example.invalid:5432/Supershyft_new",
    )
    monkeypatch.setattr(
        ssdb,
        "create_engine",
        lambda *a, **k: _Engine(connect_exc=TimeoutError("connection timed out")),
    )
    result = probe_supershyft()
    assert result.status == STATUS_UNREACHABLE
    assert result.configured is True
    assert result.reachable is False
    assert result.error == "connection timeout"
    payload = json.dumps(result.public_dict())
    assert "SuperSecretPass" not in payload
    assert "secret_user" not in payload
    assert "example.invalid" not in payload


def test_probe_configured_reachable(monkeypatch):
    monkeypatch.setattr(
        settings,
        "supershyft_database_url",
        "postgresql+asyncpg://secret_user:SuperSecretPass@example.invalid:5432/Supershyft_new",
    )
    monkeypatch.setattr(ssdb, "create_engine", lambda *a, **k: _Engine())
    result = probe_supershyft()
    assert result.status == STATUS_REACHABLE
    assert result.configured is True
    assert result.reachable is True
    assert result.query_ok is True
    assert result.error is None


def test_probe_query_failure(monkeypatch):
    monkeypatch.setattr(
        settings,
        "supershyft_database_url",
        "postgresql+psycopg://secret_user:SuperSecretPass@example.invalid:5432/db",
    )
    monkeypatch.setattr(
        ssdb,
        "create_engine",
        lambda *a, **k: _Engine(execute_exc=RuntimeError("undefined table public.users")),
    )
    result = probe_supershyft()
    assert result.status == STATUS_QUERY_FAILURE
    assert result.configured is True
    assert result.reachable is True
    assert result.query_ok is False
    assert result.error == "query failed"


def test_run_readonly_never_writes():
    try:
        run_readonly(text("INSERT INTO users (user_id) VALUES (1)"))
        assert False, "expected write to be rejected"
    except ProviderUnavailableError as exc:
        assert exc.message == PERSONAL_DATA_UNAVAILABLE


def test_readonly_guard_rejects_multi_statement_and_comment_bypass():
    for statement in (
        "SELECT 1; DROP TABLE users",
        "/* harmless */ DELETE FROM users",
        "WITH changed AS (DELETE FROM users RETURNING *) SELECT * FROM changed",
    ):
        try:
            run_readonly(text(statement))
            assert False, "expected statement to be rejected"
        except ProviderUnavailableError:
            pass


def test_run_readonly_user_message_has_no_driver_details(monkeypatch):
    monkeypatch.setattr(
        settings,
        "supershyft_database_url",
        "postgresql+asyncpg://secret_user:SuperSecretPass@10.1.2.3:5432/db",
    )
    reset_engine()
    monkeypatch.setattr(
        ssdb,
        "get_supershyft_engine",
        lambda: _Engine(connect_exc=TimeoutError("asyncpg connection timed out host=10.1.2.3 port=5432")),
    )
    try:
        run_readonly(text("SELECT 1"))
        assert False, "expected unavailable"
    except ProviderUnavailableError as exc:
        assert exc.message == PERSONAL_DATA_UNAVAILABLE
        assert "asyncpg" not in exc.message
        assert "5432" not in exc.message
        assert "SuperSecretPass" not in exc.message


def test_authentication_failed_is_a_distinct_db_status():
    assert sanitize_db_error(Exception("password authentication failed for user")) == "authentication failed"
    assert db_reason_from_classified("authentication failed") == DB_AUTH_FAILED


def test_schema_mismatch_is_distinct_from_unavailable_and_not_found():
    from integrations.supershyft.db import DB_CONNECTION_FAILED, DB_NO_RECORDS, DB_SCHEMA_ERROR

    classified = sanitize_db_error(
        Exception('column "blood_parameters" does not exist\nLINE 2: SELECT blood_parameters')
    )
    assert classified == "schema mismatch"
    assert db_reason_from_classified(classified) == DB_SCHEMA_ERROR
    assert db_reason_from_classified(classified) != DB_CONNECTION_FAILED
    assert db_reason_from_classified(classified) != DB_NO_RECORDS
    assert db_reason_from_classified(classified) != "db_query_failed"


def test_supershyft_user_id_is_authenticated_numeric_subject():
    from app.auth.models import AuthenticatedPrincipal
    from integrations.supershyft.providers import _user_id

    assert _user_id(AuthenticatedPrincipal(subject_id="5")) == 5
    try:
        _user_id(AuthenticatedPrincipal(subject_id="demo-user-001"))
        assert False, "expected non-numeric subject to fail closed"
    except ProviderUnavailableError as exc:
        assert exc.reason == "db_query_failed"


def test_run_readonly_select_succeeds(monkeypatch):
    class Result:
        def mappings(self):
            return self

        def all(self):
            return [{"user_id": 5, "ldl": 142}]

    class Conn:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, statement, params=None):
            assert "SELECT" in str(statement).upper()
            return Result()

    class Engine:
        def connect(self):
            return Conn()

        def dispose(self):
            return None

    monkeypatch.setattr(ssdb, "get_supershyft_engine", lambda: Engine())
    rows = run_readonly(text("SELECT user_id FROM users WHERE user_id = :uid"), {"uid": 5})
    assert rows == [{"user_id": 5, "ldl": 142}]


def test_run_readonly_missing_url_is_invalid_configuration(monkeypatch):
    monkeypatch.setattr(settings, "supershyft_database_url", "")
    reset_engine()
    try:
        run_readonly(text("SELECT 1"))
        assert False, "expected missing URL to fail"
    except ProviderUnavailableError as exc:
        assert exc.reason == ssdb.DB_NOT_CONFIGURED


def test_blood_query_binds_only_authenticated_user(monkeypatch):
    from app.auth.models import AuthenticatedPrincipal
    from app.contracts.common import IntentType
    from app.contracts.query import QueryPlan
    from integrations.supershyft.providers import SuperShyftBloodProvider

    captured: dict = {}

    def fake_run(statement, params=None, *, fetch="all"):
        captured["sql"] = str(statement)
        captured["params"] = params
        return [
            {
                "report_id": 1,
                "user_id": 5,
                "assessment_instance_id": 18,
                "engagement_id": 14,
                "reports": {
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "blood_parameters": {"ldl": 142, "ldl_unit": "mg/dL"},
                },
                "created_at": "2026-01-01",
                "report_url": None,
            }
        ]

    monkeypatch.setattr("integrations.supershyft.ihr.run_readonly", fake_run)
    from integrations.supershyft.ihr import reset_ihr_cache

    reset_ihr_cache()
    reports = SuperShyftBloodProvider().query(
        AuthenticatedPrincipal(subject_id="5"),
        QueryPlan(intent=IntentType.latest_result, needs_blood=True, topic="ldl"),
    )
    assert captured["params"] == {"uid": 5}
    assert ":uid" in captured["sql"]
    assert "blood_parameters" not in captured["sql"]
    assert "blood_report_raw" not in captured["sql"]
    assert "142" not in captured["sql"]
    assert reports
    assert reports[0].markers[0].key == "ldl"
    assert reports[0].markers[0].value == 142


def test_other_user_id_cannot_be_substituted_by_caller(monkeypatch):
    from app.auth.models import AuthenticatedPrincipal
    from app.contracts.common import IntentType
    from app.contracts.query import QueryPlan
    from integrations.supershyft.providers import SuperShyftBloodProvider

    captured: dict = {}

    def fake_run(statement, params=None, *, fetch="all"):
        captured["params"] = params
        return []

    monkeypatch.setattr("integrations.supershyft.ihr.run_readonly", fake_run)
    from integrations.supershyft.ihr import reset_ihr_cache

    reset_ihr_cache()
    SuperShyftBloodProvider().query(
        AuthenticatedPrincipal(subject_id="5"),
        QueryPlan(intent=IntentType.latest_result, needs_blood=True, topic="ldl"),
    )
    assert captured["params"] == {"uid": 5}
    assert captured["params"]["uid"] != 99
