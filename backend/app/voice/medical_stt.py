from __future__ import annotations

import re

# Deterministic spoken-form repairs only. Never rewrite numeric values.
_REPLACEMENTS = [
    (re.compile(r"\bh\s*b\s*a\s*(?:one|1)\s*c\b", re.I), "HbA1c"),
    (re.compile(r"\bhb\s*a\s*1\s*c\b", re.I), "HbA1c"),
    (re.compile(r"\bhba1c\b", re.I), "HbA1c"),
    (re.compile(r"\bl\s*d\s*l\b", re.I), "LDL"),
    (re.compile(r"\bh\s*d\s*l\b", re.I), "HDL"),
    (re.compile(r"\bv\s*l\s*d\s*l\b", re.I), "VLDL"),
    (re.compile(r"\bt\s*s\s*h\b", re.I), "TSH"),
    (re.compile(r"\bc\s*r\s*p\b", re.I), "CRP"),
    (re.compile(r"\ba\s*l\s*t\b", re.I), "ALT"),
    (re.compile(r"\ba\s*s\s*t\b", re.I), "AST"),
    (re.compile(r"\bvitamin\s*(?:d|dee|de)\b", re.I), "Vitamin D"),
    (re.compile(r"\bvitamin\s*b\s*(?:12|twelve)\b", re.I), "Vitamin B12"),
    (re.compile(r"\bb\s*(?:12|twelve)\b", re.I), "B12"),
]


def normalize_spoken_medical_terms(transcript: str) -> str:
    text = transcript or ""
    for pattern, replacement in _REPLACEMENTS:
        text = pattern.sub(replacement, text)
    return text
