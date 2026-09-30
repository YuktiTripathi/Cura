"""Local deterministic safety. Runs before Jev, retrieval, or any LLM call."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.contracts.common import MarkerFlag
from app.contracts.health_context import HealthContext
from app.core.config import settings

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

_DEVANAGARI = re.compile(r"[\u0900-\u097F]")
_MED_NOUN = (
    r"(?:medicine|medication|medicines|tablet|tablets|pill|pills|dose|doses|"
    r"insulin|statin|statins|metformin|drug|drugs|bp (?:tablet|pill)|"
    r"blood pressure (?:tablet|pill|medicine)|dawai|dawa| दवा|गोली)"
)

EMERGENCY_PATTERNS = (
    re.compile(
        r"\b(chest pain|difficulty breathing|shortness of breath|can't breathe|cannot breathe|"
        r"unconscious|loss of consciousness|severe bleeding|stroke symptoms|"
        r"anaphyla(?:xis|ctic)|severe allergic reaction|overdose)\b",
        re.I,
    ),
    re.compile(r"(छाती|chest)\s*(में|mein|me)?\s*(बहुत\s*|bahut\s*)?(दर्द|dard|pain)", re.I),
    re.compile(r"(सांस|saans|saas)\s*(नही|nahi|nahin).{0,12}(आ|aa)", re.I),
    re.compile(r"(बेहोश|behos[h]?|behosh|unconscious)", re.I),
    re.compile(r"(लकवा|stroke|मुंह टेढ़ा|face droop)", re.I),
)

SELF_HARM_PATTERNS = (
    re.compile(r"\b(suicid(?:e|al)|kill myself|end my life|don't want to live|do not want to live)\b", re.I),
    re.compile(r"(जीना नहीं|जीना नहि|mujhe jeena nahi|jeena nahi hai|marna chahta)", re.I),
    re.compile(r"(आत्महत्या|aatmahatya|suicide kar)", re.I),
)

MEDICATION_MISUSE = (
    re.compile(
        rf"\b(what dose|how many (?:mg|tablets)|increase my dose|decrease my dose|"
        rf"double my dose|dosage)\b",
        re.I,
    ),
    re.compile(rf"\b(stop|start)\s+(?:taking\s+)?(?:my\s+)?{_MED_NOUN}\b", re.I),
    re.compile(rf"\b{_MED_NOUN}\s+(double|badha|band)\b", re.I),
    re.compile(r"(tablet|dawai|dawa|गोली|दवा).{0,20}(double|दोगुनी|band kar|बंद)", re.I),
    re.compile(r"\b(bp ki tablet|bp tablet).{0,16}(double|badha)", re.I),
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
    if any(pattern.search(message) for pattern in SELF_HARM_PATTERNS):
        return "self_harm", language, 0.99
    if any(pattern.search(message) for pattern in EMERGENCY_PATTERNS):
        return "emergency", language, 0.99
    if PROMPT_INJECTION.search(message):
        return "prompt_injection", language, 0.95
    if OUT_OF_SCOPE.search(message):
        return "out_of_scope", language, 0.95
    if LIFESTYLE_OK.search(message) and not any(pattern.search(message) for pattern in MEDICATION_MISUSE):
        return "", language, 0.2
    if any(pattern.search(message) for pattern in MEDICATION_MISUSE) or DOSAGE_LEGACY.search(message):
        return "medication_misuse", language, 0.9
    if DIAGNOSIS_REQUEST.search(message):
        return "diagnosis_request", language, 0.9
    return "", language, 0.0


# Kept so older tests that imported DOSAGE_REQUEST still see medication intent, but
# "start my morning walks" is excluded via LIFESTYLE_OK in match_safety_category.
DOSAGE_LEGACY = re.compile(
    r"\b(what dose|how many (?:mg|tablets)|increase my dose|decrease my dose|double my dose|dosage|"
    r"stop taking my|start taking my)\b",
    re.I,
)


@dataclass
class PreSafetyDecision:
    blocked: bool = False
    answer: str | None = None
    flags: list[str] | None = None
    escalation: str | None = None
    category: str | None = None
    language: str | None = None


def _crisis_answer() -> str:
    configured = (settings.crisis_helpline_text or "").strip()
    if configured:
        return configured
    region = (settings.crisis_helpline_region or "").strip()
    suffix = f" ({region})" if region else ""
    return (
        "If you are thinking about harming yourself, please seek help now. "
        "Contact local emergency services or a trusted person nearby"
        f"{suffix}. Cura cannot provide crisis counselling or emergency care."
    )


def _urgent_answer() -> str:
    return (
        "This may need urgent medical attention. Contact your local emergency service or seek urgent in-person care now. "
        "Cura cannot assess emergencies."
    )


class SafetyLayer:
    def __init__(self, classifier=None):
        if classifier is None:
            from app.pipeline.safety_classifier import HeuristicMultilingualClassifier

            classifier = HeuristicMultilingualClassifier()
        self.classifier = classifier

    def check_input(self, user_message: str) -> PreSafetyDecision:
        category, language, confidence = match_safety_category(user_message)
        classified = self.classifier.classify(user_message)
        # Low-confidence classifier results cannot override a high-confidence local rule.
        if confidence >= 0.8:
            effective = category
        elif classified.confidence >= 0.8:
            effective = classified.category
        else:
            effective = category or classified.category

        if effective == "self_harm":
            return PreSafetyDecision(
                blocked=True,
                answer=_crisis_answer(),
                flags=["self_harm", "urgent_symptoms"],
                escalation="crisis_support",
                category="self_harm",
                language=language,
            )
        if effective == "emergency":
            return PreSafetyDecision(
                blocked=True,
                answer=_urgent_answer(),
                flags=["urgent_symptoms"],
                escalation="urgent_care",
                category="emergency",
                language=language,
            )
        if effective == "prompt_injection":
            return PreSafetyDecision(
                blocked=True,
                answer=(
                    "I can help with health questions, but I can't follow instructions that try to override Cura's safety or privacy rules."
                ),
                flags=["prompt_injection"],
                category="prompt_injection",
                language=language,
            )
        if effective == "medication_misuse":
            return PreSafetyDecision(
                blocked=True,
                answer=(
                    "I can't recommend medication doses or tell you to start, stop, or change medicine. "
                    "Please contact the clinician or pharmacist managing your medication."
                ),
                flags=["medication_or_dosage_request"],
                escalation="clinician",
                category="medication_misuse",
                language=language,
            )
        if effective == "diagnosis_request":
            return PreSafetyDecision(
                blocked=False,
                flags=["diagnosis_request"],
                escalation="clinician",
                category="diagnosis_request",
                language=language,
            )
        if effective == "out_of_scope":
            return PreSafetyDecision(
                blocked=True,
                answer="I can only help with Cura's supported health-education and health-report questions.",
                flags=["out_of_scope"],
                category="out_of_scope",
                language=language,
            )
        return PreSafetyDecision(flags=[], category="none", language=language)

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
