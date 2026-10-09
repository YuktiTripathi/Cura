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
        "Start with the risk finding. Then a short heading for what it means, what the evidence shows, "
        "and what it does not prove."
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
        "Begin with the direct answer. When there are several ideas, use a meaningful bold heading and concise bullets."
    ),
}


def presentation_note(message: str | None, response_type: str | None = None) -> str:
    text = (message or "").strip()
    if _EMERGENCY.search(text):
        hint = "First sentence is the immediate safety action. No analogy, lifestyle tips, or headings before that action."
    elif _FOLLOW_UP.match(text):
        hint = "One or two sentences. No headings or bullet list."
    elif _NUTRITION.search(text):
        hint = "Answer the food question first. Use bullets for helpful choices and for what to limit. Do not lead with unrelated labs."
    elif _LIFESTYLE.search(text) and response_type in {None, "", "DIRECT_ANSWER"}:
        hint = "Start with the habit the user asked about. Use a short heading and bullets only for the practical points."
    else:
        hint = _NOTES.get(response_type or "DIRECT_ANSWER", _NOTES["DIRECT_ANSWER"])
    return f"PRESENTATION: {hint} No emojis.\n"


_GLUED_HEADING = re.compile(r"([.!?])\s+(\*\*[^*\n]{2,80}\*\*)")
_LIST_ITEM = re.compile(r"^\s*[-*•]\s+")


def separate_answer_layout(text: str) -> str:
    """Put a bold label and a following list on their own lines. Does not rewrite words."""
    if not text or "**" not in text and "\n*" not in text and "\n-" not in text:
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
