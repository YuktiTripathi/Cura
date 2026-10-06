from datetime import date
import hashlib
import json
import logging
import re
import time

from sqlalchemy.orm import Session

from app.auth.models import AuthenticatedPrincipal
from app.contracts.chat import ChatMeta, ChatRequest, ChatResponse, EvidenceItem
from app.contracts.followup import FollowUpSuggestion
from app.contracts.common import IntentType, KnowledgeScope, LanguageCode
from app.contracts.health_context import CrossSourceFinding, CrossSourceValue, HealthContext
from app.core.config import settings
from app.core.copy import (
    casual_reply,
    document_extraction_unavailable,
    document_no_match,
    document_ocr_unavailable,
    document_unread,
    general_knowledge_unavailable,
    personal_data_not_found,
    personal_data_unavailable,
)
from app.retrieval.status import infer_retrieval_status
from app.retrieval.medical import (
    CuratedMedicalKnowledgeProvider,
    render_medical_evidence_answer,
)
from app.pipeline.provenance import build_user_provenance, internal_provenance
from app.documents.lab_answer import evidence_from_value, extract_lab_hits, render_lab_answer
from app.documents.retrieval import DocumentRetriever
from app.documents.service import DocumentService
from app.documents.value_extraction import extract_keys_present, extract_marker_from_text
from app.pipeline.cross_source import (
    CrossSourceComparator,
    compare_uploaded_with_blood,
    extracted_to_source,
    marker_to_source,
    render_comparison,
    render_multi_comparison,
    uploaded_fact_to_source,
)
from app.pipeline.intent import NAMES, is_personal_utterance, requires_personal_record
from app.pipeline.lab_parameters import expand_requested_keys, primary_lab_key, retrieval_keys
from app.pipeline.claim_check import ClaimVerdict, check_claims
from integrations.supershyft.db import DB_NO_RECORDS, DB_PROVIDER_NOT_CALLED
from app.core.errors import LLMUnavailableError, ProviderUnavailableError
from app.db.repositories import ConversationRepository
from app.llm.factory import get_llm_client
from app.llm.registry import estimate_cost_usd, fallback_tiers, model_id_for_tier, provider_for_model, uses_answer_llm
from app.llm.structured import looks_like_structured_json, public_answer_text
from app.memory.conversation import FollowUpMemory
from app.pipeline.conversation_state import ConversationStateResolver, persistable_state
from app.contracts.conversation_state import ExpectedReplyType
from app.pipeline.context_builder import ContextBuilder
from app.pipeline.context_merger import ContextMerger, attach_medical_evidence
from app.pipeline.personalized_followups import PersonalizedFollowUpEngine, build_inventory
from app.pipeline.prompt_builder import PromptBuilder
from app.pipeline.reasoning import ReasoningService
from app.pipeline.validator import ResponseValidator
from app.pipeline.composer import ResponseComposer
from app.pipeline.conversation_experience import build_experience_plan
from app.pipeline.experience_orchestrator import ExperienceOrchestrator
from app.pipeline.micro_insights import compose_micro_insight
from app.pipeline.conversation_title import conversation_title
from app.pipeline.health_sources import has_supershyft_sources, is_lab_source_compare
from app.pipeline.document_context import resolve_attached_documents
from app.pipeline.stages import RouteStage, SafetyStage
from app.pipeline.observability import ProgressEmitter
from app.contracts.presentation import AnswerPreview
from app.contracts.processing import ProcessingStage
from app.pipeline.presentation import preview_findings
from app.pipeline.indic_terms import canonicalize_biomarker_terms
from app.pipeline.renderer import (
    DeterministicRenderer,
    render_bio_ai_ambiguity,
    render_bio_ai_score_list,
    render_diagnosis_restraint,
    render_missing_blood_marker,
    render_provenance,
)
from app.pipeline.safety_messages import emergency_contacts, see_doctor_soon_message
from app.pipeline.safety import (
    SAFETY_ESCALATION_INTENT,
    SafetyLayer,
    conversation_in_safe_mode,
    package_suggestion_allowed,
)
from app.pipeline.testing_option import TestingOptionService
from app.pipeline.grounding import GroundingChecker
from app.pipeline.recommendation_engine import RecommendationEngine
from app.providers.registry import ProviderRegistry
from app.routing.model_tier import promote_for_retrieved_complexity

logger = logging.getLogger("cura.pipeline")


class ChatService:
    def __init__(self, db: Session, registry: ProviderRegistry):
        self.db = db
        self.registry = registry
        self.repo = ConversationRepository(db)
        self.memory = FollowUpMemory()
        self.builder = ContextBuilder(registry)
        self.prompts = PromptBuilder()
        self.renderer = DeterministicRenderer()
        self.reasoner = ReasoningService(self.prompts, self.renderer)
        self.validator = ResponseValidator(grounding=GroundingChecker(), safety=SafetyLayer(), renderer=self.renderer)
        self.composer = ResponseComposer()
        self.medical_knowledge = CuratedMedicalKnowledgeProvider()
        self.safety = SafetyLayer()
        self.grounding = GroundingChecker()
        self.recommendations = RecommendationEngine()
        self.followups = PersonalizedFollowUpEngine()
        self.testing_options = TestingOptionService()
        self.experience_orchestrator = ExperienceOrchestrator()
        self.llm = get_llm_client()
        self._progress = ProgressEmitter()

    def _complete_answer(self, messages, plan, budget=None):
        from app.llm.openrouter_policy import openrouter_policy
        from app.pipeline.dlp import SecurityBlockedError

        policy = openrouter_policy()
        policy.assert_privacy_for_health(personal_health=bool(plan.needs_personal_data))
        last_error = None
        remaining = budget.remaining() if budget is not None else float(settings.llm_timeout_seconds)
        for index, tier in enumerate(fallback_tiers(plan.answer_model_tier)):
            tier_cap = {
                "STANDARD_MEDICAL": 18.0,
                "DEEP_MEDICAL_REASONING": 28.0,
                "FAST_REASONING": 12.0,
            }.get(tier.value, 20.0)
            timeout = min(float(settings.llm_timeout_seconds), remaining, tier_cap)
            if budget is not None:
                timeout = budget.timeout_for(timeout)
            if timeout < 0.5:
                break
            try:
                client = get_llm_client(
                    model_tier=tier.value,
                    timeout=timeout,
                    personal_health=bool(plan.needs_personal_data),
                )
            except LLMUnavailableError:
                last_error = LLMUnavailableError("LLM model is not on the approved allowlist")
                break
            started = time.perf_counter()
            try:
                result = client.complete_structured(messages)
                logger.info(
                    "answer_llm tier=%s model=%s provider=%s fallback=%s latency_ms=%s",
                    tier.value,
                    client.model,
                    client.provider,
                    index > 0,
                    int((time.perf_counter() - started) * 1000),
                )
                return result, client, tier, index > 0
            except SecurityBlockedError as exc:
                logger.warning("answer_llm_blocked_secret_scan")
                raise LLMUnavailableError("LLM request blocked by privacy policy") from exc
            except LLMUnavailableError as exc:
                last_error = exc
                remaining = budget.remaining() if budget is not None else remaining
                logger.warning(
                    "answer_llm_unavailable tier=%s model=%s fallback_reason=%s latency_ms=%s",
                    tier.value,
                    client.model,
                    str(exc),
                    int((time.perf_counter() - started) * 1000),
                )
        raise last_error or LLMUnavailableError("LLM request failed")

    def chat(
        self,
        principal: AuthenticatedPrincipal,
        payload: ChatRequest,
        request_id: str,
        progress: ProgressEmitter | None = None,
    ) -> ChatResponse:
        eval_turn = {"principal": principal, "payload": payload, "request_id": request_id}
        self._progress = progress or ProgressEmitter()
        response = self._execute_chat(principal, payload, request_id, eval_turn)
        return self._record_evaluation(response, eval_turn)

    def _emit_plan_stages(self, plan, *, follow_up: bool) -> None:
        if follow_up:
            self._progress.emit(ProcessingStage.fetching_personal_data, plan=plan)
            return
        if plan.needs_cross_source:
            self._progress.emit(ProcessingStage.fetching_personal_data, plan=plan)
            return
        if plan.needs_user_uploaded and not (plan.needs_blood or plan.needs_bio_ai or plan.needs_supershyft):
            self._progress.emit(ProcessingStage.reading_document, plan=plan)
            return
        if plan.needs_general and not plan.needs_personal_data:
            self._progress.emit(ProcessingStage.checking_medical_evidence, plan=plan)
            return
        if plan.history:
            self._progress.emit(ProcessingStage.fetching_history, plan=plan)
            return
        if plan.needs_blood:
            self._progress.emit(ProcessingStage.fetching_blood_data, plan=plan)
        elif plan.needs_bio_ai:
            self._progress.emit(ProcessingStage.fetching_bioai_data, plan=plan)
        elif plan.needs_questionnaire:
            self._progress.emit(ProcessingStage.fetching_questionnaire, plan=plan)
        elif plan.needs_personal_data:
            self._progress.emit(ProcessingStage.fetching_personal_data, plan=plan)

    def _execute_chat(self, principal: AuthenticatedPrincipal, payload: ChatRequest, request_id: str, eval_turn: dict) -> ChatResponse:
        started = time.perf_counter()
        from app.core.time_budget import TimeBudget

        budget = TimeBudget(settings.request_timeout_seconds)
        eval_turn["budget"] = budget
        self._progress.emit(ProcessingStage.request_received)
        from app.pipeline.dev_trace import trace

        trace("AUTH", authenticated_user_resolved=True, user_id=principal.subject_id)
        # Local safety gate: no Jev, SuperShyft, documents, or LLM until this passes.
        pre_safety = SafetyStage().run(payload.message)
        eval_turn["pre_safety"] = pre_safety
        from app.pipeline.dev_trace import trace

        trace(
            "SAFETY PRECHECK",
            emergency=getattr(pre_safety, "category", None) in {"emergency", "self_harm"},
            medication_risk=getattr(pre_safety, "category", None) == "medication_misuse",
        )
        if pre_safety.blocked:
            if payload.conversation_id:
                conv = self.repo.get_for_subject(payload.conversation_id, principal.subject_id)
            else:
                conv = self.repo.create(principal.subject_id, title=conversation_title(payload.message))
            answer = pre_safety.answer or "I can't help with that request."
            urgent = getattr(pre_safety, "category", None) in {"emergency", "self_harm"}
            block_intent = SAFETY_ESCALATION_INTENT if urgent else "safety_block"
            self.repo.add_message(conv, "user", payload.message, intent=block_intent)
            self.repo.add_message(conv, "assistant", answer, intent=block_intent)
            eval_turn["conv"] = conv
            return ChatResponse(
                conversation_id=conv.id,
                answer=answer,
                evidence=[],
                follow_ups=[],
                meta=ChatMeta(
                    intent="safety_block",
                    status="safety_block",
                    llm_mode="none",
                    request_id=request_id,
                    llm_called=False,
                    supershyft_called=False,
                    document_retrieval_called=False,
                    jev_called=False,
                    safety_flags=pre_safety.flags or [],
                    safety_mode=SafetyLayer.request_safety_mode(pre_safety),
                    escalation=pre_safety.escalation,
                    db_status=DB_PROVIDER_NOT_CALLED,
                    response_language=getattr(pre_safety, "reply_language", None),
                    emergency_contacts=emergency_contacts() if urgent else [],
                ),
            )
        if (
            payload.context_ref
            and payload.context_ref.document_id
            and payload.context_ref.document_id not in payload.document_ids
        ):
            payload = payload.model_copy(
                update={"document_ids": [*payload.document_ids, payload.context_ref.document_id]}
            )
        if payload.conversation_id:
            conv = self.repo.get_for_subject(payload.conversation_id, principal.subject_id)
        else:
            title = conversation_title(payload.message)
            conv = self.repo.create(principal.subject_id, title=title)

        # Biomarker names written in an Indic script ("एलडीएल", "विटामिन डी") → the names routing matches.
        # Only planning sees this; storage, language detection and safety keep the user's own text.
        routing_message = canonicalize_biomarker_terms(payload.message)
        prior_topic, prior_name = self.memory.resolve_topic(conv, routing_message)
        conv_state = ConversationStateResolver().resolve(routing_message, conv)
        eval_turn["conversation_state"] = conv_state
        if not prior_topic and conv_state.active_entities:
            prior_topic = conv_state.active_entities[0]
            prior_name = prior_name or prior_topic.replace("_", " ")
        prior_personal = (
            self.memory.prior_was_personal(conv)
            or conv_state.prior_personal
            or conv_state.turn_type.value != "NEW_QUESTION"
        )
        previous_user_message = self.memory.last_user_message(conv)
        previous_intent = self.memory.last_user_intent(conv)
        conversation_summary = self.memory.semantic_summary(conv)
        doc_svc = DocumentService(self.db)
        listed_docs = doc_svc.list_for_user(principal.subject_id)
        completed_docs = [
            d for d in listed_docs if d.extraction_status == "completed" or d.structured_facts_ready
        ]
        response_lang = LanguageCode.en
        follow_up = conv_state.turn_type.value != "NEW_QUESTION"
        self._progress.follow_up = follow_up
        self._progress.emit(ProcessingStage.planning)
        self._progress.mark("planning")
        routed = RouteStage().run(
            routing_message,
            conversation_summary="",
            previous_user_message=previous_user_message,
            previous_intent=previous_intent,
            follow_up_topic=prior_topic,
            follow_up_name=prior_name,
            prior_personal=prior_personal,
            document_ids=payload.document_ids,
            uploaded_document_count=len(completed_docs),
            prior_source_mode=getattr(conv, "last_source_mode", None),
            context_ref=payload.context_ref,
            conversation_state=conv_state,
        )
        plan, jev_trace = routed.plan, routed.jev_trace
        from app.pipeline.dev_trace import trace

        trace(
            "PLAN",
            sources=list(plan.data_sources or []),
            entities=list(plan.requested_metrics or [])[:12],
            time_scope=plan.time_scope,
        )
        self._progress.measure("planning")
        self._progress.set_context(plan, follow_up=follow_up)
        self._emit_plan_stages(plan, follow_up=follow_up)
        if getattr(pre_safety, "category", None) == "diagnosis_request" and settings.assistant_quality_v2:
            plan.needs_blood = plan.needs_blood or bool(plan.requested_metrics)
            plan.needs_supershyft = plan.needs_personal_data or plan.needs_blood
        if (plan.operation or "").upper() == "PROVENANCE":
            if not plan.topic and getattr(conv, "current_marker_code", None):
                plan.topic = conv.current_marker_code
                plan.topic_name = plan.topic_name or conv.follow_up_topic_name
            plan.needs_blood = plan.needs_blood or True
            plan.needs_supershyft = True
            if (plan.topic or "") in {"cholesterol", "ldl", "hdl", "triglycerides"}:
                plan.requested_metrics = ["ldl", "hdl", "cholesterol", "triglycerides"]

        logger.debug(
            "query_plan request_id=%s intent=%s knowledge_scope=%s needs_personal_data=%s "
            "needs_supershyft=%s needs_user_uploaded=%s needs_general=%s needs_cross_source=%s topic=%s "
            "jev_called=%s jev_fallback=%s jev_intent=%s jev_operation=%s jev_source=%s "
            "jev_validated=%s jev_overridden=%s jev_latency_ms=%s",
            request_id,
            plan.intent.value,
            plan.knowledge_scope.value,
            plan.needs_personal_data,
            plan.needs_supershyft,
            plan.needs_user_uploaded,
            plan.needs_general,
            plan.needs_cross_source,
            plan.topic,
            jev_trace.called,
            jev_trace.fallback,
            jev_trace.decision.intent.value if jev_trace.decision else None,
            jev_trace.decision.operation.value if jev_trace.decision else None,
            jev_trace.decision.source.value if jev_trace.decision else None,
            jev_trace.validated,
            jev_trace.overridden,
            jev_trace.latency_ms,
        )
        eval_turn["conv"] = conv
        eval_turn["plan"] = plan
        eval_turn["jev_trace"] = jev_trace
        eval_turn["medical"] = []

        def _meta(**extra) -> ChatMeta:
            base = dict(
                intent=plan.intent.value,
                answer_depth=plan.answer_depth.value,
                question_type=plan.question_type,
                operations=list(plan.operations or []),
                requested_entities=list(plan.requested_metrics or []),
                request_id=request_id,
                detected_language="en",
                response_language="en",
                language_mode=payload.language_mode or "auto",
                jev_called=jev_trace.called,
                jev_fallback=jev_trace.fallback,
                jev_intent=jev_trace.decision.intent.value if jev_trace.decision else None,
                jev_source=jev_trace.decision.source.value if jev_trace.decision else None,
                jev_operation=jev_trace.decision.operation.value if jev_trace.decision else None,
                jev_confidence=jev_trace.decision.confidence if jev_trace.decision else None,
                jev_validated=jev_trace.validated,
                jev_overridden=jev_trace.overridden,
                jev_validation_error=jev_trace.validation_error,
                jev_latency_ms=jev_trace.latency_ms,
                jev_input_tokens=jev_trace.input_tokens,
                jev_output_tokens=jev_trace.output_tokens,
                router=(
                    "jev_guarded"
                    if jev_trace.called and not jev_trace.fallback and jev_trace.overridden
                    else "jev"
                    if jev_trace.called and not jev_trace.fallback
                    else "deterministic"
                ),
                requires_retrieval=bool(plan.needs_personal_data or plan.needs_user_uploaded),
                requires_personal_data=bool(plan.needs_personal_data),
                requires_historical_data=bool(plan.history),
                requires_document_search=bool(plan.needs_user_uploaded),
                conversation_context_used=bool(previous_user_message or prior_topic),
                fallback_used=bool(jev_trace.fallback),
                jev_complexity=(
                    (jev_trace.decision.complexity.value if jev_trace.decision and jev_trace.decision.complexity else None)
                    or (plan.complexity.value if plan.complexity else None)
                ),
                reasoning_depth=plan.reasoning_depth.value if plan.reasoning_depth else None,
                answer_model_tier=plan.answer_model_tier.value if plan.answer_model_tier else None,
                answer_model=(
                    model_id_for_tier(plan.answer_model_tier)
                    if uses_answer_llm(plan.answer_model_tier)
                    else None
                ),
            )
            base.update(extra)
            if settings.is_development:
                base["debug"] = {
                    "turn_type": conv_state.turn_type.value,
                    "active_topic": (plan.domains[0] if plan.domains else None) or plan.topic or conv_state.active_domain,
                    "active_entities": list(plan.display_entities or conv_state.active_entities or []),
                    "resolved_references": conv_state.resolved_references,
                    "expected_reply_type": conv_state.expected_reply_type.value,
                    "jev_plan": {
                        "intent": jev_trace.decision.intent.value if jev_trace.decision else plan.intent.value,
                        "operation": jev_trace.decision.operation.value if jev_trace.decision else plan.operation,
                        "operations": list(plan.operations or []),
                        "complexity": plan.complexity.value if plan.complexity else None,
                        "reasoning_depth": plan.reasoning_depth.value if plan.reasoning_depth else None,
                        "model_tier": plan.answer_model_tier.value if plan.answer_model_tier else None,
                        "reasons_for_model_selection": list(plan.model_selection_reasons or []),
                    },
                    "retrieval_performed": bool(base.get("retrieval_used") or plan.needs_personal_data or plan.needs_user_uploaded),
                    "reasoner_called": bool(base.get("llm_called")),
                }
            return ChatMeta(**base)

        if plan.intent.value == "ambiguous_clarification":
            metrics = (jev_trace.decision.requested_metrics if jev_trace.decision else None) or [
                "fasting glucose",
                "post-prandial glucose",
                "HbA1c",
            ]
            question = (
                (jev_trace.decision.clarification_question if jev_trace.decision else None)
                or "I can look at "
                + ", ".join(metrics[:-1])
                + f", or {metrics[-1]}. Which would you like me to use?"
            )
            self.repo.add_message(conv, "user", payload.message, intent=plan.intent.value)
            self.repo.add_message(conv, "assistant", question, intent=plan.intent.value)
            return ChatResponse(
                conversation_id=conv.id,
                answer=question,
                evidence=[],
                follow_ups=[],
                meta=_meta(
                    status="clarification_required",
                    llm_mode="none",
                    knowledge_scope=plan.knowledge_scope.value,
                    sources_used=[],
                    llm_called=False,
                    db_status=DB_PROVIDER_NOT_CALLED,
                ),
            )

        if is_lab_source_compare(plan):
            return self._cross_source(
                principal,
                payload,
                conv,
                plan,
                request_id,
                started,
                _meta,
                doc_svc,
                completed_docs,
                response_lang,
                budget=eval_turn.get("budget"),
            )

        attached = resolve_attached_documents(
            explicit_ids=payload.document_ids,
            context_ref=payload.context_ref,
            last_document_id=getattr(conv, "last_document_id", None),
            completed_docs=completed_docs,
        )
        if plan.needs_user_uploaded:
            if attached.status == "ambiguous":
                answer = (
                    "I can compare them. Which uploaded report do you want to compare "
                    "with your latest SuperShyft report?"
                    if plan.needs_cross_source
                    else "I can use your uploaded reports. Which uploaded report would you like me to use?"
                )
                status = "cross_source_ambiguous" if plan.needs_cross_source else "document_ambiguous"
                self.repo.add_message(conv, "user", payload.message, intent=plan.intent.value)
                self.repo.add_message(conv, "assistant", answer, intent=plan.intent.value)
                return ChatResponse(
                    conversation_id=conv.id,
                    answer=answer,
                    evidence=[],
                    follow_ups=[],
                    meta=_meta(
                        status=status,
                        llm_mode="none",
                        sources_used=["user_uploaded"] if not plan.needs_cross_source else [],
                        document_retrieval_called=False,
                        knowledge_scope="user_uploaded" if not plan.needs_cross_source else None,
                    ),
                )
            if attached.status == "missing":
                answer = (
                    "I don't have an uploaded report to compare with SuperShyft."
                    if plan.needs_cross_source
                    else "I don't have an uploaded report to use for this question."
                )
                status = "cross_source_missing_document" if plan.needs_cross_source else "document_missing"
                self.repo.add_message(conv, "user", payload.message, intent=plan.intent.value)
                self.repo.add_message(conv, "assistant", answer, intent=plan.intent.value)
                return ChatResponse(
                    conversation_id=conv.id,
                    answer=answer,
                    evidence=[],
                    follow_ups=[],
                    meta=_meta(status=status, llm_mode="none"),
                )
            plan = plan.model_copy(
                update={
                    "document_ids": attached.document_ids,
                    "active_document_id": attached.active_document_id,
                }
            )
            if plan.document_ids:
                doc_svc.assert_owned(principal.subject_id, plan.document_ids)

        use_docs = bool(plan.needs_user_uploaded and attached.document_ids and not has_supershyft_sources(plan))
        if plan.needs_general and not plan.needs_cross_source and not plan.needs_user_uploaded:
            use_docs = False

        if use_docs:
            self._progress.emit(ProcessingStage.reading_document, plan=plan)
            resolved = list(plan.document_ids or attached.document_ids)
            if not resolved:
                answer = "I don't have an uploaded report to use for this question."
                self.repo.add_message(conv, "user", payload.message, intent=plan.intent.value)
                self.repo.add_message(conv, "assistant", answer, intent=plan.intent.value)
                return ChatResponse(
                    conversation_id=conv.id,
                    answer=answer,
                    evidence=[],
                    follow_ups=[],
                    meta=_meta(status="document_missing", llm_mode="none"),
                )
            docs = doc_svc.assert_owned(principal.subject_id, resolved)
            from app.documents.metadata import load_meta

            pending = [
                d
                for d in docs
                if d.extraction_status in {"not_started", "processing"}
                and not load_meta(d).get("structured_facts_ready")
            ]
            failed = [d for d in docs if d.extraction_status == "failed"]
            if pending:
                answer = document_unread(response_lang)
                status = "document_processing"
            elif failed:
                err = (failed[0].extraction_error or "")
                if "OCR" in err:
                    answer = document_ocr_unavailable(response_lang)
                    status = "document_ocr_unavailable"
                else:
                    answer = document_extraction_unavailable(response_lang)
                    status = "document_failed"
            else:
                from app.pipeline.document_answer import answer_uploaded_document
                from app.documents.query_policy import wants_document_narrative as _wants_narr

                if _wants_narr(payload.message, plan):
                    self._progress.emit(ProcessingStage.retrieving_document_section, plan=plan)
                doc_answer = answer_uploaded_document(
                    self.db,
                    user_id=principal.subject_id,
                    plan=plan,
                    message=payload.message,
                    document_ids=resolved,
                )
                if doc_answer is not None:
                    answer, document_safety_flags = self.safety.review(doc_answer.answer, payload.message)
                    self.repo.add_message(conv, "user", payload.message, intent=plan.intent.value)
                    self.repo.add_message(conv, "assistant", answer, intent=plan.intent.value)
                    self.repo.update_source_mode(conv, "user_uploaded", resolved[0])
                    logger.info(
                        "document_answer structured=%s pageindex=%s indexing=%s",
                        doc_answer.used_structured,
                        doc_answer.used_pageindex,
                        doc_answer.still_indexing,
                    )
                    return ChatResponse(
                        conversation_id=conv.id,
                        answer=answer,
                        evidence=doc_answer.evidence,
                        follow_ups=doc_answer.follow_ups,
                        meta=_meta(
                            status=doc_answer.status,
                            llm_mode="none",
                            sources_used=["user_uploaded"],
                            document_retrieval_called=True,
                            llm_called=False,
                            supershyft_called=False,
                            db_status=DB_PROVIDER_NOT_CALLED,
                            safety_flags=document_safety_flags,
                        ),
                    )
                hits = DocumentRetriever(self.db).retrieve(
                    principal.subject_id,
                    payload.message,
                    document_ids=resolved,
                )
                if not hits:
                    answer = document_no_match(response_lang)
                    status = "document_no_match"
                    evidence = []
                    self.repo.add_message(conv, "user", payload.message, intent=plan.intent.value)
                    self.repo.add_message(conv, "assistant", answer, intent=plan.intent.value)
                    return ChatResponse(
                        conversation_id=conv.id,
                        answer=answer,
                        evidence=[],
                        follow_ups=[],
                        meta=_meta(
                            status=status,
                            llm_mode="none",
                            sources_used=["user_uploaded"],
                            document_retrieval_called=True,
                            llm_called=False,
                            supershyft_called=False,
                            db_status=DB_PROVIDER_NOT_CALLED,
                        ),
                    )
                extracted = extract_lab_hits(hits, payload.message)
                answer = render_lab_answer(extracted, payload.message)
                evidence = []
                if extracted and answer:
                    primary = extracted[0]
                    hit = next(
                        (h for h in hits if (primary.page and h.page_start == primary.page) or primary.source_text in h.text),
                        hits[0],
                    )
                    evidence = [evidence_from_value(hit, primary)]
                else:
                    hit = hits[0]
                    excerpt = hit.text[:400]
                    answer = f"The uploaded report includes this passage: {excerpt}"
                    if hit.page_start:
                        answer += f" Source: Uploaded report · page {hit.page_start}."
                    evidence = [
                        EvidenceItem(
                            evidence_id=hit.chunk_id,
                            report_id=hit.document_id,
                            report_type="user_uploaded",
                            report_date=date.today(),
                            source="user_uploaded",
                            document_id=hit.document_id,
                            chunk_id=hit.chunk_id,
                            filename=hit.filename,
                            page_start=hit.page_start,
                            page_end=hit.page_end,
                            excerpt=excerpt,
                        )
                    ]
                status = "document_retrieved"
                answer, document_safety_flags = self.safety.review(answer, payload.message)
                self.repo.add_message(conv, "user", payload.message, intent=plan.intent.value)
                self.repo.add_message(conv, "assistant", answer, intent=plan.intent.value)
                self.repo.update_source_mode(conv, "user_uploaded", resolved[0])
                return ChatResponse(
                    conversation_id=conv.id,
                    answer=answer,
                    evidence=evidence,
                    follow_ups=[],
                    meta=_meta(
                        status=status,
                        llm_mode="none",
                        sources_used=["user_uploaded"],
                        document_retrieval_called=True,
                        llm_called=False,
                        supershyft_called=False,
                        db_status=DB_PROVIDER_NOT_CALLED,
                        safety_flags=document_safety_flags,
                    ),
                )
            evidence = [
                EvidenceItem(
                    evidence_id=d.id,
                    report_id=d.id,
                    report_type="user_uploaded",
                    report_date=date.today(),
                    source="user_uploaded",
                    document_id=d.id,
                    filename=d.original_filename,
                )
                for d in docs
            ]
            self.repo.add_message(conv, "user", payload.message, intent=plan.intent.value)
            self.repo.add_message(conv, "assistant", answer, intent=plan.intent.value)
            return ChatResponse(
                conversation_id=conv.id,
                answer=answer,
                evidence=evidence,
                follow_ups=[],
                meta=_meta(status=status, llm_mode="none"),
            )

        general_only = (
            plan.knowledge_scope == KnowledgeScope.general
            and not plan.needs_personal_data
            and not plan.needs_supershyft
            and not plan.needs_user_uploaded
            and not plan.needs_cross_source
        )

        if plan.intent == IntentType.casual_conversation:
            answer = casual_reply(response_lang)
            self.repo.add_message(conv, "user", payload.message, intent=plan.intent.value)
            self.repo.add_message(conv, "assistant", answer, intent=plan.intent.value)
            return ChatResponse(
                conversation_id=conv.id,
                answer=answer,
                evidence=[],
                follow_ups=[],
                meta=_meta(
                    status="ok",
                    llm_mode="casual",
                    knowledge_scope=plan.knowledge_scope.value,
                    supershyft_called=False,
                    llm_called=False,
                    retrieval_status="not_required",
                    retrieval_used=False,
                ),
            )

        if general_only:
            self._progress.emit(ProcessingStage.checking_medical_evidence, plan=plan)
            context = HealthContext(
                intent=plan.intent,
                answer_depth=plan.answer_depth,
                knowledge_scope=KnowledgeScope.general,
                data_source="general",
                resolved_topic=plan.topic,
                resolved_topic_name=plan.topic_name,
            )
        elif plan.needs_personal_data:
            try:
                self._progress.mark("retrieval")
                self._progress.mark("context")
                context = self.builder.build(
                    principal,
                    plan,
                    db=self.db,
                    document_ids=(
                        plan.document_ids or attached.document_ids or payload.document_ids
                        if plan.needs_user_uploaded
                        else []
                    ),
                    conversation_report_id=getattr(conv, "current_report_id", None),
                    message=payload.message,
                    conversation_state=conv_state,
                )
                self._progress.measure("retrieval")
                self._progress.measure("context")
                if context.personalization or context.health_story:
                    self._progress.emit(ProcessingStage.personalizing, plan=plan)
            except ProviderUnavailableError as exc:
                latency_ms = int((time.perf_counter() - started) * 1000)
                reason = getattr(exc, "reason", None) or DB_PROVIDER_NOT_CALLED
                logger.warning(
                    "supershyft_db operation=health_context status=unavailable "
                    "request_id=%s intent=%s latency_ms=%s error=%s reason=%s invoked=true",
                    request_id,
                    plan.intent.value,
                    latency_ms,
                    "provider_unavailable",
                    reason,
                )
                answer = personal_data_unavailable(response_lang)
                self.repo.add_message(conv, "user", payload.message, intent=plan.intent.value)
                self.repo.add_message(conv, "assistant", answer, intent=plan.intent.value)
                return ChatResponse(
                    conversation_id=conv.id,
                    answer=answer,
                    evidence=[],
                    follow_ups=[],
                    meta=_meta(
                        status="provider_unavailable",
                        llm_mode="none",
                        knowledge_scope=plan.knowledge_scope.value,
                        supershyft_called=True,
                        llm_called=False,
                        db_status=reason,
                        supershyft_record_count=0,
                        retrieval_status="provider_unavailable",
                        retrieval_used=True,
                        ihr_queried=True,
                    ),
                )
        else:
            self._progress.mark("context")
            context = self.builder.build(
                principal,
                plan,
                db=self.db,
                document_ids=(
                    plan.document_ids or attached.document_ids or payload.document_ids
                    if plan.needs_user_uploaded
                    else []
                ),
                conversation_report_id=getattr(conv, "current_report_id", None),
                message=payload.message,
                conversation_state=conv_state,
            )
            self._progress.measure("context")

        medical_hits = []
        if getattr(plan, "medical_evidence_required", False) or general_only:
            limit = 2 if re.search(r"\b(treatment|options|should|avoid|foods|diet|lifestyle|exercise)\b", payload.message, re.I) else 1
            medical_hits = self.medical_knowledge.query(payload.message, plan.topic, limit=limit)
            context.medical_passages = [
                f"{doc.name} ({doc.url}): {doc.excerpt}" for doc in medical_hits
            ]
            attach_medical_evidence(context, medical_hits)
            ContextMerger().merge_into(context, plan, principal.subject_id)
        eval_turn["medical"] = medical_hits
        eval_turn["context"] = context

        routing_note = None
        if jev_trace.decision:
            routing_note = jev_trace.decision.model_dump_json()
        diagnosis_restraint = (
            getattr(pre_safety, "category", None) == "diagnosis_request" and settings.assistant_quality_v2
        )
        if plan.history:
            self._progress.emit(ProcessingStage.analyzing_trends, plan=plan)
        elif plan.needs_cross_source:
            self._progress.emit(ProcessingStage.comparing_results, plan=plan)
        if plan.needs_personal_data and not general_only:
            # Stream clients can show the user's own values while the explanation is written.
            try:
                self._progress.preview(AnswerPreview(findings=preview_findings(plan, context)))
            except Exception:
                logger.debug("answer_preview_failed request_id=%s", request_id, exc_info=True)
        # Retrieval can reveal complexity that was not visible to the initial router.
        # Promote before the first answer-model call so clearly complex turns do not
        # pay for STANDARD_MEDICAL and then a second DEEP generation.
        plan = promote_for_retrieved_complexity(plan, context)
        self._progress.set_context(plan, follow_up=follow_up)
        self._progress.emit(ProcessingStage.reasoning, plan=plan)
        self._progress.mark("reasoner")
        reasoned = self.reasoner.run(
            message=payload.message,
            plan=plan,
            context=context,
            conversation_summary=conversation_summary,
            response_lang=response_lang,
            routing_note=routing_note,
            medical_hits=medical_hits,
            general_only=general_only,
            diagnosis_restraint=diagnosis_restraint,
            budget=eval_turn.get("budget"),
            complete_answer=self._complete_answer,
        )
        self._progress.measure("reasoner")
        answer = reasoned.answer
        llm_result = reasoned.llm_result
        llm_called = reasoned.llm_called
        llm_mode = reasoned.llm_mode
        answer_client = reasoned.answer_client
        model_fallback_used = reasoned.model_fallback_used
        medical_llm_latency_ms = reasoned.latency_ms
        eval_turn["model_escalated"] = reasoned.model_escalated
        eval_turn["escalation_reason"] = reasoned.escalation_reason
        if llm_result and getattr(llm_result, "parse_error", None):
            logger.error(
                "llm_structured_output_contract_violation request_id=%s parse_error=%s",
                request_id,
                llm_result.parse_error,
            )
        eval_turn["diagnosis_restraint"] = diagnosis_restraint

        approved_recommendations = list(context.recommendations)
        recommendation_flags: list[str] = []
        escalation = None
        if llm_result and llm_result.recommendation_candidates:
            recommendation_result = self.recommendations.validate(
                llm_result.recommendation_candidates,
                context,
            )
            approved_recommendations.extend(recommendation_result.approved)
            recommendation_flags.extend(recommendation_result.flags)
            escalation = llm_result.escalation

        self._progress.emit(ProcessingStage.checking_safety, plan=plan)
        self._progress.mark("validation")
        answer, flags, grounding_flags = self.validator.validate(
            answer,
            message=payload.message,
            plan=plan,
            context=context,
            medical_hits=medical_hits,
            llm_called=llm_called,
            pre_safety=pre_safety,
        )

        critical_flags, critical_escalation = self.safety.scan_critical_context(context)
        if critical_escalation:
            escalation = critical_escalation
        if getattr(pre_safety, "escalation", None) and not escalation:
            escalation = pre_safety.escalation
        flags.extend(critical_flags)
        if llm_result:
            flags.extend(llm_result.safety_flags)
        flags = list(dict.fromkeys(flags))
        if flags:
            logger.info("safety_flags request_id=%s flags=%s", request_id, flags)

        allowed_packages = package_suggestion_allowed(
            payload.message,
            previous_user_question=getattr(conv_state, "previous_user_question", None),
        )
        safe_mode = conversation_in_safe_mode(conv)
        if safe_mode:
            # An earlier turn escalated: stay cautious, no routine package suggestions.
            flags.append("safe_mode")
        if safe_mode or getattr(pre_safety, "category", None) in {
            "emergency",
            "self_harm",
            "medication_misuse",
            "diagnosis_request",
            "urgent_soon",
        }:
            allowed_packages = False
        testing_option, diagnostics_trace, _test_need = self.testing_options.evaluate(
            message=payload.message,
            context=context,
            plan=plan,
            conversation_state=conv_state,
            package_suggestion_allowed=allowed_packages,
        )
        eval_turn["diagnostics"] = diagnostics_trace

        inventory = build_inventory(principal, self.registry, plan, conv, context)
        suggestions = self.followups.generate(plan, answer, context, inventory)
        experience = build_experience_plan(
            payload.message,
            plan,
            context,
            conv_state,
        )
        llm_follow = []
        if llm_result and llm_result.follow_up_questions:
            for question in llm_result.follow_up_questions:
                text = question.strip()
                if not text:
                    continue
                if plan.knowledge_scope == KnowledgeScope.general and (
                    requires_personal_record(text) or is_personal_utterance(text)
                ):
                    continue
                llm_follow.append(text)
        self._progress.measure("validation")
        self._progress.emit(ProcessingStage.composing_response, plan=plan)
        self._progress.mark("compose")
        answer, suggestions, presentation = self.composer.compose(
            answer,
            plan=plan,
            context=context,
            follow_ups=suggestions,
            llm_follow_ups=llm_follow,
            llm_result=llm_result,
            testing_option=testing_option,
            experience=experience,
            conversation_turn=conv_state.turn_type.value,
        )
        self._progress.measure("compose")
        if looks_like_structured_json(answer):
            answer = public_answer_text(answer)
        safety_caution = getattr(pre_safety, "caution", None)
        if not safety_caution and safe_mode:
            safety_caution = see_doctor_soon_message(getattr(pre_safety, "reply_language", None))
        if safety_caution:
            answer = f"{safety_caution}\n\n{answer}"

        micro_insight = compose_micro_insight(
            plan=plan,
            context=context,
            presentation=presentation,
            llm_called=llm_called,
        )
        if micro_insight and not presentation.personal_relevance:
            presentation.personal_relevance = micro_insight

        turn_experience = self.experience_orchestrator.build(
            answer=answer,
            presentation=presentation,
            follow_ups=suggestions,
            safety_mode=SafetyLayer.request_safety_mode(pre_safety),
            escalation=escalation,
        )
        if turn_experience.stream_policy.value == "SEMANTIC_BLOCKS":
            for block in turn_experience.blocks:
                self._progress.experience_block(block)

        self.repo.add_message(conv, "user", payload.message, intent=plan.intent.value)
        self.repo.add_message(conv, "assistant", answer, intent=plan.intent.value)
        self.repo.update_follow_up(
            conv,
            context.resolved_topic or plan.topic,
            context.resolved_topic_name or plan.topic_name,
        )
        selected_report_id = None
        if context.status != "ambiguous":
            selected_report_id = context.evidence[0].report_id if context.evidence else plan.report_id
        follow = suggestions[0] if suggestions else None
        expected = ExpectedReplyType.none
        if follow and follow.expected_reply_type:
            try:
                expected = ExpectedReplyType(follow.expected_reply_type)
            except ValueError:
                expected = ExpectedReplyType.none
        if expected == ExpectedReplyType.none and follow and follow.handling_path == "CONTINUE_INTERPRETATION":
            if re.search(r"\b(symptoms?|medication|supplement)\b", follow.text or "", re.I):
                expected = ExpectedReplyType.clinical_context
        next_state = persistable_state(
            conv_state,
            plan_topic=context.resolved_topic or plan.topic,
            plan_domains=list(plan.domains or []),
            plan_entities=list(plan.display_entities or plan.requested_metrics or []),
            plan_intent=plan.intent.value,
            user_message=payload.message,
            assistant_summary=(presentation.headline if presentation else None)
            or (f"Discussed {plan.topic_name}" if plan.topic_name else None),
            follow_up=follow.text if follow else None,
            expected_reply_type=expected,
            expected_handling_path=follow.handling_path if follow else None,
            report_id=selected_report_id,
            prior_personal=bool(plan.needs_personal_data),
            last_surfaced_catalog_id=testing_option.catalog_id if testing_option else None,
            last_surfaced_catalog_name=testing_option.display_name if testing_option else None,
            communication_style=(
                context.personalization.communication_preference.value if context.personalization else None
            ),
            recent_context_notes=(
                list(context.personalization.recent_user_context.notes)
                if context.personalization
                else None
            ),
            session_goal_code=(
                context.personalization.primary_health_goal
                if context.personalization and context.personalization.goal_source
                and context.personalization.goal_source.value == "conversation"
                else None
            ),
            current_concern=experience.current_concern,
            response_depth=experience.depth.value,
            conversation_goal=experience.goal.value,
            explained_entities=list(experience.relevant.requested_keys),
            topic_summary=experience.topic_summary.text if experience.topic_summary else None,
        )
        self.repo.update_conversation_state(conv, next_state.model_dump_json())
        self.repo.update_context_state(
            conv,
            marker_code=context.resolved_topic or plan.topic,
            report_id=selected_report_id,
            summary=self.memory.updated_summary(
                conv,
                plan.intent.value,
                context.resolved_topic_name or plan.topic_name,
            ),
        )

        latency = int((time.perf_counter() - started) * 1000)
        subject_hash = hashlib.sha256(principal.subject_id.encode()).hexdigest()[:12]
        from app.pipeline.retrieval_executor import audit_request

        audit_request(
            principal=principal,
            conversation_id=conv.id,
            sources=list(plan.data_sources or context.meta.sources or []),
            records=len(context.markers) + len(context.bio_ai_risks) + len(context.questionnaire),
            model_tier=plan.answer_model_tier.value if plan.answer_model_tier else None,
            success=True,
        )
        if settings.is_development:
            logger.info(
                "chat_dev auth_provider=%s subject_id=%s model_tier=%s model=%s jev_intent=%s "
                "supershyft_called=%s request_id=%s",
                (settings.auth_provider or "mock").strip().lower(),
                principal.subject_id,
                plan.answer_model_tier.value if plan.answer_model_tier else None,
                (
                    answer_client.model
                    if answer_client and llm_called
                    else (model_id_for_tier(plan.answer_model_tier) if plan.answer_model_tier else None)
                ),
                jev_trace.decision.intent.value if jev_trace.decision else plan.intent.value,
                bool(plan.needs_personal_data),
                request_id,
            )
        logger.info(
            "chat request_id=%s conversation_id=%s subject_id=%s intent=%s provider=%s latency=%s "
            "jev_called=%s jev_fallback=%s jev_ms=%s llm_ms=%s",
            request_id,
            conv.id,
            subject_hash,
            plan.intent.value,
            settings.health_provider,
            latency,
            jev_trace.called,
            jev_trace.fallback,
            jev_trace.latency_ms,
            medical_llm_latency_ms,
        )
        logger.info(
            "conversation_state turn_type=%s active_topic=%s active_entities=%s resolved_references=%s "
            "expected_reply_type=%s jev_plan=%s retrieval_performed=%s reasoner_called=%s",
            conv_state.turn_type.value,
            (plan.domains[0] if plan.domains else None) or plan.topic or conv_state.active_domain,
            list(plan.display_entities or conv_state.active_entities or []),
            conv_state.resolved_references,
            (follow.expected_reply_type if follow else conv_state.expected_reply_type.value),
            list(plan.operations or []) or (jev_trace.decision.operation.value if jev_trace.decision else plan.operation),
            bool(plan.needs_personal_data or plan.needs_user_uploaded),
            "yes" if llm_called else "no",
        )
        self.repo.add_audit(
            request_id=request_id,
            subject_id_hash=subject_hash,
            conversation_id=conv.id,
            intent=plan.intent.value,
            provider=settings.health_provider,
            latency_ms=latency,
            error_code=None,
        )

        evidence = [EvidenceItem.model_validate(e.model_dump()) for e in context.evidence]
        seen_ev = set()
        uniq_ev = []
        for item in evidence:
            key = (item.report_id, item.marker, item.source, item.page_start)
            if key in seen_ev:
                continue
            seen_ev.add(key)
            uniq_ev.append(item)
        evidence = uniq_ev
        sources = ["supershyft"] if plan.needs_personal_data else ["general"]
        if plan.needs_user_uploaded and "user_uploaded" not in sources:
            sources.append("user_uploaded")
        requested = []
        if plan.needs_general:
            requested.append("general")
        if plan.needs_supershyft or plan.needs_personal_data:
            requested.append("supershyft")
        if plan.needs_user_uploaded:
            requested.append("user_uploaded")
        if general_only:
            db_status = DB_PROVIDER_NOT_CALLED
        elif (settings.health_provider or "").lower() != "supershyft":
            db_status = DB_PROVIDER_NOT_CALLED
        elif plan.needs_personal_data and not evidence and context.missing:
            db_status = DB_NO_RECORDS
        elif plan.needs_personal_data:
            db_status = "ok"
        else:
            db_status = DB_PROVIDER_NOT_CALLED
        if plan.needs_personal_data and not evidence and context.missing:
            if "can't access your personal SuperShyft" in answer:
                answer = personal_data_not_found(response_lang)
        logger.debug(
            "query_result request_id=%s supershyft_invoked=%s records=%s evidence=%s source=%s db_status=%s",
            request_id,
            bool(plan.needs_personal_data),
            len(evidence),
            len(evidence),
            sources,
            db_status,
        )
        if plan.needs_user_uploaded and (plan.document_ids or attached.document_ids):
            mode = "cross" if has_supershyft_sources(plan) else "user_uploaded"
            self.repo.update_source_mode(
                conv, mode, (plan.document_ids or attached.document_ids)[0]
            )
        else:
            self.repo.update_source_mode(conv, "supershyft" if plan.needs_personal_data else "general")
        return ChatResponse(
            conversation_id=conv.id,
            answer=answer,
            evidence=evidence,
            follow_ups=suggestions,
            recommendations=approved_recommendations,
            presentation=presentation,
            experience=turn_experience,
            testing_option=testing_option,
            meta=_meta(
                status=context.status,
                llm_mode=llm_mode,
                sources_used=sources,
                knowledge_scope=plan.knowledge_scope.value,
                sources_requested=requested,
                llm_called=llm_called,
                supershyft_called=bool(plan.needs_personal_data),
                document_retrieval_called=bool(plan.needs_user_uploaded),
                db_status=db_status,
                supershyft_record_count=len(evidence) if plan.needs_personal_data else 0,
                safety_flags=flags,
                safety_mode=SafetyLayer.request_safety_mode(pre_safety),
                safety_caution=safety_caution,
                recommendation_flags=recommendation_flags,
                grounding_flags=grounding_flags,
                escalation=escalation,
                response_mode=presentation.mode.value if presentation else plan.response_mode,
                model=(answer_client.model if answer_client and llm_called else None),
                provider=settings.resolved_llm_provider() if llm_called else None,
                input_tokens=(getattr(answer_client, "last_usage", {}) or {}).get("input_tokens") if llm_called and answer_client else None,
                output_tokens=(getattr(answer_client, "last_usage", {}) or {}).get("output_tokens") if llm_called and answer_client else None,
                estimated_cost_usd=(
                    estimate_cost_usd(
                        answer_client.model,
                        int((getattr(answer_client, "last_usage", {}) or {}).get("input_tokens") or 0),
                        int((getattr(answer_client, "last_usage", {}) or {}).get("output_tokens") or 0),
                    )
                    if llm_called and answer_client
                    else None
                ),
                model_fallback_used=model_fallback_used if llm_called else None,
                answer_model=(
                    answer_client.model
                    if answer_client and llm_called
                    else (
                        model_id_for_tier(plan.answer_model_tier)
                        if uses_answer_llm(plan.answer_model_tier)
                        else None
                    )
                ),
                answer_model_tier=(
                    plan.answer_model_tier.value if plan.answer_model_tier else None
                ),
                reasoning_depth=plan.reasoning_depth.value if plan.reasoning_depth else None,
                medical_llm_latency_ms=medical_llm_latency_ms,
                retrieval_used=bool(plan.needs_personal_data or plan.needs_user_uploaded),
                retrieval_sources=sources,
                ihr_queried=bool(plan.needs_personal_data),
                documents_queried=bool(plan.needs_user_uploaded),
                source_outcomes=list(context.source_outcomes or []),
                conversation_goal=experience.goal.value,
                response_depth=experience.depth.value,
                next_conversation_action=experience.next_action.value,
            ),
        )

    def _cross_source(
        self,
        principal,
        payload,
        conv,
        plan,
        request_id,
        started,
        _meta,
        doc_svc,
        completed_docs,
        response_lang,
        budget=None,
    ):
        attached = resolve_attached_documents(
            explicit_ids=payload.document_ids,
            context_ref=payload.context_ref,
            last_document_id=getattr(conv, "last_document_id", None),
            completed_docs=completed_docs,
        )
        resolved = list(attached.document_ids)
        if attached.status == "ambiguous":
            latest_id = None
            if re.search(r"latest uploaded", payload.message, re.I):
                from app.pipeline.document_select import latest_uploaded_by_test_date

                latest_id = latest_uploaded_by_test_date(self.db, principal.subject_id, completed_docs)
            if latest_id:
                resolved = [latest_id]
            else:
                answer = (
                    "I can compare them. Which uploaded report do you want to compare "
                    "with your latest SuperShyft report?"
                )
                self.repo.add_message(conv, "user", payload.message, intent=plan.intent.value)
                self.repo.add_message(conv, "assistant", answer, intent=plan.intent.value)
                return ChatResponse(
                    conversation_id=conv.id,
                    answer=answer,
                    evidence=[],
                    follow_ups=[],
                    meta=_meta(status="cross_source_ambiguous", llm_mode="none"),
                )
        if attached.status == "missing" or not resolved:
            answer = "I don't have an uploaded report to compare with SuperShyft."
            self.repo.add_message(conv, "user", payload.message, intent=plan.intent.value)
            self.repo.add_message(conv, "assistant", answer, intent=plan.intent.value)
            return ChatResponse(
                conversation_id=conv.id,
                answer=answer,
                evidence=[],
                follow_ups=[],
                meta=_meta(status="cross_source_missing_document", llm_mode="none", sources_used=["supershyft"]),
            )
        docs = doc_svc.assert_owned(principal.subject_id, resolved)
        self._progress.emit(ProcessingStage.comparing_results, plan=plan)
        from app.documents.metadata import load_meta
        from app.documents.lookup import lookup_facts
        from app.documents.uploaded_context import context_from_row

        pending = [
            d
            for d in docs
            if d.extraction_status in {"not_started", "processing"}
            and not load_meta(d).get("structured_facts_ready")
        ]
        if pending:
            answer = document_unread()
            self.repo.add_message(conv, "user", payload.message, intent=plan.intent.value)
            self.repo.add_message(conv, "assistant", answer, intent=plan.intent.value)
            return ChatResponse(
                conversation_id=conv.id,
                answer=answer,
                evidence=[],
                follow_ups=[],
                meta=_meta(status="document_processing", llm_mode="none", sources_used=["user_uploaded"]),
            )
        if any(d.extraction_status == "failed" for d in docs):
            answer = document_extraction_unavailable()
            self.repo.add_message(conv, "user", payload.message, intent=plan.intent.value)
            self.repo.add_message(conv, "assistant", answer, intent=plan.intent.value)
            return ChatResponse(
                conversation_id=conv.id,
                answer=answer,
                evidence=[],
                follow_ups=[],
                meta=_meta(
                    status="document_failed",
                    llm_mode="none",
                    sources_used=["user_uploaded"],
                    retrieval_status="extraction_failed",
                    documents_queried=True,
                ),
            )

        topic = plan.topic
        query = payload.message if not topic else f"{plan.topic_name or topic} {payload.message}"
        contexts = [context_from_row(d) for d in docs]
        structured_facts = lookup_facts(contexts, keys=[topic] if topic else None)
        uploaded_keys = {
            (item.canonical_code or "").lower()
            for item in structured_facts
            if item.canonical_code
        }
        hits = []
        ext = None
        ext_hit = None
        if not structured_facts:
            hits = DocumentRetriever(self.db).retrieve(
                principal.subject_id, query, document_ids=resolved, limit=5
            )
            for h in hits:
                uploaded_keys |= extract_keys_present(h.text)
                if topic:
                    found = extract_marker_from_text(h.text, topic, page=h.page_start)
                    if found and (ext is None or found.confidence == "high"):
                        ext = found
                        ext_hit = h
            if ext is None:
                ext_hit = hits[0] if hits else None

        from app.contracts.common import IntentType

        try:
            ss_plan = plan.model_copy(
                update={
                    "needs_blood": True,
                    "needs_bio_ai": False,
                    "needs_lifestyle": False,
                    "needs_supershyft": True,
                    "needs_user_uploaded": False,
                    "needs_cross_source": False,
                    "history": False,
                    "intent": IntentType.latest_result,
                    "knowledge_scope": KnowledgeScope.personal,
                }
            )
            if not topic and uploaded_keys and not ss_plan.requested_metrics:
                # "Compare my report with SuperShyft": fetch the markers the uploaded report has,
                # otherwise the SuperShyft side is empty and every marker reads as "not found".
                ss_plan = ss_plan.model_copy(update={"requested_metrics": sorted(uploaded_keys)})
            context = self.builder.build(
                principal, ss_plan, db=self.db, document_ids=payload.document_ids
            )
        except ProviderUnavailableError:
            answer = personal_data_unavailable()
            self.repo.add_message(conv, "user", payload.message, intent=plan.intent.value)
            self.repo.add_message(conv, "assistant", answer, intent=plan.intent.value)
            return ChatResponse(
                conversation_id=conv.id,
                answer=answer,
                evidence=[],
                follow_ups=[],
                meta=_meta(
                    status="provider_unavailable",
                    llm_mode="none",
                    sources_used=["supershyft"],
                    retrieval_status="provider_unavailable",
                    retrieval_used=True,
                    ihr_queried=True,
                ),
            )
        context.uploaded_documents = contexts

        ss_marker = next((m for m in context.markers if topic and m.key == topic), None)
        ss_date = None
        for e in context.evidence:
            if topic and e.marker and topic.replace("_", " ") in (e.marker or "").lower().replace("_", " "):
                ss_date = e.report_date
                break
            if e.report_date:
                ss_date = e.report_date
        from app.contracts.blood import BloodMarker
        from app.contracts.common import MarkerFlag

        if ss_marker is None:
            ss_sv = marker_to_source(
                BloodMarker(id="missing", key=topic or "unknown", name=NAMES.get(topic or "", topic or "marker"), value=None, flag=MarkerFlag.missing),
                ss_date,
            )
        else:
            ss_sv = marker_to_source(ss_marker, ss_date)

        filename = docs[0].original_filename if docs else "uploaded.pdf"
        doc_id = resolved[0]
        result = None
        answer = ""
        if structured_facts:
            compare_keys = [topic] if topic else None
            structured_results = compare_uploaded_with_blood(
                lookup_facts(contexts),
                context.markers,
                ss_date,
                keys=compare_keys,
            )
            if not topic and structured_results:
                result = structured_results[0]
                up_sv = result.source_a
                filename = next(
                    (d.original_filename for d in docs if d.id == up_sv.document_id),
                    filename,
                )
                doc_id = up_sv.document_id or doc_id
                lower = payload.message.lower()
                why = "why" in lower and "different" in lower
                answer = (
                    render_comparison(result, why=why, newer="newer" in lower)
                    if len(structured_results) == 1
                    else render_multi_comparison(structured_results, why=why, newer="newer" in lower)
                )
            elif structured_results:
                result = structured_results[0]
                up_sv = result.source_a
                filename = next(
                    (d.original_filename for d in docs if d.id == up_sv.document_id),
                    filename,
                )
                doc_id = up_sv.document_id or doc_id
            else:
                fact = structured_facts[0]
                up_sv = uploaded_fact_to_source(fact)
                filename = next(
                    (d.original_filename for d in docs if d.id == fact.source_document_id),
                    filename,
                )
                doc_id = fact.source_document_id
                result = CrossSourceComparator().compare(
                    topic or fact.canonical_code or "marker",
                    fact.display_name or NAMES.get(topic or "", topic or "marker"),
                    up_sv,
                    ss_sv,
                )
        else:
            from app.documents.value_extraction import ExtractedValue

            if ext is None:
                ext = ExtractedValue(
                    parameter=topic or "unknown",
                    name=NAMES.get(topic or "", topic or "marker"),
                    value=None,
                    unit=None,
                    source_text=(ext_hit.text[:200] if ext_hit else ""),
                    page=ext_hit.page_start if ext_hit else None,
                    date=None,
                    date_kind=None,
                    confidence="low",
                )
                filename = ext_hit.filename if ext_hit else filename
                doc_id = ext_hit.document_id if ext_hit else doc_id
            else:
                filename = ext_hit.filename if ext_hit else filename
                doc_id = ext_hit.document_id if ext_hit else doc_id
            up_sv = extracted_to_source(ext, doc_id, filename)
            result = CrossSourceComparator().compare(topic or "marker", NAMES.get(topic or "", topic or "marker"), up_sv, ss_sv)

        context.cross_source = CrossSourceFinding(
            parameter=result.parameter,
            name=result.name,
            values=[
                CrossSourceValue(
                    source=result.source_a.source,
                    value=result.source_a.value,
                    unit=result.source_a.unit,
                    measured_at=result.source_a.date,
                    document_id=result.source_a.document_id,
                    page=result.source_a.page,
                    confidence=result.source_a.confidence,
                ),
                CrossSourceValue(
                    source=result.source_b.source,
                    value=result.source_b.value,
                    unit=result.source_b.unit,
                    measured_at=result.source_b.date,
                    report_id=context.evidence[0].report_id if context.evidence else None,
                    confidence=result.source_b.confidence,
                ),
            ],
            difference=result.difference,
            direction=result.direction,
            notes=result.notes,
        )
        lower = payload.message.lower()
        if not answer:
            answer = render_comparison(
                result,
                why="why" in lower and "different" in lower,
                newer="newer" in lower,
            )
        llm_mode = "none"
        answer_client = None
        model_fallback_used = False
        if settings.enable_llm:
            try:
                messages = self.prompts.build(
                    context,
                    self.memory.semantic_summary(conv),
                    payload.message,
                    response_lang,
                )
                llm_result, answer_client, _used_tier, model_fallback_used = self._complete_answer(
                    messages, plan, budget=budget
                )
                answer = llm_result.answer
                llm_mode = settings.resolved_llm_provider()
            except LLMUnavailableError:
                llm_mode = "deterministic_fallback"
        if looks_like_structured_json(answer):
            answer = public_answer_text(answer)
        answer, flags = self.safety.review(answer, payload.message)
        if flags:
            logger.info("safety_flags request_id=%s flags=%s", request_id, flags)

        evidence = []
        if ext_hit:
            evidence.append(
                EvidenceItem(
                    evidence_id=ext_hit.chunk_id,
                    report_id=doc_id,
                    report_type="user_uploaded",
                    report_date=ext.date or date.today(),
                    source="user_uploaded",
                    document_id=doc_id,
                    chunk_id=ext_hit.chunk_id,
                    filename=filename,
                    page_start=ext_hit.page_start,
                    page_end=ext_hit.page_end,
                    excerpt=ext.source_text,
                    marker=NAMES.get(topic or "", topic),
                    value=up_sv.value,
                    unit=up_sv.unit,
                )
            )
        elif up_sv.document_id:
            evidence.append(
                EvidenceItem(
                    evidence_id=f"ev-{doc_id[:8]}",
                    report_id=doc_id,
                    report_type="user_uploaded",
                    report_date=up_sv.date or date.today(),
                    source="user_uploaded",
                    document_id=doc_id,
                    filename=filename,
                    page_start=up_sv.page,
                    excerpt=(up_sv.excerpt or "")[:240],
                    marker=result.name,
                    value=up_sv.value,
                    unit=up_sv.unit,
                )
            )
        for e in context.evidence:
            dump = e.model_dump()
            dump["source"] = "supershyft"
            label = (NAMES.get(topic or "", topic or "") or "").lower()
            if topic and e.marker and label not in (e.marker or "").lower():
                continue
            dump["marker"] = NAMES.get(topic or "", topic)
            evidence.append(EvidenceItem.model_validate(dump))

        inventory = build_inventory(principal, self.registry, plan, conv, context)
        inventory.uploaded_marker_keys = uploaded_keys
        inventory.sources = {"supershyft", "user_uploaded"}
        suggestions = self.followups.generate(plan, answer, context, inventory)
        self.repo.add_message(conv, "user", payload.message, intent=plan.intent.value)
        self.repo.add_message(conv, "assistant", answer, intent=plan.intent.value)
        self.repo.update_follow_up(conv, plan.topic, plan.topic_name)
        self.repo.update_source_mode(conv, "cross", resolved[0])
        return ChatResponse(
            conversation_id=conv.id,
            answer=answer,
            evidence=evidence,
            follow_ups=suggestions,
            meta=_meta(
                status="cross_source_comparison",
                llm_mode=llm_mode,
                sources_used=["supershyft", "user_uploaded"],
                safety_flags=flags,
                document_retrieval_called=True,
                supershyft_called=True,
                llm_called=settings.enable_llm and llm_mode != "deterministic_fallback",
                model=(
                    answer_client.model
                    if answer_client and llm_mode not in {"none", "deterministic_fallback"}
                    else None
                ),
                provider=settings.resolved_llm_provider() if llm_mode not in {"none", "deterministic_fallback"} else None,
                model_fallback_used=model_fallback_used if answer_client else None,
                answer_model=answer_client.model if answer_client else None,
                retrieval_used=True,
                retrieval_sources=["supershyft", "user_uploaded"],
                ihr_queried=True,
                documents_queried=True,
            ),
        )

    def _record_evaluation(self, response: ChatResponse, eval_turn: dict | None = None) -> ChatResponse:
        turn = eval_turn or getattr(self, "_eval_turn", None) or {}
        conv = turn.get("conv")
        plan = turn.get("plan")
        principal = turn.get("principal")
        payload = turn.get("payload")
        if conv is None or plan is None or principal is None or payload is None:
            timing = self._progress.finish(llm_calls=0)
            response.meta.timing = timing.model_dump(exclude_none=True)
            self._progress.emit(ProcessingStage.complete)
            return response
        meta = response.meta
        if not meta.retrieval_status:
            meta.retrieval_status = infer_retrieval_status(
                personal_required=bool(plan.needs_personal_data),
                documents_required=bool(plan.needs_user_uploaded),
                meta_status=meta.status,
                db_status=meta.db_status,
                evidence_count=len(response.evidence or []),
                has_missing=meta.db_status == DB_NO_RECORDS,
            )
        meta.retrieval_used = bool(meta.retrieval_used or plan.needs_personal_data or plan.needs_user_uploaded)
        if not meta.retrieval_sources:
            meta.retrieval_sources = list(meta.sources_used or [])
        if meta.retrieval_status == "not_required":
            meta.retrieval_used = False
            meta.ihr_queried = False
            meta.documents_queried = False
        else:
            meta.ihr_queried = bool(meta.ihr_queried if meta.ihr_queried is not None else plan.needs_personal_data)
            meta.documents_queried = bool(
                meta.documents_queried if meta.documents_queried is not None else plan.needs_user_uploaded
            )
        meta.grounding_passed = not bool(meta.grounding_flags)
        meta.safety_passed = meta.status != "safety_block" and not bool(meta.escalation)
        timing = self._progress.finish(
            llm_calls=1 if meta.llm_called else 0,
            input_tokens=meta.input_tokens,
            output_tokens=meta.output_tokens,
        )
        meta.timing = timing.model_dump(exclude_none=True)
        self._progress.emit(ProcessingStage.complete)
        medical = turn.get("medical") or []
        jev_trace = turn.get("jev_trace")
        response.provenance = build_user_provenance(plan, list(response.evidence or []), medical)
        if settings.is_development:
            context = turn.get("context")
            task_sources = [
                name
                for name, flag in (
                    ("blood", plan.needs_blood),
                    ("bio_ai", plan.needs_bio_ai),
                    ("questionnaire", plan.needs_questionnaire),
                    ("profile", plan.needs_profile or plan.needs_lifestyle),
                    ("goals", plan.needs_goals),
                    ("uploaded", plan.needs_user_uploaded),
                    ("medical", plan.needs_general or plan.medical_evidence_required),
                )
                if flag
            ]
            conv_state = turn.get("conversation_state")
            meta.debug = {
                "turn_type": conv_state.turn_type.value if conv_state else None,
                "active_topic": (plan.domains[0] if plan.domains else None) or plan.topic or (conv_state.active_domain if conv_state else None),
                "active_entities": list(plan.display_entities or (conv_state.active_entities if conv_state else []) or []),
                "resolved_references": dict(conv_state.resolved_references or {}) if conv_state else {},
                "expected_reply_type": conv_state.expected_reply_type.value if conv_state and conv_state.expected_reply_type else None,
                "jev_plan": {
                    "intent": jev_trace.decision.intent.value if jev_trace and jev_trace.decision else plan.intent.value,
                    "operation": jev_trace.decision.operation.value if jev_trace and jev_trace.decision else plan.operation,
                    "operations": list(plan.operations or []),
                    "complexity": plan.complexity.value if plan.complexity else None,
                    "reasoning_depth": plan.reasoning_depth.value if plan.reasoning_depth else None,
                    "model_tier": plan.answer_model_tier.value if plan.answer_model_tier else None,
                    "reasons_for_model_selection": list(plan.model_selection_reasons or []),
                },
                "model_router": {
                    "selected_provider": provider_for_model(meta.answer_model) if meta.llm_called else None,
                    "selected_model": meta.answer_model if meta.llm_called else None,
                    "gateway": meta.provider if meta.llm_called else None,
                },
                "tokens": {
                    "input": meta.input_tokens,
                    "output": meta.output_tokens,
                },
                "latency": {
                    "jev_ms": meta.jev_latency_ms,
                    "medical_llm_ms": meta.medical_llm_latency_ms,
                },
                "estimated_cost": meta.estimated_cost_usd,
                "escalated": bool(turn.get("model_escalated")),
                "escalation_reason": turn.get("escalation_reason"),
                "retrieval_performed": bool(meta.retrieval_used or plan.needs_personal_data or plan.needs_user_uploaded),
                "reasoner_called": bool(meta.llm_called),
                "task_plan": {
                    "domains": list(plan.domains or []),
                    "entities": list(plan.requested_metrics or []),
                    "operations": list(plan.operations or []),
                    "sources": list(task_sources),
                    "selectors": list(plan.selectors or []),
                },
                "domain_expansion": {
                    "expanded_entities": expand_requested_keys(
                        plan.requested_metrics or ([plan.topic] if plan.topic else [])
                    ),
                    "optional_entities": list(plan.optional_entities or []),
                },
                "retrieval": {
                    "found": [
                        getattr(m, "key", None)
                        for m in getattr(context, "markers", []) or []
                        if getattr(m, "key", None)
                    ],
                    "missing": [
                        {"key": getattr(item, "key", None), "reason": getattr(item, "reason", None)}
                        for item in getattr(context, "missing", []) or []
                    ],
                    "source": list(meta.retrieval_sources or meta.sources_used or []),
                },
                "health_context": {
                    "markers": [
                        getattr(m, "key", None)
                        for m in getattr(context, "markers", []) or []
                        if getattr(m, "key", None)
                    ],
                    "domains": list(getattr(context, "domains", None) or []),
                    "facts": len(getattr(context, "facts", None) or []),
                },
                "reasoner": {"called": bool(meta.llm_called)},
                "validator": {
                    "grounding_passed": meta.grounding_passed,
                    "safety_passed": meta.safety_passed,
                    "flags": list(meta.safety_flags or []) + list(meta.grounding_flags or []),
                },
                "diagnostics": (turn.get("diagnostics").model_dump(mode="json") if turn.get("diagnostics") else None),
                "personalization": (
                    {
                        "active_goal": getattr(getattr(context, "personalization", None), "primary_health_goal", None),
                        "communication_style": getattr(
                            getattr(getattr(context, "personalization", None), "communication_preference", None),
                            "value",
                            None,
                        ),
                        "lifestyle_context": (
                            getattr(context.personalization.known_lifestyle, "already_supportive", None)
                            if getattr(context, "personalization", None)
                            else None
                        ),
                        "recent_context": (
                            context.personalization.recent_user_context.notes
                            if getattr(context, "personalization", None)
                            else []
                        ),
                    }
                    if context is not None
                    else None
                ),
                "longitudinal": (
                    {
                        "baseline_available": bool(getattr(context, "baselines", None)),
                        "persistent_abnormalities": [
                            item.entity
                            for item in getattr(context, "baselines", None) or []
                            if item.persistent_abnormality
                        ],
                        "new_abnormalities": [
                            item.entity
                            for item in getattr(context, "baselines", None) or []
                            if item.newly_abnormal
                        ],
                        "improved": [
                            item.entity
                            for item in getattr(context, "baselines", None) or []
                            if "IMPROVED" in item.classification.value or item.classification.value == "RETURNED_TO_RANGE"
                        ],
                        "worsened": [
                            item.entity
                            for item in getattr(context, "baselines", None) or []
                            if item.classification.value == "WORSENED"
                        ],
                        "stable": [
                            item.entity
                            for item in getattr(context, "baselines", None) or []
                            if item.classification.value == "STABLE"
                        ],
                    }
                    if context is not None
                    else None
                ),
                "prioritization": (
                    {
                        "themes_considered": [
                            item.title for item in (getattr(response.presentation, "themes", None) or [])
                        ],
                        "goal_relevance": getattr(getattr(context, "personalization", None), "primary_health_goal", None),
                        "selected_themes": [
                            item.title
                            for item in (getattr(response.presentation, "themes", None) or [])
                            if getattr(item, "status", None) and item.status.value != "reassuring"
                        ],
                    }
                    if context is not None
                    else None
                ),
                "response": {
                    "mode": response.presentation.mode.value if response.presentation else None,
                    "themes_selected": [
                        item.title for item in (getattr(response.presentation, "themes", None) or [])
                    ],
                    "followups": [getattr(item, "text", item) for item in (response.follow_ups or [])][:3],
                    "package_suggestion": bool(response.testing_option),
                    "quiet_mode": bool(getattr(response.presentation, "quiet_mode", False)) if response.presentation else False,
                },
                "final_response_path": (
                    "llm"
                    if meta.llm_called and meta.llm_mode not in {"deterministic_fallback", "structured_blood"}
                    else meta.llm_mode or "deterministic"
                ),
                "retrieval_status": meta.retrieval_status,
                "query_plan_topic": plan.topic,
                "query_plan_intent": plan.intent.value,
                "requested_metrics": list(plan.requested_metrics or []),
                "retrieved_biomarkers": [
                    getattr(m, "key", None)
                    for m in getattr(context, "markers", []) or []
                    if getattr(m, "key", None)
                ],
                "time_operation": plan.time_operation,
                "user_message": (payload.message or "")[:160],
            }
        refs = []
        for item in response.evidence or []:
            refs.append(
                {
                    "source": item.source,
                    "report_id": item.report_id,
                    "document_id": item.document_id,
                    "metric": item.marker,
                    "value": item.value,
                    "unit": item.unit,
                    "date": item.report_date.isoformat() if item.report_date else None,
                    "page": item.page_start,
                }
            )
        last = self.repo.latest_assistant_message(conv.id)
        row = self.repo.add_interaction(
            conversation_id=conv.id,
            subject_id=principal.subject_id,
            user_query=payload.message,
            assistant_response=response.answer,
            detected_intent=plan.intent.value,
            routing_decision=meta.router,
            personal_data_required=bool(plan.needs_personal_data),
            retrieval_used=bool(meta.retrieval_used),
            retrieval_sources=json.dumps(meta.retrieval_sources or []),
            retrieval_operation=meta.jev_operation or plan.intent.value,
            retrieval_status=meta.retrieval_status,
            evidence_refs=json.dumps(refs) if refs else None,
            ihr_queried=bool(meta.ihr_queried),
            documents_queried=bool(meta.documents_queried),
            model_used=meta.model,
            grounding_result=json.dumps(meta.grounding_flags or []),
            grounding_passed=meta.grounding_passed,
            safety_result=json.dumps(
                {"flags": meta.safety_flags or [], "escalation": meta.escalation}
            ),
            safety_passed=meta.safety_passed,
            fallback_used=bool(meta.fallback_used or meta.jev_fallback),
            error_status=None if meta.status in {"ok", "document_retrieved", "cross_source_comparison"} else meta.status,
            request_id=meta.request_id,
            message_id=last.id if last else None,
        )
        fact_rows = []
        for item in response.evidence or []:
            if item.marker is None or item.value is None:
                continue
            fact_rows.append(
                {
                    "subject_id": principal.subject_id,
                    "conversation_id": conv.id,
                    "interaction_id": row.id,
                    "source": item.source or "unknown",
                    "report_id": item.report_id,
                    "document_id": item.document_id,
                    "metric": item.marker,
                    "value": str(item.value) if settings.store_health_fact_values else None,
                    "unit": item.unit,
                    "observed_at": item.report_date.isoformat() if item.report_date else None,
                    "page": item.page_start,
                }
            )
        self.repo.add_health_fact_refs(fact_rows)
        return response

