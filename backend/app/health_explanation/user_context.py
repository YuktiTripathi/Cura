"""What the member has told us, read from their own profile and questionnaire, never from the browser.

Reported information is kept apart from measured information. A factor that is not on record is listed as not
reported, never assumed absent. Wording the app cannot classify safely is shown as written and used for nothing.
"""

from __future__ import annotations

import logging
import re

from app.health_explanation.story_schema import LifestyleFactor

logger = logging.getLogger("cura.story")

_LABELS = {"age": "Age", "sex": "Sex", "activity": "Physical activity", "diet": "Eating pattern", "sleep": "Sleep", "smoking": "Smoking", "alcohol": "Alcohol", "stress": "Stress", "conditions": "Health conditions you reported", "allergies": "Allergies you reported"}
_TRACKED = ("age", "sex", "activity", "diet", "sleep", "smoking", "alcohol", "stress", "conditions", "allergies")
_EXACT = {"age": ("age", "age_years"), "sex": ("sex", "gender", "biological_sex")}


def classify_activity(text: str | None) -> str | None:
    t = (text or "").strip().lower()
    if not t:
        return None
    if re.search(r"\b(not|never|no)\b.{0,12}\b(active|exercise|exercising|workout)|inactive|sedentary|rarely|seldom|\bnone\b|\blow\b|\blight\b|\bsit", t):
        return "low"
    if re.search(r"\b(5|6|7)\b|3\s*[-–to]+\s*4|4\s*[-–to]+\s*5|5\s*[-–to]+\s*6|daily|every day|most days|\bactive\b|\bhigh\b|\bmoderate\b|vigorous|regular", t):
        return "active"
    return None


def classify_diet(text: str | None) -> str | None:
    t = (text or "").strip().lower()
    if not t:
        return None
    if re.search(r"non[\s-]?veg|nonveg|meat|chicken|fish|mutton|pescatarian", t):
        return "non_vegetarian"
    if "vegan" in t:
        return "vegan"
    if "eggetarian" in t or "ovo" in t:
        return "eggetarian"
    if "veg" in t:
        return "vegetarian"
    return None


def _first(facts, *needles: str):
    for f in facts:
        blob = f"{f.fact} {f.question_id or ''} {f.value or ''}".lower()
        if any(n in blob for n in needles):
            return f
    return None


def _date(fact) -> str | None:
    value = getattr(fact, "measured_at", None)
    return str(value)[:10] if value else None


def read_lifestyle(profile, summary) -> list[LifestyleFactor]:
    """Lifestyle factors with provenance. `profile` is a PersonalHealthProfile or None, `summary` a LifestyleSummary or None."""
    facts = list(getattr(profile, "lifestyle", []) or []) + list(getattr(profile, "questionnaire", []) or [])
    diet_facts = list(getattr(profile, "dietary_preferences", []) or [])
    found: dict[str, tuple[str, object]] = {}
    act = getattr(summary, "activity_level", None) or _first(facts, "activity", "exercise")
    if act and act.value not in (None, ""):
        found["activity"] = (str(act.value), act)
    diet = getattr(summary, "dietary_pattern", None) or (diet_facts[0] if diet_facts else None) or _first(facts, "diet")
    if diet is not None:
        value = diet.value if diet.value not in (None, "") else diet.fact
        found["diet"] = (str(value), diet)
    sleep = getattr(summary, "sleep_pattern", None) or _first(facts, "sleep")
    if sleep and sleep.value not in (None, ""):
        found["sleep"] = (str(sleep.value), sleep)
    for key, needles in (("smoking", ("smok", "tobacco")), ("alcohol", ("alcohol", "drink")), ("stress", ("stress",))):
        f = _first(facts, *needles)
        if f is not None and (f.value not in (None, "") or f.fact):
            found[key] = (str(f.value if f.value not in (None, "") else f.fact), f)
    # Age and sex only from a question that is exactly that, so words like "usage" never match.
    for key, ids in _EXACT.items():
        for f in facts:
            if (f.question_id or "").lower() in ids and f.value not in (None, ""):
                found[key] = (str(f.value), f)
                break
    for key, group in (("conditions", getattr(profile, "relevant_conditions", []) or []), ("allergies", getattr(profile, "allergies", []) or [])):
        texts = [str(f.value if f.value not in (None, "") else f.fact) for f in group if (f.value not in (None, "") or f.fact)]
        if texts:
            found[key] = ("; ".join(texts[:4]), group[0])
    out: list[LifestyleFactor] = []
    for key in _TRACKED:
        if key in found:
            value, fact = found[key]
            level = classify_activity(value) if key == "activity" else classify_diet(value) if key == "diet" else None
            out.append(LifestyleFactor(key=key, label=_LABELS[key], state="reported", value=value, level=level, recorded_at=_date(fact), evidence_ids=[f"reported:{key}"]))
        else:
            out.append(LifestyleFactor(key=key, label=_LABELS[key], state="not_reported"))
    return out


def load_lifestyle(principal, registry, db) -> list[LifestyleFactor]:
    """Never raises. Without a profile every factor is simply not reported."""
    try:
        from app.pipeline.health_snapshot import build_personal_health_snapshot

        snap = build_personal_health_snapshot(principal, registry, db=db)
        return read_lifestyle(snap.profile, snap.lifestyle_summary)
    except Exception as exc:  # noqa: BLE001 - the story still works from measured data
        logger.warning("story_lifestyle_unavailable error=%s", type(exc).__name__)
        return read_lifestyle(None, None)


def value_of(factors: list[LifestyleFactor], key: str) -> str:
    for f in factors:
        if f.key == key and f.state == "reported":
            return (f.value or "").lower()
    return ""


def level_of(factors: list[LifestyleFactor], key: str) -> str:
    """normalized level, or 'not_reported', or 'unclassified' when reported in words the app does not classify."""
    for f in factors:
        if f.key == key:
            if f.state == "not_reported":
                return "not_reported"
            return f.level or "unclassified"
    return "not_reported"
