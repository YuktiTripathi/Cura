from app.contracts.blood import BloodMarker
from app.contracts.common import AnswerDepth, IntentType, KnowledgeScope, MarkerFlag
from app.contracts.health_context import HealthContext
from app.contracts.query import QueryPlan
from app.pipeline.clinical_thresholds import clinical_note, clinical_notes
from app.pipeline.micro_insights import compose_micro_insight


def _marker(key, name, value, unit, flag=MarkerFlag.high, **extra):
    return BloodMarker(id=key, key=key, name=name, value=value, unit=unit, flag=flag, **extra)


def test_hba1c_in_diabetes_range_is_urgent():
    note = clinical_note(_marker("Hba1c", "Hba1c", 9.1, "%"))
    assert note and note.urgent
    assert "6.5%" in note.text and "doctor soon" in note.text


def test_hba1c_prediabetes_is_not_urgent():
    note = clinical_note(_marker("hba1c", "HbA1c", 6.0, "%"))
    assert note and not note.urgent and "prediabetes" in note.text


def test_unit_mismatch_is_ignored():
    assert clinical_note(_marker("triglycerides", "Triglycerides", 3.0, "mmol/L")) is None


def test_normal_values_have_no_note():
    assert clinical_note(_marker("hba1c", "HbA1c", 5.2, "%", MarkerFlag.normal)) is None
    assert clinical_note(_marker("ldl", "LDL Cholestrol Calculated", 128.25, "mg/dl")) is None


def test_notes_put_urgent_first():
    notes = clinical_notes([
        _marker("triglycerides", "Triglycerides", 265.9, "mg/dl"),
        _marker("hba1c", "Hba1c", 9.1, "%"),
    ])
    assert [n.marker.key for n in notes] == ["hba1c", "triglycerides"]


def test_micro_insight_adds_clinical_note_to_range():
    marker = _marker("hba1c", "Hba1c", 9.1, "%", reference_low=4.2, reference_high=5.7)
    context = HealthContext(
        intent=IntentType.latest_result, answer_depth=AnswerDepth.simple,
        knowledge_scope=KnowledgeScope.personal, markers=[marker],
    )
    plan = QueryPlan(intent=IntentType.latest_result, knowledge_scope=KnowledgeScope.personal, needs_blood=True)
    text = compose_micro_insight(plan=plan, context=context, presentation=None, llm_called=False)
    assert "upper reference limit" in text and "diagnose diabetes" in text
