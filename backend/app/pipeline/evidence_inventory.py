"""Scoped evidence package built from a retrieval that already happened.

Does not query the database. The prompt view is the only patient-fact
payload the answer model should see for a contracted question.
"""

from __future__ import annotations

import re
from enum import Enum
from types import SimpleNamespace

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
_CHOLESTEROL_PANEL = ("cholesterol", "hdl", "ldl", "triglycerides")
_MARKER_TOKEN = re.compile(
    r"\b(hdl|ldl|hba1c|glucose|tsh|hemoglobin|haemoglobin|cholesterol|triglycerides|alt|ast|bilirubin)\b",
    re.I,
)


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
    comparisons: list[dict] = Field(default_factory=list)

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
        if self.comparisons:
            payload["comparisons"] = self.comparisons
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
    row = {
        "code": getattr(risk, "code", None),
        "name": getattr(risk, "name", None),
        "score": getattr(risk, "score", None),
        "category": getattr(risk, "status", None),
        "report_date": str(measured) if measured else None,
        "source": "bio_ai",
        "status": "AVAILABLE" if getattr(risk, "score", None) is not None else "NOT_PRESENT",
    }
    if getattr(risk, "lifestyle_contribution", None) is not None:
        row["lifestyle_contribution"] = risk.lifestyle_contribution
    factors = list(getattr(risk, "contributing_factors", None) or [])
    if factors:
        row["contributing_factors"] = factors
    if getattr(risk, "percentile", None) is not None:
        row["percentile"] = risk.percentile
    return row


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
        keys = set(requested_marker_keys(message))
        chosen = [
            item
            for item in chosen
            if keys and (_key(getattr(item, "key", None)) in keys or _key(getattr(item, "name", None)) in keys)
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
    if re.search(r"\b(active enough|physical activity|exercise)\b", message or "", re.I):
        unrelated = {"mcv", "mch", "rdw", "basophils", "eosinophils", "calcium", "bilirubin"}
        chosen = [item for item in chosen if _key(getattr(item, "key", None)) not in unrelated]
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
    elif kind == "MARKER_LOOKUP":
        coverage = classify_marker_trends(message, context.markers, context.comparisons)
        if coverage["support"] == "unsupported" and not measurements:
            blocked = "I don't have that measurement in the records I can access for your account."
        elif coverage["support"] == "partial":
            limitation = _partial_trend_limitation(coverage)
        elif coverage["support"] == "unsupported" and measurements:
            limitation = _partial_trend_limitation(coverage)
    coverage = classify_marker_trends(message, context.markers, context.comparisons)
    comparisons = _comparison_rows(coverage)
    if comparisons and limitation is None and any(not row["supported"] for row in comparisons):
        limitation = _partial_trend_limitation(coverage)
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
        comparisons=comparisons,
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


def _comparison_rows(coverage: dict) -> list[dict]:
    rows = []
    for row in coverage["supported"]:
        rows.append({**row, "supported": True, "reason": None})
    for key in coverage["missing"]:
        rows.append({"key": key, "name": key, "supported": False, "reason": "not_in_records"})
    for key in coverage["single_date"]:
        rows.append({"key": key, "name": key, "supported": False, "reason": "single_date"})
    for key in coverage["incompatible_units"]:
        rows.append({"key": key, "name": key, "supported": False, "reason": "unit_not_comparable"})
    for key in coverage["conflicting"]:
        rows.append({"key": key, "name": key, "supported": False, "reason": "same_day_conflict"})
    return rows


_ABSENCE = re.compile(
    r"only one (?:measurement |result )?date|only one measurement|no earlier|no previous|"
    r"was not found|were not found|not found in|did not include|does not contain|doesn't contain|"
    r"not in the (?:retrieved |report|records)",
    re.I,
)
_CHANGE = re.compile(
    r"\b(?:improved|improvement|worsened|went down|went up|decreased|increased|fell|dropped)\b",
    re.I,
)


def contradicting_answer(message: str | None, markers: list | None, answer: str | None, comparisons: list | None = None) -> bool:
    """True when the user-visible text denies a stored pair or states an unsupported change."""
    coverage = classify_marker_trends(message, markers, comparisons)
    text = answer or ""
    supported = {row["key"] for row in coverage["supported"]}
    if supported and _ABSENCE.search(text):
        return True
    if any(row["reason"] == "unit_not_comparable" for row in _comparison_rows(coverage)) and _CHANGE.search(text):
        return True
    if coverage["incompatible_units"] and re.search(r"\bmg/dl\b", text, re.I) and not any(
        _unit_key(getattr(item, "unit", None)) == "mg/dl" for item in markers or []
        if (_key(getattr(item, "key", None)) in coverage["incompatible_units"])
    ):
        # A unit appears in the answer for a marker whose stored rows do not share that unit.
        return True
    return False


def _needs_value_repair(message: str | None, answer: str | None) -> bool:
    """Add a stored value when an explanation uses it without stating it."""
    asks = bool(re.search(r"\b(changed|change|improved|improvement|explain|mean|why is (?:it|that|this))\b", message or "", re.I))
    if not asks:
        return False
    return bool(re.search(
        r"\b(adequate|high|low|above|below|improved|improvement|moved|rose|fell|decreased|increased|would you like)\b",
        answer or "",
        re.I,
    ))


def omitted_supported_facts(message: str | None, markers: list | None, answer: str | None, comparisons: list | None = None) -> str | None:
    """Pairs the model skipped. Appending them does not add a model call."""
    coverage = classify_marker_trends(message, markers, comparisons)
    sentences = []
    comparison_ask = bool(re.search(r"\b(changed|change|improved|improvement|compared)\b", message or "", re.I))
    for row in coverage["supported"] if comparison_ask else []:
        if _number_present(answer, row["previous_value"]) and _number_present(answer, row["current_value"]):
            continue
        change = row["absolute_change"]
        change_text = "unchanged" if change == 0 else f"change {change:+g} {row['unit']}"
        sentences.append(
            f"{row['name']} was {row['previous_value']:g} {row['unit']} on {row['previous_date']} "
            f"and {row['current_value']:g} {row['unit']} on {row['current_date']} ({change_text})."
        )
    dated_rows = _with_comparison_rows(markers, comparisons)
    for key in coverage["single_date"] if _needs_value_repair(message, answer) else []:
        rows = [
            item for item in dated_rows
            if (_key(getattr(item, "key", None)) == key or _key(getattr(item, "name", None)) == key)
            and getattr(item, "value", None) is not None
            and getattr(item, "measured_at", None) is not None
        ]
        if not rows:
            continue
        row = sorted(rows, key=lambda item: str(getattr(item, "measured_at")))[-1]
        if _number_present(answer, row.value):
            continue
        unit = getattr(row, "unit", None) or ""
        low = getattr(row, "reference_low", None)
        high = getattr(row, "reference_high", None)
        range_note = f" (your lab's range is {low:g}–{high:g} {unit})" if low is not None and high is not None else ""
        # The value the answer left out, said once and plainly. A note about a missing earlier
        # result only belongs when the member asked how it changed.
        sentences.append(
            f"Your {getattr(row, 'name', None) or key} is {row.value:g} {unit}{range_note}.".replace(" )", ")")
            + (" There is only one result on file, so a change can't be worked out yet." if comparison_ask else "")
        )
    if not coverage["requested"] and _needs_value_repair(message, answer):
        latest: dict[str, object] = {}
        for marker in markers or []:
            key = _key(getattr(marker, "key", None)) or _key(getattr(marker, "name", None))
            if not key or getattr(marker, "value", None) is None:
                continue
            current = latest.get(key)
            if current is None or str(getattr(marker, "measured_at", "") or "") >= str(getattr(current, "measured_at", "") or ""):
                latest[key] = marker
        if 0 < len(latest) <= 2:
            for marker in latest.values():
                if _number_present(answer, getattr(marker, "value", None)):
                    continue
                unit = getattr(marker, "unit", None) or ""
                low = getattr(marker, "reference_low", None)
                high = getattr(marker, "reference_high", None)
                range_note = (
                    f" (your lab's range is {low:g}–{high:g} {unit})" if low is not None and high is not None else ""
                )
                sentences.append(
                    f"Your {getattr(marker, 'name', None) or 'result'} is {marker.value:g} {unit}{range_note}.".replace(" )", ")")
                )
    if not sentences:
        return None
    if "cholesterol" in coverage["requested"] and coverage["support"] != "full":
        sentences.append(
            "These are numerical changes only. They do not show whether overall cholesterol improved, "
            "and a small change is not by itself clinically meaningful."
        )
    return " ".join(sentences)


def authoritative_measurement_answer(message: str | None, markers: list | None, comparisons: list | None = None) -> str | None:
    """Verified facts when a model answer contradicts them. No second model call."""
    text = render_partial_trend(message, markers, comparisons)
    if not text:
        return None
    if re.search(r"\bwhy\b", message or "", re.I):
        return (
            text
            + " The difference between these dates does not establish why the latest value is outside its reference range."
        )
    return text


def requested_marker_keys(message: str | None) -> list[str]:
    """Markers the question named. 'Cholesterol' asks for the lipid panel, not one row."""
    from app.pipeline.lab_parameters import fuzzy_lab_keys

    named = [key for key in fuzzy_lab_keys(message or "") if key]
    if "cholesterol" in named:
        named = list(dict.fromkeys([*named, *_CHOLESTEROL_PANEL]))
    if named:
        return list(dict.fromkeys(named))
    found = [item.lower() for item in _MARKER_TOKEN.findall(message or "")]
    keys: list[str] = []
    for token in found:
        if token == "cholesterol":
            keys.extend(_CHOLESTEROL_PANEL)
        else:
            keys.append(token)
    return list(dict.fromkeys(keys))


def _number_present(text: str | None, value) -> bool:
    if value is None:
        return False
    token = f"{value:g}"
    return re.search(rf"(?<!\d){re.escape(token)}(?:\.0+)?(?!\d)", text or "") is not None


def _unit_key(value: str | None) -> str:
    text = re.sub(r"\s+", "", (value or "").strip().lower())
    if text in {"percent", "percentage", "pct"}:
        return "%"
    return text


def _dated_unit(items: list) -> str | None:
    """One verified unit for a date. A blank comparison unit does not disagree with %."""
    present: list[str] = []
    display = ""
    for item in items:
        raw = getattr(item, "unit", None)
        unit = _unit_key(raw)
        if not unit:
            continue
        if unit not in present:
            present.append(unit)
            display = str(raw).strip()
    if len(present) > 1:
        return None
    return display if present else ""


def _with_comparison_rows(markers: list | None, comparisons: list | None) -> list:
    """Earlier dated rows live on comparisons so latest-value indexes keep the current result."""
    rows = list(markers or [])
    seen = {
        (_key(getattr(marker, "key", None)), str(getattr(marker, "measured_at", None)), getattr(marker, "value", None))
        for marker in rows
    }
    for item in comparisons or []:
        topic = getattr(item, "topic", None) or (item.get("key") if isinstance(item, dict) else None)
        pairs = (
            (
                getattr(item, "previous_value", None) if not isinstance(item, dict) else item.get("previous_value"),
                getattr(item, "previous_date", None) if not isinstance(item, dict) else item.get("previous_date"),
                getattr(item, "previous_unit", None) if not isinstance(item, dict) else item.get("previous_unit"),
            ),
            (
                getattr(item, "current_value", None) if not isinstance(item, dict) else item.get("current_value"),
                getattr(item, "current_date", None) if not isinstance(item, dict) else item.get("current_date"),
                getattr(item, "current_unit", None) if not isinstance(item, dict) else item.get("current_unit"),
            ),
        )
        for value, when, unit in pairs:
            if value is None:
                continue
            identity = (_key(topic), str(when), value)
            if identity in seen:
                continue
            seen.add(identity)
            rows.append(SimpleNamespace(key=topic, name=topic, value=value, unit=unit, measured_at=when))
    return rows


def classify_marker_trends(message: str | None, markers: list | None, comparisons: list | None = None) -> dict:
    """Split a multi-marker question into paired, missing, single-date, conflicting, or unit-mismatched keys.

    A numeric change is returned only when the same marker has two different dates and the same unit.
    """
    markers = _with_comparison_rows(markers, comparisons)
    keys = requested_marker_keys(message)
    if not keys and re.search(r"\b(improved|worsened|since last|since my last|compared with last)\b", message or "", re.I):
        keys = list(dict.fromkeys(
            _key(getattr(marker, "key", None)) or _key(getattr(marker, "name", None))
            for marker in markers or []
        ))
        keys = [key for key in keys if key]
    grouped: dict[str, list] = {key: [] for key in keys}
    for marker in markers or []:
        key = _key(getattr(marker, "key", None)) or _key(getattr(marker, "name", None))
        if key in grouped:
            grouped[key].append(marker)
    supported: list[dict] = []
    missing: list[str] = []
    single_date: list[str] = []
    incompatible_units: list[str] = []
    conflicting: list[str] = []
    for key in keys:
        rows = grouped.get(key) or []
        if not rows:
            missing.append(key)
            continue
        by_date: dict[str, list] = {}
        for marker in rows:
            when = getattr(marker, "measured_at", None)
            if when is None:
                continue
            by_date.setdefault(str(when), []).append(marker)
        if not by_date:
            single_date.append(key)
            continue
        conflicted = False
        for items in by_date.values():
            values = {getattr(item, "value", None) for item in items}
            units = {_unit_key(getattr(item, "unit", None)) for item in items}
            if len(values) > 1 or len(units) > 1:
                conflicting.append(key)
                conflicted = True
                break
        if conflicted:
            continue
        dates = sorted(by_date)
        if len(dates) < 2:
            single_date.append(key)
            continue
        previous = by_date[dates[-2]][0]
        current = by_date[dates[-1]][0]
        previous_unit = _dated_unit(by_date[dates[-2]])
        current_unit = _dated_unit(by_date[dates[-1]])
        if not previous_unit or not current_unit or previous_unit != current_unit:
            incompatible_units.append(key)
            continue
        from app.pipeline.trend_engine import compute_trend

        delta, _pct, direction = compute_trend(previous.value, current.value)
        supported.append({
            "key": key,
            "name": getattr(current, "name", None) or key,
            "previous_value": previous.value,
            "current_value": current.value,
            "unit": current_unit or getattr(current, "unit", None),
            "previous_date": dates[-2],
            "current_date": dates[-1],
            "absolute_change": delta,
            "direction": direction,
        })
    if supported and not missing and not single_date and not incompatible_units and not conflicting:
        support = "full"
    elif supported:
        support = "partial"
    else:
        support = "unsupported"
    return {
        "support": support,
        "supported": supported,
        "missing": missing,
        "single_date": single_date,
        "incompatible_units": incompatible_units,
        "conflicting": conflicting,
        "requested": keys,
    }


def _partial_trend_limitation(coverage: dict) -> str:
    parts = []
    if coverage["supported"]:
        names = ", ".join(row["name"] for row in coverage["supported"])
        parts.append(f"Verified dated changes exist for {names}.")
    if coverage["missing"]:
        parts.append("Not in the retrieved records: " + ", ".join(coverage["missing"]) + ".")
    if coverage["single_date"]:
        parts.append("Only one date, so no trend: " + ", ".join(coverage["single_date"]) + ".")
    if coverage["incompatible_units"]:
        parts.append("Units differ across dates, so no trend: " + ", ".join(coverage["incompatible_units"]) + ".")
    if coverage["conflicting"]:
        parts.append("Conflicting values on the same date, so no trend: " + ", ".join(coverage["conflicting"]) + ".")
    if "cholesterol" in (coverage.get("requested") or []) and coverage["support"] != "full":
        parts.append("A change in one lipid does not show whether overall cholesterol improved.")
    return " ".join(parts)


def render_partial_trend(message: str | None, markers: list | None, comparisons: list | None = None) -> str | None:
    """Deterministic partial comparison. Uses only paired, same-unit values."""
    coverage = classify_marker_trends(message, markers, comparisons)
    if coverage["support"] == "unsupported" and not coverage["requested"]:
        return None
    if not coverage["requested"]:
        return None
    sentences = []
    for row in coverage["supported"]:
        change = row["absolute_change"]
        change_text = "unchanged" if change == 0 else f"change {change:+g} {row['unit']}"
        sentences.append(
            f"{row['name']} was {row['previous_value']:g} {row['unit']} on {row['previous_date']} "
            f"and {row['current_value']:g} {row['unit']} on {row['current_date']} ({change_text})."
        )
    if sentences and re.search(r"\b(improved|improvement|better|worse|worsened)\b", message or "", re.I):
        sentences.append(
            "This is a numerical change only. It is not a clinical conclusion that the result is better or worse."
        )
    if coverage["missing"]:
        sentences.append(
            "Not in the retrieved records: " + ", ".join(coverage["missing"]) + ". No value was estimated."
        )
    if coverage["single_date"]:
        dated = _with_comparison_rows(markers, comparisons)
        bits = []
        for key in coverage["single_date"]:
            rows = [
                item for item in dated
                if (_key(getattr(item, "key", None)) == key or _key(getattr(item, "name", None)) == key)
                and getattr(item, "value", None) is not None
            ]
            if not rows:
                bits.append(key)
                continue
            row = sorted(rows, key=lambda item: str(getattr(item, "measured_at") or ""))[-1]
            unit = getattr(row, "unit", None) or ""
            when = getattr(row, "measured_at", None)
            bits.append(f"{getattr(row, 'name', None) or key} {row.value:g} {unit} on {when}".replace("  ", " "))
        sentences.append("Only one measurement date is on file for " + "; ".join(bits) + ", so no trend was calculated.")
    if coverage["incompatible_units"]:
        sentences.append("Units do not match across dates for " + ", ".join(coverage["incompatible_units"]) + ", so no trend was calculated.")
    if coverage["conflicting"]:
        sentences.append("Conflicting values are stored on the same date for " + ", ".join(coverage["conflicting"]) + ", so no trend was calculated.")
    if not sentences:
        return None
    if "cholesterol" in coverage["requested"] and coverage["support"] != "full":
        sentences.append(
            "These are numerical changes only. They do not show whether overall cholesterol improved, "
            "and a small change is not by itself clinically meaningful."
        )
    return " ".join(sentences)


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
