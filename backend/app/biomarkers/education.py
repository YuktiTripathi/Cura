"""Plain-language explanations for each blood test, written once and reviewed, not asked of a model.

`data/biomarker_education_v1.json` has four short bullets per test: what it is, what a higher or
positive result can mean, what a lower or negative result can mean, and what to do next. The text
is general education, never a reading of the member's own result, and it never says a value is
abnormal. Whether a result is high or low always comes from the report's reference range.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.biomarkers.registry import normalize_label
from app.contracts.unified_health import EducationNote

_FILE = Path(__file__).parent / "data" / "biomarker_education_v1.json"
_LABELS = {
    "What it is": "what_it_is",
    "If high or positive": "if_high",
    "If low or negative": "if_low",
    "What to do next": "next_step",
}
# Report test ids whose lab spelling does not match the education name.
_CANONICAL_OVERRIDES = {
    "urine_rbc": "RBC (Urine)",
    "red_blood_cells": "Red Blood Cells (RBC)",
    "mpv_mean_platelet_count": "MPV (Mean Platelet Volume)",
    "platelet_count": "Platelet Count",
    "ubic": "UIBC",
    "calcium": "Calcium Total",
}


@lru_cache(maxsize=1)
def _load() -> tuple[dict[str, EducationNote], dict[str, str]]:
    from app.biomarkers.resolver import resolve_marker

    raw = json.loads(_FILE.read_text(encoding="utf-8"))["biomarkers"]
    by_name: dict[str, EducationNote] = {}
    for item in raw:
        fields = {_LABELS[b["label"]]: b["text"].strip() for b in item["bullets"] if b["label"] in _LABELS}
        by_name[normalize_label(item["biomarker"])] = EducationNote(name=item["biomarker"], common_factors=item.get("common_factors", ""), **fields)
    # A test id is only trusted when exactly one education entry resolves to it (the resolver folds
    # "Sugar", "Fasting Sugar" and "Average Blood Glucose" together, so those are matched by name).
    seen: dict[str, list[str]] = {}
    for item in raw:
        cid = resolve_marker(item["biomarker"]).canonical_id
        if cid:
            seen.setdefault(cid, []).append(normalize_label(item["biomarker"]))
    by_canonical = {cid: names[0] for cid, names in seen.items() if len(names) == 1}
    for cid, name in _CANONICAL_OVERRIDES.items():
        by_canonical[cid] = normalize_label(name)
    return by_name, by_canonical


def education_for(canonical_id: str | None, *names: str | None) -> EducationNote | None:
    by_name, by_canonical = _load()
    if canonical_id and canonical_id in by_canonical:
        return by_name.get(by_canonical[canonical_id])
    for name in names:
        hit = by_name.get(normalize_label(name or ""))
        if hit:
            return hit
    return None


def first_sentence(text: str) -> str:
    cut = text.find(". ")
    return text if cut < 0 else text[: cut + 1]
