"""Closed ontology helpers for QueryPlan construction. No SQL, no credentials."""

from __future__ import annotations

import re

from app.contracts.common import IntentType
from app.contracts.query import QueryPlan
from app.pipeline.intent import BIO_ALIASES, NAMES, _alias_in_text, _named_score_code
from app.pipeline.lab_parameters import display_name_for, expand_requested_keys, match_lab_keys, primary_lab_key
from app.pipeline.language import normalize_for_intent

_BIO_CUE = re.compile(r"\b(score|bio-?ai|assessment|risk)\b", re.I)
_GUIDANCE = re.compile(
    r"\b("
    r"what should i (?:do|eat|change)|"
    r"how (?:can|do) i (?:lower|reduce|improve|raise)|"
    r"lifestyle|"
    r"exercise based on|"
    r"what (?:foods|diet)|"
    r"to reduce (?:it|them|this)|"
    r"based on my (?:blood report|health profile|results?)"
    r")\b",
    re.I,
)
_LATEST_REPORT = re.compile(
    r"\b("
    r"in my latest (?:blood |lab )?(?:report|test)|"
    r"what(?:'s| is) in my latest (?:blood |lab )?(?:report|test)|"
    r"latest (?:blood |lab )report|"
    r"my latest (?:blood |lab )report"
    r")\b",
    re.I,
)
_EXERCISE_PROFILE = re.compile(
    r"\b(based on my (?:health )?profile|based on my (?:blood )?report|for my health)\b",
    re.I,
)


def match_bio_keys(text: str) -> list[str]:
    lowered = (text or "").lower()
    found: list[str] = []
    seen: set[str] = set()
    for alias, code in sorted(BIO_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        if code in seen:
            continue
        if _alias_in_text(alias, lowered):
            seen.add(code)
            found.append(code)
    return found


def requested_metrics_from_message(message: str) -> list[str]:
    text = normalize_for_intent(message).lower()
    labs = match_lab_keys(text)
    bios = match_bio_keys(text)
    score_cue = bool(_BIO_CUE.search(text))
    if labs and bios and not score_cue:
        return labs
    if bios and (score_cue or not labs):
        if labs and score_cue:
            return list(dict.fromkeys([*labs, *bios]))
        return bios
    if score_cue:
        named = _named_score_code(text)
        if named:
            return [named]
    return labs


def infer_time_operation(message: str, intent: IntentType) -> str:
    text = normalize_for_intent(message).lower()
    if intent in {IntentType.trend, IntentType.bio_ai_comparison} or (
        re.search(r"\b(changed|trend|compare|compared|comparison)\b", text)
        and intent != IntentType.latest_result
    ):
        if intent == IntentType.bio_ai_comparison:
            return "compare"
        if intent == IntentType.trend:
            return "trend"
    if intent == IntentType.previous_result:
        return "previous"
    if intent == IntentType.bio_ai_comparison:
        return "compare"
    if intent == IntentType.trend:
        return "trend"
    if _LATEST_REPORT.search(text) and not match_lab_keys(text):
        return "latest_report"
    if intent == IntentType.broad_health_summary and re.search(r"\bblood report\b", text):
        return "latest_report"
    return "latest_marker"


def needs_guidance(message: str) -> bool:
    return bool(_GUIDANCE.search(normalize_for_intent(message)))


def is_personalized_lifestyle(message: str) -> bool:
    text = normalize_for_intent(message).lower()
    return bool(_EXERCISE_PROFILE.search(text))


def canonicalize_metric_key(item: str | None) -> str | None:
    """Map a free-text marker/entity onto a closed ontology key. Routing-neutral."""
    if not item:
        return None
    key = primary_lab_key(item)
    if key:
        return key
    lowered_space = item.strip().lower().replace("_", " ")
    if lowered_space in BIO_ALIASES:
        return BIO_ALIASES[lowered_space]
    slug = item.strip().lower().replace(" ", "_")
    if slug in BIO_ALIASES:
        return BIO_ALIASES[slug]
    if slug in set(BIO_ALIASES.values()):
        return slug
    return slug


def normalize_requested_metrics(plan: QueryPlan) -> QueryPlan:
    """Canonicalize marker/entity names. Does not change source, intent, or retrieval flags."""
    metrics: list[str] = []
    for item in plan.requested_metrics or []:
        key = canonicalize_metric_key(item)
        if key and key not in metrics:
            metrics.append(key)
    plan.requested_metrics = metrics
    if plan.topic:
        topic_key = canonicalize_metric_key(plan.topic)
        if topic_key:
            plan.topic = topic_key
            plan.topic_name = NAMES.get(topic_key, plan.topic_name) or display_name_for(topic_key)
    elif metrics:
        plan.topic = metrics[0]
        plan.topic_name = plan.topic_name or NAMES.get(metrics[0], display_name_for(metrics[0]))
    return plan


def attach_ontology(plan: QueryPlan, message: str) -> QueryPlan:
    """Deterministic-path ontology: extract metrics and infer time/guidance from the message.

    Used by build_query_plan. Validated Jev routes must not call this; they use
    normalize_requested_metrics so heuristic time/guidance cannot overwrite Jev.
    """
    metrics = list(plan.requested_metrics or [])
    extracted = requested_metrics_from_message(message)
    if extracted:
        metrics = extracted
    elif plan.topic and not metrics:
        metrics = [plan.topic]
    plan.requested_metrics = metrics
    if metrics and not plan.topic:
        plan.topic = metrics[0]
        plan.topic_name = plan.topic_name or display_name_for(metrics[0])
    plan = normalize_requested_metrics(plan)
    plan.time_operation = infer_time_operation(message, plan.intent)
    plan.needs_guidance = needs_guidance(message)
    return plan


def retrieval_metric_keys(plan: QueryPlan) -> list[str]:
    return expand_requested_keys(plan.requested_metrics or ([plan.topic] if plan.topic else []))
