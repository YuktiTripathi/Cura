"""Medical knowledge library, revision 2.3.

Loaded once. Screens and chat read this library directly. A row is not hidden
because of an old review status. The medical text is not rewritten here.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

LIBRARY = Path(__file__).resolve().parents[1] / "medical_content" / "library"
CONTENT_VERSION = "2.3"
REJECTED = "rejected"


def _load(relative: str):
    return json.loads((LIBRARY / relative).read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def inventory() -> tuple[dict, ...]:
    return tuple(_load("inventory/master_biomarker_inventory.json"))


@lru_cache(maxsize=1)
def _identity_by_content_key() -> dict[str, str]:
    path = Path(__file__).resolve().parents[1] / "biomarkers" / "data" / "identity_extension_v2.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {item["content_key"]: item["canonical_id"] for item in data.get("entries") or []}


@lru_cache(maxsize=1)
def biomarker_content() -> dict[str, dict]:
    from app.biomarkers.resolver import resolve_marker

    identities = _identity_by_content_key()
    rows = _load("content/biomarker_content.json")
    index: dict[str, dict] = {}
    for row in rows:
        marker_id = (row.get("biomarker_id") or "").strip() or identities.get(row.get("content_key") or "", "")
        if not marker_id:
            hit = resolve_marker(row.get("clinical_name") or "", None)
            if hit.canonical_id and hit.method in {"source_label", "source_group_label", "alias", "slug", "cura_key"}:
                marker_id = hit.canonical_id
        if marker_id:
            row = {**row, "biomarker_id": marker_id}
            index.setdefault(marker_id, row)
    return index


@lru_cache(maxsize=1)
def allergy_content() -> dict[str, dict]:
    identities = _identity_by_content_key()
    rows = _load("content/allergy_content.json")
    index = {}
    for row in rows:
        key = (row.get("biomarker_id") or "").strip() or identities.get(row.get("content_key") or "", "") or row.get("content_key")
        if key and not str(key).startswith("WB-"):
            index[key] = {**row, "biomarker_id": key if not str(key).startswith("WB-") else row.get("biomarker_id")}
        elif row.get("content_key"):
            index[row["content_key"]] = row
    return index


@lru_cache(maxsize=1)
def bio_ai_content() -> dict[str, dict]:
    rows = _load("content/bio_ai_content.json")
    return {row["risk_id"]: row for row in rows if row.get("risk_id")}


@lru_cache(maxsize=1)
def relationships() -> tuple[dict, ...]:
    return tuple(_load("relationships/biomarker_relationships.json"))


def library_revision() -> str:
    """Stable fingerprint of the library files. Not a clinical approval."""

    import hashlib

    root = LIBRARY
    digest = hashlib.sha256()
    if root.is_dir():
        for path in sorted(root.rglob("*.json")):
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()[:16]


def eligible(row: dict | None) -> bool:
    """A library row is usable when it exists. Review status does not hide it."""

    if not row:
        return False
    return row.get("review_status") != REJECTED


def eligible_for_chat(row: dict | None) -> bool:
    """Chat may use any library row that is not rejected. The same rule applies in every environment;
    clinical approval is not a prerequisite. Personal statements still come only from member data."""
    return eligible(row)


def eligible_for_personal_interpretation(row: dict | None) -> bool:
    """Kept for callers that name the old rule. Same as eligible_for_chat."""
    return eligible_for_chat(row)


@lru_cache(maxsize=1)
def _verified_claims() -> frozenset[tuple[str, str, str]]:
    """(entry id, field, claim) for claims a source page was read for. High-stakes fields are gated on this."""
    try:
        data = json.loads((LIBRARY / "evidence" / "claim_evidence_map.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return frozenset()
    return frozenset((c["id"], c["field"], c["claim"]) for c in data.get("claims") or [] if c.get("status") == "page_read_supports_claim")


def claim_verified(entry_id: str | None, field: str, claim: str) -> bool:
    return (entry_id or "", field, claim) in _verified_claims()


def category_about(category_id: str | None) -> str:
    rows = {row.get("health_category"): row for row in _load("content/health_category_content.json")}
    row = rows.get(category_id or "")
    if not eligible(row):
        return ""
    body = row.get("what_happens_inside_my_body") or []
    return " ".join(str(part) for part in body if part) or row.get("short_description") or ""


def category_intro(category_id: str | None) -> str:
    """The one-line V2.3 short description, for overview cards. Full text stays on the detail screen."""
    rows = {row.get("health_category"): row for row in _load("content/health_category_content.json")}
    row = rows.get(category_id or "")
    return (row.get("short_description") or "").strip() if eligible(row) else ""


def _intent_of(text: str) -> str:
    if re.search(r"\b(eat|diet|food|foods|nutrition|meal|meals)\b", text):
        return "nutrition"
    if re.search(r"\b(why|cause|causes|reason|reasons|explain why|what could|how come)\b", text):
        return "possible_causes"
    if re.search(r"\b(relate|related|relationship|connected|connection|link|linked|together|compare|affect|affects)\b", text):
        return "relationship"
    if re.search(r"\b(what does|mean|means|results?|meaning|explain|my report|my score|my level)\b", text):
        return "interpretation"
    return "definition"


def _clean_lines(value) -> list[str]:
    if isinstance(value, str):
        value = [value]
    return [str(v).strip() for v in value or [] if str(v).strip()]


def canonical_key(key: str | None) -> str | None:
    """The library id for a CURA key ("hdl" becomes "hdl_cholesterol_direct"), or the key itself."""
    if not key:
        return key
    if key in biomarker_content() or key in bio_ai_content():
        return key
    try:
        from app.biomarkers.resolver import resolve_marker

        hit = resolve_marker(key)
        return hit.canonical_id if hit.canonical_id and hit.canonical_id in biomarker_content() else key
    except Exception:  # noqa: BLE001 - a missing identity leaves the key as it was
        return key


def _factor_lines(row: dict, limit: int = 4) -> list[str]:
    """Factors with how each one acts, when the library explains them; names alone otherwise."""
    explained = [f"{x.get('factor')}: {x.get('how_it_acts')}" for x in row.get("factor_explanations") or [] if x.get("factor") and x.get("how_it_acts")]
    return explained[:limit] or _clean_lines(row.get("possible_influencing_factors") or row.get("influencing_factors"))


# Token budget for curated knowledge, by question type. A definition needs little; a personal explanation
# that spans several results gets more. Estimates use about four characters per token.
BASE_BUDGET = {"definition": 220, "body": 380, "interpretation": 520, "possible_causes": 520, "relationship": 520,
               "nutrition": 620, "improvement": 560}
PER_EXTRA_RESULT = 200
MAX_BUDGET = 1600
_HOW_BODY = re.compile(r"\b(how does|how do|what does .* do|work|works|role|function|in my body|in the body)\b")
_IMPROVE = re.compile(r"\b(improve|lower|raise|reduce|increase|bring (it )?down|keep|maintain|prevent|protect|what can i do|healthy|risk)\b")
_BROAD = re.compile(r"\b(my results|my report|overall|everything|whole report|all my|summary|summar)\b")


def _tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _mentioned(row: dict, key: str, text: str) -> bool:
    names = [row.get("display_name"), row.get("clinical_name"), key.replace("_", " ")] + list(row.get("aliases") or [])
    for name in names:
        if not name:
            continue
        base = str(name).lower().split(" (")[0].strip()
        short = re.search(r"\(([^)]+)\)", str(name))
        for token in filter(None, [base, short.group(1).lower() if short else None]):
            if len(token) >= 3 and re.search(rf"\b{re.escape(token)}\b", text):
                return True
    return False


def question_mode(text: str) -> str:
    mode = _intent_of(text)
    if mode in {"definition", "interpretation"} and _IMPROVE.search(text):
        return "improvement"
    if mode == "definition" and _HOW_BODY.search(text):
        return "body"
    return mode


def passage_budget(mode: str, extra_results: int, broad: bool) -> int:
    budget = BASE_BUDGET.get(mode, 400) + PER_EXTRA_RESULT * max(0, extra_results)
    if broad:
        budget += 300
    return min(budget, MAX_BUDGET)


def chat_passages(message: str, keys: list[str], sides: dict[str, str] | None = None) -> list[str]:
    """Relevant V2.3 knowledge for this question, ranked and cut to a budget that fits its complexity.

    Never the whole library and never every field of an entry: each question type pulls the fields that
    help answer it, results the person asked about or that are outside their range come first, and
    threshold notes are used only where a source page supports them."""

    text = (message or "").lower()
    mode = question_mode(text)
    broad = bool(_BROAD.search(text))
    side = "low" if re.search(r"\blow(er)?\b|\bbelow\b|\bdeficien", text) else "high" if re.search(r"\bhigh(er)?\b|\babove\b|\braised\b|\belevated\b", text) else ""
    sides = sides or {}
    candidates: list[tuple[float, int, str]] = []  # (priority, order, line)
    seen: set[str] = set()

    def add(priority: float, label: str, parts: list[str]) -> None:
        fresh = []
        for part in parts:
            k = " ".join(part.lower().split()).rstrip(".")
            if k and k not in seen:
                seen.add(k)
                fresh.append(part.rstrip("."))
        if fresh:
            candidates.append((priority, len(candidates), f"{label}: " + ". ".join(fresh) + "."))

    keys = [canonical_key(k) for k in keys if k]
    used_keys: list[str] = []
    for position, key in enumerate(keys):
        risk = bio_ai_content().get(key)
        row = entry_for(key) or (risk if eligible(risk) else None)
        if not eligible_for_chat(row):
            continue
        primary = position == 0
        actual = sides.get(key)
        relevant = primary or _mentioned(row, key, text) or (actual in {"high", "low"} and (broad or mode in {"nutrition", "improvement"}))
        if not relevant:
            continue  # related results still contribute through the relationship lines
        used_keys.append(key)
        weight = 1.0 if (primary or broad) else 0.7
        name = row.get("display_name") or row.get("clinical_name") or key
        explanations = row.get("result_explanations") or {}
        limits = _clean_lines(row.get("clinical_limitations"))
        state = (side if primary else "") or actual or ""
        is_risk = risk is not None and row is risk

        if primary and side and actual and actual != side and mode in {"possible_causes", "interpretation", "nutrition", "improvement"}:
            note = (f"The latest result is inside the range on the report, so an explanation for a {side} result does not describe it"
                    if actual == "normal" else f"The latest result is {actual} on the report, not {side}")
            add(100, f"{name}, premise check", [note])
            state = actual

        if mode in {"definition", "body"}:
            body = _clean_lines(row.get("what_happens_inside_my_body"))
            add(95 * weight, name, _clean_lines(row.get("short_description")) + body[: (4 if mode == "body" else 2)])
            if mode == "body":
                add(60 * weight, f"{name}, why it matters", _clean_lines(row.get("why_this_test_matters") or row.get("why_it_matters"))[:1])
        else:
            add(70 * weight, name, _clean_lines(row.get("short_description")))

        if is_risk and mode != "definition":
            add(88 * weight, f"{name}, what a Bio-AI band means", _clean_lines(row.get("risk_meaning"))[:3])
            if key == "metabolic_age":
                add(80, "MetSights inputs, not a formula", _clean_lines(row.get("product_inputs")))
        if state and mode != "definition":
            label = "an in-range" if state == "normal" else f"a {state}"
            add(92 * weight, f"{name}, what {label} result may reflect", _clean_lines(explanations.get(state)))

        if mode in {"possible_causes", "nutrition"}:
            add(85 * weight, f"{name}, how influencing factors act", _factor_lines(row))
        elif mode in {"interpretation", "improvement"}:
            add(55 * weight, f"{name}, how influencing factors act", _factor_lines(row, 3))

        if mode in {"nutrition", "improvement"} or (mode == "interpretation" and state):
            boost = 1.0 if mode in {"nutrition", "improvement"} else 0.75
            if state == "normal" or not state:
                add(80 * weight * boost, f"{name}, keeping it healthy", _clean_lines(row.get("keeping_healthy"))[:2])
            else:
                add(80 * weight * boost, f"{name}, everyday steps that may help", _clean_lines(row.get("everyday_support"))[:3])
            add(62 * weight * boost, f"{name}, lowering modifiable risk", _clean_lines(row.get("lowering_risk"))[:2])

        if mode in {"interpretation", "possible_causes", "improvement"}:
            note = row.get("reference_range_note")
            if note and claim_verified(key if is_risk else row.get("content_key"), "reference_range_note", note):
                add(78 * weight, f"{name}, lab range and clinical thresholds", [note])
            add(50 * weight, f"{name}, a common misunderstanding", _clean_lines(row.get("common_misconceptions"))[:1])
            add(58 * weight, f"{name}, limits", limits[:1])
            if state in {"high", "low"}:
                add(48 * weight, f"{name}, when to see a doctor", _clean_lines(row.get("when_to_seek_medical_advice"))[:1])

    if used_keys and (mode in {"possible_causes", "relationship", "interpretation"} or len(used_keys) > 1):
        used = set(used_keys)
        added = 0
        for rel in sorted(relationships(), key=lambda r: 0 if r.get("priority") == "primary" else 1):
            if added >= (5 if mode == "relationship" else 3):
                break
            if not eligible_for_chat(rel) or (mode not in (rel.get("retrieve_when") or []) and len(used_keys) < 2):
                continue
            left, right = _endpoint(rel, "source"), _endpoint(rel, "related")
            both = left in used and right in used
            other = right if left == used_keys[0] else left if right == used_keys[0] else (right if both else None)
            if other and rel.get("user_explanation"):
                priority = 90 if (mode == "relationship" or both) else 65
                add(priority, f"Relationship with {other.replace('_', ' ')}", [rel["user_explanation"]] + _clean_lines(rel.get("reading_together")) + _clean_lines(rel.get("clinical_limitations"))[:1])
                added += 1

    budget = passage_budget(mode, len(used_keys) - 1, broad)
    chosen, spent = [], 0
    for priority, order, line in sorted(candidates, key=lambda c: (-c[0], c[1])):
        cost = _tokens(line)
        if spent + cost > budget and chosen:
            continue
        chosen.append((order, line))
        spent += cost
    # Keep the reading order the passages were built in, so each result's lines stay together.
    return [line for _, line in sorted(chosen)]


def entry_for(biomarker_id: str | None) -> dict | None:
    row = biomarker_content().get(biomarker_id or "")
    if eligible(row):
        return row
    return None


def invalidate() -> None:
    inventory.cache_clear()
    biomarker_content.cache_clear()
    allergy_content.cache_clear()
    bio_ai_content.cache_clear()
    relationships.cache_clear()
    _verified_claims.cache_clear()


def _endpoint(row: dict, side: str) -> str | None:
    marker = row.get(f"{side}_biomarker_id")
    if marker:
        return marker
    key = row.get(f"{side}_content_key")
    if not key:
        return None
    for entry in biomarker_content().values():
        if entry.get("content_key") == key and entry.get("biomarker_id"):
            return entry["biomarker_id"]
    return None


def related_ids(biomarker_id: str, present: set[str] | None = None) -> list[str]:
    """One hop. When present is set, only biomarkers on this person's report."""

    biomarker_id = canonical_key(biomarker_id) or biomarker_id
    found: list[str] = []
    for row in relationships():
        if not eligible(row):
            continue
        left = _endpoint(row, "source")
        right = _endpoint(row, "related")
        other = right if left == biomarker_id else left if right == biomarker_id else None
        if not other or other in found:
            continue
        if present is not None and other not in present:
            continue
        found.append(other)
    return found


def lifestyle_personalisation_enabled() -> bool:
    """Staging question ids are not production keys. Keep this off."""

    return False
