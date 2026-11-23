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


_KNOWN_LABELS = ("What to do first", "Then", "Looking good", "When to see a doctor", "What the numbers show", "What it means", "How to read the scores")
# Labels that are no longer shown: the sentence stays, the bold heading goes.
_DROPPED_LABELS = ("what the numbers show", "what it means", "how to read the scores", "looking good", "then")
_LABEL = re.compile(r"^- \*{0,2}(" + "|".join(_KNOWN_LABELS) + r")\*{0,2}\s*:\s*\*{0,2}\s*(?=\S)", re.I)
_ANY_LABEL = re.compile(r"^- \*\*([A-Za-z][A-Za-z ,&'-]{1,40}):\*\*\s*")
_KEPT_LABELS = {"what to do first", "when to see a doctor"}
_BOLD_LABEL_GLUED = re.compile(r"^(- \*\*[^*\n]{1,60}:\*\*)(?=\S)")


def _fix_labels(line: str) -> str:
    """The same bold label style on every bullet, with a space after it."""
    canon = {label.lower(): label for label in _KNOWN_LABELS}
    def _swap(m):
        if m.group(1).lower() in _DROPPED_LABELS:
            return "- "
        return f"- **{canon[m.group(1).lower()]}:** "

    line = _LABEL.sub(_swap, line)
    line = _BOLD_LABEL_GLUED.sub(r"\1 ", line)
    # Any other short bold lead in label (for example "Body protection:") is dropped too; only the kept labels stay.
    m = _ANY_LABEL.match(line)
    if m and m.group(1).strip().lower() not in _KEPT_LABELS:
        return "- " + line[m.end():]
    return line


def _fix_units(line: str) -> str:
    line = _PERCENT_GAP.sub(r"\1%", line)
    line = _UNIT_STICKY_SLASH.sub(lambda m: f"{m.group(1)} {m.group(2)}/{m.group(3)}", line)
    return _UNIT_GAP.sub(r"\1 ", line)


_GLUED_HEADING = re.compile(r"(?<=\S)[ \t]+(#{2,3}[ \t]+[A-Z][^\n#]{2,60})(?=\s*(?:\n|$|-\s))")


def tidy_markdown(text: str) -> str:
    if not text:
        return ""
    # A heading glued to the end of a bullet goes back on its own line.
    text = _GLUED_HEADING.sub(lambda m: "\n\n" + m.group(1), text)
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
            line = _fix_labels("- " + _fix_units(bullet.group(1).strip()))
        else:
            line = _fix_units(line.strip())
        line = re.sub(r"[ \t]+-$", "", line)  # a stray bullet dash left at the end of a line
        line = re.sub(r"\*\*\s*\*\*", "", line)
        line = re.sub(r"(?<!\*)\*\*(?!\*)([^*]*)$", r"\1", line) if line.count("**") % 2 else line
        out.append(line)
    text = "\n".join(out)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# Most bullets a report section may keep. Bullets are written most important first, so
# trimming drops the least important ones. Cards under the answer hold every value.
# A body system section holds its two bullets and, at most, one extra short one.
DEFAULT_SECTION_LIMIT = 3

SECTION_LIMITS = {
    "overall health summary": 2,
    "important findings": 4,
    "reassuring findings": 2,
    "what these results mean": 3,
    "how your findings fit together": 2,
    "practical recommendations": 4,
    "when to consult a doctor": 2,
    "what to do next": 3,
}


def cap_report_sections(text: str) -> str:
    """Trim each report section to its bullet limit. Text without the report headings is untouched."""
    if not text or "## " not in text:
        return text
    out: list[str] = []
    limit: int | None = None
    kept = 0
    for line in text.split("\n"):
        heading = re.match(r"^##\s+(.+?)\s*$", line)
        if heading:
            limit = SECTION_LIMITS.get(heading.group(1).strip().lower(), DEFAULT_SECTION_LIMIT)
            kept = 0
            out.append(line)
            continue
        if limit is not None and line.startswith("- "):
            kept += 1
            if kept > limit:
                continue
        out.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()


_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_ISO_DATE = re.compile(r"\b(20\d{2})-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])\b")
_RANGE_DASH = re.compile(r"(?<=\d)\s*[\u2013\u2014]\s*(?=\d)|(?<=\d)\s+-\s+(?=\d)")
_DL = re.compile(r"(?<=[A-Za-z])/dl\b")
_NAME_FIXES = (("Cholestrol", "Cholesterol"), ("cholestrol", "cholesterol"))


def friendly_text(text: str) -> str:
    """Dates in words, ranges with 'to', units with a capital L, common lab misspellings fixed."""
    if not text:
        return text
    text = _ISO_DATE.sub(lambda m: f"{int(m.group(3))} {_MONTHS[int(m.group(2)) - 1]} {m.group(1)}", text)
    text = _RANGE_DASH.sub(" to ", text)
    text = _DL.sub("/dL", text)
    for wrong, right in _NAME_FIXES:
        text = text.replace(wrong, right)
    return text


def drop_empty_headings(text: str) -> str:
    """A heading with no bullet under it is removed."""
    lines = text.split("\n")
    out: list[str] = []
    for i, line in enumerate(lines):
        if line.startswith("## "):
            follow = next((x for x in lines[i + 1:] if x.strip()), "")
            if not follow.startswith("- "):
                continue
        out.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()


def strip_headings(text: str) -> str:
    """Narrow questions get plain bullets: remove every heading line."""
    lines = [line for line in text.split("\n") if not re.match(r"^#{1,6}\s", line)]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


MAX_REPORT_BULLETS = 14


def cap_total_bullets(text: str, limit: int = MAX_REPORT_BULLETS) -> str:
    """A whole report answer keeps at most `limit` bullets. Bullets are written most important first."""
    kept = 0
    out: list[str] = []
    for line in text.split("\n"):
        if line.startswith("- "):
            kept += 1
            if kept > limit:
                continue
        out.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()


_LIMIT_SENTENCE = re.compile(
    r"\b(?:cannot|can't|can not|does not|doesn't|do not)\s+(?:by itself\s+)?(?:confirm|diagnos|identify|rule out|prove|tell)|"
    r"\bnot a diagnosis\b|\brisk estimate\b|\bnot (?:a )?(?:medical )?diagnos",
    re.I,
)


def drop_repeated_limits(text: str) -> str:
    """The limit of what a report can tell ("it cannot confirm a disease", "a risk estimate, not a diagnosis") is
    said once. Later sentences that only restate it are dropped, and a bullet left empty goes with them."""
    if not text:
        return text
    seen = False
    out: list[str] = []
    for line in text.split("\n"):
        if not line.startswith("- "):
            out.append(line)
            continue
        kept: list[str] = []
        for sentence in re.split(r"(?<=[.!?])\s+", line):
            if _LIMIT_SENTENCE.search(sentence):
                if seen:
                    continue
                seen = True
            kept.append(sentence)
        joined = " ".join(kept).strip()
        if joined and joined != "-" and len(joined.split()) > 1:
            out.append(joined)
    return "\n".join(out)


_DOCTOR_SENTENCE = re.compile(
    r"\b(?:share|discuss|mention|bring|show|talk)\b[^.!?]*\b(?:doctor|clinician|physician)\b|\b(?:doctor|clinician)\b[^.!?]*\broutine (?:visit|check)",
    re.I,
)
_REASSURING = re.compile(r"\b(?:within (?:the )?range|in range|inside (?:the )?range|healthy|look(?:s)? (?:great|good)|normal)\b", re.I)
_CONCERN = re.compile(r"\b(?:above|below|outside|high|low|raised|elevated|critical|very high|slightly|needs attention)\b", re.I)


def drop_doctor_for_healthy(text: str) -> str:
    """A "share it with your doctor" sentence belongs only to a result outside its range or a serious pointer.
    Where a bullet is about results that are within range or Healthy and says nothing of concern, it goes."""
    if not text:
        return text
    out: list[str] = []
    for line in text.split("\n"):
        if line.startswith("- ") and _REASSURING.search(line) and not _CONCERN.search(line) and _DOCTOR_SENTENCE.search(line):
            kept = [x for x in re.split(r"(?<=[.!?])\s+", line) if not _DOCTOR_SENTENCE.search(x)]
            joined = " ".join(kept).strip()
            if joined and len(joined.split()) > 2:
                out.append(joined)
            continue
        out.append(line)
    return "\n".join(out)


_ROUTINE_DOCTOR = re.compile(
    r"\b(?:doctor|clinician|physician|healthcare provider)\b[^.!?\n]*\b(?:routine|next|regular)\s+(?:visit|check|appointment|checkup|check-up)\b"
    r"|\b(?:routine|next|regular)\s+(?:visit|check|appointment|checkup|check-up)\b[^.!?\n]*\b(?:doctor|clinician|physician)\b"
    r"|^\W*(?:please\s+)?(?:discuss|talk about|go through|review)\s+(?:this|these|them|it)\s+with\s+(?:your|a)\s+(?:doctor|clinician)\W*$",
    re.I,
)


def drop_routine_doctor(text: str) -> str:
    """A routine-visit or generic "discuss this with your doctor" sentence is filler. Drop it wherever it appears.
    A real referral says how soon or why ("within a few weeks", "as this is well above range") and is kept."""
    if not text:
        return text
    out: list[str] = []
    for line in text.split("\n"):
        if not _ROUTINE_DOCTOR.search(line):
            out.append(line)
            continue
        kept = [x for x in re.split(r"(?<=[.!?])\s+", line) if not _ROUTINE_DOCTOR.search(x)]
        joined = " ".join(kept).strip()
        marker = re.match(r"^(\s*[-*]\s+)", line)
        if joined and (not marker or len(joined.split()) > 2) and joined not in ("-", "*"):
            out.append(joined if not marker or joined.startswith(marker.group(1).strip()) else marker.group(1) + joined)
    return "\n".join(out)


_PRAISE_OPENER = re.compile(
    r"^\s*(?:(?:thanks|thank you)[,!.]?\s*)?(?:that'?s |what )?(?:a |an )?(?:really |very |such )?"
    r"(?:great|good|nice|excellent|fair|smart|interesting|important|lovely|wonderful)\s+(?:question|ask)\b[^\n]*",
    re.I,
)
_QUESTION_LABEL = re.compile(r"(?m)^(\s*[-*]\s+)(?:Change|Trend|Worry\??|Is it a worry\??|Next step|What it means|Result):\s+")
_BULLET_LABEL = re.compile(r"(?m)^(\s*[-*]\s+)(?:[A-Z][A-Za-z']*)(?: [A-Za-z']+){0,3}:\s+(?=[^\s\d])")


_ROBOTIC_LEAD = re.compile(
    r"(?:(?<=^)|(?<=[.!?]\s)|(?<=\n)|(?<=\*\s)|(?<=-\s))\s*(?:Based on|According to) (?:the )?(?:retrieved|available|provided|supplied)"
    r"(?: medical)? (?:biomarkers?|data|medical context|context|information|records?|results?)\s*,?\s*(?P<c>[A-Za-z])",
    re.I,
)
_RECOMMENDED = re.compile(
    r"\bIt is recommended that (?:the patient|you|the individual) (?:should |may |can )?"
    r"(?=(?:consider|try|avoid|limit|increase|reduce|eat|drink|get|keep|follow|take|include|stay|exercise|monitor|recheck|repeat|discuss)\b)",
    re.I,
)
_FURTHER_EVALUATION = re.compile(
    r"[^.!?\n]*\b(?:consult|see|speak (?:to|with)|talk to|contact) (?:your |a )?(?:healthcare provider|healthcare professional|doctor|physician)"
    r"[^.!?\n]*\bfor (?:a )?further (?:evaluation|assessment|guidance)\b[^.!?\n]*[.!?]?\s*",
    re.I,
)
_HYPE_SENTENCE = re.compile(
    r"^\W*(?:congratulations|congrats|well done|great job|good job|awesome|fantastic|amazing|kudos|way to go|bravo)\b",
    re.I,
)
_BLAME = re.compile(
    r"\b(?:you (?:have )?failed|your fault|you should have|you neglected|you(?:'ve| have) been (?:careless|lazy)|you(?:'re| are) to blame)\b",
    re.I,
)


def soften_robotic_phrases(text: str) -> str:
    """Report-speak becomes plain talk, and the generic referral line is kept at most once."""
    if not text:
        return text

    def lead(match: re.Match) -> str:
        whole = match.group(0)
        return whole[: len(whole) - len(whole.lstrip())] + match.group("c").upper()

    out = _ROBOTIC_LEAD.sub(lead, text)
    out = _RECOMMENDED.sub("You can ", out)
    seen = False

    def once(match: re.Match) -> str:
        nonlocal seen
        if not seen:
            seen = True
            return match.group(0)
        return ""

    return _FURTHER_EVALUATION.sub(once, out)


def drop_hype_and_blame(text: str) -> str:
    """Medical results are not a game. Cheering interjections and blame wording are dropped, sentence by sentence."""
    if not text:
        return text
    lines: list[str] = []
    for line in text.split("\n"):
        parts = re.split(r"(?<=[.!?])\s+", line)
        kept = [part for part in parts if not (_HYPE_SENTENCE.search(part) or _BLAME.search(part))]
        if len(kept) == len(parts):
            lines.append(line)
            continue
        joined = " ".join(kept).strip()
        marker = re.match(r"^(\s*[-*]\s+)", line)
        if joined and joined not in ("-", "*") and (not marker or len(joined.split()) > 2):
            lines.append(joined if not marker or joined.startswith(marker.group(1).strip()) else marker.group(1) + joined)
    return "\n".join(lines)


def drop_praise_opener(text: str) -> str:
    """'Great question about ...' is not an answer. The first line goes when it only praises the question."""
    if not text:
        return text
    lines = text.lstrip().split("\n")
    if lines and not lines[0].lstrip().startswith(("-", "*", "#")) and _PRAISE_OPENER.match(lines[0]):
        return "\n".join(lines[1:]).lstrip("\n")
    return text


def drop_bullet_labels(text: str) -> str:
    """A bullet is a sentence, not 'Worry level: ...'. Bold labels the report shapes allow are left alone."""
    def _strip(match: re.Match) -> str:
        rest = match.string[match.end():match.end() + 1]
        return match.group(1) + rest.upper()

    out = []
    for line in (text or "").split("\n"):
        m = _QUESTION_LABEL.match(line) or _BULLET_LABEL.match(line)
        if m:
            tail = line[m.end():]
            line = m.group(1) + tail[:1].upper() + tail[1:]
        out.append(line)
    return "\n".join(out)


_DASHES = re.compile(r"\s*[\u2014\u2013]\s*")


def drop_dashes(text: str) -> str:
    """No em or en dashes in an answer. A range reads 'to', a compound word keeps a hyphen, a pause is a comma."""
    def _swap(match: re.Match) -> str:
        before = match.string[max(0, match.start() - 1):match.start()]
        after = match.string[match.end():match.end() + 1]
        token = match.group(0)
        if before.isdigit() and after.isdigit():
            return " to "
        if token == token.strip():  # glued, as in "D\u2013rich"
            return "-"
        return ", "

    return _DASHES.sub(_swap, text or "")


_INLINE_BULLET = re.compile(r"(?<=[.!?])\s+[-*]\s+(?=[A-Z0-9*])")


def split_inline_bullets(text: str) -> str:
    """Bullets that arrived glued into one paragraph ("... energy. - Next point. - Another") go back on their own lines."""
    out = []
    for line in (text or "").split("\n"):
        if len(_INLINE_BULLET.findall(line)) >= 2:
            parts = _INLINE_BULLET.split(line)
            head = parts[0].strip()
            first_is_bullet = head.startswith(("-", "*"))
            out.append(head if first_is_bullet else head)
            if not first_is_bullet and head:
                out.append("")
            out.extend("- " + p.strip() for p in parts[1:] if p.strip())
        else:
            out.append(line)
    return "\n".join(out)


def clean_bullet_runs(text: str) -> str:
    """Remove empty bullets and the blank line the model leaves between two bullets of one list."""
    lines = [ln for ln in (text or "").split("\n") if ln.strip() not in {"-", "*", "\u2022"}]
    out: list[str] = []
    for i, line in enumerate(lines):
        if not line.strip() and out and out[-1].lstrip().startswith("- ") and i + 1 < len(lines) and lines[i + 1].lstrip().startswith("- "):
            continue
        out.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()
