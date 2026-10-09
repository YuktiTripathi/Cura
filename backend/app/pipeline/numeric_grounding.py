"""Match numbers that sit next to a retrieved marker or score name.

Ordinary percentages and explanation numbers are ignored unless they are
written beside a name that came from the evidence package.
"""

from __future__ import annotations

import re


def unsupported_adjacent_numbers(answer: str, package: dict | None) -> list[str]:
    if not package or not answer:
        return []
    flags: list[str] = []
    rows = list(package.get("measurements") or []) + list(package.get("bio_ai_risks") or [])
    for row in rows:
        name = (row.get("name") or "").strip()
        if len(name) < 3:
            continue
        value = row.get("value", row.get("score"))
        if not isinstance(value, (int, float)):
            continue
        allowed = {float(value)}
        for bound in (row.get("reference_low"), row.get("reference_high")):
            if isinstance(bound, (int, float)):
                allowed.add(float(bound))
        pattern = re.compile(rf"{re.escape(name)}\D{{0,40}}(\d+(?:\.\d+)?)", re.I)
        for match in pattern.finditer(answer):
            number = float(match.group(1))
            if not any(abs(number - item) < 0.05 for item in allowed):
                flags.append("unsupported_adjacent_number")
                return flags
    return flags
