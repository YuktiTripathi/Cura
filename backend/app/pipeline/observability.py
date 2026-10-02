"""Processing-stage events and request timing. Never exposes model names or chain-of-thought."""

from __future__ import annotations

import time
from collections.abc import Callable

from app.contracts.presentation import AnswerPreview
from app.contracts.turn_experience import ExperienceBlock
from app.contracts.processing import ProcessingEvent, ProcessingStage, RequestFamily, TimingReport
from app.contracts.query import QueryPlan

_STAGE_KEYS = {
    ProcessingStage.request_received: "request.received",
    ProcessingStage.planning: "planning",
    ProcessingStage.fetching_personal_data: "health.fetch",
    ProcessingStage.fetching_blood_data: "blood.fetch",
    ProcessingStage.fetching_bioai_data: "bioai.fetch",
    ProcessingStage.fetching_questionnaire: "questionnaire.fetch",
    ProcessingStage.fetching_history: "history.fetch",
    ProcessingStage.reading_document: "document.read",
    ProcessingStage.retrieving_document_section: "document.section",
    ProcessingStage.checking_medical_evidence: "medical.fetch",
    ProcessingStage.comparing_results: "compare.results",
    ProcessingStage.analyzing_trends: "trend.analyze",
    ProcessingStage.personalizing: "personalize",
    ProcessingStage.reasoning: "reason",
    ProcessingStage.checking_safety: "safety.check",
    ProcessingStage.composing_response: "response.compose",
    ProcessingStage.complete: "complete",
}


def request_family(plan: QueryPlan | None, *, follow_up: bool = False) -> RequestFamily:
    if follow_up:
        return RequestFamily.followup
    if plan is None:
        return RequestFamily.personal
    ops = {str(item).upper() for item in (plan.operations or [])}
    if "RECOMMEND" in ops or (plan.operation or "").upper() == "RECOMMEND":
        return RequestFamily.package
    if plan.needs_cross_source:
        return RequestFamily.cross
    if plan.needs_user_uploaded and not plan.needs_supershyft:
        return RequestFamily.document
    if plan.history or (plan.time_scope or "") in {"historical", "trend"}:
        return RequestFamily.trend
    if plan.needs_bio_ai and not plan.needs_blood:
        return RequestFamily.bioai
    if plan.needs_questionnaire and not plan.needs_blood and not plan.needs_bio_ai:
        return RequestFamily.questionnaire
    if plan.needs_blood:
        return RequestFamily.blood
    if plan.needs_general and not plan.needs_personal_data:
        return RequestFamily.general
    if "PRIORITIZE" in ops:
        return RequestFamily.priority
    if plan.needs_personal_data:
        return RequestFamily.personal
    return RequestFamily.general


def message_key_for(stage: ProcessingStage, family: RequestFamily, *, follow_up: bool = False) -> str:
    if follow_up and stage == ProcessingStage.planning:
        return "followup.context"
    if follow_up and stage in {ProcessingStage.fetching_blood_data, ProcessingStage.fetching_personal_data}:
        return "followup.fetch"
    base = _STAGE_KEYS.get(stage, stage.value.lower())
    if family == RequestFamily.blood and stage == ProcessingStage.reasoning:
        return "blood.reason"
    if family == RequestFamily.bioai and stage == ProcessingStage.reasoning:
        return "bioai.reason"
    if family == RequestFamily.document and stage == ProcessingStage.reasoning:
        return "document.reason"
    if family == RequestFamily.general and stage == ProcessingStage.planning:
        return "general.understand"
    return base


class ProgressEmitter:
    def __init__(
        self,
        callback: Callable[[ProcessingEvent], None] | None = None,
        preview_callback: Callable[[AnswerPreview], None] | None = None,
        experience_callback: Callable[[ExperienceBlock], None] | None = None,
    ):
        self._callback = callback
        self._preview_callback = preview_callback
        self._experience_callback = experience_callback
        self._started = time.perf_counter()
        self._last: ProcessingStage | None = None
        self.events: list[ProcessingEvent] = []
        self.family = RequestFamily.personal
        self.follow_up = False
        self.timing = TimingReport()
        self._marks: dict[str, float] = {}

    def set_context(self, plan: QueryPlan | None, *, follow_up: bool = False) -> None:
        self.follow_up = follow_up
        self.family = request_family(plan, follow_up=follow_up)

    def emit(self, stage: ProcessingStage, *, plan: QueryPlan | None = None) -> ProcessingEvent:
        if plan is not None:
            self.set_context(plan, follow_up=self.follow_up)
        if stage == self._last:
            return self.events[-1] if self.events else ProcessingEvent(
                stage=stage, message_key=message_key_for(stage, self.family, follow_up=self.follow_up)
            )
        self._last = stage
        event = ProcessingEvent(
            stage=stage,
            message_key=message_key_for(stage, self.family, follow_up=self.follow_up),
            family=self.family,
            follow_up=self.follow_up,
            elapsed_ms=int((time.perf_counter() - self._started) * 1000),
        )
        self.events.append(event)
        if self._callback is not None:
            self._callback(event)
        return event

    def preview(self, preview: AnswerPreview) -> None:
        """Send already-retrieved values to a streaming client before reasoning starts."""
        if self._preview_callback is not None and preview.findings:
            self._preview_callback(preview)

    def experience_block(self, block: ExperienceBlock) -> None:
        """Send an already-validated semantic response block to a streaming client."""
        if self._experience_callback is not None:
            self._experience_callback(block)

    def mark(self, name: str) -> None:
        self._marks[name] = time.perf_counter()

    def measure(self, name: str) -> int:
        started = self._marks.pop(name, None)
        if started is None:
            return 0
        ms = int((time.perf_counter() - started) * 1000)
        self.timing.marks[name] = ms
        return ms

    def finish(self, *, llm_calls: int = 0, input_tokens: int | None = None, output_tokens: int | None = None) -> TimingReport:
        self.timing.total_ms = int((time.perf_counter() - self._started) * 1000)
        self.timing.planning_ms = self.timing.marks.get("planning")
        self.timing.database_retrieval_ms = self.timing.marks.get("retrieval")
        self.timing.context_build_ms = self.timing.marks.get("context")
        self.timing.document_retrieval_ms = self.timing.marks.get("document")
        self.timing.reasoner_ms = self.timing.marks.get("reasoner")
        self.timing.validation_ms = self.timing.marks.get("validation")
        self.timing.response_compose_ms = self.timing.marks.get("compose")
        self.timing.llm_calls = llm_calls
        self.timing.input_tokens = input_tokens
        self.timing.output_tokens = output_tokens
        return self.timing
