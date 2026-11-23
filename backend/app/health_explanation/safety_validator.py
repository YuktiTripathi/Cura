"""Safety check for explanation text, applied to anything a model writes.

It rejects text that diagnoses, claims a cause, says a result rules a condition out or in, gives a dose, advises
a supplement or medicine, or turns a score into a probability. A failing field falls back to the rules wording.
This is a pattern check. It is not clinical review and it will not catch everything.
"""

from __future__ import annotations

import re

_CONDITIONS = r"(?:type\s*2\s+)?(?:diabetes|diabetic|prediabetes|pre-?diabetic|fatty liver|nafld|hypertension|heart disease|heart attack|anaemia|anemia|kidney disease|thyroid disease|metabolic syndrome|dyslipidemia)"
_NEGATION = r"(?:not|n't|never|cannot|can't|does not|do not|doesn't|don't|without)"

_CHECKS: dict[str, re.Pattern[str]] = {
    "diagnosis": re.compile(
        rf"\b(?:you\s+(?:have|are\s+suffering\s+from|suffer\s+from|already\s+have)\s+{_CONDITIONS}|you\s+are\s+(?:diabetic|prediabetic)|"
        rf"(?:diagnosed|diagnosis\s+of)\s+(?:with\s+)?{_CONDITIONS}|this\s+confirms\s+(?:that\s+)?you)",
        re.I,
    ),
    "causal_claim": re.compile(
        r"\b(?:is|are|was|were)\s+caused\s+by\b|\bcaused\s+by\s+your\b|\bbecause\s+of\s+your\b|\bdue\s+to\s+your\b|"
        r"\bis\s+the\s+reason\s+(?:for|why)\s+your\b|\bleading\s+to\s+your\b|\bresulting\s+from\s+your\b",
        re.I,
    ),
    "rules_out": re.compile(r"\b(?:rules?\s+out|ruled\s+out|proves?\s+you\s+(?:are|have)|means\s+you\s+are\s+(?:healthy|fine|safe))\b", re.I),
    "dose_or_medicine": re.compile(
        r"\b\d+(?:\.\d+)?\s?(?:mg|mcg|µg|iu|ml|units?)\b(?!\s*/\s*d?l)|"
        r"\b(?:take|start|stop|increase|reduce|skip)\b[^.]{0,30}\b(?:medicine|medication|tablets?|pills?|supplements?|statin|metformin|insulin|vitamin\s+d\s+\d)",
        re.I,
    ),
    "probability": re.compile(r"\b\d+(?:\.\d+)?\s?%\s*(?:chance|probability|likelihood|risk\s+of)\b|\b(?:percent|per\s+cent)\s+chance\b", re.I),
}


def safety_problems(text: str | None) -> list[str]:
    """Names of the checks this text fails. Empty means it passed."""
    value = text or ""
    found = []
    for name, pattern in _CHECKS.items():
        if name == "rules_out":
            for m in pattern.finditer(value):
                before = value[max(0, m.start() - 25) : m.start()].lower()
                if not re.search(_NEGATION, before):
                    found.append(name)
                    break
        elif pattern.search(value):
            found.append(name)
    return found


def is_safe(text: str | None) -> bool:
    return not safety_problems(text)
