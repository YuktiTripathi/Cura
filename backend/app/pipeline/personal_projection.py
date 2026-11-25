"""A small, typed slice of what CURA knows about the member, chosen for one question.

The prompt never receives the whole profile. Each lifestyle field is sent only when a question key it
stands for can change the answer for the results being discussed (see questionnaire_relevance), or
when the person asked about food. Everything else stays out. A field that is missing is simply not
sent, so the model cannot read it as a negative answer.
"""

from __future__ import annotations

import re

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


_FACT_KEYS = {
    "dietary_preference": ("diet_preference", "food_groups", "healthy_breakfast_frequency"),
    "activity_level": ("physical_activity_frequency", "exercise_frequency_week", "daily_active_duration", "exercise_level", "sitting_hours"),
    "sleep_quality": ("sleeping_hours",),
    "alcohol": ("alcohol_frequency",),
    "smoking": ("tobacco_frequency",),
}
_CAUSE_WORDS = ("why", "cause", "reason", "explain", "mean", "low", "high", "what can i", "what should i", "protect", "improve", "eat", "diet", "food", "relate")


def _fact(row) -> dict:
    out = {"value": row.value}
    if getattr(row, "unit", None):
        out["unit"] = row.unit
    out["source"] = row.source_type or row.source
    when = getattr(row, "measured_at", None)
    if when:
        out["recorded"] = str(when)[:10]
    return out


def personal_context_payload(context, message: str = "") -> dict:
    """The one personal context every personal chat path sends to the model.

    It reads what the member snapshot already placed on the context, so nothing is fetched again. Names,
    contact details, identifiers and dates of birth never appear. Sex is sent only when recorded, never
    guessed from a name. Each lifestyle fact carries its source and recording date. A field that is not
    available is left out, so it cannot be read as a negative answer.
    """
    from app.pipeline.turn_kinds import TurnKind, kind_of

    text = (message or "").lower()
    intent = getattr(getattr(context, "intent", None), "value", "") or ""
    entities = [*(getattr(context, "requested_entity_codes", None) or []), *(getattr(context, "display_entity_codes", None) or [])]
    food = kind_of(context, message) == TurnKind.nutrition_overview or intent == "nutrition_guidance" or bool(re.search(r"\b(eat|diet|food|vegetarian|vegan|meal)\b", text))
    interpretive = food or any(word in text for word in _CAUSE_WORDS)
    keys = set(relevant_questionnaire_keys(entities))
    if food:
        keys.update(_FACT_KEYS["dietary_preference"])
    out: dict = {}
    profile = getattr(context, "profile", None)
    if profile is not None:
        about = {}
        for row in profile.preferences or []:
            if row.fact in {"age_band", "sex"} and row.value not in (None, ""):
                about[row.fact] = row.value
        if about:
            out["about_member"] = about
        if interpretive:
            diet = [str(r.value) for r in (profile.dietary_preferences or []) if r.value]
            states_own_diet = bool(re.search(r"\b(if i (?:follow|am|eat|was)|as a|i am a|i'm a)\b[^?.]*\b(vegetarian|vegan|keto|jain|eggetarian|pescatarian)", text))
            if diet and not states_own_diet and keys.intersection(_FACT_KEYS["dietary_preference"]):
                out["dietary_preference"] = _fact(profile.dietary_preferences[0]) | {"value": diet[0]}
            allergies = [str(r.value) for r in (profile.allergies or []) if r.value]
            if allergies and (food or "eat" in text):
                out["allergies_and_restrictions"] = allergies[:6]
            meds = [str(r.value) for r in (profile.medications or []) if r.value]
            if meds:
                out["medicines_recorded"] = meds[:6]
            # Bio-AI levels are sent with their assessment names in the evidence, never as bare conditions here.
            life = {}
            for row in profile.lifestyle or []:
                wanted = _FACT_KEYS.get(row.fact)
                if wanted and row.fact != "dietary_preference" and keys.intersection(wanted) and row.value not in (None, ""):
                    life[row.fact] = _fact(row)
            if life:
                out["lifestyle"] = life
    perso = getattr(context, "personalization", None)
    if perso is not None:
        projected = {"communication_preference": perso.communication_preference.value}
        recent = perso.recent_user_context.model_dump(mode="json", exclude_none=True)
        if any(recent.get(k) for k in ("symptoms", "supplements", "medications", "illness", "pregnancy", "fasting_status")):
            projected["recent_user_context"] = recent
        if intent in {"trend", "previous_result", "bio_ai_comparison"}:
            projected["longitudinal"] = perso.compact_longitudinal.model_dump(mode="json")
        out["personalization"] = projected
    goals = [g for g in (getattr(context, "goals", None) or []) if set(getattr(g, "target_metrics", None) or []) & set(entities) or "goal" in text or intent == "health_goal_progress"]
    if goals:
        out["goals"] = [{"goal": g.goal_code, "label": g.label, "target_metrics": list(g.target_metrics or [])[:6]} for g in goals[:3]]
    screen = getattr(context, "screen_context", None)
    if screen:
        out["screen_context"] = screen
    return out


def personal_context_block(context, message: str = "") -> str:
    import json

    payload = personal_context_payload(context, message)
    if not payload:
        return ""
    return "PERSONAL CONTEXT (verified, selected for this question; anything not listed is unknown, not negative):\n" + json.dumps(payload, separators=(",", ":"), default=str) + "\n"
