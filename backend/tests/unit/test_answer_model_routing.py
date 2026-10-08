from unittest.mock import MagicMock

from app.contracts.blood import BloodMarker
from app.contracts.chat import ChatMeta, ChatResponse
from app.contracts.common import AnswerModelTier, IntentType, KnowledgeScope, MarkerFlag, ReasoningDepth
from app.contracts.health_context import HealthContext
from app.contracts.query import QueryPlan
from app.core.config import settings
from app.core.errors import LLMUnavailableError
from app.llm.factory import get_llm_client
from app.llm.openai_compatible import OpenAICompatibleLLMClient
from app.llm.registry import estimate_cost_usd, fallback_tiers, model_id_for_tier, model_pricing, model_registry, uses_answer_llm
from app.pipeline.planner import plan_needs_reasoning
from app.pipeline.prompt_builder import _minimal_context_payload, _use_compact_context
from app.pipeline.quality_gate import review_answer, should_escalate_to_deep
from app.pipeline.query_planner import build_query_plan
from app.routing.jev_client import JevDecisionsClient
from app.routing import jev_client as jev_client_mod
from app.routing.jev_router import resolve_plan
from app.routing.mapper import plan_from_jev
from app.routing.schemas import (
    JevDecision,
    JevIntent,
    JevOperation,
    JevSource,
    JevTimeRange,
)


LOOKUP_PARAPHRASES = (
    "What is my creatinine?",
    "What is my latest creatinine?",
    "Show my current creatinine value.",
    "What's my creatinine result?",
)
GENERAL_EXPLAIN_PARAPHRASES = (
    "What does creatinine mean?",
    "What is creatinine?",
    "Can you explain creatinine in general?",
)
PERSONAL_EXPLAIN_PARAPHRASES = (
    "What does my creatinine mean?",
    "Please interpret my creatinine result.",
    "How should I read my creatinine?",
)
TREND_ONLY_PARAPHRASES = (
    "Compare my creatinine over time.",
    "Compare my creatinine with previous results.",
    "Show my creatinine trend.",
)
TREND_INTERPRET_PARAPHRASES = (
    "Compare my creatinine over time and explain what the change means.",
    "Why did my creatinine change compared with previous reports?",
)
HIGH_LIST_PARAPHRASES = (
    "Show all high markers.",
    "List my high results only.",
    "Which markers are high?",
)
RELATED_HIGH_PARAPHRASES = (
    "Which high markers might be related?",
    "Are any of my high results connected?",
    "Do my elevated markers form a pattern?",
)
LIVER_PARAPHRASES = (
    "How is my liver?",
    "How are my liver results looking?",
    "Give me a read on liver function.",
)
KIDNEY_COMPLEX_PARAPHRASES = (
    "Review kidney function using creatinine, eGFR, blood pressure, diabetes markers and history.",
    "Look at creatinine, eGFR, blood pressure, and diabetes markers together with my history.",
)
SCENARIO_PARAPHRASES = (
    "Review my complete health scenario.",
    "Give me a bigger-picture review of my overall health.",
    "Review my blood results, Bio-AI, questionnaire and history, identify related patterns, "
    "explain contradictions, and tell me what deserves the most attention.",
)


def _assert_tier(messages, expected: AnswerModelTier, *, reasons_any=None):
    for message in messages:
        plan = build_query_plan(message)
        assert plan.answer_model_tier == expected, (
            message,
            plan.answer_model_tier,
            plan.operations,
            plan.model_selection_reasons,
        )
        assert plan.model_tier == expected
        if reasons_any:
            blob = " ".join(plan.model_selection_reasons or [])
            assert any(token in blob for token in reasons_any), (message, plan.model_selection_reasons)


def test_registry_maps_capability_tiers_to_configured_models():
    registry = model_registry()
    assert "DETERMINISTIC" not in registry
    assert registry["FAST_REASONING"] == settings.answer_model_fast_reasoning == "google/gemini-3.8-flash"
    assert registry["STANDARD_MEDICAL"] == settings.answer_model_standard_medical == "openai/gpt-5-mini"
    assert registry["DEEP_MEDICAL_REASONING"] == settings.answer_model_deep_medical == "openai/gpt-5.6-luna"
    assert model_id_for_tier("DETERMINISTIC") == ""
    assert model_id_for_tier("FAST_REASONING") == settings.answer_model_fast_reasoning
    client = get_llm_client(model_tier="STANDARD_MEDICAL")
    assert client.model == settings.answer_model_standard_medical
    assert client.provider == "openrouter"
    assert client.api_key == settings.active_llm_api_key()
    assert not uses_answer_llm(AnswerModelTier.deterministic)
    assert uses_answer_llm(AnswerModelTier.fast_reasoning)
    assert uses_answer_llm(AnswerModelTier.standard_medical)


def test_single_value_lookups_are_deterministic():
    _assert_tier(LOOKUP_PARAPHRASES, AnswerModelTier.deterministic, reasons_any=["deterministic"])
    for message in LOOKUP_PARAPHRASES:
        plan = build_query_plan(message)
        assert plan.complexity.value == "LOW"
        assert plan.reasoning_depth == ReasoningDepth.none
        assert not plan_needs_reasoning(plan)
        assert not uses_answer_llm(plan.answer_model_tier)


def test_general_creatinine_explanation_is_standard_medical():
    _assert_tier(GENERAL_EXPLAIN_PARAPHRASES, AnswerModelTier.standard_medical)
    for message in GENERAL_EXPLAIN_PARAPHRASES:
        plan = build_query_plan(message)
        assert plan.knowledge_scope == KnowledgeScope.general
        assert uses_answer_llm(plan.answer_model_tier)


def test_personal_creatinine_interpretation_retrieves_then_uses_standard_medical():
    for message in PERSONAL_EXPLAIN_PARAPHRASES:
        plan = build_query_plan(message)
        assert plan.needs_personal_data or plan.needs_blood
        assert plan.answer_model_tier == AnswerModelTier.standard_medical, (
            message,
            plan.answer_model_tier,
            plan.model_selection_reasons,
        )
        assert plan.reasoning_depth == ReasoningDepth.standard


def test_trend_is_deterministic_unless_interpretation_is_requested():
    for message in TREND_ONLY_PARAPHRASES:
        plan = build_query_plan(message)
        assert plan.answer_model_tier == AnswerModelTier.deterministic, (
            message,
            plan.answer_model_tier,
            plan.operations,
            plan.intent,
            plan.model_selection_reasons,
        )
    for message in TREND_INTERPRET_PARAPHRASES:
        plan = build_query_plan(message)
        assert plan.answer_model_tier == AnswerModelTier.standard_medical, (
            message,
            plan.answer_model_tier,
            plan.model_selection_reasons,
        )


def test_high_marker_lists_are_deterministic():
    _assert_tier(HIGH_LIST_PARAPHRASES, AnswerModelTier.deterministic)


def test_related_high_markers_use_medical_reasoning():
    for message in RELATED_HIGH_PARAPHRASES:
        plan = build_query_plan(message)
        assert plan.answer_model_tier in {
            AnswerModelTier.standard_medical,
            AnswerModelTier.deep_medical_reasoning,
        }, (message, plan.answer_model_tier, plan.model_selection_reasons)
        assert uses_answer_llm(plan.answer_model_tier)


def test_liver_domain_questions_default_to_standard_medical():
    _assert_tier(LIVER_PARAPHRASES, AnswerModelTier.standard_medical)


def test_multi_domain_kidney_review_is_deep_when_complexity_is_sufficient():
    for message in KIDNEY_COMPLEX_PARAPHRASES:
        plan = build_query_plan(message)
        assert plan.answer_model_tier == AnswerModelTier.deep_medical_reasoning, (
            message,
            plan.requested_metrics,
            plan.domains,
            plan.model_selection_reasons,
        )
        assert plan.complexity.value == "HIGH"
        assert plan.reasoning_depth == ReasoningDepth.deep


def test_complete_health_scenario_is_deep_medical_reasoning():
    _assert_tier(SCENARIO_PARAPHRASES, AnswerModelTier.deep_medical_reasoning, reasons_any=["deep", "scenario", "synthesis"])


def test_pdf_simple_lookup_is_deterministic():
    plan = build_query_plan("What is my LDL in this uploaded report?", document_ids=["doc-1"])
    assert plan.needs_user_uploaded
    assert plan.answer_model_tier == AnswerModelTier.deterministic


def test_complex_pdf_and_longitudinal_use_deep_medical():
    analyze = build_query_plan("Analyze my uploaded diagnostic report.", document_ids=["doc-1"])
    assert analyze.answer_model_tier == AnswerModelTier.deep_medical_reasoning
    compare = build_query_plan("Compare my last three blood reports.")
    assert compare.answer_model_tier in {
        AnswerModelTier.standard_medical,
        AnswerModelTier.deep_medical_reasoning,
    }
    mixed = build_query_plan(
        "My LDL increased from 120 to 168, triglycerides increased, HDL decreased, "
        "and my Bio-AI dyslipidemia score also increased. Explain the overall picture."
    )
    assert mixed.answer_model_tier == AnswerModelTier.deep_medical_reasoning


def test_jev_cannot_under_route_a_complex_question_to_deterministic():
    decision = JevDecision(
        intent=JevIntent.lab_result_lookup,
        source=JevSource.lab_results,
        operation=JevOperation.retrieve_and_explain,
        requires_personal_data=True,
        requires_historical_data=True,
        time_range=JevTimeRange.historical,
        requested_metrics=["ldl", "triglycerides", "hdl"],
        complexity="LOW",
        answer_model_tier=AnswerModelTier.deterministic,
        confidence=0.93,
    )
    plan = plan_from_jev(
        decision,
        "My LDL increased from 120 to 168 over the last year. Why did this happen "
        "and how does it relate to my triglycerides and Bio-AI risk?",
    )
    assert plan.answer_model_tier == AnswerModelTier.deep_medical_reasoning


def test_fast_reasoning_is_promoted_off_patient_facing_answers():
    decision = JevDecision(
        intent=JevIntent.lab_result_interpretation,
        source=JevSource.lab_results,
        operation=JevOperation.interpret,
        requires_personal_data=True,
        reasoning_required=True,
        answer_model_tier=AnswerModelTier.fast_reasoning,
        complexity="MEDIUM",
        confidence=0.9,
    )
    plan = plan_from_jev(decision, "What does my Vitamin D result mean?")
    assert plan.answer_model_tier == AnswerModelTier.standard_medical
    assert "fast_reasoning_not_used_for_medical_answers" in (plan.model_selection_reasons or [])


def test_jev_unavailable_still_selects_deterministic_tier(monkeypatch):
    monkeypatch.setattr(settings, "jev_enabled", True)
    monkeypatch.setattr(
        "app.routing.jev_client.JevDecisionsClient.decide",
        lambda self, state: (_ for _ in ()).throw(LLMUnavailableError("down")),
    )
    plan, trace = resolve_plan("What is my LDL?")
    assert trace.fallback is True
    assert plan.answer_model_tier == AnswerModelTier.deterministic


def test_fast_model_failure_falls_back_to_standard(monkeypatch):
    monkeypatch.setattr(settings, "enable_llm", True)
    calls = []

    def complete(self, messages, json_mode=False):
        calls.append(self.model)
        if self.model == settings.answer_model_fast_reasoning:
            raise LLMUnavailableError("fast down")
        return (
            '{"answer":"LDL stands for low-density lipoprotein.",'
            '"claims":[],"recommendation_candidates":[],"follow_up_questions":[],'
            '"safety_flags":[],"escalation":null}'
        )

    monkeypatch.setattr(OpenAICompatibleLLMClient, "complete", complete)
    from fastapi.testclient import TestClient
    from app.main import app

    body = TestClient(app).post(
        "/api/v1/chat",
        headers={"X-Cura-User-Id": "demo-user-001"},
        json={"message": "What does LDL stand for?"},
    ).json()
    assert calls == [settings.answer_model_fast_reasoning, settings.answer_model_standard_medical]
    assert body["meta"]["model_fallback_used"] is True
    assert body["meta"]["answer_model"] == settings.answer_model_standard_medical
    assert "low-density lipoprotein" in body["answer"].lower()


def test_fallback_policy_never_silently_downgrades_complex_reasoning():
    fast, standard, deep = (AnswerModelTier.fast_reasoning, AnswerModelTier.standard_medical, AnswerModelTier.deep_medical_reasoning)
    assert fallback_tiers(fast, 1) == [fast, standard]
    assert fallback_tiers(standard, 3) == [standard, fast]  # straightforward enough for FAST
    assert fallback_tiers(standard, 5) == [standard, deep]  # not straightforward: go up, not down
    assert fallback_tiers(deep, 7) == [deep, standard]  # still answerable by STANDARD
    assert fallback_tiers(deep, 12) == [deep]  # too complex: honest unavailable message instead
    assert fallback_tiers(AnswerModelTier.deterministic) == []


def test_fallback_never_retries_the_same_model(monkeypatch):
    monkeypatch.setattr(settings, "answer_model_deep_medical", settings.answer_model_standard_medical)
    assert fallback_tiers(AnswerModelTier.deep_medical_reasoning, 6) == [AnswerModelTier.deep_medical_reasoning]

    assert not hasattr(settings, "anthropic_api_key")


def test_jev_typed_payload_uses_provider_independent_tiers(monkeypatch):
    payload = {
        "answers": {
            "request_type": {"type": "choice", "choice": "lab_result_lookup", "confidence": 0.91},
            "data_source": {"type": "choice", "choice": "lab_results", "confidence": 0.94},
            "operation": {"type": "choice", "choice": "lookup", "confidence": 0.93},
            "time_scope": {"type": "choice", "choice": "latest", "confidence": 0.98},
            "complexity": {"type": "choice", "choice": "LOW", "confidence": 0.9},
            "model_tier": {"type": "choice", "choice": "DETERMINISTIC", "confidence": 0.9},
            "reasoning_depth": {"type": "choice", "choice": "NONE", "confidence": 0.9},
            "requires_personal_data": {"type": "noul", "noul": 0.99},
            "requires_historical_data": {"type": "noul", "noul": 0.02},
            "requires_document": {"type": "noul", "noul": 0.01},
            "requires_clarification": {"type": "noul", "noul": 0.01},
            "reasoning_required": {"type": "noul", "noul": 0.02},
            "pdf_analysis_required": {"type": "noul", "noul": 0.01},
        },
        "model": "typesafe/jev-1.13",
        "provider": "TypeSafe",
        "usage": {"input_tokens": 42, "output_tokens": 8},
    }
    response = MagicMock(status_code=200)
    response.json.return_value = payload
    transport = MagicMock()
    transport.__enter__.return_value = transport
    transport.post.return_value = response
    monkeypatch.setattr("app.routing.jev_client.get_http_client", lambda: transport)
    from app.routing.schemas import JevRoutingState

    decision, _parsed = JevDecisionsClient(api_key="test").decide(
        JevRoutingState(current_message="What is my HbA1c?")
    )
    assert decision.answer_model_tier == AnswerModelTier.deterministic
    assert decision.complexity.value == "LOW"
    assert decision.reasoning_depth == ReasoningDepth.none
    plan = plan_from_jev(decision, "What is my HbA1c?")
    assert plan.answer_model_tier == AnswerModelTier.deterministic


def test_jev_questions_do_not_name_providers_or_models():
    blob = " ".join(
        [
            str(jev_client_mod._MODEL_TIER),
            str(jev_client_mod._COMPLEXITY),
            str(jev_client_mod._REASONING_DEPTH),
        ]
    ).lower()
    for token in ("gpt", "gemini", "claude", "openai", "anthropic", "google/", "luna"):
        assert token not in blob


def test_answer_models_use_openrouter_key_only():
    fast = get_llm_client(model_tier="FAST_REASONING")
    standard = get_llm_client(model_tier="STANDARD_MEDICAL")
    deep = get_llm_client(model_tier="DEEP_MEDICAL_REASONING")
    assert fast.provider == standard.provider == deep.provider == "openrouter"
    assert fast.base_url == standard.base_url == deep.base_url == settings.active_llm_base_url()
    assert fast.api_key == standard.api_key == deep.api_key == settings.active_llm_api_key()
    assert settings.active_llm_api_key() == (settings.openrouter_api_key or settings.llm_api_key).strip()
    assert not hasattr(settings, "openai_api_key")
    assert not hasattr(settings, "google_api_key")
    assert not hasattr(settings, "anthropic_api_key")


def test_pricing_is_separate_from_routing(monkeypatch):
    monkeypatch.setattr(settings, "answer_model_deep_medical", "anthropic/claude-sonnet-5")
    prices = model_pricing()
    assert prices[settings.answer_model_fast_reasoning].input_per_1m == settings.model_price_fast_reasoning_input_per_1m
    assert prices[settings.answer_model_standard_medical].output_per_1m == settings.model_price_standard_medical_output_per_1m
    assert prices[settings.answer_model_deep_medical].input_per_1m == settings.model_price_deep_medical_input_per_1m
    cost = estimate_cost_usd(settings.answer_model_fast_reasoning, 1_000_000, 1_000_000)
    assert cost == round(settings.model_price_fast_reasoning_input_per_1m + settings.model_price_fast_reasoning_output_per_1m, 8)


def test_chat_contract_keeps_existing_fields():
    meta = ChatMeta(
        intent="latest_result",
        answer_model_tier="DETERMINISTIC",
        reasoning_depth="NONE",
    )
    response = ChatResponse(conversation_id="c1", answer="ok", meta=meta)
    dumped = response.model_dump()
    assert dumped["conversation_id"] == "c1"
    assert dumped["answer"] == "ok"
    assert dumped["meta"]["intent"] == "latest_result"
    assert dumped["meta"]["llm_called"] is False
    assert dumped["meta"]["answer_model_tier"] == "DETERMINISTIC"
    assert dumped["meta"]["reasoning_depth"] == "NONE"


def test_chat_meta_records_selected_tier(monkeypatch):
    monkeypatch.setattr(settings, "jev_enabled", False)
    from fastapi.testclient import TestClient
    from app.main import app

    body = TestClient(app).post(
        "/api/v1/chat",
        headers={"X-Cura-User-Id": "demo-user-001"},
        json={"message": "What is my LDL?"},
    ).json()
    assert body["meta"]["answer_model_tier"] == "DETERMINISTIC"
    assert body["meta"]["answer_model"] in {None, ""}
    assert body["meta"]["jev_complexity"] == "LOW"
    assert body["meta"]["reasoning_depth"] == "NONE"
    assert body["meta"]["supershyft_called"] is True
    assert "138" in body["answer"]


def test_development_debug_includes_routing_observability(monkeypatch):
    monkeypatch.setattr(settings, "jev_enabled", False)
    monkeypatch.setattr(settings, "app_env", "development")
    from fastapi.testclient import TestClient
    from app.main import app

    body = TestClient(app).post(
        "/api/v1/chat",
        headers={"X-Cura-User-Id": "demo-user-001"},
        json={"message": "What is my LDL?"},
    ).json()
    debug = body["meta"]["debug"]
    assert debug["jev_plan"]["model_tier"] == "DETERMINISTIC"
    assert "complexity" in debug["jev_plan"]
    assert "reasoning_depth" in debug["jev_plan"]
    assert "reasons_for_model_selection" in debug["jev_plan"]
    assert "selected_provider" in debug["model_router"]
    assert "selected_model" in debug["model_router"]
    assert "input" in debug["tokens"]
    assert "output" in debug["tokens"]
    assert "jev_ms" in debug["latency"]
    assert "estimated_cost" in debug
    assert debug["escalated"] is False


def test_production_hides_routing_debug():
    from app.core.config import Settings

    assert Settings(app_env="production").is_development is False
    assert Settings(app_env="development").is_development is True
    assert Settings(app_env="test").is_development is True


def test_quality_gate_does_not_pay_a_second_call_for_wording():
    plan = QueryPlan(
        intent=IntentType.blood_marker_explanation,
        knowledge_scope=KnowledgeScope.personal,
        needs_blood=True,
        answer_model_tier=AnswerModelTier.standard_medical,
        requested_metrics=["creatinine"],
        display_entities=["creatinine"],
    )
    context = HealthContext(
        intent=IntentType.blood_marker_explanation,
        answer_depth="focused",
        knowledge_scope=KnowledgeScope.personal,
        markers=[
            BloodMarker(id="creatinine", key="creatinine", name="Creatinine", value=1.4, unit="mg/dL", flag=MarkerFlag.high)
        ],
    )
    generic = (
        "It depends. In general many people have kidney variation and typically overall health is fine."
    )
    gate = review_answer(generic, plan, context)
    assert "generic_despite_personal" in gate.flags or "entity_unmentioned" in gate.flags
    # Wording issues are the validator's job; a second model call is reserved for answers
    # that could not reconcile the evidence or produced no usable output.
    assert not should_escalate_to_deep(gate.flags, plan, context, generic)
    assert should_escalate_to_deep(["contradictions_unaddressed"], plan, context, generic)
    long_ok = "Your creatinine is 1.4 mg/dL, which the report flags above the reference range."
    ok_gate = review_answer(long_ok, plan, context)
    assert not should_escalate_to_deep(ok_gate.flags, plan, context, long_ok)


def test_quality_gate_does_not_escalate_for_length_alone():
    plan = QueryPlan(
        intent=IntentType.blood_marker_explanation,
        knowledge_scope=KnowledgeScope.personal,
        needs_blood=True,
        answer_model_tier=AnswerModelTier.standard_medical,
        requested_metrics=["creatinine"],
        display_entities=["creatinine"],
    )
    context = HealthContext(
        intent=IntentType.blood_marker_explanation,
        answer_depth="focused",
        knowledge_scope=KnowledgeScope.personal,
        markers=[
            BloodMarker(id="creatinine", key="creatinine", name="Creatinine", value=1.4, unit="mg/dL", flag=MarkerFlag.high)
        ],
    )
    long_answer = "Your creatinine is 1.4 mg/dL. " * 40
    gate = review_answer(long_answer, plan, context)
    assert not should_escalate_to_deep(gate.flags, plan, context, long_answer)


def test_question_specific_context_is_compact():
    markers = [
        BloodMarker(id=str(i), key=f"m{i}", name=f"Marker {i}", value=float(i), unit="u", flag=MarkerFlag.normal)
        for i in range(30)
    ]
    context = HealthContext(
        intent=IntentType.latest_result,
        answer_depth="focused",
        knowledge_scope=KnowledgeScope.personal,
        requested_entity_codes=["m0"],
        display_entity_codes=["m0"],
        markers=markers,
        notes=["n"] * 20,
    )
    assert _use_compact_context(context) is True
    payload = _minimal_context_payload(context, compact=True)
    assert len(payload["markers"]) <= 12
    assert "scenario" not in payload
    assert payload["meta"]["minimal_context"] is True


def test_shared_model_is_priced_at_the_cheaper_tier(monkeypatch):
    monkeypatch.setattr(settings, "answer_model_deep_medical", settings.answer_model_standard_medical)
    price = model_pricing()[settings.answer_model_standard_medical]
    cheaper = (settings.model_price_standard_medical_input_per_1m, settings.model_price_standard_medical_output_per_1m)
    assert (price.input_per_1m, price.output_per_1m) == cheaper
