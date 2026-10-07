"""Message catalog for deterministic text (readiness plan 3.4).

Keyed templates per language in ``messages/<lang>.json``. English is the source; other
files are DRAFT translations until a native speaking clinician signs them off. A missing
key or language falls back to English. The web and Flutter apps can load the same files.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

MESSAGES_DIR = Path(__file__).resolve().parent / "messages"
_PLACEHOLDER = re.compile(r"\{(\w+)\}")


@lru_cache(maxsize=None)
def messages(language: str) -> dict[str, str]:
    path = MESSAGES_DIR / f"{language}.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def languages() -> list[str]:
    return sorted(p.stem for p in MESSAGES_DIR.glob("*.json"))


def t(key: str, language: str | None = None, **values: str) -> str:
    template = messages(language or "en").get(key) or messages("en")[key]
    return template.format(**values) if values else template


@lru_cache(maxsize=None)
def _english_index() -> dict[str, str]:
    return {text: key for key, text in messages("en").items() if not _PLACEHOLDER.search(text)}


def localize_known(text: str, language: str) -> str | None:
    """If ``text`` is exactly a catalog message, return its reviewed translation."""
    key = _english_index().get((text or "").strip())
    if key is None:
        return None
    translated = messages(language).get(key)
    return translated or None
