"""Load the biomarker relationship map once and resolve related markers.

The JSON file owns the relationships. This module only checks the file, maps a
catalogue id onto an existing CURA lab key when one already exists, and applies
the file's intent and cap rules. A marker that is not on the person's record is
never invented here.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

_PATH = Path(__file__).resolve().parent / "config" / "cura_biomarker_relationship_map.json"
_REQUIRED = ("retrieval_policy", "panels", "marker_catalog", "relationships", "aliases", "not_in_supplied_inventory")
_STOP = frozenset(
    "only when the question asks about user explicitly relevant being discussed requested "
    "context relationship broader function together and or with for from that this into "
    "possible a an is of to in on".split()
)


class RelationshipMapError(ValueError):
    """The relationship file is missing a required field or names an unknown marker."""


@lru_cache(maxsize=1)
def load_relationship_map() -> dict:
    try:
        data = json.loads(_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RelationshipMapError(f"Relationship map not found: {_PATH}") from exc
    except json.JSONDecodeError as exc:
        raise RelationshipMapError(f"Relationship map is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise RelationshipMapError("Relationship map must be a JSON object")
    missing = [key for key in _REQUIRED if key not in data]
    if missing:
        raise RelationshipMapError(f"Relationship map is missing: {', '.join(missing)}")
    policy = data["retrieval_policy"]
    for key in ("expand_for_intents", "avoid_expansion_for_intents", "max_additional_markers_default"):
        if key not in policy:
            raise RelationshipMapError(f"retrieval_policy is missing {key}")
    catalog = set(data["marker_catalog"])
    unavailable = {row["canonical_id"] for row in data["not_in_supplied_inventory"]}
    seen = set()
    for row in data["relationships"]:
        primary = row.get("primary")
        if not primary or primary in seen:
            raise RelationshipMapError(f"Duplicate or empty relationship primary: {primary}")
        seen.add(primary)
        if primary not in catalog and primary not in unavailable:
            raise RelationshipMapError(f"Relationship primary is not in the catalogue: {primary}")
        for related in row.get("related") or []:
            marker = related.get("marker")
            if marker not in catalog and marker not in unavailable:
                raise RelationshipMapError(f"Related marker {marker} from {primary} is not in the catalogue")
            if not related.get("when"):
                raise RelationshipMapError(f"Related marker {marker} has no intents")
    return data


def _cura_key(json_id: str) -> str | None:
    """Existing CURA lab key for a catalogue id. None when CURA has no such marker."""
    from app.pipeline.lab_parameters import _BY_KEY, match_lab_keys

    if json_id in _BY_KEY:
        return json_id
    text = json_id.replace("_", " ")
    keys = match_lab_keys(text)
    if len(keys) == 1:
        return keys[0]
    data = load_relationship_map()
    alias = data["aliases"].get(json_id)
    if alias and alias != json_id:
        return _cura_key(alias)
    return None


def unresolved_catalogue_ids() -> list[str]:
    """Catalogue ids that do not match a CURA lab key. They are never retrieved."""
    data = load_relationship_map()
    ids = set(data["marker_catalog"])
    for row in data["relationships"]:
        ids.add(row["primary"])
        ids.update(item["marker"] for item in row["related"])
    return sorted(item for item in ids if _cura_key(item) is None)


def unavailable_in_catalogue() -> set[str]:
    data = load_relationship_map()
    ids = {row["canonical_id"] for row in data["not_in_supplied_inventory"]}
    ids.update(row["primary"] for row in data["relationships"] if row.get("available_in_supplied_inventory") is False)
    return ids


def question_relation(message: str) -> str | None:
    """Map a question onto one intent name from the relationship file. None skips expansion."""
    text = (message or "").lower()
    policy = load_relationship_map()["retrieval_policy"]
    if re.search(r"\bwhat is\b", text) and not re.search(r"\b(my|mine)\b", text):
        return None if "definition" in policy["avoid_expansion_for_intents"] else "definition"
    if re.search(r"\b(why|cause|causes|reason)\b", text):
        return "possible_causes"
    if re.search(r"\b(related|relationship|connection|linked)\b", text):
        return "relationship"
    if re.search(r"\b(changed|change|trend|compare|since|previous|history|last time)\b", text):
        return "comparison"
    if re.search(r"\b(food|diet|eat|lifestyle|lower|improve|help)\b", text):
        return "recommendation"
    if re.search(r"\b(my|mine)\b", text):
        return "interpretation"
    return None


def _condition_met(condition: str | None, message: str) -> bool:
    if not condition:
        return True
    words = [word for word in re.findall(r"[a-z]{5,}", condition.lower()) if word not in _STOP]
    text = (message or "").lower()
    return any(word in text for word in words)


def related_keys(primary_keys: list[str], message: str, *, intent: str | None = None, ignore_conditions: bool = False) -> list[str]:
    """One hop of related CURA keys. The directly asked keys are not repeated."""
    intent = intent or question_relation(message)
    data = load_relationship_map()
    policy = data["retrieval_policy"]
    if intent is None or intent not in policy["expand_for_intents"]:
        return []
    by_cura: dict[str, dict] = {}
    for row in data["relationships"]:
        cura = _cura_key(row["primary"])
        if cura:
            by_cura[cura] = row
    asked = [key for key in primary_keys if key]
    cap = int(policy["max_additional_markers_default"])
    if intent == "relationship":
        cap = int(policy.get("max_additional_markers_for_cross_system_question") or cap)
    extra: list[str] = []
    seen = set(asked)
    for key in asked:
        row = by_cura.get(key)
        if not row:
            continue
        for related in row.get("related") or []:
            if intent not in (related.get("when") or []):
                continue
            if not ignore_conditions and not _condition_met(related.get("condition"), message):
                continue
            cura = _cura_key(related["marker"])
            if not cura or cura in seen:
                continue
            seen.add(cura)
            extra.append(cura)
            if len(extra) >= cap:
                return extra
    return extra


def panel_keys_for_text(message: str) -> list[str]:
    """CURA keys in a catalogue panel whose label is named in the question."""
    text = (message or "").lower()
    found: list[str] = []
    for panel in load_relationship_map()["panels"]:
        label = (panel.get("label") or "").lower()
        if not label or label.split()[0] not in text and panel.get("id", "").split("_")[0] not in text:
            continue
        for marker in panel.get("markers") or []:
            cura = _cura_key(marker)
            if cura and cura not in found:
                found.append(cura)
    return found


def panel_label(cura_key: str) -> str | None:
    """First catalogue panel that contains this CURA key. None when it is not grouped."""
    data = load_relationship_map()
    for panel in data["panels"]:
        for marker in panel.get("markers") or []:
            if _cura_key(marker) == cura_key:
                return panel.get("label")
    return None


def group_measurements(measurements: list[dict]) -> list[dict]:
    """Group already selected rows. A marker is listed once, under its first panel."""
    groups: dict[str, list] = {}
    order: list[str] = []
    for row in measurements:
        label = panel_label(str(row.get("key") or "")) or "Other results"
        if label not in groups:
            groups[label] = []
            order.append(label)
        groups[label].append(row)
    if len(measurements) < 2:
        return []
    return [{"label": label, "measurements": groups[label]} for label in order]
