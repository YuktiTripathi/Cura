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
from app.contracts.common import IntentType, KnowledgeScope
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
from app.retrieval.medical import render_medical_evidence_answer, retrieve_medical_evidence
from app.pipeline.provenance import build_user_provenance, internal_provenance
from app.documents.lab_answer import evidence_from_value, extract_lab_hits, render_lab_answer
from app.documents.retrieval import DocumentRetriever
from app.documents.service import DocumentService
from app.documents.value_extraction import extract_keys_present, extract_marker_from_text
from app.pipeline.cross_source import (
    CrossSourceComparator,
    extracted_to_source,
    marker_to_source,
    render_comparison,
)
from app.pipeline.intent import NAMES, is_personal_utterance, requires_personal_record
from app.pipeline.lab_parameters import expand_requested_keys, primary_lab_key, retrieval_keys
from app.pipeline.claim_check import ClaimVerdict, check_claims
from app.pipeline.followup_i18n import localize_followups
from app.pipeline.language import LanguageCode, resolve_response_language
from integrations.supershyft.db import DB_NO_RECORDS, DB_PROVIDER_NOT_CALLED
from app.core.errors import LLMUnavailableError, ProviderUnavailableError
from app.db.repositories import ConversationRepository
from app.llm.factory import get_llm_client
from app.llm.structured import looks_like_structured_json, public_answer_text
from app.memory.conversation import FollowUpMemory
from app.pipeline.context_builder import ContextBuilder
from app.pipeline.personalized_followups import PersonalizedFollowUpEngine, build_inventory
from app.pipeline.prompt_builder import PromptBuilder
from app.pipeline.conversation_title import conversation_title
from app.routing.jev_router import resolve_plan
from app.pipeline.renderer import DeterministicRenderer, render_bio_ai_score_list
from app.pipeline.safety import SafetyLayer
from app.pipeline.grounding import GroundingChecker
from app.pipeline.recommendation_engine import RecommendationEngine
from app.providers.registry import ProviderRegistry

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
        self.safety = SafetyLayer()
        self.grounding = GroundingChecker()
        self.recommendations = RecommendationEngine()
        self.followups = PersonalizedFollowUpEngine()
        self.llm = get_llm_client()

    def chat(self, principal: AuthenticatedPrincipal, payload: ChatRequest, request_id: str) -> ChatResponse:
        self._eval_turn = {"principal": principal, "payload": payload, "request_id": request_id}
        response = self._execute_chat(principal, payload, request_id)
        return self._record_evaluation(response)

    def _execute_chat(self, principal: AuthenticatedPrincipal, payload: ChatRequest, request_id: str) -> ChatResponse:
        started = time.perf_counter()
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

        prior_topic, prior_name = self.memory.resolve_topic(conv, payload.message)
        prior_personal = self.memory.prior_was_personal(conv)
        previous_user_message = self.memory.last_user_message(conv)
        previous_intent = self.memory.last_user_intent(conv)
        conversation_summary = self.memory.semantic_summary(conv)
        doc_svc = DocumentService(self.db)
        listed_docs = doc_svc.list_for_user(principal.subject_id)
        completed_docs = [d for d in listed_docs if d.extraction_status == "completed"]
        detection, response_lang, new_pref = resolve_response_language(
            message=payload.message,
            language_mode=payload.language_mode,
            requested=payload.language,
            conversation_pref=getattr(conv, "language_preference", None),
        )
        if new_pref and new_pref != LanguageCode.auto:
            self.repo.update_language_preference(conv, new_pref.value)
        plan, jev_trace = resolve_plan(
            payload.message,
            conversation_summary=conversation_summary,
            previous_user_message=previous_user_message,
            previous_intent=previous_intent,
            follow_up_topic=prior_topic,
            follow_up_name=prior_name,
            prior_personal=prior_personal,
            document_ids=payload.document_ids,
            uploaded_document_count=len(completed_docs),
            prior_source_mode=getattr(conv, "last_source_mode", None),
            context_ref=payload.context_ref,
        )

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
        self._eval_turn["conv"] = conv
        self._eval_turn["plan"] = plan
        self._eval_turn["jev_trace"] = jev_trace
        self._eval_turn["medical"] = []

        def _meta(**extra) -> ChatMeta:
            base = dict(
                intent=plan.intent.value,
                answer_depth=plan.answer_depth.value,
                request_id=request_id,
                detected_language=detection.language.value,
                response_language=response_lang.value,
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
            )
            base.update(extra)
            return ChatMeta(**base)

        pre_safety = self.safety.check_input(payload.message)
        if pre_safety.blocked:
            answer = pre_safety.answer or "I can't help with that request."
            self.repo.add_message(conv, "user", payload.message, intent=plan.intent.value)
            self.repo.add_message(conv, "assistant", answer, intent=plan.intent.value)
            return ChatResponse(
                conversation_id=conv.id,
                answer=answer,
                evidence=[],
                follow_ups=[],
                meta=_meta(
                    status="safety_block",
                    llm_mode="none",
                    knowledge_scope=plan.knowledge_scope.value,
                    sources_used=[],
                    safety_flags=pre_safety.flags or [],
                    escalation=pre_safety.escalation,
                    db_status=DB_PROVIDER_NOT_CALLED,
                ),
            )

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

        if plan.needs_cross_source:
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
            )

        use_docs = bool(payload.document_ids or plan.needs_user_uploaded)
        if plan.needs_general and not plan.needs_cross_source and not plan.needs_user_uploaded:
            use_docs = False

        if use_docs:
            resolved = list(payload.document_ids)
            if not resolved:
                last = getattr(conv, "last_document_id", None)
                if last:
                    resolved = [last]
                elif len(completed_docs) == 1:
                    resolved = [completed_docs[0].document_id]
                elif len(completed_docs) > 1:
                    answer = "I can use your uploaded reports. Which uploaded report would you like me to use?"
                    self.repo.add_message(conv, "user", payload.message, intent=plan.intent.value)
                    self.repo.add_message(conv, "assistant", answer, intent=plan.intent.value)
                    return ChatResponse(
                        conversation_id=conv.id,
                        answer=answer,
                        evidence=[],
                        follow_ups=[],
                        meta=_meta(status="document_ambiguous", llm_mode="none", sources_used=["user_uploaded"], document_retrieval_called=False, knowledge_scope="user_uploaded"),
                    )
                else:
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
            pending = [d for d in docs if d.extraction_status in {"not_started", "processing"}]
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
                from app.retrieval.documents import retrieve_structured_documents

                structured_docs, structured_ev, used_stored = retrieve_structured_documents(
                    self.db, principal, plan, resolved
                )
                lookup_key = primary_lab_key(payload.message)
                value_lookup = bool(re.search(r"\bwhat(?:'s| is| was) my\b", payload.message, re.I))
                if structured_ev and lookup_key and value_lookup:
                    from app.documents.value_extraction import ExtractedValue

                    extracted = []
                    for ev in structured_ev:
                        if ev.value is None:
                            continue
                        low = high = None
                        if ev.reference_range:
                            parts = re.findall(r"[0-9]+(?:\.[0-9]+)?", ev.reference_range)
                            if len(parts) >= 2:
                                low, high = float(parts[0]), float(parts[1])
                        extracted.append(
                            ExtractedValue(
                                parameter=(ev.marker or "").lower().replace(" ", "_"),
                                name=ev.marker or "marker",
                                value=ev.value,
                                unit=ev.unit,
                                source_text=ev.excerpt or "",
                                page=ev.page_start,
                                date=ev.report_date,
                                date_kind="report",
                                reference_low=low,
                                reference_high=high,
                                confidence="high",
                            )
                        )
                    answer = render_lab_answer(extracted, payload.message)
                    if answer:
                        preferred = next((ev for ev in structured_ev if ev.value is not None), structured_ev[0])
                        evidence = [
                            EvidenceItem(
                                evidence_id=preferred.evidence_id,
                                report_id=preferred.report_id,
                                report_type="user_uploaded",
                                report_date=preferred.report_date,
                                source="user_uploaded",
                                document_id=preferred.document_id,
                                filename=preferred.filename,
                                page_start=preferred.page_start,
                                excerpt=preferred.excerpt,
                                marker=preferred.marker,
                                value=preferred.value,
                                unit=preferred.unit,
                                reference_range=preferred.reference_range,
                            )
                        ]
                        status = "document_retrieved"
                        answer, document_safety_flags = self.safety.review(answer, payload.message)
                        self.repo.add_message(conv, "user", payload.message, intent=plan.intent.value)
                        self.repo.add_message(conv, "assistant", answer, intent=plan.intent.value)
                        self.repo.update_source_mode(conv, "user_uploaded", resolved[0])
                        logger.info(
                            "document_structured_hit used_stored=%s reparsed_pdf=false count=%s",
                            used_stored,
                            len(structured_ev),
                        )
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
                    answer = excerpt
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
                context = self.builder.build(
                    principal, plan, db=self.db, document_ids=payload.document_ids
                )
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
            context = self.builder.build(
                principal, plan, db=self.db, document_ids=payload.document_ids
            )

        medical_hits = []
        if getattr(plan, "medical_evidence_required", False) or general_only:
            limit = 2 if re.search(r"\b(treatment|options|should|avoid|foods|diet|lifestyle|exercise)\b", payload.message, re.I) else 1
            medical_hits = retrieve_medical_evidence(payload.message, plan.topic, limit=limit)
            context.medical_passages = [
                f"{doc.name} ({doc.url}): {doc.excerpt}" for doc in medical_hits
            ]
        self._eval_turn["medical"] = medical_hits
        self._eval_turn["context"] = context

        llm_called = False
        llm_result = None
        medical_llm_latency_ms = None
        grounding_flags: list[str] = []
        recommendation_flags: list[str] = []
        escalation = None
        llm_mode = settings.resolved_llm_provider() if settings.enable_llm else "deterministic_mock"
        routing_note = None
        if jev_trace.decision:
            routing_note = jev_trace.decision.model_dump_json()
        llm_started = time.perf_counter()
        structured_bio_ai = (
            plan.intent == IntentType.bio_ai_score
            and bool(context.bio_ai_risks)
            and context.status != "ambiguous"
        )
        missing_bio_score = (
            plan.intent == IntentType.bio_ai_score
            and context.status != "ambiguous"
            and not context.bio_ai_risks
            and any(getattr(item, "reason", None) == "score_not_available" for item in context.missing)
        )
        if structured_bio_ai:
            answer = render_bio_ai_score_list(context.bio_ai_risks)
            llm_mode = "structured_bio_ai"
        elif missing_bio_score:
            answer = "Score not available in this report."
            llm_mode = "structured_bio_ai"
        elif general_only:
            corpus_answer = render_medical_evidence_answer(plan.topic, medical_hits)
            messages = self.prompts.build(
                context, conversation_summary, payload.message, response_lang, routing_note=routing_note
            )
            try:
                llm_result = self.llm.complete_structured(messages)
                answer = llm_result.answer
                llm_called = True
                llm_mode = settings.resolved_llm_provider() if settings.enable_llm else "deterministic_mock"
            except LLMUnavailableError:
                logger.warning("llm_unavailable request_id=%s", request_id)
                llm_called = True
                if corpus_answer:
                    answer = corpus_answer
                    llm_mode = "medical_corpus"
                else:
                    answer = general_knowledge_unavailable(response_lang)
                    llm_mode = "unavailable"
        elif settings.enable_llm:
            messages = self.prompts.build(
                context, conversation_summary, payload.message, response_lang, routing_note=routing_note
            )
            try:
                llm_result = self.llm.complete_structured(messages)
                answer = llm_result.answer
                llm_called = True
            except LLMUnavailableError:
                logger.warning("llm_unavailable request_id=%s", request_id)
                answer = self.renderer.render(payload.message, context)
                llm_mode = "deterministic_fallback"
        else:
            answer = self.renderer.render(payload.message, context)
        if llm_called:
            medical_llm_latency_ms = int((time.perf_counter() - llm_started) * 1000)

        approved_recommendations = list(context.recommendations)
        if llm_result and llm_result.recommendation_candidates:
            recommendation_result = self.recommendations.validate(
                llm_result.recommendation_candidates,
                context,
            )
            approved_recommendations.extend(recommendation_result.approved)
            recommendation_flags.extend(recommendation_result.flags)
            escalation = llm_result.escalation

        if llm_called and plan.needs_personal_data:
            unsupported = self.grounding.unsupported_personal_numbers(answer, context)
            if unsupported:
                grounding_flags.append("unsupported_personal_numbers")
                logger.warning(
                    "grounding_fallback request_id=%s unsupported_number_count=%s",
                    request_id,
                    len(unsupported),
                )
                answer = self.renderer.render(payload.message, context)
        if medical_hits or general_only:
            answer, medical_flags = self.grounding.sanitize_medical_answer(answer, medical_hits)
            grounding_flags.extend(medical_flags)
            if medical_hits:
                for _claim, verdict in check_claims(answer, medical_hits):
                    if verdict in {ClaimVerdict.UNSUPPORTED, ClaimVerdict.CONTRADICTED}:
                        grounding_flags.append(verdict.value.lower())
                if any(flag == "contradicted" for flag in grounding_flags):
                    from app.pipeline.claim_check import revise_unsupported_answer

                    answer, claim_flags = revise_unsupported_answer(answer, medical_hits)
                    grounding_flags.extend(claim_flags)

        critical_flags, critical_escalation = self.safety.scan_critical_context(context)
        if critical_escalation:
            escalation = critical_escalation
        answer, flags = self.safety.review(answer, payload.message)
        flags.extend(critical_flags)
        if llm_result:
            flags.extend(llm_result.safety_flags)
        flags = list(dict.fromkeys(flags))
        if flags:
            logger.info("safety_flags request_id=%s flags=%s", request_id, flags)

        inventory = build_inventory(principal, self.registry, plan, conv, context)
        suggestions = localize_followups(
            self.followups.generate(plan, answer, context, inventory),
            response_lang,
            context.resolved_topic_name or plan.topic_name,
        )
        if llm_result and llm_result.follow_up_questions:
            existing = {item.text.strip().lower() for item in suggestions}
            extras = []
            for question in llm_result.follow_up_questions:
                text = question.strip()
                if not text or text.lower() in existing:
                    continue
                if plan.knowledge_scope == KnowledgeScope.general and (
                    requires_personal_record(text) or is_personal_utterance(text)
                ):
                    continue
                extras.append(
                    FollowUpSuggestion(
                        text=text,
                        category="suggested",
                        knowledge_scope=plan.knowledge_scope.value,
                        requires_personal_context=plan.needs_personal_data,
                    )
                )
            suggestions = extras + suggestions
        if looks_like_structured_json(answer):
            answer = public_answer_text(answer)

        self.repo.add_message(conv, "user", payload.message, intent=plan.intent.value)
        self.repo.add_message(conv, "assistant", answer, intent=plan.intent.value)
        self.repo.update_follow_up(
            conv,
            context.resolved_topic or plan.topic,
            context.resolved_topic_name or plan.topic_name,
        )
        self.repo.update_context_state(
            conv,
            marker_code=context.resolved_topic or plan.topic,
            report_id=context.evidence[0].report_id if context.evidence else plan.report_id,
            summary=self.memory.updated_summary(
                conv,
                plan.intent.value,
                context.resolved_topic_name or plan.topic_name,
            ),
        )

        latency = int((time.perf_counter() - started) * 1000)
        subject_hash = hashlib.sha256(principal.subject_id.encode()).hexdigest()[:12]
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
        self.repo.update_source_mode(conv, "supershyft" if plan.needs_personal_data else "general")
        return ChatResponse(
            conversation_id=conv.id,
            answer=answer,
            evidence=evidence,
            follow_ups=suggestions,
            recommendations=approved_recommendations,
            meta=_meta(
                status=context.status,
                llm_mode=llm_mode,
                sources_used=sources,
                knowledge_scope=plan.knowledge_scope.value,
                sources_requested=requested,
                llm_called=llm_called,
                supershyft_called=bool(plan.needs_personal_data),
                document_retrieval_called=False,
                db_status=db_status,
                supershyft_record_count=len(evidence) if plan.needs_personal_data else 0,
                safety_flags=flags,
                recommendation_flags=recommendation_flags,
                grounding_flags=grounding_flags,
                escalation=escalation,
                model=settings.active_llm_model() if llm_called else None,
                provider=settings.resolved_llm_provider() if llm_called else None,
                input_tokens=(getattr(self.llm, "last_usage", {}) or {}).get("input_tokens") if llm_called else None,
                output_tokens=(getattr(self.llm, "last_usage", {}) or {}).get("output_tokens") if llm_called else None,
                medical_llm_latency_ms=medical_llm_latency_ms,
                retrieval_used=bool(plan.needs_personal_data or plan.needs_user_uploaded),
                retrieval_sources=sources,
                ihr_queried=bool(plan.needs_personal_data),
                documents_queried=bool(plan.needs_user_uploaded),
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
    ):
        resolved = list(payload.document_ids or [])
        last = getattr(conv, "last_document_id", None)
        if not resolved:
            if last:
                resolved = [last]
            elif len(completed_docs) == 1:
                resolved = [completed_docs[0].document_id]
            elif len(completed_docs) > 1:
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
            else:
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
        if any(d.extraction_status in {"not_started", "processing"} for d in docs):
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
        hits = DocumentRetriever(self.db).retrieve(
            principal.subject_id, query, document_ids=resolved, limit=5
        )
        uploaded_keys: set[str] = set()
        ext = None
        ext_hit = None
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

        if ext is None:
            from app.documents.value_extraction import ExtractedValue

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
            filename = ext_hit.filename if ext_hit else (docs[0].original_filename if docs else "uploaded.pdf")
            doc_id = ext_hit.document_id if ext_hit else resolved[0]
        else:
            filename = ext_hit.filename if ext_hit else docs[0].original_filename
            doc_id = ext_hit.document_id if ext_hit else resolved[0]

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
        answer = render_comparison(
            result,
            why="why" in lower and "different" in lower,
            newer="newer" in lower,
        )
        llm_mode = "none"
        if settings.enable_llm:
            try:
                messages = self.prompts.build(
                    context,
                    self.memory.semantic_summary(conv),
                    payload.message,
                    response_lang,
                )
                answer = self.llm.complete_structured(messages).answer
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
        suggestions = localize_followups(
            self.followups.generate(plan, answer, context, inventory),
            LanguageCode.en,
            plan.topic_name,
        )
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
                model=settings.active_llm_model() if llm_mode not in {"none", "deterministic_fallback"} else None,
                provider=settings.resolved_llm_provider() if llm_mode not in {"none", "deterministic_fallback"} else None,
                retrieval_used=True,
                retrieval_sources=["supershyft", "user_uploaded"],
                ihr_queried=True,
                documents_queried=True,
            ),
        )

    def _record_evaluation(self, response: ChatResponse) -> ChatResponse:
        turn = getattr(self, "_eval_turn", None) or {}
        conv = turn.get("conv")
        plan = turn.get("plan")
        principal = turn.get("principal")
        payload = turn.get("payload")
        if conv is None or plan is None or principal is None or payload is None:
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
        medical = turn.get("medical") or []
        jev_trace = turn.get("jev_trace")
        response.provenance = build_user_provenance(plan, list(response.evidence or []), medical)
        if settings.is_development:
            meta.debug = {
                "retrieval_status": meta.retrieval_status,
                "source": list(meta.retrieval_sources or meta.sources_used or []),
                "operation": meta.jev_operation or plan.intent.value,
                "ihr_queried": meta.ihr_queried,
                "documents_queried": meta.documents_queried,
                "evidence_count": len(response.evidence or []),
                "report_id": [item.report_id for item in (response.evidence or []) if item.report_id][:8],
                "report_date": [
                    item.report_date.isoformat()
                    for item in (response.evidence or [])
                    if item.report_date
                ][:8],
                "internal_provenance": internal_provenance(plan, list(response.evidence or []), medical),
                "personal_reference": getattr(plan, "personal_reference", False),
                "personal_data_required": plan.needs_personal_data,
                "medical_evidence_required": getattr(plan, "medical_evidence_required", False),
                "data_sources": list(getattr(plan, "data_sources", []) or []),
                "user_message": (payload.message or "")[:160],
                "jev_intent": meta.jev_intent,
                "jev_entities": list((jev_trace.decision.requested_entities if jev_trace and jev_trace.decision else []) or []),
                "query_plan_topic": plan.topic,
                "query_plan_intent": plan.intent.value,
                "requested_metrics": list(plan.requested_metrics or []),
                "time_operation": plan.time_operation,
                "fallback_reason": plan.fallback_reason,
                "retrieval_topic": plan.topic,
                "requested_biomarkers": expand_requested_keys(plan.requested_metrics or ([plan.topic] if plan.topic else [])),
                "retrieved_biomarkers": [
                    getattr(m, "key", None) for m in getattr(turn.get("context"), "markers", []) or [] if getattr(m, "key", None)
                ],
                "context_biomarkers": [
                    getattr(m, "key", None) for m in getattr(turn.get("context"), "markers", []) or [] if getattr(m, "key", None)
                ],
                "source": "blood_report" if plan.needs_blood else ("bio_ai_report" if plan.needs_bio_ai else "general"),
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
                    "value": str(item.value),
                    "unit": item.unit,
                    "observed_at": item.report_date.isoformat() if item.report_date else None,
                    "page": item.page_start,
                }
            )
        self.repo.add_health_fact_refs(fact_rows)
        return response
