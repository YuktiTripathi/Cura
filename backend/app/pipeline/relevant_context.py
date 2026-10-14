"""Select a small relevant personal-context budget after retrieval.

Does not fetch a new user identity. Uses already-authorized reports on HealthContext.
"""

from __future__ import annotations

from app.contracts.blood import BloodMarker, BloodReport
from app.contracts.common import AnswerDepth, MarkerFlag
from app.contracts.conversation_experience import ConversationGoal, RelevantContext, ResponseDepth
from app.contracts.health_context import HealthContext
from app.contracts.query import QueryPlan
from app.pipeline.health_domains import domain_for_entity
from app.pipeline.lab_parameters import FAMILY_MEMBERS, display_name_for
from app.pipeline.personal_selection import latest_report

_ABNORMAL = {MarkerFlag.low, MarkerFlag.high, MarkerFlag.critical, "low", "high", "critical"}
_PATTERN_NEIGHBORS = {
    "hemoglobin": ("mcv", "mch", "mchc", "rbc", "hematocrit", "iron", "ferritin", "tibc"),
    "mcv": ("hemoglobin", "mch", "iron", "ferritin"),
    "mch": ("hemoglobin", "mcv", "iron", "ferritin"),
    "iron": ("hemoglobin", "mcv", "mch", "ferritin", "tibc", "transferrin"),
    "ferritin": ("iron", "hemoglobin", "tibc"),
    "vitamin_b12": ("folate", "hemoglobin", "mcv"),
    "vitamin_d": ("calcium",),
    "hdl": ("ldl", "triglycerides", "cholesterol"),
    "ldl": ("hdl", "triglycerides", "cholesterol"),
    "triglycerides": ("hdl", "ldl", "hba1c"),
    "hba1c": ("fasting_blood_glucose", "glucose", "triglycerides"),
    "glucose": ("fasting_blood_glucose", "hba1c"),
    "fasting_blood_glucose": ("hba1c", "glucose"),
    "tsh": ("t3", "t4"),
    "t3": ("tsh", "t4"),
    "t4": ("tsh", "t3"),
    "alt": ("ast", "bilirubin"),
    "ast": ("alt", "bilirubin"),
    "creatinine": ("egfr", "urea"),
    "egfr": ("creatinine", "urea"),
}


def _flag(marker: BloodMarker) -> str:
    raw = getattr(getattr(marker, "flag", None), "value", getattr(marker, "flag", None))
    return str(raw or "").lower()


def _usable(marker: BloodMarker) -> bool:
    return marker.value is not None


class RelevantContextSelector:
    """Split requested facts from a small set of directly related personal facts."""

    def select(
        self,
        context: HealthContext,
        plan: QueryPlan,
        *,
        reports: list[BloodReport] | None = None,
        goal: ConversationGoal | None = None,
        depth: ResponseDepth | None = None,
    ) -> RelevantContext:
        requested = list(
            dict.fromkeys(
                [
                    *(plan.display_entities or []),
                    *(plan.requested_metrics or []),
                    *(context.display_entity_codes or []),
                    *(context.requested_entity_codes or []),
                    *([plan.topic] if plan.topic else []),
                ]
            )
        )
        requested = [key for key in requested if key]
        present = {marker.key: marker for marker in context.markers or [] if marker.key}
        latest = latest_report(reports or []) if reports else None
        pool: dict[str, BloodMarker] = dict(present)
        if latest:
            for marker in latest.markers:
                if marker.key and _usable(marker):
                    pool.setdefault(marker.key, marker)

        supporting: list[str] = []
        pattern: list[str] = []
        budget = _supporting_budget(plan, goal, depth)
        for key in requested:
            neighbors = list(_PATTERN_NEIGHBORS.get(key, ()))
            family = FAMILY_MEMBERS.get(getattr(pool.get(key), "category", "") or "", ())
            domain = domain_for_entity(key)
            domain_keys = list(domain.primary_entities) if domain else []
            for neighbor in list(dict.fromkeys([*neighbors, *family, *domain_keys])):
                if neighbor in requested or neighbor in supporting:
                    continue
                marker = pool.get(neighbor)
                if marker is None or not _usable(marker):
                    continue
                if _flag(marker) not in _ABNORMAL:
                    continue
                if not _same_clinical_neighborhood(key, neighbor):
                    continue
                supporting.append(neighbor)
                if neighbor in neighbors:
                    pattern.append(neighbor)
                if len(supporting) >= budget:
                    break
            if len(supporting) >= budget:
                break

        pattern_keys = list(dict.fromkeys([key for key in requested if key in _PATTERN_NEIGHBORS] + pattern))
        note = None
        if len(pattern) >= 1 and requested:
            names = [display_name_for(key) for key in pattern_keys[:4]]
            note = (
                f"{', '.join(names[:-1])} and {names[-1]} sit together as a related pattern."
                if len(names) > 1
                else None
            )

        trend_keys: list[str] = []
        for item in context.baselines or []:
            if item.entity in {*requested, *supporting} and item.observations >= 2:
                trend_keys.append(item.entity)

        missing: list[str] = []
        present_keys = set(pool)
        for item in context.missing or []:
            key = item.key
            if key in {*requested, *supporting} or _related_missing(key, requested):
                missing.append(key)
        for key in requested:
            for neighbor in _PATTERN_NEIGHBORS.get(key, ()):
                if neighbor not in present_keys and neighbor not in missing and _related_missing(neighbor, requested):
                    missing.append(neighbor)

        return RelevantContext(
            requested_keys=requested[:8],
            supporting_keys=supporting[:budget],
            related_trend_keys=list(dict.fromkeys(trend_keys))[:4],
            relevant_missing_keys=list(dict.fromkeys(missing))[:4],
            pattern_keys=pattern_keys[:6],
            pattern_note=note,
        )

    def apply(
        self,
        context: HealthContext,
        relevant: RelevantContext,
        *,
        reports: list[BloodReport] | None = None,
        depth: ResponseDepth | None = None,
    ) -> HealthContext:
        """Keep requested + supporting markers on the context used for answering."""
        keep = set(relevant.requested_keys) | set(relevant.supporting_keys)
        if not keep:
            context.notes = _with_pattern_note(context.notes, relevant.pattern_note)
            return context
        if depth == ResponseDepth.deep or context.answer_depth in {AnswerDepth.broad, AnswerDepth.detailed}:
            context.notes = _with_pattern_note(context.notes, relevant.pattern_note)
            return context
        if context.question_type in {"health_review", "health_scenario"} or "overall_health" in (context.domains or []):
            context.notes = _with_pattern_note(context.notes, relevant.pattern_note)
            return context
        latest = latest_report(reports or []) if reports else None
        by_key = {marker.key: marker for marker in context.markers or [] if marker.key}
        if latest:
            for marker in latest.markers:
                if marker.key and marker.key not in by_key and _usable(marker):
                    by_key[marker.key] = marker
        ordered = [by_key[key] for key in [*relevant.requested_keys, *relevant.supporting_keys] if key in by_key]
        comparison_topics = {item.topic for item in (context.comparisons or []) if getattr(item, "topic", None)}
        preserved = [marker for marker in (context.markers or []) if marker.key in comparison_topics]
        if ordered or preserved:
            seen: set[tuple] = set()
            merged = []
            for marker in [*preserved, *ordered]:
                ident = (marker.key, str(getattr(marker, "measured_at", "") or ""), marker.value)
                if ident in seen:
                    continue
                seen.add(ident)
                merged.append(marker)
            context.markers = merged
        if relevant.relevant_missing_keys:
            context.missing = [
                item
                for item in context.missing or []
                if item.key in set(relevant.requested_keys) | set(relevant.relevant_missing_keys)
            ]
        context.notes = _with_pattern_note(context.notes, relevant.pattern_note)
        context.display_entity_codes = list(relevant.requested_keys)
        context.reasoning_context_codes = list(
            dict.fromkeys([*(context.reasoning_context_codes or []), *relevant.supporting_keys])
        )[:8]
        return context


def _supporting_budget(plan: QueryPlan, goal: ConversationGoal | None, depth: ResponseDepth | None) -> int:
    if depth == ResponseDepth.short or goal == ConversationGoal.quick_answer:
        return 3
    if depth == ResponseDepth.deep or goal in {ConversationGoal.health_review, ConversationGoal.deep_dive, ConversationGoal.prioritize}:
        return 6
    if plan.answer_depth in {AnswerDepth.broad, AnswerDepth.detailed}:
        return 6
    return 3


def _same_clinical_neighborhood(requested: str, candidate: str) -> bool:
    if candidate in _PATTERN_NEIGHBORS.get(requested, ()):
        return True
    left = domain_for_entity(requested)
    right = domain_for_entity(candidate)
    if left and right and left.code == right.code:
        return True
    for members in FAMILY_MEMBERS.values():
        if requested in members and candidate in members:
            return True
    return False


def _related_missing(key: str, requested: list[str]) -> bool:
    return any(key in _PATTERN_NEIGHBORS.get(item, ()) for item in requested)


def _with_pattern_note(notes: list[str] | None, note: str | None) -> list[str]:
    rows = list(notes or [])
    if note and note not in rows:
        rows.insert(0, note)
    return rows[:8]
