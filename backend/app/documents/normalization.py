from __future__ import annotations

import re
import unicodedata

_HYPHEN_BREAK = re.compile(r"(\w)-\n(\w)")
_MULTI_NL = re.compile(r"\n{3,}")
_MULTI_SPACE = re.compile(r"[^\S\n]{2,}")


def normalize_extracted_text(text: str) -> str:
    if not text:
        return ""
    value = unicodedata.normalize("NFKC", text)
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = _HYPHEN_BREAK.sub(r"\1\2", value)
    value = _MULTI_NL.sub("\n\n", value)
    value = _MULTI_SPACE.sub(" ", value)
    lines = [line.strip() for line in value.split("\n")]
    return "\n".join(lines).strip()
