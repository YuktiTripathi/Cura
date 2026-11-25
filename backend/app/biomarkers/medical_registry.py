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
    if re.search(r"\b(what does|mean|means|result|meaning)\b", text):
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


def chat_passages(message: str, keys: list[str], sides: dict[str, str] | None = None) -> list[str]:
    """Relevant V2.3 fields for this question only. Never the whole library, never a biology lesson
    when the person asked why a result is low."""

    text = (message or "").lower()
    mode = _intent_of(text)
    side = "low" if re.search(r"\blow(er)?\b|\bbelow\b|\bdeficien", text) else "high" if re.search(r"\bhigh(er)?\b|\babove\b|\braised\b|\belevated\b", text) else ""
    lines: list[str] = []
    seen: set[str] = set()

    def add(label: str, parts: list[str]) -> None:
        fresh = []
        for part in parts:
            key = " ".join(part.lower().split()).rstrip(".")
            if key and key not in seen:
                seen.add(key)
                fresh.append(part.rstrip("."))
        if fresh:
            lines.append(f"{label}: " + ". ".join(fresh) + ".")

    keys = [canonical_key(k) for k in keys if k]
    for position, key in enumerate(keys):
        risk = bio_ai_content().get(key)
        row = entry_for(key) or (risk if eligible(risk) else None)
        if not row:
            continue
        if position > 0 and mode not in {"definition", "nutrition"}:
            continue  # related results contribute through the relationship lines only
        name = row.get("display_name") or row.get("clinical_name") or key
        explanations = row.get("result_explanations") or {}
        limits = _clean_lines(row.get("clinical_limitations"))
        limits = [line for line in limits if "not confirmed" not in line.lower()]
        if mode == "nutrition":
            # Food advice reads what a result outside its range may reflect and what influences it, per result.
            own = (sides or {}).get(key) or (sides or {}).get(keys[position] if position < len(keys) else "") or side
            if own:
                add(f"{name}, what a {own} result may reflect", _clean_lines(explanations.get(own)))
            else:
                add(name, _clean_lines(row.get("short_description")) + _clean_lines(row.get("what_happens_inside_my_body"))[:2])
            add(f"{name}, possible influencing factors", _clean_lines(row.get("possible_influencing_factors")))
        elif mode == "possible_causes":
            if side:
                add(f"{name}, what a {side} result may reflect", _clean_lines(explanations.get(side)))
            add(f"{name}, possible influencing factors", _clean_lines(row.get("possible_influencing_factors")))
            add(f"{name}, limits", limits)
        elif mode == "relationship":
            add(f"{name}, summary", _clean_lines(row.get("short_description")))
            add(f"{name}, limits", limits)
        elif mode == "interpretation":
            add(f"{name}", _clean_lines(row.get("short_description")))
            if side:
                add(f"{name}, what a {side} result may reflect", _clean_lines(explanations.get(side)))
            add(f"{name}, limits", limits)
        else:
            add(name, _clean_lines(row.get("short_description")) + _clean_lines(row.get("what_happens_inside_my_body"))[:2])
    if mode in {"possible_causes", "relationship", "interpretation"}:
        wanted = set(keys[:1])
        added = 0
        for rel in sorted(relationships(), key=lambda r: 0 if r.get("priority") == "primary" else 1):
            if added >= 3:
                break
            if not eligible(rel) or mode not in (rel.get("retrieve_when") or []):
                continue
            left, right = _endpoint(rel, "source"), _endpoint(rel, "related")
            other = right if left in wanted else left if right in wanted else None
            if other and rel.get("user_explanation"):
                add(f"Relationship with {other.replace('_', ' ')}", [rel["user_explanation"]] + _clean_lines(rel.get("clinical_limitations"))[:1])
                added += 1
    return lines[:8]


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
