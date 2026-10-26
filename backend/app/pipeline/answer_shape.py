"""One-line answer-shape hint chosen from the task contract. No extra model call."""

from __future__ import annotations

import re

_EMERGENCY = re.compile(
    r"\b(chest pain|trouble breathing|cannot breathe|can't breathe|severe bleeding)\b",
    re.I,
)
_FOLLOW_UP = re.compile(
    r"^(?:why\??|what about (?:mine|me)\??|is that (?:okay|ok|dangerous|bad)\??|tell me more\.?)$",
    re.I,
)
_NUTRITION = re.compile(r"\b(diet|nutrition|what should i eat|food)\b", re.I)
_LIFESTYLE = re.compile(r"\b(sleep|exercise|physical activity|stress|recovery)\b", re.I)

_NOTES = {
    "MARKER_LOOKUP": (
        "State the verified value, unit, date and a short meaning. Do not add a long bullet list."
    ),
    "ABNORMAL_LIST": (
        "Lead with the out-of-range results. Keep each finding to one line. Do not invent a reference range."
    ),
    "BIO_AI_SCORE_LIST": (
        "List the verified scores and categories. Do not turn a score into a disease probability."
    ),
    "PERSONAL_RISK_EXPLANATION": (
        "Start with what the risk finding means in everyday words. Do not add lifestyle advice unless asked."
    ),
    "CROSS_SOURCE_EXPLANATION": (
        "Show the two findings first. Then explain why they can differ. Keep facts separate from possibilities."
    ),
    "SYMPTOM_CONTEXT": (
        "Name relevant possibilities without diagnosing. Use short bullets for supporting findings and say what is uncertain."
    ),
    "PRIORITIZED_CONCERNS": (
        "Use a short numbered list. Give one reason per item. Separate urgent issues from longer-term risk."
    ),
    "DIRECT_ANSWER": (
        "If the answer is one idea, use one short paragraph. If it has several findings, reasons, or factors, use 2 to 4 Markdown bullets written as plain sentences, without bold labels. Never open with Direct answer, Short answer, Measured results, Possible explanations, or What that means. "
    ),
}


_PERSONAL_DIRECT = (
    "A short opening line, then short bullets for separate points, written as plain sentences without bold labels. "
    "One simple idea needs only one or two sentences."
)


def presentation_note(message: str | None, response_type: str | None = None, *, personal: bool = False) -> str:
    text = (message or "").strip()
    if _EMERGENCY.search(text):
        hint = "First sentence is the immediate safety action. No analogy, lifestyle tips, or headings before that action."
    elif _FOLLOW_UP.match(text):
        hint = "One or two sentences. No headings or bullet list."
    elif _NUTRITION.search(text):
        hint = "Answer the food question first, using everyday food names and serving sizes. Use bullets for helpful choices and for what to limit. Do not lead with unrelated labs or change a calculated amount."
    elif _LIFESTYLE.search(text) and response_type in {None, "", "DIRECT_ANSWER"}:
        hint = "Start with the habit the user asked about. Use 3 to 5 plain bullet sentences for the practical points, without bold labels."
    elif personal and (response_type or "DIRECT_ANSWER") == "DIRECT_ANSWER":
        hint = _PERSONAL_DIRECT
    else:
        hint = _NOTES.get(response_type or "DIRECT_ANSWER", _NOTES["DIRECT_ANSWER"])
    return f"PRESENTATION: {hint} No emojis.\n"


_GLUED_HEADING = re.compile(r"([.!?])\s+(\*\*[^*\n]{2,80}\*\*)")
# Only a closing offer, not a question mark inside the explanation.
_CLOSING_OFFER = re.compile(
    r"(?:(?<=[.!:])[ \t]+|\n\n)\[?((?:Would you like|Do you want|Want me to|Shall I|Should I)\b[^\n?\]]{0,300}\?)\]?\s*$",
    re.I,
)
_LIST_ITEM = re.compile(r"^\s*[-*•]\s+")
_INLINE_BULLET = re.compile(r"(?<=\S)[ \t]+([-*•])[ \t]+")


def _detach_closing_question(text: str) -> str:
    """Put a final offer question in its own paragraph, including one glued onto a bullet."""
    match = _CLOSING_OFFER.search(text or "")
    if not match:
        return text
    question = match.group(1).strip()
    head = text[: match.start()].rstrip()
    if not head:
        return text
    return f"{head}\n\n{question}"


def omit_duplicate_closing_offer(text: str, suggestions: list[str]) -> str:
    """Drop a closing offer that is already shown as a separate follow-up chip."""
    match = _CLOSING_OFFER.search(text or "")
    if not match or not suggestions:
        return text
    question = re.sub(r"\s+", " ", match.group(1)).strip().lower().rstrip("?")
    existing = {re.sub(r"\s+", " ", item).strip().lower().rstrip("?") for item in suggestions if item}
    if question not in existing:
        return text
    return text[: match.start()].rstrip()


def separate_answer_layout(text: str) -> str:
    """Put a bold label and a following list on their own lines. Does not rewrite words."""
    if not text:
        return text
    text = _detach_closing_question(text)
    text = _INLINE_BULLET.sub(r"\n\1 ", text)
    if "**" not in text and "\n*" not in text and "\n-" not in text:
        return text
    text = _GLUED_HEADING.sub(r"\1\n\n\2", text)
    text = re.sub(r"(\*\*[^*\n]+\*\*)\s+(\*\s+)", r"\1\n\n\2", text)
    lines = text.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    for line in lines:
        if _LIST_ITEM.match(line) and out and out[-1].strip() and not _LIST_ITEM.match(out[-1]):
            out.append("")
        out.append(line.rstrip())
    return "\n".join(out).strip()
