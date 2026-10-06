"""Topic risk for the "no evidence" policy (production readiness plan, 4.6).

Low risk education (diet, sleep, exercise, what a marker is) may be answered from model
knowledge with a "general information" label. High risk topics need reviewed evidence or
a polite redirect to a clinician.
"""

from __future__ import annotations

import re

from app.pipeline.red_flags import normalize_text

HIGH_RISK_TOPICS: dict[str, re.Pattern[str]] = {
    "medication": re.compile(
        r"\b(drug|drugs|medicine|medication|tablet|pill|dose|dosage|mg|side effects?|interaction\w*|"
        r"antibiotic\w*|steroid\w*|insulin|statin\w*|supplement dose|dawai|goli)\b",
        re.I,
    ),
    "pregnancy": re.compile(r"\b(pregnan\w*|trimester|breastfeed\w*|lactat\w*|ivf|miscarriage|garbh\w*)\b", re.I),
    "children": re.compile(r"\b(baby|babies|infant|newborn|toddler|child|children|kid|kids|paediatric|pediatric|bachch?a)\b", re.I),
    "cancer": re.compile(r"\b(cancer|tumou?r|malignan\w*|chemo\w*|oncolog\w*|metasta\w*|carcinoma|lymphoma|leukemia)\b", re.I),
    "stopping_treatment": re.compile(
        r"\b(stop|quit|skip|discontinue|come off|give up)\b.{0,30}\b(treatment|therapy|dialysis|medicine|medication)\b",
        re.I,
    ),
}


def high_risk_topics(message: str) -> list[str]:
    text = normalize_text(message)
    return [name for name, pattern in HIGH_RISK_TOPICS.items() if pattern.search(text)]


def is_high_risk_topic(message: str) -> bool:
    return bool(high_risk_topics(message))
