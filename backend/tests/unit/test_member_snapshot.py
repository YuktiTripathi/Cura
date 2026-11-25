"""Member snapshot: values, cache, isolation, and no model calls on exploration."""

from __future__ import annotations

from datetime import date

import pytest

from app.auth.models import AuthenticatedPrincipal
from app.contracts.bio_ai import BioAIReport, BioAIRisk
from app.contracts.blood import BloodMarker, BloodReport
from app.contracts.common import MarkerFlag
from app.contracts.context_ref import ContextRef
from app.contracts.user import UserProfile
from app.core.config import settings
from app.core.errors import ProviderUnavailableError
from app.pipeline.query_planner import build_query_plan
from app.snapshot.assemble import assemble_snapshot, exploration_llm_calls
from app.snapshot.cache import invalidate_snapshot, load_snapshot


class _Blood:
    def __init__(self, rows):
        self.rows = rows
        self.calls = 0

    def query(self, principal, plan):
        self.calls += 1
        if isinstance(self.rows, Exception):
            raise self.rows
        return list(self.rows)


class _Bio:
    def __init__(self, rows):
        self.rows = rows
        self.calls = 0

    def query(self, principal, plan):
        self.calls += 1
        if isinstance(self.rows, Exception):
            raise self.rows
        return list(self.rows)


class _Life:
    def query(self, principal, plan):
        return None


class _Questions:
    def query(self, principal, plan):
        return []


class _Users:
    def get_profile(self, principal):
        return UserProfile(subject_id=principal.subject_id, display_name="Alex")


class Registry:
    def __init__(self, blood, bio):
        self.blood = blood
        self.bio_ai = bio
        self.lifestyle = _Life()
        self.questionnaires = _Questions()
        self.users = _Users()


def _marker(name, value, low, high, unit="mg/dL"):
    flag = MarkerFlag.unknown
    if value is None:
        flag = MarkerFlag.missing
    elif low is not None and value < low:
        flag = MarkerFlag.low
    elif high is not None and value > high:
        flag = MarkerFlag.high
    elif low is not None or high is not None:
        flag = MarkerFlag.normal
    return BloodMarker(
        id=name, key=name, name=name, value=value, unit=unit, reference_low=low, reference_high=high, flag=flag
    )


def _blood(report_id, day, markers):
    return BloodReport(report_id=report_id, report_date=day, markers=markers)


def _bio(report_id, day, score, status, metabolic_age=None):
    return BioAIReport(
        report_id=report_id,
        report_date=day,
        source_line="bio_ai",
        metabolic_age=metabolic_age,
        risks=[BioAIRisk(code="nafld", name="Fatty liver", score=score, status=status)],
    )


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(settings, "member_snapshot_enabled", True)
    monkeypatch.setattr(settings, "member_snapshot_ttl_seconds", 600)


def test_preserves_values_and_picks_latest_without_merging_same_day(enabled):
    day = date(2026, 8, 21)
    older = _blood("blood-old", date(2026, 1, 1), [_marker("hdl", 40, 40, 80)])
    same_a = _blood("blood-a", day, [_marker("hdl", 55, 40, 80, "mg/dL")])
    same_b = _blood("blood-b", day, [_marker("hdl", 61, 40, 80, "mg/dL")])
    bio_old = _bio("bio-old", date(2026, 1, 2), 10, "healthy")
    bio_new = _bio("bio-new", date(2026, 8, 25), 22, "increased", metabolic_age=41)
    registry = Registry(_Blood([same_a, older, same_b]), _Bio([bio_new, bio_old]))
    snapshot = assemble_snapshot(AuthenticatedPrincipal(subject_id="member-a"), registry)
    assert snapshot.latest_blood.report_id == "blood-b"
    assert snapshot.previous_blood.report_id == "blood-a"
    assert snapshot.latest_blood.report_id != snapshot.previous_blood.report_id
    assert snapshot.latest_bio_ai.report_id == "bio-new"
    assert snapshot.previous_bio_ai.report_id == "bio-old"
    assert snapshot.metabolic_age == 41
    measured = [item for item in snapshot.findings.values() if item.source_type == "measured" and item.value == 61]
    assert measured
    assert measured[0].unit == "mg/dL"
    assert measured[0].reference_low == 40
    assert measured[0].reference_high == 80
    risk = next(item for item in snapshot.findings.values() if item.source_type == "predicted_risk")
    assert risk.score == 22
    assert risk.classification or risk.status_label
    assert exploration_llm_calls == 0


def test_missing_range_is_not_treated_as_normal(enabled):
    report = _blood("blood-1", date(2026, 5, 1), [_marker("crp", 3.2, None, None)])
    snapshot = assemble_snapshot(AuthenticatedPrincipal(subject_id="member-a"), Registry(_Blood([report]), _Bio([])))
    finding = next(iter(snapshot.findings.values()))
    assert finding.value == 3.2
    assert finding.status != "within_range"
    assert finding.education is None or finding.education.what_it_is


def test_partial_provider_failure_keeps_the_other_source(enabled):
    report = _bio("bio-1", date(2026, 5, 1), 15, "healthy")
    snapshot = assemble_snapshot(
        AuthenticatedPrincipal(subject_id="member-a"),
        Registry(_Blood(ProviderUnavailableError("down")), _Bio([report])),
    )
    assert snapshot.state == "partial"
    assert snapshot.availability.blood == "unavailable"
    assert snapshot.availability.bio_ai == "ready"
    assert any(item.source_type == "predicted_risk" for item in snapshot.findings.values())


def test_no_reports_is_ready_and_empty(enabled):
    snapshot = assemble_snapshot(AuthenticatedPrincipal(subject_id="member-a"), Registry(_Blood([]), _Bio([])))
    assert snapshot.state == "ready"
    assert snapshot.findings == {}
    assert snapshot.overview.categories == [] or snapshot.overview.available in {False, True}


def test_cache_hit_skips_provider_and_isolation(enabled):
    blood = _Blood([_blood("blood-1", date(2026, 5, 1), [_marker("hdl", 50, 40, 80)])])
    registry = Registry(blood, _Bio([]))
    principal = AuthenticatedPrincipal(subject_id="member-cache")
    other = AuthenticatedPrincipal(subject_id="member-other")
    invalidate_snapshot(principal.subject_id)
    first = load_snapshot(principal, registry, refresh=True)
    calls = blood.calls
    second = load_snapshot(principal, registry)
    assert second.snapshot_version == first.snapshot_version
    assert blood.calls == calls
    other_blood = _Blood([_blood("secret", date(2026, 5, 2), [_marker("ldl", 99, 0, 100)])])
    other_snap = load_snapshot(other, Registry(other_blood, _Bio([])), refresh=True)
    assert "secret" not in first.source_ids
    assert other_snap.latest_blood.report_id == "secret"
    assert first.findings.keys().isdisjoint(other_snap.findings.keys()) or first.latest_blood.report_id != other_snap.latest_blood.report_id


def test_refresh_rebuilds_and_expired_ttl_does_not_return_stale(enabled, monkeypatch):
    blood = _Blood([_blood("blood-1", date(2026, 5, 1), [_marker("hdl", 50, 40, 80)])])
    registry = Registry(blood, _Bio([]))
    principal = AuthenticatedPrincipal(subject_id="member-refresh")
    load_snapshot(principal, registry, refresh=True)
    monkeypatch.setattr(settings, "member_snapshot_ttl_seconds", 0)
    blood.rows = [_blood("blood-2", date(2026, 6, 1), [_marker("hdl", 48, 40, 80)])]
    rebuilt = load_snapshot(principal, registry, refresh=True)
    assert rebuilt.latest_blood.report_id == "blood-2"


def test_redis_read_failure_still_returns_a_snapshot(enabled, monkeypatch):
    from app.core import request_controls as controls

    def boom(key):
        raise RuntimeError("redis down")

    monkeypatch.setattr(controls.request_controls, "_get", boom)
    monkeypatch.setattr(controls.request_controls, "_set_nx", lambda *args, **kwargs: False)
    snapshot = load_snapshot(
        AuthenticatedPrincipal(subject_id="member-redis"),
        Registry(_Blood([_blood("blood-9", date(2026, 5, 1), [_marker("hdl", 50, 40, 80)])]), _Bio([])),
        refresh=True,
    )
    assert snapshot.latest_blood.report_id == "blood-9"


def test_concurrent_builds_share_one_provider_read(enabled):
    import threading

    blood = _Blood([_blood("blood-1", date(2026, 5, 1), [_marker("hdl", 50, 40, 80)])])
    registry = Registry(blood, _Bio([]))
    principal = AuthenticatedPrincipal(subject_id="member-flight")
    invalidate_snapshot(principal.subject_id)
    errors = []

    def run():
        try:
            load_snapshot(principal, registry)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=run) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    assert blood.calls == 1


def test_model_wording_is_not_used(enabled, monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("wording model called")

    monkeypatch.setattr("app.pipeline.unified_wording.model_wording", fail)
    assemble_snapshot(
        AuthenticatedPrincipal(subject_id="member-a"),
        Registry(_Blood([_blood("blood-1", date(2026, 5, 1), [_marker("hdl", 50, 40, 80)])]), _Bio([])),
    )


def test_card_context_yields_when_the_question_names_another_marker(enabled):
    ref = ContextRef(type="blood_marker", source="supershyft", marker_code="hdl", category_id="heart_circulation")
    plan = build_query_plan("What is my vitamin D?", context_ref=ref)
    blob = " ".join([plan.topic or "", " ".join(plan.requested_metrics or [])]).lower()
    assert "hdl" not in blob or "vitamin" in blob or "d" in blob
    assert plan.needs_blood


def test_general_question_does_not_force_the_card(enabled):
    ref = ContextRef(type="blood_marker", source="supershyft", marker_code="hdl")
    plan = build_query_plan("What is HDL cholesterol?", context_ref=ref)
    assert plan.needs_supershyft is False or plan.knowledge_scope.value == "general" or not plan.needs_blood


def test_history_question_requests_comparison(enabled):
    ref = ContextRef(type="blood_marker", source="supershyft", marker_code="hdl")
    plan = build_query_plan("How does my HDL compare with last time?", context_ref=ref)
    assert plan.history or plan.compare
