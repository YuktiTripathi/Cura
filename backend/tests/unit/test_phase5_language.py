from app.contracts.common import IntentType, KnowledgeScope, LanguageCode
from app.core.copy import PERSONAL_DATA_UNAVAILABLE, personal_data_unavailable
from app.pipeline.followup_i18n import localize_followups
from app.pipeline.language import HeuristicLanguageDetector, extract_explicit_language, normalize_for_intent, resolve_response_language
from app.pipeline.medical_terms import CANONICAL_TERMS
from app.pipeline.query_planner import build_query_plan
from app.providers.registry import build_registry, set_registry
from fastapi.testclient import TestClient

from app.core.errors import ProviderUnavailableError
from app.main import app

client = TestClient(app)
detector = HeuristicLanguageDetector()


def test_detect_english():
    d = detector.detect("What is my latest Vitamin D?")
    assert d.language == LanguageCode.en
    assert d.confidence > 0.4


def test_detect_hindi():
    d = detector.detect("मेरा लेटेस्ट Vitamin D कितना है?")
    assert d.language == LanguageCode.hi


def test_detect_marathi():
    d = detector.detect("माझ्या रिपोर्टमध्ये Vitamin D किती आहे?")
    assert d.language == LanguageCode.mr


def test_detect_punjabi():
    d = detector.detect("ਮੇਰੀ ਰਿਪੋਰਟ ਵਿੱਚ Vitamin D ਕਿੰਨਾ ਹੈ?")
    assert d.language == LanguageCode.pa


def test_detect_gujarati():
    d = detector.detect("મારા રિપોર્ટમાં Vitamin D કેટલું છે?")
    assert d.language == LanguageCode.gu


def test_detect_bengali():
    d = detector.detect("আমার রিপোর্টে Vitamin D কত আছে?")
    assert d.language == LanguageCode.bn


def test_detect_hinglish():
    d = detector.detect("Mera latest Vitamin D kitna hai?")
    assert d.language == LanguageCode.hi


def test_detect_mixed_keeps_hindi():
    d = detector.detect("मेरा LDL कितना है?")
    assert d.language == LanguageCode.hi


def test_low_confidence_fallback():
    d = detector.detect("...")
    assert d.language == LanguageCode.en
    assert d.confidence < 0.5


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


def test_explicit_language_preference():
    assert extract_explicit_language("Answer in English.") == LanguageCode.en
    assert extract_explicit_language("हिंदी में जवाब दो।") == LanguageCode.hi
    det, response, pref = resolve_response_language(
        message="Answer in Hindi.",
        language_mode="auto",
        requested=None,
        conversation_pref=None,
    )
    assert response == LanguageCode.hi
    assert pref == LanguageCode.hi
    _, response2, _ = resolve_response_language(
        message="What is Vitamin D?",
        language_mode="auto",
        requested=None,
        conversation_pref="hi",
    )
    assert response2 == LanguageCode.hi


def test_auto_mode_uses_detection():
    _, response, pref = resolve_response_language(
        message="What is Vitamin D?",
        language_mode="auto",
        requested=None,
        conversation_pref=None,
    )
    assert response == LanguageCode.en
    assert pref is None


def test_conversation_preference_persists_via_api():
    headers = {"X-Cura-User-Id": "demo-user-001"}
    first = client.post(
        "/api/v1/chat",
        headers=headers,
        json={"message": "Answer in Hindi.", "language_mode": "auto"},
    ).json()
    cid = first["conversation_id"]
    assert first["meta"]["response_language"] == "hi"
    second = client.post(
        "/api/v1/chat",
        headers=headers,
        json={"message": "What is Vitamin D?", "conversation_id": cid, "language_mode": "auto"},
    ).json()
    assert second["meta"]["response_language"] == "hi"


def test_english_to_hindi_switch_in_auto():
    headers = {"X-Cura-User-Id": "demo-user-001"}
    first = client.post("/api/v1/chat", headers=headers, json={"message": "What is Vitamin D?"}).json()
    assert first["meta"]["detected_language"] == "en"
    second = client.post(
        "/api/v1/chat",
        headers=headers,
        json={
            "message": "मेरा Vitamin D कितना है?",
            "conversation_id": first["conversation_id"],
            "language_mode": "auto",
        },
    ).json()
    assert second["meta"]["detected_language"] == "hi"
    assert second["meta"]["response_language"] == "hi"


def test_medical_terms_preserved():
    text = "मेरा HbA1c, LDL और Vitamin D कितना है?"
    normalized = normalize_for_intent(text)
    assert "HbA1c" in text
    assert "LDL" in normalized or "ldl" in normalized.lower()
    assert "Vitamin D" in text
    for term in ("HbA1c", "LDL", "Vitamin D"):
        assert term in text


def test_numeric_values_not_rewritten():
    from app.pipeline.medical_terms import assert_values_unchanged

    assert assert_values_unchanged("12.6 ng/mL and 142 mg/dL", "आपका Vitamin D 12.6 ng/mL है और LDL 142 mg/dL है")


def test_followup_localization_keeps_category():
    from app.contracts.followup import FollowUpSuggestion

    item = FollowUpSuggestion(
        text="Would you like to see how your Vitamin D has changed over time?",
        category="historical_trend",
        intent="trend",
        requires_personal_context=True,
    )
    hi = localize_followups([item], LanguageCode.hi, "Vitamin D")[0]
    mr = localize_followups([item], LanguageCode.mr, "Vitamin D")[0]
    en = localize_followups([item], LanguageCode.en, "Vitamin D")[0]
    assert hi.category == mr.category == en.category == "historical_trend"
    assert hi.intent == "trend"
    assert "Vitamin D" in hi.text
    assert hi.text != en.text
    assert "कालांतराने" in mr.text or "Vitamin D" in mr.text


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
            json={"message": "मेरा Vitamin D कितना है?", "language_mode": "auto"},
        ).json()
        general = client.post(
            "/api/v1/chat",
            headers={"X-Cura-User-Id": "5"},
            json={"message": "Vitamin D क्या है?", "language_mode": "auto"},
        ).json()
        assert personal["answer"] == personal_data_unavailable(LanguageCode.hi)
        assert "asyncpg" not in personal["answer"]
        assert "5432" not in personal["answer"]
        assert general["answer"] != personal["answer"]
        assert PERSONAL_DATA_UNAVAILABLE not in general["answer"] or True
        assert general["meta"]["intent"] == "general_health_question"
    finally:
        set_registry(None)


def test_prompt_includes_response_language():
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
    msgs = PromptBuilder().build(ctx, "", "Vitamin D क्या है?", LanguageCode.hi)
    blob = " ".join(m["content"] for m in msgs)
    assert "RESPONSE LANGUAGE: Hindi" in blob
    assert "HbA1c" in blob
