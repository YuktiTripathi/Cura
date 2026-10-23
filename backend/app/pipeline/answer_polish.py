"""Last wording fixes on a finished answer, model-written or not.

These are deterministic so they hold whatever the model writes:
- a laboratory-only answer never calls its results "risk estimates";
- each not-a-diagnosis qualifier (risk estimate, lab reading) appears once;
- internal words ("retrieved", "retrieval") become plain language;
- test names use their standard spelling (HbA1c);
- a sentence naming a Bio-AI assessment the member's report does not have is dropped.
"""

from __future__ import annotations

import re

from app.contracts.health_context import HealthContext

_RISK_QUALIFIER = re.compile(r"(?:This|These|That|Those) (?:is|are) (?:a )?risk estimates?, not (?:a )?(?:medical )?diagnos[ie]s\.", re.I)
# Short stand-alone qualifier sentences only, so a longer sentence with real content stays.
_ANY_QUALIFIER = re.compile(
    r"(?<![^\s])[^.!?\n]{0,70}\bnot (?:a )?(?:medical )?diagnos[ie]s\b[^.!?\n]{0,40}[.!?]", re.I
)
_RETRIEVED = (
    (re.compile(r"\b(\w[\w\s-]{0,40}?) (?:was|were) not retrieved\b", re.I), r"\1 isn't included in your report"),
    (re.compile(r"\bnot retrieved\b", re.I), "not included in your report"),
    (re.compile(r"\bin the retrieved (?:records|report|data)\b", re.I), "in your report"),
)
_SPELLING = (
    (re.compile(r"\bHba1c\b|\bHBA1C\b|\bHBA1c\b|\bhba1c\b"), "HbA1c"),
)
# Bio-AI assessment names as members see them. Only these are checked.
_ASSESSMENTS = {
    "nafld": ("nafld", "fatty liver"),
    "metabolic_syndrome": ("metabolic syndrome",),
    "cardiac_health": ("cardiac health", "heart health"),
    "type_2_diabetes": ("type 2 diabetes",),
    "dyslipidemia": ("dyslipidemia", "dyslipidaemia"),
    "hypertension": ("hypertension",),
    "obesity": ("obesity",),
    "oxidative_stress": ("oxidative stress",),
    "thyroid": ("thyroid health",),
}


def _norm(text: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")


def _present_assessments(context: HealthContext) -> set[str]:
    present = set()
    for risk in context.bio_ai_risks or []:
        blob = f"{_norm(risk.code)} {_norm(risk.name)}"
        for code, names in _ASSESSMENTS.items():
            if code in blob or any(_norm(name) in blob for name in names):
                present.add(code)
    return present


def _drop_unlisted_assessments(text: str, context: HealthContext) -> str:
    """Bio-AI answers may name only assessments the member's report contains."""
    if not context.bio_ai_risks:
        return text
    present = _present_assessments(context)
    missing_names = [
        name for code, names in _ASSESSMENTS.items() if code not in present for name in names
    ]
    if not missing_names:
        return text
    pattern = re.compile(r"\b(" + "|".join(re.escape(n) for n in missing_names) + r")\b", re.I)
    kept_lines = []
    for line in text.split("\n"):
        sentences = re.split(r"(?<=[.!?])\s+", line)
        kept = [s for s in sentences if not pattern.search(s) or re.search(r"\b(isn't|not) included\b|\bdoesn't include\b", s)]
        if line.strip() and not "".join(kept).strip():
            continue  # a bullet that was only about an unlisted assessment
        kept_lines.append(" ".join(kept))
    return "\n".join(kept_lines)


def _qualifier_once(text: str) -> str:
    """Each kind once: a Bio-AI risk-estimate qualifier and a lab-results qualifier can both belong."""
    seen: set[str] = set()

    def keep_first(match: re.Match) -> str:
        kind = "risk" if re.search(r"risk estimate", match.group(0), re.I) else "other"
        if kind in seen:
            return ""
        seen.add(kind)
        return match.group(0)

    out = _ANY_QUALIFIER.sub(keep_first, text)
    return re.sub(r"[ \t]{2,}", " ", out).replace(" \n", "\n").strip()


def polish_answer(text: str, context: HealthContext, *, intent: str | None = None) -> str:
    if not text:
        return text
    out = text
    for pattern, repl in _SPELLING:
        out = pattern.sub(repl, out)
    for pattern, repl in _RETRIEVED:
        out = pattern.sub(repl, out)
    lab_only = (intent or "").startswith(("report_", "blood_", "latest_", "previous_", "trend")) and not context.bio_ai_risks
    if lab_only:
        out = _RISK_QUALIFIER.sub("This is a reading of your results, not a diagnosis.", out)
    out = _drop_unlisted_assessments(out, context)
    return _qualifier_once(out)
