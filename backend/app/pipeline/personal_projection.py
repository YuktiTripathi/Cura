"""A small, typed slice of what CURA knows about the member, chosen for one question.

The prompt never receives the whole profile. Each lifestyle field is sent only when a question key it
stands for can change the answer for the results being discussed (see questionnaire_relevance), or
when the person asked about food. Everything else stays out. A field that is missing is simply not
sent, so the model cannot read it as a negative answer.
"""

from __future__ import annotations

from app.pipeline.questionnaire_relevance import relevant_questionnaire_keys

# Which lifestyle field answers which questionnaire keys.
_FIELD_KEYS: dict[str, tuple[str, ...]] = {
    "sleep": ("sleeping_hours",),
    "activity": ("physical_activity_frequency", "exercise_frequency_week", "daily_active_duration", "sitting_hours"),
    "diet": ("diet_preference", "food_groups", "healthy_breakfast_frequency"),
    "alcohol": ("alcohol_frequency",),
    "smoking": ("tobacco_frequency",),
}


def project_personalization(perso, *, entities: list[str] | None, food_question: bool = False, wants_history: bool = False) -> dict:
    """Return the personalization payload for one question. Always small, often just the goal."""
    keys = set(relevant_questionnaire_keys(entities))
    if food_question:
        keys.update(_FIELD_KEYS["diet"])
    lifestyle = perso.known_lifestyle.model_dump(mode="json", exclude_none=True)
    chosen = {
        field: lifestyle[field]
        for field, field_keys in _FIELD_KEYS.items()
        if field in lifestyle and keys.intersection(field_keys)
    }
    out: dict = {
        "primary_health_goal": perso.primary_health_goal,
        "communication_preference": perso.communication_preference.value,
    }
    if chosen:
        out["known_lifestyle"] = chosen
    if perso.dietary_preferences and keys.intersection(_FIELD_KEYS["diet"]):
        out["dietary_preferences"] = perso.dietary_preferences
    supportive = [item for item in perso.known_lifestyle.already_supportive if chosen]
    if supportive:
        out["already_supportive_lifestyle"] = supportive
    recent = perso.recent_user_context.model_dump(mode="json", exclude_none=True)
    if any(recent.get(k) for k in ("symptoms", "supplements", "medications", "illness", "pregnancy", "fasting_status")):
        # What the person said in this chat can change how a result is read, so it travels.
        out["recent_user_context"] = recent
    if wants_history:
        out["longitudinal"] = perso.compact_longitudinal.model_dump(mode="json")
        out["improved_domains"] = perso.improved_domains[:6]
        out["reassuring_domains"] = perso.reassuring_domains[:6]
    return out
