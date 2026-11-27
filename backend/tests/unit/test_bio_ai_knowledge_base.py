import json

import pytest

from app.pipeline.prompt_modules import house_system
from app.retrieval.hybrid import HybridMedicalKnowledgeProvider
from app.retrieval.medical import (
    BIO_AI_EXPLAINER,
    active_corpus,
    is_servable,
    passage_label,
)

provider = HybridMedicalKnowledgeProvider()


def _guide():
    return [doc for doc in active_corpus() if doc.provenance == BIO_AI_EXPLAINER]


def test_guide_is_loaded_and_servable_in_production_mode():
    docs = _guide()
    assert len(docs) >= 18
    assert all(is_servable(doc) for doc in docs)
    # The system instructions section is not served as evidence.
    assert not any("system instructions" in doc.excerpt.lower() for doc in docs)


def test_existing_content_is_published():
    assert all(is_servable(doc) for doc in active_corpus() if doc.provenance == "cura_knowledge_base")


def test_guide_text_has_no_dashes_or_markup():
    for doc in _guide():
        assert "–" not in doc.excerpt and "—" not in doc.excerpt
        assert "**" not in doc.excerpt and "≠" not in doc.excerpt


def test_reviewer_and_date_never_reach_the_model_text():
    for doc in _guide():
        text = passage_label(doc)
        assert "Yukti" not in text and "2026-11-18" not in text


@pytest.mark.parametrize(
    "question,expected",
    [
        ("What is Bio-AI?", "What is Bio-AI"),
        ("Does a risk score of 75 mean a 75% chance of diabetes?", "Score"),
        ("What is metabolic age?", "Metabolic age"),
        ("What is a percentile in my report?", "percentile"),
        ("How can I improve my Bio-AI score?", "What can change my risk score"),
        ("When should I see a doctor about my Bio-AI score?", "When should I see a doctor"),
        ("Why is my Bio-AI risk high if my blood tests are normal?", "blood tests are normal"),
    ],
)
def test_bio_ai_questions_find_the_guide(question, expected):
    hits = provider.query(question, None, limit=3)
    assert any(expected.lower() in doc.title.lower() for doc in hits), [d.title for d in hits]
    assert any(doc.provenance == BIO_AI_EXPLAINER for doc in hits)


def test_guide_does_not_appear_for_other_questions():
    for question in ("What is LDL cholesterol?", "How do I lower triglycerides?", "What is high risk pregnancy?"):
        assert not any(d.provenance == BIO_AI_EXPLAINER for d in provider.query(question, None, limit=5))


def test_personal_question_can_use_only_the_guide():
    hits = provider.query("Explain my Bio-AI report", None, limit=2, only_provenance=BIO_AI_EXPLAINER)
    assert hits and all(doc.provenance == BIO_AI_EXPLAINER for doc in hits)


def test_bio_ai_rules_only_for_bio_ai_questions():
    from app.contracts.common import AnswerDepth, IntentType
    from app.contracts.health_context import HealthContext

    context = HealthContext(intent=IntentType.general_health_question, answer_depth=AnswerDepth.focused)
    score = house_system(context, "What is my Bio-AI score?")
    ldl = house_system(context, "What is my LDL?")
    assert score == ldl
    assert "predicted risks, not confirmed diagnoses" in score


def test_response_never_shows_reviewer_or_review_date():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    reply = client.post(
        "/api/v1/chat",
        headers={"X-Cura-User-Id": "demo-user-001"},
        json={"message": "What is Bio-AI?"},
    )
    assert reply.status_code == 200
    blob = json.dumps(reply.json()).lower()
    assert "yukti" not in blob and "2026-11-18" not in blob and "reviewer" not in blob


def test_why_my_risk_is_high_if_my_marker_is_normal_is_personal():
    from app.pipeline.intent import requires_personal_record

    for question in (
        "Why is my Bio-AI cardiac risk high if my cholesterol is normal?",
        "Why is my diabetes risk high if my HbA1c is normal?",
    ):
        assert requires_personal_record(question) is True

    from fastapi.testclient import TestClient

    from app.main import app

    reply = TestClient(app).post(
        "/api/v1/chat",
        headers={"X-Cura-User-Id": "demo-user-001"},
        json={"message": "Why is my Bio-AI cardiac risk high if my cholesterol is normal?"},
    ).json()
    names = [s["name"] for s in reply["provenance"]["sources"]]
    assert "WHO" not in names and "MedlinePlus" not in names
