import re

from app.contracts.health_context import HealthContext
from app.retrieval.medical import MedicalEvidenceDoc

_SOURCE_LINE = re.compile(r"\s*sources?:\s*.*$", re.I | re.M)
_NAMED_ORGS = re.compile(
    r"\b(WHO|NICE|CDC|NIH|NLM|MedlinePlus|NIDDK|Mayo Clinic|Cleveland Clinic|Johns Hopkins)\b",
    re.I,
)
_ABSOLUTE = re.compile(r"\b(always|never|must|cure[sd]?|prevents|guaranteed safe|guaranteed unsafe)\b", re.I)


class GroundingChecker:
    def unsupported_personal_numbers(self, answer: str, context: HealthContext) -> list[str]:
        allowed = set()
        for m in context.markers:
            for value in (m.value, m.reference_low, m.reference_high):
                if value is not None:
                    allowed.add(self._norm(value))
        for fact in getattr(context, "facts", None) or []:
            if isinstance(fact.value, (int, float)):
                allowed.add(self._norm(fact.value))
        for progress in getattr(context, "goal_progress", None) or []:
            for fact in progress.metrics:
                if isinstance(fact.value, (int, float)):
                    allowed.add(self._norm(fact.value))
        for r in context.bio_ai_risks:
            if r.score is not None:
                allowed.add(self._norm(r.score))
        for c in context.comparisons:
            for v in (c.previous_value, c.current_value, c.absolute_delta, c.percentage_change):
                if v is not None:
                    allowed.add(self._norm(v))
        for value in (context.metabolic_age, context.metabolic_score):
            if value is not None:
                allowed.add(self._norm(value))
        for evidence in context.evidence:
            if evidence.value is not None:
                allowed.add(self._norm(evidence.value))
            for date_part in (
                evidence.report_date.year,
                evidence.report_date.month,
                evidence.report_date.day,
            ):
                allowed.add(self._norm(date_part))
        issues = []
        for match in re.findall(r"\d+(?:\.\d+)?", answer):
            if self._norm(float(match)) not in allowed:
                if len(match) >= 2:
                    issues.append(match)
        return issues

    def _norm(self, value: float) -> str:
        return f"{float(value):.4f}"

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
            text = _ABSOLUTE.sub("can", text)
            if "depend" not in text.lower():
                text += (
                    "\n\nThe exact recommendations can depend on the cause, treatment, and individual "
                    "circumstances. A healthcare professional can provide advice specific to the person."
                )
        return text, flags
