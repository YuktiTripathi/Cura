"""Health topic registry: what a question is ABOUT, independent of what the user wants.

Config-driven and deterministic. Biomarkers and Bio-AI scores come from the existing
ontology (``requested_metrics_from_message``) and organ/system domains from
``health_domains``; this module adds the non-biomarker concepts people ask about
(activity, sleep, fatigue, weight ...) and, for every topic, the evidence that MAY be
relevant to it.

A topic's evidence list means "these sources may contain relevant context". It is never
a list of causes and never a diagnosis.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache

from app.pipeline.language import normalize_for_intent


@dataclass(frozen=True)
class TopicSpec:
    code: str
    aliases: tuple[str, ...]
    domains: tuple[str, ...] = ()
    # Lab markers that may hold relevant context (never "causes").
    markers: tuple[str, ...] = ()
    bio_ai: tuple[str, ...] = ()
    questionnaire_keys: tuple[str, ...] = ()
    profile_fields: tuple[str, ...] = ()
    # True when the topic is answered from self-reported data rather than labs.
    behavioural: bool = False


_ACTIVITY_KEYS = (
    "physical_activity_frequency",
    "exercise_frequency_week",
    "exercise_level",
    "daily_active_duration",
    "sitting_hours",
)
_DIET_KEYS = ("diet_preference", "food_groups", "healthy_breakfast_frequency", "fresh_fruit_frequency", "fresh_vegetable_frequency")
_LIFESTYLE_KEYS = (
    "physical_activity_frequency",
    "exercise_frequency_week",
    "sitting_hours",
    "sleeping_hours",
    "food_groups",
    "diet_preference",
    "alcohol_frequency",
    "tobacco_frequency",
)

# Aliases are matched as whole words/phrases after the shared intent normalizer, which
# already maps common Indic biomarker terms. Hinglish and casual forms are listed here.
CONCEPT_TOPICS: tuple[TopicSpec, ...] = (
    TopicSpec(
        "physical_activity",
        ("active", "activity", "activities", "physically", "exercise", "exercising", "exercises", "workout",
         "excercise", "excercising", "exercize", "excersize", "exersize", "excercises", "workouts", "wrkout",
         "work out", "working out", "gym", "walk", "walking", "steps", "sport", "sports",
         "running", "cardio", "move", "moving", "movement", "sedentary", "sitting", "fitness", "training",
         "yoga", "vyayam", "kasrat"),
        domains=("lifestyle_recovery", "metabolic_health"),
        questionnaire_keys=_ACTIVITY_KEYS,
        profile_fields=("age", "bmi"),
        behavioural=True,
    ),
    TopicSpec(
        "sleep",
        ("sleep", "sleeping", "slept", "insomnia", "neend", "nind"),
        domains=("lifestyle_recovery",),
        questionnaire_keys=("sleeping_hours",),
        behavioural=True,
    ),
    TopicSpec(
        "nutrition",
        ("diet", "food", "foods", "eat", "eating", "meal", "meals", "nutrition", "khana", "breakfast",
         "vegetarian", "fruit", "fruits", "vegetables"),
        domains=("lifestyle_recovery", "nutrition_micronutrient_health"),
        questionnaire_keys=_DIET_KEYS,
        behavioural=True,
    ),
    TopicSpec(
        "alcohol",
        ("alcohol", "drink", "drinking", "drinks", "beer", "wine", "daru", "sharab"),
        domains=("lifestyle_recovery", "liver_health"),
        questionnaire_keys=("alcohol_frequency",),
        behavioural=True,
    ),
    TopicSpec(
        "tobacco",
        ("smoke", "smoking", "smoker", "cigarette", "cigarettes", "tobacco", "gutka", "vape", "vaping"),
        domains=("lifestyle_recovery", "cardiovascular_health"),
        questionnaire_keys=("tobacco_frequency",),
        behavioural=True,
    ),
    TopicSpec(
        "lifestyle",
        ("lifestyle", "habit", "habits", "routine", "daily life", "day to day"),
        domains=("lifestyle_recovery",),
        questionnaire_keys=_LIFESTYLE_KEYS,
        profile_fields=("age", "bmi"),
        behavioural=True,
    ),
    TopicSpec(
        "fatigue",
        ("tired", "tiredness", "fatigue", "fatigued", "exhausted", "exhaustion", "low energy", "no energy",
         "energy", "sleepy", "drowsy", "weak", "weakness", "thakan", "thaka", "thaki", "thakawat"),
        domains=("energy_fatigue_context",),
        markers=("hemoglobin", "ferritin", "vitamin_b12", "vitamin_d", "tsh", "fasting_blood_glucose"),
        questionnaire_keys=("sleeping_hours", "physical_activity_frequency"),
    ),
    TopicSpec(
        "weight",
        ("weight", "overweight", "bmi", "obese", "obesity", "belly", "waist", "lose weight", "weight loss", "vajan"),
        domains=("weight_body_composition", "metabolic_health"),
        markers=("fasting_blood_glucose", "hba1c", "triglycerides"),
        bio_ai=("obesity",),
        questionnaire_keys=("physical_activity_frequency", "sitting_hours", "food_groups", "sleeping_hours"),
        profile_fields=("weight", "height", "bmi"),
    ),
    TopicSpec(
        "stress",
        ("stress", "stressed", "anxious", "anxiety", "tension"),
        domains=("lifestyle_recovery",),
        questionnaire_keys=("sleeping_hours",),
        behavioural=True,
    ),
)

_BY_CODE = {spec.code: spec for spec in CONCEPT_TOPICS}


@lru_cache(maxsize=1)
def _alias_patterns() -> tuple[tuple[re.Pattern[str], str], ...]:
    pairs = sorted(
        ((alias, spec.code) for spec in CONCEPT_TOPICS for alias in spec.aliases),
        key=lambda item: len(item[0]),
        reverse=True,
    )
    return tuple((re.compile(rf"(?<![\w-]){re.escape(alias)}(?![\w-])", re.I), code) for alias, code in pairs)


def concept_spec(code: str) -> TopicSpec | None:
    return _BY_CODE.get(code)


@dataclass
class TopicMatch:
    markers: list[str] = field(default_factory=list)  # lab keys
    bio_ai: list[str] = field(default_factory=list)  # Bio-AI codes
    concepts: list[str] = field(default_factory=list)  # behavioural / symptom topics
    domains: list[str] = field(default_factory=list)  # health_domains codes

    @property
    def all(self) -> list[str]:
        return list(dict.fromkeys([*self.markers, *self.bio_ai, *self.concepts, *self.domains]))

    @property
    def empty(self) -> bool:
        return not (self.markers or self.bio_ai or self.concepts or self.domains)


_FATTY = re.compile(r"\bfatty liver\b", re.I)


def extract_topics(message: str, *, conversation_entities: list[str] | None = None) -> TopicMatch:
    """Health subjects mentioned in the message (not the user's goal)."""
    from app.pipeline.health_domains import domain_for_entity, match_domains
    from app.pipeline.intent import BIO_KEYS
    from app.pipeline.ontology import requested_metrics_from_message

    text = normalize_for_intent(message or "")
    match = TopicMatch()
    for key in requested_metrics_from_message(message or ""):
        (match.bio_ai if key in BIO_KEYS else match.markers).append(key)
    # "sugar" in Indian English usually means blood glucose.
    if re.search(r"\b(?:my |mera |meri )?sugar\b", text, re.I) and not match.markers and not re.search(
        r"\bsugar (?:intake|in my diet|drinks?)\b", text, re.I
    ):
        # The glucose family: whichever glucose the report stores (fasting or not) answers it.
        match.markers.append("glucose")
    scrubbed = _FATTY.sub(" ", text)
    for pattern, code in _alias_patterns():
        if code not in match.concepts and pattern.search(scrubbed):
            match.concepts.append(code)
    # "weight" also arrives via the ontology as BMI; keep one subject.
    if "weight" in match.concepts and "bmi" in match.markers:
        match.markers.remove("bmi")
    for domain in match_domains(message or ""):
        if domain.code not in match.domains:
            match.domains.append(domain.code)
    for code in match.concepts:
        for domain in _BY_CODE[code].domains:
            if domain not in match.domains:
                match.domains.append(domain)
    for key in [*match.markers, *match.bio_ai]:
        domain = domain_for_entity(key)
        if domain and domain.code not in match.domains:
            match.domains.append(domain.code)
    if match.empty and conversation_entities:
        for key in conversation_entities:
            (match.bio_ai if key in BIO_KEYS else match.markers).append(key)
    return match


def questionnaire_keys_for(topics: TopicMatch, *, limit: int = 8) -> list[str]:
    """Questionnaire fields that could change an answer about these topics."""
    from app.pipeline.questionnaire_relevance import relevant_questionnaire_keys

    keys: list[str] = []
    for code in topics.concepts:
        keys.extend(_BY_CODE[code].questionnaire_keys)
    keys.extend(relevant_questionnaire_keys([*topics.markers, *topics.bio_ai], topics.domains))
    return list(dict.fromkeys(keys))[:limit]


def evidence_markers_for(topics: TopicMatch) -> list[str]:
    """Lab markers that may hold context for the topics (named markers first)."""
    keys = list(topics.markers)
    for code in topics.concepts:
        keys.extend(_BY_CODE[code].markers)
    if not keys:
        from app.pipeline.health_domains import domain_for_code

        for domain in topics.domains:
            spec = domain_for_code(domain)
            if spec:
                keys.extend((*spec.primary_entities, *spec.supporting_entities))
    return list(dict.fromkeys(keys))


def evidence_bio_ai_for(topics: TopicMatch) -> list[str]:
    keys = list(topics.bio_ai)
    for code in topics.concepts:
        keys.extend(_BY_CODE[code].bio_ai)
    from app.pipeline.health_domains import domain_for_code

    for domain in topics.domains:
        spec = domain_for_code(domain)
        if spec:
            keys.extend(spec.bioai_domains)
    return list(dict.fromkeys(keys))


def is_behavioural_only(topics: TopicMatch) -> bool:
    return bool(topics.concepts) and not topics.markers and not topics.bio_ai and all(
        _BY_CODE[c].behavioural for c in topics.concepts
    )
