"""Classify operation, named sources, recommendation category, and numeric ask-count."""

from __future__ import annotations

import re

from app.contracts.common import IntentType
from app.contracts.operations import AnswerOperation
from app.contracts.query import QueryPlan

_PROVENANCE = re.compile(
    r"\b("
    r"where did you get|"
    r"where is that from|"
    r"which report|"
    r"what source|"
    r"source of (?:that|this|the)|"
    r"how do you know|"
    r"where (?:is|was) that (?:value|result|number|cholesterol)"
    r")\b",
    re.I,
)
_INCREASE = re.compile(
    r"\b(increased|increase|went up|risen|rose|higher than (?:last|before|previously)|got worse)\b",
    re.I,
)
_DECREASE = re.compile(
    r"\b(decreased|decrease|went down|fallen|fell|lower than (?:last|before|previously)|improved)\b",
    re.I,
)
_MEASURE = re.compile(r"\b(measure|stand for|definition of|defined as)\b", re.I)
_THREE = re.compile(r"\b(three|3)\b", re.I)
_DIET = re.compile(r"\b(diet|dietary|foods?|eat|nutrition|meal)\b", re.I)
_ACTIVITY = re.compile(r"\b(exercise|activity|movement|walk|workout)\b", re.I)
_SLEEP = re.compile(r"\b(sleep|bedtime)\b", re.I)
_BLOOD = re.compile(r"\b(blood|lab) (report|result|test)s?|\b(?:cbc|lipid panel|markers?)\b", re.I)
_BIO = re.compile(r"\bbio-?ai\b", re.I)
_QUESTIONNAIRE = re.compile(r"\bquestionnaires?\b|\bsurvey answers?\b", re.I)
_GOALS = re.compile(r"\b(?:health )?goals?\b", re.I)
_UPLOAD = re.compile(r"\b(upload(?:ed)?|this (?:pdf|document)|the pdf)\b", re.I)
_OVERVIEW = re.compile(
    r"\b(overview|comprehensive|bigger picture|overall health|all (?:my |available )?sources)\b",
    re.I,
)
_CLINICIAN = re.compile(
    r"\b(summarize (?:this |it )?for my doctor|what should i ask my doctor|"
    r"prepare .{0,20}doctor|clinician (?:handoff|summary)|take to my doctor)\b",
    re.I,
)
_GOAL_PROGRESS = re.compile(
    r"\b(progress(?:ing)? toward|how am i doing (?:on|with) my goals?|goal progress)\b",
    re.I,
)


def named_personal_sources(message: str) -> set[str]:
    text = message or ""
    found: set[str] = set()
    if _BLOOD.search(text):
        found.add("blood")
    if _BIO.search(text):
        found.add("bio_ai")
    if _QUESTIONNAIRE.search(text):
        found.add("questionnaire")
    if _GOALS.search(text):
        found.add("goals")
    if _UPLOAD.search(text):
        found.add("uploaded")
    return found


def is_multi_source_request(message: str) -> bool:
    return len(named_personal_sources(message)) >= 2


def is_provenance_request(message: str) -> bool:
    return bool(_PROVENANCE.search(message or ""))


def is_falseable_change_claim(message: str) -> bool:
    return bool(_INCREASE.search(message or "") or _DECREASE.search(message or ""))


def requested_recommendation_category(message: str) -> str | None:
    text = message or ""
    if _DIET.search(text) and not _ACTIVITY.search(text) and not _SLEEP.search(text):
        return "diet"
    if _ACTIVITY.search(text) and not _DIET.search(text):
        return "activity"
    if _SLEEP.search(text) and not _DIET.search(text):
        return "sleep"
    if _DIET.search(text):
        return "diet"
    return None


def requested_item_count(message: str) -> int | None:
    text = message or ""
    if _THREE.search(text) and _DIET.search(text):
        return 3
    match = re.search(r"\b(\d+)\s+(dietary changes|foods|recommendations|changes)\b", text, re.I)
    if match:
        return int(match.group(1))
    return None


def classify_operation(plan: QueryPlan, message: str) -> AnswerOperation:
    text = message or plan.raw_message or ""
    if is_provenance_request(text):
        return AnswerOperation.provenance
    if _CLINICIAN.search(text):
        return AnswerOperation.prepare_clinician_discussion
    if plan.intent == IntentType.health_goal_progress or _GOAL_PROGRESS.search(text):
        return AnswerOperation.assess_goal_progress
    if plan.needs_cross_source:
        return AnswerOperation.cross_source_analysis
    if plan.intent in {IntentType.trend} or is_falseable_change_claim(text):
        return AnswerOperation.trend
    if plan.intent in {IntentType.bio_ai_comparison} or plan.compare:
        if plan.intent == IntentType.trend:
            return AnswerOperation.trend
        if plan.intent in {IntentType.bio_ai_comparison}:
            return AnswerOperation.compare
    if plan.intent in {IntentType.nutrition_guidance} or requested_recommendation_category(text):
        if plan.knowledge_scope.value == "personal" and plan.intent == IntentType.nutrition_guidance:
            return AnswerOperation.recommend
    if plan.intent in {IntentType.broad_health_summary, IntentType.report_explanation, IntentType.health_scenario}:
        return AnswerOperation.summarize
    if _OVERVIEW.search(text) and named_personal_sources(text):
        return AnswerOperation.summarize
    if plan.intent == IntentType.health_goal_progress:
        return AnswerOperation.assess_goal_progress
    if plan.intent in {IntentType.blood_marker_explanation, IntentType.bio_ai_explanation}:
        return AnswerOperation.personal_interpretation
    if plan.intent == IntentType.general_health_question or _MEASURE.search(text):
        return AnswerOperation.explain
    if plan.intent in {IntentType.latest_result, IntentType.previous_result, IntentType.bio_ai_score, IntentType.questionnaire_lookup}:
        return AnswerOperation.lookup
    if plan.intent == IntentType.personal_profile:
        return AnswerOperation.summarize
    return AnswerOperation.lookup


def apply_operation_metadata(plan: QueryPlan) -> QueryPlan:
    message = plan.raw_message or ""
    plan.operation = classify_operation(plan, message).value
    plan.requested_category = requested_recommendation_category(message)
    plan.requested_count = requested_item_count(message)
    if is_falseable_change_claim(message):
        if _INCREASE.search(message):
            plan.premise_claim = "increased"
        elif _DECREASE.search(message):
            plan.premise_claim = "decreased"
    named = named_personal_sources(message)
    personal = plan.knowledge_scope.value == "personal" or plan.needs_personal_data
    if personal:
        if "blood" in named:
            plan.needs_blood = True
            plan.needs_supershyft = True
        if "bio_ai" in named:
            plan.needs_bio_ai = True
            plan.needs_supershyft = True
        if "questionnaire" in named:
            plan.needs_questionnaire = True
        if "goals" in named:
            plan.needs_goals = True
            plan.needs_profile = True
            plan.needs_supershyft = True
        if "uploaded" in named:
            plan.needs_user_uploaded = True
        if is_multi_source_request(message) or (_OVERVIEW.search(message) and personal):
            if _OVERVIEW.search(message) and not named:
                plan.needs_blood = True
                plan.needs_bio_ai = True
                plan.needs_questionnaire = True
                plan.needs_goals = True
            plan.needs_supershyft = True
            if len(named) >= 2 or _OVERVIEW.search(message):
                from app.contracts.common import QuerySource

                plan.source = QuerySource.mixed
    return plan
