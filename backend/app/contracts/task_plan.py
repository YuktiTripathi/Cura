"""Compositional task plan. One request may have many entities, sources, and operations."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from app.contracts.common import AnswerComplexity, AnswerModelTier, ReasoningDepth


class QuestionType(str, Enum):
    general_education = "general_education"
    personal_lookup = "personal_lookup"
    personal_health_reasoning = "personal_health_reasoning"
    safety = "safety"


class TaskOperation(str, Enum):
    retrieve = "RETRIEVE"
    explain = "EXPLAIN"
    interpret = "INTERPRET"
    update_context = "UPDATE_CONTEXT"
    continue_interpretation = "CONTINUE_INTERPRETATION"
    compare = "COMPARE"
    trend = "TREND"
    group = "GROUP"
    summarize = "SUMMARIZE"
    correlate = "CORRELATE"
    prioritize = "PRIORITIZE"
    identify_gaps = "IDENTIFY_GAPS"
    identify_pattern = "IDENTIFY_PATTERN"
    verify_premise = "VERIFY_PREMISE"
    recommend = "RECOMMEND"
    escalate = "ESCALATE"
    provenance = "PROVENANCE"
    assess_goal_progress = "ASSESS_GOAL_PROGRESS"
    prepare_clinician_discussion = "PREPARE_CLINICIAN_DISCUSSION"
    document_structured_lookup = "DOCUMENT_STRUCTURED_LOOKUP"
    document_narrative_retrieval = "DOCUMENT_NARRATIVE_RETRIEVAL"
    document_summary = "DOCUMENT_SUMMARY"
    document_cross_source_compare = "DOCUMENT_CROSS_SOURCE_COMPARE"


class EntityKind(str, Enum):
    biomarker = "BIOMARKER"
    health_domain = "HEALTH_DOMAIN"
    lifestyle_factor = "LIFESTYLE_FACTOR"
    symptom = "SYMPTOM"
    condition = "CONDITION"
    goal = "GOAL"
    risk_assessment = "RISK_ASSESSMENT"
    document = "DOCUMENT"
    profile_attribute = "PROFILE_ATTRIBUTE"
    user_stated_fact = "USER_STATED_FACT"
    temporal_reference = "TEMPORAL_REFERENCE"


class TaskSelector(str, Enum):
    all = "ALL"
    latest = "LATEST"
    historical = "HISTORICAL"
    high = "HIGH"
    low = "LOW"
    abnormal = "ABNORMAL"
    normal = "NORMAL"
    missing = "MISSING"
    changed = "CHANGED"
    improved = "IMPROVED"
    worsened = "WORSENED"
    related = "RELATED"
    relevant_to_goal = "RELEVANT_TO_GOAL"


class TaskEntity(BaseModel):
    code: str
    source: str = "blood"
    kind: EntityKind = EntityKind.biomarker
    optional: bool = False
    stated_value: float | str | None = None
    stated_unit: str | None = None
    stated: bool = False


class TaskPlan(BaseModel):
    question_type: QuestionType = QuestionType.general_education
    domains: list[str] = Field(default_factory=list)
    entities: list[TaskEntity] = Field(default_factory=list)
    selectors: list[TaskSelector] = Field(default_factory=list)
    operations: list[TaskOperation] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    time_scope: str = "latest"
    history_required: bool = False
    medical_evidence_required: bool = False
    requires_personal_data: bool = False
    personalization_dimensions: list[str] = Field(default_factory=list)
    premise_claim: str | None = None
    user_stated: list[TaskEntity] = Field(default_factory=list)
    raw_message: str = ""
    display_entities: list[str] = Field(default_factory=list)
    reasoning_context: list[str] = Field(default_factory=list)
    response_mode: str | None = None
    complexity: AnswerComplexity | None = None
    reasoning_depth: ReasoningDepth | None = None
    model_tier: AnswerModelTier | None = None

    def entity_codes(self) -> list[str]:
        return list(dict.fromkeys(item.code for item in self.entities if item.code))

    def operation_values(self) -> list[str]:
        return [item.value for item in self.operations]

    def needs_reasoning(self) -> bool:
        if self.question_type == QuestionType.general_education:
            return True
        if self.question_type == QuestionType.safety:
            return False
        reasoning_ops = {
            TaskOperation.explain,
            TaskOperation.interpret,
            TaskOperation.compare,
            TaskOperation.trend,
            TaskOperation.summarize,
            TaskOperation.correlate,
            TaskOperation.group,
            TaskOperation.prioritize,
            TaskOperation.identify_gaps,
            TaskOperation.identify_pattern,
            TaskOperation.verify_premise,
            TaskOperation.recommend,
            TaskOperation.update_context,
            TaskOperation.continue_interpretation,
            TaskOperation.document_narrative_retrieval,
            TaskOperation.document_summary,
            TaskOperation.document_cross_source_compare,
        }
        if any(op in reasoning_ops for op in self.operations):
            return True
        return False

    def lookup_only(self) -> bool:
        ops = set(self.operations)
        reasoning = {
            TaskOperation.explain,
            TaskOperation.interpret,
            TaskOperation.compare,
            TaskOperation.trend,
            TaskOperation.group,
            TaskOperation.summarize,
            TaskOperation.correlate,
            TaskOperation.prioritize,
            TaskOperation.identify_gaps,
            TaskOperation.identify_pattern,
            TaskOperation.verify_premise,
            TaskOperation.recommend,
            TaskOperation.update_context,
            TaskOperation.continue_interpretation,
            TaskOperation.document_narrative_retrieval,
            TaskOperation.document_summary,
            TaskOperation.document_cross_source_compare,
        }
        return not (ops & reasoning)
