"""Orchestrate health-gap → test-need → catalog match → policy. After medical reasoning."""

from __future__ import annotations

import logging
import re
from datetime import date, datetime

from app.contracts.common import MarkerFlag
from app.contracts.conversation_state import ConversationState
from app.contracts.diagnostics import (
    CatalogPackageRef,
    DiagnosticsTrace,
    ExistingResult,
    HealthGap,
    HealthGapType,
    PackageAction,
    PackageActionType,
    PackageCandidate,
    PackageComparison,
    PackageRelevance,
    TestNeed,
    TestingOption,
    TestingRelevance,
)
from app.contracts.health_context import HealthContext
from app.contracts.query import QueryPlan
from app.core.config import settings
from app.pipeline.health_gaps import HealthGapDetector
from app.pipeline.lab_parameters import FAMILY_MEMBERS, display_name_for, match_lab_keys, primary_lab_key
from app.pipeline.package_matcher import PackageMatcher
from app.pipeline.package_policy import PackageRecommendationPolicy
from app.pipeline.test_need import TestNeedGenerator

logger = logging.getLogger("cura.diagnostics")

_EXPLICIT_PACKAGE = re.compile(
    r"\b(which (?:supershyft )?(?:package|panel|test group)|"
    r"package includes|which package has|"
    r"can i get (?:this|that|it|them) through supershyft|"
    r"supershyft package|"
    r"which test (?:shall|should|can|do) i|"
    r"(?:opt|choose|pick) for|"
    r"get tested for|"
    r"(?:on|for|through|from|via) supershyft)\b",
    re.I,
)
_ANOTHER_TEST = re.compile(
    r"\b(do i need (?:another|a new) (?:test|package|panel)|"
    r"should i (?:repeat|retest|get another)|"
    r"another test|test this again)\b",
    re.I,
)
_HEADLINES = {
    PackageRelevance.high: "A test that may help clarify this",
    PackageRelevance.moderate: "This test may be worth considering",
    PackageRelevance.optional: "This is an option, although your current data already covers part of it",
    PackageRelevance.not_recommended_now: "You probably don't need to repeat this test right now",
}
_HELPS = {
    "iron_status": "Whether your iron stores are depleted.",
    "red_cell_anaemia_health": "Whether iron stores help explain the current red-cell pattern.",
    "vitamin_d_bone_mineral_health": "Whether this has changed since the last measurement.",
    "lipid_health": "Whether a newer lipid panel would change the current picture.",
    "glycemic_health": "Whether glucose-related measurements would add information.",
    "metabolic_health": "Whether additional metabolic measurements would add information.",
}
_MONTH = {
    1: "Jan",
    2: "Feb",
    3: "Mar",
    4: "Apr",
    5: "May",
    6: "Jun",
    7: "Jul",
    8: "Aug",
    9: "Sep",
    10: "Oct",
    11: "Nov",
    12: "Dec",
}


def is_explicit_catalog_lookup(message: str) -> bool:
    return bool(_EXPLICIT_PACKAGE.search(message or ""))


def panel_member_keys(message: str) -> list[str]:
    """Map a named panel such as CBC onto the markers a catalog package is matched against."""
    lowered = (message or "").lower()
    keys: list[str] = []
    if re.search(r"\b(cbc|complete blood count)\b", lowered):
        keys.extend(FAMILY_MEMBERS.get("cbc", ()))
    return list(dict.fromkeys(keys))


def wants_another_test(message: str) -> bool:
    return bool(_ANOTHER_TEST.search(message or ""))


def _as_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _human_date(value) -> str | None:
    measured = _as_date(value)
    if not measured:
        return None
    return f"{measured.day} {_MONTH[measured.month]} {measured.year}"


def _flag(marker) -> MarkerFlag:
    raw = getattr(marker, "status", None) or getattr(marker, "flag", None)
    if isinstance(raw, MarkerFlag):
        return raw
    try:
        return MarkerFlag(str(raw))
    except ValueError:
        return MarkerFlag.unknown


def _latest_markers(context: HealthContext) -> dict[str, object]:
    latest: dict[str, object] = {}
    for marker in context.markers or []:
        key = getattr(marker, "key", None)
        if not key:
            continue
        current = latest.get(key)
        if current is None:
            latest[key] = marker
            continue
        left = _as_date(getattr(marker, "measured_at", None))
        right = _as_date(getattr(current, "measured_at", None))
        if left and (right is None or left >= right):
            latest[key] = marker
    return latest


def _label(item: PackageCandidate, key: str) -> str:
    return item.item.included_test_labels.get(key) or display_name_for(key)


def _join_names(names: list[str]) -> str:
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return f"{', '.join(names[:-1])} and {names[-1]}"


def _personalized_reason(
    *,
    context: HealthContext,
    gaps: list[HealthGap],
    candidate: PackageCandidate,
    relevance: PackageRelevance,
    explicit: bool,
    requested: list[str],
) -> str:
    latest = _latest_markers(context)
    if explicit and not gaps:
        names = [_label(candidate, key) for key in requested[:4] if key in candidate.item.included_tests]
        named = _join_names(names) or candidate.item.display_name
        return f"You asked which SuperShyft option includes {named}."
    lead = gaps[0] if gaps else None
    if relevance == PackageRelevance.not_recommended_now:
        present = []
        for key in candidate.coverage.matched_entities or requested:
            marker = latest.get(key)
            if marker is None or getattr(marker, "value", None) is None:
                continue
            when = _human_date(getattr(marker, "measured_at", None))
            label = _label(candidate, key)
            present.append(f"{label}" + (f" from {when}" if when else ""))
        if present:
            return (
                f"Your current reports already include {_join_names(present[:4])}, "
                "so repeating this now is unlikely to add much."
            )
        return "Your current reports already cover the measurements this would repeat."
    if lead and lead.gap_type in {
        HealthGapType.previous_abnormality_needs_follow_up,
        HealthGapType.stale_relevant_data,
    }:
        when = _human_date(lead.last_measured_on) or lead.last_measured_on
        names = _join_names([display_name_for(key) for key in (lead.stale_entities or requested)[:3]])
        dated = f" from {when}" if when else ""
        return (
            f"Your most recent {names or 'result'}{dated} cannot tell whether this has changed since then."
        )
    abnormal: list[str] = []
    missing: list[str] = []
    for gap in gaps:
        for key in gap.supporting_entities:
            marker = latest.get(key)
            if marker is not None and _flag(marker) in {MarkerFlag.low, MarkerFlag.high, MarkerFlag.critical}:
                name = display_name_for(key)
                if name not in abnormal:
                    abnormal.append(name)
        for key in gap.missing_entities:
            name = display_name_for(key)
            if name not in missing:
                missing.append(name)
    if abnormal and missing:
        verb = "is" if len(abnormal) == 1 else "are"
        miss_verb = "is" if len(missing) == 1 else "are"
        return (
            f"Your {_join_names(abnormal)} {verb} outside the reported range, "
            f"while {_join_names(missing)} {miss_verb} not available."
        )
    if missing:
        return f"{_join_names(missing)} would add information that is not in the current reports."
    if lead:
        return lead.reason
    return f"{candidate.item.display_name} includes the measurements related to this question."


def _helps_answer(gaps: list[HealthGap], relevance: PackageRelevance, explicit: bool) -> str:
    if explicit and not gaps:
        return "Which SuperShyft option includes the test you asked about."
    if relevance == PackageRelevance.not_recommended_now:
        return "Whether repeating these measurements would change what you already know."
    lead = gaps[0] if gaps else None
    if lead and lead.domain and lead.domain in _HELPS:
        return _HELPS[lead.domain]
    if lead and lead.gap_type in {
        HealthGapType.previous_abnormality_needs_follow_up,
        HealthGapType.stale_relevant_data,
    }:
        return "Whether this has changed since the last measurement."
    if lead and lead.missing_entities:
        names = _join_names([display_name_for(key) for key in lead.missing_entities[:3]])
        return f"Whether {names} would clarify the current pattern."
    return "Whether additional testing would add information for this question."


def _comparison(
    *,
    context: HealthContext,
    candidate: PackageCandidate,
    requested: list[str],
    relevance: PackageRelevance,
) -> PackageComparison:
    latest = _latest_markers(context)
    wanted = set(requested) | set(candidate.coverage.matched_entities)
    included_keys = [key for key in candidate.item.included_tests if key in wanted]
    if len(included_keys) < 2:
        included_keys = list(candidate.item.included_tests)[:4]
    included = [_label(candidate, key) for key in included_keys]
    already: list[ExistingResult] = []
    adds: list[str] = []
    for key in candidate.item.included_tests:
        marker = latest.get(key)
        label = _label(candidate, key)
        has = (
            marker is not None
            and getattr(marker, "value", None) is not None
            and _flag(marker) != MarkerFlag.missing
        )
        if has:
            already.append(
                ExistingResult(
                    key=key,
                    label=label,
                    measured_on=_human_date(getattr(marker, "measured_at", None)),
                )
            )
        elif key in wanted:
            adds.append(label)
    already.sort(key=lambda item: 0 if item.key in wanted else 1)
    already = already[:4]
    if relevance == PackageRelevance.not_recommended_now:
        adds = []
        timing = "Recent results already cover the relevant measurements."
    elif already and adds:
        timing = "Some included tests already appear in your reports; others would add new information."
    elif already:
        timing = "These measurements are already in your recent reports."
    else:
        timing = "These measurements are not in your current reports."
    return PackageComparison(
        included=included,
        already_have=already,
        adds_information=list(dict.fromkeys(adds))[:4],
        timing_note=timing,
        recently_available=[item.label for item in already],
        missing=list(dict.fromkeys(adds))[:4],
        stale=[],
        new_information=list(dict.fromkeys(adds))[:4],
    )


def build_recommendation(
    *,
    candidate: PackageCandidate,
    relevance: PackageRelevance,
    context: HealthContext,
    gaps: list[HealthGap],
    requested: list[str],
    explicit: bool,
) -> TestingOption:
    name = candidate.item.display_name
    headline = _HEADLINES[relevance]
    if explicit and relevance == PackageRelevance.optional:
        headline = "A SuperShyft option that includes this"
    reason = _personalized_reason(
        context=context,
        gaps=gaps,
        candidate=candidate,
        relevance=relevance,
        explicit=explicit,
        requested=requested,
    )
    if context.personalization and context.personalization.primary_health_goal and relevance in {
        PackageRelevance.high,
        PackageRelevance.moderate,
    }:
        goal = context.personalization.primary_health_goal.replace("_", " ")
        reason = f"{reason} This is more relevant because your current goal is {goal}."
    comparison = _comparison(
        context=context,
        candidate=candidate,
        requested=requested,
        relevance=relevance,
    )
    relevant = list(
        dict.fromkeys(
            [
                *comparison.adds_information,
                *[item.label for item in comparison.already_have],
                *comparison.included,
            ]
        )
    )[:4]
    if len(relevant) < 2:
        relevant = (comparison.included or relevant)[:4]
    already_recent = [item.label for item in comparison.already_have]
    view = PackageAction(
        type=PackageActionType.open_package,
        label=f"View {name}",
        package_id=candidate.item.catalog_id,
        catalog_kind=candidate.item.kind,
    )
    compare = PackageAction(
        type=PackageActionType.compare_with_existing,
        label="Check what I already have",
        package_id=candidate.item.catalog_id,
        catalog_kind=candidate.item.kind,
    )
    if relevance == PackageRelevance.not_recommended_now:
        primary, secondary = compare, view
    elif comparison.already_have:
        primary, secondary = view, compare
    else:
        primary, secondary = view, None
    return TestingOption(
        type="package_recommendation",
        relevance=relevance,
        headline=headline,
        package=CatalogPackageRef(
            id=candidate.item.catalog_id,
            name=name,
            kind=candidate.item.kind,
        ),
        reason=reason,
        helps_answer=_helps_answer(gaps, relevance, explicit),
        relevant_tests=relevant,
        already_recent=already_recent,
        primary_action=primary,
        secondary_action=secondary,
        comparison=comparison,
        catalog_id=candidate.item.catalog_id,
        kind=candidate.item.kind,
        display_name=name,
        provider=candidate.item.provider,
        included_matched_tests=list(candidate.coverage.matched_entities),
        included_matched_labels=relevant,
        price=candidate.item.price,
        currency=candidate.item.currency,
        medical_rationale=reason,
        match_reason=reason,
        cta_label=primary.label,
        invitation=headline,
    )


def _candidate_trace(candidate: PackageCandidate) -> dict:
    return {
        "catalog_id": candidate.item.catalog_id,
        "name": candidate.item.display_name,
        "kind": candidate.item.kind.value,
        "status": candidate.item.status,
        "price": candidate.item.price,
        "covered": candidate.coverage.matched_entities,
        "missing": candidate.coverage.missing_entities,
        "coverage_score": candidate.coverage.coverage_score,
        "available": candidate.available,
    }


class TestingOptionService:
    def __init__(
        self,
        matcher: PackageMatcher | None = None,
        detector: HealthGapDetector | None = None,
        needs: TestNeedGenerator | None = None,
        policy: PackageRecommendationPolicy | None = None,
    ):
        self.detector = detector or HealthGapDetector()
        self.needs = needs or TestNeedGenerator()
        self.matcher = matcher or PackageMatcher()
        self.policy = policy or PackageRecommendationPolicy()

    def evaluate(
        self,
        *,
        message: str,
        context: HealthContext,
        plan: QueryPlan | None = None,
        conversation_state: ConversationState | None = None,
        package_suggestion_allowed: bool = True,
    ) -> tuple[TestingOption | None, DiagnosticsTrace, TestNeed]:
        explicit = is_explicit_catalog_lookup(message)
        gaps = self.detector.detect(
            message=message,
            context=context,
            plan=plan,
            conversation_state=conversation_state,
        )
        test_need = self.needs.generate(gaps, explicit_catalog_lookup=explicit)
        requested = list(test_need.recommended_test_entities)
        mentioned = match_lab_keys(message) or panel_member_keys(message) or (
            [primary_lab_key(message)] if primary_lab_key(message) else []
        )
        if not mentioned and conversation_state:
            mentioned = [key for key in conversation_state.active_entities if key]
        if explicit and mentioned:
            requested = list(dict.fromkeys([*mentioned, *requested]))
            if test_need.testing_relevance == TestingRelevance.none:
                test_need = test_need.model_copy(
                    update={
                        "recommended_test_entities": requested,
                        "testing_relevance": TestingRelevance.none,
                        "reason": "Named-test lookup.",
                    }
                )
        recent_adequate = wants_another_test(message) and (
            test_need.testing_relevance in {TestingRelevance.none, TestingRelevance.optional}
            or (
                bool(gaps)
                and all(gap.gap_type == HealthGapType.goal_tracking_data_insufficient for gap in gaps)
            )
        )
        lookup_keys = list(requested)
        if recent_adequate and not lookup_keys:
            lookup_keys = list(
                dict.fromkeys(
                    mentioned
                    + list(getattr(plan, "requested_metrics", None) or [])
                    + list(getattr(context, "requested_entity_codes", None) or [])
                )
            )
        lookup = self.matcher.match(lookup_keys) if lookup_keys else []
        candidate = lookup[0] if lookup else None
        decision = self.policy.decide(
            test_need=test_need,
            candidate=candidate,
            package_suggestion_allowed=package_suggestion_allowed,
            explicit_catalog_lookup=explicit,
            recent_adequate=recent_adequate,
            conversation_state=conversation_state,
        )
        option: TestingOption | None = None
        if decision.allowed and candidate is not None and decision.relevance is not None:
            option = build_recommendation(
                candidate=candidate,
                relevance=decision.relevance,
                context=context,
                gaps=gaps,
                requested=lookup_keys or requested,
                explicit=explicit,
            )
        elif lookup_keys and not lookup and (explicit or test_need.testing_relevance == TestingRelevance.useful):
            logger.info("PACKAGE LOOKUP no_match requested=%s", lookup_keys)
        trace = DiagnosticsTrace(
            gaps=[gap.model_dump(mode="json") for gap in gaps],
            test_need=test_need.model_dump(mode="json"),
            package_lookup=[_candidate_trace(item) for item in lookup[:8]],
            policy_allowed=decision.allowed,
            policy_reason=decision.reason,
            package_suggestion_allowed=package_suggestion_allowed,
            relevance=decision.relevance.value if decision.relevance else None,
            surfaced=(
                {
                    "catalog_id": option.catalog_id,
                    "display_name": option.display_name,
                    "reason": decision.reason,
                    "relevance": option.relevance.value,
                }
                if option
                else None
            ),
        )
        self._log(trace, lookup_keys or requested)
        return option, trace, test_need

    def _log(self, trace: DiagnosticsTrace, requested: list[str]) -> None:
        if not settings.is_development:
            return
        for gap in trace.gaps:
            logger.info(
                "HEALTH GAP type=%s domain=%s missing=%s stale=%s supporting=%s",
                gap.get("gap_type"),
                gap.get("domain"),
                gap.get("missing_entities"),
                gap.get("stale_entities"),
                gap.get("supporting_entities"),
            )
        need = trace.test_need or {}
        logger.info(
            "TEST NEED tests=%s relevance=%s urgency=%s rationale=%s",
            need.get("recommended_test_entities") or requested,
            need.get("testing_relevance"),
            need.get("urgency"),
            (need.get("reason") or "")[:180],
        )
        for row in trace.package_lookup:
            logger.info(
                "PACKAGE LOOKUP id=%s name=%s covered=%s missing=%s available=%s score=%s",
                row.get("catalog_id"),
                row.get("name"),
                row.get("covered"),
                row.get("missing"),
                row.get("available"),
                row.get("coverage_score"),
            )
        logger.info(
            "RECOMMENDATION POLICY allowed=%s reason=%s relevance=%s",
            trace.policy_allowed,
            trace.policy_reason,
            trace.relevance,
        )
        if trace.surfaced:
            logger.info(
                "FINAL SURFACED PACKAGE id=%s name=%s reason=%s relevance=%s",
                trace.surfaced.get("catalog_id"),
                trace.surfaced.get("display_name"),
                trace.surfaced.get("reason"),
                trace.surfaced.get("relevance"),
            )
        else:
            logger.info("FINAL SURFACED PACKAGE none")
