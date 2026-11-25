"""Load the versioned medical library once. Draft text is not treated as approved."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

LIBRARY = Path(__file__).parent / "library"
CONTENT_VERSION = "2.3"


def _load(path: Path):
    return json.loads(path.read_text())


@lru_cache(maxsize=1)
def load_registry() -> dict:
    biomarkers = _load(LIBRARY / "content" / "biomarker_content.json")
    by_id = {}
    by_key = {}
    for entry in biomarkers:
        marker_id = (entry.get("biomarker_id") or "").strip()
        content_key = (entry.get("content_key") or "").strip()
        if marker_id:
            by_id.setdefault(marker_id, entry)
        if content_key:
            by_key[content_key] = entry
    relationships = _load(LIBRARY / "relationships" / "biomarker_relationships.json")
    return {
        "version": CONTENT_VERSION,
        "biomarkers": biomarkers,
        "by_id": by_id,
        "by_key": by_key,
        "allergens": _load(LIBRARY / "content" / "allergy_content.json"),
        "shared": _load(LIBRARY / "content" / "shared_education_modules.json"),
        "bio_ai": _load(LIBRARY / "content" / "bio_ai_content.json"),
        "categories": _load(LIBRARY / "content" / "health_category_content.json"),
        "relationships": relationships,
        "questionnaire": _load(LIBRARY / "lifestyle" / "questionnaire_registry.json"),
        "lifestyle_relationships": _load(LIBRARY / "relationships" / "lifestyle_relationships.json"),
        "unresolved": _load(LIBRARY / "inventory" / "unresolved_mappings.json"),
    }


def invalidate() -> None:
    load_registry.cache_clear()
