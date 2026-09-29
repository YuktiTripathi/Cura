"""CURA-owned semantic validation for untrusted Jev routing decisions."""

from __future__ import annotations

from app.routing.schemas import (
    JevDecision,
    JevIntent,
    JevOperation,
    JevRoutingState,
    JevSource,
    JevTimeRange,
)


class JevDecisionValidationError(ValueError):
    pass


_GENERAL_INTENTS = {
    JevIntent.casual_conversation,
    JevIntent.fitness_question,
    JevIntent.general_health_question,
    JevIntent.medication_question,
    JevIntent.symptom_question,
    JevIntent.preventive_health_question,
    JevIntent.general_information,
}
# nutrition_question / lifestyle_question are dual-use: general education unless
# the request is record-dependent. They are demoted below rather than treated as
# always-general, so a validated personalized nutrition/lifestyle route can stand.
_PERSONAL_INTENTS = {
    JevIntent.personal_profile_lookup,
    JevIntent.lab_result_lookup,
    JevIntent.lab_result_interpretation,
    JevIntent.bio_ai_report_lookup,
    JevIntent.bio_ai_report_interpretation,
    JevIntent.health_trend_analysis,
    JevIntent.questionnaire_lookup,
    JevIntent.questionnaire_interpretation,
}
_PERSONAL_SOURCES = {
    JevSource.profile,
    JevSource.assessment,
    JevSource.questionnaire,
    JevSource.blood_reports,
    JevSource.lab_results,
    JevSource.bio_ai_report,
    JevSource.bio_ai_trends,
    JevSource.health_metrics,
    JevSource.nutrition,
    JevSource.multiple_sources,
}
_HISTORICAL_SCOPES = {
    JevTimeRange.previous,
    JevTimeRange.historical,
    JevTimeRange.three_months,
    JevTimeRange.six_months,
    JevTimeRange.twelve_months,
    JevTimeRange.custom,
}


def validate_jev_decision(
    decision: JevDecision,
    state: JevRoutingState,
    *,
    deterministic_requires_personal: bool,
) -> JevDecision:
    """Validate and safely normalize Jev output before QueryPlan mapping.

    Jev's questions are answered independently, so CURA treats the request type
    and deterministic record-dependency guard as authoritative constraints.
    """
    if decision.intent == JevIntent.clarification or decision.requires_clarification:
        return decision.model_copy(
            update={
                "intent": JevIntent.clarification,
                "source": JevSource.none,
                "operation": JevOperation.clarify,
                "requires_personal_data": False,
                "requires_historical_data": False,
                "requires_document_search": False,
                "time_range": JevTimeRange.none,
                "requires_clarification": True,
                "clarification_question": decision.clarification_question
                or "Would you like general information, your latest result, or a comparison with previous results?",
            }
        )

    if decision.intent == JevIntent.unsupported:
        return decision.model_copy(
            update={
                "source": JevSource.none,
                "operation": JevOperation.none,
                "requires_personal_data": False,
                "requires_historical_data": False,
                "requires_document_search": False,
                "time_range": JevTimeRange.none,
            }
        )

    if decision.intent in {
        JevIntent.questionnaire_lookup,
        JevIntent.questionnaire_interpretation,
    } and "questionnaires" not in state.supported_capabilities:
        return JevDecision(
            intent=JevIntent.clarification,
            source=JevSource.none,
            operation=JevOperation.clarify,
            requires_clarification=True,
            clarification_question=(
                "Questionnaire retrieval is not available here yet. "
                "Would you like general information instead?"
            ),
        )

    if decision.intent in _GENERAL_INTENTS:
        if deterministic_requires_personal:
            raise JevDecisionValidationError("Jev classified a record-dependent request as general")
        return decision.model_copy(
            update={
                "source": JevSource.none,
                "operation": JevOperation.general_answer,
                "requires_personal_data": False,
                "requires_historical_data": False,
                "requires_document_search": False,
                "time_range": JevTimeRange.none,
            }
        )

    if decision.intent in {JevIntent.nutrition_question, JevIntent.lifestyle_question} and not deterministic_requires_personal:
        return decision.model_copy(
            update={
                "source": JevSource.none,
                "operation": JevOperation.general_answer,
                "requires_personal_data": False,
                "requires_historical_data": False,
                "requires_document_search": False,
                "time_range": JevTimeRange.none,
            }
        )

    if decision.intent in _PERSONAL_INTENTS and not decision.requires_personal_data:
        raise JevDecisionValidationError("Personal request type omitted personal-data dependency")

    if deterministic_requires_personal and not (
        decision.requires_personal_data or decision.requires_document_search
    ):
        raise JevDecisionValidationError("Decision conflicts with record-dependent request")

    if not deterministic_requires_personal and decision.requires_personal_data:
        raise JevDecisionValidationError("Decision would retrieve personal data for a general request")

    if decision.requires_personal_data and decision.source not in _PERSONAL_SOURCES:
        raise JevDecisionValidationError("Personal-data decision selected a non-personal source")

    if not decision.requires_personal_data and decision.source in _PERSONAL_SOURCES:
        raise JevDecisionValidationError("Personal source selected without personal-data dependency")

    if decision.requires_document_search:
        if decision.source not in {JevSource.uploaded_documents, JevSource.multiple_sources}:
            raise JevDecisionValidationError("Document search selected an incompatible source")
        if not (state.selected_document_count or state.uploaded_document_available):
            return JevDecision(
                intent=JevIntent.clarification,
                source=JevSource.none,
                operation=JevOperation.clarify,
                requires_clarification=True,
                clarification_question="Please upload or select the document you want me to use.",
            )

    if decision.intent == JevIntent.uploaded_document_query and not decision.requires_document_search:
        raise JevDecisionValidationError("Uploaded-document request omitted document dependency")

    if decision.requires_historical_data:
        if not decision.requires_personal_data:
            raise JevDecisionValidationError("Historical data requires personal-data authorization")
        if decision.time_range not in _HISTORICAL_SCOPES:
            raise JevDecisionValidationError("Historical decision has no historical time scope")
        if decision.operation not in {
            JevOperation.trend,
            JevOperation.compare,
            JevOperation.lookup,
            JevOperation.retrieve_and_explain,
        }:
            raise JevDecisionValidationError("Historical decision selected an incompatible operation")

    if decision.operation == JevOperation.general_answer and decision.requires_personal_data:
        raise JevDecisionValidationError("General operation cannot require personal data")

    return decision
