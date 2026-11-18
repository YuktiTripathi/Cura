"""CURA home readiness contract regression tests."""
from unittest.mock import patch

from app.auth.models import AuthenticatedPrincipal
from app.api.routes.cura_home import home_readiness
from app.core.config import settings


def test_cold_cache_schedules_preload():
    principal = AuthenticatedPrincipal(subject_id="test-cold")
    with patch("app.api.routes.cura_home.request_controls") as store, patch(
        "app.api.routes.cura_home.schedule_latest_preload"
    ) as schedule:
        store._get.return_value = None
        result = home_readiness(principal, registry=object())
        assert result.status == "loading"
        assert result.blood_cached is False
        schedule.assert_called_once()


def test_cached_empty_results_are_ready():
    principal = AuthenticatedPrincipal(subject_id="test-empty")
    with patch("app.api.routes.cura_home.request_controls") as store, patch(
        "app.api.routes.cura_home.schedule_latest_preload"
    ) as schedule:
        store._get.return_value = '{"payload":null}'
        result = home_readiness(principal, registry=object())
        assert result.status == "ready"
        assert result.questionnaire_cached
        schedule.assert_not_called()


def test_disabled_cache_is_unavailable(monkeypatch):
    monkeypatch.setattr(settings, "health_data_cache_seconds", 0)
    result = home_readiness(AuthenticatedPrincipal(subject_id="test-disabled"), registry=object())
    assert result.status == "unavailable"
    assert result.refresh_me_when_ready is False


def test_partial_cache_reports_partial_and_retries_preload():
    principal = AuthenticatedPrincipal(subject_id="test-partial")
    with patch("app.api.routes.cura_home.request_controls") as store, patch(
        "app.api.routes.cura_home.schedule_latest_preload"
    ) as schedule:
        store._get.side_effect = lambda key: "cached" if ":blood:" in key else None
        result = home_readiness(principal, registry=object())
        assert result.status == "partial"
        assert result.blood_cached
        assert not result.bio_ai_cached
        schedule.assert_called_once()


def test_cold_starter_snapshot_does_not_query_lifestyle(monkeypatch):
    from unittest.mock import Mock
    from app.pipeline import me_service
    from app.providers import cache

    monkeypatch.setattr(cache, "peek", lambda *args: None)
    registry = Mock()
    snapshot = me_service._snapshot_from_cache(
        AuthenticatedPrincipal(subject_id="test-cold-starters"), registry
    )
    assert snapshot.has_nutrition is False
    registry.lifestyle.query.assert_not_called()
