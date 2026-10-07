"""OpenRouter Jev Decisions API adapter.

This client sends routing state only. It never receives credentials, health
records, database metadata, or authority to execute a query.
"""

from __future__ import annotations

import time
from typing import Any

import httpx
from pydantic import ValidationError

from app.contracts.common import parse_complexity, parse_model_tier, parse_reasoning_depth
from app.core.circuit_breaker import CircuitOpenError, jev_breaker
from app.core.config import settings
from app.core.errors import LLMUnavailableError
from app.core.http import get_http_client
from app.routing.schemas import (
    JevChoiceAnswer,
    JevDecision,
    JevDecisionsResponse,
    JevIntent,
    JevNoulAnswer,
    JevOperation,
    JevRoutingState,
    JevSource,
    JevTimeRange,
)


_REQUEST_TYPE = {
    "type": "choice",
    "instructions": (
        "Classify the current user request. Decide what the request asks CURA to do, "
        "not merely which health topic it mentions. General education and lifestyle "
        "advice remain general even when phrased with 'my'. "
        "If turn_type is ANSWER_TO_ASSISTANT, continue the prior personal interpretation "
        "using new_context; do not reclassify it as a brand-new general_health_question. "
        "If turn_type is REFERENCE_RESOLUTION or FOLLOW_UP_QUESTION, keep the active topic "
        "and entities from conversation state and retrieve personal records again."
    ),
    "criteria": {
        "casual_conversation": "Greeting, thanks, or casual conversation without a health-information request.",
        "personal_profile_lookup": "Request for a value from this user's personal profile.",
        "lab_result_lookup": "Request to retrieve this user's measured lab value or blood report result.",
        "lab_result_interpretation": "Request to assess or explain this user's measured lab result.",
        "bio_ai_report_lookup": "Request to retrieve a Bio-AI report or score belonging to this user.",
        "bio_ai_report_interpretation": "Request to explain or assess this user's Bio-AI report.",
        "health_trend_analysis": "Request to compare or analyze this user's values across time.",
        "questionnaire_lookup": (
            "Request to retrieve this user's stored questionnaire responses "
            "(what they answered/reported). Not a lab lookup. "
            "'What is my sleep?' without questionnaire wording is not this intent."
        ),
        "questionnaire_interpretation": "Request to interpret this user's questionnaire responses.",
        "uploaded_document_query": "Request that must use a user-selected or uploaded document.",
        "nutrition_question": "Nutrition or diet education; use personal data only when the user explicitly asks for personalized advice based on their records.",
        "lifestyle_question": "General lifestyle or behavior-change education; use personal data only when the user explicitly asks for personalized advice based on their records.",
        "fitness_question": "General exercise or fitness education that does not require personal records.",
        "general_health_question": "General medical education answerable without this user's records.",
        "medication_question": "General medication information, not a request to prescribe or change a dose.",
        "symptom_question": "General symptom information not requiring retrieval of this user's records.",
        "preventive_health_question": "General prevention or screening information.",
        "medical_risk_question": "General explanation of medical risk, unless explicitly based on this user's records.",
        "general_information": "Non-medical general information supported by the assistant.",
        "unsupported": "Outside CURA's supported informational and personal-health capabilities.",
        "clarification": "The requested operation or source is genuinely ambiguous and cannot be executed safely.",
    },
}

_SOURCE = {
    "type": "choice",
    "instructions": (
        "Select the source required to answer. Select none when general knowledge is sufficient. "
        "A health topic or first-person wording alone does not require a personal source."
    ),
    "criteria": {
        "profile": "Authenticated user's profile.",
        "assessment": "A personal health assessment other than Bio-AI.",
        "questionnaire": "Authenticated user's questionnaire responses.",
        "blood_reports": "Authenticated user's blood report records.",
        "lab_results": "Authenticated user's measured laboratory values.",
        "bio_ai_report": "Authenticated user's Bio-AI report.",
        "bio_ai_trends": "Multiple authenticated-user Bio-AI reports over time.",
        "health_metrics": "Authenticated user's longitudinal health metrics.",
        "uploaded_documents": "User-owned uploaded documents selected or referenced in the conversation.",
        "nutrition": "Recorded personal nutrition/preferences; not general nutrition knowledge.",
        "none": "No personal or uploaded data is needed; answer from general knowledge.",
        "multiple_sources": "The user explicitly requests comparison or synthesis across source types.",
    },
}

_OPERATION = {
    "type": "choice",
    "instructions": "Select the operation CURA must perform to answer the current request.",
    "criteria": {
        "none": "No supported operation is required.",
        "lookup": "Retrieve a current or specified personal value/report.",
        "retrieve_and_explain": "Retrieve personal evidence and explain it.",
        "trend": "Analyze change over a time period.",
        "compare": "Compare two reports, periods, or source types.",
        "summarize": "Summarize a selected report or set of personal records.",
        "interpret": "Interpret retrieved personal evidence.",
        "general_answer": "Answer using general knowledge only.",
        "clarify": "Ask a focused clarification before retrieval.",
    },
}

_TIME_SCOPE = {
    "type": "choice",
    "instructions": "Select only the time scope explicitly requested or clearly implied.",
    "criteria": {
        "none": "No personal time scope is needed.",
        "latest": "Latest or current personal record.",
        "previous": "The immediately previous personal record.",
        "historical": "Historical records without a specific fixed interval.",
        "3_months": "The last three months.",
        "6_months": "The last six months.",
        "12_months": "The last twelve months.",
        "custom": "An explicit time period not represented by another option.",
    },
}

_BOOLEAN_QUESTIONS = {
    "requires_personal_data": {
        "type": "noul",
        "instructions": "Does answering require information from this authenticated user's records?",
        "criteria": {
            "true": "The answer depends on this user's measured result, report, questionnaire responses, profile, history, trend, or recorded preferences.",
            "false": "The request is answerable from general knowledge. Words such as my, LDL, blood, or health alone are insufficient.",
        },
    },
    "requires_historical_data": {
        "type": "noul",
        "instructions": "Does answering require more than the latest personal record or a previous/historical comparison?",
        "criteria": {
            "true": "The user asks for previous, change, trend, history, or comparison over time.",
            "false": "No historical personal records are needed.",
        },
    },
    "requires_document": {
        "type": "noul",
        "instructions": "Must CURA search a user-owned uploaded document to answer?",
        "criteria": {
            "true": "The user explicitly refers to an uploaded/selected PDF or document.",
            "false": "No uploaded document is required.",
        },
    },
    "requires_clarification": {
        "type": "noul",
        "instructions": "Is a focused clarification required before CURA can safely select an operation and source?",
        "criteria": {
            "true": "Multiple materially different supported interpretations remain and context does not resolve them.",
            "false": "The requested operation and source are clear enough to proceed.",
        },
    },
    "reasoning_required": {
        "type": "noul",
        "instructions": "Does the answer require medical reasoning beyond restating a retrieved value?",
        "criteria": {
            "true": "The user asks why, how findings relate, interpretation, or advice.",
            "false": "A retrieved fact or short definition is sufficient.",
        },
    },
    "pdf_analysis_required": {
        "type": "noul",
        "instructions": "Does answering require analyzing an uploaded diagnostic document beyond a single extracted value?",
        "criteria": {
            "true": "The user asks to analyze, summarize, or relate multiple findings in an uploaded report.",
            "false": "No uploaded-document analysis is required, or only a single extracted value is needed.",
        },
    },
}

_COMPLEXITY = {
    "type": "choice",
    "instructions": (
        "Estimate semantic complexity. Do not choose a vendor or model name. "
        "LOW = single retrieved value, a date, a list of markers, or a deterministic calculation. "
        "MEDIUM = a patient-facing explanation or modest multi-marker interpretation. "
        "HIGH = multi-domain, multi-source, longitudinal, contradictory, or complete-health synthesis."
    ),
    "criteria": {
        "LOW": "Single retrieved value, listing, report date, source identification, or deterministic trend/derived math.",
        "MEDIUM": "Patient-friendly explanation, domain interpretation, routine nutrition, or two-to-four marker reasoning.",
        "HIGH": "Several domains or sources, history plus synthesis, contradictions, or a complete health scenario.",
    },
}

_MODEL_TIER = {
    "type": "choice",
    "instructions": (
        "Select a provider-independent capability tier. Do not return a provider, vendor, or model ID. "
        "DETERMINISTIC = no answer model. FAST_REASONING = internal planning only, not a medical answer. "
        "STANDARD_MEDICAL = default patient-facing medical reasoning. "
        "DEEP_MEDICAL_REASONING = reserved for high-complexity synthesis."
    ),
    "criteria": {
        "DETERMINISTIC": "Lookup, list, date, source, reference-range status, or deterministic calculation with no interpretation.",
        "FAST_REASONING": "Task planning, entity extraction, follow-up resolution, or conversation-state understanding only.",
        "STANDARD_MEDICAL": "General or personal biomarker explanation, domain review, routine nutrition, or modest multi-marker interpretation.",
        "DEEP_MEDICAL_REASONING": "Complete health scenario, multi-source synthesis, longitudinal pattern grouping, or balancing several explanations.",
    },
}

_REASONING_DEPTH = {
    "type": "choice",
    "instructions": (
        "NONE if the answer can be rendered from retrieved facts without a medical model. "
        "STANDARD for ordinary patient-facing interpretation. DEEP for high-complexity synthesis. "
        "Do not name a model."
    ),
    "criteria": {
        "NONE": "Deterministic retrieval or calculation.",
        "STANDARD": "Ordinary medical explanation.",
        "DEEP": "Multi-domain or contradictory evidence that must be balanced.",
    },
}


_REASONING_GOAL = {
    "type": "choice",
    "instructions": (
        "What is the user trying to accomplish? Judge the task, not the topic or exact wording. "
        "Pick the goal that should shape the reply."
    ),
    "criteria": {
        "LOOKUP": "Wants a stored fact or value (a result, a score, what they reported).",
        "EXPLAIN": "Wants the meaning of something, or how two facts fit together.",
        "CAUSES": "Wants possible reasons or explanations (why).",
        "ASSESS": "Wants a judgment: is it enough, okay, concerning, good or bad.",
        "COMPARE": "Wants change or difference over time or between reports.",
        "PRIORITIZE": "Wants a ranking: what matters most or what to do first.",
        "ACTION": "Wants next steps or how to improve something.",
        "SYNTHESIZE": "Wants an overall picture combining several findings or sources.",
        "RISK": "Wants implications or whether to worry.",
        "GENERAL_EDUCATION": "Wants general knowledge that does not depend on this user's data.",
        "DOCUMENT_LOOKUP": "Asks about an uploaded or selected document.",
        "FOLLOW_UP": "Depends on the previous turn to make sense.",
    },
}

_PERSONALIZATION = {
    "type": "choice",
    "instructions": "Does a useful answer depend on this user's own health data or reported habits?",
    "criteria": {
        "NONE": "General knowledge fully answers it.",
        "OPTIONAL": "General knowledge answers it; personal data could add context.",
        "REQUIRED": "The answer is about this user (their results, habits, priorities or situation).",
    },
}

_TEMPORAL = {
    "type": "choice",
    "instructions": "What time span of personal data does the answer need?",
    "criteria": {
        "NONE": "No personal data.",
        "CURRENT": "Only the latest data.",
        "HISTORICAL": "An older report or value.",
        "TREND": "Direction over several reports.",
        "COMPARISON": "A difference between two points in time.",
    },
}


class JevDecisionsClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: int | None = None,
    ) -> None:
        self.base_url = (base_url or settings.active_llm_base_url()).rstrip("/")
        self.api_key = api_key if api_key is not None else settings.active_llm_api_key()
        self.model = model or settings.jev_model
        self.timeout = timeout if timeout is not None else settings.jev_timeout_seconds

    @property
    def endpoint(self) -> str:
        base = self.base_url
        if base.endswith("/api/v1"):
            return f"{base[:-3]}/alpha/decisions"
        if base.endswith("/v1"):
            return f"{base[:-3]}/alpha/decisions"
        if base.endswith("/api"):
            return f"{base}/alpha/decisions"
        return f"{base}/api/alpha/decisions"

    def decide(self, state: JevRoutingState) -> tuple[JevDecision, JevDecisionsResponse]:
        if not self.api_key:
            raise LLMUnavailableError("OPENROUTER_API_KEY is not configured")
        try:
            jev_breaker.allow()
        except CircuitOpenError as exc:
            raise LLMUnavailableError("Jev Decisions is temporarily unavailable") from exc
        payload = {
            "model": self.model,
            "state": state.model_dump(mode="json", exclude_none=True),
            "questions": {
                "request_type": _REQUEST_TYPE,
                "data_source": _SOURCE,
                "operation": _OPERATION,
                "time_scope": _TIME_SCOPE,
                "complexity": _COMPLEXITY,
                "model_tier": _MODEL_TIER,
                "reasoning_depth": _REASONING_DEPTH,
                "reasoning_goal": _REASONING_GOAL,
                "personalization": _PERSONALIZATION,
                "temporal_requirement": _TEMPORAL,
                **_BOOLEAN_QUESTIONS,
            },
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        if settings.openrouter_http_referer:
            headers["HTTP-Referer"] = settings.openrouter_http_referer
        if settings.openrouter_app_title:
            headers["X-Title"] = settings.openrouter_app_title

        response: httpx.Response | None = None
        attempts = max(1, int(settings.llm_max_retries) + 1)
        client = get_http_client()
        for attempt in range(attempts):
            try:
                response = client.post(self.endpoint, headers=headers, json=payload, timeout=self.timeout)
            except httpx.HTTPError as exc:
                # A timed-out router call is not retried: the deterministic planner is the
                # fallback and costs milliseconds, a second attempt costs the full timeout.
                if attempt + 1 >= attempts or isinstance(exc, httpx.TimeoutException):
                    jev_breaker.record_failure()
                    raise LLMUnavailableError("Jev Decisions request failed") from exc
                time.sleep(0.1 * (attempt + 1))
                continue
            if response.status_code < 400:
                break
            if response.status_code not in {408, 429, 500, 502, 503, 504} or attempt + 1 >= attempts:
                jev_breaker.record_failure()
                raise LLMUnavailableError(f"Jev Decisions provider returned HTTP {response.status_code}")
            time.sleep(0.1 * (attempt + 1))

        if response is None:
            jev_breaker.record_failure()
            raise LLMUnavailableError("Jev Decisions request failed")
        try:
            parsed = JevDecisionsResponse.model_validate(response.json())
            decision = self._normalize(parsed)
        except (ValueError, ValidationError, KeyError) as exc:
            jev_breaker.record_failure()
            raise LLMUnavailableError("Jev Decisions returned an invalid response") from exc
        jev_breaker.record_success()
        return decision, parsed

    @staticmethod
    def _normalize(response: JevDecisionsResponse) -> JevDecision:
        answers = response.answers
        request_type = _choice(answers, "request_type", JevIntent)
        source = _choice(answers, "data_source", JevSource)
        operation = _choice(answers, "operation", JevOperation)
        time_scope = _choice(answers, "time_scope", JevTimeRange)
        # Confidence is the primary request_type classification only.
        # Auxiliary fields (time_scope, operation, source) are independent and
        # must not min() a valid high-confidence route below the 0.80 gate.
        field_confidences = {
            key: answer.confidence
            for key, answer in answers.items()
            if isinstance(answer, JevChoiceAnswer) and answer.confidence is not None
        }
        return JevDecision(
            intent=request_type,
            source=source,
            operation=operation,
            requires_personal_data=_noul(answers, "requires_personal_data"),
            requires_historical_data=_noul(answers, "requires_historical_data"),
            requires_document_search=_noul(answers, "requires_document"),
            # The explicit request/operation choices are authoritative. Jev's
            # parallel clarification noul cannot see those answers and is kept
            # for observability rather than allowed to overrule a clear route.
            requires_clarification=(
                request_type == JevIntent.clarification
                or operation == JevOperation.clarify
            ),
            time_range=time_scope,
            confidence=request_type_answer_confidence(answers),
            field_confidences=field_confidences,
            complexity=parse_complexity(_choice_text(answers, "complexity")),
            answer_model_tier=parse_model_tier(
                _choice_text(answers, "model_tier") or _choice_text(answers, "answer_model_tier")
            ),
            reasoning_depth=parse_reasoning_depth(_choice_text(answers, "reasoning_depth")),
            reasoning_required=_optional_noul(answers, "reasoning_required"),
            pdf_analysis_required=_optional_noul(answers, "pdf_analysis_required"),
            reasoning_goal=_allowed(answers, "reasoning_goal", _REASONING_GOAL["criteria"]),
            personalization=_allowed(answers, "personalization", _PERSONALIZATION["criteria"]),
            temporal_requirement=_allowed(answers, "temporal_requirement", _TEMPORAL["criteria"]),
        )


def request_type_answer_confidence(answers: dict[str, Any]) -> float | None:
    answer = answers.get("request_type")
    if not isinstance(answer, JevChoiceAnswer):
        return None
    return answer.confidence


def _choice(answers: dict[str, Any], key: str, enum_type):
    answer = answers.get(key)
    if not isinstance(answer, JevChoiceAnswer):
        raise ValueError(f"Missing choice answer: {key}")
    return enum_type(answer.choice)


def _noul(answers: dict[str, Any], key: str) -> bool:
    answer = answers.get(key)
    if not isinstance(answer, JevNoulAnswer):
        raise ValueError(f"Missing noul answer: {key}")
    # Noul is a probability for the true proposition; 0.5 is its binary boundary,
    # not an application confidence threshold.
    return answer.noul >= 0.5


def _choice_text(answers: dict[str, Any], key: str) -> str | None:
    answer = answers.get(key)
    if not isinstance(answer, JevChoiceAnswer) or not answer.choice:
        return None
    return answer.choice


def _optional_noul(answers: dict[str, Any], key: str) -> bool:
    answer = answers.get(key)
    if not isinstance(answer, JevNoulAnswer):
        return False
    return answer.noul >= 0.5


def _optional_choice(answers: dict[str, Any], key: str, enum_type):
    answer = answers.get(key)
    if not isinstance(answer, JevChoiceAnswer) or not answer.choice:
        return None
    try:
        return enum_type(answer.choice)
    except ValueError:
        return None


def _allowed(answers: dict[str, Any], key: str, criteria: dict) -> str | None:
    """An optional choice restricted to the offered options; anything else is dropped."""
    text = _choice_text(answers, key)
    return text if text in criteria else None
