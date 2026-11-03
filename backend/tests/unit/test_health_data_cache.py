"""Provider cache: member + kind + standard|history. Not a HealthContext cache."""

from __future__ import annotations

import threading
from datetime import date

import pytest

from app.auth.models import AuthenticatedPrincipal
from app.contracts.blood import BloodMarker, BloodReport
from app.contracts.common import IntentType, KnowledgeScope
from app.contracts.query import QueryPlan
from app.core import request_controls as rc
from app.core.config import settings
from app.core.request_controls import RequestControlStore
from app.pipeline.query_planner import build_query_plan
from app.providers.cache import (
    cache_scope,
    cached_blood,
    invalidate_health_data,
    read_through,
    storage_key,
)
from pydantic import TypeAdapter

ME = AuthenticatedPrincipal(subject_id="member-a")
OTHER = AuthenticatedPrincipal(subject_id="member-b")


def _report(report_id: str, key: str, value: float, day: date | None = None) -> BloodReport:
    return BloodReport(
        report_id=report_id,
        report_date=day or date(2026, 1, 1),
        markers=[BloodMarker(id=f"{report_id}-{key}", key=key, name=key, value=value, unit="mg/dL", report_id=report_id, measured_at=day or date(2026, 1, 1))],
    )


def _personal(metrics: list[str], **extra) -> QueryPlan:
    operation = extra.pop("time_operation", "latest_marker")
    return QueryPlan(
        intent=IntentType.latest_result,
        knowledge_scope=KnowledgeScope.personal,
        needs_blood=True,
        requested_metrics=metrics,
        time_operation=operation,
        **extra,
    )


class Store:
    def __init__(self, reports: list[BloodReport]):
        self.reports = reports
        self.loads = 0
        self.scopes: list[str] = []

    def load_for_cache(self, principal, scope: str):
        self.loads += 1
        self.scopes.append(scope)
        if scope == "history":
            return list(self.reports)
        return list(self.reports[-2:])

    def apply_plan(self, reports, plan: QueryPlan):
        if not plan.requested_metrics:
            return reports
        wanted = set(plan.requested_metrics)
        return [
            report.model_copy(update={"markers": [m for m in report.markers if m.key in wanted]})
            for report in reports
        ]

    def query(self, principal, plan):
        return self.apply_plan(self.load_for_cache(principal, cache_scope(plan)), plan)


@pytest.fixture(autouse=True)
def fresh_store(monkeypatch):
    monkeypatch.setattr(settings, "redis_url", "")
    monkeypatch.setattr(settings, "health_data_cache_seconds", 600)
    monkeypatch.setattr(settings, "health_data_cache_wait_seconds", 2.0)
    monkeypatch.setattr(rc, "request_controls", RequestControlStore())


def test_same_member_different_standard_plans_load_once():
    inner = Store([_report("r1", "ldl", 100), _report("r2", "hba1c", 6.1), _report("r3", "crp", 7)])
    blood = cached_blood(inner)
    hba = QueryPlan(intent=IntentType.latest_result, needs_blood=True, requested_metrics=["hba1c"], time_operation="latest_marker")
    crp = QueryPlan(intent=IntentType.latest_result, needs_blood=True, requested_metrics=["crp"], time_operation="latest_marker")
    first = blood.query(ME, hba)
    second = blood.query(ME, crp)
    assert inner.loads == 1
    assert {marker.key for report in first for marker in report.markers} == {"hba1c"}
    assert {marker.key for report in second for marker in report.markers} == {"crp"}
    assert len(blood.query(ME, QueryPlan(intent=IntentType.latest_result, needs_blood=True, time_operation="latest_marker"))) == 2


def test_members_do_not_share_entries():
    inner = Store([_report("r1", "ldl", 100)])
    blood = cached_blood(inner)
    plan = QueryPlan(intent=IntentType.latest_result, needs_blood=True, time_operation="latest_marker")
    blood.query(ME, plan)
    blood.query(OTHER, plan)
    assert inner.loads == 2
    own = storage_key("blood", ME.subject_id, "latest")
    assert own != storage_key("blood", OTHER.subject_id, "latest")
    assert ME.subject_id not in own


def test_expired_entry_loads_again(monkeypatch):
    monkeypatch.setattr(settings, "health_data_cache_seconds", 1)
    inner = Store([_report("r1", "ldl", 100)])
    blood = cached_blood(inner)
    plan = QueryPlan(intent=IntentType.latest_result, needs_blood=True, time_operation="latest_marker")
    blood.query(ME, plan)
    key = storage_key("blood", ME.subject_id, "standard")
    rc.request_controls._memory[key].expires_at = 0
    blood.query(ME, plan)
    assert inner.loads == 2


def test_history_scope_is_not_served_from_the_latest_two():
    inner = Store([_report(f"r{i}", "ldl", i) for i in range(4)])
    blood = cached_blood(inner)
    latest = QueryPlan(intent=IntentType.latest_result, needs_blood=True, time_operation="latest_marker")
    trend = QueryPlan(intent=IntentType.trend, needs_blood=True, history=True, time_operation="trend")
    assert len(blood.query(ME, latest)) == 2
    assert len(blood.query(ME, trend)) == 4
    assert inner.loads == 2
    assert cache_scope(latest) == "latest"
    assert cache_scope(trend) == "history"


def test_concurrent_misses_load_once():
    inner = Store([_report("r1", "ldl", 1)])
    started = threading.Barrier(4)

    def work():
        started.wait()
        read_through("blood", "member-a", "standard", TypeAdapter(list[BloodReport]), lambda: inner.load_for_cache(ME, "standard"))

    threads = [threading.Thread(target=work) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert inner.loads == 1


def test_lock_failure_and_expired_lock_still_return(monkeypatch):
    calls = {"n": 0}

    def loader():
        calls["n"] += 1
        return ["ok"]

    monkeypatch.setattr(rc.request_controls, "_set_nx", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("redis down")))
    assert read_through("lifestyle", "member-a", "standard", TypeAdapter(list[str]), loader) == ["ok"]

    monkeypatch.setattr(rc.request_controls, "_set_nx", lambda *args, **kwargs: False)
    assert read_through("lifestyle", "member-a", "history", TypeAdapter(list[str]), loader) == ["ok"]
    assert calls["n"] == 2


def test_redis_write_failure_still_returns_the_read(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("redis")

    monkeypatch.setattr(rc.request_controls, "_get", boom)
    monkeypatch.setattr(rc.request_controls, "_set", boom)
    monkeypatch.setattr(rc.request_controls, "_set_nx", boom)
    assert read_through("bio_ai", "member-a", "standard", TypeAdapter(list[str]), lambda: ["score"]) == ["score"]


def test_database_failure_is_not_cached_as_an_empty_result():
    def broken():
        raise RuntimeError("database down")

    with pytest.raises(RuntimeError):
        read_through("blood", "member-a", "standard", TypeAdapter(list[str]), broken)
    assert rc.request_controls._get(storage_key("blood", "member-a", "standard")) is None

    read_through("blood", "member-a", "standard", TypeAdapter(list[str]), lambda: ["fresh"])
    assert read_through("blood", "member-a", "standard", TypeAdapter(list[str]), broken) == ["fresh"]


def test_explicit_invalidation_per_kind():
    for kind in ("blood", "bio_ai", "lifestyle", "questionnaire"):
        read_through(kind, "member-a", "standard", TypeAdapter(list[str]), lambda: [kind])
        invalidate_health_data("member-a", kind)
        assert rc.request_controls._get(storage_key(kind, "member-a", "standard")) is None


def test_general_question_does_not_ask_for_personal_data():
    plan = build_query_plan("What is CRP?")
    assert plan.needs_blood is False
    assert plan.needs_bio_ai is False
    assert plan.needs_personal_data is False


def test_entry_preload_is_scoped_and_a_general_question_starts_nothing():
    from app.contracts.context_ref import ContextRef
    from app.pipeline.me_service import preload_for_entry

    class Reg:
        def __init__(self):
            self.blood_calls = 0
            self.bio_calls = 0

        def blood_query(self, principal, plan):
            self.blood_calls += 1
            assert plan.history is False

        def bio_query(self, principal, plan):
            self.bio_calls += 1
            assert plan.history is False

    class Registry:
        def __init__(self, reg):
            self.blood = type("B", (), {"query": reg.blood_query})()
            self.bio_ai = type("A", (), {"query": reg.bio_query})()

    reg = Reg()
    registry = Registry(reg)
    preload_for_entry(ME, registry, ContextRef(type="blood_report", source="supershyft", entry_point="blood_report_overview"))
    assert reg.blood_calls == 1 and reg.bio_calls == 0
    preload_for_entry(ME, registry, ContextRef(type="bio_ai_report", source="supershyft"))
    assert reg.bio_calls == 1 and reg.blood_calls == 1
    preload_for_entry(ME, registry, None)
    assert reg.blood_calls == 1 and reg.bio_calls == 1


def test_questionnaire_filter_keeps_each_plans_answers():
    from app.contracts.questionnaire import QuestionnaireAnswer, QuestionnaireInstance
    from integrations.supershyft.questionnaire import select_questionnaire_instances

    instance = QuestionnaireInstance(
        assessment_instance_id="1",
        subject_id="member-a",
        answers=[
            QuestionnaireAnswer(response_id="1", assessment_instance_id="1", question_id="1", question_key="sleeping_hours", question="Sleep", value="7", response_type="text", subject_id="member-a"),
            QuestionnaireAnswer(response_id="2", assessment_instance_id="1", question_id="2", question_key="diet_preference", question="Diet", value="vegetarian", response_type="text", subject_id="member-a"),
        ],
    )
    sleep = select_questionnaire_instances(
        [instance],
        QueryPlan(intent=IntentType.questionnaire_lookup, needs_questionnaire=True, topic="sleep", raw_message="how do I sleep"),
    )
    diet = select_questionnaire_instances(
        [instance],
        QueryPlan(intent=IntentType.questionnaire_lookup, needs_questionnaire=True, topic="diet", raw_message="what is my diet"),
    )
    assert [answer.question_key for answer in sleep[0].answers] == ["sleeping_hours"]
    assert "diet_preference" in [answer.question_key for answer in diet[0].answers]
    assert instance.answers[0].question_key == "sleeping_hours"


def _series() -> list[BloodReport]:
    return [
        _report("old-a", "ferritin", 10, date(2024, 1, 1)),
        _report("old-b", "ferritin", 30, date(2024, 6, 1)),
        _report("new-a", "hba1c", 6.1, date(2025, 1, 1)),
        _report("new-b", "ldl", 110, date(2025, 6, 1)),
    ]


def test_marker_in_latest_two_does_not_read_history():
    inner = Store(_series())
    reports = cached_blood(inner).query(ME, _personal(["hba1c"]))
    assert inner.loads == 1
    assert [(m.key, m.value) for r in reports for m in r.markers] == [("hba1c", 6.1)]


def test_marker_missing_from_latest_two_uses_the_newest_older_result():
    inner = Store(_series())
    reports = cached_blood(inner).query(ME, _personal(["ferritin"]))
    assert inner.loads == 2
    found = [(r.report_id, r.report_date, m.value) for r in reports for m in r.markers if m.key == "ferritin"]
    assert found == [("old-b", date(2024, 6, 1), 30)]
    assert all(r.report_id != "old-a" for r in reports)


def test_marker_missing_from_history_stays_absent():
    inner = Store(_series())
    reports = cached_blood(inner).query(ME, _personal(["vitamin_d"]))
    assert inner.loads == 2
    assert _keys(reports) == set()


def _keys(reports):
    return {m.key for r in reports for m in r.markers}


def test_general_and_definition_questions_do_not_read_history():
    inner = Store(_series())
    general = QueryPlan(intent=IntentType.general_health_question, knowledge_scope=KnowledgeScope.general, needs_blood=True, requested_metrics=["ferritin"])
    cached_blood(inner).query(ME, general)
    definition = build_query_plan("What is CRP?")
    cached_blood(inner).query(ME, definition)
    assert "history" not in inner.scopes


def test_explicit_history_request_is_a_single_read():
    inner = Store(_series())
    plan = _personal(["ferritin"], history=True, time_operation="trend")
    cached_blood(inner).query(ME, plan)
    assert inner.scopes == ["history"]


def test_older_value_does_not_replace_the_latest_value():
    reports = [
        _report("old", "hba1c", 9.0, date(2024, 1, 1)),
        _report("mid", "ldl", 100, date(2025, 1, 1)),
        _report("new", "hba1c", 6.1, date(2025, 6, 1)),
    ]
    inner = Store(reports)
    got = cached_blood(inner).query(ME, _personal(["hba1c"]))
    assert inner.loads == 1
    assert [(m.value, m.measured_at) for r in got for m in r.markers] == [(6.1, date(2025, 6, 1))]


def test_history_cache_hit_does_not_load_again():
    inner = Store(_series())
    blood = cached_blood(inner)
    blood.query(ME, _personal(["ferritin"]))
    assert inner.loads == 2
    blood.query(ME, _personal(["ferritin"]))
    assert inner.loads == 2


def test_redis_outage_still_returns_the_historical_marker(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("redis")

    monkeypatch.setattr(rc.request_controls, "_get", boom)
    monkeypatch.setattr(rc.request_controls, "_set", boom)
    monkeypatch.setattr(rc.request_controls, "_set_nx", boom)
    inner = Store(_series())
    reports = cached_blood(inner).query(ME, _personal(["ferritin"]))
    assert any(m.key == "ferritin" and m.value == 30 for r in reports for m in r.markers)


def test_missing_consent_does_not_read_history():
    class Guard(Store):
        def load_for_cache(self, principal, scope):
            if "blood" not in (principal.consent_scopes or []):
                raise PermissionError("consent")
            return super().load_for_cache(principal, scope)

    inner = Guard(_series())
    with pytest.raises(PermissionError):
        cached_blood(inner).query(AuthenticatedPrincipal(subject_id="member-a", consent_scopes=[]), _personal(["ferritin"]))
    assert inner.loads == 0
