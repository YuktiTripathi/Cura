"""Loaders for the approved knowledge the health story is built from. Nothing here calls a model."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_DIR = Path(__file__).parent / "knowledge"


def _read(name: str) -> dict:
    return json.loads((_DIR / name).read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _markers() -> dict:
    data = _read("biomarker_knowledge.json")
    return {"version": data["kb_version"], "by_id": {m["marker_id"]: m for m in data["biomarkers"]}}


@lru_cache(maxsize=1)
def _categories() -> dict:
    return _read("category_education.json")


def kb_version() -> str:
    return _markers()["version"]


def marker_knowledge(canonical_id: str | None) -> dict | None:
    return _markers()["by_id"].get(canonical_id or "")


def category_education(category_id: str) -> dict | None:
    return _categories()["categories"].get(category_id)


def markers_for_category(category_id: str) -> set[str]:
    return {k for k, v in _markers()["by_id"].items() if category_id in v.get("categories", [])}
