from pydantic import BaseModel, Field

from app.contracts.common import AnswerDepth, IntentType, KnowledgeScope, QuerySource


class QueryPlan(BaseModel):
    intent: IntentType
    source: QuerySource = QuerySource.none
    knowledge_scope: KnowledgeScope = KnowledgeScope.general
    topic: str | None = None
    topic_name: str | None = None
    history: bool = False
    reports: str = "relevant"
    report_id: str | None = None
    answer_depth: AnswerDepth = AnswerDepth.simple
    needs_blood: bool = False
    needs_bio_ai: bool = False
    needs_lifestyle: bool = False
    needs_profile: bool = False
    needs_goals: bool = False
    needs_user_uploaded: bool = False
    needs_supershyft: bool = False
    needs_general: bool = False
    needs_cross_source: bool = False
    compare: bool = False
    time_scope: str = "none"
    follow_up: bool = False
    raw_message: str = ""
    explicit_source_ref: bool = False
    personal_reference: bool = False
    medical_evidence_required: bool = False
    data_sources: list[str] = Field(default_factory=list)
    requested_metrics: list[str] = Field(default_factory=list)
    time_operation: str = "latest_marker"
    needs_guidance: bool = False
    fallback_reason: str | None = None

    @property
    def personal_data_required(self) -> bool:
        return self.needs_personal_data

    @property
    def needs_personal_data(self) -> bool:
        if self.needs_supershyft:
            return True
        if self.knowledge_scope == KnowledgeScope.general:
            return False
        return bool(
            self.needs_blood
            or self.needs_bio_ai
            or self.needs_lifestyle
            or self.needs_profile
            or self.needs_goals
        )
