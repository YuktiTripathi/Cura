"""Scoped evidence package built from a retrieval that already happened.

Does not query the database. The prompt view is the only patient-fact
payload the answer model should see for a contracted question.
"""

from __future__ import annotations

import re
from enum import Enum

from pydantic import BaseModel, Field

from app.contracts.health_context import HealthContext
from app.contracts.query import QueryPlan

_GLYCEMIC = {"glucose", "hba1c", "fasting_blood_glucose", "fasting_insulin", "hba1c_percent"}
_LIVER = {"alt", "ast", "bilirubin", "ggt", "alp", "sgpt", "sgot"}
_FATIGUE = {
    "hemoglobin",
    "haemoglobin",
    "hematocrit",
    "ferritin",
    "iron",
    "tibc",
    "tsh",
    "vitamin_b12",
    "b12",
    "glucose",
    "hba1c",
}
_DIABETES_RISK = {"type_2_diabetes", "diabetes", "prediabetes"}
_LIVER_RISK = {"nafld", "liver", "liver_health", "fatty_liver"}


class EvidenceStatus(str, Enum):
    available = "AVAILABLE"
    not_present = "NOT_PRESENT"
    not_retrieved = "NOT_RETRIEVED"
    retrieval_failed = "RETRIEVAL_FAILED"
    extraction_failed = "EXTRACTION_FAILED"


class EvidencePackage(BaseModel):
    response_type: str | None = None
    operations: list[str] = Field(default_factory=list)
    required_sources: list[str] = Field(default_factory=list)
    measurements: list[dict] = Field(default_factory=list)
    bio_ai_risks: list[dict] = Field(default_factory=list)
    missing: list[dict] = Field(default_factory=list)
    limitation: str | None = None
    blocked_answer: str | None = None
    questionnaire: list[dict] = Field(default_factory=list)
    report_counts: dict | None = None

    def prompt_payload(self) -> dict:
        """Patient facts for the model. Database identifiers stay out."""
        payload = {
            "response_type": self.response_type,
            "measurements": self.measurements,
            "bio_ai_risks": self.bio_ai_risks,
            "missing": self.missing,
            "limitation": self.limitation,
        }
        if self.questionnaire:
            payload["questionnaire"] = self.questionnaire
        if self.report_counts:
            payload["report_counts"] = self.report_counts
        return payload


def _key(value: str | None) -> str:
    return (value or "").strip().lower().replace(" ", "_").replace("-", "_")


def _outside(marker) -> bool:
    flag = str(getattr(marker, "flag", "") or getattr(marker, "status", "") or "").lower()
    if flag in {"high", "low", "critical"}:
        return True
    value = getattr(marker, "value", None)
    low = getattr(marker, "reference_low", None)
    high = getattr(marker, "reference_high", None)
    if value is None:
        return False
    if high is not None and value > high:
        return True
    if low is not None and value < low:
        return False or value < low
    return False


def _measurement(marker) -> dict:
    flag = getattr(marker, "flag", None)
    measured = getattr(marker, "measured_at", None)
    key = getattr(marker, "key", None)
    return {
        "fact_id": f"blood:{key}:{measured}:{getattr(marker, 'value', None)}",
        "key": key,
        "name": getattr(marker, "name", None),
        "value": getattr(marker, "value", None),
        "unit": getattr(marker, "unit", None),
        "reference_low": getattr(marker, "reference_low", None),
        "reference_high": getattr(marker, "reference_high", None),
        "flag": getattr(flag, "value", flag),
        "report_date": str(measured) if measured else None,
        "source": "blood_report",
        "status": "AVAILABLE" if getattr(marker, "value", None) is not None else "NOT_PRESENT",
    }


def _risk_row(risk) -> dict:
    measured = getattr(risk, "measured_at", None)
    return {
        "code": getattr(risk, "code", None),
        "name": getattr(risk, "name", None),
        "score": getattr(risk, "score", None),
        "category": getattr(risk, "status", None),
        "report_date": str(measured) if measured else None,
        "source": "bio_ai",
        "status": "AVAILABLE" if getattr(risk, "score", None) is not None else "NOT_PRESENT",
    }


def _source_status(plan: QueryPlan, context: HealthContext, source: str) -> EvidenceStatus:
    outcomes = list(getattr(context, "source_outcomes", None) or [])
    for row in outcomes:
        name = str(getattr(row, "source", "") or "")
        status = str(getattr(getattr(row, "status", None), "value", getattr(row, "status", "")) or "")
        if source not in name:
            continue
        if status in {"error", "failed"}:
            return EvidenceStatus.retrieval_failed
        if status in {"empty", "unavailable"}:
            return EvidenceStatus.not_present
    if source == "blood" and plan.needs_blood:
        return EvidenceStatus.available if context.markers else EvidenceStatus.not_present
    if source == "bio" and plan.needs_bio_ai:
        return EvidenceStatus.available if context.bio_ai_risks else EvidenceStatus.not_present
    return EvidenceStatus.not_retrieved


def _select_measurements(kind: str, message: str, markers: list) -> list:
    text = (message or "").lower()
    chosen = list(markers or [])
    if kind == "BIO_AI_SCORE_LIST":
        return []
    if kind == "MARKER_LOOKUP":
        token = ""
        match = re.search(
            r"\b(hdl|ldl|hba1c|glucose|tsh|hemoglobin|haemoglobin|cholesterol|triglycerides|alt|ast|bilirubin)\b",
            message or "",
            re.I,
        )
        if match:
            token = match.group(1).lower()
        chosen = [
            item
            for item in chosen
            if token and (token in _key(getattr(item, "key", None)) or token in _key(getattr(item, "name", None)))
        ]
    elif kind == "ABNORMAL_LIST":
        chosen = [item for item in chosen if _outside(item)]
    elif kind == "PERSONAL_RISK_EXPLANATION" and "diabetes" in text:
        chosen = [item for item in chosen if _key(getattr(item, "key", None)) in _GLYCEMIC or _key(getattr(item, "name", None)) in _GLYCEMIC]
    elif kind == "CROSS_SOURCE_EXPLANATION" and "liver" in text:
        chosen = [item for item in chosen if _key(getattr(item, "key", None)) in _LIVER or _key(getattr(item, "name", None)) in _LIVER]
    elif kind == "SYMPTOM_CONTEXT":
        chosen = [item for item in chosen if _key(getattr(item, "key", None)) in _FATIGUE or _outside(item)]
    elif kind == "PRIORITIZED_CONCERNS":
        abnormal = [item for item in chosen if _outside(item)]
        chosen = abnormal or chosen
    return chosen[:24]


def _select_risks(kind: str, message: str, risks: list) -> list:
    text = (message or "").lower()
    chosen = list(risks or [])
    if kind == "ABNORMAL_LIST":
        return []
    if kind == "PERSONAL_RISK_EXPLANATION" and "diabetes" in text:
        matched = [item for item in chosen if _key(getattr(item, "code", None)) in _DIABETES_RISK or "diabet" in (getattr(item, "name", "") or "").lower()]
        return matched
    if kind == "CROSS_SOURCE_EXPLANATION" and "liver" in text:
        matched = [item for item in chosen if _key(getattr(item, "code", None)) in _LIVER_RISK or "liver" in (getattr(item, "name", "") or "").lower()]
        return matched
    return chosen[:16]


def assemble_evidence(plan: QueryPlan, context: HealthContext) -> EvidencePackage:
    contract = plan.task_contract or {}
    kind = contract.get("response_type")
    message = contract.get("original_message") or plan.raw_message or ""
    measurements = [_measurement(item) for item in _select_measurements(kind, message, context.markers)]
    measurements = _with_history(measurements, context)
    risks = [_risk_row(item) for item in _select_risks(kind, message, context.bio_ai_risks)]
    questionnaire = _questionnaire_rows(plan, context, message)
    measurements, questionnaire, restored, unavailable = _complete_required_facts(
        measurements, questionnaire, plan, context, message
    )
    counts = _report_counts(context)
    missing: list[dict] = []
    limitation = None
    blocked = None

    blood_needed = "blood_report" in (contract.get("required_sources") or []) or (
        plan.needs_blood and kind not in {None, "BIO_AI_SCORE_LIST"}
    )
    bio_needed = "bio_ai" in (contract.get("required_sources") or []) or (
        plan.needs_bio_ai and kind not in {None, "ABNORMAL_LIST"}
    )
    if blood_needed and not measurements:
        status = _source_status(plan, context, "blood")
        missing.append({"source": "blood_report", "status": status.value})
    if bio_needed and not risks:
        status = _source_status(plan, context, "bio")
        missing.append({"source": "bio_ai", "status": status.value})

    if kind == "BIO_AI_SCORE_LIST" and not risks:
        blocked = "I don't have a Bio-AI assessment on file, so I can't list those risk scores."
    elif kind == "ABNORMAL_LIST" and not measurements:
        blocked = "I don't have blood measurements from your SuperShyft report for this question."
    elif kind == "PERSONAL_RISK_EXPLANATION" and "diabetes" in message.lower():
        if not risks and not measurements:
            blocked = "I don't have a diabetes risk score or related blood measurements on file for this question."
        elif not risks or not measurements:
            limitation = "Only part of the diabetes-risk evidence is on file. Say which part is missing."
    elif kind == "CROSS_SOURCE_EXPLANATION" and "liver" in message.lower():
        if not risks and not measurements:
            blocked = "I don't have both the liver risk score and the liver blood measurements for this comparison."
        elif not risks or not measurements:
            limitation = "One side of the liver comparison is missing. Describe only the side that is on file."
    elif kind == "SYMPTOM_CONTEXT" and not measurements and not risks:
        blocked = "I don't have report findings that I can use to discuss this symptom."
    elif kind == "MARKER_LOOKUP" and not measurements:
        blocked = "I don't have that measurement in the records I can access for your account."
    if unavailable and limitation is None:
        limitation = (
            "Some required facts could not be placed in this answer's evidence: "
            + ", ".join(unavailable)
            + "."
        )
    if restored or unavailable:
        import logging
        logging.getLogger("cura.evidence").info(
            "evidence_completeness restored=%s unavailable=%s",
            restored,
            unavailable,
        )

    return EvidencePackage(
        response_type=kind,
        operations=[str(item) for item in (contract.get("operations") or [])],
        required_sources=list(contract.get("required_sources") or []),
        measurements=measurements,
        bio_ai_risks=risks,
        missing=missing,
        limitation=limitation,
        blocked_answer=blocked,
        questionnaire=questionnaire,
        report_counts=counts,
    )


def _complete_required_facts(
    measurements: list[dict],
    questionnaire: list[dict],
    plan: QueryPlan,
    context: HealthContext,
    message: str,
) -> tuple[list[dict], list[dict], list[str], list[str]]:
    """Restore comparison and questionnaire facts that selection dropped, inside the measurement cap."""
    restored: list[str] = []
    unavailable: list[str] = []
    present = {row.get("fact_id") for row in measurements}
    required: list[dict] = []
    for row in context.comparisons or []:
        topic = getattr(row, "topic", None)
        for value, when in (
            (getattr(row, "previous_value", None), getattr(row, "previous_date", None)),
            (getattr(row, "current_value", None), getattr(row, "current_date", None)),
        ):
            if value is None:
                continue
            fact_id = f"blood:{topic}:{when}:{value}"
            if fact_id in present:
                continue
            match = next(
                (
                    marker
                    for marker in context.markers or []
                    if getattr(marker, "key", None) == topic and getattr(marker, "value", None) == value
                ),
                None,
            )
            flag = getattr(match, "flag", None) if match is not None else None
            required.append({
                "fact_id": fact_id,
                "key": topic,
                "name": getattr(match, "name", None) or topic,
                "value": value,
                "unit": getattr(match, "unit", None) if match is not None else None,
                "reference_low": getattr(match, "reference_low", None) if match is not None else None,
                "reference_high": getattr(match, "reference_high", None) if match is not None else None,
                "flag": getattr(flag, "value", flag) if flag is not None else None,
                "report_date": str(when) if when else None,
                "source": "blood_report",
                "status": "AVAILABLE",
            })
    cap = 24
    protected = {row["fact_id"] for row in required} | present
    for row in required:
        if len(measurements) >= cap:
            drop = next((index for index, item in enumerate(measurements) if item.get("fact_id") not in protected), None)
            if drop is None:
                unavailable.append(row["fact_id"])
                continue
            measurements.pop(drop)
        measurements.append(row)
        restored.append(row["fact_id"])
    asked = bool(plan.needs_questionnaire or re.search(r"\bquestionnaire\b", message or "", re.I))
    if asked and not questionnaire:
        unavailable.append("questionnaire:required")
    return measurements, questionnaire, restored, unavailable


def _with_history(measurements: list[dict], context: HealthContext) -> list[dict]:
    """A comparison already built in context is evidence. Do not leave only the latest point."""
    seen = {(row.get("key"), str(row.get("report_date") or ""), row.get("value")) for row in measurements}
    extra: list[dict] = []
    for row in context.comparisons or []:
        topic = getattr(row, "topic", None)
        for value, when in (
            (getattr(row, "previous_value", None), getattr(row, "previous_date", None)),
            (getattr(row, "current_value", None), getattr(row, "current_date", None)),
        ):
            if value is None:
                continue
            key = (topic, str(when or ""), value)
            if key in seen:
                continue
            seen.add(key)
            match = next(
                (
                    marker
                    for marker in context.markers or []
                    if getattr(marker, "key", None) == topic and getattr(marker, "value", None) == value
                ),
                None,
            )
            flag = getattr(match, "flag", None) if match is not None else None
            extra.append({
                "fact_id": f"blood:{topic}:{when}:{value}",
                "key": topic,
                "name": getattr(match, "name", None) or topic,
                "value": value,
                "unit": getattr(match, "unit", None) if match is not None else None,
                "reference_low": getattr(match, "reference_low", None) if match is not None else None,
                "reference_high": getattr(match, "reference_high", None) if match is not None else None,
                "flag": getattr(flag, "value", flag) if flag is not None else None,
                "report_date": str(when) if when else None,
                "source": "blood_report",
                "status": "AVAILABLE",
            })
    return measurements + extra


def _questionnaire_rows(plan: QueryPlan, context: HealthContext, message: str) -> list[dict]:
    asked = bool(plan.needs_questionnaire or re.search(r"\bquestionnaire\b", message or "", re.I))
    if not asked:
        return []
    rows = []
    for answer in context.questionnaire or []:
        value = getattr(answer, "value", None)
        if value in (None, ""):
            continue
        key = getattr(answer, "question_key", None)
        rows.append({
            "fact_id": f"questionnaire:{key}",
            "key": key,
            "question": getattr(answer, "question", None),
            "value": value,
            "source": "questionnaire",
            "status": "AVAILABLE",
        })
    return rows


def _report_counts(context: HealthContext) -> dict | None:
    summary = getattr(context, "in_range_summary", None)
    if summary is None:
        return None
    total = summary.in_range + summary.out_of_range + summary.missing + summary.unclassified
    if not total:
        return None
    return {
        "total_markers": total,
        "within_range": summary.in_range,
        "outside_range": summary.out_of_range,
        "unclassified": summary.unclassified,
        "selected_for_this_answer": len(context.markers or []),
    }
