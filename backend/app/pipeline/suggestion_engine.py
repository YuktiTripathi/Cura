"""Deterministic welcome questions. No answer-model call."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass

from app.pipeline.starters import GENERAL_POOL, HealthSnapshot

logger = logging.getLogger("cura.suggestions")

_PREFERRED = ("hba1c", "ldl", "hdl", "triglycerides", "vitamin_d", "tsh", "vitamin_b12", "glucose")


@dataclass(frozen=True)
class Suggestion:
    id: str
    text: str
    category: str


def _rotate(items: list[Suggestion], salt: str) -> list[Suggestion]:
    if len(items) < 2:
        return items
    start = int(hashlib.sha256(salt.encode()).hexdigest()[:8], 16) % len(items)
    return items[start:] + items[:start]


def candidates_for(snap: HealthSnapshot) -> list[Suggestion]:
    rows: list[Suggestion] = []
    if snap.has_blood:
        rows.append(
            Suggestion("blood.overview", "What stands out in my latest blood report?", "blood_report")
        )
    flagged = [m for m in snap.markers if str(getattr(m.flag, "value", m.flag)) in {"low", "high", "critical"}]
    rest = [m for m in snap.markers if m not in flagged]
    rest.sort(key=lambda m: (_PREFERRED.index(m.key) if m.key in _PREFERRED else 50, m.name))
    for marker in (flagged + rest)[:4]:
        name = marker.name
        rows.append(Suggestion(f"marker.{marker.key}.meaning", f"What does my {name} result mean?", "blood_report"))
    trend = [key for key, count in snap.marker_history.items() if count >= 2]
    if trend and snap.has_blood:
        rows.append(
            Suggestion("blood.trend", "Have my results changed since my previous report?", "comparison")
        )
    if snap.has_bio:
        rows.append(Suggestion("bio.overview", "What do my Bio-AI scores mean?", "bio_ai"))
        rows.append(Suggestion("bio.attention", "Which of my Bio-AI scores deserve attention?", "bio_ai"))
    if snap.has_bio and snap.has_blood:
        rows.append(
            Suggestion(
                "cross.blood_bio",
                "How does my Bio-AI report compare with my blood results?",
                "comparison",
            )
        )
    topics = set(getattr(snap, "lifestyle_topics", set()) or [])
    if snap.has_nutrition or "diet" in topics:
        rows.append(Suggestion("life.nutrition", "What does my eating pattern suggest?", "lifestyle"))
    if "sleep" in topics:
        rows.append(Suggestion("life.sleep", "What does my sleep pattern say about my health?", "lifestyle"))
    if "activity" in topics:
        rows.append(Suggestion("life.activity", "How can I improve my daily activity?", "lifestyle"))
    if snap.has_blood or snap.has_bio:
        rows.append(Suggestion("priority.overview", "Which health concern should I understand first?", "comparison"))
    for key, text in GENERAL_POOL:
        rows.append(Suggestion(f"general.{key}", text, "general_education"))
    return rows


def _journey_suggestions(snap: HealthSnapshot, avoid: set[str], limit: int) -> list[Suggestion]:
    """Opening questions from the member's own findings (followup_generator), most important first."""
    if not (snap.has_blood or snap.has_bio):
        return []
    from app.pipeline.followup_generator import build_brief, select_followups, stage_of

    from app.contracts.blood import BloodMarker

    markers = []
    for m in snap.markers or []:
        try:
            markers.append(m if isinstance(m, BloodMarker) else BloodMarker(
                id=str(getattr(m, "id", "") or getattr(m, "key", "")), key=getattr(m, "key", ""),
                name=getattr(m, "name", "") or getattr(m, "key", ""), value=getattr(m, "value", None),
                unit=getattr(m, "unit", None), flag=getattr(m, "flag", "unknown"),
            ))
        except ValueError:
            continue
    brief = build_brief(
        markers=markers,
        risks=list(snap.bio_risks or []),
        history_keys={key for key, count in (snap.marker_history or {}).items() if count >= 2},
    )
    out: list[Suggestion] = []
    for text in select_followups(brief, current_question=None, count=limit + 2):
        sid = "journey." + hashlib.sha256(text.lower().encode()).hexdigest()[:10]
        if sid in avoid:
            continue
        out.append(Suggestion(sid, text, f"journey_{stage_of(text) or 'start'}"))
    return out[:limit]


def choose_suggestions(
    snap: HealthSnapshot,
    *,
    avoid_ids: set[str] | None = None,
    salt: str = "",
    limit: int = 4,
) -> list[Suggestion]:
    started = time.perf_counter()
    avoid = avoid_ids or set()
    journey = _journey_suggestions(snap, avoid, limit)
    if len(journey) >= min(3, limit):
        logger.info("suggestion_generated source=journey selected=%s", len(journey))
        return journey
    pool = candidates_for(snap)
    fresh = [item for item in pool if item.id not in avoid]
    fallback = not fresh
    source = fresh or pool
    order = ("blood_report", "lifestyle", "general_education", "comparison", "bio_ai")
    picked: list[Suggestion] = []
    seen: set[str] = set()
    for category in order:
        group = _rotate([item for item in source if item.category == category and item.id not in seen], salt + category)
        if not group:
            continue
        picked.append(group[0])
        seen.add(group[0].id)
        if len(picked) >= limit:
            break
    for item in _rotate(source, salt + "fill"):
        if len(picked) >= limit:
            break
        if item.id in seen:
            continue
        picked.append(item)
        seen.add(item.id)
    elapsed = int((time.perf_counter() - started) * 1000)
    logger.info(
        "suggestion_generated latency_ms=%s candidates=%s selected=%s fallback=%s",
        elapsed,
        len(pool),
        len(picked),
        int(fallback),
    )
    return picked[:limit]


def suggestions_from_json(raw: str | None) -> list[dict]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return [item for item in data if isinstance(item, dict) and item.get("text")]


def recent_suggestion_ids(db, subject_id: str) -> set[str]:
    from sqlalchemy import select

    from app.db.models import Conversation

    rows = db.scalars(
        select(Conversation.suggestions_json)
        .where(Conversation.subject_id == subject_id, Conversation.suggestions_json.is_not(None))
        .order_by(Conversation.created_at.desc())
        .limit(6)
    )
    found: set[str] = set()
    for raw in rows:
        for item in suggestions_from_json(raw):
            if item.get("id"):
                found.add(item["id"])
    return found


def assign_suggestions(conv, principal, registry, db) -> list[dict]:
    """Write a snapshot once. A second call for the same conversation returns the saved set."""
    existing = suggestions_from_json(getattr(conv, "suggestions_json", None))
    if existing:
        return existing
    from app.pipeline.starters import collect_snapshot

    snap = collect_snapshot(principal, registry)
    chosen = choose_suggestions(snap, avoid_ids=recent_suggestion_ids(db, conv.subject_id), salt=conv.id)
    payload = [{"id": item.id, "text": item.text, "category": item.category} for item in chosen]
    conv.suggestions_json = json.dumps(payload)
    db.commit()
    return payload

