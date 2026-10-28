"""Deterministic post-generation clinical checks. Prompt text is not the only layer."""

from __future__ import annotations

import re

from app.contracts.health_context import HealthContext
from app.contracts.query import QueryPlan

_CAUSAL = re.compile(
    r"\b(caused your|caused the|this proves that|directly caused|is the cause of)\b",
    re.I,
)
_BIOAI_DX = re.compile(
    r"\b(you have (?:type 2 )?diabetes|this confirms (?:type 2 )?diabetes|you are diabetic)\b",
    re.I,
)
_CURRENT_AS_NOW = re.compile(
    r"\byour (?:latest )?(vitamin d|ldl|hdl|hba1c|alt|ast|tsh|ferritin) is\b",
    re.I,
)
_HAS_DATE = re.compile(r"\b(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}|\d{4}-\d{2}-\d{2})\b")
_INTERNAL_ID = re.compile(
    r"\b(blood-\d+|bioai-|assessment_instance|report_id|user_id=|subject_id=)\b",
    re.I,
)
_PII = re.compile(r"\b(eyJ[A-Za-z0-9_-]{8,}|sk-[A-Za-z0-9]{8,}|Bearer\s+\S+|\S+@\S+\.\S+)\b")
_FERRITIN_SUB = re.compile(r"\bferritin\b.{0,40}\b(serum iron|estimated)\b", re.I)
_SCORE_AS_PROBABILITY = re.compile(
    r"\b{token}\s*(?:%|percent)\s*(?:chance|probability|likelihood)\b(?:\s+of\b[^.!?]{{0,48}})?",
    re.I,
)
_BIO_HORIZON = re.compile(
    r"\b(?:within|in|over) the next \d+\s+(?:days?|weeks?|months?|years?)\b",
    re.I,
)
_BIO_CERTAINTY = re.compile(r"\byou will (?:develop|get|have)\b", re.I)
# Score copy that states a chance, without a percent sign, is still not a calibrated probability.
_BIO_CHANCE = re.compile(r"\bestimates your chance(?:\s+of(?:\s+having)?)?\b", re.I)
_BIO_CHANCE_BAND = re.compile(r"\bhigher-than-typical chance of\b", re.I)


def _score_probabilities(text: str, context: HealthContext) -> tuple[str, list[str]]:
    """A Bio-AI score is not a percent chance of disease unless a validated model says so.
    Lab percentages such as HbA1c 9.1% are left alone."""
    flags: list[str] = []
    out = text
    for risk in context.bio_ai_risks or []:
        score = getattr(risk, "score", None)
        if score is None:
            continue
        token = f"{score:g}"
        name = getattr(risk, "name", None) or "Bio-AI"
        pattern = re.compile(_SCORE_AS_PROBABILITY.pattern.format(token=re.escape(token)), re.I)
        if pattern.search(out):
            flags.append("bio_ai_score_as_probability")
            out = pattern.sub(
                f"a {name} score of {token}, which is a risk estimate rather than a percentage probability",
                out,
            )
    return out, flags


_ABSENCE = re.compile(
    r"\b(not found|not available|not on file|was not found|were not found|wasn't found|not retrieved|are missing|is missing|was not measured|were not measured|has not been measured)\b",
    re.I,
)
_PERSONAL_LIFESTYLE = re.compile(
    r"\b(you follow|you reported|you noted|your diet|you drink|you sleep|you said you|sleeping habits)\b",
    re.I,
)
_FOOD = re.compile(r"\b(chicken|fish|pulses|legumes|eggs|curd|milk|nuts)\b", re.I)


def _questionnaire_blob(context: HealthContext) -> str:
    parts: list[str] = []
    for row in context.questionnaire or []:
        parts.append(str(row.question_key or ""))
        parts.append(str(row.question or ""))
        parts.append(str(row.value or ""))
    return " ".join(parts).lower()


def _measured_markers(context: HealthContext):
    rows = list(context.markers or []) + list(getattr(context, "panel_markers", None) or [])
    seen = set()
    out = []
    for marker in rows:
        if marker.value is None:
            continue
        key = (marker.key or marker.name or "").lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(marker)
    return out


def correct_false_absence(answer: str, context: HealthContext) -> tuple[str, list[str]]:
    """Replace a 'not on file' sentence when that marker is already in the record.

    Omitting a marker from the model context is not evidence that it was never measured.
    """
    from app.pipeline.lab_parameters import aliases_for, canonicalize_marker_name

    markers = _measured_markers(context)
    if not markers or not answer:
        return answer, []
    flags: list[str] = []
    kept: list[str] = []
    for sentence in re.split(r"(?<=[.!?])\s+", answer.strip()):
        if not _ABSENCE.search(sentence):
            kept.append(sentence)
            continue
        replacement = None
        low = sentence.lower()
        for marker in markers:
            code = canonicalize_marker_name(marker.key or marker.name or "")
            names = [marker.name or "", marker.key or "", code, *aliases_for(code)]
            if not any(name and name.lower() in low for name in names):
                continue
            unit = f" {marker.unit}" if marker.unit else ""
            replacement = f"Your {marker.name or code} result on file is {marker.value}{unit}."
            flags.append("false_absence_corrected")
            break
        kept.append(replacement or sentence)
    return " ".join(part for part in kept if part).strip(), flags


def drop_unsupported_lifestyle(answer: str, context: HealthContext) -> tuple[str, list[str]]:
    """Remove a personal lifestyle claim that the questionnaire does not support.

    General advice ("a balanced diet", "limit alcohol") and conditional suggestions stay.
    """
    if not answer or not _PERSONAL_LIFESTYLE.search(answer):
        return answer, []
    blob = _questionnaire_blob(context)
    flags: list[str] = []
    kept: list[str] = []
    for sentence in re.split(r"(?<=[.!?])\s+", answer.strip()):
        if not _PERSONAL_LIFESTYLE.search(sentence):
            kept.append(sentence)
            continue
        foods = [m.group(0).lower() for m in _FOOD.finditer(sentence)]
        if foods and any(food not in blob for food in foods):
            flags.append("unsupported_lifestyle_removed")
            continue
        if re.search(r"\b(vegetarian|non-vegetarian|non vegetarian|vegan)\b", sentence, re.I):
            if not any(token in blob for token in ("vegetarian", "non-vegetarian", "non vegetarian", "vegan")):
                flags.append("unsupported_lifestyle_removed")
                continue
        if re.search(r"\byou drink\b|\bservings per week\b", sentence, re.I) and "alcohol" not in blob:
            flags.append("unsupported_lifestyle_removed")
            continue
        kept.append(sentence)
    if not flags:
        return answer, []
    return " ".join(kept).strip(), flags


_TREND = re.compile(
    r"\b(increased|decreased|improved|getting worse|worsened|newly abnormal)\b",
    re.I,
)


def drop_unsupported_trends(answer: str, context: HealthContext) -> tuple[str, list[str]]:
    """A change claim needs a dated comparison. 'Newly abnormal' needs a prior result that was in range."""
    if not answer or not _TREND.search(answer):
        return answer, []
    comparisons = list(context.comparisons or [])
    baselines = list(getattr(context, "baselines", None) or [])
    flags: list[str] = []
    kept: list[str] = []
    for sentence in re.split(r"(?<=[.!?])\s+", answer.strip()):
        if not _TREND.search(sentence):
            kept.append(sentence)
            continue
        low = sentence.lower()
        if "newly abnormal" in low:
            supported = any(getattr(item, "newly_abnormal", False) for item in baselines)
            if not supported:
                flags.append("unsupported_trend_removed")
                continue
        direction = None
        if re.search(r"\b(increased|getting worse|worsened)\b", low):
            direction = "increased"
        elif re.search(r"\b(decreased|improved)\b", low):
            direction = "decreased"
        if direction:
            supported = any((row.direction or "") == direction for row in comparisons) or any(
                (getattr(item, "direction", None) or "") == direction for item in baselines
            )
            if not supported:
                flags.append("unsupported_trend_removed")
                continue
        kept.append(sentence)
    if not flags:
        return answer, []
    return " ".join(kept).strip(), flags


_NEGATED = re.compile(
    r"\b(not|n't|cannot|never|no|whether|without|rule out|ruled out|confirm(?:s|ed)? that|mean that)\b[^.!?]{0,30}$",
    re.I,
)


def _rewrite_unless_negated(match: re.Match) -> str:
    """"You have diabetes" claims a diagnosis; "does not confirm that you have diabetes" is
    the correct caveat and must stay as written."""
    before = match.string[max(0, match.start() - 60):match.start()]
    if _NEGATED.search(before):
        return match.group(0)
    return "your Bio-AI Type 2 Diabetes risk score"


def review_clinical_output(answer: str, *, plan: QueryPlan, context: HealthContext) -> tuple[str, list[str]]:
    flags: list[str] = []
    out, absence_flags = correct_false_absence(answer or "", context)
    flags.extend(absence_flags)
    out, lifestyle_flags = drop_unsupported_lifestyle(out, context)
    flags.extend(lifestyle_flags)
    out, trend_flags = drop_unsupported_trends(out, context)
    flags.extend(trend_flags)
    if _CAUSAL.search(out):
        flags.append("causal_overclaim")
        out = _CAUSAL.sub("can be associated with", out)
        if "does not establish" not in out.lower():
            out = out.rstrip() + " The available information does not establish this as the cause."
    if _BIOAI_DX.search(out) and context.bio_ai_risks:
        flags.append("bio_ai_treated_as_diagnosis")
        out = _BIOAI_DX.sub(_rewrite_unless_negated, out)
        if "not a diagnosis" not in out.lower() and "risk" in out.lower():
            out = out.rstrip() + " A Bio-AI score is a risk assessment, not a diagnosis."
    asks_timing = re.search(r"\b(when|date|trend|changed|change|since|compare|previous|last report)\b", plan.raw_message or "", re.I)
    if asks_timing and context.markers and _CURRENT_AS_NOW.search(out) and not _HAS_DATE.search(out):
        dated = [
            row.measured_at.date() if hasattr(row.measured_at, "date") else row.measured_at
            for row in context.markers
            if getattr(row, "measured_at", None)
        ]
        dated.extend(ev.report_date for ev in (context.evidence or []) if ev.report_date)
        latest = max(dated) if dated else None
        if latest:
            flags.append("stale_presented_as_current")
            label = latest.strftime("%d %b %Y") if hasattr(latest, "strftime") else str(latest)
            out = out.rstrip() + f" This is from your last available report on {label}."
    if _INTERNAL_ID.search(out):
        flags.append("internal_identifier_exposed")
        out = _INTERNAL_ID.sub("", out)
        out = re.sub(r"\s{2,}", " ", out).strip()
    if _PII.search(out):
        flags.append("sensitive_payload_leak")
        out = _PII.sub("[removed]", out)
    if "ferritin" in (plan.topic or "").lower() or any(
        (item.key or "").lower() == "ferritin" for item in (context.missing or [])
    ):
        if _FERRITIN_SUB.search(out):
            flags.append("missing_value_substituted")
            out = re.sub(_FERRITIN_SUB, "ferritin is not available in the retrieved results", out)
    rewritten, score_flags = _score_probabilities(out, context)
    flags.extend(score_flags)
    if context.bio_ai_risks:
        if _BIO_HORIZON.search(rewritten):
            flags.append("bio_ai_time_horizon")
            rewritten = _BIO_HORIZON.sub("over time", rewritten)
        if _BIO_CERTAINTY.search(rewritten):
            flags.append("bio_ai_outcome_certainty")
            rewritten = _BIO_CERTAINTY.sub("this estimate does not mean you will", rewritten)
        if _BIO_CHANCE.search(rewritten):
            flags.append("bio_ai_chance_as_probability")
            rewritten = _BIO_CHANCE.sub("is a risk estimate for", rewritten)
            rewritten = _BIO_CHANCE_BAND.sub("a higher risk estimate for", rewritten)
    return rewritten, flags
