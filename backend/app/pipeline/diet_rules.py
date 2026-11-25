"""Keep deterministic food text inside the diet the person follows or asked about.

Used only on text CURA wrote itself (the model is told the diet directly). A diet stated in the
conversation is a scenario, never a change to the stored profile. Allergies are handled elsewhere and
are never relaxed.
"""

from __future__ import annotations

import re

_PLANT_ONLY = {"vegetarian", "vegan", "jain", "eggetarian"}
_ANIMAL = re.compile(r"\b(chicken|mutton|meat|fish|salmon|sardines?|mackerel|prawns?|beef|pork|poultry)\b", re.I)
_EGG_OR_DAIRY = re.compile(r"\b(eggs?|egg yolks?|milk|curd|dahi|paneer|cheese|yogh?urt|dairy|ghee|butter)\b", re.I)

_REPLACEMENTS = (
    (re.compile(r"oily fish such as salmon, sardines and mackerel, ", re.I), ""),
    (re.compile(r"eggs, fish or lean meat, and fortified foods", re.I), "nuts, seeds and fortified foods"),
    (re.compile(r"egg yolks, and milk, curd or cereals fortified with vitamin D", re.I), "and foods fortified with vitamin D"),
    (re.compile(r"\bfish or lean meat\b", re.I), "plant protein"),
)


def recorded_diet(context) -> str | None:
    profile = getattr(context, "profile", None)
    for row in (getattr(profile, "dietary_preferences", None) or []):
        value = str(getattr(row, "value", "") or "").lower()
        if "non" in value:
            return None
        for diet in _PLANT_ONLY:
            if diet in value:
                return diet
    return None


def diet_in_force(context, message: str = "") -> str | None:
    from app.pipeline.personal_projection import active_diet_scenario

    scenario = active_diet_scenario(context, message)
    if scenario:
        return scenario["diet"]
    return recorded_diet(context)


def apply_diet(text: str, diet: str | None) -> str:
    if not text or diet not in _PLANT_ONLY:
        return text
    out = text
    for pattern, repl in _REPLACEMENTS:
        out = pattern.sub(repl, out)
    strict = diet != "eggetarian"
    kept: list[str] = []
    for part in re.split(r"(?<=[.!?])\s+|\n", out):
        if not part.strip():
            continue
        if _ANIMAL.search(part) or (strict and diet in {"vegan", "jain"} and _EGG_OR_DAIRY.search(part)):
            continue
        kept.append(part)
    return "\n".join(kept) if "\n" in out else " ".join(kept)
