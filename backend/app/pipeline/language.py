from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from app.contracts.common import LanguageCode
from app.pipeline.medical_terms import strip_protected_spans

LANGUAGE_NAMES = {
    LanguageCode.en: "English",
    LanguageCode.hi: "Hindi",
    LanguageCode.mr: "Marathi",
    LanguageCode.pa: "Punjabi",
    LanguageCode.gu: "Gujarati",
    LanguageCode.bn: "Bengali",
}

_DEVANAGARI = re.compile(r"[\u0900-\u097F]")
_GURMUKHI = re.compile(r"[\u0A00-\u0A7F]")
_GUJARATI = re.compile(r"[\u0A80-\u0AFF]")
_BENGALI = re.compile(r"[\u0980-\u09FF]")
_LATIN = re.compile(r"[A-Za-z]+")

_HI_HINTS = ("है", "क्या", "कितना", "मेरा", "मेरी", "रिपोर्ट", "जवाब", "मतलब")
_MR_HINTS = ("आहे", "किती", "माझ्या", "माझा", "पाहायचे", "सांगा")
_HINGLISH = {
    "hai",
    "kya",
    "kitna",
    "kitni",
    "mera",
    "meri",
    "mere",
    "hota",
    "mujhe",
    "nahi",
    "kyun",
    "kyunki",
    "aur",
    "batao",
    "samjhao",
}
_EN_FUNC = {"the", "is", "are", "what", "why", "how", "can", "please", "explain", "you", "your", "this", "that"}

_INTENT_REPLACEMENTS = [
    ("इसका मतलब क्या है", "what does it mean"),
    ("मतलब क्या है", "what does it mean"),
    ("क्या होता है", "what is"),
    ("क्या है", "what is"),
    ("क्यों", "why"),
    ("लेटेस्ट", "latest"),
    ("रिपोर्ट", "report"),
    ("मेरी", "my"),
    ("मेरा", "my"),
    ("मेरे", "my"),
    ("माझ्या", "my"),
    ("माझा", "my"),
    ("माझी", "my"),
    ("ਮੇਰੀ", "my"),
    ("ਮੇਰਾ", "my"),
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
    ("latest ", "latest "),
    ("please answer in english", "answer in english"),
    ("हिंदी में जवाब दो", "answer in hindi"),
    ("हिन्दी में जवाब दो", "answer in hindi"),
    ("मराठीत सांगा", "answer in marathi"),
]


@dataclass
class LanguageDetection:
    language: LanguageCode
    confidence: float
    mode: str = "auto"


class LanguageDetector(Protocol):
    def detect(self, text: str) -> LanguageDetection: ...


class HeuristicLanguageDetector:
    def detect(self, text: str) -> LanguageDetection:
        raw = (text or "").strip()
        if not raw:
            return LanguageDetection(LanguageCode.en, 0.2, "auto")
        sample = strip_protected_spans(raw)
        scores: dict[LanguageCode, float] = {
            LanguageCode.en: 0.0,
            LanguageCode.hi: 0.0,
            LanguageCode.mr: 0.0,
            LanguageCode.pa: 0.0,
            LanguageCode.gu: 0.0,
            LanguageCode.bn: 0.0,
        }
        if _GURMUKHI.search(sample):
            scores[LanguageCode.pa] += 4
        if _GUJARATI.search(sample):
            scores[LanguageCode.gu] += 4
        if _BENGALI.search(sample):
            scores[LanguageCode.bn] += 4
        if _DEVANAGARI.search(sample):
            mr = sum(1 for h in _MR_HINTS if h in sample)
            hi = sum(1 for h in _HI_HINTS if h in sample)
            if mr > hi:
                scores[LanguageCode.mr] += 4 + mr
            else:
                scores[LanguageCode.hi] += 4 + hi
        tokens = [t.lower() for t in _LATIN.findall(sample)]
        hi_lat = sum(1 for t in tokens if t in _HINGLISH)
        en_lat = sum(1 for t in tokens if t in _EN_FUNC)
        if hi_lat:
            scores[LanguageCode.hi] += hi_lat * 1.2
        if en_lat:
            scores[LanguageCode.en] += en_lat * 1.1
        if tokens and not hi_lat and en_lat:
            scores[LanguageCode.en] += 2
        best = max(scores, key=scores.get)
        total = sum(scores.values()) or 1
        conf = min(0.99, scores[best] / total)
        if scores[best] < 0.5:
            return LanguageDetection(LanguageCode.en, 0.35, "auto")
        return LanguageDetection(best, round(conf, 2), "auto")


_detector: LanguageDetector = HeuristicLanguageDetector()


def get_language_detector() -> LanguageDetector:
    return _detector


def set_language_detector(detector: LanguageDetector) -> None:
    global _detector
    _detector = detector


def normalize_for_intent(message: str) -> str:
    text = message or ""
    lowered = text
    for src, dest in _INTENT_REPLACEMENTS:
        lowered = re.sub(re.escape(src), dest, lowered, flags=re.I)
    return lowered


_EXPLICIT = [
    (LanguageCode.en, re.compile(r"\b(answer|respond|reply)\b.*\benglish\b|\bin english\b", re.I)),
    (LanguageCode.hi, re.compile(r"हिंदी|हिन्दी|\bhindi\b", re.I)),
    (LanguageCode.mr, re.compile(r"मराठी|\bmarathi\b|मराठीत", re.I)),
    (LanguageCode.pa, re.compile(r"ਪੰਜਾਬੀ|\bpunjabi\b", re.I)),
    (LanguageCode.gu, re.compile(r"ગુજરાતી|\bgujarati\b", re.I)),
    (LanguageCode.bn, re.compile(r"বাংলা|\bbengali\b|\bbangla\b", re.I)),
]


def extract_explicit_language(message: str) -> LanguageCode | None:
    text = message or ""
    if not re.search(r"(answer|respond|reply|जवाब|सांगा|in\s)", text, re.I):
        if re.search(r"हिंदी में|मराठीत सांगा|answer in", text, re.I):
            pass
        else:
            # require a response-instruction, not just a language name in a medical sentence
            if not re.search(r"(जवाब|सांगा|please respond|answer in|respond in)", text, re.I):
                return None
    for code, pattern in _EXPLICIT:
        if pattern.search(text) and re.search(r"(answer|respond|reply|जवाब|सांगा|में|in )", text, re.I):
            return code
    return None


def parse_language_code(value: str | None) -> LanguageCode | None:
    if not value:
        return None
    raw = value.strip().lower()
    try:
        code = LanguageCode(raw)
    except ValueError:
        return None
    if code == LanguageCode.auto:
        return None
    return code


def resolve_response_language(
    *,
    message: str,
    language_mode: str | None,
    requested: str | None,
    conversation_pref: str | None,
) -> tuple[LanguageDetection, LanguageCode, LanguageCode | None]:
    """Returns detection, response language, new conversation preference to store."""
    detector = get_language_detector()
    detection = detector.detect(message)
    explicit = extract_explicit_language(message)
    mode = (language_mode or "auto").strip().lower()
    requested_code = parse_language_code(requested)
    stored = parse_language_code(conversation_pref)

    new_pref = stored
    if explicit:
        new_pref = explicit
        return detection, explicit, new_pref
    if mode not in {"auto", "", "detect"} and requested_code:
        new_pref = requested_code
        return detection, requested_code, new_pref
    if stored:
        return detection, stored, stored
    if detection.confidence < 0.4:
        return detection, stored or LanguageCode.en, new_pref
    return detection, detection.language, new_pref
