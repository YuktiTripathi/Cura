"""When a SuperShyft catalog item may be shown. Never promotional."""

from __future__ import annotations

from dataclasses import dataclass

from app.contracts.conversation_state import ConversationState
from app.contracts.diagnostics import (
    HealthGapType,
    PackageCandidate,
    PackageRelevance,
    TestNeed,
    TestingRelevance,
)


@dataclass
class PolicyDecision:
    allowed: bool
    reason: str
    relevance: PackageRelevance | None = None


class PackageRecommendationPolicy:
    def decide(
        self,
        *,
        test_need: TestNeed,
        candidate: PackageCandidate | None,
        package_suggestion_allowed: bool,
        explicit_catalog_lookup: bool,
        recent_adequate: bool,
        conversation_state: ConversationState | None = None,
    ) -> PolicyDecision:
        if not package_suggestion_allowed:
            return PolicyDecision(False, "acute_or_emergency_symptoms")
        last_id = getattr(conversation_state, "last_surfaced_catalog_id", None) if conversation_state else None
        if candidate and last_id and last_id == candidate.item.catalog_id and not explicit_catalog_lookup:
            return PolicyDecision(False, "already_surfaced_in_topic")
        if recent_adequate and not explicit_catalog_lookup:
            if candidate is None:
                return PolicyDecision(False, "recent_adequate_testing")
            return PolicyDecision(True, "recent_adequate_testing", PackageRelevance.not_recommended_now)
        if candidate is None:
            return PolicyDecision(False, "no_catalog_match")
        if not candidate.available:
            return PolicyDecision(False, "catalog_item_unavailable")
        if (candidate.item.status or "").lower() not in {"active", "available", ""}:
            return PolicyDecision(False, "inactive_catalog_item")
        if explicit_catalog_lookup:
            return PolicyDecision(True, "explicit_catalog_question", PackageRelevance.optional)
        if test_need.testing_relevance == TestingRelevance.none:
            return PolicyDecision(False, "no_medical_testing_need")
        if test_need.testing_relevance == TestingRelevance.optional and candidate.coverage.coverage_score < 1.0:
            return PolicyDecision(False, "optional_need_incomplete_coverage")
        if test_need.testing_relevance == TestingRelevance.useful:
            if candidate.coverage.matched < 1:
                return PolicyDecision(False, "unrelated_to_information_gap")
            moderate = {
                HealthGapType.stale_relevant_data,
                HealthGapType.previous_abnormality_needs_follow_up,
            }
            relevance = (
                PackageRelevance.moderate
                if test_need.lead_gap_type in moderate
                else PackageRelevance.high
            )
            return PolicyDecision(True, "covers_identified_information_gap", relevance)
        if test_need.testing_relevance == TestingRelevance.optional:
            if candidate.coverage.matched < 1:
                return PolicyDecision(False, "unrelated_to_information_gap")
            return PolicyDecision(True, "covers_identified_information_gap", PackageRelevance.optional)
        if test_need.testing_relevance == TestingRelevance.clinician_led:
            return PolicyDecision(False, "clinician_led_testing")
        return PolicyDecision(False, "not_health_driven")
