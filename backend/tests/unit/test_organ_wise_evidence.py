"""The evidence a whole report answer is written from names the body system and carries the counts."""

from app.contracts.blood import BloodMarker
from app.contracts.common import AnswerDepth, IntentType, KnowledgeScope, MarkerFlag
from app.contracts.health_context import BioAIRisk, HealthContext
from app.pipeline.answer_evidence import build_clinical_evidence_brief


def _marker(i, key, name, value, flag, unit="mg/dL"):
    return BloodMarker(id=str(i), key=key, name=name, value=value, unit=unit, flag=flag)


def _ctx(markers=(), risks=()):
    return HealthContext(
        intent=IntentType.report_explanation,
        answer_depth=AnswerDepth.broad,
        knowledge_scope=KnowledgeScope.personal,
        markers=list(markers),
        bio_ai_risks=list(risks),
    )


def test_blood_brief_has_counts_and_body_systems():
    markers = [
        _marker(1, "ldl", "LDL Cholesterol", 178.8, MarkerFlag.high),
        _marker(2, "vitamin_d", "Vitamin D", 9.67, MarkerFlag.low, "ng/mL"),
        _marker(3, "alt", "ALT", 22, MarkerFlag.normal, "U/L"),
        _marker(4, "creatinine", "Creatinine", 0.9, MarkerFlag.normal),
        _marker(5, "tsh", "TSH", 2.1, MarkerFlag.normal, "uIU/mL"),
    ]
    brief = build_clinical_evidence_brief(_ctx(markers), primary_source="blood_report")
    assert brief["report_counts"] == {"outside_range": 2, "within_range": 3, "total_results": 5}
    systems = {p["body_system"] for p in brief["patterns"]}
    assert any("Heart and blood vessels" in s for s in systems)
    assert any("Bones" in s for s in systems)
    fine = {row["body_system"] for row in brief["within_range_by_body_system"]}
    assert "Liver" in fine and any("Kidneys" in s for s in fine) and any("Thyroid" in s for s in fine)


def test_bio_ai_brief_has_counts_and_the_organ_of_each_assessment():
    risks = [
        BioAIRisk(code="oxidative_stress", name="Oxidative Stress", score=64, status="High"),
        BioAIRisk(code="nafld", name="NAFLD", score=18, status="Healthy"),
        BioAIRisk(code="cardiac_health", name="Cardiac Health", score=19, status="Healthy"),
    ]
    brief = build_clinical_evidence_brief(_ctx(risks=risks), primary_source="bio_ai")
    assert brief["report_counts"] == {"assessment_areas": 3, "raised": 1}
    by_name = {a["name"]: a.get("body_system") for a in brief["assessments"]}
    assert by_name["NAFLD"] == "Liver"
    assert by_name["Cardiac Health"] == "Heart and blood vessels"
    assert "Whole body" in by_name["Oxidative Stress"]
