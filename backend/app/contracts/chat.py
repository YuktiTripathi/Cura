from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.contracts.diagnostics import TestingOption
from app.contracts.evidence import EvidenceRecord
from app.contracts.followup import FollowUpSuggestion
from app.contracts.context_ref import ContextRef
from app.contracts.operations import SourceOutcome
from app.contracts.presentation import StructuredResponse
from app.contracts.turn_experience import TurnExperience
from app.contracts.recommendation import ApprovedRecommendation


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str
    conversation_id: str | None = None
    language: str | None = None
    language_mode: str = "auto"
    document_ids: list[str] = Field(default_factory=list)
    context_ref: ContextRef | None = None

    @model_validator(mode="before")
    @classmethod
    def ignore_client_identity(cls, data):
        from app.auth.identity import drop_client_identity

        return drop_client_identity(data)


class FollowUp(FollowUpSuggestion):
    prompt: str | None = None


class ChatMeta(BaseModel):
    intent: str | None = None
    answer_depth: str | None = None
    status: str = "ok"
    llm_mode: str = "disabled"
    request_id: str | None = None
    detected_language: str | None = None
    response_language: str | None = None
    language_mode: str | None = None
    sources_used: list[str] = Field(default_factory=list)
    knowledge_scope: str | None = None
    sources_requested: list[str] = Field(default_factory=list)
    llm_called: bool = False
    supershyft_called: bool = False
    document_retrieval_called: bool = False
    db_status: str | None = None
    supershyft_record_count: int | None = None
    safety_flags: list[str] = Field(default_factory=list)
    safety_mode: str | None = None
    recommendation_flags: list[str] = Field(default_factory=list)
    grounding_flags: list[str] = Field(default_factory=list)
    escalation: str | None = None
    model: str | None = None
    provider: str | None = None
    cache_hit: bool = False
    prompt_version: str = "cura-v1"
    input_tokens: int | None = None
    output_tokens: int | None = None
    jev_called: bool = False
    jev_fallback: bool = False
    jev_intent: str | None = None
    jev_source: str | None = None
    jev_operation: str | None = None
    jev_confidence: float | None = None
    jev_validated: bool = False
    jev_overridden: bool = False
    jev_validation_error: str | None = None
    jev_latency_ms: int | None = None
    jev_input_tokens: int | None = None
    jev_output_tokens: int | None = None
    medical_llm_latency_ms: int | None = None
    router: str | None = None
    requires_retrieval: bool | None = None
    requires_personal_data: bool | None = None
    requires_historical_data: bool | None = None
    requires_document_search: bool | None = None
    conversation_context_used: bool | None = None
    fallback_used: bool | None = None
    retrieval_status: str | None = None
    retrieval_used: bool | None = None
    retrieval_sources: list[str] = Field(default_factory=list)
    ihr_queried: bool | None = None
    documents_queried: bool | None = None
    grounding_passed: bool | None = None
    safety_passed: bool | None = None
    jev_complexity: str | None = None
    reasoning_depth: str | None = None
    answer_model_tier: str | None = None
    answer_model: str | None = None
    model_fallback_used: bool | None = None
    estimated_cost_usd: float | None = None
    source_outcomes: list[SourceOutcome] = Field(default_factory=list)
    question_type: str | None = None
    operations: list[str] = Field(default_factory=list)
    requested_entities: list[str] = Field(default_factory=list)
    response_mode: str | None = None
    conversation_goal: str | None = None
    response_depth: str | None = None
    next_conversation_action: str | None = None
    timing: dict | None = None
    debug: dict | None = None
    # Numbers the clients render as call buttons on emergency and self-harm replies.
    emergency_contacts: list[dict[str, str]] = Field(default_factory=list)
    # Short caution prepended for "see a doctor soon" red flags.
    safety_caution: str | None = None


# Fields a production client may see. Model, provider, cost, tokens and routing stay in logs.
PUBLIC_META_FIELDS = frozenset(
    {
        "intent",
        "status",
        "request_id",
        "detected_language",
        "response_language",
        "safety_flags",
        "safety_mode",
        "escalation",
        "emergency_contacts",
        "safety_caution",
        "cache_hit",
    }
)


class EvidenceItem(EvidenceRecord):
    pass


class ProvenanceSource(BaseModel):
    name: str
    url: str | None = None
    source_type: str
    source_id: str | None = None
    occurred_at: str | None = None


class UserProvenance(BaseModel):
    type: str = "none"
    sources: list[ProvenanceSource] = Field(default_factory=list)


class ChatResponse(BaseModel):
    conversation_id: str
    answer: str
    evidence: list[EvidenceItem] = Field(default_factory=list)
    follow_ups: list[FollowUpSuggestion] = Field(default_factory=list)
    recommendations: list[ApprovedRecommendation] = Field(default_factory=list)
    meta: ChatMeta = Field(default_factory=ChatMeta)
    provenance: UserProvenance = Field(default_factory=UserProvenance)
    presentation: StructuredResponse | None = None
    experience: TurnExperience | None = None
    testing_option: TestingOption | None = None


class ConversationSummary(BaseModel):
    id: str
    title: str | None = None
    updated_at: str


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    created_at: str


class ConversationDetail(BaseModel):
    id: str
    title: str | None = None
    messages: list[MessageOut]


class FeedbackRequest(BaseModel):
    conversation_id: str
    message_id: str | None = None
    rating: str
    comment: str | None = None


def public_chat_response(response: ChatResponse) -> ChatResponse:
    """Copy of ``response`` whose meta carries only ``PUBLIC_META_FIELDS``."""
    kept = response.meta.model_dump(include=set(PUBLIC_META_FIELDS))
    return response.model_copy(update={"meta": ChatMeta(**kept)})
