import re

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
_OVERCLAIM_FALLBACK = (
    "I can share the retrieved medical information without absolute claims. "
    "Please discuss personal treatment decisions with a clinician."
)


def _norm(value: float) -> str:
    return f"{float(value):.4f}"


class GroundingChecker:
    def unsupported_personal_numbers(self, answer: str, context: HealthContext) -> list[str]:
        by_marker = self._allowed_by_marker(context)
        all_allowed = set()
        for values in by_marker.values():
            all_allowed.update(values)
        issues: list[str] = []
        for sentence in re.split(r"(?<=[.!?])\s+", answer or ""):
            bound = list(_MARKER_CLAIM.finditer(sentence))
            if bound:
                for match in bound:
                    marker = _canonical_marker(match.group(1))
                    number = match.group(2)
                    allowed = by_marker.get(marker, set())
                    if _norm(float(number)) not in allowed:
                        issues.append(number)
                continue
            for match in _NUMBER.findall(sentence):
                if "." not in match and len(match) < 2:
                    continue
                if _norm(float(match)) not in all_allowed:
                    issues.append(match)
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
