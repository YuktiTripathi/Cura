from fastapi.testclient import TestClient

from app.main import app
from app.pipeline.grounding import GroundingChecker
from app.pipeline.intent import requires_personal_record
from app.pipeline.provenance import build_user_provenance
from app.pipeline.query_planner import build_query_plan
from app.retrieval.medical import MedicalEvidenceDoc, retrieve_medical_evidence
from app.contracts.common import IntentType, KnowledgeScope
from app.contracts.evidence import EvidenceRecord
from datetime import date

client = TestClient(app)
H = {"X-Cura-User-Id": "demo-user-001"}


def test_bio_ai_report_uses_personal_source_label():
    plan = build_query_plan("Explain my latest Bio-AI report")
    assert plan.needs_personal_data
    assert plan.needs_supershyft
    assert "bio_ai_report" in plan.data_sources
    body = client.post("/api/v1/chat", headers=H, json={"message": "Explain my latest Bio-AI report"}).json()
    names = [s["name"] for s in body["provenance"]["sources"]]
    assert any("bio-ai" in name.lower() or "bio ai" in name.lower() for name in names)
    assert "supershyft" not in " ".join(names).lower()
    assert not any("id" in s["name"].lower() for s in body["provenance"]["sources"])


def test_latest_hba1c_uses_blood_report_source():
    plan = build_query_plan("What was my latest HbA1c?")
    assert plan.needs_personal_data
    assert plan.needs_blood
    body = client.post("/api/v1/chat", headers=H, json={"message": "What was my latest HbA1c?"}).json()
    names = [s["name"] for s in body["provenance"]["sources"]]
    assert any("blood report" in name.lower() for name in names)


def test_hypertension_general_uses_retrieved_who():
    plan = build_query_plan("What is hypertension?")
    assert plan.intent == IntentType.general_health_question
    assert plan.knowledge_scope == KnowledgeScope.general
    assert not plan.needs_supershyft
    assert plan.medical_evidence_required
    docs = retrieve_medical_evidence("What is hypertension?", plan.topic, limit=1)
    assert docs
    assert docs[0].name == "WHO"
    body = client.post("/api/v1/chat", headers=H, json={"message": "What is hypertension?"}).json()
    assert body["meta"]["supershyft_called"] is False
    names = [s["name"] for s in body["provenance"]["sources"]]
    assert names
    assert "WHO" in names or "CDC" in names or "NICE" in names
    assert all(
        s.get("url")
        for s in body["provenance"]["sources"]
        if s["name"] in {"WHO", "CDC", "NICE"}
    )


def test_explicit_general_only_request_never_calls_supershyft():
    body = client.post(
        "/api/v1/chat",
        headers=H,
        json={"message": "Explain heart health without using my reports."},
    ).json()

    assert body["meta"]["knowledge_scope"] == "general"
    assert body["meta"]["supershyft_called"] is False
    assert "personal supershyft health data" not in body["answer"].lower()
    assert not any(
        source["source_type"] == "personal_record"
        for source in body["provenance"]["sources"]
    )


def test_hyperthyroidism_symptoms_use_retrieved_evidence():
    plan = build_query_plan("What are the symptoms of hyperthyroidism?")
    assert plan.knowledge_scope == KnowledgeScope.general
    assert plan.medical_evidence_required
    docs = retrieve_medical_evidence("What are the symptoms of hyperthyroidism?", plan.topic)
    assert docs
    body = client.post("/api/v1/chat", headers=H, json={"message": "What are the symptoms of hyperthyroidism?"}).json()
    names = [s["name"] for s in body["provenance"]["sources"]]
    assert names
    assert set(names) <= {"NIDDK", "MedlinePlus", "NICE", "WHO", "CDC"}


def test_if_my_thyroid_is_high_does_not_query_supershyft():
    msg = "If my thyroid is high, what should I do?"
    assert requires_personal_record(msg) is False
    plan = build_query_plan(msg)
    assert plan.personal_reference is True
    assert plan.personal_data_required is False
    assert plan.needs_supershyft is False
    assert plan.medical_evidence_required is True
    body = client.post("/api/v1/chat", headers=H, json={"message": msg}).json()
    assert body["meta"]["supershyft_called"] is False
    assert body["meta"]["ihr_queried"] in {False, None}
    assert body["provenance"]["sources"]


def test_based_on_thyroid_report_is_personal_and_may_add_medical():
    msg = "Based on my thyroid report, what should I do?"
    assert requires_personal_record(msg) is True
    plan = build_query_plan(msg)
    assert plan.needs_personal_data
    assert plan.medical_evidence_required
    body = client.post("/api/v1/chat", headers=H, json={"message": msg}).json()
    names = [s["name"] for s in body["provenance"]["sources"]]
    assert any("blood report" in name.lower() for name in names)
    assert "supershyft" not in names


def test_provenance_builder_never_uses_internal_names():
    plan = build_query_plan("What was my latest HbA1c?")
    evidence = [
        EvidenceRecord(
            evidence_id="ev-1",
            report_id="blood-002",
            report_type="blood_report",
            report_date=date(2026, 1, 2),
            source="supershyft",
            marker="HbA1c",
        )
    ]
    prov = build_user_provenance(plan, evidence, [])
    assert any("blood report" in s.name.lower() for s in prov.sources)
    assert all("blood-002" not in s.name for s in prov.sources)


def test_grounding_strips_invented_sources():
    docs = [
        MedicalEvidenceDoc(
            name="WHO",
            url="https://www.who.int/news-room/fact-sheets/detail/hypertension",
            source_type="guideline",
            tier=1,
            topics=("hypertension",),
            keywords=("hypertension",),
            excerpt="Hypertension is high blood pressure.",
        )
    ]
    text, flags = GroundingChecker().sanitize_medical_answer(
        "According to Mayo Clinic, hypertension is always high blood pressure. Source: Mayo Clinic",
        docs,
    )
    assert "invented_medical_source" in flags
    assert "Mayo Clinic" not in text
    assert "Source:" not in text
    assert "You should can" not in text
    assert "never" not in text.lower() or "not a single universal" in text.lower() or "retrieved medical information" in text.lower()


def test_hba1c_foods_question_is_general_and_has_nutrition_evidence():
    msg = "What foods are commonly discussed in relation to HbA1c?"
    plan = build_query_plan(msg)
    assert plan.intent == IntentType.general_health_question
    assert not plan.needs_personal_data
    docs = retrieve_medical_evidence(msg, plan.topic, limit=2)
    assert docs
    assert any("food" in " ".join(doc.keywords) or "diet" in " ".join(doc.keywords) for doc in docs)


def test_hba1c_foods_does_not_present_index_text_as_an_answer_when_llm_unavailable(monkeypatch):
    from app.core.config import settings
    from app.core.errors import LLMUnavailableError
    from app.llm.openai_compatible import OpenAICompatibleLLMClient

    monkeypatch.setattr(settings, "enable_llm", True)

    def boom(self, messages, json_mode=False):
        raise LLMUnavailableError("down")

    monkeypatch.setattr(OpenAICompatibleLLMClient, "complete", boom)
    body = client.post(
        "/api/v1/chat",
        headers=H,
        json={"message": "What foods are commonly discussed in relation to HbA1c?"},
    ).json()
    answer = body["answer"].lower()
    assert "can't access the general medical knowledge" in answer
    assert body["meta"]["intent"] == "general_health_question"
    assert body["meta"]["llm_mode"] == "unavailable"
    names = [s["name"] for s in body["provenance"]["sources"]]
    assert names
    assert set(names) <= {"NIDDK", "CDC", "MedlinePlus", "WHO", "NICE"}
    assert "Blood Report" not in names
    assert "source pointer" not in answer


def test_vitamin_d_does_not_present_index_text_as_an_answer_when_llm_unavailable(monkeypatch):
    from app.core.config import settings
    from app.core.errors import LLMUnavailableError
    from app.llm.openai_compatible import OpenAICompatibleLLMClient

    monkeypatch.setattr(settings, "enable_llm", True)

    def boom(self, messages, json_mode=False):
        raise LLMUnavailableError("down")

    monkeypatch.setattr(OpenAICompatibleLLMClient, "complete", boom)
    body = client.post(
        "/api/v1/chat",
        headers=H,
        json={"message": "What does Vitamin D do in the body?"},
    ).json()
    answer = body["answer"].lower()
    assert "can't access the general medical knowledge" in answer
    assert "source pointer" not in answer
    assert body["meta"]["llm_mode"] == "unavailable"


def test_lifestyle_hba1c_follow_up_stays_general(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "enable_llm", False)
    first = client.post("/api/v1/chat", headers=H, json={"message": "What is my latest HbA1c?"}).json()
    cid = first["conversation_id"]
    second = client.post(
        "/api/v1/chat",
        headers=H,
        json={"conversation_id": cid, "message": "How can lifestyle affect HbA1c?"},
    ).json()
    assert second["meta"]["intent"] == "general_health_question"
    assert "can't access the general medical knowledge" not in second["answer"].lower()
    names = [s["name"] for s in second["provenance"]["sources"]]
    assert "Blood Report" not in names
    assert names
