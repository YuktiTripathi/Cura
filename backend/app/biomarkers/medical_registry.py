"""Medical knowledge library, revision 2.3.

Loaded once. Screens and chat read this library directly. A row is not hidden
because of an old review status. The medical text is not rewritten here.
"""

from __future__ import annotations

import json
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


def chat_passages(message: str, keys: list[str]) -> list[str]:
    """Relevant V2.3 fields only. Never the whole library."""

    text = (message or "").lower()
    detailed = any(word in text for word in ("why", "low", "high", "connected", "related", "compare"))
    lines: list[str] = []
    for key in keys:
        row = entry_for(key) or (bio_ai_content().get(key) if eligible(bio_ai_content().get(key)) else None)
        if not row:
            continue
        name = row.get("display_name") or row.get("clinical_name") or key
        body = " ".join(row.get("what_happens_inside_my_body") or [])
        why = " ".join(row.get("why_it_matters") or []) if isinstance(row.get("why_it_matters"), list) else (row.get("why_it_matters") or "")
        if detailed:
            explanations = row.get("result_explanations") or {}
            side = "low" if "low" in text else "high" if "high" in text else ""
            chosen = explanations.get(side) or [] if side else []
            piece = " ".join(
                part
                for part in (
                    body,
                    " ".join(chosen),
                    " ".join(row.get("clinical_limitations") or []),
                )
                if part
            )
        else:
            piece = " ".join(part for part in (row.get("short_description") or "", body, why) if part)
        if piece:
            lines.append(f"{name}: {piece}")
    return lines[:6]


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
