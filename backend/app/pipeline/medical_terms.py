"""Canonical medical terms. Do not translate these into other words."""

from __future__ import annotations

import re

CANONICAL_TERMS = (
    "HbA1c",
    "LDL",
    "HDL",
    "VLDL",
    "TSH",
    "T3",
    "T4",
    "Vitamin D",
    "Vitamin B12",
    "CRP",
    "ALT",
    "AST",
    "triglycerides",
    "creatinine",
    "hemoglobin",
    "ferritin",
    "insulin",
    "glucose",
    "Bio-AI",
)

MARKER_ALIASES_I18N = {
    "विटामिन डी": "vitamin_d",
    "विटामिन d": "vitamin_d",
    "व्हिटॅमिन डी": "vitamin_d",
    "ਵਿਟਾਮਿਨ ਡੀ": "vitamin_d",
    "વિટામિન ડી": "vitamin_d",
    "ভিটামিন ডি": "vitamin_d",
    # Mixed script, as people type it: Indic "vitamin" with a Latin "D".
    "व्हिटॅमिन d": "vitamin_d",
    "ਵਿਟਾਮਿਨ d": "vitamin_d",
    "વિટામિન d": "vitamin_d",
    "ভিটামিন d": "vitamin_d",
    "हीमोग्लोबिन": "hemoglobin",
    "हिमोग्लोबिन": "hemoglobin",
    "ਹੀਮੋਗਲੋਬਿਨ": "hemoglobin",
    "હિમોગ્લોબિન": "hemoglobin",
    "হিমোগ্লোবিন": "hemoglobin",
    "विटामिन बी12": "vitamin_b12",
    "कोलेस्ट्रॉल": "cholesterol",
    "कोलेस्टेरॉल": "cholesterol",
    "ਕੋਲੈਸਟ੍ਰੋਲ": "cholesterol",
    "ਕੋਲੇਸਟ੍ਰੋਲ": "cholesterol",
    "કોલેસ્ટ્રોલ": "cholesterol",
    "কোলেস্টেরল": "cholesterol",
    "cholesterol": "cholesterol",
}

_PROTECTED = re.compile(
    r"\b(hba1c|a1c|ldl|hdl|vldl|tsh|t3|t4|crp|alt|ast|vitamin\s*d|vitamin\s*b12|b12|triglycerides|creatinine|ferritin|hemoglobin|insulin|glucose|bio-?ai)\b",
    re.I,
)


def is_protected_medical_span(text: str) -> bool:
    return bool(_PROTECTED.search(text or ""))


def strip_protected_spans(text: str) -> str:
    return _PROTECTED.sub(" ", text or "")


def assert_values_unchanged(original: str, rendered: str) -> bool:
    nums = re.findall(r"\d+(?:\.\d+)?", original)
    return all(n in rendered for n in nums)
