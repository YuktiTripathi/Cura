"""Last check on everything a member sees, in every response mode.

Applied once per response, after safety and composition, so no stage can reintroduce:

* em dashes (replaced naturally: commas, full stops, parentheses, en dash in ranges);
* duplicate paragraphs;
* the same safety disclaimer repeated in different words (the first one stays);
* raw "None to None" ranges;
* generic "that marker was not available" filler;
* full blood-report tables under answers that did not ask for a report;
* "still unclear" sections built from optional missing markers.

It never adds content and never changes a measured value.
"""

from __future__ import annotations

import re

from pydantic import BaseModel

# ---------------------------------------------------------------- text

_EM = "\u2014"
_NONE_RANGE = re.compile(
    r"\s*[\(\[]?\s*(?:reference\s+)?(?:range:?\s*)?\bNone\s*(?:to|-|\u2013|\u2014)\s*None\b\s*[\)\]]?", re.I
)
_GENERIC_UNAVAILABLE = re.compile(
    r"\b(?:that|this)\s+(?:marker|result|value|test)\s+(?:was|is|remains)\s+(?:not\s+available|unavailable)\b"
    r"|\bremains?\s+unavailable\b",
    re.I,
)
# Disclaimer families: the first sentence of each family is kept, later ones are dropped.
# Each kind of qualifier is said at most once: one "not a diagnosis", one clinician pointer.
_DISCLAIMERS = {
    "diagnosis": re.compile(r"\bnot\s+(?:a|an)\s+(?:medical\s+|formal\s+|clinical\s+)?diagnos\w*|\bdoes\s+not\s+(?:mean|confirm)\s+(?:a\s+)?diagnos\w*", re.I),
    "clinician": re.compile(
        r"\b(?:talk|speak|discuss|check|consult|review)\w*\b[^.!?]{0,70}\b(?:doctor|clinician|physician|healthcare\s+(?:provider|professional|team))\b"
        r"|\bclinician\s+(?:interpretation|review)\b",
        re.I,
    ),
    "causation": re.compile(
        r"\b(?:does\s+not|doesn't|cannot|can't|do\s+not|don't)\s+(?:establish|prove|confirm|show|tell\s+us)\b[^.!?]{0,60}\bcaus\w*", re.I
    ),
}
_GENERIC_FOLLOW_UP = re.compile(
    r"\b(?:any (?:new )?(?:symptoms|medications?|supplements?)|anything else|other questions?|how (?:are|do) you feel)\b", re.I
)
# Topics where asking about symptoms, medication or supplements is genuinely useful.
_CARE_TOPIC = re.compile(
    r"\b(?:symptoms?|supplements?|medications?|medicines?|tired|fatigue|tablets?|pills?|"
    r"b12|vitamin|iron|ferritin|folate|anaemi\w*|anemi\w*|alt|ast|liver)\b",  # liver enzymes: medicines and supplements matter
    re.I,
)
_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[\"'(*A-Z0-9])")


def _pure_disclaimer(sentence: str) -> bool:
    """Short and value-free: a qualifier, not a finding that happens to mention a doctor."""
    return not re.search(r"\d", sentence) and len(sentence.split()) <= 25


def remove_em_dashes(text: str) -> str:
    if _EM not in text:
        return text
    text = re.sub(rf"(\d)\s*{_EM}\s*(\d)", "\\1\u2013\\2", text)  # numeric range -> en dash
    text = re.sub(rf"(?m)^(\s*){_EM}\s*", r"\1- ", text)  # dash used as a bullet
    text = re.sub(rf"\s+{_EM}\s+([^{_EM}.!?\n]{{1,80}}?)\s+{_EM}\s+", r" (\1) ", text)  # paired aside
    text = re.sub(rf"\s*{_EM}\s*(?=[A-Z])", ". ", text)  # new thought
    text = re.sub(  # "... level — this is a risk estimate" -> "... level. This is a risk estimate"
        rf"\s*{_EM}\s*(this|that|these|those|it|they|you|your|there|which means)\b",
        lambda m: ". " + m.group(1)[0].upper() + m.group(1)[1:],
        text,
    )
    text = re.sub(rf"\s*{_EM}\s*$", ".", text, flags=re.M)
    text = re.sub(rf"\s*{_EM}\s*", ", ", text)  # everything else reads as a comma
    text = re.sub(r",\s*([.,;:!?])", r"\1", text)
    text = re.sub(r"([.!?:;])\s*,\s*", r"\1 ", text)
    return text


def _norm(paragraph: str) -> str:
    return re.sub(r"[\W_]+", " ", paragraph).strip().lower()


def clean_text(text: str | None, *, keep_clinician: bool = False) -> str | None:
    """Normalize one visible string. Returns the same type it was given.

    keep_clinician: when the safety layer escalated, a "see your doctor" sentence is never
    merged away by an earlier "not a diagnosis".
    """
    if not isinstance(text, str) or not text:
        return text
    text = remove_em_dashes(text)
    text = _NONE_RANGE.sub("", text)
    paragraphs = re.split(r"\n\s*\n", text)
    seen_paragraphs: set[str] = set()
    seen_families: set[str] = set()
    seen_sentences: set[str] = set()
    kept_paragraphs = []
    for paragraph in paragraphs:
        key = _norm(paragraph)
        if key and key in seen_paragraphs:
            continue
        seen_paragraphs.add(key)
        lines = []
        for line in paragraph.split("\n"):
            sentences = _SENTENCE.split(line) if line.strip() else [line]
            kept = []
            for sentence in sentences:
                if _GENERIC_UNAVAILABLE.search(sentence):
                    continue
                sentence_key = _norm(sentence)
                if len(sentence_key) > 25 and sentence_key in seen_sentences:
                    continue  # the same sentence said twice
                seen_sentences.add(sentence_key)
                family = next((name for name, rx in _DISCLAIMERS.items() if rx.search(sentence)), None)
                if family and not _pure_disclaimer(sentence):
                    family = None  # a sentence with real content is never dropped as a repeat
                if family == "clinician" and keep_clinician:
                    family = None  # escalated, or the member asked about their doctor
                if family:
                    if family in seen_families:
                        continue
                    seen_families.add(family)
                kept.append(sentence)
            joined = " ".join(s for s in kept if s is not None)
            if line.strip() and not joined.strip():
                continue  # the whole line was filler
            lines.append(joined)
        cleaned = "\n".join(lines).strip()
        if cleaned:
            kept_paragraphs.append(cleaned)
    out = "\n\n".join(kept_paragraphs)
    out = re.sub(r"[ \t]{2,}", " ", out)
    return out.strip() if text.strip() else out


def _walk(value):
    """Clean every string inside a pydantic model / list / dict, in place where possible."""
    if isinstance(value, str):
        return remove_em_dashes(_NONE_RANGE.sub("", value)) if (_EM in value or "None" in value) else value
    if isinstance(value, BaseModel):
        for name in type(value).model_fields:
            current = getattr(value, name, None)
            if current is None:
                continue
            new = _walk(current)
            if new is not current:
                try:
                    setattr(value, name, new)
                except (TypeError, ValueError):
                    pass
        return value
    if isinstance(value, list):
        return [_walk(v) for v in value]
    if isinstance(value, dict):
        return {k: _walk(v) for k, v in value.items()}
    return value


# ---------------------------------------------------------------- report view

_REPORT_VIEW = re.compile(
    r"\b(?:show|open|list|see|view|display|give\s+me|pull\s+up)\b[^.?!]{0,40}\b(?:report|results|values|markers|labs?|tests?|bloodwork)\b"
    r"|\ball\s+(?:my\s+)?(?:results|values|markers|abnormal)\b|\babnormal\s+(?:results|values|markers)\b",
    re.I,
)


def is_report_view(message: str | None) -> bool:
    """The member explicitly asked to see results as a report or list."""
    return bool(_REPORT_VIEW.search(message or ""))


MAX_CONVERSATIONAL_FINDINGS = 4
_MISSING_NOTE = re.compile(r"\b(?:not\s+(?:available|in\s+(?:your\s+)?reports?|found|retrieved)|unavailable|missing)\b", re.I)


def _finding_key(finding) -> str:
    return (getattr(finding, "canonical_key", None) or getattr(finding, "label", "") or "").lower()


def _important_findings(findings, evidence_codes: list[str]) -> list:
    order = {code: i for i, code in enumerate(evidence_codes)}

    def rank(item):
        key = _finding_key(item)
        status = (getattr(item, "status", None) or "").lower()
        abnormal = any(word in status for word in ("high", "low", "critical", "abnormal", "above", "below"))
        return (0 if key in order else 1, order.get(key, 99), 0 if abnormal else 1)

    preferred = [f for f in findings if _finding_key(f) in order]
    pool = preferred or findings
    return sorted(pool, key=rank)[:MAX_CONVERSATIONAL_FINDINGS]


def trim_presentation(presentation, message: str, plan=None, context=None, answer: str = "") -> None:
    """Rich-mode cards follow the same rule as the answer: a few relevant values, never the
    whole report unless the member asked to see it."""
    if presentation is None:
        return
    report_view = is_report_view(message)
    evidence_codes = list(((getattr(context, "answer_evidence_trace", None) or {}).get("evidence_codes")) or [])
    if not report_view:
        findings = list(presentation.findings or [])
        if len(findings) > MAX_CONVERSATIONAL_FINDINGS:
            presentation.findings = _important_findings(findings, evidence_codes)
            presentation.display_entities = [_finding_key(f) for f in presentation.findings]
        # The full list stays reachable only as the folded "all results" disclosure of a
        # whole-health or report summary; it is never rendered under other answers.
        if getattr(presentation, "summary_style", None) != "NARRATIVE_HEALTH_SUMMARY":
            presentation.raw_findings = []
        presentation.related_findings = list(presentation.related_findings or [])[:3]
    # "What's still unclear": only when nothing could answer the question.
    gaps = [u for u in presentation.uncertainties or [] if _MISSING_NOTE.search(u)]
    notes = [u for u in presentation.uncertainties or [] if u not in gaps]
    if presentation.findings or answer.strip():
        gaps = []
    if notes and any(rx.search(answer or "") for rx in _DISCLAIMERS.values()):
        notes = []  # the answer already carries its one qualifier
    presentation.uncertainties = gaps + notes[:1]


def finalize_response(response, message: str, plan=None, context=None):
    """One normalization pass over every visible part of a response."""
    if response is None:
        return response
    escalated = bool(getattr(getattr(response, "meta", None), "escalation", None))
    asked_about_clinician = bool(re.search(r"\b(?:doctor|clinician|physician|gp)\b", message or "", re.I))
    response.answer = clean_text(response.answer, keep_clinician=escalated or asked_about_clinician) or response.answer
    trim_presentation(getattr(response, "presentation", None), message, plan, context, response.answer or "")
    for field in ("presentation", "experience", "testing_option"):
        if getattr(response, field, None) is not None:
            _walk(getattr(response, field))
    semantic = getattr(response, "semantic", None)
    if semantic is not None:
        semantic.summary = clean_text(semantic.summary) or semantic.summary
        for block in semantic.blocks:
            block.text = clean_text(block.text) if block.text else block.text
            block.title = remove_em_dashes(block.title) if block.title else block.title
            for item in block.items:
                item.title = clean_text(item.title) if item.title else item.title
                item.text = clean_text(item.text) if item.text else item.text
        semantic.follow_ups = [remove_em_dashes(f) for f in semantic.follow_ups][:3]
    # Symptom / medication / supplement questions only when this conversation is about them.
    topical = bool(_CARE_TOPIC.search(f"{message or ''} {response.answer or ''}"))
    generic = (lambda text: False) if topical else (lambda text: bool(_GENERIC_FOLLOW_UP.search(text or "")))
    follow_ups = [f for f in (getattr(response, "follow_ups", None) or []) if not generic(getattr(f, "text", "") or "")]
    for follow in follow_ups:
        if getattr(follow, "text", None):
            follow.text = remove_em_dashes(follow.text)
    response.follow_ups = follow_ups[:3]
    presentation = getattr(response, "presentation", None)
    if presentation is not None and getattr(presentation, "suggestion_chips", None):
        presentation.suggestion_chips = [c for c in presentation.suggestion_chips if not generic(str(getattr(c, "text", c)))][:3]
    return response
