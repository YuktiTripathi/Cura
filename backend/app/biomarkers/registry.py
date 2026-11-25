"""Versioned canonical biomarker registry.

Source of truth: data/biomarker_registry_v1.csv (one row per source group and test) plus
data/registry_overlay_v1.json (aliases, key bridge, review notes, allergy groups). Both files are
data: editing them changes the mapping without touching code. Original laboratory names and source
groups are kept on every entry and never rewritten.
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from app.biomarkers.systems import system_id_for_name

DATA_DIR = Path(__file__).parent / "data"
REGISTRY_CSV = DATA_DIR / "biomarker_registry_v1.csv"
OVERLAY_JSON = DATA_DIR / "registry_overlay_v1.json"


class RegistryError(ValueError):
    """The registry data contradicts itself. Raised at load so a bad edit fails fast."""


@dataclass(frozen=True)
class SourceEntry:
    group: str
    test_name: str
    sex_scope: str  # "shared", "male_panel" or "female_panel": package configuration only


@dataclass
class RegistryEntry:
    canonical_id: str
    primary_system: str
    secondary_systems: tuple[str, ...]
    sources: list[SourceEntry] = field(default_factory=list)
    derived: bool = False
    review_note: str | None = None

    @property
    def sex_scopes(self) -> set[str]:
        return {source.sex_scope for source in self.sources}


@dataclass(frozen=True)
class AllergyGroup:
    subsection: str
    group: str
    listed_count: int


@dataclass(frozen=True)
class Registry:
    version: str
    status: str
    entries: dict[str, RegistryEntry]
    by_label: dict[str, tuple[tuple[str, str], ...]]  # normalized test name -> ((canonical_id, normalized group), ...)
    by_alias: dict[str, str]
    key_bridge: dict[str, str]
    bridge_notes: dict[str, str]
    ambiguous_bare: frozenset[str]
    allergy_groups: tuple[AllergyGroup, ...]
    group_tests: dict[str, frozenset[str]]  # normalized source group -> canonical ids listed in it
    group_names: dict[str, str]  # normalized source group -> source group as supplied
    spelling: dict[str, str]


def normalize_label(text: str, spelling: dict[str, str] | None = None) -> str:
    lowered = (text or "").lower().replace("&", " and ")
    for wrong, right in (spelling or {}).items():
        lowered = lowered.replace(wrong, right)
    lowered = re.sub(r"[^a-z0-9]+", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def _sex_scope(group: str) -> str:
    if re.search(r"\bfemale\b", group, re.I):
        return "female_panel"
    if re.search(r"\bmale\b", group, re.I):
        return "male_panel"
    return "shared"


def _split_secondary(raw: str) -> tuple[str, ...]:
    out: list[str] = []
    for part in re.split(r"[;,]", raw or ""):
        part = part.strip()
        if not part or part in {"—", "-", "–"}:
            continue
        system_id = system_id_for_name(part)
        if system_id is None:
            raise RegistryError(f"Unknown secondary body system: {part!r}")
        out.append(system_id)
    return tuple(dict.fromkeys(out))


@lru_cache(maxsize=1)
def load_registry() -> Registry:
    overlay = json.loads(OVERLAY_JSON.read_text(encoding="utf-8"))
    spelling = overlay.get("spelling", {})
    derived = set(overlay.get("derived", []))
    notes = overlay.get("review_notes", {})

    entries: dict[str, RegistryEntry] = {}
    by_label: dict[str, list[tuple[str, str]]] = {}
    group_tests: dict[str, set[str]] = {}
    group_names: dict[str, str] = {}
    with REGISTRY_CSV.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            group = row["source_group"].strip()
            name = row["source_test_name"].strip()
            canonical = row["proposed_canonical_id"].strip()
            primary = system_id_for_name(row["primary_body_system"])
            if not (group and name and canonical):
                raise RegistryError(f"Incomplete registry row: {row!r}")
            if primary is None:
                raise RegistryError(f"Unknown primary body system: {row['primary_body_system']!r}")
            secondary = _split_secondary(row.get("secondary_body_systems", ""))
            entry = entries.get(canonical)
            if entry is None:
                entry = RegistryEntry(
                    canonical_id=canonical,
                    primary_system=primary,
                    secondary_systems=secondary,
                    derived=canonical in derived,
                    review_note=notes.get(canonical),
                )
                entries[canonical] = entry
            elif entry.primary_system != primary or entry.secondary_systems != secondary:
                raise RegistryError(f"{canonical} is assigned to more than one body system")
            entry.sources.append(SourceEntry(group=group, test_name=name, sex_scope=_sex_scope(group)))
            normalized_group = normalize_label(group, spelling)
            by_label.setdefault(normalize_label(name, spelling), []).append((canonical, normalized_group))
            group_tests.setdefault(normalized_group, set()).add(canonical)
            group_names.setdefault(normalized_group, group)

    key_bridge = dict(overlay.get("key_bridge", {}))
    for key, canonical in key_bridge.items():
        if canonical not in entries:
            raise RegistryError(f"key_bridge {key!r} points to unknown canonical id {canonical!r}")
    by_alias: dict[str, str] = {}
    for canonical, aliases in overlay.get("aliases", {}).items():
        if canonical not in entries:
            raise RegistryError(f"alias list for unknown canonical id {canonical!r}")
        for alias in aliases:
            by_alias[normalize_label(alias, spelling)] = canonical
    for canonical in notes:
        if canonical not in entries:
            raise RegistryError(f"review note for unknown canonical id {canonical!r}")

    extension_path = DATA_DIR / "identity_extension_v2.json"
    if extension_path.exists():
        extension = json.loads(extension_path.read_text(encoding="utf-8"))
        known_systems = {system.id for system in __import__("app.biomarkers.systems", fromlist=["SYSTEMS"]).SYSTEMS}
        for item in extension.get("entries") or []:
            canonical = item["canonical_id"]
            if canonical in entries or canonical.startswith("WB-"):
                continue
            primary = item.get("health_category") or "other_unmapped"
            if primary not in known_systems:
                primary = "other_unmapped"
            entries[canonical] = RegistryEntry(canonical_id=canonical, primary_system=primary, secondary_systems=())
            label = normalize_label(item.get("original_name") or "", spelling)
            if label:
                by_label.setdefault(label, []).append((canonical, ""))

    return Registry(
        version=str(overlay["registry_version"]),
        status=str(overlay.get("status", "")),
        entries=entries,
        by_label={label: tuple(dict.fromkeys(items)) for label, items in by_label.items()},
        by_alias=by_alias,
        key_bridge=key_bridge,
        bridge_notes=dict(overlay.get("bridge_notes", {})),
        ambiguous_bare=frozenset(normalize_label(x, spelling) for x in overlay.get("ambiguous_bare_labels", [])),
        allergy_groups=tuple(AllergyGroup(**item) for item in overlay.get("allergy_groups", [])),
        group_tests={group: frozenset(ids) for group, ids in group_tests.items()},
        group_names=group_names,
        spelling=spelling,
    )
