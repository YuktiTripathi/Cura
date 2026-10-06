"""Local deterministic safety. Runs before Jev, retrieval, or any LLM call."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.contracts.common import MarkerFlag
from app.contracts.health_context import HealthContext
from app.core.config import settings
from app.pipeline.red_flags import RED_FLAGS, URGENCY_SOON, match_red_flags, normalize_text
from app.pipeline.safety_messages import (
    crisis_message,
    detect_safety_language,
    emergency_message,
    medication_message,
    see_doctor_soon_message,
)

DIAGNOSIS = re.compile(r"\b(you have|diagnosed with|this confirms|this proves you)\b", re.I)
MEDICATION = re.compile(r"\b(take \d+ mg|prescribe|dosage of|start metformin|take insulin)\b", re.I)
EMERGENCY = re.compile(r"\b(call 911|emergency department immediately|you are having a heart attack)\b", re.I)
IMPROVED = re.compile(r"\b(your (health|diabetes) (improved|got worse)|this confirms diabetes)\b", re.I)
UNSAFE_REQUEST = re.compile(
    r"(do i have diabetes|what disease i have|definitely cancer|stop my (medicine|medication)|"
    r"double my dose|ignore (your |the )?safety|prescribe treatment|ignore previous instructions)",
    re.I,
)
PROMPT_INJECTION = re.compile(
    r"\b(ignore previous|ignore your|reveal (?:the )?(?:system|prompt)|"
    r"developer message|bypass safety|act as an? unrestricted)\b",
    re.I,
)
OUT_OF_SCOPE = re.compile(r"\b(build malware|steal password|hack account)\b", re.I)
DIAGNOSIS_REQUEST = re.compile(
    r"\b("
    r"diagnose me|give me a diagnosis|what (?:disease|illness|condition) do i have|"
    r"am i diabetic|do i have (?:diabetes|cancer|ckd|anemia as a diagnosis)"
    r")\b",
    re.I,
)

_DEVANAGARI = re.compile(r"[ऀ-ॿ]")

# Maintained drug lexicon: generics plus common Indian brand names. Extend with the
# clinical team; matching is case-insensitive on normalized text.
DRUG_LEXICON = (
    "metformin", "glycomet", "glucophage", "janumet", "glimepiride", "amaryl", "gliclazide", "glipizide",
    "sitagliptin", "vildagliptin", "galvus", "teneligliptin", "dapagliflozin", "empagliflozin", "jardiance",
    "pioglitazone", "insulin", "lantus", "mixtard", "ozempic", "semaglutide",
    "amlodipine", "amlong", "stamlo", "telmisartan", "telma", "losartan", "olmesartan", "ramipril",
    "enalapril", "atenolol", "metoprolol", "bisoprolol", "nebivolol", "hydrochlorothiazide",
    "chlorthalidone", "furosemide", "lasix", "spironolactone",
    "atorvastatin", "atorva", "rosuvastatin", "rosuvas", "simvastatin", "statin", "statins",
    "aspirin", "ecosprin", "clopidogrel", "warfarin", "apixaban", "rivaroxaban",
    "levothyroxine", "thyroxine", "eltroxin", "thyronorm", "thyrox",
    "paracetamol", "dolo", "crocin", "calpol", "ibuprofen", "brufen", "combiflam", "diclofenac",
    "pantoprazole", "pan 40", "omeprazole", "rabeprazole", "prednisolone", "wysolone", "deflazacort",
    "azithromycin", "amoxicillin", "augmentin", "ciprofloxacin", "doxycycline",
    "sertraline", "escitalopram", "alprazolam", "clonazepam",
)
_DRUG_ALT = "|".join(re.escape(name) for name in sorted(DRUG_LEXICON, key=len, reverse=True))
_MED_NOUN = (
    r"(?:medicine|medicines|medication|medications|tablet|tablets|pill|pills|capsule|capsules|"
    r"dose|doses|drug|drugs|injection|injections|bp (?:tablet|pill|medicine)|"
    r"(?:blood pressure|sugar|diabetes|thyroid|cholesterol|heart) (?:tablet|tablets|pill|pills|medicine|medicines|medication)|"
    r"dawai|dawaai|dawa|goli|गोली|दवा|दवाई|औषध|ਦਵਾਈ|દવા|ওষুধ|"
    rf"{_DRUG_ALT})"
)
_MED_CHANGE_VERB = (
    r"(?:stop|stopping|quit|quitting|skip|skipping|miss|missing|start|starting|change|changing|switch|switching|"
    r"double|doubling|halve|halving|increase|increasing|reduce|reducing|decrease|decreasing|lower|raise|"
    r"cut down|come off|coming off|get off|give up|discontinue|discontinuing|combine|combining|mix|mixing|"
    r"swap|replace|taper)"
)

EMERGENCY_PATTERNS = tuple(p for flag in RED_FLAGS if flag.category == "emergency" for p in flag.patterns)
SELF_HARM_PATTERNS = tuple(p for flag in RED_FLAGS if flag.category == "self_harm" for p in flag.patterns)

MEDICATION_MISUSE = (
    re.compile(
        r"\b(what dose|which dose|how many (?:mg|tablets|pills)|how much (?:mg|insulin)|"
        r"increase my dose|decrease my dose|double (?:my |the )?dose|dosage)\b",
        re.I,
    ),
    re.compile(rf"\b{_MED_CHANGE_VERB}\s+(?:taking\s+|using\s+)?(?:my\s+|his\s+|her\s+|the\s+|this\s+)?(?:\S+\s+){{0,2}}{_MED_NOUN}\b", re.I),
    re.compile(rf"\b{_MED_NOUN}\b.{{0,30}}\b(?:stop|skip|double|instead of|band|badha|chhod|kam kar|zyada)\b", re.I),
    re.compile(rf"\b(?:take|have|give)\s+(?:\d+|two|three|four|half|extra|another|double)\s+(?:\w+\s+)?(?:of\s+)?{_MED_NOUN}", re.I),
    re.compile(rf"\b(?:take|taking|have)\b.{{0,40}}\binstead of\b", re.I),
    re.compile(rf"\b{_MED_NOUN}\b.{{0,40}}\b(?:with|and|together with|along with)\b.{{0,20}}\b{_MED_NOUN}\b.{{0,20}}\btogether\b", re.I),
    re.compile(rf"\bcan i (?:take|have|mix|combine)\b.{{0,30}}\b{_MED_NOUN}\b.{{0,30}}\b(?:with|and)\b.{{0,20}}\b{_MED_NOUN}\b", re.I),
    re.compile(r"(tablet|dawai|dawa|goli|गोली|दवा|दवाई).{0,20}(double|दोगुनी|band kar|बंद|chhod|छोड़)", re.I),
    re.compile(r"\b(bp ki tablet|bp tablet).{0,16}(double|badha)", re.I),
    re.compile(r"(?:औषध|ਦਵਾਈ|દવા|ওষুধ).{0,20}(?:बंद|थांबव|ਬੰਦ|બંધ|বন্ধ)", re.I),
)

ACUTE_TESTING_SUPPRESS = (
    re.compile(
        r"\b(fever(?:ish)?|high temperature|pyrexia|chills and fever|"
        r"chest pain|shortness of breath|can't breathe|cannot breathe|"
        r"severe (?:headache|dehydration)|stroke symptoms|face droop|"
        r"loss of consciousness|unconscious|seizure|vomiting blood|"
        r"acute neurological)\b",
        re.I,
    ),
    re.compile(r"(बुखार|bukhar|feverish)", re.I),
)
_RECOVERED_FOLLOW_UP = re.compile(
    r"\b(after (?:i |the )?(?:recover|recovery|fever)|once (?:i(?:'m| am) )?better|"
    r"now that (?:i(?:'m| am) )?(?:better|recovered)|preventive follow-?up|"
    r"after this settles)\b",
    re.I,
)


def package_suggestion_allowed(message: str, *, previous_user_question: str | None = None) -> bool:
    text = message or ""
    if _RECOVERED_FOLLOW_UP.search(text):
        return True
    if any(pattern.search(text) for pattern in ACUTE_TESTING_SUPPRESS):
        return False
    testing_follow = re.search(
        r"\b(get tested|another test|should i test|which package|what (?:should|to) test)\b",
        text,
        re.I,
    )
    if (
        testing_follow
        and previous_user_question
        and any(pattern.search(previous_user_question) for pattern in ACUTE_TESTING_SUPPRESS)
    ):
        return False
    return True


LIFESTYLE_OK = re.compile(
    r"\b(morning walks?|walks?|yoga|exercise|diet|sleep|water intake|start karna chahta|"
    r"walks start|gym)\b",
    re.I,
)


def detect_language_hint(text: str) -> str:
    if _DEVANAGARI.search(text or ""):
        return "hi"
    lowered = (text or "").lower()
    if any(token in lowered for token in ("mein", "mujhe", "nahi", "dawai", "saans", "jeena")):
        return "hinglish"
    return "en"


def match_safety_category(text: str) -> tuple[str, str, float]:
    message = text or ""
    language = detect_language_hint(message)
    normalized = normalize_text(message)
    hits = match_red_flags(message)
    if any(flag.category == "self_harm" for flag in hits):
        return "self_harm", language, 0.99
    if any(flag.category == "emergency" for flag in hits):
        return "emergency", language, 0.99
    if PROMPT_INJECTION.search(normalized):
        return "prompt_injection", language, 0.95
    if OUT_OF_SCOPE.search(normalized):
        return "out_of_scope", language, 0.95
    medication = any(pattern.search(normalized) for pattern in MEDICATION_MISUSE) or bool(
        DOSAGE_LEGACY.search(normalized)
    )
    if LIFESTYLE_OK.search(normalized) and not medication:
        return "", language, 0.2
    if medication:
        return "medication_misuse", language, 0.9
    if DIAGNOSIS_REQUEST.search(normalized):
        return "diagnosis_request", language, 0.9
    if any(flag.urgency == URGENCY_SOON for flag in hits):
        return "urgent_soon", language, 0.85
    return "", language, 0.0


# Kept so older tests that imported DOSAGE_REQUEST still see medication intent, but
# "start my morning walks" is excluded via LIFESTYLE_OK in match_safety_category.
DOSAGE_LEGACY = re.compile(
    r"\b(what dose|how many (?:mg|tablets)|increase my dose|decrease my dose|double my dose|dosage|"
    r"stop taking my|start taking my)\b",
    re.I,
)

# Words that suggest a symptom report. Used only when the model classifier is unavailable,
# to add a conservative caution instead of silently answering.
SYMPTOM_HINT = re.compile(
    r"\b(pain|ache|bleed\w*|vomit\w*|dizz\w*|faint\w*|breath\w*|fever|numb\w*|swell\w*|"
    r"weak\w*|confus\w*|rash|palpitation\w*|dard|bukhar|chakkar|ulti)\b|दर्द|बुखार|चक्कर|उल्टी",
    re.I,
)

_URGENT_CATEGORIES = {"emergency", "self_harm"}


@dataclass
class PreSafetyDecision:
    blocked: bool = False
    answer: str | None = None
    flags: list[str] | None = None
    escalation: str | None = None
    category: str | None = None
    language: str | None = None
    reply_language: str | None = None
    # Non-blocking caution text prepended to the final answer ("see a doctor soon").
    caution: str | None = None


def _crisis_answer(language: str | None = None) -> str:
    configured = (settings.crisis_helpline_text or "").strip()
    if configured:
        return configured
    return crisis_message(language)


def _urgent_answer(language: str | None = None) -> str:
    return emergency_message(language)


class SafetyLayer:
    def __init__(self, classifier=None):
        if classifier is None:
            from app.pipeline.safety_classifier import default_classifier

            classifier = default_classifier()
        self.classifier = classifier

    def _classify(self, user_message: str):
        try:
            return self.classifier.classify(user_message), False
        except Exception:  # noqa: BLE001 - a classifier failure must never open the gate
            return None, True

    def check_input(self, user_message: str) -> PreSafetyDecision:
        category, language, confidence = match_safety_category(user_message)
        reply_language = detect_safety_language(user_message)
        classified, classifier_failed = self._classify(user_message)
        classifier_failed = classifier_failed or bool(getattr(classified, "degraded", False))
        classified_category = getattr(classified, "category", "none") or "none"
        classified_confidence = float(getattr(classified, "confidence", 0.0) or 0.0)

        # Urgent from either layer wins. Otherwise a high-confidence local rule wins.
        if category in _URGENT_CATEGORIES:
            effective = category
        elif classified_category in _URGENT_CATEGORIES and classified_confidence >= 0.6:
            effective = classified_category
        elif confidence >= 0.8:
            effective = category
        elif classified_confidence >= 0.8:
            effective = classified_category
        else:
            effective = category or classified_category

        extra_flags: list[str] = []
        if classifier_failed:
            extra_flags.append("safety_classifier_unavailable")

        if effective == "self_harm":
            return PreSafetyDecision(
                blocked=True,
                answer=_crisis_answer(reply_language),
                flags=["self_harm", "urgent_symptoms", *extra_flags],
                escalation="crisis_support",
                category="self_harm",
                language=language,
                reply_language=reply_language,
            )
        if effective == "emergency":
            return PreSafetyDecision(
                blocked=True,
                answer=_urgent_answer(reply_language),
                flags=["urgent_symptoms", *extra_flags],
                escalation="urgent_care",
                category="emergency",
                language=language,
                reply_language=reply_language,
            )
        if effective == "prompt_injection":
            return PreSafetyDecision(
                blocked=True,
                answer=(
                    "I can help with health questions, but I can't follow instructions that try to override Cura's safety or privacy rules."
                ),
                flags=["prompt_injection", *extra_flags],
                category="prompt_injection",
                language=language,
                reply_language=reply_language,
            )
        if effective == "medication_misuse":
            return PreSafetyDecision(
                blocked=True,
                answer=medication_message(reply_language),
                flags=["medication_or_dosage_request", *extra_flags],
                escalation="clinician",
                category="medication_misuse",
                language=language,
                reply_language=reply_language,
            )
        if effective == "diagnosis_request":
            return PreSafetyDecision(
                blocked=False,
                flags=["diagnosis_request", *extra_flags],
                escalation="clinician",
                category="diagnosis_request",
                language=language,
                reply_language=reply_language,
            )
        if effective == "out_of_scope":
            return PreSafetyDecision(
                blocked=True,
                answer="I can only help with Cura's supported health-education and health-report questions.",
                flags=["out_of_scope", *extra_flags],
                category="out_of_scope",
                language=language,
                reply_language=reply_language,
            )
        if effective == "urgent_soon":
            return PreSafetyDecision(
                blocked=False,
                flags=["see_doctor_soon", *extra_flags],
                escalation="see_doctor_24h",
                category="urgent_soon",
                language=language,
                reply_language=reply_language,
                caution=see_doctor_soon_message(reply_language),
            )
        caution = None
        if classifier_failed and SYMPTOM_HINT.search(normalize_text(user_message)):
            # Conservative fallback when the model layer is down and symptoms are mentioned.
            extra_flags.append("symptom_caution")
            caution = see_doctor_soon_message(reply_language)
        return PreSafetyDecision(
            flags=extra_flags,
            category="none",
            language=language,
            reply_language=reply_language,
            caution=caution,
        )

    @staticmethod
    def request_safety_mode(decision: PreSafetyDecision | None) -> str:
        category = getattr(decision, "category", None)
        if category in {"emergency", "self_harm"}:
            return "EMERGENCY"
        if category == "medication_misuse":
            return "MEDICATION_BOUNDARY"
        if category == "diagnosis_request":
            return "DIAGNOSIS_RESTRAINT"
        return "STANDARD"

    def scan_critical_context(self, context: HealthContext) -> tuple[list[str], str | None]:
        critical = [m.name for m in context.markers if m.flag == MarkerFlag.critical]
        if not critical:
            return [], None
        return ["critical_value"], "urgent_clinician_review"

    def review(self, answer: str, user_message: str | None = None) -> tuple[str, list[str]]:
        flags: list[str] = []
        out = answer
        if DIAGNOSIS.search(answer):
            flags.append("diagnosis_language")
            out += "\n\nThis is not a diagnosis. Discuss results with a clinician."
        if MEDICATION.search(answer):
            flags.append("medication_recommendation")
            out = re.sub(MEDICATION, "[medication advice removed]", out)
            out += "\n\nI cannot recommend medications or dosages."
        if EMERGENCY.search(answer):
            flags.append("emergency_language")
        if IMPROVED.search(answer):
            flags.append("clinical_judgment")
            out += "\n\nA value difference is not by itself an assessment of improvement or worsening."
        if user_message and UNSAFE_REQUEST.search(user_message):
            flags.append("unsafe_user_request")
            out += (
                "\n\nI can't diagnose, prescribe, or change medication. "
                "Please discuss your results with a clinician."
            )
        return out, flags


SAFETY_ESCALATION_INTENT = "safety_escalation"


def conversation_in_safe_mode(conversation) -> bool:
    """True once any earlier turn in the conversation escalated (emergency or self harm)."""
    messages = getattr(conversation, "messages", None) or []
    return any(getattr(message, "intent", None) == SAFETY_ESCALATION_INTENT for message in messages)
