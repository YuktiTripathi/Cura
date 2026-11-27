from app.contracts.bio_ai import BioAIRisk
from app.contracts.blood import BloodMarker
from app.contracts.common import AnswerDepth, IntentType
from app.contracts.context_ref import ContextRef
from app.contracts.health_context import HealthContext
from app.pipeline.query_planner import _apply_context_ref
from app.pipeline.response_mode import plain_answer
from app.pipeline.risk_explanation import action_icon, parse_risk_explanation

ANSWER = """## What is Type 2 diabetes?
Your body turns food into sugar for energy. A hormone called insulin works like a key.

In Type 2 diabetes the key stops working well, so extra sugar stays in your blood.

## What does this mean for you?
Your result is in the healthy band today. Daily habits keep it that way.

## Want to know your current blood sugar health?
Your HbA1c test shows how your sugar has been over three months.
Button: Check my blood sugar results
- **HbA1c**: shows your average blood sugar over three months.
- **Made up test**: not in the report.

## What can you do?
- **Eat balanced meals**: Add dal and vegetables at lunch.
- **Walk daily**: Walk 30 minutes after dinner.
- **Sleep well**: Keep a steady bedtime.

## More to explore
### Common signs
- Feeling very thirsty
### What can raise this risk
- Low activity
- Family history
"""


def _ctx():
    return HealthContext(intent=IntentType.bio_ai_explanation, answer_depth=list(AnswerDepth)[0], turn_kind="bio_ai_risk")


def _parse(markers):
    risk = BioAIRisk(code="type_2_diabetes", name="Type 2 diabetes", score=17, status="Healthy", percentile=4, lifestyle_contribution=18, contributing_factors=["Low activity"])
    cleaned = plain_answer(ANSWER, None, _ctx(), whole_report=False, keep_layout=True)
    return parse_risk_explanation(cleaned, risk=risk, markers=markers)


def test_explanation_is_split_into_the_four_steps_after_cleanup():
    marker = BloodMarker(id="1", key="hba1c", name="HbA1c", value=5.2, unit="%", reference_low=4, reference_high=5.6)
    parsed = _parse([marker])
    assert parsed.condition_title == "What is Type 2 diabetes?" and len(parsed.condition) == 2
    assert parsed.meaning_title.startswith("What does this mean")
    assert [a.icon for a in parsed.actions] == ["meal", "move", "sleep"]
    assert [s.title for s in parsed.more] == ["Common signs", "What can raise this risk"]


def test_score_and_blood_values_come_from_the_report_not_the_model():
    marker = BloodMarker(id="1", key="hba1c", name="HbA1c", value=5.2, unit="%", reference_low=4, reference_high=5.6)
    parsed = _parse([marker])
    assert parsed.score_card.score == 17 and parsed.score_card.status == "Healthy" and parsed.score_card.level == "not_raised"
    assert [t.finding.value for t in parsed.related_tests] == ["5.2"]  # the invented test is dropped
    assert _parse([]).related_tests == []


def test_a_plain_paragraph_is_not_an_explanation():
    risk = BioAIRisk(code="x", name="X", score=1, status="Healthy")
    assert parse_risk_explanation("Just a paragraph.", risk=risk, markers=[]) is None


def test_action_icons_use_the_title_first():
    assert action_icon("Walk daily") == "move"
    assert action_icon("Something else") == "habit"


def test_only_the_explicit_entry_point_makes_an_explanation():
    from app.contracts.query import QueryPlan

    base = QueryPlan(intent=IntentType.general_health_question, raw_message="What does my Type 2 diabetes risk mean?")
    ask = ContextRef(type="bio_ai_risk", source="supershyft", risk_code="type_2_diabetes", entry_point="risk_explainer")
    plan = _apply_context_ref(base, ask)
    assert plan.entry_point == "risk_explainer" and plan.needs_blood is True
    other = _apply_context_ref(base, ContextRef(type="bio_ai_risk", source="supershyft", risk_code="type_2_diabetes"))
    assert other.entry_point is None and other.needs_blood is False


def test_risk_explainer_prompt_is_added_only_for_the_explainer():
    from app.pipeline.prompt_modules import RISK_EXPLAINER, house_system

    assert "—" not in RISK_EXPLAINER and "–" not in RISK_EXPLAINER
    for heading in ("## What does this mean for you?", "Button: Check my", "## What can you do?", "## More to explore"):
        assert heading in RISK_EXPLAINER
    on = house_system(_ctx(), "What does my Type 2 diabetes risk result mean?")
    off_ctx = HealthContext(intent=IntentType.bio_ai_explanation, answer_depth=list(AnswerDepth)[0])
    assert RISK_EXPLAINER not in on
    assert RISK_EXPLAINER not in house_system(off_ctx, "What can I do about my Type 2 diabetes risk?")
    assert on == house_system(off_ctx, "What can I do about my Type 2 diabetes risk?")


def test_points_are_bullets_and_stock_notes_are_dropped():
    text = ANSWER.replace(
        "Your body turns food into sugar for energy. A hormone called insulin works like a key.\n\nIn Type 2 diabetes the key stops working well, so extra sugar stays in your blood.",
        "- Your body turns food into sugar.\n- Insulin works like a key.\n- This card is an estimate of future risk, not a diagnosis.",
    ) + "### Blood tests doctors use\n- Your report did not list specific markers, so this section is left out.\n"
    risk = BioAIRisk(code="t", name="T", score=1, status="Healthy")
    parsed = parse_risk_explanation(plain_answer(text, None, _ctx(), whole_report=False, keep_layout=True), risk=risk, markers=[])
    assert parsed.condition == ["Your body turns food into sugar.", "Insulin works like a key."]
    assert [s.title for s in parsed.more] == ["Common signs", "What can raise this risk"]


def test_everyday_names_come_first_and_unknown_risks_keep_the_report_name():
    from app.biomarkers.risk_overview import _display, _registry

    reg = _registry()
    assert _display(reg, "hypertension", "Hypertension") == {"name": "High Blood Pressure", "medical": "Hypertension"}
    assert _display(reg, "nafld", "NAFLD")["name"] == "Fatty Liver"
    assert _display(reg, "hypothyroidism", "x")["name"] == "Underactive Thyroid"
    assert _display(reg, "oxidative_stress", "Oxidative Stress")["explain"]
    assert _display(reg, "brand_new_risk", "Brand New Risk") == {"name": "Brand New Risk"}
    assert reg["_group_of"]["hypothyroidism"] == "thyroid_health"


def test_related_card_wording_is_written_for_the_condition():
    marker = BloodMarker(id="1", key="hba1c", name="HbA1c", value=5.2, unit="%", reference_low=4, reference_high=5.6)
    parsed = _parse([marker])
    assert parsed.related_title == "Want to know your current blood sugar health?"
    assert parsed.related_text.startswith("Your HbA1c test")
    assert parsed.related_button == "Check my blood sugar results"
    assert _parse([]).related_title == ""  # no verified test, no card


def test_overview_questions_load_blood_results_and_habits_together():
    from app.contracts.query import QueryPlan

    base = QueryPlan(intent=IntentType.general_health_question, raw_message="What do my blood tests say about my heart health?")
    area = _apply_context_ref(base, ContextRef(type="bio_ai_report", source="supershyft", entry_point="health_area"))
    assert area.needs_blood and area.needs_bio_ai and area.needs_questionnaire and area.entry_point == "health_area"
    plain = _apply_context_ref(base, ContextRef(type="bio_ai_report", source="supershyft"))
    assert plain.needs_blood is False and plain.entry_point is None


def test_overview_context_sees_the_whole_panel_and_gets_the_area_prompt():
    from app.pipeline.prompt_builder import _relevant_markers
    from app.pipeline.prompt_modules import HEALTH_AREA, house_system

    marker = BloodMarker(id="1", key="ldl", name="LDL", value=120, unit="mg/dL", reference_low=0, reference_high=100)
    ctx = HealthContext(intent=IntentType.bio_ai_explanation, answer_depth=list(AnswerDepth)[0], turn_kind="health_area", markers=[marker])
    assert _relevant_markers(ctx) == [marker]
    assert HEALTH_AREA not in house_system(ctx, "What do my blood tests say about my heart health?")
    assert "—" not in HEALTH_AREA and "–" not in HEALTH_AREA


def test_missing_item_note_is_a_sentence_not_a_reason_code():
    from app.pipeline.validator import _missing_sentence

    assert _missing_sentence("Cardiac Health", "no_reports") == "Cardiac Health is not in your reports."
    assert "no_reports" not in _missing_sentence("X", "weird_code")
