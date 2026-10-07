from pydantic import BaseModel, Field

from app.contracts.common import (
    AnswerComplexity,
    AnswerDepth,
    HealthSourceType,
    IntentType,
    KnowledgeScope,
    QuerySource,
    AnswerModelTier,
    ReasoningDepth,
)


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
    needs_questionnaire: bool = False
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
    sources: list[HealthSourceType] = Field(default_factory=list)
    document_ids: list[str] = Field(default_factory=list)
    active_document_id: str | None = None
    complexity: AnswerComplexity | None = None
    answer_model_tier: AnswerModelTier | None = None
    model_tier: AnswerModelTier | None = None
    reasoning_depth: ReasoningDepth | None = None
    model_selection_reasons: list[str] = Field(default_factory=list)
    reasoning_required: bool = False
    pdf_analysis_required: bool = False
    operation: str = "LOOKUP"
    operations: list[str] = Field(default_factory=list)
    question_type: str | None = None
    requested_category: str | None = None
    requested_count: int | None = None
    premise_claim: str | None = None
    domains: list[str] = Field(default_factory=list)
    selectors: list[str] = Field(default_factory=list)
    optional_entities: list[str] = Field(default_factory=list)
    display_entities: list[str] = Field(default_factory=list)
    reasoning_context: list[str] = Field(default_factory=list)
    response_mode: str | None = None
    operations_hint: list[str] = Field(default_factory=list)
    conversation_entities: list[str] = Field(default_factory=list)
    conversation_turn: str | None = None
    # True when the semantic evidence planner scoped the sources; providers then fetch
    # only the flagged sources instead of their broad defaults.
    semantic_scoped: bool = False

    @property
    def personal_data_required(self) -> bool:
        return self.needs_personal_data

    @property
    def needs_document_data(self) -> bool:
        return bool(self.needs_user_uploaded or HealthSourceType.uploaded_document in self.sources)

    @property
    def needs_medical_knowledge(self) -> bool:
        return bool(
            self.needs_general
            or self.medical_evidence_required
            or HealthSourceType.medical_knowledge in self.sources
        )

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
            or             self.needs_goals
            or self.needs_questionnaire
        )
