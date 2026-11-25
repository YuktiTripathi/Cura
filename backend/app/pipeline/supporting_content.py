"""Supporting content the answer model may point at by ID.

The model never writes this content. It names an eligible ID; the backend validates the ID
against what is on this member's record and resolves the text from the V2.3 library.

    edu.<biomarker_id>        medical_education     what the test is and what this side of the range may reflect
    rel.<id_a>.<id_b>         medical_relationship  how two results on the record connect
    life.<biomarker_id>       lifestyle_education   general influencing factors for a result

Measured, predicted and historical content already resolve through evidence keys
(``blood.<code>.latest``, ``bioai.<code>``, ``blood.<code>.trend``).
"""

from __future__ import annotations

from app.biomarkers import medical_registry as registry

MAX_CANDIDATES = 8
_SIDE = {"low": "low", "high": "high", "critical": "high"}


def _flag(marker) -> str | None:
    flag = getattr(marker, "flag", None)
    return getattr(flag, "value", flag)


def _on_record(index) -> dict[str, object]:
    found: dict[str, object] = {}
    for key, marker in index.markers.items():
        canonical = registry.canonical_key(key) or key
        found.setdefault(canonical, marker)
    return found


def _lines(value, limit: int = 3) -> list[str]:
    if isinstance(value, str):
        value = [value]
    return [str(v).strip() for v in (value or []) if str(v).strip()][:limit]


def candidates(index) -> list[dict]:
    """Compact, ID-only menu for the prompt. Only content that exists for this record."""
    present = _on_record(index)
    menu: list[dict] = []
    for biomarker_id in present:
        row = registry.entry_for(biomarker_id)
        if row:
            menu.append({"ref": f"edu.{biomarker_id}", "about": row.get("display_name") or biomarker_id})
    seen: set[frozenset] = set()
    for biomarker_id in present:
        for other in registry.related_ids(biomarker_id, set(present)):
            pair = frozenset({biomarker_id, other})
            if pair in seen or len(pair) != 2:
                continue
            seen.add(pair)
            a, b = sorted(pair)
            if _relationship(a, b):
                menu.append({"ref": f"rel.{a}.{b}", "about": f"{a} and {b}"})
    for biomarker_id in present:
        row = registry.entry_for(biomarker_id)
        if row and _lines(row.get("possible_influencing_factors")):
            menu.append({"ref": f"life.{biomarker_id}", "about": f"factors for {row.get('display_name') or biomarker_id}"})
    return menu[:MAX_CANDIDATES * 3]


def _relationship(a: str, b: str) -> dict | None:
    for row in registry.relationships():
        if not registry.eligible(row) or not row.get("user_explanation"):
            continue
        ends = {registry._endpoint(row, "source"), registry._endpoint(row, "related")}
        if ends == {a, b}:
            return row
    return None


def resolve(ref: str, kind: str, index) -> tuple[str | None, list[str]] | None:
    """Return (title, lines) or None when the reference is not eligible for this member."""
    parts = (ref or "").strip().lower().split(".")
    present = _on_record(index)
    if kind == "medical_education" and len(parts) == 2 and parts[0] == "edu":
        row = registry.entry_for(parts[1])
        if not row or parts[1] not in present:
            return None
        side = _SIDE.get(_flag(present[parts[1]]) or "")
        explanations = row.get("result_explanations") or {}
        lines = _lines(row.get("short_description"), 1) + _lines(row.get("what_happens_inside_my_body"), 2)
        if side:
            lines += _lines(explanations.get(side), 2)
        return row.get("display_name"), lines
    if kind == "medical_relationship" and len(parts) == 3 and parts[0] == "rel":
        if parts[1] not in present or parts[2] not in present:
            return None
        row = _relationship(*sorted(parts[1:]))
        if not row:
            return None
        return None, [row["user_explanation"]] + _lines(row.get("clinical_limitations"), 1)
    if kind == "lifestyle_education" and len(parts) == 2 and parts[0] == "life":
        row = registry.entry_for(parts[1])
        factors = _lines(row.get("possible_influencing_factors"), 5) if row and parts[1] in present else []
        if not factors:
            return None
        return f"What can influence {row.get('display_name') or parts[1]}", [
            "General factors that may influence this result: " + ", ".join(factors) + ".",
            "These are general, not a finding about you.",
        ]
    return None
