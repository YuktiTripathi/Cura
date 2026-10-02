from app.contracts.common import IntentType, KnowledgeScope
from app.core.copy import PERSONAL_DATA_UNAVAILABLE, personal_data_unavailable
from app.pipeline.language import normalize_for_intent
from app.pipeline.query_planner import build_query_plan
from app.providers.registry import build_registry, set_registry
from fastapi.testclient import TestClient

from app.core.errors import ProviderUnavailableError
from app.main import app

client = TestClient(app)


def test_hindi_general_vs_personal():
    general = build_query_plan("Vitamin D kya hota hai?")
    personal = build_query_plan("mera Vitamin D kitna hai?")
    script = build_query_plan("मेरी Vitamin D रिपोर्ट क्या कहती है?")
    causes = build_query_plan("Vitamin D क्यों कम हो सकता है?")
    assert general.knowledge_scope == KnowledgeScope.general
    assert personal.needs_personal_data and personal.topic == "vitamin_d"
    assert script.needs_personal_data
    assert causes.knowledge_scope == KnowledgeScope.general


def test_multilingual_personal_vitamin_d():
    samples = [
        "मेरा लेटेस्ट Vitamin D कितना है?",
        "माझ्या रिपोर्टमध्ये Vitamin D किती आहे?",
        "ਮੇਰੀ ਰਿਪੋਰਟ ਵਿੱਚ Vitamin D ਕਿੰਨਾ ਹੈ?",
        "મારા રિપોર્ટમાં Vitamin D કેટલું છે?",
        "আমার রিপোর্টে Vitamin D কত আছে?",
    ]
    for msg in samples:
        plan = build_query_plan(msg)
        assert plan.needs_personal_data, msg
        assert plan.topic == "vitamin_d", msg


def test_hindi_why_and_b12_followups():
    first = build_query_plan("मेरा Vitamin D कितना है?")
    why = build_query_plan("क्यों?", first.topic, first.topic_name, prior_personal=True)
    assert why.intent == IntentType.blood_marker_explanation
    assert why.topic == "vitamin_d"
    b12 = build_query_plan("और B12?", "vitamin_d", "Vitamin D", prior_personal=True)
    assert b12.topic == "vitamin_b12"
    meaning = build_query_plan("इसका मतलब क्या है?", "vitamin_b12", "Vitamin B12", prior_personal=True)
    assert meaning.intent == IntentType.blood_marker_explanation


def test_answers_stay_english():
    headers = {"X-Cura-User-Id": "demo-user-001"}
    first = client.post(
        "/api/v1/chat",
        headers=headers,
        json={"message": "Answer in Hindi.", "language_mode": "auto", "language": "hi"},
    ).json()
    assert first["meta"]["response_language"] == "en"
    second = client.post(
        "/api/v1/chat",
        headers=headers,
        json={"message": "मेरा Vitamin D कितना है?", "conversation_id": first["conversation_id"]},
    ).json()
    assert second["meta"]["response_language"] == "en"


def test_medical_terms_preserved():
    text = "मेरा HbA1c, LDL और Vitamin D कितना है?"
    normalized = normalize_for_intent(text)
    assert "HbA1c" in text
    assert "LDL" in normalized or "ldl" in normalized.lower()
    assert "Vitamin D" in text


def test_numeric_values_not_rewritten():
    from app.pipeline.medical_terms import assert_values_unchanged

    assert assert_values_unchanged("12.6 ng/mL and 142 mg/dL", "आपका Vitamin D 12.6 ng/mL है और LDL 142 mg/dL है")


def test_hindi_personal_db_unavailable():
    class Boom:
        def get_profile(self, *a, **k):
            raise ProviderUnavailableError()

        def query(self, *a, **k):
            raise ProviderUnavailableError()

    reg = build_registry()
    boom = Boom()
    reg.users = boom
    reg.blood = boom
    set_registry(reg)
    try:
        personal = client.post(
            "/api/v1/chat",
            headers={"X-Cura-User-Id": "5"},
            json={"message": "मेरा Vitamin D कितना है?"},
        ).json()
        general = client.post(
            "/api/v1/chat",
            headers={"X-Cura-User-Id": "5"},
            json={"message": "Vitamin D क्या है?"},
        ).json()
        assert personal["answer"] == personal_data_unavailable()
        assert personal["answer"] == PERSONAL_DATA_UNAVAILABLE
        assert "asyncpg" not in personal["answer"]
        assert "5432" not in personal["answer"]
        assert general["answer"] != personal["answer"]
        assert general["meta"]["intent"] == "general_health_question"
    finally:
        set_registry(None)


def test_prompt_is_english():
    from app.contracts.health_context import HealthContext
    from app.contracts.common import AnswerDepth
    from app.pipeline.prompt_builder import PromptBuilder

    ctx = HealthContext(
        intent=IntentType.general_health_question,
        answer_depth=AnswerDepth.simple,
        knowledge_scope=KnowledgeScope.general,
        resolved_topic="vitamin_d",
        resolved_topic_name="Vitamin D",
    )
    msgs = PromptBuilder().build(ctx, "", "Vitamin D क्या है?", "hi")
    blob = " ".join(m["content"] for m in msgs)
    assert "Write the entire answer in English" in blob
    assert "RESPONSE LANGUAGE" not in blob
    assert "HbA1c" in blob
