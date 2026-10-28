"""Last wording fixes on a finished answer, model-written or not.

These are deterministic so they hold whatever the model writes:
- a laboratory-only answer never calls its results "risk estimates";
- each not-a-diagnosis qualifier (risk estimate, lab reading) appears once;
- internal words ("retrieved", "retrieval") become plain language;
- test names use their standard spelling (HbA1c);
- a sentence naming a Bio-AI assessment the member's report does not have is dropped.
"""

from __future__ import annotations

import re

from app.contracts.health_context import HealthContext

_RISK_QUALIFIER = re.compile(r"(?:This|These|That|Those) (?:is|are) (?:a )?risk estimates?, not (?:a )?(?:medical )?diagnos[ie]s\.", re.I)
# Short stand-alone qualifier sentences only, so a longer sentence with real content stays.
# A qualifier that is its own sentence. Matching from any space would delete the
# end of a content sentence and leave a fragment such as "unhealthy blood".
_ANY_QUALIFIER = re.compile(
    r"(?:^|(?<=[.!?।]\s))\s*[-*•]?\s*[^.!?\n]{0,90}\bnot (?:a )?(?:medical )?diagnos[ie]s\b[^.!?\n]{0,40}[.!?]",
    re.I | re.M,
)
_RETRIEVED = (
    (re.compile(r"\b(\w[\w\s-]{0,40}?) (?:was|were) not retrieved\b", re.I), r"\1 isn't included in your report"),
    (re.compile(r"\bnot retrieved\b", re.I), "not included in your report"),
    (re.compile(r"\bin the retrieved (?:records|report|data)\b", re.I), "in your report"),
)
_SPELLING = (
    (re.compile(r"\bHba1c\b|\bHBA1C\b|\bHBA1c\b|\bhba1c\b"), "HbA1c"),
    (re.compile(r"\bCholestrol\b", re.I), "Cholesterol"),
    (re.compile(r"\b(LDL|HDL|VLDL) Cholesterol(?: (?:Calculated|Direct|Calc\.?))?\b", re.I), lambda m: f"{m.group(1).upper()} cholesterol"),
    (re.compile(r"\bCholesterol,? Total\b", re.I), "total cholesterol"),
)
# Data-sheet habits a model sometimes copies from the evidence; said the way a person would.
_SHEET = (
    # "Quick idea:" / "How they connect:" style labels.
    (re.compile(r"(^|(?<=[.!?]\s)|(?<=^- )|(?<=^\* ))(?:Quick idea|Short answer|In short|Bottom line|How they connect|Why it matters|What it means|Summary)\s*:\s*", re.I | re.M), r"\1"),
    # "this report marks it high" -> plain words.
    (re.compile(r"\b(?:this|the|your) report marks (?:it|this) (high|low)\b", re.I), lambda m: f"that is {'higher' if m.group(1).lower() == 'high' else 'lower'} than the healthy range"),
    (re.compile(r"\b(?:this|the|your) report marks (?:it|this) (?:normal|within range)\b", re.I), "that is in the healthy range"),
    # "sleeping_hours = Between 5 to 7 hours" -> "sleeping hours: Between 5 to 7 hours".
    (re.compile(r"\bYour questionnaire\s*:\s*", re.I), "In your questionnaire, "),
    (re.compile(r"\b([a-z]+(?:_[a-z0-9]+)+)\s*=\s*([^.;\n]+)"),
     lambda m: f'your answer for {m.group(1).replace("_", " ")} was "{m.group(2).strip()}"'),
)
_DATED_VALUE = re.compile(r"(\d(?:[\d.]*)\s*(?:%|[A-Za-zµμ/]+(?:/[A-Za-z]+)?))\s+on\s+(\d{4}-\d{2}-\d{2})\b")
_MEMBER_QUESTION = re.compile(
    r"(?:(?<=[.!])[ \t]+|^)(?:Why|What|How|Is|Are|Can|Could|Should|Do|Does|Will|Would)\b[^.!?\n]{0,160}\bmy\b[^.!?\n]{0,160}\?[ \t]*$",
    re.M,
)
# The Bio-AI report's assessments as members see them: 9 for men, 10 for women (PCOS).
_ASSESSMENTS = {
    "metabolic_syndrome": ("metabolic syndrome",),
    "dyslipidemia": ("dyslipidemia", "dyslipidaemia"),
    "cardiac_health": ("cardiac health", "heart health"),
    "nafld": ("nafld", "fatty liver", "non-alcoholic fatty liver"),
    "oxidative_stress": ("oxidative stress",),
    "hypertension": ("hypertension",),
    "obesity": ("obesity",),
    "thyroid": ("thyroid health",),
    "type_2_diabetes": ("type 2 diabetes",),
    "pcos": ("pcos", "polycystic ovary", "polycystic ovarian"),
}


def _norm(text: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")


def _present_assessments(context: HealthContext) -> set[str]:
    present = set()
    for risk in context.bio_ai_risks or []:
        blob = f"{_norm(risk.code)} {_norm(risk.name)}"
        for code, names in _ASSESSMENTS.items():
            if code in blob or any(_norm(name) in blob for name in names):
                present.add(code)
    return present


_BULLET = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")


def _drop_unlisted_assessments(text: str, context: HealthContext) -> str:
    """Bio-AI answers may name only assessments the member's report contains.

    Only a whole bullet that is solely about a missing assessment is removed. Sentences
    inside a paragraph are never cut, because removing one mid-explanation leaves the
    rest without its subject.
    """
    if not context.bio_ai_risks:
        return text
    present = _present_assessments(context)
    missing = {code: names for code, names in _ASSESSMENTS.items() if code not in present}
    if not missing:
        return text
    missing_pattern = re.compile(
        r"\b(" + "|".join(re.escape(n) for names in missing.values() for n in names) + r")\b", re.I
    )
    present_pattern = re.compile(
        r"\b(" + "|".join(re.escape(n) for code in present for n in _ASSESSMENTS[code]) + r")\b", re.I
    ) if present else None
    kept = []
    for line in text.split("\n"):
        about_missing_only = (
            _BULLET.match(line)
            and missing_pattern.search(line)
            and not (present_pattern and present_pattern.search(line))
            and not re.search(r"\b(isn't|not) included\b|\bdoesn't include\b", line)
        )
        if not about_missing_only:
            kept.append(line)
    return "\n".join(kept)


def _qualifier_once(text: str, *, both_sources: bool = True) -> str:
    """Once per kind when an answer covers lab results and Bio-AI scores; otherwise once in all."""
    seen: dict[str, str] = {}

    def take(match: re.Match) -> str:
        kind = "risk" if both_sources and re.search(r"risk estimate", match.group(0), re.I) else "other"
        if kind not in seen:
            seen[kind] = match.group(0).strip()
        return ""

    out = _ANY_QUALIFIER.sub(take, text)
    out = re.sub(r"[ \t]{2,}", " ", out).replace(" \n", "\n").strip()
    tail = [seen[kind] for kind in ("other", "risk") if kind in seen and seen[kind].lower() not in out.lower()]
    if tail:
        out = out.rstrip() + "\n\n" + " ".join(tail)
    return out


_LEAKED_LABEL = re.compile(
    r"(?im)^\s*[-*]?\s*(?:short opening line\s*:?\s*)?"
    r"(?:here (?:is|are) (?:a |the )?(?:short,? )?(?:plain )?(?:summary|key things|main points)\b[^\n]*|"
    r"let me explain your results\.?)\s*"
)
_MISSING_BIO = re.compile(
    r"(?im)^\s*[-*]?\s*.*\bbio-?\s*ai\b[^\n]*\b(?:not (?:present|included|found)|does not include)\b[^\n]*\n?"
)
_REFERRAL = re.compile(r"\b(doctor|clinician|physician|medical review)\b", re.I)
_DISCUSS_SOON = re.compile(r"Please discuss this result with your doctor soon\.\s*", re.I)


def _ensure_urgent_notes(text: str, context: HealthContext) -> str:
    """A result in a guideline range that needs a doctor soon (HbA1c 9.1%, triglycerides over
    500 mg/dL) is stated once, with its value and cut-off. Do not add a second referral."""
    from app.pipeline.clinical_thresholds import clinical_notes

    markers = [m for m in context.markers or [] if getattr(m, "value", None) is not None]
    if not markers:
        return text
    additions = []
    already_referred = bool(_REFERRAL.search(text))
    for note in clinical_notes(markers):
        if not note.urgent:
            continue
        value = f"{note.marker.value:g}"
        name = note.marker.name or note.marker.key or ""
        cutoffs = re.findall(r"\((\d+(?:\.\d+)?)", note.text)
        has_value = bool(re.search(rf"(?<![\d.]){re.escape(value)}(?![\d])", text))
        has_name = bool(name and re.search(re.escape(name), text, re.I))
        said = has_value and any(c in text for c in cutoffs)
        if said or (already_referred and (has_value or has_name)):
            continue
        fact = _DISCUSS_SOON.sub("", note.text).strip() if already_referred else note.text
        if fact:
            additions.append(fact)
    if not additions:
        return text
    return text.rstrip() + "\n\n**Important:** " + " ".join(additions)


def _plain_speech(text: str) -> str:
    out = text
    for pattern, repl in _SHEET:
        out = pattern.sub(repl, out)
    # One test date repeated after every value: the cards show it, so drop it. Several dates stay.
    if len(set(_DATED_VALUE.findall(out) and [d for _v, d in _DATED_VALUE.findall(out)])) == 1:
        out = _DATED_VALUE.sub(r"\1", out)
    # A question in the member's own voice ("Why might my sleep...?") is a follow-up chip, not Cura's words.
    out = _MEMBER_QUESTION.sub("", out)
    # Capitalize a line or sentence the label removal left lower-case.
    out = re.sub(r"(^|^[-*] |[.!?] )([a-z])", lambda m: m.group(1) + m.group(2).upper(), out, flags=re.M)
    return out


_BULLET_START = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")
_HEADING = re.compile(r"^\s*#{1,6}\s+\S|^\s*\*\*[^*]+\*\*\s*$")
# A finished sentence, a measurement, or a unit. "Dr." and "mg/dL" count; "average blood" does not.
_COMPLETE_END = re.compile(
    r"(?:[.!?।…]|[)\"”’]|%|\d|"
    r"(?:mg/dl|mg/l|ng/ml|pg/ml|g/dl|u/l|iu/l|mmol/l|mm ?hg|ml/min|kg/m2))\s*$",
    re.I,
)


def _segments(text: str) -> list[str]:
    """Join a sentence that wraps onto the next line, then treat each bullet as its own segment."""
    segments: list[str] = []
    buf = ""
    for line in (text or "").splitlines():
        if not line.strip():
            if buf:
                segments.append(buf)
                buf = ""
            continue
        continuation = buf and not _BULLET_START.match(line) and not _COMPLETE_END.search(buf.rstrip())
        if continuation:
            buf = buf.rstrip() + " " + line.strip()
        else:
            if buf:
                segments.append(buf)
            buf = line
    if buf:
        segments.append(buf)
    return segments


def incomplete_segments(text: str) -> list[str]:
    """Bullets or sentences that stop mid-clause, wherever they sit in the answer."""
    found = []
    for segment in _segments(text):
        if _HEADING.match(segment):
            continue
        body = _BULLET_START.sub("", segment).strip()
        if not body or len(body.split()) < 2 or _COMPLETE_END.search(body):
            continue
        found.append(segment)
    return found


def _stated_number(text: str, value) -> bool:
    try:
        token = f"{float(value):g}"
    except (TypeError, ValueError):
        return False
    return bool(re.search(rf"(?<![\d.]){re.escape(token)}(?![\d.])", text or ""))


def _fact_line(marker) -> str:
    unit = marker.unit or ""
    value = f"{float(marker.value):g}"
    shown = f"{value}{unit}" if unit.startswith("%") else f"{value} {unit}".strip()
    name = marker.name or marker.key or "This result"
    return f"{name} is {shown}."


def repair_incomplete_output(text: str, context: HealthContext) -> str:
    """Drop a fragment. If it was the only place a verified result appeared, keep that result."""
    bad = incomplete_segments(text)
    if not bad:
        return text
    kept: list[str] = []
    for segment in _segments(text):
        if segment not in bad:
            kept.append(segment)
            continue
        already = "\n".join(kept)
        for marker in context.markers or []:
            if getattr(marker, "value", None) is None:
                continue
            if _stated_number(segment, marker.value) and not _stated_number(already, marker.value):
                kept.append(_fact_line(marker))
                break
        else:
            for risk in context.bio_ai_risks or []:
                if risk.score is None:
                    continue
                if _stated_number(segment, risk.score) and not _stated_number(already, risk.score):
                    name = risk.name or risk.code or "This score"
                    status = f", {risk.status}" if risk.status else ""
                    kept.append(f"{name} is {float(risk.score):g}{status}.")
                    break
    return "\n".join(kept).strip()


_BARE_LABEL = re.compile(r"(?m)^\s*[-*]?\s*[A-Za-z][^:\n\d]{0,40}:\s*$")
# A planning label glued to the front of a bullet ("What this test is: ..."), not a phrase list.
_LABEL_PREFIX = re.compile(r"(?m)^(\s*[-*]\s+)[A-Z][A-Za-z ]{0,32}:\s+")


def _drop_repeated_bullets(text: str) -> str:
    """Drop a later bullet that only restates an earlier one."""
    kept: list[str] = []
    seen: list[str] = []
    for line in _LABEL_PREFIX.sub(r"\1", _BARE_LABEL.sub("", text)).splitlines():
        body = re.sub(r"\s+", " ", _BULLET_START.sub("", line).strip().lower())
        if body and len(body) > 24 and any(body in prior or prior in body for prior in seen):
            continue
        kept.append(line)
        if body:
            seen.append(body)
    return "\n".join(kept)


def polish_answer(text: str, context: HealthContext, *, intent: str | None = None, add_notes: bool = True) -> str:
    if not text:
        return text
    out = _MISSING_BIO.sub("", _LEAKED_LABEL.sub("", text))
    for pattern, repl in _SPELLING:
        out = pattern.sub(repl, out)
    for pattern, repl in _RETRIEVED:
        out = pattern.sub(repl, out)
    out = _plain_speech(out)
    lab_only = (intent or "").startswith(("report_", "blood_", "latest_", "previous_", "trend")) and not context.bio_ai_risks
    if lab_only:
        out = _RISK_QUALIFIER.sub("This is a reading of your results, not a diagnosis.", out)
    out = _drop_unlisted_assessments(out, context)
    if add_notes:
        out = _ensure_urgent_notes(out, context)
    both = bool(context.markers) and bool(context.bio_ai_risks) and not (intent or "").startswith("bio_ai")
    out = _qualifier_once(out, both_sources=both)
    return repair_incomplete_output(_drop_repeated_bullets(out), context)
