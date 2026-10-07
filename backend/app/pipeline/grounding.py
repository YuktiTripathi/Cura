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
    r"\b(ldl|hdl|hba1c|triglycerides?|vitamin d|tsh|glucose|cholesterol|crp|alt|ast|insulin|"
    r"dyslipidemia|metabolic age|metabolic score)\b[^.]{0,80}?(\d+(?:\.\d+)?)",
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
        by_marker = self._allowed_by_marker(context)
        all_allowed = set()
        for values in by_marker.values():
            all_allowed.update(values)
        issues: list[tuple[str, str]] = []
        text = to_ascii_digits(answer)
        for sentence in re.split(r"(?<=[.!?।])\s+", text or ""):
            scrubbed = _NON_MEASUREMENT.sub(" ", sentence)
            bound = list(_MARKER_CLAIM.finditer(scrubbed))
            if bound:
                # A value must belong to a marker named in the same sentence ("HbA1c 9.1% and
                # glucose 214 mg/dL"); another marker's value attributed here is still caught.
                named = set()
                for match in bound:
                    named |= by_marker.get(_canonical_marker(match.group(1)), set())
                for match in bound:
                    number = match.group(2)
                    if "." not in number and len(number) < 2:
                        continue
                    if _norm(float(number)) not in named:
                        issues.append((sentence, number))
                continue
            for match in _UNIT_VALUE.finditer(scrubbed):
                number = match.group(1)
                if _norm(float(number)) not in all_allowed:
                    issues.append((sentence, number))
        return issues

    def _allowed_by_marker(self, context: HealthContext) -> dict[str, set[str]]:
        by_marker: dict[str, set[str]] = {}

        def add(marker: str | None, value) -> None:
            if marker is None or value is None:
                return
            key = _canonical_marker(marker)
            by_marker.setdefault(key, set()).add(_norm(float(value)))

        for m in context.markers:
            for value in (m.value, m.reference_low, m.reference_high):
                add(m.key or m.name, value)
                add(m.name, value)
        for fact in getattr(context, "facts", None) or []:
            if isinstance(fact.value, (int, float)):
                add(fact.fact, fact.value)
        for progress in getattr(context, "goal_progress", None) or []:
            for fact in progress.metrics:
                if isinstance(fact.value, (int, float)):
                    add(getattr(fact, "fact", None) or "goal", fact.value)
        for r in context.bio_ai_risks:
            if r.score is not None:
                add(r.code or r.name or "bio_ai", r.score)
        for c in context.comparisons:
            topic = c.topic
            for v in (c.previous_value, c.current_value, c.absolute_delta, c.percentage_change):
                add(topic, v)
        if context.metabolic_age is not None:
            add("metabolic age", context.metabolic_age)
        if context.metabolic_score is not None:
            add("metabolic score", context.metabolic_score)
        for evidence in context.evidence:
            add(evidence.marker, evidence.value)
            if evidence.report_date:
                add(evidence.marker, evidence.report_date.year)
                add(evidence.marker, evidence.report_date.month)
                add(evidence.marker, evidence.report_date.day)
                by_marker.setdefault("_dates", set()).add(_norm(float(evidence.report_date.year)))
        return by_marker

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
            excerpts = " ".join((doc.excerpt or "").strip() for doc in medical if doc.excerpt).strip()
            text = excerpts or _OVERCLAIM_FALLBACK
            if "clinician" not in text.lower():
                text = f"{text} A healthcare professional can provide advice specific to the person."
        return text, flags


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
