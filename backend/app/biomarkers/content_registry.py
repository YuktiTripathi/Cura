"""Reviewed medical content, version 2.1.

Screens read these files. They do not ask a model to rewrite them.
A missing entry stays empty. The older education file is only a fallback
when this registry has no matching biomarker.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.biomarkers.registry import normalize_label
from app.contracts.unified_health import EducationNote

CONTENT_VERSION = "2.1"
_ROOT = Path(__file__).parent / "content" / "v2" / "content"


def _join(lines: list | None) -> str:
    return " ".join(str(line).strip() for line in lines or [] if str(line).strip())


@lru_cache(maxsize=1)
def _biomarkers() -> dict[str, dict]:
    rows = json.loads((_ROOT / "biomarker_content.json").read_text(encoding="utf-8"))
    index: dict[str, dict] = {}
    for row in rows:
        if row.get("biomarker_id"):
            index[row["biomarker_id"]] = row
        for label in (row.get("clinical_name"), row.get("display_name"), *(row.get("original_test_names") or [])):
            key = normalize_label(label or "")
            if key and key not in index:
                index[key] = row
    return index


@lru_cache(maxsize=1)
def _risks() -> dict[str, dict]:
    rows = json.loads((_ROOT / "bio_ai_content.json").read_text(encoding="utf-8"))
    return {row["risk_id"]: row for row in rows if row.get("risk_id")}


def _note(row: dict, canonical_id: str | None) -> EducationNote:
    explanations = row.get("result_explanations") or {}
    body = _join(row.get("what_happens_inside_my_body"))
    return EducationNote(
        name=row.get("display_name") or row.get("clinical_name") or canonical_id or "",
        what_it_is=body or row.get("short_description") or "",
        body=body,
        why_it_matters=_join(row.get("why_this_test_matters") or row.get("why_it_matters")),
        if_high=_join(explanations.get("high") or explanations.get("above_range")),
        if_low=_join(explanations.get("low") or explanations.get("below_range")),
        next_step=_join(explanations.get("normal") or explanations.get("within_range")),
        common_factors=_join(row.get("possible_influencing_factors")),
        limitations=_join(row.get("clinical_limitations")),
        content_version=str(row.get("content_version") or ""),
        review_status=str(row.get("review_status") or ""),
        content_source="medical_knowledge_v2.3",
    )


def note_for(canonical_id: str | None, *names: str | None) -> EducationNote | None:
    from app.biomarkers.medical_registry import allergy_content, entry_for

    library = entry_for(canonical_id)
    if library is None:
        for name in (canonical_id, *names):
            library = entry_for(name)
            if library:
                break
    if library is None and canonical_id:
        row = allergy_content().get(canonical_id)
        from app.biomarkers.medical_registry import eligible

        library = row if eligible(row) else None
    if not library:
        return None
    return _note(library, canonical_id)


def risk_explanation(code: str | None) -> str:
    from app.biomarkers.medical_registry import bio_ai_content, eligible

    row = bio_ai_content().get(code or "")
    if not eligible(row):
        return ""
    return _join(row.get("what_happens_inside_my_body")) or row.get("short_description") or ""
