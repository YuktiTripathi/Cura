"""Deterministic Markdown cleanup for house style answers.

Fixes layout only: heading levels, blank lines, bullet markers, unit spacing and stray
bold. It never changes a number, a unit or the meaning of a sentence.
"""

import re

_HEADING = re.compile(r"^\s{0,3}#{1,6}\s*(.+?)\s*#*\s*$")
_BULLET = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+(.*)$")
_UNIT_GAP = re.compile(
    r"(?<![\w.])(\d+(?:\.\d+)?)(?=(?:mg/dL|g/dL|mmol/L|mIU/L|uIU/mL|IU/L|U/L|ng/mL|pg/mL|ng/dL|ug/dL|mcg/dL|mEq/L|fL|pg|g/L|mg/L)\b)",
    re.I,
)
_PERCENT_GAP = re.compile(r"(\d)\s+%")
_UNIT_STICKY_SLASH = re.compile(r"(\d)\s*(mg|g|ng|pg|ug|mcg|mIU|uIU|IU|U|mmol|mEq)\s*/\s*(dL|mL|L)\b", re.I)


def _fix_units(line: str) -> str:
    line = _PERCENT_GAP.sub(r"\1%", line)
    line = _UNIT_STICKY_SLASH.sub(lambda m: f"{m.group(1)} {m.group(2)}/{m.group(3)}", line)
    return _UNIT_GAP.sub(r"\1 ", line)


def tidy_markdown(text: str) -> str:
    if not text:
        return ""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out: list[str] = []
    in_fence = False
    for raw in lines:
        line = raw.rstrip()
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            out.append(line)
            continue
        if in_fence:
            out.append(line)
            continue
        if not line.strip():
            out.append("")
            continue
        heading = _HEADING.match(line)
        if heading:
            title = heading.group(1).replace("**", "").strip().rstrip(":")
            if out and out[-1] != "":
                out.append("")
            out.append(f"## {title}")
            out.append("")
            continue
        bullet = _BULLET.match(line)
        if bullet:
            line = "- " + _fix_units(bullet.group(1).strip())
        else:
            line = _fix_units(line.strip())
        line = re.sub(r"\*\*\s*\*\*", "", line)
        line = re.sub(r"(?<!\*)\*\*(?!\*)([^*]*)$", r"\1", line) if line.count("**") % 2 else line
        out.append(line)
    text = "\n".join(out)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
