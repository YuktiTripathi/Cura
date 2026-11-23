"""One reading of a Bio-AI category word, so "High Risk" and "high" mean the same thing everywhere.

The Bio-AI knowledge base (cura.kb.bio_ai.explainer 1.0) lists the sample report's labels as Healthy (0 to 25),
Increased Risk (26 to 50), High Risk (51 to 75) and Very High Risk (76 to 100). A feed may send either those labels
or short words, so comparisons use this key. The label shown to the person is still the report's own word.
"""

from __future__ import annotations


def risk_status_key(status: object) -> str:
    text = " ".join(str(status or "").lower().split())
    return text[: -len(" risk")] if text.endswith(" risk") else text


# Bands of the sample report (knowledge base section 3.1). Reference only: the person's own report label wins.
SAMPLE_BANDS: tuple[tuple[int, int, str], ...] = (
    (0, 25, "Healthy"),
    (26, 50, "Increased Risk"),
    (51, 75, "High Risk"),
    (76, 100, "Very High Risk"),
)
