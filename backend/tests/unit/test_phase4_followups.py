from app.contracts.common import AnswerDepth, IntentType, KnowledgeScope
from app.contracts.health_context import HealthContext
from app.contracts.query import QueryPlan
from app.core.copy import PERSONAL_DATA_UNAVAILABLE
from app.core.errors import ProviderUnavailableError
from app.pipeline.personalized_followups import FollowUpInventory, PersonalizedFollowUpEngine
from app.pipeline.query_planner import build_query_plan
from fastapi.testclient import TestClient

from app.main import app
from app.providers.registry import build_registry, set_registry

client = TestClient(app)
engine = PersonalizedFollowUpEngine()


def _ctx(**kwargs):
    data = dict(
        intent=IntentType.latest_result,
        answer_depth=AnswerDepth.simple,
        knowledge_scope=KnowledgeScope.personal,
        resolved_topic="vitamin_d",
        resolved_topic_name="Vitamin D",
        data_source="supershyft",
    )
    data.update(kwargs)
    return HealthContext.model_validate(data)


def _plan(message="What is my Vitamin D?", **kwargs):
    plan = build_query_plan(message)
    return plan.model_copy(update=kwargs)


def _marker():
    from app.contracts.blood import BloodMarker
    from app.contracts.common import MarkerFlag

    return BloodMarker(
        id="m",
        key="vitamin_d",
        name="Vitamin D",
        value=12.6,
        unit="ng/mL",
        reference_low=30,
        reference_high=100,
        flag=MarkerFlag.low,
    )


def _cats(items):
    return {i.category for i in items}


def test_personal_vitamin_d_relevant_followups():
    inv = FollowUpInventory(topic_result_count=1, latest_marker_keys={"vitamin_d"})
    items = engine.generate(_plan(), "answer", _ctx(markers=[_marker()]), inv)
    assert items
    assert "historical_trend" not in _cats(items)
    assert any(i.category in {"explanation", "general_education"} for i in items)


def test_general_vitamin_d_not_personal():
    plan = build_query_plan("What is Vitamin D?")
    items = engine.generate(plan, "answer", _ctx(intent=IntentType.general_health_question, knowledge_scope=KnowledgeScope.general, markers=[]), FollowUpInventory())
    assert items
    assert all(not i.requires_personal_context or i.category == "next_action" for i in items)
    blob = " ".join(i.text.lower() for i in items)
    assert "previous result" not in blob
    assert "your latest" not in blob or "if you'd like" in blob


def test_no_previous_no_trend():
    inv = FollowUpInventory(topic_result_count=1, latest_marker_keys={"vitamin_d"})
    items = engine.generate(_plan(), "a", _ctx(markers=[_marker()]), inv)
    assert "historical_trend" not in _cats(items)


def test_multiple_results_allows_trend():
    inv = FollowUpInventory(topic_result_count=2, latest_marker_keys={"vitamin_d"})
    items = engine.generate(_plan(), "a", _ctx(markers=[_marker()]), inv)
    assert "historical_trend" in _cats(items)


def test_no_bio_ai_no_bio_followup():
    inv = FollowUpInventory(topic_result_count=1, latest_marker_keys={"hba1c"})
    from app.contracts.blood import BloodMarker
    from app.contracts.common import MarkerFlag

    marker = BloodMarker(id="h", key="hba1c", name="HbA1c", value=5.5, flag=MarkerFlag.normal)
    plan = build_query_plan("What is my HbA1c?")
    items = engine.generate(plan, "a", _ctx(resolved_topic="hba1c", resolved_topic_name="HbA1c", markers=[marker]), inv)
    assert "bio_ai_relationship" not in _cats(items)


def test_bio_ai_allows_relationship_for_hba1c():
    inv = FollowUpInventory(
        topic_result_count=1,
        latest_marker_keys={"hba1c"},
        bio_codes={"type_2_diabetes", "metabolic_score"},
    )
    from app.contracts.blood import BloodMarker
    from app.contracts.common import MarkerFlag

    marker = BloodMarker(id="h", key="hba1c", name="HbA1c", value=5.5, flag=MarkerFlag.normal)
    plan = build_query_plan("What is my HbA1c?")
    items = engine.generate(plan, "a", _ctx(resolved_topic="hba1c", resolved_topic_name="HbA1c", markers=[marker]), inv)
    assert "bio_ai_relationship" in _cats(items)


def test_no_nutrition_no_personal_nutrition_claim():
    inv = FollowUpInventory(topic_result_count=1, latest_marker_keys={"vitamin_d"}, has_nutrition=False)
    items = engine.generate(_plan(), "a", _ctx(markers=[_marker()]), inv)
    assert "nutrition" not in _cats(items)
    blob = " ".join(i.text.lower() for i in items)
    assert "your recorded nutrition" not in blob


def test_nutrition_available():
    inv = FollowUpInventory(topic_result_count=1, latest_marker_keys={"vitamin_d"}, has_nutrition=True)
    items = engine.generate(_plan(), "a", _ctx(markers=[_marker()]), inv)
    assert "nutrition" in _cats(items)


def test_dedup_after_explanation_discussed():
    inv = FollowUpInventory(
        topic_result_count=2,
        latest_marker_keys={"vitamin_d"},
        discussed_intents={"blood_marker_explanation"},
        discussed_text=["what is my vitamin d?", "why is it low?"],
    )
    plan = build_query_plan("Why?", "vitamin_d", prior_personal=True)
    items = engine.generate(plan, "a", _ctx(intent=IntentType.blood_marker_explanation, markers=[_marker()]), inv)
    assert "explanation" not in _cats(items)
    blob = " ".join(i.text.lower() for i in items)
    assert "what vitamin d does" not in blob


def test_topic_change_adapts():
    vit = engine.generate(_plan(), "a", _ctx(markers=[_marker()]), FollowUpInventory(topic_result_count=2, latest_marker_keys={"vitamin_d", "vitamin_b12"}))
    from app.contracts.blood import BloodMarker
    from app.contracts.common import MarkerFlag

    b12 = BloodMarker(id="b", key="vitamin_b12", name="Vitamin B12", value=154, flag=MarkerFlag.low)
    plan = build_query_plan("What about my B12?")
    other = engine.generate(
        plan,
        "a",
        _ctx(resolved_topic="vitamin_b12", resolved_topic_name="Vitamin B12", markers=[b12]),
        FollowUpInventory(topic_result_count=2, latest_marker_keys={"vitamin_d", "vitamin_b12"}),
    )
    assert any("B12" in i.text or "b12" in i.text.lower() for i in other)
    assert not any("Vitamin D has changed" in i.text for i in other)


def test_two_users_different_candidates():
    user_a = FollowUpInventory(topic_result_count=1, latest_marker_keys={"vitamin_d"}, has_nutrition=True)
    user_b = FollowUpInventory(
        topic_result_count=2,
        latest_marker_keys={"vitamin_d", "calcium", "vitamin_b12"},
        latest_marker_names={"calcium": "calcium", "vitamin_b12": "Vitamin B12"},
    )
    a = _cats(engine.generate(_plan(), "a", _ctx(markers=[_marker()]), user_a))
    b = _cats(engine.generate(_plan(), "a", _ctx(markers=[_marker()]), user_b))
    assert a != b
    assert "historical_trend" in b and "historical_trend" not in a
    assert "related_marker" in b
    assert "nutrition" in a and "nutrition" not in b


def test_zero_followups_allowed():
    items = engine.generate(_plan(), "a", _ctx(markers=[]), FollowUpInventory())
    assert items == []


def test_provider_unavailable_no_fabricated_followups():
    items = engine.generate(_plan(), PERSONAL_DATA_UNAVAILABLE, _ctx(), FollowUpInventory(), provider_unavailable=True)
    assert items == []


def test_general_followups_when_db_down():
    plan = build_query_plan("What is Vitamin D?")
    items = engine.generate(
        plan,
        "educational",
        _ctx(intent=IntentType.general_health_question, knowledge_scope=KnowledgeScope.general, markers=[]),
        FollowUpInventory(),
    )
    assert items
    assert all(i.source != "supershyft" or not i.requires_personal_context or i.category == "next_action" for i in items)
    assert "next_action" not in _cats(items)


def test_chat_api_followups_structured_and_safe():
    res = client.post(
        "/api/v1/chat",
        headers={"X-Cura-User-Id": "demo-user-001"},
        json={"message": "What is my Vitamin D?"},
    )
    body = res.json()
    assert res.status_code == 200
    fus = body["follow_ups"]
    assert isinstance(fus, list)
    if fus:
        assert "text" in fus[0] and "category" in fus[0]
        blob = str(fus).lower()
        assert "asyncpg" not in blob
        assert "password" not in blob


def test_chat_api_user2_no_trend_chip():
    res = client.post(
        "/api/v1/chat",
        headers={"X-Cura-User-Id": "demo-user-002"},
        json={"message": "What is my Vitamin D?"},
    )
    cats = {row["category"] for row in res.json()["follow_ups"]}
    assert "historical_trend" not in cats
