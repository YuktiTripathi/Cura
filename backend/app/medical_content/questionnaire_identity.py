"""Match a stored SuperShyft questionnaire answer to a library question, only when it can be verified.

The library registry carries staging question ids and no production keys. A staging id alone is never
trusted. A library question is matched to a stored question only when the question wording is identical
after normalising case, spacing and punctuation. Anything else stays unmatched, which means "unknown",
never "no" and never "not applicable".
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

_PATH = Path(__file__).parent / "library" / "lifestyle" / "questionnaire_registry.json"


def _norm(text: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def _rows() -> list[dict]:
    return json.loads(_PATH.read_text(encoding="utf-8"))["questions"]


@lru_cache(maxsize=1)
def _by_text() -> dict[str, dict]:
    rows = _rows()
    index: dict[str, dict] = {}
    clashes: set[str] = set()
    for row in rows:
        key = _norm(row.get("question"))
        if not key:
            continue
        if key in index:
            clashes.add(key)
        index[key] = row
    for key in clashes:
        index.pop(key, None)  # two library questions with one wording cannot be told apart
    return index


def verified_library_question(stored_question_text: str | None) -> dict | None:
    """The library row for a stored question, or None when the wording does not match exactly."""
    return _by_text().get(_norm(stored_question_text))


def coverage() -> dict:
    rows = _rows()
    return {
        "library_questions": len(rows),
        "with_production_key": sum(1 for r in rows if r.get("question_key")),
        "unique_wordings": len(_by_text()),
    }
