"""One test per turn kind: what it loads, which prompt module it adds, and the shape it returns."""

import pytest

from app.contracts.common import AnswerDepth, IntentType
from app.contracts.context_ref import ContextRef
from app.contracts.health_context import HealthContext
from app.contracts.query import QueryPlan
from app.pipeline import prompt_modules
from app.pipeline.prompt_modules import house_system
from app.pipeline.query_planner import _apply_context_ref
from app.pipeline.turn_kinds import REGISTRY, TurnKind, kind_of, resolve_turn_kind, spec_for


def _plan(**kw):
    return QueryPlan(intent=IntentType.general_health_question, raw_message="x", **kw)


def _ctx(kind="general"):
    return HealthContext(intent=IntentType.bio_ai_explanation, answer_depth=list(AnswerDepth)[0], turn_kind=kind)


def test_every_kind_has_a_spec_and_shares_the_house_prompt():
    assert set(REGISTRY) == set(TurnKind)
    assert house_system(_ctx("general"), "a question") == prompt_modules.HOUSE_CORE.strip()


@pytest.mark.parametrize(
    "ref,kind,blood,bio,quest",
    [
        (ContextRef(type="bio_ai_risk", source="supershyft", risk_code="x", entry_point="risk_explainer"), TurnKind.bio_ai_risk, True, True, True),
        (ContextRef(type="bio_ai_report", source="supershyft", entry_point="health_area"), TurnKind.health_area, True, True, True),
    ],
)
def test_card_entry_points_load_what_their_kind_needs(ref, kind, blood, bio, quest):
    plan = _apply_context_ref(_plan(), ref)
    assert resolve_turn_kind(plan.raw_message, plan.entry_point) == kind
    assert (plan.needs_blood, plan.needs_bio_ai, plan.needs_questionnaire) == (blood, bio, quest)


def test_a_plain_tap_without_an_entry_point_stays_general_and_narrow():
    plan = _apply_context_ref(_plan(), ContextRef(type="bio_ai_risk", source="supershyft", risk_code="x"))
    assert resolve_turn_kind(plan.raw_message, plan.entry_point) == TurnKind.general
    assert plan.needs_blood is False


def test_typed_text_only_matches_the_nutrition_overview():
    assert resolve_turn_kind("What should I know about my nutrition?") == TurnKind.nutrition_overview
    assert resolve_turn_kind("What can I eat to lower my LDL?") == TurnKind.general
    assert resolve_turn_kind("What does my Hypertension risk mean?") == TurnKind.general


@pytest.mark.parametrize("kind", [TurnKind.bio_ai_risk, TurnKind.health_area, TurnKind.nutrition_overview])
def test_each_kind_uses_the_same_house_prompt(kind):
    system = house_system(_ctx(kind.value), "a question")
    assert system == prompt_modules.HOUSE_CORE.strip()
    assert "valid JSON object" in system


def test_card_kinds_keep_their_layout_and_the_rest_do_not():
    assert spec_for(TurnKind.bio_ai_risk).keep_layout and spec_for(TurnKind.bio_ai_risk).card == "risk_explanation"
    assert spec_for(TurnKind.nutrition_overview).card == "nutrition_plan"
    assert not spec_for(TurnKind.general).keep_layout and spec_for(TurnKind.general).card is None
    assert kind_of(_ctx("health_area"), "x") == TurnKind.health_area


def test_a_bio_ai_report_id_does_not_hide_the_blood_report():
    from app.contracts.blood import BloodReport
    from integrations.supershyft.ihr import shape_blood_reports

    blood = BloodReport(report_id="blood-1", report_date="2026-08-25", markers=[])
    plan = _plan(report_id="bioai-9", needs_blood=True, needs_bio_ai=True)
    assert [r.report_id for r in shape_blood_reports([blood], plan)] == ["blood-1"]
