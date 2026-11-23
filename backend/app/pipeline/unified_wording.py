"""Wording for the unified overview: rules text as the floor, one model request on top.

The model writes sentences only. It is given the verified findings and never asked for a number;
any number it writes that is not in the data it was given drops that field back to the rules text.
All categories are written in one request, cached per member and per report versions, and the
category screens reuse that same cached text.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field

from app.biomarkers.health_categories import REGISTRY_VERSION, category_for
from app.contracts.unified_health import CategoryCard, Priority, Provenance
from app.health_explanation.safety_validator import safety_problems

logger = logging.getLogger("cura.unified")
PROMPT_VERSION = "u4"
_TTL = 7 * 24 * 3600
_DASH = re.compile(r"\s*[—–]\s*")
_NUMBER = re.compile(r"\d+(?:\.\d+)?")


@dataclass
class Wording:
    opening: str = ""
    priorities: list[Priority] = field(default_factory=list)
    categories: dict[str, dict] = field(default_factory=dict)
    source: str = "rules"


def _join(names: list[str]) -> str:
    names = [n for n in names if n]
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


def _verb(names: list[str], one="is", many="are") -> str:
    return one if len(names) == 1 else many


def _names(findings, statuses) -> list[str]:
    return [f.name for f in findings if f.status in statuses]


def _summary(card: CategoryCard, p) -> str:
    out = _names(p.measured, {"above_range", "below_range", "critical"})[:2]
    raised = _names(p.risks, {"risk_raised"})
    healthy = _names(p.risks, {"risk_healthy"})
    s = card.scenario
    if s == "both_reassuring":
        return "Your measured results and predicted risks here are all where we would hope."
    if s == "blood_out_risk_ok":
        return f"{_join(out)} {_verb(out)} outside range, even though your predicted {_join(healthy[:2])} risk is in the healthy band."
    if s == "blood_ok_risk_up":
        return f"Your measured results are within range, but your predicted {_join(raised[:2])} risk is increased."
    if s == "both_out":
        return f"{_join(out)} {_verb(out)} outside range, and your predicted {_join(raised[:2])} risk is increased."
    if s == "blood_only":
        return f"{_join(out)} {_verb(out)} outside range." if out else "Your measured results here are within range."
    if s == "risk_only":
        return f"Your predicted {_join(raised[:2])} risk is increased." if raised else f"Your predicted {_join(healthy[:2])} risk is in the healthy band."
    return "Some results here are unavailable, so this area is not fully assessed."


def _interpretation(card: CategoryCard, p, prov: Provenance) -> list[str]:
    s = card.scenario
    from app.health_explanation.relationship_engine import rules

    # The four scenarios that compare blood results with the prediction use the approved relationship wording.
    approved = [r["interpretation"] for r in rules()["scenario_rules"] if r["scenario"] == s]
    if approved:
        return approved
    return {
        "blood_only": ["This is based on your measured results only. No Bio-AI risk was assessed for this area."],
        "risk_only": ["This is based on your predicted risk only. No blood results were available for this area."],
    }.get(s, ["Some information is missing, so this area cannot be fully assessed yet."])


def _actions(card: CategoryCard, p) -> list[dict]:
    out = _names(p.measured, {"above_range", "below_range", "critical"})
    raised = _names(p.risks, {"risk_raised"})
    items: list[dict] = []
    if out:
        items.append({"title": "Review your results", "detail": f"Talk to your doctor about {_join(out[:3])}.", "icon": "clipboard"})
    if raised:
        items.append({"title": "Understand your risk", "detail": f"Ask your doctor what your predicted {_join(raised[:2])} risk means for you.", "icon": "heart"})
    if out or raised:
        items.append({"title": "Keep track of changes", "detail": "Repeat the relevant tests if your doctor advises.", "icon": "calendar"})
    else:
        items.append({"title": "Keep it this way", "detail": "Keep up the habits that are working for you.", "icon": "check"})
    return items[:4]


def _follow_ups(card: CategoryCard, p) -> list[str]:
    topic = category_for(card.id).topic
    out = [f for f in p.measured if f.status in {"above_range", "below_range", "critical"}]
    raised = [f for f in p.risks if f.status == "risk_raised"]
    healthy = [f for f in p.risks if f.status == "risk_healthy"]
    qs: list[str] = []
    if out:
        f = out[0]
        qs.append(f"Why is my {f.name} {'high' if f.status == 'above_range' else 'low'}?")
    if raised:
        qs.append(f"Why is my {raised[0].name} risk increased?")
    if out and healthy:
        qs.append(f"How can my {healthy[0].name} risk be healthy if my blood results are outside range?")
    qs.append(f"Which foods can help my {topic}?")
    if any(r.previous_value is not None for r in p.raw_measured):
        qs.append(f"Have my {topic} results changed over time?")
    else:
        qs.append(f"What can I do to protect my {topic}?")
    seen, final = set(), []
    for q in qs:
        if q not in seen:
            seen.add(q)
            final.append(q)
    return final[:4]


def rules_wording(cards: list[CategoryCard], parts: dict, prov: Provenance, detail: bool = False) -> Wording:
    w = Wording()
    for card in cards:
        p = parts[card.id]
        entry = {"summary": _summary(card, p)}
        if detail:
            entry.update(about=p.meta.about, interpretation=_interpretation(card, p, prov), actions=_actions(card, p), follow_ups=_follow_ups(card, p))
        w.categories[card.id] = entry
    # Membership and order are fixed by rule: the closer attention tier first, then the registry order.
    # Neither the model nor how far a value sits from its range decides which areas come first.
    attention = sorted(
        (c for c in cards if c.status in {"needs_closer_attention", "worth_attention"}),
        key=lambda c: (c.status != "needs_closer_attention", category_for(c.id).order),
    )
    if len(cards) > 1:
        w.opening = (
            "I have put your blood results and future health risks together. "
            + (f"{len(attention)} {'area deserves' if len(attention) == 1 else 'areas deserve'} a closer look, and the rest look good." if attention else "Everything we could assess looks good.")
        )
        priorities = [
            Priority(category_id=c.id, title=f"Give your {category_for(c.id).topic} some attention", detail=w.categories[c.id]["summary"], icon=c.icon, tone="attention")
            for c in attention[:3]
        ]
        good = next((c for c in cards if c.status == "looking_good" and c.measured.total and c.risks.assessed), None) or next((c for c in cards if c.status == "looking_good"), None)
        if good and len(priorities) < 4:
            priorities.append(Priority(category_id=good.id, title=f"Encouraging {category_for(good.id).topic}", detail=w.categories[good.id]["summary"], icon="check", tone="good"))
        w.priorities = priorities
    return w


# ---- one model request for every category -------------------------------------------------

def _payload(cards: list[CategoryCard], parts: dict, prov: Provenance, context: list[str]) -> dict:
    cats = []
    for c in cards:
        p = parts[c.id]
        cats.append(
            {
                "id": c.id,
                "name": c.name,
                "status": c.status_label,
                "scenario": c.scenario,
                "findings": [
                    {
                        "kind": f.source_type,
                        "name": f.name,
                        "status": f.status_label,
                        "how_far": f.how_far,
                        "value": f.value,
                        "unit": f.unit,
                        "range": [f.reference_low, f.reference_high],
                        "score": f.score,
                    }
                    for f in sorted(p.measured + p.risks, key=lambda f: (not f.important, f.name))[:14]
                ],
                "counts": {"blood_tests": c.measured.total, "risks": c.risks.assessed},
            }
        )
    return {
        "blood_report_date": prov.blood_report_date,
        "bio_ai_date": prov.bio_ai_report_date,
        "dates_differ": prov.dates_differ,
        "member_context": context[:10],
        "categories": cats,
    }


SYSTEM = """You write the wording for a member's health overview. A person with no medical background, even a 10 year old, must understand it. Short sentences. Calm, warm, direct.

You get verified findings per health category. Blood findings are measured results. Predicted risks come from a Bio-AI estimate. They are different kinds of evidence: never treat them as the same, never call a risk a diagnosis or a percent chance, and never say a normal result rules out a condition or an abnormal result confirms one.

Scenarios: both_reassuring (encouraging, never say risk free), blood_out_risk_ok (the results still deserve attention, a healthy risk does not cancel them), blood_ok_risk_up (results are encouraging, the risk deserves attention, name personal reasons only if given), both_out (explain both, never say one caused the other), blood_only, risk_only (no claims about the other source), incomplete (say what is missing). Never mention report dates or that the reports were made at different times.

Rules: the app already shows a reviewed explanation of every individual blood test, so never define or explain what a single test measures; explain how the findings fit together and what they mean for the member. Never write a number, value, score or date (the app shows them). Never invent a result, habit or condition; use member_context only if it helps. Do not recommend supplements or medicines. Use everyday names, with no jargon. The summary, interpretation and actions must each add something new: never say the same thing twice. Do not repeat the same advice in every category: make actions fit that category's actual findings and the member's context. Mention a doctor when a result is outside range or a risk is raised. Never use dashes.

Return only JSON:
{"opening": "1 or 2 sentences about the whole picture",
 "priorities": [{"category_id": "...", "title": "short", "detail": "one sentence", "tone": "attention" or "good"}],  // at most 4, attention first, one good only if true
 "categories": {"<id>": {"about": "what this part of the body does, one plain sentence", "summary": "1 to 2 sentences that say what this area means for the member, combining measured and predicted findings", "interpretation": ["2 to 3 short sentences that EXPLAIN: what the findings are measuring, why they matter, how they relate. Do not repeat the summary or list the values"], "insight": "", "actions": [{"title": "2 to 4 words", "detail": "one sentence", "icon": "clipboard|heart|calendar|check|food|walk|moon"}], // 3 or 4
 "follow_ups": ["max 4 questions the member may ask next"]}}}"""


def _numbers_ok(text: str, allowed: set[str]) -> bool:
    return all(n in allowed for n in _NUMBER.findall(text or ""))


def _clean(text) -> str:
    return _DASH.sub(", ", str(text or "")).strip()


def _fit(raw: dict, cards: list[CategoryCard], parts: dict, prov: Provenance, allowed: set[str]) -> Wording:
    base = rules_wording(cards, parts, prov, detail=True)
    w = Wording(source="model", categories={})
    ids = {c.id for c in cards}

    def ok(t) -> str:
        t = _clean(t)
        if not t or not _numbers_ok(t, allowed):
            return ""
        problems = safety_problems(t)
        if problems:
            # One failing field falls back to the rules wording for that field. Nothing unsafe is shown.
            logger.warning("explanation_safety_rejected checks=%s", ",".join(problems))
            return ""
        return t

    got = raw.get("categories") if isinstance(raw.get("categories"), dict) else {}
    for cid in ids:
        mine, fb = got.get(cid) or {}, base.categories[cid]
        entry = dict(fb)
        for key in ("about", "summary", "insight"):
            if ok(mine.get(key)):
                entry[key] = ok(mine[key])
        lines = [ok(x) for x in (mine.get("interpretation") or []) if ok(x)][:3]
        if lines:
            entry["interpretation"] = lines
        acts = []
        for a in (mine.get("actions") or [])[:4]:
            if isinstance(a, dict) and ok(a.get("title")) and ok(a.get("detail")):
                acts.append({"title": ok(a["title"]), "detail": ok(a["detail"]), "icon": str(a.get("icon") or "check")[:12]})
        if len(acts) >= 2:
            entry["actions"] = acts
        qs = [ok(q) for q in (mine.get("follow_ups") or []) if ok(q)][:4]
        if qs:
            entry["follow_ups"] = qs
        w.categories[cid] = entry
    w.opening = ok(raw.get("opening")) or base.opening
    # The rules decide which areas are priorities and in what order. The model may only reword their text.
    reworded = {i.get("category_id"): i for i in (raw.get("priorities") or []) if isinstance(i, dict)}
    pri = []
    for fixed in base.priorities:
        item = reworded.get(fixed.category_id)
        if fixed.tone == "attention" and item and ok(item.get("title")) and ok(item.get("detail")):
            pri.append(fixed.model_copy(update={"title": ok(item["title"]), "detail": ok(item["detail"])}))
        else:
            pri.append(fixed)
    w.priorities = pri
    return w


def _key(subject_id: str, prov: Provenance, context: list[str]) -> str:
    from app.providers.cache import member_token

    material = json.dumps([prov.blood_report_id, prov.blood_report_date, prov.bio_ai_report_id, prov.bio_ai_report_date, context, REGISTRY_VERSION, PROMPT_VERSION], default=str)
    return f"cura:unified:{member_token(subject_id)}:{hashlib.sha256(material.encode()).hexdigest()[:24]}"


def _store():
    from app.core.request_controls import request_controls

    return request_controls


def model_wording(subject_id: str, cards: list[CategoryCard], parts: dict, prov: Provenance, context: list[str], client=None) -> Wording:
    """Cached model wording, or the rules text when the model is unavailable. Never raises."""
    if not cards:
        return rules_wording(cards, parts, prov, detail=True)
    key = _key(subject_id, prov, context)
    try:
        cached = _store()._get(key)
    except Exception:  # noqa: BLE001 - a cache outage must not fail the screen
        cached = None
    payload = _payload(cards, parts, prov, context)
    allowed = set(_NUMBER.findall(json.dumps(payload)))
    if cached:
        try:
            return _fit(json.loads(cached), cards, parts, prov, allowed)
        except Exception:  # noqa: BLE001
            logger.warning("unified_wording cache_unreadable")
    try:
        if client is None:
            from app.llm.factory import get_llm_client

            client = get_llm_client(personal_health=True)
        text = client.complete([{"role": "system", "content": SYSTEM}, {"role": "user", "content": json.dumps(payload)}], json_mode=True)
        start, end = text.find("{"), text.rfind("}")
        raw = json.loads(text[start : end + 1])
        wording = _fit(raw, cards, parts, prov, allowed)
        try:
            _store()._set(key, json.dumps(raw), _TTL)
        except Exception:  # noqa: BLE001
            pass
        return wording
    except Exception as exc:  # noqa: BLE001 - the screen still works on the rules text
        logger.warning("unified_wording model_failed error=%s", type(exc).__name__)
        return rules_wording(cards, parts, prov, detail=True)
