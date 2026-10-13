"""Questionnaire as reasoning context, not display data.

Questionnaire answers are user-reported, not measurements. They are used to personalize
an answer only when they change it: which recommendation leads, which generic advice is
dropped because the member already does it, or how a result is interpreted (for example a
vegetarian diet for B12). Simple lookups never pull the questionnaire in.

The matrix only uses question keys that exist in ``questionnaire_definitions``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.pipeline.health_domains import domain_for_entity
from app.pipeline.questionnaire_topics import SUMMARY_KEYS

# Ordered by how often the key changes the advice for that marker.
ENTITY_QUESTIONNAIRE_MATRIX: dict[str, tuple[str, ...]] = {
    # Glycemic / metabolic
    "hba1c": ("physical_activity_frequency", "sitting_hours", "food_groups", "exercise_frequency_week",
              "daily_active_duration", "healthy_breakfast_frequency", "sleeping_hours", "diet_preference"),
    "glucose": ("physical_activity_frequency", "sitting_hours", "food_groups", "exercise_frequency_week",
                "daily_active_duration", "sleeping_hours"),
    "fasting_blood_glucose": ("physical_activity_frequency", "sitting_hours", "food_groups",
                              "exercise_frequency_week", "daily_active_duration", "sleeping_hours"),
    "fasting_insulin": ("physical_activity_frequency", "sitting_hours", "food_groups", "sleeping_hours"),
    "type_2_diabetes": ("physical_activity_frequency", "sitting_hours", "food_groups", "exercise_frequency_week",
                        "sleeping_hours"),
    "metabolic_score": ("physical_activity_frequency", "sitting_hours", "food_groups", "sleeping_hours",
                        "alcohol_frequency"),
    "metabolic_syndrome": ("physical_activity_frequency", "sitting_hours", "food_groups", "sleeping_hours",
                           "alcohol_frequency"),
    "metabolic_age": ("physical_activity_frequency", "sitting_hours", "food_groups", "sleeping_hours"),
    "obesity": ("daily_active_duration", "sitting_hours", "physical_activity_frequency", "food_groups",
                "sleeping_hours"),
    "bmi": ("daily_active_duration", "sitting_hours", "physical_activity_frequency", "food_groups"),
    # Lipids
    "triglycerides": ("alcohol_frequency", "food_groups", "physical_activity_frequency", "sitting_hours",
                      "diet_preference"),
    "ldl": ("food_groups", "diet_preference", "physical_activity_frequency", "tobacco_frequency"),
    "cholesterol": ("food_groups", "diet_preference", "physical_activity_frequency", "tobacco_frequency"),
    "dyslipidemia": ("food_groups", "physical_activity_frequency", "alcohol_frequency", "tobacco_frequency"),
    "hdl": ("physical_activity_frequency", "exercise_frequency_week", "tobacco_frequency", "food_groups"),
    # Cardiac / blood pressure
    "cardiac_health": ("physical_activity_frequency", "tobacco_frequency", "alcohol_frequency", "sleeping_hours"),
    "hypertension": ("physical_activity_frequency", "alcohol_frequency", "tobacco_frequency", "sleeping_hours"),
    "blood_pressure": ("physical_activity_frequency", "alcohol_frequency", "tobacco_frequency", "sleeping_hours"),
    # Liver / NAFLD
    "nafld": ("alcohol_frequency", "physical_activity_frequency", "food_groups", "sitting_hours"),
    "pcos": ("physical_activity_frequency", "sitting_hours", "food_groups", "sleeping_hours"),
    "oxidative_stress": ("tobacco_frequency", "alcohol_frequency", "food_groups", "physical_activity_frequency"),
    "alt": ("alcohol_frequency", "physical_activity_frequency", "food_groups"),
    "ast": ("alcohol_frequency", "physical_activity_frequency", "food_groups"),
    "ggt": ("alcohol_frequency",),
    # Nutrients where diet pattern changes interpretation
    "vitamin_b12": ("diet_preference",),
    "hemoglobin": ("diet_preference",),
    "iron": ("diet_preference",),
    "ferritin": ("diet_preference",),
    # Kidney, thyroid, vitamin D, blood counts: no questionnaire field changes the advice.
}

DOMAIN_QUESTIONNAIRE_MATRIX: dict[str, tuple[str, ...]] = {
    "glycemic_health": ENTITY_QUESTIONNAIRE_MATRIX["hba1c"],
    "metabolic_health": ("physical_activity_frequency", "sitting_hours", "food_groups", "alcohol_frequency",
                         "sleeping_hours"),
    "lipid_health": ENTITY_QUESTIONNAIRE_MATRIX["cholesterol"],
    "cardiovascular_health": ENTITY_QUESTIONNAIRE_MATRIX["cardiac_health"],
    "blood_pressure_health": ENTITY_QUESTIONNAIRE_MATRIX["hypertension"],
    "liver_health": ENTITY_QUESTIONNAIRE_MATRIX["nafld"],
    "weight_body_composition": ENTITY_QUESTIONNAIRE_MATRIX["obesity"],
    "pcos_health": ENTITY_QUESTIONNAIRE_MATRIX["pcos"],
    "inflammation": ENTITY_QUESTIONNAIRE_MATRIX["oxidative_stress"],
    "vitamin_b12_folate_status": ("diet_preference",),
    "iron_status": ("diet_preference",),
    "red_cell_anaemia_health": ("diet_preference",),
    "lifestyle_recovery": SUMMARY_KEYS + ("sitting_hours", "exercise_frequency_week", "food_groups"),
}

# A whole-health or lifestyle review may use the broader set.
REVIEW_KEYS: tuple[str, ...] = (
    "physical_activity_frequency", "sitting_hours", "sleeping_hours", "food_groups", "diet_preference",
    "alcohol_frequency", "tobacco_frequency", "exercise_frequency_week",
)

# Answers to these keys only matter as interpretation context for specific markers.
_CONTEXT_ONLY = {"diet_preference": {"vitamin_b12", "hemoglobin", "iron", "ferritin"}}

LABELS = {
    "sleeping_hours": "sleep",
    "physical_activity_frequency": "physical activity",
    "exercise_level": "exercise intensity",
    "exercise_frequency_week": "exercise frequency",
    "daily_active_duration": "daily active time",
    "sitting_hours": "sitting time",
    "diet_preference": "diet pattern",
    "food_groups": "food choices",
    "healthy_breakfast_frequency": "breakfast",
    "fresh_fruit_frequency": "fruit intake",
    "fresh_vegetable_frequency": "vegetable intake",
    "alcohol_frequency": "alcohol",
    "tobacco_frequency": "tobacco",
}

SUPPORTIVE = "supportive"
LEVER = "possible_lever"
CONTEXT = "interpretation_context"
NEUTRAL = "neutral"

_GUIDANCE = {
    SUPPORTIVE: "Already supportive. Acknowledge briefly only if it changes the advice; do not tell the member to "
                "start doing this or make 'do more of it' the main recommendation.",
    LEVER: "A practical area that may be worth focusing on. User-reported; never say it caused a result.",
    CONTEXT: "Context that can change how the result is interpreted. User-reported.",
}


@dataclass
class QuestionnaireSignal:
    key: str
    label: str
    value: str
    stance: str
    source: str = "questionnaire"  # questionnaire | recent_conversation
    recorded_at: str | None = None

    def for_model(self) -> dict:
        return {
            "area": self.label,
            "reported": self.value,
            "stance": self.stance,
            "source": "user stated in this conversation" if self.source == "recent_conversation" else "questionnaire (user-reported)",
            "use": _GUIDANCE.get(self.stance, ""),
        }


@dataclass
class QuestionnaireSelection:
    signals: list[QuestionnaireSignal] = field(default_factory=list)
    retrieved_keys: list[str] = field(default_factory=list)
    considered_keys: list[str] = field(default_factory=list)
    overridden_keys: list[str] = field(default_factory=list)

    @property
    def selected_keys(self) -> list[str]:
        return [s.key for s in self.signals]


def relevant_questionnaire_keys(entities: list[str] | None, domains: list[str] | None = None) -> list[str]:
    """Questionnaire keys that could change the advice for these markers or domains."""
    keys: list[str] = []
    for entity in entities or []:
        found = ENTITY_QUESTIONNAIRE_MATRIX.get(entity)
        if found is None:
            domain = domain_for_entity(entity)
            found = DOMAIN_QUESTIONNAIRE_MATRIX.get(domain.code, ()) if domain else ()
        keys.extend(found)
    for code in domains or []:
        keys.extend(DOMAIN_QUESTIONNAIRE_MATRIX.get(code, ()))
    return list(dict.fromkeys(keys))


# ---------------------------------------------------------------- stance of an answer

def _has(text: str, *needles: str) -> bool:
    return any(n in text for n in needles)


def stance_for(key: str, value: str, entities: list[str] | None = None) -> str:
    """Calibrated reading of a user-reported answer. Never a clinical judgement."""
    text = (value or "").lower()
    if not text:
        return NEUTRAL
    if key in {"physical_activity_frequency", "exercise_frequency_week"}:
        if _has(text, "rarely", "never", "none", "0-1", "0 ", "1-2", "once"):
            return LEVER
        if _has(text, "3-4", "4-5", "5-6", "6-7", "daily", "every day", "most days", "5 ", "6 ", "7 ") or re.search(r"\b[3-7]\b", text):
            return SUPPORTIVE
        return NEUTRAL
    if key == "exercise_level":
        if _has(text, "sedentary", "none", "light"):
            return LEVER
        if _has(text, "moderate", "vigorous", "high", "intense", "active"):
            return SUPPORTIVE
        return NEUTRAL
    if key == "daily_active_duration":
        if _has(text, "less than 30", "<30", "under 30", "less than 15"):
            return LEVER
        if _has(text, "more than 60", "60", "1 hour", "more than 1", "45"):
            return SUPPORTIVE
        return NEUTRAL
    if key == "sitting_hours":
        if _has(text, "more than 8", "8+", "more than 6", "10", "12", "9"):
            return LEVER
        if _has(text, "less than 4", "2-4", "less than 2", "under 4"):
            return SUPPORTIVE
        return NEUTRAL
    if key == "sleeping_hours":
        hours = [int(n) for n in re.findall(r"\d{1,2}", text)]
        if not hours:
            return NEUTRAL
        low, high = min(hours), max(hours)
        if "less than" in text or "under" in text:
            return LEVER if high <= 6 else NEUTRAL
        if "more than" in text:
            return SUPPORTIVE if low >= 7 else NEUTRAL
        if high < 6 or (high <= 6 and low < 6):
            return LEVER  # e.g. "5-6 hours"
        if low >= 7:
            return SUPPORTIVE  # e.g. "7-8 hours"
        return NEUTRAL  # e.g. "6-7 hours"
    if key == "alcohol_frequency":
        if _has(text, "daily", "every day", "weekly", "most days", "frequent", "regular"):
            return LEVER
        if _has(text, "rarely", "occasionally", "sometimes"):
            return NEUTRAL  # occasional drinking is neither a lever nor a habit to praise
        if _has(text, "never", "no", "don't", "do not"):
            return SUPPORTIVE
        return NEUTRAL
    if key == "tobacco_frequency":
        if _has(text, "never", "no", "don't", "do not", "quit", "stopped", "non"):
            return SUPPORTIVE
        if _has(text, "daily", "occasionally", "weekly", "regular", "smoke"):
            return LEVER
        return NEUTRAL
    if key in {"fresh_fruit_frequency", "fresh_vegetable_frequency", "healthy_breakfast_frequency"}:
        if _has(text, "rarely", "never", "weekly", "once"):
            return LEVER
        if _has(text, "daily", "every day", "most days"):
            return SUPPORTIVE
        return NEUTRAL
    if key == "food_groups":
        if _has(text, "refined", "processed", "fried", "sugar", "sweets", "fast food", "junk"):
            return LEVER
        if _has(text, "whole grain", "vegetables", "pulses", "legumes", "fruits", "balanced"):
            return SUPPORTIVE
        return NEUTRAL
    if key == "diet_preference":
        relevant = set(entities or []) & _CONTEXT_ONLY["diet_preference"]
        if relevant and _has(text, "vegetarian", "vegan", "eggetarian", "jain"):
            return CONTEXT
        return NEUTRAL
    return NEUTRAL


# ---------------------------------------------------------------- recent statements

_RECENT_PATTERNS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    ("physical_activity_frequency",
     re.compile(r"\b(?:i\s+)?(?:now\s+)?(?:work ?out|exercis|go to the gym|train|run|walk|cycl|swim|gym)\w*\b.{0,40}"
                r"\b(?:\d|two|three|four|five|six|seven|daily|every day|most days|regularly)\b", re.I),
     SUPPORTIVE),
    ("physical_activity_frequency",
     re.compile(r"\b(?:i\s+)?(?:don'?t|do not|never|rarely|barely)\s+(?:work ?out|exercise|go to the gym|move much)\b", re.I),
     LEVER),
    ("tobacco_frequency", re.compile(r"\b(?:i\s+)?(?:quit|stopped|gave up|don'?t|do not|never)\s+(?:smok\w*|tobacco)\b", re.I), SUPPORTIVE),
    ("tobacco_frequency", re.compile(r"\bi\s+(?:still\s+)?smoke\b", re.I), LEVER),
    ("alcohol_frequency", re.compile(r"\b(?:i\s+)?(?:quit|stopped|gave up|don'?t|do not|never)\s+(?:drink\w*|alcohol)\b", re.I), SUPPORTIVE),
    ("sleeping_hours", re.compile(r"\bi\s+(?:only\s+)?sleep\s+(?:about\s+|around\s+)?(\d{1,2})\s*(?:-\s*\d{1,2}\s*)?(?:hours|hrs|h)\b", re.I), NEUTRAL),
)

_ACTIVITY_GROUP = {"physical_activity_frequency", "exercise_frequency_week", "exercise_level", "daily_active_duration"}


def recent_statements(messages: list[str]) -> dict[str, QuestionnaireSignal]:
    """Lifestyle facts the member stated in this conversation. Newest wins."""
    found: dict[str, QuestionnaireSignal] = {}
    for text in messages:  # oldest -> newest
        for key, pattern, stance in _RECENT_PATTERNS:
            match = pattern.search(text or "")
            if not match:
                continue
            value = match.group(0).strip()
            if key == "sleeping_hours":
                hours = int(match.group(1))
                stance = LEVER if hours < 6 else SUPPORTIVE if hours >= 7 else NEUTRAL
            found[key] = QuestionnaireSignal(key, LABELS[key], value, stance, source="recent_conversation")
    return found


# ---------------------------------------------------------------- selection

def _answers(questionnaire) -> list:
    out = []
    for item in questionnaire or []:
        answers = getattr(item, "answers", None)
        out.extend(answers if answers is not None else [item])
    # Latest answer per key wins.
    latest: dict[str, object] = {}
    for answer in sorted(out, key=lambda a: str(getattr(a, "recorded_at", "") or "")):
        if getattr(answer, "value", None) not in (None, ""):
            latest[answer.question_key] = answer
    return list(latest.values())


def select_questionnaire_context(
    question: str,
    *,
    entities: list[str] | None,
    domains: list[str] | None = None,
    questionnaire=None,
    review: bool = False,
    recent_messages: list[str] | None = None,
    budget: int | None = None,
    keys: list[str] | None = None,
    subject_keys: list[str] | None = None,
) -> QuestionnaireSelection:
    """Return only the questionnaire answers that would change this answer.

    ``review`` (whole-health or lifestyle review) allows a broader set. Neutral answers
    are dropped: if an answer would not change the interpretation, priority or next
    step, it is not personalization and does not reach the model.
    """
    answers = _answers(questionnaire)
    # ``keys``: candidates chosen by the semantic evidence planner for the question's topics.
    # ``subject_keys``: the habit the question is ABOUT ("am I active enough?"); its answer is
    # kept even when neutral, because it is the fact being judged.
    candidates = list(keys) if keys else list(REVIEW_KEYS) if review else relevant_questionnaire_keys(entities, domains)
    subject = set(subject_keys or [])
    selection = QuestionnaireSelection(retrieved_keys=[a.question_key for a in answers], considered_keys=candidates)
    if not candidates:
        return selection
    by_key = {a.question_key: a for a in answers}
    overrides = recent_statements(list(recent_messages or []) + [question])
    limit = budget if budget is not None else (5 if review else 3)
    picked: list[QuestionnaireSignal] = []
    activity_overridden = "physical_activity_frequency" in overrides
    for key in candidates:
        if key in overrides:
            signal = overrides[key]
            if key in by_key:
                selection.overridden_keys.append(key)
        elif activity_overridden and key in _ACTIVITY_GROUP:
            # A recent statement about activity supersedes every stored activity answer.
            if key in by_key:
                selection.overridden_keys.append(key)
            continue
        elif key in by_key:
            answer = by_key[key]
            value = str(answer.value)
            signal = QuestionnaireSignal(
                key, LABELS.get(key, key.replace("_", " ")), value, stance_for(key, value, entities),
                recorded_at=str(getattr(answer, "recorded_at", "") or "") or None,
            )
        else:
            continue
        if signal.stance == NEUTRAL and key not in subject:
            continue
        if signal.stance == NEUTRAL:
            signal = QuestionnaireSignal(signal.key, signal.label, signal.value, CONTEXT, signal.source, signal.recorded_at)
        if any(p.label == signal.label for p in picked):
            continue
        picked.append(signal)
    # Levers shape the plan; one supportive habit is kept when available because it removes
    # generic advice ("you already exercise, so..."); context answers change interpretation.
    levers = [p for p in picked if p.stance == LEVER]
    context = [p for p in picked if p.stance == CONTEXT]
    # Activity first: "exercise more" is the generic advice most worth suppressing.
    supportive = sorted(
        (p for p in picked if p.stance == SUPPORTIVE), key=lambda p: p.key not in _ACTIVITY_GROUP
    )
    chosen: list[QuestionnaireSignal] = []
    if supportive and limit >= 2:
        chosen.append(supportive.pop(0))
    for group in (context, levers, supportive):
        for signal in group:
            if len(chosen) >= limit:
                break
            chosen.append(signal)
    order = {LEVER: 0, CONTEXT: 1, SUPPORTIVE: 2}
    chosen.sort(key=lambda s: order.get(s.stance, 3))
    selection.signals = chosen
    return selection


# ---------------------------------------------------------------- when to fetch

_ADVICE = re.compile(
    r"\b(how (?:can|do|should) i|what (?:can|should) i (?:do|eat|change)|what to do|tips|"
    r"improve|lower|reduce|raise|increase|bring (?:down|up)|manage|plan|change first|focus on|priorit)\w*",
    re.I,
)
_WHY = re.compile(r"\bwhy\b|\bwhat (?:could|might) (?:cause|explain)|\breason\b", re.I)


def should_enrich_with_questionnaire(
    message: str,
    *,
    personal: bool,
    entities: list[str] | None,
    domains: list[str] | None,
    overall: bool = False,
    explicit: bool = False,
) -> bool:
    """Relevance-driven enrichment: fetch the questionnaire only when it can change the answer."""
    if explicit:
        return True
    if not personal:
        return False
    if overall:
        return True
    if not relevant_questionnaire_keys(entities, domains):
        return False
    return bool(_ADVICE.search(message or "") or _WHY.search(message or ""))
