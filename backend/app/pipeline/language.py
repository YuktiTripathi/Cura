"""Normalize Indic/Hinglish phrasing so English intent routing still works.

Cura answers in English. This module does not detect or switch response language.
"""

from __future__ import annotations

import re


_INTENT_REPLACEMENTS = [
    ("इसका मतलब क्या है", "what does it mean"),
    ("मतलब क्या है", "what does it mean"),
    ("क्या होता है", "what is"),
    ("क्या है", "what is"),
    ("क्यों", "why"),
    ("लेटेस्ट", "latest"),
    ("पिछली रिपोर्ट से", "since my previous report"),
    ("पिछली रिपोर्ट", "previous report"),
    ("पिछले रिपोर्ट", "previous report"),
    ("मागील रिपोर्ट", "previous report"),
    ("मागच्या रिपोर्ट", "previous report"),
    ("ਪਿਛਲੀ ਰਿਪੋਰਟ", "previous report"),
    ("પાછલા રિપોર્ટ", "previous report"),
    ("પાછલી રિપોર્ટ", "previous report"),
    ("আগের রিপোর্ট", "previous report"),
    ("बदलाव", "change"),
    ("बदल गया", "changed"),
    ("बदला", "changed"),
    ("बदलला", "changed"),
    ("ਬਦਲਿਆ", "changed"),
    ("બદલાયું", "changed"),
    ("বদলেছে", "changed"),
    ("रिपोर्ट", "report"),
    ("मेरी", "my"),
    ("मेरा", "my"),
    ("मेरे", "my"),
    ("माझ्या", "my"),
    ("माझा", "my"),
    ("माझी", "my"),
    ("माझे", "my"),
    ("ਮੇਰੀ", "my"),
    ("ਮੇਰਾ", "my"),
    ("ਮੇਰੇ", "my"),
    ("મારું", "my"),
    ("મારો", "my"),
    ("મારા", "my"),
    ("મારી", "my"),
    ("আমার", "my"),
    ("कितना है", "how much"),
    ("कितनी है", "how much"),
    ("कितना", "how much"),
    ("किती आहे", "how much"),
    ("किती", "how much"),
    ("ਕਿੰਨਾ", "how much"),
    ("કેટલું", "how much"),
    ("কত", "how much"),
    ("और ", "and "),
    ("kya hota hai", "what is"),
    ("kya hai", "what is"),
    ("kitna hai", "how much"),
    ("kitni hai", "how much"),
    ("mera ", "my "),
    ("meri ", "my "),
    ("mere ", "my "),
    ("mujhe ", "my "),
    ("kyun", "why"),
    ("kyon", "why"),
    ("aur ", "and "),
]


def normalize_for_intent(message: str) -> str:
    from app.pipeline.indic_terms import (
        canonicalize_biomarker_terms,
        follow_up_as_english,
        status_question_as_english,
    )

    lowered = follow_up_as_english(canonicalize_biomarker_terms(message or ""))
    for src, dest in _INTENT_REPLACEMENTS:
        lowered = re.sub(re.escape(src), dest, lowered, flags=re.I)
    return status_question_as_english(lowered)
