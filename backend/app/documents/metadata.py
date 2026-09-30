"""JSON metadata helpers for uploaded documents. Avoids extra tables."""

from __future__ import annotations

import json
from typing import Any

from app.db.models import Document


def load_meta(row: Document) -> dict[str, Any]:
    if not row.metadata_json:
        return {}
    try:
        payload = json.loads(row.metadata_json)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def save_meta(row: Document, payload: dict[str, Any]) -> None:
    row.metadata_json = json.dumps(payload)


def update_meta(row: Document, **fields: Any) -> dict[str, Any]:
    payload = load_meta(row)
    payload.update(fields)
    save_meta(row, payload)
    return payload
