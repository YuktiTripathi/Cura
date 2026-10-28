import re
import unicodedata

from app.contracts.health_context import HealthContext
from app.retrieval.medical import MedicalEvidenceDoc

_SOURCE_LINE = re.compile(r"\s*sources?:\s*.*$", re.I | re.M)
_NAMED_ORGS = re.compile(
    r"\b(WHO|NICE|CDC|NIH|NLM|MedlinePlus|NIDDK|Mayo Clinic|Cleveland Clinic|Johns Hopkins)\b",
    re.I,
)
_ABSOLUTE = re.compile(r"\b(always|never|must|cure[sd]?|prevents|guaranteed safe|guaranteed unsafe)\b", re.I)
_NUMBER = re.compile(r"\d+(?:\.\d+)?")
_MARKER_CLAIM = re.compile(
    r"\b(ldl|hdl|hba1c|triglycerides?|vitamin d|tsh|glucose|cholesterol|crp|hs-crp|alt|ast|insulin|"
    r"vldl|phosphorus|homocysteine|bmi|dyslipidemia|metabolic age|metabolic score|"
    r"type 2 diabetes|nafld|oxidative stress)\b"
    r"[^.]{0,40}?(\d+(?:\.\d+)?)(\s*(?:%|mg/dl|mg/l|mmol/l|u/l|kg/m2))?",
    re.I,
)
# Numbers that are explanation, not a personal measurement.
_NON_MEASUREMENT = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:-|–|to)\s*\d+(?:\.\d+)?\s*(?:months?|weeks?|days?|years?|hours?|minutes?|times?|servings?)\b|"
    r"\b\d+(?:\.\d+)?\s*(?:months?|weeks?|days?|years?|hours?|hrs?|minutes?|mins?|times?|servings?|steps?|"
    r"glasses|cups|kg of|percent of people)\b|"
    r"\b(?:type|top|step|stage|grade|priority|number|no\.?|#)\s*\d+\b|"
    r"\b(?:19|20)\d{2}\b",
    re.I,
)
_UNIT_VALUE = re.compile(
    r"\b(\d+(?:\.\d+)?)\s*(?:%|mg/dl|mg/l|ng/ml|pg/ml|g/dl|u/l|iu/l|miu/l|uiu/ml|µiu/ml|mmol/l|fl|pg|"
    r"ml/min(?:/1\.73\s?m2)?|kg/m2|mm ?hg)",
    re.I,
)
_OVERCLAIM_FALLBACK = (
    "I can share the retrieved medical information without absolute claims. "
    "Please discuss personal treatment decisions with a clinician."
)


def to_ascii_digits(text: str) -> str:
    """Map Devanagari, Gurmukhi, Gujarati, Bengali (and any Unicode) digits to ASCII.

    A value written in local digits must not slip past the numeric grounding check.
    """
    return "".join(str(unicodedata.digit(ch)) if ch.isdigit() and not ch.isascii() else ch for ch in text or "")


def _norm(value: float) -> str:
    return f"{float(value):.4f}"


class GroundingChecker:
    def unsupported_personal_numbers(self, answer: str, context: HealthContext) -> list[str]:
        return [number for _sentence, number in self.unsupported_number_sentences(answer, context)]

    def unsupported_number_sentences(self, answer: str, context: HealthContext) -> list[tuple[str, str]]:
        """(sentence, number) pairs where a stated personal value is not in the member's record.

        Only measurement-like numbers count: a number with a lab unit, or a decimal / multi-digit
        number claimed for a named marker. Time spans ("2-3 months"), counts ("top 3"), steps,
        names ("type 2 diabetes") and dates are explanation, not personal values.
        """
        catalog = self._catalog(context)
        issues: list[tuple[str, str]] = []
        text = to_ascii_digits(answer)
        for sentence in re.split(r"(?<=[.!?।])\s+", text or ""):
            issues.extend(_attribution_issues(sentence, catalog))
        return issues

    def _catalog(self, context: HealthContext) -> dict:
        """Values keyed by canonical biomarker. A number's presence under another key does not count."""
        measured: dict[str, list[dict]] = {}
        ranges: dict[str, set[str]] = {}
        bio: dict[str, set[str]] = {}
        derived: dict[str, set[str]] = {}

        def put(bucket, marker, value, **extra):
            if marker is None or value is None:
                return
            try:
                number = float(value)
            except (TypeError, ValueError):
                return
            key = _canonical_code(marker)
            bucket.setdefault(key, []).append({"value": _norm(number), **extra})

        def add_range(marker, value):
            if marker is None or value is None:
                return
            try:
                number = float(value)
            except (TypeError, ValueError):
                return
            ranges.setdefault(_canonical_code(marker), set()).add(_norm(number))

        rows = list(context.markers or []) + list(getattr(context, "panel_markers", None) or [])
        for marker in rows:
            put(measured, marker.key or marker.name, marker.value, unit=marker.unit, when=getattr(marker, "measured_at", None), report_id=getattr(marker, "report_id", None))
            add_range(marker.key or marker.name, marker.reference_low)
            add_range(marker.key or marker.name, marker.reference_high)
        for fact in list(getattr(context, "facts", None) or []) + list(getattr(context, "derived", None) or []):
            kind = str(getattr(fact, "source_type", "") or "")
            target = derived if kind == "derived" or (fact.fact or "").lower() == "bmi" else measured
            put(target, fact.fact, fact.value, unit=getattr(fact, "unit", None), when=getattr(fact, "measured_at", None))
        for progress in getattr(context, "goal_progress", None) or []:
            for fact in progress.metrics:
                put(measured, getattr(fact, "fact", None) or "goal", fact.value)
        for risk in context.bio_ai_risks or []:
            if risk.score is not None:
                bio.setdefault(_canonical_code(risk.code or risk.name or "bio_ai"), set()).add(_norm(float(risk.score)))
        for row in context.comparisons or []:
            put(measured, row.topic, row.previous_value, current=False)
            put(measured, row.topic, row.current_value, current=True)
        _mark_current(measured)
        if context.metabolic_age is not None:
            bio.setdefault(_canonical_code("metabolic age"), set()).add(_norm(float(context.metabolic_age)))
        if context.metabolic_score is not None:
            bio.setdefault(_canonical_code("metabolic score"), set()).add(_norm(float(context.metabolic_score)))
        return {"measured": measured, "ranges": ranges, "bio": bio, "derived": derived}

    def sanitize_medical_answer(self, answer: str, medical: list[MedicalEvidenceDoc]) -> tuple[str, list[str]]:
        flags: list[str] = []
        text = _SOURCE_LINE.sub("", answer or "").strip()
        allowed = {doc.name.lower() for doc in medical}
        invented = []
        for match in _NAMED_ORGS.findall(text):
            if match.lower() not in allowed:
                invented.append(match)
        if invented:
            flags.append("invented_medical_source")
            for name in invented:
                text = re.sub(rf"\b{re.escape(name)}\b", "", text)
            text = _SOURCE_LINE.sub("", text)
            text = re.sub(r"\s{2,}", " ", text).strip()
        if medical and _ABSOLUTE.search(text):
            flags.append("overgeneralized_claim")
        return text, flags


def _mark_current(measured: dict) -> None:
    """A value from an older report is not the current result unless the answer names its date."""
    from datetime import date as date_cls, datetime

    def day(value):
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date_cls):
            return value
        return None

    days = [day(row.get("when")) for rows in measured.values() for row in rows]
    days = [item for item in days if item]
    latest = max(days) if days else None
    for rows in measured.values():
        for row in rows:
            if "current" in row:
                continue
            when = day(row.get("when"))
            row["current"] = latest is None or when is None or when == latest


def drop_unverified_claims(answer: str, context: HealthContext) -> str:
    """Last step before display. Drop a line that states a personal value the current report does not hold."""
    if not answer:
        return answer
    catalog = GroundingChecker()._catalog(context)
    kept = []
    for line in answer.splitlines():
        issues = _attribution_issues(line, catalog)
        if issues:
            repaired = _without_unverified_clauses(line, issues)
            restored = _restore_verified_measurements(line, repaired or "", context)
            if restored:
                kept.append(restored)
            continue
        kept.append(line)
    text = "\n".join(kept).strip()
    return text or answer


def _without_unverified_clauses(line: str, issues: list[tuple[str, str]]) -> str | None:
    """Keep clauses that state a verified fact. Drop only the clause with an unsupported number."""
    bad: set[str] = set()
    for _sentence, number in issues:
        try:
            bad.add(_norm(float(number)))
        except (TypeError, ValueError):
            bad.add(number)
    parts = re.split(r"\s*(?:,|;|\band\b|\bbut\b)\s*", line)
    kept = []
    for part in parts:
        norms = []
        for raw in re.findall(r"\d+(?:\.\d+)?", part):
            try:
                norms.append(_norm(float(raw)))
            except (TypeError, ValueError):
                continue
        if any(number in bad for number in norms):
            continue
        if part.strip():
            kept.append(part.strip())
    if not kept:
        return None
    return ", ".join(kept)


def _restore_verified_measurements(original: str, repaired: str, context: HealthContext) -> str:
    """A clause that mixes a real result with an unsupported one must not take the real result with it."""
    extras = []
    for marker in list(context.markers or []) + list(getattr(context, "panel_markers", None) or []):
        if getattr(marker, "value", None) is None:
            continue
        token = f"{float(marker.value):g}"
        if not re.search(rf"(?<![\d.]){re.escape(token)}(?![\d.])", original or ""):
            continue
        if re.search(rf"(?<![\d.]){re.escape(token)}(?![\d.])", repaired or ""):
            continue
        unit = marker.unit or ""
        shown = f"{token}{unit}" if unit.startswith("%") else f"{token} {unit}".strip()
        extras.append(f"{marker.name or marker.key} is {shown}.")
    if not extras:
        return repaired
    return "\n".join(part for part in (repaired, *extras) if part).strip()


def _canonical_code(name: str) -> str:
    from app.pipeline.lab_parameters import canonicalize_marker_name

    return canonicalize_marker_name(name) or _canonical_marker(name)


def _personal_sentence(sentence: str) -> bool:
    return bool(re.search(r"\b(your|my|mine)\b", sentence or "", re.I))


def _norm_unit(unit: str | None) -> str:
    return re.sub(r"[^a-z0-9/%]+", "", (unit or "").lower())


def _attribution_issues(sentence: str, catalog: dict) -> list[tuple[str, str]]:
    """A stated personal value must be that biomarker's own measurement, not any number in the record."""
    scrubbed = _NON_MEASUREMENT.sub(" ", sentence or "")
    if not scrubbed.strip():
        return []
    issues: list[tuple[str, str]] = []
    range_spans = [(match.start(), match.end()) for match in re.finditer(r"\d+(?:\.\d+)?\s*(?:-|–|to)\s*\d+(?:\.\d+)?", scrubbed)]

    def in_range(pos: int) -> bool:
        return any(start <= pos < end for start, end in range_spans)

    claims = list(_MARKER_CLAIM.finditer(scrubbed))
    seen: set[tuple[str, str]] = set()
    for match in claims:
        code = _canonical_code(match.group(1))
        underscored = code.replace(" ", "_")
        if underscored in catalog["bio"]:
            code = underscored
        if code not in catalog["measured"]:
            # The claim pattern captures only the last word of a multi-word name
            # ("Fasting Blood Glucose" -> "Glucose"); try the longer names it ends.
            words = scrubbed[: match.start(1)].split()
            for size in range(1, min(3, len(words)) + 1):
                longer = _canonical_code(" ".join(words[-size:] + [match.group(1)]))
                if longer in catalog["measured"]:
                    code = longer
                    break
        number = match.group(2)
        if "." not in number and len(number) < 2:
            continue
        normalized = _norm(float(number))
        if in_range(match.start(2)):
            allowed = catalog["ranges"].get(code, set())
            general = re.search(r"\b(typical|usually|general|often)\b", sentence, re.I) and not re.search(
                r"\byour report\b", sentence, re.I
            )
            if general or not _personal_sentence(sentence) or normalized in allowed:
                continue
            issues.append((sentence, number))
            continue
        rows = catalog["measured"].get(code) or []
        if code in catalog["bio"] and normalized in catalog["bio"][code]:
            continue
        if code in catalog["derived"] and any(row["value"] == normalized for row in catalog["derived"][code]):
            continue
        stated_unit = match.group(3) if match.lastindex and match.lastindex >= 3 else None
        matched = [
            row for row in rows
            if row["value"] == normalized and (not stated_unit or not row.get("unit") or _norm_unit(stated_unit) == _norm_unit(row.get("unit")))
        ]
        if matched and not _HAS_DATE.search(sentence) and not re.search(r"\b(previous report|since your previous|->)\b", sentence, re.I):
            current_rows = [row for row in matched if row.get("current", True)]
            if current_rows:
                matched = current_rows
            else:
                current_values = {row["value"] for row in rows if row.get("current", True)}
                neighbors = {_norm(float(item)) for item in re.findall(r"\d+(?:\.\d+)?", scrubbed)}
                matched = matched if current_values & neighbors else []
        if not matched:
            key = (sentence, number)
            if key not in seen:
                seen.add(key)
                issues.append((sentence, number))
            continue
        if _HAS_DATE.search(sentence):
            dates = [row.get("when") for row in matched if row.get("when")]
            if dates and not any(_date_in_sentence(sentence, when) for when in dates):
                issues.append((sentence, number))
    if claims:
        return issues
    if not _personal_sentence(sentence):
        return []
    for match in _UNIT_VALUE.finditer(scrubbed):
        if in_range(match.start(1)):
            continue
        number = match.group(1)
        normalized = _norm(float(number))
        known = set()
        for bucket in (catalog["measured"], catalog["derived"]):
            for rows in bucket.values():
                known.update(row["value"] for row in rows)
        for values in catalog["bio"].values():
            known.update(values)
        for values in catalog["ranges"].values():
            known.update(values)
        if normalized not in known:
            issues.append((sentence, number))
    return issues


_HAS_DATE = re.compile(r"\b(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}|\d{4}-\d{2}-\d{2})\b")


def _date_in_sentence(sentence: str, when) -> bool:
    text = sentence.lower()
    iso = str(when)[:10]
    if iso and iso in text:
        return True
    try:
        label = when.strftime("%d %b %Y").lower()
    except AttributeError:
        return False
    return label in text or label.lstrip("0") in text


def _canonical_marker(name: str) -> str:
    key = re.sub(r"[^a-z0-9]+", "", (name or "").lower())
    aliases = {
        "ldlcholesterol": "ldl",
        "ldlcholestrol": "ldl",
        "hdlcholesterol": "hdl",
        "hba1c": "hba1c",
        "vitamind": "vitamind",
        "triglyceride": "triglycerides",
        "triglycerides": "triglycerides",
        "dyslipidemiascore": "dyslipidemia",
        "dyslipidemia": "dyslipidemia",
        "metabolicscore": "metabolicscore",
        "metabolicage": "metabolicage",
    }
    return aliases.get(key, key)
