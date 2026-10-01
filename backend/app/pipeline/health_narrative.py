"""Health narrative summaries. Presentation only; does not change retrieval."""

from __future__ import annotations

from app.contracts.health_context import HealthContext
from app.contracts.presentation import HealthTheme, PresentedFinding
from app.contracts.query import QueryPlan
from app.pipeline.narrative import (
    build_narrative_summary,
    summary_style_for,
    wants_narrative_summary,
    wants_raw_snapshot,
)


class HealthNarrativeService:
    """Formal entry point for 'how am I doing' / 'what should I focus on' reviews."""

    def applies(self, message: str | None, plan: QueryPlan | None = None) -> bool:
        return wants_narrative_summary(message, plan)

    def wants_raw_table(self, message: str | None, plan: QueryPlan | None = None) -> bool:
        return wants_raw_snapshot(message, plan)

    def summary_style(self, message: str | None, plan: QueryPlan | None = None):
        return summary_style_for(message, plan)

    def build(
        self,
        context: HealthContext,
        *,
        plan: QueryPlan | None = None,
        message: str | None = None,
        llm_overall: str | None = None,
        llm_themes: list[dict] | None = None,
    ) -> tuple[str, list[HealthTheme], list[PresentedFinding], str | None]:
        return build_narrative_summary(
            context,
            plan=plan,
            message=message,
            llm_overall=llm_overall,
            llm_themes=llm_themes,
        )
