"""Turn health gaps into a provider-independent test need. No catalog lookup."""

from __future__ import annotations

from app.contracts.diagnostics import (
    HealthGap,
    HealthGapType,
    TestNeed,
    TestingRelevance,
    TestingUrgency,
)
from app.pipeline.lab_parameters import display_name_for

_PRIORITY = (
    HealthGapType.relevant_test_missing,
    HealthGapType.previous_abnormality_needs_follow_up,
    HealthGapType.stale_relevant_data,
    HealthGapType.user_explicitly_asks_what_to_test,
    HealthGapType.goal_tracking_data_insufficient,
    HealthGapType.domain_assessment_incomplete,
)


class TestNeedGenerator:
    def generate(self, gaps: list[HealthGap], *, explicit_catalog_lookup: bool = False) -> TestNeed:
        if explicit_catalog_lookup and not gaps:
            return TestNeed(testing_relevance=TestingRelevance.none, urgency=TestingUrgency.none)
        if not gaps:
            return TestNeed(testing_relevance=TestingRelevance.none, urgency=TestingUrgency.none)

        ranked = sorted(gaps, key=lambda gap: _PRIORITY.index(gap.gap_type) if gap.gap_type in _PRIORITY else 99)
        entities: list[str] = []
        for gap in ranked:
            for key in [*gap.missing_entities, *gap.stale_entities]:
                if key not in entities:
                    entities.append(key)
        if not entities:
            return TestNeed(testing_relevance=TestingRelevance.none, reason="", urgency=TestingUrgency.none)

        lead = ranked[0]
        useful_types = {
            HealthGapType.relevant_test_missing,
            HealthGapType.previous_abnormality_needs_follow_up,
            HealthGapType.stale_relevant_data,
            HealthGapType.user_explicitly_asks_what_to_test,
            HealthGapType.goal_tracking_data_insufficient,
        }
        relevance = TestingRelevance.useful if lead.gap_type in useful_types else TestingRelevance.optional
        names = ", ".join(display_name_for(key) for key in entities[:4])
        rationale = lead.reason
        if lead.gap_type == HealthGapType.relevant_test_missing:
            rationale = lead.reason
        elif lead.gap_type in {
            HealthGapType.previous_abnormality_needs_follow_up,
            HealthGapType.stale_relevant_data,
        }:
            when = f" from {lead.last_measured_on}" if lead.last_measured_on else ""
            rationale = (
                f"The latest measurement{when} cannot answer whether this has changed since then. "
                f"An updated {names} measurement would allow a direct comparison."
            )
        return TestNeed(
            recommended_test_entities=entities[:6],
            reason=rationale,
            urgency=TestingUrgency.routine,
            testing_relevance=relevance,
            medical_rationale=rationale,
            lead_gap_type=lead.gap_type,
        )
