"""Behavioral regression tests for CURA answers (behaviors, not exact prose).

Scenario user ``eval-user-metabolic`` (mock data): HbA1c 6.1 % (high, report range
4.4-5.7, was 6.2 in June), triglycerides 220 (high, was 240), HDL 38 (low), BMI 29.4
(high), fasting glucose 96 (normal), LDL 96 / total cholesterol 176 / Vitamin D 34 / BUN 14
(normal); Bio-AI type 2 diabetes and cardiac risk high, obesity elevated; questionnaire:
rarely active, sits > 8 h, mostly refined grains, never drinks or smokes.
"""

import json
import threading
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from app.auth.models import AuthenticatedPrincipal
from app.contracts.presentation import ResponseMode, StructuredResponse
from app.core.config import settings
from app.main import app
from app.pipeline.answer_evidence import build_answer_evidence
from app.pipeline.context_builder import ContextBuilder
from app.pipeline.evidence_planner import reconcile_query_plan
from app.pipeline.presentation import flatten_structured_response
from app.pipeline.prompt_builder import PromptBuilder
from app.pipeline.query_planner import build_query_plan
from app.pipeline.semantic_plan import build_semantic_plan
from app.pipeline.urgency_guard import strip_unsupported_urgency
from app.providers.registry import build_registry

client = TestClient(app)
MET = {"X-Cura-User-Id": "eval-user-metabolic"}
USER = AuthenticatedPrincipal(subject_id="eval-user-metabolic")


def _chat(message: str, headers=MET, **extra) -> dict:
    return client.post("/api/v1/chat", headers=headers, json={"message": message, **extra}).json()


def _evidence(message: str, conversation_markers: list[str] | None = None, turn: str | None = None):
    semantic = build_semantic_plan(message)
    plan, _ = reconcile_query_plan(build_query_plan(message), semantic)
    if conversation_markers:
        plan = plan.model_copy(update={
            "requested_metrics": list(dict.fromkeys([*(plan.requested_metrics or []), *conversation_markers])),
            "display_entities": list(plan.display_entities or plan.requested_metrics or []),
        })
    ctx = ContextBuilder(build_registry()).build(USER, plan)
    ctx.semantic_plan = semantic.model_dump(mode="json") | {
        "markers": semantic.markers, "bio_ai": semantic.bio_ai, "concepts": semantic.concepts,
        "domains": semantic.domains, "conversation_markers": conversation_markers or [],
    }
    ctx.conversation_turn = turn
    evidence = build_answer_evidence(ctx, message)
    prompt = PromptBuilder().build(ctx, "", message)
    return ctx, evidence, prompt


def _codes(facts) -> set[str]:
    return {f.get("code") for f in facts}


# ------------------------------------------------------------ reasoning strategies


def test_personalized_single_marker_answer_uses_report_range_and_explains():
    _, evidence, prompt = _evidence("What does my HbA1c mean?")
    fact = next(f for f in evidence.primary_facts if f["code"] == "hba1c")
    assert fact["value"] == 6.1 and fact["unit"] == "%"
    # Patient-specific report range, exactly as stored.
    assert fact["reference_low"] == 4.4 and fact["reference_high"] == 5.7
    payload = evidence.payload()
    assert "FACT" in payload["how_to_answer"] and "CONNECTION" in payload["how_to_answer"]
    system = prompt[0]["content"]
    assert "reference range printed on the member's own report" in system
    assert "Explain, do not just retrieve" in system


def test_multi_marker_reasoning_does_not_concatenate_templates():
    _, evidence, _ = _evidence("What do my HbA1c and triglycerides mean?")
    assert {"hba1c", "triglycerides"} <= _codes(evidence.primary_facts)
    how = evidence.payload()["how_to_answer"]
    assert "Do not write one paragraph per marker" in how
    assert "common theme" in how and "should NOT be assumed" in how


def test_blood_and_bio_ai_reasoning_connects_sources():
    _, evidence, _ = _evidence("Why is my metabolic risk high?")
    facts = [*evidence.primary_facts, *evidence.supporting_facts]
    sources = {f.get("source", "") for f in facts}
    assert any(s.startswith("Bio-AI") for s in sources)
    assert "measured blood result" in sources
    assert "several inputs" in evidence.payload()["how_to_answer"]


def test_cross_report_normal_cholesterol_but_high_cardiac_risk():
    _, evidence, _ = _evidence("My cholesterol looks okay, so why is my cardiac risk high?")
    payload = json.dumps(evidence.payload())
    assert "cardiac_health" in payload
    assert "one normal marker does not make the overall risk low" in payload


def test_priority_response_prioritizes_with_multiple_sources():
    _, evidence, _ = _evidence("What should I work on first?")
    assert evidence.response_mode == "PRIORITIZATION"
    primary = _codes(evidence.primary_facts)
    assert 1 <= len(evidence.primary_facts) <= 3
    assert primary & {"hba1c", "triglycerides", "hdl", "bmi"}
    # Prioritizes rather than dumping: in-range results are not priorities.
    assert not primary & {"vitamin_d", "bun", "creatinine", "ldl", "cholesterol"}
    areas = {f["area"] for f in evidence.questionnaire_facts}
    assert areas & {"physical activity", "sitting time", "food choices"}
    assert any(f.get("source", "").startswith("Bio-AI") for f in evidence.supporting_facts)
    how = evidence.payload()["how_to_answer"]
    assert "Prioritize by PATTERN" in how and "not a formal risk ranking" in how


def test_questionnaire_personalization_uses_reported_habits_without_inventing():
    _, evidence, _ = _evidence("Why are my triglycerides high?")
    reported = {f["area"]: f["reported"] for f in evidence.questionnaire_facts}
    assert reported, "relevant questionnaire answers should be selected"
    for value in reported.values():
        assert value in {"Rarely", "0-1 days", "Less than 30 minutes", "More than 8 hours", "Mostly refined grains",
                         "Never", "Non-vegetarian", "6-7 hours"}  # only stored answers


def test_general_health_synthesis_uses_structured_data_not_uploads():
    body = _chat("Anything in my reports I should pay attention to?")
    assert "uploaded report" not in body["answer"].lower()
    assert body["meta"]["requires_personal_data"] is True
    plan_sources = body["meta"]["debug"]["semantic_plan"]["required_sources"]
    assert {"blood", "bio_ai"} <= set(plan_sources)


def test_what_should_i_focus_on_is_not_routed_to_uploads():
    body = _chat("What should I focus on?")
    assert body["meta"]["status"] not in {"document_missing", "document_ambiguous"}
    assert "uploaded report" not in body["answer"].lower()


def test_trend_response_shows_values_dates_and_change():
    answer = _chat("Has my HbA1c improved?")["answer"]
    assert "6.2%" in answer and "6.1%" in answer
    assert "12 Jun 2026" in answer and "20 Sep 2026" in answer
    assert "0.1 percentage points" in answer
    assert "still flagged high" in answer


def test_multi_turn_follow_up_keeps_previous_marker_in_context():
    _, evidence, _ = _evidence(
        "But my fasting glucose is normal?", conversation_markers=["hba1c"], turn="FOLLOW_UP_QUESTION"
    )
    assert "fasting_blood_glucose" in _codes(evidence.primary_facts)
    assert "hba1c" in _codes(evidence.supporting_facts)
    assert "Do not restart" in evidence.payload()["how_to_answer"]


def test_follow_up_through_chat_carries_previous_marker():
    first = _chat("Why is my HbA1c high?")
    body = _chat("But my fasting glucose is normal?", conversation_id=first["conversation_id"])
    assert body["meta"]["requires_personal_data"] is True
    assert "hba1c" in body["meta"]["requested_entities"]


# ------------------------------------------------------------ relevance (Part 26)


def test_vitamin_d_answer_does_not_shoehorn_unrelated_context():
    _, evidence, prompt = _evidence("What does my Vitamin D mean?")
    payload = json.dumps(evidence.payload()).lower()
    assert "vitamin_d" in payload
    for unrelated in ("cardiac", "type_2_diabetes", "tobacco", "smok", "family history", "triglycerides", "hba1c"):
        assert unrelated not in payload, unrelated
    assert evidence.questionnaire_facts == []


# ------------------------------------------------------------ known evaluation failures


@pytest.mark.parametrize("message", ["What is my BUN?", "What is my Blood Urea Nitrogen?", "What is my BUN Urea Nitrogen?"])
def test_bun_aliases_retrieve_the_stored_marker(message):
    answer = _chat(message)["answer"]
    assert "14" in answer and "mg/dL" in answer


def test_urea_question_never_converts_or_relabels_bun():
    # The report stores BUN only. CURA may answer with the stored BUN (labelled as BUN) or say
    # urea is absent, but never converts the number or presents BUN 14 as a urea value.
    answer = _chat("What is my urea?")["answer"]
    assert "Urea is 14" not in answer and "urea of 14" not in answer.lower() and "urea 14" not in answer.lower()
    assert "30" not in answer  # 14 x 2.14 would be ~30 mg/dL urea
    assert "BUN" in answer or "I don't see Urea" in answer


def test_missing_data_answer_is_honest():
    answer = _chat("What is my ferritin?")["answer"]
    assert "I don't see Ferritin" in answer and "not available" in answer


def test_explanation_request_is_not_refused_as_diagnosis():
    body = _chat("Help me understand my HbA1c result")
    answer = body["answer"].lower()
    assert "can't diagnose" not in answer and "cannot diagnose" not in answer
    assert "6.1" in answer
    assert body["meta"]["intent"] == "blood_marker_explanation"


def test_diagnosis_request_is_still_restrained():
    answer = _chat("Do I have diabetes?")["answer"].lower()
    assert "diagnos" in answer
    assert "you have diabetes" not in answer


def test_response_has_no_duplicated_explanation():
    text = "HbA1c reflects your average glucose over roughly three months."
    presentation = StructuredResponse(mode=ResponseMode.interpretation, summary=text, interpretation=text)
    flat = flatten_structured_response(presentation, raw_answer=text)
    assert flat.count("average glucose") == 1


def test_unsupported_urgency_is_removed_but_routine_advice_kept():
    text = (
        "Your HbA1c is above your report's range. Please see a doctor within 24 hours. "
        "It is worth discussing at your next routine check-up."
    )
    cleaned, changed = strip_unsupported_urgency(text)
    assert changed
    assert "24 hours" not in cleaned
    assert "routine check-up" in cleaned and "above your report's range" in cleaned


def test_red_flag_urgency_is_untouched():
    body = _chat("I have crushing chest pain and my left arm is numb")
    assert body["meta"].get("escalation") or "emergency" in body["answer"].lower() or "112" in body["answer"]


# ------------------------------------------------------------ latency instrumentation and efficiency


def test_latency_instrumentation_records_stages_without_phi():
    body = _chat("Why is my HbA1c high?")
    stages = body["meta"]["timing"]["stages"]
    for key in ("total_ms", "intent_ms", "context_build_ms", "safety_ms", "retry_count", "provider_attempts", "cache_hit"):
        assert key in stages, key
    blob = json.dumps(stages).lower()
    assert "hba1c" not in blob and "6.1" not in blob and "sam" not in blob


def test_parallel_health_retrieval(monkeypatch):
    from app.providers import registry as registry_module

    reg = registry_module.get_registry()
    active, peak = [0], [0]
    lock = threading.Lock()

    def slow(original):
        def run(*args, **kwargs):
            with lock:
                active[0] += 1
                peak[0] = max(peak[0], active[0])
            time.sleep(0.25)
            with lock:
                active[0] -= 1
            return original(*args, **kwargs)
        return run

    monkeypatch.setattr(reg.blood, "query", slow(reg.blood.query))
    monkeypatch.setattr(reg.bio_ai, "query", slow(reg.bio_ai.query))
    monkeypatch.setattr(reg.lifestyle, "query", slow(reg.lifestyle.query))
    from app.retrieval.router import HealthRetrievalRouter

    plan = build_query_plan("How am I doing overall?").model_copy(
        update={"needs_blood": True, "needs_bio_ai": True, "needs_lifestyle": True}
    )
    started = time.perf_counter()
    HealthRetrievalRouter(reg).retrieve(USER, plan)
    elapsed = time.perf_counter() - started
    assert peak[0] >= 2, "independent provider reads should overlap"
    assert elapsed < 0.6


def test_llm_timeout_is_not_retried_with_another_format(monkeypatch):
    from app.core.circuit_breaker import openrouter_breaker
    from app.core.errors import LLMUnavailableError
    from app.llm import openai_compatible as oc

    calls = []

    class Timeouting:
        def post(self, *args, **kwargs):
            calls.append(kwargs.get("timeout"))
            raise httpx.ReadTimeout("slow")

    openrouter_breaker.reset()
    monkeypatch.setattr(oc, "get_http_client", lambda: Timeouting())
    monkeypatch.setattr(settings, "llm_max_retries", 1)
    llm = oc.OpenAICompatibleLLMClient(api_key="k", base_url="https://example.invalid/api/v1", model="m", timeout=5)
    real_complete = getattr(oc.OpenAICompatibleLLMClient, "_real_complete", oc.OpenAICompatibleLLMClient.complete)
    with pytest.raises(LLMUnavailableError):
        real_complete(llm, [{"role": "user", "content": "hi"}], json_mode=True)
    # One HTTP retry inside one format; never a second format after a timeout.
    assert len(calls) == 2
    assert all(t is not None and t <= 5 for t in calls)
    openrouter_breaker.reset()


def test_jev_timeout_is_not_retried(monkeypatch):
    from app.core.circuit_breaker import jev_breaker
    from app.core.errors import LLMUnavailableError
    from app.routing import jev_client
    from app.routing.schemas import JevRoutingState

    calls = []

    class Timeouting:
        def post(self, *args, **kwargs):
            calls.append(1)
            raise httpx.ReadTimeout("slow")

    jev_breaker.reset()
    monkeypatch.setattr(jev_client, "get_http_client", lambda: Timeouting())
    monkeypatch.setattr(settings, "llm_max_retries", 2)
    with pytest.raises(LLMUnavailableError):
        jev_client.JevDecisionsClient(api_key="k", base_url="https://example.invalid/api/v1").decide(
            JevRoutingState(current_message="What is my HbA1c?")
        )
    assert len(calls) == 1
    jev_breaker.reset()


def test_obvious_lookup_skips_the_router_call(monkeypatch):
    from app.routing.jev_client import JevDecisionsClient

    def boom(*_args, **_kwargs):
        raise AssertionError("Jev should not be called for an obvious lookup")

    monkeypatch.setattr(settings, "jev_enabled", True)
    monkeypatch.setattr(settings, "jev_fast_path", True)
    monkeypatch.setattr(JevDecisionsClient, "decide", boom)
    body = _chat("What is my HbA1c?")
    assert "6.1" in body["answer"]
    assert body["meta"]["jev_called"] is False


def test_ambiguous_question_still_uses_the_router(monkeypatch):
    from app.routing.jev_client import JevDecisionsClient

    called = []

    def decide(_self, state):
        from app.core.errors import LLMUnavailableError

        called.append(state.current_message)
        raise LLMUnavailableError("offline")

    monkeypatch.setattr(settings, "jev_enabled", True)
    monkeypatch.setattr(settings, "jev_fast_path", True)
    monkeypatch.setattr(JevDecisionsClient, "decide", decide)
    _chat("My cholesterol looks okay, so why is my cardiac risk high?")
    assert called
