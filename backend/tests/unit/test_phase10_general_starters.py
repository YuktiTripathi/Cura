from fastapi.testclient import TestClient

from app.auth.models import AuthenticatedPrincipal
from app.contracts.bio_ai import BioAIRisk
from app.contracts.blood import BloodMarker
from app.contracts.common import IntentType, KnowledgeScope, MarkerFlag
from app.core.copy import GENERAL_KNOWLEDGE_UNAVAILABLE, PERSONAL_DATA_UNAVAILABLE
from app.core.errors import LLMUnavailableError
from app.main import app
from app.pipeline.intent import classify_intent
from app.pipeline.query_planner import build_query_plan
from app.pipeline.starters import HealthSnapshot, build_starters
from app.providers.registry import build_registry, set_registry

client = TestClient(app)
H = {"X-Cura-User-Id": "demo-user-001"}


def chat(message, conversation_id=None, **extra):
    body = {"message": message, **extra}
    if conversation_id:
        body["conversation_id"] = conversation_id
    return client.post("/api/v1/chat", headers=H, json=body)


def test_vitamin_d_followup_stays_general():
    intent, *_ = classify_intent(
        "What are common reasons Vitamin D can be low or high?"
    )
    assert intent == IntentType.general_health_question
    plan = build_query_plan("What are common reasons Vitamin D can be low or high?")
    assert plan.knowledge_scope == KnowledgeScope.general
    assert not plan.needs_personal_data
    assert not plan.needs_supershyft


def test_open_ended_general_questions():
    for msg in (
        "What is Vitamin D?",
        "What is metabolic age?",
        "What causes high LDL?",
        "What does HbA1c measure?",
        "What is insulin resistance?",
        "What is fatty liver?",
        "What does CRP measure?",
        "What is the difference between HDL and LDL?",
        "Why is Vitamin B12 important?",
        "How does the thyroid work?",
    ):
        plan = build_query_plan(msg)
        assert plan.knowledge_scope == KnowledgeScope.general, msg
        assert not plan.needs_supershyft, msg
        assert plan.needs_general, msg


def test_personal_questions_still_personal():
    for msg in ("What is my Vitamin D?", "What is my HbA1c?", "How is my LDL?"):
        plan = build_query_plan(msg)
        assert plan.knowledge_scope == KnowledgeScope.personal, msg
        assert plan.needs_supershyft, msg


def test_general_chat_zero_supershyft_one_llm():
    from app.llm.openai_compatible import OpenAICompatibleLLMClient

    calls = {"llm": 0}
    orig = OpenAICompatibleLLMClient.complete

    def wrap_llm(self, messages, json_mode=False):
        calls["llm"] += 1
        return "Vitamin D is a fat-soluble vitamin involved in bone and immune health."

    OpenAICompatibleLLMClient.complete = wrap_llm
    try:
        body = chat("What is Vitamin D?").json()
        assert body["meta"].get("question_type") == "general_education" or body["meta"]["intent"] == "general_health_question"
        assert body["meta"]["knowledge_scope"] == "general"
        assert body["meta"]["llm_called"] is True
        assert body["meta"]["supershyft_called"] is False
        assert body["meta"]["document_retrieval_called"] is False
        assert PERSONAL_DATA_UNAVAILABLE not in body["answer"]
        assert calls["llm"] == 1
        chips = body["follow_ups"]
        assert chips
        assert any("common reasons" in c["text"].lower() or "low or high" in c["text"].lower() for c in chips)
    finally:
        OpenAICompatibleLLMClient.complete = orig


def test_general_then_general_followup_no_supershyft():
    first = chat("What is Vitamin D?").json()
    cid = first["conversation_id"]
    follow = next(
        c["text"]
        for c in first["follow_ups"]
        if c.get("knowledge_scope") == "general" or not c.get("requires_personal_context")
    )
    class Boom:
        def query(self, *a, **k):
            raise AssertionError("SuperShyft should not be queried")
        def get_profile(self, *a, **k):
            raise AssertionError("profile should not be queried")

    reg = build_registry()
    boom = Boom()
    orig_b, orig_u = reg.blood, reg.users
    reg.blood = boom
    set_registry(reg)
    try:
        second = chat(follow, cid).json()
        assert second["meta"]["supershyft_called"] is False
        assert second["meta"].get("question_type") == "general_education" or second["meta"]["intent"] == "general_health_question"
        assert PERSONAL_DATA_UNAVAILABLE not in second["answer"]
    finally:
        reg.blood = orig_b
        set_registry(None)


def test_general_then_personal_followup():
    first = chat("What is Vitamin D?").json()
    cid = first["conversation_id"]
    mine = chat("What is my Vitamin D level?", cid).json()
    assert mine["meta"]["supershyft_called"] is True
    assert mine["meta"].get("question_type") != "general_education"
    assert "12.6" in mine["answer"]


def test_general_then_document_followup():
    plan = build_query_plan(
        "What does my uploaded report say about Vitamin D?",
        uploaded_document_count=1,
    )
    assert plan.needs_user_uploaded
    assert not plan.needs_supershyft
    first = chat("What is Vitamin D?").json()
    follow = build_query_plan(
        "What does my uploaded report say about Vitamin D?",
        "vitamin_d",
        prior_personal=False,
        uploaded_document_count=1,
        prior_source_mode="general",
    )
    assert follow.needs_user_uploaded
    assert not follow.needs_supershyft
    assert first["meta"]["knowledge_scope"] == "general"


def test_llm_unavailable_does_not_use_supershyft():
    from app.llm.openai_compatible import OpenAICompatibleLLMClient

    def boom(self, messages, json_mode=False):
        raise LLMUnavailableError("down")

    orig = OpenAICompatibleLLMClient.complete
    OpenAICompatibleLLMClient.complete = boom
    try:
        body = chat("What is Vitamin D?").json()
        assert PERSONAL_DATA_UNAVAILABLE not in body["answer"]
        assert body["meta"]["supershyft_called"] is False
        assert body["meta"]["llm_called"] is True
        assert "12.6" not in body["answer"]
        assert (
            GENERAL_KNOWLEDGE_UNAVAILABLE in body["answer"]
            or "general medical knowledge" in body["answer"].lower()
            or "calcium" in body["answer"].lower()
            or "bone" in body["answer"].lower()
        )
    finally:
        OpenAICompatibleLLMClient.complete = orig


def test_starters_case_a_many_markers():
    res = client.get("/api/v1/me", headers=H).json()
    assert len(res["starters"]["personal"]) == 3
    assert len(res["starters"]["general"]) == 2
    texts = " ".join(q["text"] for q in res["starters"]["personal"])
    assert "Vitamin D" in texts or "LDL" in texts or "HbA1c" in texts
    assert all(q["knowledge_scope"] == "personal" for q in res["starters"]["personal"])
    assert all(q["knowledge_scope"] == "general" for q in res["starters"]["general"])
    assert "my Vitamin D" not in " ".join(q["text"] for q in res["starters"]["general"]).replace("What is Vitamin D", "")


def test_starters_case_b_one_marker():
    from datetime import date as d

    snap = HealthSnapshot(
        available=True,
        has_blood=True,
        markers=[
            BloodMarker(id="1", key="hba1c", name="HbA1c", value=5.5, flag=MarkerFlag.normal)
        ],
        marker_history={"hba1c": 1},
    )
    p = AuthenticatedPrincipal(subject_id="one", display_name="A")
    set_q = build_starters(p, build_registry(), snapshot=snap)
    assert len(set_q.personal) == 1
    assert "HbA1c" in set_q.personal[0].text
    assert len(set_q.general) >= 2
    assert len(set_q.personal) + len(set_q.general) >= 3


def test_starters_case_c_unavailable():
    p = AuthenticatedPrincipal(subject_id="x", display_name="")
    out = build_starters(p, build_registry(), profile_available=False)
    assert out.personal == []
    assert len(out.general) == 2
    assert out.personal_unavailable is True


def test_starters_case_d_bio_only():
    snap = HealthSnapshot(
        available=True,
        has_bio=True,
        bio_risks=[BioAIRisk(code="cardiac_health", name="Cardiac health", score=30)],
    )
    p = AuthenticatedPrincipal(subject_id="bio", display_name="A")
    out = build_starters(p, build_registry(), snapshot=snap)
    assert out.personal
    assert any("Cardiac" in q.text or "cardiac" in q.text.lower() for q in out.personal)


def test_starters_stay_english_when_language_query_is_sent():
    res = client.get("/api/v1/me?language=hi", headers=H).json()
    blob = " ".join(q["text"] for q in res["starters"]["personal"] + res["starters"]["general"])
    assert not any("\u0900" <= ch <= "\u097F" for ch in blob)
    assert "HbA1c" in blob or "LDL" in blob or "Vitamin D" in blob or "TSH" in blob or "Vitamin B12" in blob


def test_starter_click_scopes():
    me = client.get("/api/v1/me", headers=H).json()
    gen = me["starters"]["general"][0]["text"]
    pers = me["starters"]["personal"][0]["text"]
    g = chat(gen).json()
    assert g["meta"]["knowledge_scope"] == "general"
    assert g["meta"]["llm_called"] is True
    assert g["meta"]["supershyft_called"] is False
    p = chat(pers).json()
    assert p["meta"]["knowledge_scope"] == "personal"
    assert p["meta"]["supershyft_called"] is True
