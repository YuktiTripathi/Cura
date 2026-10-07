from __future__ import annotations

import re

from app.contracts.common import AnswerDepth, IntentType, KnowledgeScope
from app.pipeline.lab_parameters import match_lab_keys, parameter_alias_map
from app.pipeline.language import normalize_for_intent
from app.pipeline.medical_terms import MARKER_ALIASES_I18N
from app.pipeline.operations import is_provenance_request
from app.pipeline.questionnaire_intent import (
    explicit_questionnaire_request,
    is_questionnaire_topic,
    questionnaire_follow_up_topic,
)
from app.pipeline.questionnaire_topics import questionnaire_topic

MARKER_ALIASES = {
    "vitamin d": "vitamin_d",
    "vit d": "vitamin_d",
    "25 oh": "vitamin_d",
    "vitamin b12": "vitamin_b12",
    "b12": "vitamin_b12",
    "iron": "iron",
    "hdl": "hdl",
    "ldl": "ldl",
    "triglycerides": "triglycerides",
    "hba1c": "hba1c",
    "a1c": "hba1c",
    "bilirubin": "bilirubin",
    "creatinine": "creatinine",
    "tsh": "tsh",
    "ferritin": "ferritin",
    "crp": "crp",
    "alt": "alt",
    "ast": "ast",
    "hemoglobin": "hemoglobin",
    "cholesterol": "cholesterol",
    "systolic": "systolic",
    "diastolic": "diastolic",
    "urea": "urea",
    "uric acid": "uric_acid",
    "esr": "esr",
}
MARKER_ALIASES.update(MARKER_ALIASES_I18N)
MARKER_ALIASES.update(parameter_alias_map())

BIO_ALIASES = {
    "cardiac": "cardiac_health",
    "heart": "cardiac_health",
    "nafld": "nafld",
    "fatty liver": "nafld",
    "obesity": "obesity",
    "oxidative": "oxidative_stress",
    "thyroid": "thyroid",
    "diabetes": "type_2_diabetes",
    "dyslipidemia": "dyslipidemia",
    "lipid risk": "dyslipidemia",
    "hypertension": "hypertension",
    "blood pressure": "hypertension",
    "metabolic age": "metabolic_age",
    "metabolic score": "metabolic_score",
    "metabolic risk": "metabolic_score",
    "pcod": "pcos",
    "pcos": "pcos",
    "polycystic ovarian": "pcos",
    "polycystic ovary": "pcos",
    "polycystic": "pcos",
}

NAMES = {
    "vitamin_d": "Vitamin D",
    "vitamin_b12": "Vitamin B12",
    "ferritin": "ferritin",
    "crp": "CRP",
    "ldl": "LDL",
    "hdl": "HDL",
    "hba1c": "HbA1c",
    "cardiac_health": "cardiac health",
    "nafld": "NAFLD",
    "metabolic_age": "metabolic age",
    "metabolic_score": "metabolic score",
    "glucose": "Glucose",
    "fasting_blood_glucose": "Fasting Blood Sugar Glucose",
    "cholesterol": "Cholesterol",
    "hemoglobin": "Hemoglobin",
    "fasting_insulin": "Fasting insulin",
    "magnesium": "Magnesium",
    "mcv": "MCV",
    "mch": "MCH",
    "iron": "Iron",
    "urea": "Urea",
    "uric_acid": "Uric Acid",
    "esr": "ESR",
    "systolic": "Systolic pressure",
    "diastolic": "Diastolic pressure",
    "t3": "T3",
    "t4": "T4",
    "tsh": "TSH",
    "creatinine": "Creatinine",
    "egfr": "eGFR",
    "alt": "ALT",
    "ast": "AST",
    "kidney_function": "Kidney function",
    "thyroid_function": "Thyroid function",
    "liver_function": "Liver function",
    "blood_pressure": "Blood pressure",
    "hypertension": "hypertension",
    "type_2_diabetes": "diabetes",
    "pcos": "PCOS",
    "pcod": "PCOD",
    "sleep": "sleep",
    "sleeping_hours": "sleep",
    "alcohol": "alcohol",
    "alcohol_frequency": "alcohol",
    "diet": "diet",
    "diet_preference": "diet",
    "activity": "physical activity",
    "physical_activity_frequency": "physical activity",
    "lifestyle": "lifestyle",
}

BLOOD_KEYS = set(MARKER_ALIASES.values())
BIO_KEYS = set(BIO_ALIASES.values())

_PERSONAL = re.compile(r"\b(my|mine|myself)\b", re.I)
_MY_NON_RECORD = re.compile(
    r"\bmy (doctor|physician|gp|friend|family|wife|husband|partner|mom|dad|child|kids?)\b",
    re.I,
)
_YOUR_PERSONAL = re.compile(
    r"\byour\b.{0,48}\b(result|report|score|level|value|assessment|latest|current|recorded)\b",
    re.I,
)
_TELL_ME_ABOUT = re.compile(r"\btell me about\b", re.I)
_EDUCATIONAL = re.compile(
    r"\b("
    r"what is|what are|what does|what do|what causes|what cause|"
    r"define|meaning of|how does|how do|tell me about|explain|"
    r"learn about|common reasons|causes of|symptoms of|"
    r"difference between|why (?:is|are|can|does|do)|"
    r"would you like to learn|important|"
    r"lifestyle(?: changes)?|what foods|which foods|how can|how to|ways to|"
    r"measure|stand for"
    r")\b",
    re.I,
)
_GENERIC_ADVICE = re.compile(
    r"\b("
    r"lifestyle(?: changes)?|"
    r"what foods|which foods|foods (?:can|that) (?:help|lower|raise|improve)|"
    r"how can (?:i|someone|people|you)|"
    r"how (?:to|do (?:i|you)|does (?:one|exercise|diet|lifestyle))|"
    r"ways to (?:lower|improve|reduce|raise|increase|help)|"
    r"(?:can )?help (?:lower|improve|reduce|raise)|"
    r"common reasons|common causes|"
    r"healthy (?:level|range|cholesterol)|"
    r"generally (?:mean|means)|"
    r"difference between"
    r")\b",
    re.I,
)
_PERSONAL_RECORD = re.compile(
    r"\b("
    r"what(?:'s| is| was| are) my|"
    r"is my .{0,48}\b(?:high|low|normal|ok|okay|elevated)|"
    r"are my .{0,48}\b(?:high|low|normal)|"
    r"(?:show|tell|check|look at|analyze|review) (?:me )?my|"
    r"based on my|according to my|given my|using my|"
    r"from my (?:latest |previous |current )?(?:result|report|value|level|score)|"
    r"my (?:latest|previous|current|last) |"
    r"has my .{0,40}\b(?:improved|changed|increased|decreased|gone)|"
    r"compare my|"
    r"my (?:blood|lab|bio-?ai) (?:report|result|test)|"
    r"what does my .{0,40}(?:report|result) say|"
    r"should i .{0,40}based on my"
    r")\b",
    re.I,
)
_NUMERIC_OWN_VALUE = re.compile(r"\bmy .{0,24} of \d", re.I)
_WHAT_ABOUT = re.compile(r"^\s*what about\b", re.I)
_PRONOUN = re.compile(
    r"\b(it|that|this|these|those|they|them|the above|that score|that result|is that|"
    r"the previous one|previous one|the latest one|latest one)\b",
    re.I,
)
_MINE = re.compile(r"\bmine\b", re.I)
_WHY = re.compile(r"^\s*why\b", re.I)
_SHORT = re.compile(
    r"^\s*(why|why\?|and\??|so\??|mine\??|and mine\??|what about mine\??|what is mine\??)\s*$",
    re.I,
)
_PREVIOUS = re.compile(r"\b(previous|previously|last time|before that)\b", re.I)
_TREND = re.compile(
    r"\b(changed|improve|improved|trend|compare|increased|increase|decreased|decrease|"
    r"went up|went down|risen|rose|fallen|fell)\b",
    re.I,
)
# "Changed over time" in Hinglish and the Indic scripts (word boundaries do not apply to Indic text).
_TREND_I18N = re.compile(
    r"\b(badla|badli|badle|badal gaya|time ke saath|samay ke saath)\b|"
    r"बदला|बदली|बदले|समय के साथ|बदलले|बदलल|काळानुसार|ਬਦਲਿਆ|ਸਮੇਂ ਨਾਲ|બદલાયું|સમય સાથે|বদলেছে|সময়ের সাথে",
    re.I,
)
_LATEST = re.compile(r"\b(latest|current|most recent|recent|now)\b", re.I)
_BIO_REPORT = re.compile(r"\b(bio-?ai|bio ai)\b", re.I)
_BLOOD_REPORT = re.compile(r"\b(blood report|blood result|blood test|lab report)\b", re.I)
_SCENARIO = re.compile(
    r"\b(health scenario|overall health|what (?:areas )?should i focus|"
    r"important findings|how am i doing|what matters most|"
    r"summarize my health|complete health|biggest health concerns)\b",
    re.I,
)
_VIEW_ALL_RESULTS = re.compile(
    r"\b(view all results|show all (?:my )?(?:results|values|markers)|full (?:report|table))\b",
    re.I,
)
_EAT = re.compile(r"\b(eat|nutrition|diet|food)\b", re.I)
_GOAL = re.compile(
    r"\b(health goals?|toward my goals?|progress(?:ing)? toward|how am i doing (?:on|with) my goals?)\b",
    re.I,
)
_REPORT_EXPLAIN = re.compile(
    r"\bexplain my (?:latest |last |current )?(?:blood |lab |bio-?ai )?(?:report|results?)\b",
    re.I,
)
_PROFILE = re.compile(
    r"\b((?:what(?:'s| is)|show|tell me) my (?:health )?profile|"
    r"my dietary preference|my diet preference|my allergies|my medications)\b",
    re.I,
)
_PERSONAL_ACTION = re.compile(r"\b(what should i|what can i|for me)\b", re.I)
_CASUAL = re.compile(
    r"^\s*("
    r"hi|hello|hey|howdy|"
    r"good (?:morning|afternoon|evening)|"
    r"how are you(?: doing)?|"
    r"what(?:'s| is) up|"
    r"thanks|thank you|"
    r"what can you (?:do|help(?: me with)?)|"
    r"what do you do|"
    r"who are you"
    r")[\s!?.]*$",
    re.I,
)
_BIO_CUE = re.compile(r"\b(scores?|bio-?ai|assessment|risks?)\b", re.I)
_SCORE_FOR = re.compile(
    r"\b(?:risk\s+score|score|risk)\s+(?:for|of)\s+([a-z][a-z0-9]+(?:[\s-][a-z][a-z0-9]+){0,3})",
    re.I,
)
_MY_CONDITION_SCORE = re.compile(
    r"\bmy\s+([a-z][a-z0-9]+(?:[\s-][a-z][a-z0-9]+){0,2}?)\s+(?:risk|score|assessment)\b",
    re.I,
)
_HYPOTHETICAL = re.compile(
    r"\b("
    r"if (?:my|someone(?:'s)?|a person(?:'s)?|one(?:'s)?|the) |"
    r"if .{0,80}\b(?:were|was) |"
    r"suppose(?: that)?|"
    r"hypothetically|"
    r"what (?:should|can|would) (?:someone|a person|people)|"
    r"what should (?:i|someone) do if"
    r")\b",
    re.I,
)
_ADVICE_REQUEST = re.compile(
    r"\b(what should i|what can i|what should someone|treatment options|foods? (?:to )?(?:avoid|eat)|"
    r"what (?:foods|diet))\b",
    re.I,
)


def _contains(text: str, *needles: str) -> bool:
    return any(n in text for n in needles)


def is_personal_utterance(message: str) -> bool:
    text = normalize_for_intent(message).lower()
    if _TELL_ME_ABOUT.search(text) and not _PERSONAL.search(text.replace("tell me about", " ")):
        return False
    if _YOUR_PERSONAL.search(text):
        return True
    return bool(_PERSONAL.search(text) or _MINE.search(text))


def is_generic_health_advice(message: str) -> bool:
    return bool(_GENERIC_ADVICE.search(normalize_for_intent(message)))


def requires_personal_record(
    message: str,
    *,
    prior_personal: bool = False,
    follow_up_topic: str | None = None,
) -> bool:
    """True only when answering needs this user's records/documents, not merely a health topic."""
    text = normalize_for_intent(message).lower().strip()
    if _NUMERIC_OWN_VALUE.search(text) or _PERSONAL_RECORD.search(text) or _YOUR_PERSONAL.search(text):
        return True
    if _SCENARIO.search(text) and not _HYPOTHETICAL.search(text):
        return True
    if _VIEW_ALL_RESULTS.search(text) and not _HYPOTHETICAL.search(text):
        return True
    if _BIO_REPORT.search(text) and is_personal_utterance(message) and not _HYPOTHETICAL.search(text):
        return True
    if explicit_questionnaire_request(message):
        return True
    if _MINE.search(text):
        return True
    generic = is_generic_health_advice(message)
    hypothetical = bool(_HYPOTHETICAL.search(text))
    pronoun_follow_up = bool(_PRONOUN.search(text) or _WHAT_ABOUT.match(text) or _SHORT.match(text))
    if generic and not pronoun_follow_up:
        return False
    if hypothetical and not _PERSONAL_RECORD.search(text):
        return False
    if is_personal_utterance(message) and not generic:
        if _MY_NON_RECORD.search(text) and is_educational_utterance(message) and not _PERSONAL_RECORD.search(text):
            return False
        if hypothetical:
            return False
        return True
    if bool(_PERSONAL_ACTION.search(text)) and not generic and not hypothetical:
        if re.search(r"\b(report|result|score|level|value|latest|blood|lab|bio-?ai)\b", text):
            return True
    if prior_personal and is_contextual_follow_up(message):
        return True
    if prior_personal and follow_up_topic and _PREVIOUS.search(text):
        return True
    return False


def is_hypothetical_health_question(message: str) -> bool:
    text = normalize_for_intent(message).lower()
    return bool(_HYPOTHETICAL.search(text)) and not _PERSONAL_RECORD.search(text)


def is_medical_advice_request(message: str) -> bool:
    return bool(_ADVICE_REQUEST.search(normalize_for_intent(message)))


def is_educational_utterance(message: str) -> bool:
    text = normalize_for_intent(message)
    return (
        bool(_EDUCATIONAL.search(text))
        or is_generic_health_advice(message)
        or is_hypothetical_health_question(message)
    )


def is_contextual_follow_up(message: str) -> bool:
    text = normalize_for_intent(message).strip()
    return bool(
        _SHORT.match(text)
        or _WHY.match(text)
        or _PRONOUN.search(text)
        or _MINE.search(text)
        or _WHAT_ABOUT.match(text)
        or re.search(r"\b(are they consistent|is that concerning|the latest one)\b", text, re.I)
    )


def extract_topics(message: str) -> tuple[str | None, str | None]:
    return _extract_topics(normalize_for_intent(message).lower())


def _extract_topics(text: str) -> tuple[str | None, str | None]:
    labs = match_lab_keys(text)
    marker = labs[0] if labs else next(
        (
            code
            for alias, code in sorted(MARKER_ALIASES.items(), key=lambda kv: len(kv[0]), reverse=True)
            if _alias_in_text(alias, text)
        ),
        None,
    )
    bio = next(
        (
            code
            for alias, code in sorted(BIO_ALIASES.items(), key=lambda kv: len(kv[0]), reverse=True)
            if _alias_in_text(alias, text)
        ),
        None,
    )
    if bio == "thyroid" and not _BIO_CUE.search(text):
        marker = marker or "thyroid_function"
        bio = None
    if bio == "thyroid" and marker in {"thyroid_function", "tsh", "t3", "t4"} and not _BIO_CUE.search(text):
        bio = None
    if bio == "hypertension" and marker in {"blood_pressure", "systolic", "diastolic"} and not _BIO_CUE.search(text):
        bio = None
    if bio == "cardiac_health" and not _BIO_CUE.search(text):
        bio = None
    return marker, bio


def _alias_in_text(alias: str, text: str) -> bool:
    value = alias.strip()
    if not value:
        return False
    return bool(re.search(rf"(?<!\w){re.escape(value)}(?!\w)", text, re.I))


def _name(code: str | None) -> str | None:
    if not code:
        return None
    return NAMES.get(code, code.replace("_", " "))


def _named_score_code(text: str) -> str | None:
    marker, bio = _extract_topics(text)
    if bio:
        return bio
    for pattern in (_SCORE_FOR, _MY_CONDITION_SCORE):
        match = pattern.search(text)
        if not match:
            continue
        raw = next((group for group in match.groups() if group), "")
        raw = re.sub(r"[?!.]+$", "", raw).strip().lower()
        if not raw or raw in {"my", "health", "overall", "the", "a"}:
            continue
        for alias, code in sorted(BIO_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
            if raw == alias or raw.replace(" ", "_") == alias.replace(" ", "_") or raw == code:
                return code
        return re.sub(r"[^a-z0-9]+", "_", raw).strip("_")
    return None


def classify_intent(
    message: str,
    follow_up_topic: str | None = None,
    prior_personal: bool = False,
) -> tuple[IntentType, str | None, str | None, AnswerDepth]:
    text = normalize_for_intent(message).lower().strip()
    depth = AnswerDepth.simple
    if _CASUAL.match(text):
        return IntentType.casual_conversation, None, None, AnswerDepth.simple
    if _contains(text, "detailed", "in detail", "explain everything"):
        depth = AnswerDepth.detailed
    elif _contains(text, "summary", "overall", "important findings", "what changed"):
        depth = AnswerDepth.broad
    elif _contains(text, "why", "compare", "changed"):
        depth = AnswerDepth.focused

    marker, bio = _extract_topics(text)
    personal_turn = requires_personal_record(
        message, prior_personal=prior_personal, follow_up_topic=follow_up_topic
    )
    educational = is_educational_utterance(message)
    contextual = bool(follow_up_topic) and is_contextual_follow_up(message)

    if contextual and not marker and not bio:
        if follow_up_topic in BLOOD_KEYS:
            marker = follow_up_topic
        elif follow_up_topic in BIO_KEYS:
            bio = follow_up_topic

    topic = marker or bio
    name = _name(topic)

    # Educational/general unless this turn needs this user's records.
    if educational and not personal_turn:
        return IntentType.general_health_question, topic, name, depth

    if personal_turn and explicit_questionnaire_request(message) and not marker and not bio:
        q_topic = questionnaire_topic(message)
        if not q_topic and is_questionnaire_topic(follow_up_topic):
            q_topic = follow_up_topic
        return (
            IntentType.questionnaire_lookup,
            q_topic,
            _name(q_topic) if q_topic else "questionnaire",
            depth,
        )

    if contextual and not marker and not bio:
        q_topic = questionnaire_follow_up_topic(message, follow_up_topic)
        if q_topic:
            return IntentType.follow_up, q_topic, _name(q_topic), depth

    if contextual and _MINE.search(text) and follow_up_topic:
        if follow_up_topic in BIO_KEYS:
            return IntentType.bio_ai_score, follow_up_topic, _name(follow_up_topic), depth
        return IntentType.latest_result, follow_up_topic, _name(follow_up_topic), AnswerDepth.simple

    if contextual and _WHY.match(text) and follow_up_topic:
        if follow_up_topic in BIO_KEYS:
            return IntentType.bio_ai_explanation, follow_up_topic, _name(follow_up_topic), AnswerDepth.focused
        return IntentType.blood_marker_explanation, follow_up_topic, _name(follow_up_topic), AnswerDepth.focused

    if personal_turn and _BLOOD_REPORT.search(text) and _BIO_REPORT.search(text):
        return IntentType.health_scenario, None, "health scenario", AnswerDepth.broad
    if _contains(text, "compare") and (bio or _BIO_REPORT.search(text)):
        code = bio or "cardiac_health"
        return IntentType.bio_ai_comparison, code, _name(code), depth
    if personal_turn and (_BIO_REPORT.search(text) or (bio and _contains(text, "why", "explain", "high", "increased"))):
        if _contains(text, "compare"):
            code = bio or "cardiac_health"
            return IntentType.bio_ai_comparison, code, _name(code), depth
        if bio and _contains(text, "why", "increased", "high", "explain"):
            return IntentType.bio_ai_explanation, bio, _name(bio), depth
        if _BIO_REPORT.search(text) and not bio:
            return IntentType.bio_ai_score, None, "Bio-AI", depth
    if _contains(text, "why") and bio and personal_turn:
        return IntentType.bio_ai_explanation, bio, _name(bio), depth
    if bio and personal_turn:
        if marker and not _BIO_CUE.search(text):
            pass
        else:
            return IntentType.bio_ai_score, bio, _name(bio), depth
    if bio and not personal_turn:
        return IntentType.general_health_question, bio, _name(bio), depth

    if marker and personal_turn and _PREVIOUS.search(text):
        return IntentType.previous_result, marker, _name(marker), depth
    if marker and personal_turn and (_TREND.search(text) or _TREND_I18N.search(text)):
        return IntentType.trend, marker, _name(marker), depth
    if is_provenance_request(message):
        topic = marker or follow_up_topic
        return IntentType.latest_result, topic, _name(topic) if topic else "result", AnswerDepth.simple
    if marker and not personal_turn:
        return IntentType.general_health_question, marker, _name(marker), depth
    if marker and (_contains(text, "why", "what does", "mean", "normal", "ok", "okay") or (contextual and educational and prior_personal)):
        return IntentType.blood_marker_explanation, marker, _name(marker), depth
    if marker:
        return IntentType.latest_result, marker, _name(marker), AnswerDepth.simple

    if personal_turn and _GOAL.search(text):
        return IntentType.health_goal_progress, None, "health goals", AnswerDepth.broad
    if personal_turn and _REPORT_EXPLAIN.search(text):
        return IntentType.report_explanation, None, "latest report", AnswerDepth.broad
    if personal_turn and _PROFILE.search(text) and not marker:
        return IntentType.personal_profile, None, "health profile", AnswerDepth.focused
    if personal_turn and _SCENARIO.search(text):
        return IntentType.health_scenario, None, "health scenario", AnswerDepth.broad
    if personal_turn and _EAT.search(text):
        return IntentType.nutrition_guidance, marker, _name(marker) if marker else "nutrition", AnswerDepth.focused
    if personal_turn and _BLOOD_REPORT.search(text):
        return IntentType.broad_health_summary, None, "blood report", AnswerDepth.broad
    if _contains(text, "missing"):
        return IntentType.missing_data, marker, _name(marker) if marker else None, AnswerDepth.focused
    if personal_turn and _contains(text, "summary", "important findings", "overall health", "focus"):
        return IntentType.broad_health_summary, None, None, AnswerDepth.broad
    if contextual and follow_up_topic:
        if _PREVIOUS.search(text):
            return IntentType.previous_result, follow_up_topic, _name(follow_up_topic), depth
        if follow_up_topic in BIO_KEYS:
            return IntentType.bio_ai_score, follow_up_topic, _name(follow_up_topic), depth
        return IntentType.follow_up, follow_up_topic, _name(follow_up_topic), depth

    if personal_turn and _BIO_CUE.search(text) and not marker:
        code = bio or _named_score_code(text)
        return IntentType.bio_ai_score, code, _name(code) if code else "requested score", AnswerDepth.simple
    if personal_turn:
        return IntentType.broad_health_summary, None, None, AnswerDepth.broad
    return IntentType.general_health_question, topic, name, depth


def knowledge_scope_for(intent: IntentType) -> KnowledgeScope:
    if intent in {
        IntentType.general_health_question,
        IntentType.casual_conversation,
        IntentType.ambiguous_clarification,
    }:
        return KnowledgeScope.general
    return KnowledgeScope.personal
