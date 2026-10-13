"""The evidence brief follows the person's records and does not invent a clinical score."""

from app.contracts.blood import BloodMarker
from app.contracts.common import AnswerDepth, IntentType, KnowledgeScope, MarkerFlag
from app.contracts.health_context import HealthContext
from app.pipeline.answer_evidence import build_clinical_evidence_brief
from app.pipeline.prompt_builder import _clinical_brief_block


def _marker(key, name, value, flag, **extra):
    return BloodMarker(id=key, key=key, name=name, value=value, unit="u", flag=flag, **extra)


def _context(markers):
    return HealthContext(
        intent=IntentType.report_explanation,
        answer_depth=AnswerDepth.focused,
        knowledge_scope=KnowledgeScope.personal,
        markers=markers,
        task_contract={"goal": "interpret", "primary_source": "blood_report"},
    )


def test_normal_report_does_not_invent_an_abnormality():
    brief = build_clinical_evidence_brief(
        _context([_marker("hemoglobin", "Hemoglobin", 14, MarkerFlag.normal)]),
        primary_source="blood_report",
    )
    assert brief["all_listed_results_within_range"] is True
    assert brief["patterns"] == []


def test_glucose_and_lipid_profiles_select_different_measurements():
    sugar = build_clinical_evidence_brief(
        _context([_marker("hba1c", "HbA1c", 8.2, MarkerFlag.high), _marker("ldl", "LDL", 90, MarkerFlag.normal)]),
        primary_source="blood_report",
    )
    lipids = build_clinical_evidence_brief(
        _context([_marker("ldl", "LDL", 190, MarkerFlag.high), _marker("hba1c", "HbA1c", 5.2, MarkerFlag.normal)]),
        primary_source="blood_report",
    )
    sugar_codes = {row["code"] for group in sugar["patterns"] for row in group["measured_results"]}
    lipid_codes = {row["code"] for group in lipids["patterns"] for row in group["measured_results"]}
    assert "hba1c" in sugar_codes and "ldl" not in sugar_codes
    assert "ldl" in lipid_codes and "hba1c" not in lipid_codes


def test_laboratory_status_is_not_described_as_clinical_importance():
    brief = build_clinical_evidence_brief(
        _context([_marker("creatinine", "Creatinine", 0.5, MarkerFlag.low)]),
        primary_source="blood_report",
    )
    row = brief["patterns"][0]["measured_results"][0]
    assert row["laboratory_status"] == "low"
    assert "clinical_importance" not in row
    assert "score" not in row


def test_blood_brief_is_what_the_answer_prompt_receives():
    text = _clinical_brief_block(
        _context([_marker("alt", "ALT", 90, MarkerFlag.high)]),
        "Help me understand my latest blood report",
    )
    assert "CLINICAL EVIDENCE BRIEF" in text
    assert "alt" in text
    assert "outside the expected range" in text
