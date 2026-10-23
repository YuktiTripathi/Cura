"""Provider-independent health information gaps. Does not look at commercial packages."""

from __future__ import annotations

import re
from datetime import date

from app.contracts.common import MarkerFlag
from app.contracts.conversation_state import ConversationState
from app.contracts.diagnostics import HealthGap, HealthGapType
from app.contracts.health_context import HealthContext
from app.contracts.query import QueryPlan
from app.pipeline.health_domains import DOMAIN_CODES, domain_for_code
from app.pipeline.lab_parameters import display_name_for, is_lab_key, match_lab_keys, related_keys
from app.pipeline.personal_selection import coerce_marker_date, latest_context_markers, marker_flag

_ABNORMAL = {MarkerFlag.low, MarkerFlag.high, MarkerFlag.critical}
_EXPLICIT_TEST = re.compile(
    r"\b(what (?:should|could|can) i (?:test|get tested)|which tests? (?:should|would|do i)|"
    r"what (?:labs?|investigations?) (?:should|would)|should i (?:get )?tested|"
    r"do i need (?:another |a )?(?:test|panel|package)|"
    r"which (?:supershyft )?package|package includes|"
    r"can i get (?:this|that|it) through supershyft)\b",
    re.I,
)
_COMPARISON = re.compile(
    r"\b(improv(?:ed|e|ing)|gotten better|come down|gone up|changed|"
    r"current(?:ly)?|now|still (?:low|high|abnormal)|has (?:my|it))\b",
    re.I,
)
_GOAL_LANG = re.compile(r"\b(goal|progress|track(?:ing)?|target)\b", re.I)
_IRON_PATTERN_KEYS = ("hemoglobin", "mcv", "mch", "iron")
_IRON_MISSING = ("ferritin", "transferrin")


def _available_keys(latest: dict[str, object]) -> set[str]:
    out: set[str] = set()
    for key, marker in latest.items():
        if getattr(marker, "value", None) is not None and marker_flag(marker) != MarkerFlag.missing:
            out.add(key)
    return out


def _abnormal_keys(latest: dict[str, object]) -> set[str]:
    return {key for key, marker in latest.items() if marker_flag(marker) in _ABNORMAL}


def _domains(plan: QueryPlan | None, context: HealthContext, state: ConversationState | None) -> list[str]:
    codes: list[str] = []
    for item in list(getattr(context, "domains", None) or []) + list(getattr(plan, "domains", None) or []):
        if item and item not in codes:
            codes.append(item)
    if state and state.active_domain and state.active_domain not in codes:
        codes.append(state.active_domain)
    return codes


def _explicit_test_question(message: str) -> bool:
    return bool(_EXPLICIT_TEST.search(message or ""))


def _comparison_question(message: str) -> bool:
    return bool(_COMPARISON.search(message or ""))


class HealthGapDetector:
    def detect(
        self,
        *,
        message: str,
        context: HealthContext,
        plan: QueryPlan | None = None,
        conversation_state: ConversationState | None = None,
        _today: date | None = None,
    ) -> list[HealthGap]:
        latest = latest_context_markers(context)
        available = _available_keys(latest)
        abnormal = _abnormal_keys(latest)
        gaps: list[HealthGap] = []
        domains = _domains(plan, context, conversation_state)
        requested = [
            item
            for item in (
                list(getattr(context, "requested_entity_codes", None) or [])
                + list(getattr(plan, "requested_metrics", None) or [])
                + list(getattr(conversation_state, "active_entities", None) or [])
            )
            if is_lab_key(item)
        ]

        iron_support = [key for key in _IRON_PATTERN_KEYS if key in abnormal]
        if iron_support:
            missing_iron = [key for key in _IRON_MISSING if key not in available]
            if "ferritin" in missing_iron:
                gaps.append(
                    HealthGap(
                        gap_type=HealthGapType.relevant_test_missing,
                        domain="iron_status",
                        missing_entities=["ferritin"],
                        supporting_entities=iron_support,
                        reason=(
                            "Ferritin would provide information about iron stores and would help "
                            "interpret the current red-cell/iron pattern."
                        ),
                    )
                )
            if "transferrin" in missing_iron and "iron" in available:
                gaps.append(
                    HealthGap(
                        gap_type=HealthGapType.relevant_test_missing,
                        domain="iron_status",
                        missing_entities=["transferrin"],
                        supporting_entities=iron_support,
                        reason=(
                            "Transferrin saturation would help interpret how much of the available "
                            "iron-binding capacity is being used."
                        ),
                    )
                )

        comparison_keys = [
            key
            for key in dict.fromkeys(
                requested
                + [item for item in match_lab_keys(message) if is_lab_key(item)]
                + list(getattr(conversation_state, "active_entities", None) or [])
            )
            if is_lab_key(key)
        ]
        if _comparison_question(message) and comparison_keys:
            for key in comparison_keys:
                marker = latest.get(key)
                measured = coerce_marker_date(getattr(marker, "measured_at", None)) if marker is not None else None
                if measured is None:
                    for row in context.comparisons or []:
                        if getattr(row, "topic", None) == key:
                            measured = coerce_marker_date(
                                getattr(row, "current_date", None) or getattr(row, "previous_date", None)
                            )
                            break
                if marker is None and measured is None:
                    continue
                flag = marker_flag(marker) if marker is not None else MarkerFlag.unknown
                when = measured.isoformat() if measured else None
                gaps.append(
                    HealthGap(
                        gap_type=(
                            HealthGapType.previous_abnormality_needs_follow_up
                            if flag in _ABNORMAL
                            else HealthGapType.stale_relevant_data
                        ),
                        domain=next(iter(domains), None),
                        stale_entities=[key],
                        supporting_entities=[key],
                        last_measured_on=when,
                        reason=(
                            f"The most recent {display_name_for(key)} result"
                            + (f" is from {when}" if when else "")
                            + ", so a newer measurement would be needed to tell whether this has changed since then."
                        ),
                    )
                )

        if _explicit_test_question(message):
            for code in domains or ["overall_health"]:
                domain = domain_for_code(code) if code in DOMAIN_CODES else None
                primaries = list(domain.primary_entities) if domain else list(requested)
                missing = [key for key in primaries if is_lab_key(key) and key not in available]
                if missing:
                    gaps.append(
                        HealthGap(
                            gap_type=HealthGapType.user_explicitly_asks_what_to_test,
                            domain=code,
                            missing_entities=missing,
                            supporting_entities=[key for key in primaries if key in available],
                            reason="The question asks which tests would add information for this topic.",
                        )
                    )

        for code in domains:
            domain = domain_for_code(code)
            if domain is None:
                continue
            primaries = [key for key in domain.primary_entities if is_lab_key(key)]
            if not primaries:
                continue
            missing = [key for key in primaries if key not in available]
            present = [key for key in primaries if key in available]
            if missing and present and not any(gap.domain == code and gap.missing_entities == missing for gap in gaps):
                if code in {"iron_status", "red_cell_anaemia_health"} and "ferritin" in missing:
                    continue
                gaps.append(
                    HealthGap(
                        gap_type=HealthGapType.domain_assessment_incomplete,
                        domain=code,
                        missing_entities=missing[:4],
                        supporting_entities=present,
                        reason=f"Some {domain.code.replace('_', ' ')} measurements that usually travel together are not in the available reports.",
                    )
                )

        goals = list(getattr(context, "goals", None) or [])
        if goals and requested and _GOAL_LANG.search(message or ""):
            for key in requested:
                if key in available:
                    continue
                if related_keys(key) & available:
                    continue
                gaps.append(
                    HealthGap(
                        gap_type=HealthGapType.goal_tracking_data_insufficient,
                        domain=next(iter(domains), None),
                        missing_entities=[key],
                        reason=f"{display_name_for(key)} is needed to compare against the current health goal.",
                    )
                )

        unique: list[HealthGap] = []
        seen: set[tuple] = set()
        for gap in gaps:
            token = (gap.gap_type.value, gap.domain, tuple(gap.missing_entities), tuple(gap.stale_entities))
            if token in seen:
                continue
            seen.add(token)
            unique.append(gap)
        return unique
