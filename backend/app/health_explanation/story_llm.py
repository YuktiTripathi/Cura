"""Optional model narration for the health story. The model writes short lead lines and questions, nothing else.

It never sees or writes a value, range, date or score. It cannot add, remove or reorder findings, relationships or
actions. Anything it writes must pass the number guard and the safety validator or it is dropped, and the story
simply keeps its rules text. If the model is off or fails, the story is already complete.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re

from app.health_explanation.safety_validator import safety_problems
from app.health_explanation.story_schema import HealthStory

logger = logging.getLogger("cura.story")
_TTL = 7 * 24 * 3600
_DASH = re.compile(r"\s*[—–]\s*")
_NUMBER = re.compile(r"\d")

SYSTEM = """You write short, friendly lead lines for a health education screen. You are given facts already decided by the app.
You do not decide anything. You only communicate it.

Rules:
- Use only the facts in the JSON. Never invent a result, habit, condition, cause or number. Never write any digit.
- Keep measured results (from a blood report), predicted risks (from the Bio-AI assessment) and reported lifestyle (from the questionnaire) clearly separate.
- Never diagnose. Never say a result or score proves, rules out or causes anything. Say "can be linked with" at most.
- Never advise medicines, supplements or doses. Never promise an action will change a score or result.
- If something is not reported, do not assume it. Do not mention missing information unless it is in "not_reported".
- Plain words for a person with no medical knowledge. No dashes. Do not repeat the same idea in two lines.
- Write in the requested language.

Return only JSON: {"headline": "5 to 9 words", "lead_assessment": "1 sentence", "lead_personal": "1 to 2 sentences", "lead_plan": "1 sentence", "questions": ["up to 4 short questions the person could ask next, based only on the facts"]}"""


def build_payload(story: HealthStory, language: str = "en") -> dict:
    """The minimum the model needs. No values, ranges, dates or scores are included."""
    return {
        "category": story.category_name,
        "language": language,
        "reading_level": "simple",
        "measured": [{"name": m.finding.name, "status": m.finding.status_label} for m in story.personal_factors.measured],
        "predicted": [{"name": r.name, "group": r.classification} for r in story.your_assessment.risks],
        "reported_lifestyle": [{"factor": x.label, "level": x.level or "reported"} for x in story.personal_factors.lifestyle if x.state == "reported"],
        "not_reported": [x.label for x in story.personal_factors.lifestyle if x.state == "not_reported"],
        "approved_relationships": [r.text for r in story.personal_factors.relationships],
        "approved_actions": [a.title for a in story.improvement_plan.actions],
        "data_state": story.metadata.data_state,
    }


def _ok(text) -> str:
    t = _DASH.sub(", ", str(text or "")).strip()
    if not t or _NUMBER.search(t):
        return ""
    if safety_problems(t):
        logger.warning("story_safety_rejected")
        return ""
    return t[:300]


def apply_narration(story: HealthStory, raw: dict, model: str | None) -> HealthStory:
    """Adds only fields that pass. Returns a copy; the facts are untouched."""
    out = story.model_copy(deep=True)
    changed = False
    headline = _ok(raw.get("headline"))
    if headline and len(headline.split()) <= 12:
        out.headline, changed = headline, True
    for key, setter in (("lead_assessment", "assessment"), ("lead_personal", "personal"), ("lead_plan", "plan")):
        text = _ok(raw.get(key))
        if not text:
            continue
        changed = True
        if setter == "assessment" and out.your_assessment.available:
            out.your_assessment.lead = text
        elif setter == "personal":
            out.personal_factors.lead = text
        elif setter == "plan" and out.improvement_plan.actions:
            out.improvement_plan.lead = text
    questions = [q for q in (_ok(q) for q in (raw.get("questions") or [])[:4]) if q and q.endswith("?")]
    if questions:
        merged = questions + [q for q in out.next_steps.suggested_questions if q not in questions]
        out.next_steps.suggested_questions, changed = merged[:5], True
    if changed:
        out.metadata.generation = "model"
        out.metadata.generation_model = model
    return out


def cache_key(member_token: str, story: HealthStory, language: str) -> str:
    m = story.metadata
    material = json.dumps([story.category_id, m.evidence_version, m.knowledge_version, m.rules_version, m.actions_version, m.prompt_version, language])
    return f"cura:story:{member_token}:{hashlib.sha256(material.encode()).hexdigest()[:24]}"


def narrate(subject_id: str, story: HealthStory, language: str = "en", client=None) -> HealthStory:
    """Cached model narration, or the unchanged story. Never raises."""
    from app.core.request_controls import request_controls
    from app.providers.cache import member_token

    if story.metadata.data_state == "empty":
        return story
    key = cache_key(member_token(subject_id), story, language)
    try:
        cached = request_controls._get(key)
    except Exception:  # noqa: BLE001
        cached = None
    if cached:
        try:
            data = json.loads(cached)
            return apply_narration(story, data["raw"], data.get("model"))
        except Exception:  # noqa: BLE001
            logger.warning("story_cache_unreadable")
    try:
        if client is None:
            from app.llm.factory import get_llm_client

            client = get_llm_client(personal_health=True)
        text = client.complete([{"role": "system", "content": SYSTEM}, {"role": "user", "content": json.dumps(build_payload(story, language))}], json_mode=True)
        raw = json.loads(text[text.find("{") : text.rfind("}") + 1])
        model = getattr(client, "model", None)
        result = apply_narration(story, raw, model if isinstance(model, str) else None)
        if result.metadata.generation == "model":
            try:
                request_controls._set(key, json.dumps({"raw": raw, "model": model if isinstance(model, str) else None}), _TTL)
            except Exception:  # noqa: BLE001
                pass
        return result
    except Exception as exc:  # noqa: BLE001 - the rules story is complete without the model
        logger.warning("story_model_failed error=%s", type(exc).__name__)
        return story
