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

import logging

logger = logging.getLogger("cura.safety")

DIAGNOSIS = re.compile(
    r"\b(diagnosed with|this confirms|this proves you|you have (?:a |an )?(?:[a-z]+ )?(?:condition|disease|disorder|deficiency|diabetes|anaemia|anemia|infection|syndrome))\b",
    re.I,
)
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
    r"am i diabetic|am i (?:anaemic|anemic|prediabetic)|"
    r"do i have (?:diabetes|prediabetes|cancer|ckd|anaemia|anemia|anemia as a diagnosis)"
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


def explicit_diagnosis_request(text: str) -> bool:
    """True only when the user asks to be diagnosed. Explaining a result is not a diagnosis request."""
    return bool(DIAGNOSIS_REQUEST.search(text or ""))


_SYMPTOM_EDUCATION = re.compile(
    r"\b(when should|when is|what causes|what cause|warning signs|treated as|"
    r"how (?:do|can) (?:i|you) know|an emergency)\b|"
    r"कब|क्या कारण|emergency kab|dard kab|kab emergency",
    re.I,
)
_CURRENT_SYMPTOM = re.compile(
    r"\b(i have|i'm having|i am having|i feel|right now|"
    r"my (?:father|mother|dad|mom|husband|wife|son|daughter|friend|parent|papa)\b)\b|"
    r"मुझे|अभी|हो रहा|हो रही|mere (?:papa|father|dad)|"
    r"\b(?:papa|father|dad|mother|mom) ko\b",
    re.I,
)


def educational_symptom_question(text: str) -> bool:
    """A question about warning signs, not a report that someone has them now."""
    message = text or ""
    if _CURRENT_SYMPTOM.search(message):
        return False
    return bool(_SYMPTOM_EDUCATION.search(message))


def match_safety_category(text: str) -> tuple[str, str, float]:
    message = text or ""
    language = detect_language_hint(message)
    normalized = normalize_text(message)
    hits = match_red_flags(message)
    if educational_symptom_question(message):
        hits = [flag for flag in hits if flag.category != "emergency"]
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


ANSWER_JUDGE_FALLBACK = (
    "I can explain what your results mean in general, but I can't advise on starting, stopping or "
    "changing medicine, or tell you whether you have a condition. Please discuss this with your doctor."
)

SAFE_REVIEW_FALLBACK = (
    "I couldn't check this answer safely, so I'm not showing it. "
    "Please try again, or discuss your question with a clinician."
)

_DOSE_UNIT = r"(?:mg|mcg|µg|g|ml|units?|iu|tablets?|pills?|capsules?|puffs?)"
OUTPUT_MEDICATION_PATTERNS = (
    re.compile(
        rf"\b(?:take|increase|decrease|reduce|raise|lower|double|halve|adjust|titrate)\s+(?:your\s+|the\s+)?"
        rf"(?:\w+\s+){{0,3}}?(?:to|by|at)\s+\d+(?:\.\d+)?\s*{_DOSE_UNIT}\b",
        re.I,
    ),
    re.compile(rf"\b\d+(?:\.\d+)?\s*{_DOSE_UNIT}\s+(?:once|twice|thrice|daily|a day|per day|every|at night|in the morning|before|after)\b", re.I),
    re.compile(
        rf"\b(?:you should|you can|you may|it is (?:fine|safe|ok) to|go ahead and|try to|i recommend|i suggest)\s+"
        rf"(?:stop|skip|discontinue|switch|start|double|halve|change|come off|quit)\b[^.!?\n]{{0,60}}",
        re.I,
    ),
    re.compile(rf"\bswitch (?:from|to)\s+(?:\S+\s+){{0,2}}{_MED_NOUN}\b", re.I),
)
_OUTPUT_NEGATION = re.compile(r"\b(?:not|never|don't|do not|without|avoid|unless|before you)\b[^.!?]{0,30}$", re.I)


def unsafe_medication_spans(answer: str) -> list[str]:
    """Medication instructions in a model answer (dose, stop, skip, switch), skipping negated ones."""
    spans: list[str] = []
    text = answer or ""
    for pattern in OUTPUT_MEDICATION_PATTERNS:
        for match in pattern.finditer(text):
            if _OUTPUT_NEGATION.search(text[max(0, match.start() - 40):match.start()]):
                continue
            spans.append(match.group(0))
    return spans


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
        if educational_symptom_question(user_message) and classified_category == "emergency":
            classified_category = "none"
            classified_confidence = 0.0
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
            # A dose request that also names a stored result still refuses dosing,
            # after the verified measurement is retrieved.
            names_stored_result = bool(
                re.search(r"\b20\d{2}-\d{2}-\d{2}\b", user_message or "")
                and re.search(r"\b(report|result|stored|stores)\b", user_message or "", re.I)
            )
            refusal = medication_message(reply_language)
            if names_stored_result:
                return PreSafetyDecision(
                    blocked=False,
                    flags=["medication_or_dosage_request", *extra_flags],
                    escalation="clinician",
                    category="medication_misuse",
                    language=language,
                    reply_language=reply_language,
                    caution=(
                        refusal
                        + " A single stored measurement is not enough to establish a diagnosis, "
                        "and I will not give a dose."
                    ),
                )
            return PreSafetyDecision(
                blocked=True,
                answer=refusal,
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
            # A model label alone must not attach a next-day emergency warning to a lab question.
            # The caution is used when the message itself matches a red-flag pattern.
            from app.pipeline.red_flags import URGENCY_NOW, URGENCY_SOON, match_red_flags

            grounded = any(
                flag.urgency in {URGENCY_NOW, URGENCY_SOON} and flag.category in {"emergency", "urgent_soon"}
                for flag in match_red_flags(user_message)
            ) and not educational_symptom_question(user_message)
            if not grounded:
                effective = "none"
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
        if (
            classifier_failed
            and SYMPTOM_HINT.search(normalize_text(user_message))
            and not educational_symptom_question(user_message)
        ):
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

    @staticmethod
    def critical_notice(context: HealthContext, language: str | None) -> str | None:
        """Escalation sentence that must open any answer touching a critical lab value (plan 2.8).

        Cura never invents thresholds: it only uses the lab's own ``critical`` flag.
        """
        names = list(dict.fromkeys(m.name for m in context.markers if m.flag == MarkerFlag.critical))
        if not names:
            return None
        from app.i18n.catalog import t

        return t(
            "critical_value_notice",
            language,
            markers=", ".join(names[:4]),
            emergency=(settings.emergency_number or "112").strip(),
        )

    def scan_critical_context(self, context: HealthContext) -> tuple[list[str], str | None]:
        critical = [m.name for m in context.markers if m.flag == MarkerFlag.critical]
        if not critical:
            return [], None
        return ["critical_value"], "urgent_clinician_review"

    def review(self, answer: str, user_message: str | None = None) -> tuple[str, list[str]]:
        try:
            out, flags = self._review(answer, user_message)
        except Exception:  # noqa: BLE001 - a failed check must give the safe fallback, not the raw answer
            return SAFE_REVIEW_FALLBACK, ["safety_review_failed"]
        from app.pipeline.answer_judge import judge_answer, should_judge

        if should_judge(out):
            verdict = judge_answer(out)
            if not verdict.available:
                flags.append("answer_judge_unavailable")
            elif verdict.unsafe:
                logger.warning("answer_judge status=blocked reason=%s", verdict.reason)
                return ANSWER_JUDGE_FALLBACK, [*flags, "answer_judge_blocked"]
        return out, flags

    def _review(self, answer: str, user_message: str | None = None) -> tuple[str, list[str]]:
        flags: list[str] = []
        out = answer
        med_spans = unsafe_medication_spans(answer)
        if med_spans:
            flags.append("medication_instruction")
            for span in sorted(med_spans, key=len, reverse=True):
                out = out.replace(span, "[medication advice removed]")
            out += (
                "\n\nI can't advise starting, stopping, switching or changing the dose of a medicine. "
                "Please talk to the clinician who manages it."
            )
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
            if not re.search(r"\b(can't|cannot) diagnose\b", out, re.I):
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
