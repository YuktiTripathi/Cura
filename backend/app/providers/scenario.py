from __future__ import annotations

from app.auth.models import AuthenticatedPrincipal
from app.contracts.common import IntentType, KnowledgeScope
from app.contracts.query import QueryPlan
from app.contracts.scenario import ScenarioContext


class CompositeHealthScenarioProvider:
    """Reads canonical DTOs from existing providers; it does not reinterpret raw data."""

    def __init__(self, blood, bio_ai, lifestyle):
        self.blood = blood
        self.bio_ai = bio_ai
        self.lifestyle = lifestyle

    def query(self, principal: AuthenticatedPrincipal, plan: QueryPlan) -> ScenarioContext:
        blood_plan = QueryPlan(
            intent=IntentType.broad_health_summary,
            knowledge_scope=KnowledgeScope.personal,
            needs_blood=True,
            history=True,
        )
        bio_plan = QueryPlan(
            intent=IntentType.bio_ai_score,
            knowledge_scope=KnowledgeScope.personal,
            needs_bio_ai=True,
            history=True,
        )
        lifestyle_plan = QueryPlan(
            intent=IntentType.broad_health_summary,
            knowledge_scope=KnowledgeScope.personal,
            needs_lifestyle=True,
        )
        if plan.semantic_scoped:
            # Narrowed by the evidence planner: read only what can change this answer.
            return ScenarioContext(
                blood_reports=self.blood.query(principal, blood_plan) if plan.needs_blood else [],
                bio_ai_reports=self.bio_ai.query(principal, bio_plan) if plan.needs_bio_ai else [],
                lifestyle=self.lifestyle.query(principal, lifestyle_plan) if (plan.needs_lifestyle or plan.needs_profile) else None,
            )
        return ScenarioContext(
            blood_reports=self.blood.query(principal, blood_plan),
            bio_ai_reports=self.bio_ai.query(principal, bio_plan),
            lifestyle=self.lifestyle.query(principal, lifestyle_plan),
        )

    def available_topics(self, principal: AuthenticatedPrincipal) -> list[str]:
        context = self.query(
            principal,
            QueryPlan(
                intent=IntentType.health_scenario,
                knowledge_scope=KnowledgeScope.personal,
                needs_blood=True,
                needs_bio_ai=True,
                needs_lifestyle=True,
            ),
        )
        topics: list[str] = []
        for report in context.blood_reports:
            topics.extend(marker.key for marker in report.markers)
        for report in context.bio_ai_reports:
            topics.extend(risk.code for risk in report.risks)
        return list(dict.fromkeys(topics))
