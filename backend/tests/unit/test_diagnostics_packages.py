from datetime import date

from fastapi.testclient import TestClient

from app.contracts.blood import BloodMarker
from app.contracts.common import AnswerDepth, IntentType, KnowledgeScope, MarkerFlag
from app.contracts.conversation_state import ConversationState
from app.contracts.diagnostics import CatalogItemKind, HealthGapType, TestingRelevance as Relevance
from app.contracts.health_context import HealthContext
from app.contracts.query import QueryPlan
from app.main import app
from app.pipeline.health_gaps import HealthGapDetector
from app.pipeline.lab_parameters import canonicalize_marker_name
from app.pipeline.package_matcher import PackageMatcher
from app.pipeline.package_policy import PackageRecommendationPolicy
from app.pipeline.safety import package_suggestion_allowed
from app.pipeline.test_need import TestNeedGenerator as NeedGenerator
from app.pipeline.testing_option import TestingOptionService as DiagnosticsTesting

client = TestClient(app)
IRON = {"X-Cura-User-Id": "eval-user-iron"}
DEMO = {"X-Cura-User-Id": "demo-user-001"}


def _marker(key: str, value: float, flag: MarkerFlag, measured: date) -> BloodMarker:
    return BloodMarker(
        id=f"{key}-1",
        key=key,
        name=key,
        value=value,
        flag=flag,
        measured_at=measured,
        report_id="eval-blood-2",
    )


def _iron_context() -> HealthContext:
    measured = date(2026, 8, 24)
    return HealthContext(
        intent=IntentType.blood_marker_explanation,
        answer_depth=AnswerDepth.focused,
        knowledge_scope=KnowledgeScope.personal,
        markers=[
            _marker("hemoglobin", 10.5, MarkerFlag.low, measured),
            _marker("mcv", 72.0, MarkerFlag.low, measured),
            _marker("mch", 24.0, MarkerFlag.low, measured),
            _marker("iron", 35.0, MarkerFlag.low, measured),
        ],
        domains=["iron_status", "red_cell_anaemia_health"],
        requested_entity_codes=["hemoglobin", "mcv", "mch", "iron"],
    )


def test_canonicalize_supershyft_parameter_keys():
    assert canonicalize_marker_name("iron_serum") == "iron"
    assert canonicalize_marker_name("vitamin_d_total-25_hydroxy") == "vitamin_d"
    assert canonicalize_marker_name("transferrin_saturation") == "transferrin"


def test_iron_gap_identifies_ferritin_without_diagnosis():
    gaps = HealthGapDetector().detect(
        message="My haemoglobin, MCV, MCH and serum iron are low. What else would help interpret this?",
        context=_iron_context(),
        plan=QueryPlan(
            intent=IntentType.blood_marker_explanation,
            domains=["iron_status"],
            requested_metrics=["hemoglobin", "mcv", "mch", "iron"],
        ),
    )
    ferritin = next(gap for gap in gaps if "ferritin" in gap.missing_entities)
    assert ferritin.gap_type == HealthGapType.relevant_test_missing
    assert ferritin.domain == "iron_status"
    assert "diagnos" not in ferritin.reason.lower()
    need = NeedGenerator().generate(gaps)
    assert "ferritin" in need.recommended_test_entities
    assert need.testing_relevance == Relevance.useful


def test_package_matcher_prefers_smallest_covering_item():
    matcher = PackageMatcher()
    ranked = matcher.match(["ferritin", "iron", "tibc"])
    names = [item.item.display_name for item in ranked]
    assert "Fatigue" not in names
    assert ranked[0].item.display_name == "Iron Studies with Ferritin"
    assert ranked[0].item.kind == CatalogItemKind.test_group
    assert ranked[0].coverage.matched == 3
    wider = next(item for item in ranked if item.item.display_name == "Peak Performance Women")
    assert wider.coverage.matched == 3
    assert len(wider.item.included_tests) > len(ranked[0].item.included_tests)


def test_iron_studies_without_ferritin_is_not_the_best_match():
    best = PackageMatcher().best(["ferritin", "iron", "tibc"])
    assert best is not None
    assert best.item.display_name != "Iron Studies"
    assert "ferritin" in best.item.included_tests


def test_inactive_fatigue_package_never_matched():
    ranked = PackageMatcher().match(["ferritin"])
    assert all(item.item.display_name != "Fatigue" for item in ranked)
    assert all((item.item.status or "active").lower() == "active" for item in ranked)


def test_no_catalog_match_when_tests_are_absent():
    assert PackageMatcher().match(["anti_tpo"]) == []


def test_recent_adequate_testing_suppresses_package():
    context = HealthContext(
        intent=IntentType.latest_result,
        answer_depth=AnswerDepth.simple,
        knowledge_scope=KnowledgeScope.personal,
        markers=[
            _marker("ldl", 138, MarkerFlag.high, date(2026, 8, 18)),
            _marker("hdl", 41, MarkerFlag.normal, date(2026, 8, 18)),
            _marker("triglycerides", 155, MarkerFlag.high, date(2026, 8, 18)),
            _marker("cholesterol", 200, MarkerFlag.normal, date(2026, 8, 18)),
        ],
        domains=["lipid_health"],
        requested_entity_codes=["ldl", "hdl", "triglycerides", "cholesterol"],
    )
    option, trace, need = DiagnosticsTesting().evaluate(
        message="Do I need another package for my cholesterol?",
        context=context,
        plan=QueryPlan(intent=IntentType.latest_result, domains=["lipid_health"], requested_metrics=["ldl"]),
    )
    assert need.testing_relevance in {Relevance.none, Relevance.optional}
    assert option is not None
    assert option.relevance.value == "NOT_RECOMMENDED_NOW"
    assert "don't need to repeat" in option.headline.lower() or "probably don't need" in option.headline.lower()
    assert option.primary_action.type.value == "COMPARE_WITH_EXISTING_RESULTS"
    assert "catalog match" not in (option.invitation or "").lower()
    assert trace.policy_reason == "recent_adequate_testing"


def test_stale_vitamin_d_follow_up_may_surface_vitamin_profile():
    context = HealthContext(
        intent=IntentType.trend,
        answer_depth=AnswerDepth.focused,
        knowledge_scope=KnowledgeScope.personal,
        markers=[_marker("vitamin_d", 12.6, MarkerFlag.low, date(2026, 1, 15))],
        domains=["vitamin_d_bone_mineral_health"],
        requested_entity_codes=["vitamin_d"],
    )
    option, trace, need = DiagnosticsTesting().evaluate(
        message="Has my Vitamin D improved?",
        context=context,
        plan=QueryPlan(intent=IntentType.trend, domains=["vitamin_d_bone_mineral_health"], requested_metrics=["vitamin_d"]),
    )
    assert "vitamin_d" in need.recommended_test_entities
    assert option is not None
    assert option.display_name == "Vitamin Profile"
    assert option.relevance.value == "MODERATE_RELEVANCE"
    assert "Vitamin D" in " ".join(option.relevant_tests) or "Vitamin D" in option.reason
    assert "due for testing" not in (option.reason or "").lower()
    assert option.primary_action.type.value == "OPEN_PACKAGE"
    assert option.primary_action.label.startswith("View ")
    assert "test group" not in option.primary_action.label.lower()
    assert trace.policy_allowed is True


def test_acute_fever_suppresses_packages():
    assert package_suggestion_allowed("I feel feverish today, should I get tested?") is False
    option, trace, _need = DiagnosticsTesting().evaluate(
        message="I feel feverish today, should I get tested?",
        context=_iron_context(),
        package_suggestion_allowed=False,
    )
    assert option is None
    assert trace.package_suggestion_allowed is False
    assert trace.policy_reason == "acute_or_emergency_symptoms"


def test_explicit_ferritin_package_lookup_uses_catalog_name():
    option, _trace, _need = DiagnosticsTesting().evaluate(
        message="Which SuperShyft package includes ferritin?",
        context=HealthContext(
            intent=IntentType.general_health_question,
            answer_depth=AnswerDepth.simple,
            knowledge_scope=KnowledgeScope.general,
        ),
    )
    assert option is not None
    assert option.display_name == "Iron Studies with Ferritin"
    assert "ferritin" in [item.lower() for item in option.included_matched_tests]
    assert option.relevance.value == "OPTIONAL"
    assert "catalog match" not in option.reason.lower()
    assert option.primary_action.label == "View Iron Studies with Ferritin"


def test_metabolic_hba1c_glucose_prefers_diabetes_profile_pro():
    best = PackageMatcher().best(["hba1c", "fasting_blood_glucose"])
    assert best is not None
    assert best.item.display_name == "Diabetes Profile Pro"
    basic = PackageMatcher().best(["hba1c"])
    assert basic is not None
    assert basic.item.display_name == "Diabetes Profile"


def test_policy_rejects_duplicate_surfacing():
    matcher = PackageMatcher()
    candidate = matcher.best(["ferritin", "iron", "tibc"])
    decision = PackageRecommendationPolicy().decide(
        test_need=NeedGenerator().generate(
            HealthGapDetector().detect(message="what else would help", context=_iron_context())
        ),
        candidate=candidate,
        package_suggestion_allowed=True,
        explicit_catalog_lookup=False,
        recent_adequate=False,
        conversation_state=ConversationState(last_surfaced_catalog_id=candidate.item.catalog_id if candidate else "31"),
    )
    assert decision.allowed is False
    assert decision.reason == "already_surfaced_in_topic"


def test_chat_iron_pattern_may_surface_iron_studies_with_ferritin():
    body = client.post(
        "/api/v1/chat",
        headers=IRON,
        json={"message": "My haemoglobin, MCV, MCH and serum iron are low. What else would help interpret this?"},
    ).json()
    answer = body["answer"].lower()
    option = body.get("testing_option") or (body.get("presentation") or {}).get("testing_option")
    assert "anemia as a diagnosis" not in answer
    assert "you have iron deficiency" not in answer
    assert option is not None
    assert option["display_name"] == "Iron Studies with Ferritin"
    assert option["relevance"] == "HIGH_RELEVANCE"
    assert option["package"]["name"] == "Iron Studies with Ferritin"
    assert "ferritin" in (option.get("reason") or "").lower() or "ferritin" in answer
    assert option["primary_action"]["type"] == "OPEN_PACKAGE"
    assert option["primary_action"]["label"] == "View Iron Studies with Ferritin"
    assert "view test group" not in answer
    assert "catalog match" not in answer
    assert "fatigue" not in option["display_name"].lower()
    assert "need to purchase" not in answer


def test_chat_recent_cholesterol_does_not_push_a_package():
    body = client.post(
        "/api/v1/chat",
        headers=DEMO,
        json={"message": "Do I need another package for my cholesterol?"},
    ).json()
    option = body.get("testing_option") or (body.get("presentation") or {}).get("testing_option")
    assert option is not None
    assert option["relevance"] == "NOT_RECOMMENDED_NOW"
    assert "peak performance" not in body["answer"].lower()
    assert "catalog match" not in body["answer"].lower()
    assert "view test group" not in body["answer"].lower()
    assert option["primary_action"]["type"] == "COMPARE_WITH_EXISTING_RESULTS"


def test_chat_stale_vitamin_d_mentions_catalog_option():
    body = client.post(
        "/api/v1/chat",
        headers=DEMO,
        json={"message": "Has my Vitamin D improved?"},
    ).json()
    option = body.get("testing_option") or (body.get("presentation") or {}).get("testing_option")
    assert "vitamin d" in body["answer"].lower() or "12.6" in body["answer"]
    assert option is not None
    assert option["display_name"] in {"Vitamin Profile", "Supershyft Core"}
    assert option["relevance"] in {"MODERATE_RELEVANCE", "HIGH_RELEVANCE"}
    assert "due for testing" not in body["answer"].lower()
    assert "catalog match" not in body["answer"].lower()
    assert option["primary_action"]["type"] == "OPEN_PACKAGE"


def test_chat_fever_has_no_package_recommendation():
    body = client.post(
        "/api/v1/chat",
        headers=DEMO,
        json={"message": "I feel feverish today, should I get tested?"},
    ).json()
    option = body.get("testing_option") or (body.get("presentation") or {}).get("testing_option")
    assert option is None
    low = body["answer"].lower()
    assert "iron studies with ferritin" not in low
    assert "peak performance" not in low
    assert "vitamin profile" not in low


def test_chat_explicit_package_lookup_is_deterministic():
    body = client.post(
        "/api/v1/chat",
        headers=DEMO,
        json={"message": "Which SuperShyft package includes ferritin?"},
    ).json()
    option = body.get("testing_option") or (body.get("presentation") or {}).get("testing_option")
    assert option is not None
    assert option["display_name"] == "Iron Studies with Ferritin"
    assert "ferritin" in body["answer"].lower() or "ferritin" in (option.get("reason") or "").lower()
    assert option["primary_action"]["label"] == "View Iron Studies with Ferritin"
    assert "view test group" not in body["answer"].lower()
    assert "catalog match" not in (option.get("reason") or "").lower()


def test_iron_recommendation_explains_fit_and_detects_recent_duplicates():
    option, _trace, _need = DiagnosticsTesting().evaluate(
        message="My haemoglobin, MCV, MCH and serum iron are low. What else would help interpret this?",
        context=_iron_context(),
        plan=QueryPlan(
            intent=IntentType.blood_marker_explanation,
            domains=["iron_status"],
            requested_metrics=["hemoglobin", "mcv", "mch", "iron"],
        ),
    )
    assert option is not None
    assert option.relevance.value == "HIGH_RELEVANCE"
    assert option.headline == "A test that may help clarify this"
    assert "ferritin" in option.reason.lower()
    assert option.helps_answer
    assert 2 <= len(option.relevant_tests) <= 4
    assert any("iron" in item.lower() for item in option.already_recent)
    assert any("ferritin" in item.lower() for item in option.comparison.adds_information)
    assert option.package.name == "Iron Studies with Ferritin"
    assert option.package.id == option.primary_action.package_id
    assert option.price == 699


def test_answer_does_not_embed_plain_text_cta():
    body = client.post(
        "/api/v1/chat",
        headers=IRON,
        json={"message": "My haemoglobin, MCV, MCH and serum iron are low. What else would help interpret this?"},
    ).json()
    answer = body["answer"].lower()
    assert "[view" not in answer
    assert "view test group" not in answer
    assert "catalog match" not in answer
    option = body["testing_option"]
    assert option["primary_action"]["type"] == "OPEN_PACKAGE"
    assert option["type"] == "package_recommendation"


def test_no_package_when_not_clinically_relevant():
    option, _trace, need = DiagnosticsTesting().evaluate(
        message="What is blood pressure?",
        context=HealthContext(
            intent=IntentType.general_health_question,
            answer_depth=AnswerDepth.simple,
            knowledge_scope=KnowledgeScope.general,
        ),
    )
    assert need.testing_relevance == Relevance.none
    assert option is None


def test_recommendation_metadata_comes_from_catalog():
    catalog = PackageMatcher().best(["ferritin", "iron", "tibc"])
    option, _trace, _need = DiagnosticsTesting().evaluate(
        message="My haemoglobin, MCV, MCH and serum iron are low. What else would help interpret this?",
        context=_iron_context(),
        plan=QueryPlan(
            intent=IntentType.blood_marker_explanation,
            domains=["iron_status"],
            requested_metrics=["hemoglobin", "mcv", "mch", "iron"],
        ),
    )
    assert catalog is not None
    assert option is not None
    assert option.package.name == catalog.item.display_name
    assert option.package.id == catalog.item.catalog_id
    assert option.price == catalog.item.price
    assert option.primary_action.package_id == catalog.item.catalog_id
    assert "iron profile" not in option.package.name.lower()
    assert option.primary_action.label == f"View {catalog.item.display_name}"


def test_composer_does_not_embed_package_cta():
    from app.pipeline.composer import ResponseComposer

    option, _, _ = DiagnosticsTesting().evaluate(
        message="My haemoglobin, MCV, MCH and serum iron are low. What else would help interpret this?",
        context=_iron_context(),
        plan=QueryPlan(
            intent=IntentType.blood_marker_explanation,
            domains=["iron_status"],
            requested_metrics=["hemoglobin", "mcv", "mch", "iron"],
        ),
    )
    text, _, presentation = ResponseComposer().compose(
        "Ferritin would help interpret the iron pattern.",
        plan=QueryPlan(
            intent=IntentType.blood_marker_explanation,
            raw_message="My haemoglobin, MCV, MCH and serum iron are low. What else would help interpret this?",
        ),
        context=_iron_context(),
        testing_option=option,
    )
    assert "view iron" not in text.lower()
    assert "view test group" not in text.lower()
    assert "[view" not in text.lower()
    assert presentation.testing_option is option


def test_prompt_forbids_hallucinated_package_metadata():
    from app.pipeline.prompt_builder import SAFETY_INSTRUCTIONS

    lower = SAFETY_INSTRUCTIONS.lower()
    assert "never invent packages" in lower
    assert "booking actions" in lower

