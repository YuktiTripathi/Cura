"""Map user language onto stored questionnaire_definitions.question_key values."""

from __future__ import annotations

import re

# Latest-answer snapshot / default retrieval. Not lab measurements.
SUMMARY_KEYS = (
    "sleeping_hours",
    "physical_activity_frequency",
    "exercise_level",
    "diet_preference",
    "alcohol_frequency",
    "tobacco_frequency",
)

TOPIC_KEYS: dict[str, tuple[str, ...]] = {
    "sleep": ("sleeping_hours",),
    "sleeping_hours": ("sleeping_hours",),
    "alcohol": ("alcohol_frequency",),
    "alcohol_frequency": ("alcohol_frequency",),
    "diet": ("diet_preference", "food_groups", "healthy_breakfast_frequency", "fresh_fruit_frequency"),
    "dietary": ("diet_preference", "food_groups"),
    "nutrition": ("diet_preference", "food_groups", "fresh_vegetable_frequency"),
    "diet_preference": ("diet_preference",),
    "activity": (
        "physical_activity_frequency",
        "exercise_frequency_week",
        "exercise_level",
        "daily_active_duration",
        "sitting_hours",
    ),
    "exercise": ("exercise_frequency_week", "exercise_level", "physical_activity_frequency"),
    "physical_activity": ("physical_activity_frequency", "daily_active_duration"),
    "physical_activity_frequency": ("physical_activity_frequency",),
    "tobacco": ("tobacco_frequency",),
    "smoking": ("tobacco_frequency",),
    "lifestyle": SUMMARY_KEYS,
}

_TOPIC_ALIASES = {
    "sleep": "sleep",
    "sleeping": "sleep",
    "alcohol": "alcohol",
    "drinking": "alcohol",
    "diet": "diet",
    "dietary": "dietary",
    "nutrition": "nutrition",
    "food": "diet",
    "activity": "activity",
    "exercise": "exercise",
    "workout": "exercise",
    "physical activity": "physical_activity",
    "tobacco": "tobacco",
    "smoking": "smoking",
    "smoke": "smoking",
    "lifestyle": "lifestyle",
}


def questionnaire_topic(message: str) -> str | None:
    text = (message or "").lower()
    for alias, key in sorted(_TOPIC_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        if re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", text):
            return key
    return None


LAB_METRIC_KEYS = {
    "ldl",
    "hdl",
    "cholesterol",
    "triglycerides",
    "hba1c",
    "glucose",
    "fasting_blood_glucose",
    "hemoglobin",
    "vitamin_d",
    "vitamin_b12",
    "cardiac_health",
    "dyslipidemia",
    "nafld",
    "obesity",
    "hypertension",
    "type_2_diabetes",
    "metabolic_age",
    "metabolic_score",
    "pcos",
}


def keys_for_plan(
    topic: str | None,
    requested_metrics: list[str] | None = None,
    message: str = "",
) -> list[str]:
    keys: list[str] = []
    for item in requested_metrics or []:
        if item in LAB_METRIC_KEYS:
            continue
        keys.extend(TOPIC_KEYS.get(item, (item,)))
    q_topic = topic
    if topic in LAB_METRIC_KEYS:
        q_topic = questionnaire_topic(message)
    if q_topic:
        if q_topic in TOPIC_KEYS:
            keys.extend(TOPIC_KEYS[q_topic])
        else:
            keys.append(q_topic)
    out: list[str] = []
    for key in keys:
        if key and key not in out:
            out.append(key)
    return out or list(SUMMARY_KEYS)


def lifestyle_summary_key(question_key: str) -> str | None:
    return {
        "physical_activity_frequency": "activity_level",
        "exercise_level": "activity_level",
        "sleeping_hours": "sleep_pattern",
        "diet_preference": "dietary_pattern",
    }.get(question_key)
