"""Remove urgency the facts do not support.

Emergency and same-day advice belongs to the safety layer, which raises it from red-flag
rules, the safety classifier and critical lab values. When none of those fired, a model
sentence such as "see a doctor within 24 hours" or "call emergency services" is not
grounded in the member's data and is removed. The answer keeps its routine
"discuss this with your clinician" advice.
"""

from __future__ import annotations

import re

_URGENT = re.compile(
    r"(within (?:the next )?(?:24|48) hours|within a day|today itself|right away|immediately|as soon as possible|"
    r"urgent(?:ly)?|emergency (?:services|department|room)|call (?:an )?ambulance|call 1\d{2}\b|go to (?:the )?(?:er|a&e|hospital))",
    re.I,
)
_SENTENCE = re.compile(r"(?<=[.!?])\s+")


def strip_unsupported_urgency(answer: str) -> tuple[str, bool]:
    """Drop sentences with urgency language. Returns (text, changed)."""
    if not answer or not _URGENT.search(answer):
        return answer, False
    paragraphs = []
    for paragraph in answer.split("\n"):
        kept = [s for s in _SENTENCE.split(paragraph) if not _URGENT.search(s)]
        paragraphs.append(" ".join(kept).strip())
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(paragraphs)).strip()
    return (text or answer), bool(text) and text != answer.strip()
