"""Semantic health planning: unseen questions map onto goals x topics x evidence.

The planner is scored separately from final prose (goal, topic, personalization, time,
source and clarification accuracy), so a bad answer can be traced to the stage that failed.
"""

import json

import pytest
from fastapi.testclient import TestClient

from app.auth.models import AuthenticatedPrincipal
from app.contracts.questionnaire import QuestionnaireAnswer, QuestionnaireInstance
from app.core.config import settings
from app.main import app
from app.pipeline.answer_evidence import build_answer_evidence
from app.pipeline.context_builder import ContextBuilder
from app.pipeline.evidence_planner import SUPPORTED_SOURCES, reconcile_query_plan
from app.pipeline.query_planner import build_query_plan
from app.pipeline.semantic_plan import (
    ExecutionPath,
    HealthSource,
    Personalization,
    ReasoningGoal,
    TemporalNeed,
    build_semantic_plan,
)
from app.providers.registry import build_registry
from app.routing.jev_client import JevDecisionsClient
from app.routing.schemas import JevDecision, JevDecisionsResponse, JevIntent, JevOperation, JevSource

client = TestClient(app)
DEMO = {"X-Cura-User-Id": "demo-user-001"}
Q1 = {"X-Cura-User-Id": "demo-user-q1"}
G = ReasoningGoal


def _plan(message: str, **kwargs):
    return build_semantic_plan(message, **kwargs)


def _chat(message: str, headers=DEMO, **extra) -> dict:
    return client.post("/api/v1/chat", headers=headers, json={"message": message, **extra}).json()


def _semantic(body: dict) -> dict:
    return (body.get("meta", {}).get("debug") or {}).get("semantic_plan") or {}


# ------------------------------------------------------------ paraphrase generalisation

ACTIVITY_ASSESS = [
    "Am I active enough?",
    "Do I move enough for my health?",
    "Is my exercise level okay?",
    "Given my results, should I be doing more activity?",
    "Is my current workout routine enough for me?",
    "Am I physically active enough for my current health situation?",
    "mera activity enough hai kya for current reports?",
    "is my excercise ok for my health",  # typo
]

PRIORITIZE = [
    "What should I change first?",
    "Where should I start?",
    "What's the biggest thing I can improve?",
    "Which habit matters most right now?",
    "If I only changed one thing, what should it be?",
    "What I need to work on first?",
    "out of everything what really matters?",
    "Based on my lifestyle, what is likely worth changing first?",
]


@pytest.mark.parametrize("message", ACTIVITY_ASSESS)
def test_unseen_paraphrase_routes_to_same_reasoning_goal(message):
    plan = _plan(message)
    assert plan.primary_goal == G.assess, message
    assert "physical_activity" in plan.health_topics, message
    assert plan.personalization == Personalization.required, message
    assert HealthSource.questionnaire in plan.required_sources, message
    assert not plan.clarification_needed


@pytest.mark.parametrize("message", PRIORITIZE)
def test_prioritization_paraphrases_map_to_prioritize(message):
    plan = _plan(message)
    assert plan.primary_goal == G.prioritize, message
    assert plan.personalization == Personalization.required, message
    assert HealthSource.questionnaire in plan.required_sources, message
    assert not plan.clarification_needed


ADVERSARIAL = [
    ("I do gym tho, why tg still high?", G.causes, "triglycerides"),
    ("why sugar so high in my report??", G.causes, "glucose"),
    ("Kindly advise whether my lipid profile warrants concern.", G.risk, "lipid_health"),
    ("hba1c went up. bad?", G.assess, "hba1c"),
    ("my neend is like 5 hrs only, is that ok for my health", G.assess, "sleep"),
    ("Why do I feel so tired by evening", G.causes, "fatigue"),
    ("what can I do about my weight", G.action, "weight"),
    ("Has my vitamin D improved?", G.compare, "vitamin_d"),
]


@pytest.mark.parametrize(("message", "goal", "topic"), ADVERSARIAL)
def test_adversarial_phrasings(message, goal, topic):
    plan = _plan(message)
    assert plan.primary_goal == goal, (message, plan.primary_goal)
    assert topic in plan.health_topics, (message, plan.health_topics)
    assert plan.personalization == Personalization.required


def test_personalized_question_uses_semantic_goal_not_exact_phrase():
    # Same task, no shared trigger phrase.
    a = _plan("Is my sleep okay for my health?")
    b = _plan("Do I get enough sleep given my results?")
    assert a.primary_goal == b.primary_goal == G.assess
    assert "sleep" in a.health_topics and "sleep" in b.health_topics
    assert a.required_sources == b.required_sources == [HealthSource.questionnaire]


def test_multi_goal_query_supports_compare_assess_and_action():
    plan = _plan("My triglycerides improved but HbA1c went up. Is that good or bad and what should I do?")
    assert plan.primary_goal == G.assess
    assert {G.compare, G.action} <= set(plan.secondary_goals)
    assert {"triglycerides", "hba1c"} <= set(plan.health_topics)
    assert plan.temporal_requirement in {TemporalNeed.comparison, TemporalNeed.trend}
    assert HealthSource.history in plan.required_sources


def test_unseen_cross_source_question():
    plan = _plan("My blood tests look mostly normal, so why is my Bio-AI metabolic risk high?")
    assert plan.primary_goal in {G.causes, G.explain}
    assert {HealthSource.blood, HealthSource.bio_ai} <= set(plan.required_sources)


def test_exercising_member_triglyceride_question_plans_activity_context():
    plan = _plan("I work out regularly, so why are my triglycerides still high?")
    assert plan.primary_goal in {G.causes, G.explain}
    assert {"triglycerides", "physical_activity"} <= set(plan.health_topics)
    assert HealthSource.blood in plan.required_sources
    assert HealthSource.questionnaire in plan.required_sources


# ------------------------------------------------------------ personalization / time / sources


def test_general_health_question_does_not_fetch_personal_context_unnecessarily():
    for message in ("What is HbA1c?", "What causes fatty liver?", "How does exercise affect cholesterol?"):
        plan = _plan(message)
        assert plan.personalization == Personalization.none, message
        assert plan.required_sources == [HealthSource.medical_knowledge], message
        assert not (set(plan.optional_sources) & {HealthSource.blood, HealthSource.questionnaire}), message


def test_explicit_value_question_is_optional_personalization():
    plan = _plan("What does an HbA1c of 5.3 usually mean?")
    assert plan.personalization == Personalization.optional
    assert HealthSource.blood not in plan.required_sources


def test_personal_health_question_marks_personalization_required():
    for message in ("What does my HbA1c mean for me?", "What should I change first?", "Am I physically active enough?",
                    "Why is my triglyceride level high?"):
        assert _plan(message).personalization == Personalization.required, message


def test_conditional_my_is_hypothetical():
    assert _plan("If my thyroid is high, what does that mean?").personalization != Personalization.required


def test_simple_lookup_retrieves_minimal_context():
    plan = _plan("What is my LDL?")
    assert plan.primary_goal == G.lookup
    assert plan.required_sources == [HealthSource.blood]
    assert plan.execution_path == ExecutionPath.fast
    # FAST path never fetches optional sources.
    routed, _ = reconcile_query_plan(build_query_plan("What is my LDL?"), plan)
    assert not routed.needs_questionnaire and not routed.needs_bio_ai and not routed.history


def test_vitamin_d_lookup_never_plans_questionnaire():
    plan = _plan("What's my Vitamin D?")
    assert HealthSource.questionnaire not in plan.required_sources + plan.optional_sources


@pytest.mark.parametrize(
    ("message", "temporal"),
    [
        ("What is my HbA1c?", TemporalNeed.current),
        ("What was my HbA1c last time?", TemporalNeed.historical),
        ("Is my HbA1c improving over time?", TemporalNeed.trend),
        ("Has my LDL changed since my previous report?", TemporalNeed.comparison),
        ("What is HbA1c?", TemporalNeed.none),
    ],
)
def test_temporal_requirement(message, temporal):
    assert _plan(message).temporal_requirement == temporal


def test_planner_sources_are_always_supported_capabilities():
    for message in [*ACTIVITY_ASSESS, *PRIORITIZE, *(m for m, _, _ in ADVERSARIAL)]:
        plan = _plan(message)
        assert set(plan.required_sources + plan.optional_sources) <= SUPPORTED_SOURCES


def test_plan_describes_operations_not_diagnoses():
    plan = _plan("Why is my HbA1c high?")
    blob = json.dumps(plan.trace()).lower()
    for word in ("diagnosis", "insulin resistance", "diabetic", "prediabetes"):
        assert word not in blob


# ------------------------------------------------------------ clarification is a last resort


def test_activity_assessment_does_not_trigger_generic_clarification():
    body = _chat("Am I physically active enough for my current health situation?", Q1)
    assert "general information, your latest result" not in body["answer"]
    assert body["meta"].get("status") != "clarification_required"
    assert body["meta"]["requires_personal_data"] is True


def test_lifestyle_prioritization_does_not_trigger_latest_vs_history_prompt():
    body = _chat("Based on my lifestyle, what is likely worth changing first?", Q1)
    assert "comparison with previous results" not in body["answer"]
    assert body["meta"].get("status") != "clarification_required"
    assert "could not find matching personal health data" not in body["answer"].lower()


def test_true_ambiguity_can_still_trigger_clarification():
    plan = _plan("Is 120 bad?")
    assert plan.clarification_needed and plan.clarification_reason == "number_without_measure"
    body = _chat("Is 120 bad?")
    assert body["meta"].get("status") == "clarification_required"
    assert "general information, your latest result" not in body["answer"]
    assert "fasting glucose" in body["answer"].lower()


def test_pronoun_with_conversation_context_is_not_ambiguous():
    plan = _plan("Is it bad?", conversation_entities=["ldl"], prior_personal=True)
    assert not plan.clarification_needed
    assert "ldl" in plan.health_topics


def _jev_clarify_low_confidence(monkeypatch):
    def decide(_self, state):
        return (
            JevDecision(
                intent=JevIntent.clarification,
                source=JevSource.none,
                operation=JevOperation.clarify,
                requires_clarification=True,
                confidence=0.41,
                clarification_question="Would you like general information, your latest result, or a comparison with previous results?",
                reasoning_goal="ASSESS",
                personalization="REQUIRED",
                temporal_requirement="CURRENT",
            ),
            JevDecisionsResponse(answers={}, model="jev", provider="test"),
        )

    monkeypatch.setattr(settings, "jev_enabled", True)
    monkeypatch.setattr(JevDecisionsClient, "decide", decide)


def test_low_router_confidence_does_not_automatically_trigger_clarification(monkeypatch):
    _jev_clarify_low_confidence(monkeypatch)
    body = _chat("Am I active enough?", Q1)
    assert "general information, your latest result" not in body["answer"]
    assert body["meta"].get("status") != "clarification_required"
    assert _semantic(body).get("primary_goal") == "ASSESS"


def test_jev_semantic_answers_are_validated(monkeypatch):
    # Jev may raise personalization only when the message refers to the member.
    plan = _plan("What is HbA1c?", jev_goal="ASSESS", jev_personalization="REQUIRED")
    assert plan.personalization == Personalization.none
    plan = _plan("Is my sleep fine?", jev_goal="NOT_A_GOAL")
    assert plan.primary_goal == G.assess


# ------------------------------------------------------------ evidence selection


def _questionnaire(answers: dict, subject="demo-user-001"):
    rows = [
        QuestionnaireAnswer(
            response_id=f"r{i}", assessment_instance_id="qa", question_id=f"q{i}", question_key=k,
            question=k.replace("_", " "), value=v, response_type="text", recorded_at="2026-09-01", subject_id=subject,
        )
        for i, (k, v) in enumerate(answers.items())
    ]
    return [QuestionnaireInstance(assessment_instance_id="qa", subject_id=subject, recorded_at="2026-09-01", answers=rows)]


FULL = {
    "sleeping_hours": "6-7 hours",
    "physical_activity_frequency": "Rarely",
    "exercise_level": "Light",
    "exercise_frequency_week": "0-1 days",
    "daily_active_duration": "Less than 30 minutes",
    "sitting_hours": "More than 8 hours",
    "diet_preference": "Vegetarian",
    "food_groups": "Mostly refined grains",
    "healthy_breakfast_frequency": "Rarely",
    "fresh_fruit_frequency": "Weekly",
    "fresh_vegetable_frequency": "Daily",
    "alcohol_frequency": "Never",
    "tobacco_frequency": "Never",
}


def _evidence(message: str, answers: dict | None = None, recent: list[str] | None = None, subject="demo-user-001"):
    semantic = _plan(message)
    plan, _ = reconcile_query_plan(build_query_plan(message), semantic)
    ctx = ContextBuilder(build_registry()).build(AuthenticatedPrincipal(subject_id=subject), plan)
    ctx.semantic_plan = semantic.model_dump(mode="json") | {
        "markers": semantic.markers, "bio_ai": semantic.bio_ai, "concepts": semantic.concepts, "domains": semantic.domains,
    }
    if answers is not None:
        ctx.questionnaire = _questionnaire(answers, subject)
    if recent:
        ctx.recent_user_messages = recent
    return ctx, build_answer_evidence(ctx, message)


def test_activity_question_uses_relevant_questionnaire_context():
    _, evidence = _evidence("Am I active enough?", FULL)
    areas = {item["area"] for item in evidence.questionnaire_facts}
    assert "physical activity" in areas
    assert evidence.response_mode == "PERSONALIZED_ASSESSMENT"


def test_activity_question_does_not_dump_entire_questionnaire():
    _, evidence = _evidence("Am I active enough?", FULL)
    assert len(evidence.questionnaire_facts) <= 4
    areas = {item["area"] for item in evidence.questionnaire_facts}
    assert not areas & {"alcohol", "tobacco", "diet pattern"}


def test_current_user_statement_can_override_stale_questionnaire_for_current_reasoning():
    _, evidence = _evidence(
        "Am I active enough?", FULL, recent=["I've been exercising five days a week for the last two months."]
    )
    activity = [f for f in evidence.questionnaire_facts if f["area"] == "physical activity"]
    assert activity and activity[0]["source"] == "user stated in this conversation"
    assert activity[0]["stance"] == "supportive"
    assert evidence.questionnaire.overridden_keys  # provenance kept, nothing silently overwritten


def test_high_premise_is_corrected_when_latest_value_is_normal():
    # demo-user-001: HDL 41 mg/dL is within range.
    _, evidence = _evidence("Why is my HDL high?")
    check = evidence.premise_check
    assert check and check["latest_measurement"]["code"] == "hdl"
    assert check["latest_measurement"]["value"] == 41.0
    assert "does not match" in check["instruction"]


def test_high_hba1c_premise_is_corrected_when_latest_hba1c_is_normal():
    from app.pipeline.answer_evidence import _premise_check

    class M:
        key, name, value, unit, reference_low, reference_high, measured_at = "hba1c", "HbA1c", 5.3, "%", 4.0, 5.6, None

        class flag:  # noqa: N801
            value = "normal"

    check = _premise_check({"topic": "hba1c", "claimed": "high"}, [M()], [])
    assert check["latest_measurement"]["value"] == 5.3 and check["latest_measurement"]["unit"] == "%"
    assert "does not match" in check["instruction"]
    assert _premise_check({"topic": "hba1c", "claimed": "low"}, [M()], [])  # also mismatched
    M.flag.value = "high"
    assert _premise_check({"topic": "hba1c", "claimed": "high"}, [M()], []) is None


def test_fatigue_checks_relevant_markers_without_claiming_cause():
    _, evidence = _evidence("Why do I feel tired in the afternoon?")
    codes = {f["code"] for f in evidence.primary_facts}
    assert codes <= {"hemoglobin", "ferritin", "vitamin_b12", "vitamin_d", "tsh", "fasting_blood_glucose"}
    assert "several possible contributors" in evidence.payload()["how_to_answer"]


@pytest.mark.parametrize(
    ("answers", "must_not_lead", "expect_supportive"),
    [
        ({**FULL, "physical_activity_frequency": "Rarely", "alcohol_frequency": "Never"}, None, {"alcohol"}),
        ({**FULL, "physical_activity_frequency": "Daily", "exercise_frequency_week": "5-6 days",
          "exercise_level": "Moderate", "daily_active_duration": "More than 60 minutes"}, "physical activity", {"physical activity"}),
        ({**FULL, "physical_activity_frequency": "Daily", "exercise_frequency_week": "5-6 days",
          "alcohol_frequency": "Daily"}, "physical activity", {"physical activity"}),
    ],
)
def test_same_question_personalizes_differently(answers, must_not_lead, expect_supportive):
    _, evidence = _evidence("What should I do to improve my triglycerides?", answers)
    supportive = {f["area"] for f in evidence.questionnaire_facts if f["stance"] == "supportive"}
    levers = [f["area"] for f in evidence.questionnaire_facts if f["stance"] == "possible_lever"]
    assert expect_supportive <= supportive | set(evidence.already_doing)
    if must_not_lead:
        assert must_not_lead not in levers
    if answers["alcohol_frequency"] == "Daily":
        assert "alcohol" in levers


# ------------------------------------------------------------ planner quality scoring

GOLD = [
    # message, goal, topic (any of), personalization, temporal, required source, clarify
    ("What is my HDL?", "LOOKUP", "hdl", "REQUIRED", "CURRENT", "blood", False),
    ("Why is my HDL low?", "CAUSES", "hdl", "REQUIRED", "CURRENT", "blood", False),
    ("Is my HDL something I should worry about?", "RISK", "hdl", "REQUIRED", "CURRENT", "blood", False),
    ("What should I focus on first?", "PRIORITIZE", "overall_health", "REQUIRED", "CURRENT", "blood", False),
    ("Am I active enough?", "ASSESS", "physical_activity", "REQUIRED", "CURRENT", "questionnaire", False),
    ("I already exercise regularly, what else should I work on?", "ACTION", "physical_activity", "REQUIRED", "CURRENT", "questionnaire", False),
    ("Based on my lifestyle, what should I change first?", "PRIORITIZE", "lifestyle", "REQUIRED", "CURRENT", "questionnaire", False),
    ("Why am I tired?", "CAUSES", "fatigue", "REQUIRED", "CURRENT", "blood", False),
    ("My sugar looks okay, so why is my metabolic risk high?", "CAUSES", "metabolic_score", "REQUIRED", "CURRENT", "bio_ai", False),
    ("Which of my results matters most for my goal?", "PRIORITIZE", "overall_health", "REQUIRED", "CURRENT", "blood", False),
    ("What's improved since my previous report?", "COMPARE", "overall_health", "REQUIRED", "COMPARISON", "history", False),
    ("What has become worse?", "COMPARE", "overall_health", "REQUIRED", "COMPARISON", "history", False),
    ("How am I doing overall?", "SYNTHESIZE", "overall_health", "REQUIRED", "CURRENT", "blood", False),
    ("What am I already doing well?", "ASSESS", "overall_health", "REQUIRED", "CURRENT", "blood", False),
    ("I don't drink, so what else could be relevant for my triglycerides?", "ACTION", "triglycerides", "REQUIRED", "CURRENT", "blood", False),
    ("My questionnaire says I'm active but my metabolic risk is high. How can both be true?", "EXPLAIN", "metabolic_score", "REQUIRED", "CURRENT", "bio_ai", False),
    ("What is HbA1c?", "GENERAL_EDUCATION", "hba1c", "NONE", "NONE", "medical_knowledge", False),
    ("What causes fatty liver?", "GENERAL_EDUCATION", "nafld", "NONE", "NONE", "medical_knowledge", False),
    ("How can I improve my HbA1c?", "ACTION", "hba1c", "REQUIRED", "CURRENT", "blood", False),
    ("What did I report about sleep?", "LOOKUP", "sleep", "REQUIRED", "CURRENT", "questionnaire", False),
    ("Is 120 bad?", "ASSESS", None, "OPTIONAL", "NONE", None, True),
    ("Do I sleep enough?", "ASSESS", "sleep", "REQUIRED", "CURRENT", "questionnaire", False),
    ("Should I be worried about my liver?", "RISK", "liver_health", "REQUIRED", "CURRENT", "blood", False),
    ("Is my weight affecting my sugar?", "EXPLAIN", "weight", "REQUIRED", "CURRENT", "blood", False),
    ("How do my blood report and Bio-AI report fit together?", "SYNTHESIZE", None, "REQUIRED", "CURRENT", "blood", False),
    ("What's my metabolic score?", "LOOKUP", "metabolic_score", "REQUIRED", "CURRENT", "bio_ai", False),
    ("Compare my cholesterol with last year", "COMPARE", "cholesterol", "REQUIRED", "COMPARISON", "history", False),
]


def test_planner_quality_scores():
    """Each dimension is scored on its own so failures point at one planner stage."""
    totals = {k: 0 for k in ("goal", "topic", "personalization", "temporal", "source", "clarification")}
    misses: dict[str, list[str]] = {k: [] for k in totals}
    for message, goal, topic, perso, temporal, source, clarify in GOLD:
        plan = _plan(message)
        checks = {
            "goal": plan.primary_goal.value == goal,
            "topic": topic is None or topic in plan.health_topics,
            "personalization": plan.personalization.value == perso,
            "temporal": plan.temporal_requirement.value == temporal,
            "source": source is None or source in [s.value for s in plan.required_sources],
            "clarification": plan.clarification_needed == clarify,
        }
        for key, ok in checks.items():
            totals[key] += int(ok)
            if not ok:
                misses[key].append(message)
    n = len(GOLD)
    scores = {k: v / n for k, v in totals.items()}
    print("planner quality", json.dumps(scores), json.dumps({k: v for k, v in misses.items() if v}))
    assert scores["clarification"] == 1.0, misses["clarification"]
    assert scores["personalization"] >= 0.95, misses["personalization"]
    assert scores["goal"] >= 0.9, misses["goal"]
    assert scores["topic"] >= 0.9, misses["topic"]
    assert scores["temporal"] >= 0.9, misses["temporal"]
    assert scores["source"] >= 0.9, misses["source"]


def test_source_selection_metrics_low_irrelevant_retrieval():
    """Recall for useful sources stays high while irrelevant fetches stay rare."""
    irrelevant = {
        "What is my LDL?": {HealthSource.questionnaire, HealthSource.bio_ai, HealthSource.history},
        "What's my Vitamin D?": {HealthSource.questionnaire, HealthSource.bio_ai, HealthSource.history},
        "What did I report about sleep?": {HealthSource.blood, HealthSource.bio_ai, HealthSource.history},
        "Why am I tired?": {HealthSource.bio_ai, HealthSource.history},
        "What is HbA1c?": {HealthSource.blood, HealthSource.questionnaire, HealthSource.bio_ai},
    }
    fetched_irrelevant = 0
    for message, bad in irrelevant.items():
        plan = _plan(message)
        fetched = set(plan.required_sources)
        if plan.execution_path != ExecutionPath.fast:
            fetched |= set(plan.optional_sources)
        fetched_irrelevant += len(fetched & bad)
    assert fetched_irrelevant == 0


# ------------------------------------------------------------ end to end (planning through the API)

E2E = [
    ("What is my HDL?", "LOOKUP"),
    ("Why is my HDL low?", "CAUSES"),
    ("Is my HDL something I should worry about?", "RISK"),
    ("What should I focus on first?", "PRIORITIZE"),
    ("Am I active enough?", "ASSESS"),
    ("I already exercise regularly, what else should I work on?", "ACTION"),
    ("Based on my lifestyle, what should I change first?", "PRIORITIZE"),
    ("Why am I tired?", "CAUSES"),
    ("My sugar looks okay, so why is my metabolic risk high?", "CAUSES"),
    ("Which of my results matters most for my goal?", "PRIORITIZE"),
    ("What's improved since my previous report?", "COMPARE"),
    ("What has become worse?", "COMPARE"),
    ("How am I doing overall?", "SYNTHESIZE"),
    ("What am I already doing well?", "ASSESS"),
    ("I don't drink, so what else could be relevant for my triglycerides?", "ACTION"),
    ("My questionnaire says I'm active but my metabolic risk is high. How can both be true?", "EXPLAIN"),
]


@pytest.mark.parametrize(("message", "goal"), E2E)
def test_end_to_end_semantic_planning(message, goal):
    body = _chat(message)
    trace = _semantic(body)
    assert trace.get("primary_goal") == goal, (message, trace)
    assert body["meta"].get("status") != "clarification_required"
    assert body["meta"]["requires_personal_data"] is True
    assert "general information, your latest result" not in body["answer"]
    latency = trace.get("latency_ms") or {}
    assert "planner" in latency and "total" in latency


def test_follow_up_what_should_i_do_about_it_uses_conversation():
    first = _chat("Why is my HDL low?")
    body = _chat("What should I do about it?", conversation_id=first["conversation_id"])
    assert body["meta"].get("status") != "clarification_required"
    assert body["meta"]["requires_personal_data"] is True
