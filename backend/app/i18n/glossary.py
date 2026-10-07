"""Approved glossary of biomarkers, organs and conditions (readiness plan 3.7).

One list of local names and plain-language explanations (about grade 6 to 8), used by the
translation prompt and available to the message catalog and clients. DRAFT until reviewed.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

GLOSSARY_PATH = Path(__file__).resolve().parent / "glossary.json"


@lru_cache(maxsize=1)
def terms() -> dict[str, dict]:
    return json.loads(GLOSSARY_PATH.read_text(encoding="utf-8"))["terms"]


@lru_cache(maxsize=1)
def _matchers() -> list[tuple[re.Pattern[str], str]]:
    out = []
    for key, entry in terms().items():
        for name in [key, *entry.get("aliases", [])]:
            out.append((re.compile(rf"(?<![a-z0-9]){re.escape(name)}(?![a-z0-9])", re.I), key))
    return out


def terms_in(text: str) -> list[str]:
    found: list[str] = []
    for pattern, key in _matchers():
        if key not in found and pattern.search(text or ""):
            found.append(key)
    return found


def local_name(key: str, language: str) -> str | None:
    return terms().get(key, {}).get(language)


def glossary_lines(text: str, language: str) -> list[str]:
    """"English term -> approved local name" lines for the terms present in ``text``."""
    lines = []
    for key in terms_in(text):
        name = local_name(key, language)
        if name:
            lines.append(f"{key} -> {name}")
    return lines
