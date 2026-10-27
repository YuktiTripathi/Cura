"""Grounded, conversational follow-up questions.

Suggestions follow the way people explore a report:
overview -> concerns -> abnormal results -> connections -> lifestyle -> trends -> future risks -> next steps.

The model's own follow_up_questions come first, after validation against the member's
data. Gaps are filled from the member's findings: real tests, their values, guideline
notes, raised Bio-AI scores and the blood results behind them, and earlier reports.
Nothing here is a fixed list: every question is built from what this member's records
contain and what this conversation has already covered.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.contracts.followup import FollowUpSuggestion

STAGES = (
    "overview",
    "concerns",
    "abnormal",
    "connections",
    "lifestyle",
    "trends",
    "risks",
    "next_steps",
)

# What kind of question a message is, so covered stages are not suggested again.
_STAGE_OF = (
    ("next_steps", re.compile(r"\b(doctor|specialist|retest|re-test|recheck|next steps?|what (?:should|do) i do next|appointment|follow[- ]?up test)\b", re.I)),
    ("trends", re.compile(r"\b(chang\w*|trend|previous|earlier|last (?:report|test)|over time|better|worse|improved|compare)\b", re.I)),
    ("lifestyle", re.compile(r"\b(eat|food|diet|meal|exercise|walk|lifestyle|habit|sleep|lower|raise|reduce|increase|improv(?:e|ing)|bring (?:it|them) (?:down|up))\b", re.I)),
    ("connections", re.compile(r"\b(connect\w*|link\w*|relat\w*|together|because of|caus\w*|explain my .* score|fit)\b", re.I)),
    ("risks", re.compile(r"\b(risk|future|chance|lead to|develop|long[- ]term|score)\b", re.I)),
    ("concerns", re.compile(r"\b(concern\w*|worr\w*|attention|most important|focus|serious|abnormal|wrong)\b", re.I)),
    ("abnormal", re.compile(r"\b(mean|why (?:is|are) my|(?:is|are) my .{1,30}(?:high|low|ok|okay|normal|bad)|explain my)\b", re.I)),
    ("overview", re.compile(r"\b(summar\w*|overall|overview|stands? out|is everything|understand my (?:latest )?(?:blood|bio-?ai)? ?report|go through|how am i doing)\b", re.I)),
)

_UNSAFE = re.compile(
    r"\b(dose|dosage|mg\b|prescri\w*|start taking|stop taking|which (?:medicine|medication|drug)|antibiotic|insulin dose|statin dose)\b",
    re.I,
)
_GENERIC = re.compile(
    r"\b(any (?:new )?(?:symptoms|medications?)|anything else|other questions?|how (?:are|do) you feel|"
    r"tell me more|learn more|what else|more information)\b",
    re.I,
)
# A chip is the member asking Cura. Questions Cura would ask the member ("Would you like a
# plan I can tailor?", "How many minutes can you walk?") belong in the answer, not in chips.
_CURA_VOICE = re.compile(
    r"\b(would you like|do you (?:have|want|take|feel|get|eat|drink|exercise|smoke|sleep|know)|have you|"
    r"are you|did you|were you|will you|can you realistically|how (?:much|many|often|long)\b.{0,30}\byou\b|"
    r"you can|I can|I'll|I will|let me|shall I|should I make)\b",
    re.I,
)
_WORD = re.compile(r"[a-z0-9]+")
_STOP = {
    "my", "i", "the", "a", "an", "is", "are", "of", "to", "do", "does", "what", "how", "should",
    "can", "me", "it", "this", "that", "and", "in", "for", "be", "about", "with", "on", "was",
}
# Lab words a question might name; a named test must be one the member has.
_LAB_WORDS = {
    "hba1c": ("hba1c", "a1c"), "glucose": ("glucose", "blood sugar"), "ldl": ("ldl",), "hdl": ("hdl",),
    "vldl": ("vldl",), "triglycerides": ("triglyceride",), "cholesterol": ("cholesterol",),
    "vitamin_d": ("vitamin d",), "vitamin_b12": ("b12",), "ferritin": ("ferritin",), "tibc": ("tibc",),
    "iron": ("serum iron", "iron level"), "hemoglobin": ("haemoglobin", "hemoglobin"), "mcv": ("mcv",),
    "mch": ("mch",), "rdw": ("rdw",), "creatinine": ("creatinine",), "egfr": ("egfr",), "urea": ("urea",),
    "tsh": ("tsh",), "t4": ("t4",), "t3": ("t3",), "alt": ("alt", "sgpt"), "ast": ("ast", "sgot"),
    "bilirubin": ("bilirubin",), "uric_acid": ("uric acid",), "platelets": ("platelet",),
    "chloride": ("chloride",), "sodium": ("sodium",), "potassium": ("potassium",),
}


@dataclass(frozen=True)
class Finding:
    key: str
    name: str
    value: float | None
    unit: str
    direction: str  # "high" | "low" | "normal"
    theme: str
    note: str | None = None
    urgent: bool = False
    has_history: bool = False

    @property
    def plural(self) -> bool:
        return self.name.lower().endswith(("ides", "cells", "platelets", "lipids"))

    @property
    def label(self) -> str:
        unit = "" if not self.unit else (self.unit if self.unit == "%" else f" {self.unit}")
        return f"{self.name} of {self.value:g}{unit}" if self.value is not None else self.name


@dataclass(frozen=True)
class Risk:
    code: str
    name: str
    score: float
    level: str
    raised: bool
    linked: tuple[str, ...] = ()


@dataclass
class FollowUpBrief:
    findings: list[Finding] = field(default_factory=list)
    risks: list[Risk] = field(default_factory=list)
    covered: set[str] = field(default_factory=set)
    asked: list[str] = field(default_factory=list)
    focus_keys: set[str] = field(default_factory=set)
    shown: list[str] = field(default_factory=list)  # suggested earlier in this conversation
    has_history: bool = False    # an earlier report exists, so change over time can be answered
    has_lifestyle: bool = False  # diet, activity, sleep or symptom answers are on record

    @property
    def data_kind(self) -> str:
        """Which verified sources exist: none, blood, bio or both."""
        if self.findings and self.risks:
            return "both"
        return "blood" if self.findings else "bio" if self.risks else "none"

    def prompt_json(self, *, bio_only: bool = False) -> dict:
        """What the model sees when writing follow_up_questions. A Bio-AI question lists
        only the scores and the blood tests linked to them."""
        return {
            "stages_in_order": list(STAGES),
            "stages_already_covered": [s for s in STAGES if s in self.covered],
            "already_asked": self.asked[-6:],
            "already_suggested": self.shown[-6:],
            # Names and directions only: values stay in the verified evidence, stated once.
            "findings": [
                {"test": f.name, "direction": f.direction,
                 "guideline_range_reached": bool(f.note) or None, "see_doctor_soon": f.urgent or None,
                 "earlier_report_available": f.has_history or None}
                for f in self.findings[:6] if f.direction != "normal" and not bio_only
            ],
            "bio_ai_scores": [
                {"assessment": r.name, "level": r.level, "raised": r.raised,
                 "related_blood_tests": [re.sub(r"\s+[\d.].*$", "", x) for x in r.linked] or None}
                for r in self.risks[:5]
            ],
        }


# ---------------------------------------------------------------------------- building the brief

def _short_name(name: str) -> str:
    from app.pipeline.report_explainer import _display_name

    name = _display_name(re.sub(r"\s*\([^)]*\)", "", name or "").strip())
    name = re.sub(r"\b(calculated|total[- ]25 hydroxy|mean platelet count|serum)\b", "", name, flags=re.I)
    name = re.sub(r"\s+", " ", name).strip()
    # Keep acronyms (LDL, HbA1c, MCV); lower-case ordinary words mid-sentence ("triglycerides").
    words = [w if re.search(r"[A-Z].*[A-Z]|\d", w) or (len(w) == 1 and w.isupper()) else w.lower() for w in name.split()]
    return " ".join(words)


def stage_of(text: str | None) -> str | None:
    for stage, pattern in _STAGE_OF:
        if pattern.search(text or ""):
            return stage
    return None


def build_brief(
    *,
    markers=(),
    risks=(),
    comparisons=(),
    history_keys: set[str] | None = None,
    asked: list[str] | None = None,
    focus_keys: set[str] | None = None,
    shown: list[str] | None = None,
    has_lifestyle: bool = False,
) -> FollowUpBrief:
    from app.pipeline.clinical_thresholds import clinical_note
    from app.pipeline.report_explainer import _concern, _CONCERN, _out_of_range, _theme, _dedupe, related_blood_results

    history = set(history_keys or set()) | {str(getattr(c, "topic", "")) for c in comparisons or []}
    findings: list[Finding] = []
    for marker in _dedupe([m for m in markers if getattr(m, "value", None) is not None]):
        flag = str(getattr(marker.flag, "value", marker.flag) or "").lower()
        direction = "high" if "high" in flag else "low" if "low" in flag else "normal"
        note = clinical_note(marker) if _out_of_range(marker) else None
        findings.append(Finding(
            key=marker.key, name=_short_name(marker.name), value=marker.value, unit=marker.unit or "",
            direction=direction, theme=_theme(marker).code, note=note.text if note else None,
            urgent=bool(note and note.urgent), has_history=marker.key in history,
        ))
    order = [t for t in ("sugar", "lipids", "iron", "liver", "kidney", "thyroid", "vitamins", "cells", "other")]
    findings.sort(key=lambda f: (
        f.direction == "normal", not f.urgent, f.note is None,
        order.index(f.theme) if f.theme in order else len(order),
    ))
    risk_rows: list[Risk] = []
    for risk in risks or []:
        if getattr(risk, "score", None) is None:
            continue
        raised = _concern(risk.status) < len(_CONCERN)
        linked = tuple(related_blood_results(risk, list(markers)))
        risk_rows.append(Risk(risk.code, risk.name, risk.score, (risk.status or "").lower(), raised, linked))
    risk_rows.sort(key=lambda r: (not r.raised, -r.score))
    covered = {s for s in (stage_of(q) for q in asked or []) if s}
    return FollowUpBrief(findings=findings, risks=risk_rows, covered=covered,
                         asked=list(asked or []), focus_keys=set(focus_keys or set()),
                         shown=list(shown or []),
                         has_history=bool(history) or any(f.has_history for f in findings),
                         has_lifestyle=has_lifestyle)


# ---------------------------------------------------------------------------- candidates

# Tests that food and daily habits move directly; cell-size indices (MCV, MCH, RDW) follow iron.
_LIFESTYLE_KEYS = re.compile(
    r"hba1c|glucose|sugar|ldl|hdl|vldl|triglycer|cholesterol|vitamin|b12|ferritin|iron|ha?emoglobin|uric|alt|sgpt",
    re.I,
)


def _lifestyle_moves(f: "Finding") -> bool:
    return bool(_LIFESTYLE_KEYS.search(f"{f.key} {f.name}"))


def _candidates(brief: FollowUpBrief) -> list[tuple[str, str, int]]:
    """(question, stage, priority) built from this member's findings. Higher priority first."""
    out: list[tuple[str, str, int]] = []
    flagged = [f for f in brief.findings if f.direction != "normal"]
    top = flagged[:3]
    raised = [r for r in brief.risks if r.raised]

    def boost(f: Finding) -> int:
        return (40 if f.urgent else 20 if f.note else 0) + (25 if f.key in brief.focus_keys else 0)

    normal = [f for f in brief.findings if f.direction == "normal"]
    if not flagged and not raised and normal:
        out.append(("Is everything in my report in the healthy range?", "overview", 6))
        for f in normal[:2]:
            if _lifestyle_moves(f):
                out.append((f"How can I keep my {f.name} in a healthy range?", "lifestyle", 6))
        out.append(("When should I get my next blood test?", "next_steps", 5))
        out.append(("Which other tests would give a fuller picture of my health?", "next_steps", 4))
    if flagged or raised:
        out.append(("What stands out most in my results?", "overview", 5))
        out.append(("Which of my results should I focus on first?", "concerns", 12 if len(flagged) > 2 else 4))
    for f in top:
        word = "high" if f.direction == "high" else "low"
        if f.urgent:
            out.append((f"How serious is my {f.label}?", "concerns", 30 + boost(f)))
        out.append((f"Why {'are' if f.plural else 'is'} my {f.name} {word}?", "abnormal", 10 + boost(f)))
        out.append((f"What does a {f.label} mean for me?", "abnormal", 8 + boost(f)))
        if _lifestyle_moves(f):
            verb = "lower" if f.direction == "high" else "raise"
            out.append((f"What can I eat to {verb} my {f.name}?", "lifestyle", 8 + boost(f)))
            out.append((f"Which habits would help my {f.name} most?", "lifestyle", 6 + boost(f)))
        if f.has_history:
            out.append((f"{'Have' if f.plural else 'Has'} my {f.name} changed since my last report?", "trends", 9 + boost(f)))
        if f.urgent:
            out.append((f"Should I see a doctor about my {f.name}?", "next_steps", 28 + boost(f)))
            out.append((f"What could happen if my {f.name} stays this {word}?", "risks", 14 + boost(f)))
        elif f.note:
            out.append((f"When should I recheck my {f.name}?", "next_steps", 10 + boost(f)))
    # Pairs in the same body system: the connections people want explained.
    for i, a in enumerate(flagged[:5]):
        for b in flagged[i + 1:5]:
            if a.theme == b.theme and a.key != b.key:
                out.append((f"Are my {a.direction} {a.name} and {b.direction} {b.name} connected?", "connections",
                            12 + (25 if a.key in brief.focus_keys or b.key in brief.focus_keys else 0)))
                break
    for r in raised[:3]:
        if r.linked:
            lead = r.linked[0].split(" (")[0]
            test = _short_name(re.sub(r"\s+[\d.]+.*$", "", lead))
            out.append((f"Is my {test} linked to my {r.name} score?", "connections", 18))
        out.append((f"What does my {r.name} score of {r.score:g} mean for my future?", "risks", 12))
        out.append((f"How can I bring my {r.name} score down?", "lifestyle", 9))
    if raised and not any(q[1] == "next_steps" for q in out):
        out.append((f"Which Bio-AI score should I discuss with my doctor first?", "next_steps", 8))
    if flagged and not any(q[1] == "next_steps" for q in out):
        out.append(("Which of these results should I discuss with my doctor?", "next_steps", 6))
    if any(f.has_history for f in brief.findings) and not any(q[1] == "trends" for q in out):
        out.append(("What has changed since my last report?", "trends", 6))
    if not brief.has_history and (flagged or raised):
        # Nothing to compare with: point forward instead of backward.
        out.append(("What should I focus on improving?", "trends", 9))  # takes the place of trend questions
    if not brief.has_lifestyle and (flagged or raised):
        # Ask for the context rather than assume it.
        out.append(("Can I tell you about my diet and activity?", "lifestyle", 3))
    return out


# ---------------------------------------------------------------------------- validation

def _tokens(text: str) -> set[str]:
    return {w for w in _WORD.findall((text or "").lower()) if w not in _STOP}


def _similar(a: str, b: str) -> bool:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return False
    return len(ta & tb) / max(1, min(len(ta), len(tb))) >= 0.75


_ACRONYM = re.compile(r"\b[A-Z][A-Z0-9]{1,4}\b")
_NOT_TESTS = {"AI", "BIO", "OK", "I", "BMI", "BP"}


def _named_tests_present(text: str, brief: FollowUpBrief) -> bool:
    from app.pipeline.lab_parameters import match_lab_keys

    low = (text or "").lower()
    present_keys = {f.key for f in brief.findings}
    names_blob = " ".join(f"{f.key} {f.name}".lower() for f in brief.findings)
    for key in match_lab_keys(text or ""):
        if key and key not in present_keys and key.replace("_", " ") not in names_blob:
            if not (key == "glucose" and any("glucose" in k for k in present_keys)):
                return False
    for code in _ACRONYM.findall(text or ""):
        if code not in _NOT_TESTS and code.lower() not in names_blob:
            return False
    have = " ".join(f"{f.key} {f.name}".lower() for f in brief.findings)
    have_norm = re.sub(r"[^a-z0-9]+", "", have)
    for key, words in _LAB_WORDS.items():
        if any(re.search(rf"\b{re.escape(w)}\b", low) for w in words):
            if key.replace("_", "") not in have_norm and not any(w.replace(" ", "") in have_norm for w in words):
                return False
    from app.pipeline.answer_polish import _ASSESSMENTS

    present = " ".join(f"{r.code} {r.name}".lower() for r in brief.risks)
    for code, names in _ASSESSMENTS.items():
        if any(re.search(rf"\b{re.escape(n)}\b", low) for n in names):
            if code.replace("_", " ") not in present.replace("_", " ") and not any(n in present for n in names):
                return False
    # Standalone numbers only: the digits in "HbA1c" or "B12" are part of a name.
    numbers = re.findall(r"(?<![A-Za-z\d.])\d+(?:\.\d+)?(?![A-Za-z\d])", text or "")
    known = {f"{f.value:g}" for f in brief.findings if f.value is not None} | {f"{r.score:g}" for r in brief.risks}
    known |= {"2", "3", "6", "12"}  # durations such as "3 months"
    return all(f"{float(n):g}" in known for n in numbers)


def is_member_question(text: str) -> bool:
    """A clickable chip must be something the member would ask Cura, not a question Cura asks them."""
    q = (text or "").strip()
    if not q:
        return False
    return not (_CURA_VOICE.search(q) or _GENERIC.search(q))


def valid_question(text: str, brief: FollowUpBrief, *, current: str | None = None, chosen: list[str] = ()) -> bool:
    q = (text or "").strip()
    if not q.endswith("?") or len(q) > 90 or len(q.split()) > 12 or len(q.split()) < 3:
        return False
    if _UNSAFE.search(q) or _GENERIC.search(q) or _CURA_VOICE.search(q):
        return False
    for seen in [*(brief.asked or []), *(brief.shown or []), *([current] if current else []), *chosen]:
        if seen and _similar(q, seen):
            return False
    return _named_tests_present(q, brief) and _fits_available_data(q, brief)


_BIO_WORDS = re.compile(r"\b(bio-?ai|scores?|risk estimates?)\b", re.I)
_RESULT_WORDS = re.compile(
    r"\b(blood (?:test|report|results?)|lab(?:s| results?)?|biomarkers?|my results|my report)\b", re.I
)
_ASSUMED_LIFESTYLE = re.compile(
    r"\bmy (?:poor |bad |low |high |current |daily )?(?:diet|sleep|exercise|activity|stress|symptoms?|"
    r"smoking|drinking|alcohol|weight)\b",
    re.I,
)
_ASKS_TO_SHARE = re.compile(r"\b(share|tell you|give you|add)\b", re.I)


def _fits_available_data(q: str, brief: FollowUpBrief) -> bool:
    """Cura must be able to answer it from what is on record (critical rule 4)."""
    if not brief.risks and _BIO_WORDS.search(q):
        return False  # no Bio-AI report: no scores or risk estimates to talk about
    if not brief.findings and _RESULT_WORDS.search(q) and brief.data_kind != "none":
        return False  # Bio-AI only: there are no blood values to discuss
    if not brief.has_history and stage_of(q) == "trends":
        return False  # no earlier report to compare with
    if not brief.has_lifestyle and _ASSUMED_LIFESTYLE.search(q) and not _ASKS_TO_SHARE.search(q):
        return False  # do not assume diet, sleep or symptoms that are not on record
    return True


# Small, clinically safe sets for when nothing personal fits or the model is unavailable.
# Each still passes the same checks, so a set never names data the member does not have.
FALLBACK = {
    "none": (
        "How can I improve my overall health?",
        "What health checks should I consider?",
        "What does a routine blood test usually check?",
        "How much exercise do I need each week?",
    ),
    "blood": (
        "Which of my results should I focus on first?",
        "What should I focus on improving?",
        "Which of these results should I discuss with my doctor?",
        "When should I get my next blood test?",
    ),
    "bio": (
        "Which of my Bio-AI scores deserve attention?",
        "What can I do to lower my highest risk score?",
        "Which score should I discuss with my doctor first?",
    ),
    "both": (
        "Which of my results should I focus on first?",
        "How do my blood results relate to my Bio-AI scores?",
        "What should I focus on improving?",
        "Which of these results should I discuss with my doctor?",
    ),
    "unreadable": (
        "Can I upload a clearer copy of my report?",
        "Which results could you read from my report?",
        "What should a complete blood report include?",
    ),
}


def fallback_questions(
    brief: FollowUpBrief, *, count: int = 3, current: str | None = None, chosen: list[str] = (), kind: str | None = None,
) -> list[str]:
    out: list[str] = []
    for text in FALLBACK[kind or brief.data_kind]:
        if len(out) + len(chosen) >= count:
            break
        if valid_question(text, brief, current=current, chosen=[*chosen, *out]):
            out.append(text)
    return out


# ---------------------------------------------------------------------------- selection

def _stage_weight(stage: str, brief: FollowUpBrief, current_stage: str | None) -> int:
    if stage in brief.covered or stage == current_stage:
        return -30
    idx = STAGES.index(stage)
    if current_stage in STAGES:
        ahead = idx - STAGES.index(current_stage)
        return 20 - 4 * ahead if ahead > 0 else 2  # the next step in the journey first
    return 10 - idx


def select_followups(
    brief: FollowUpBrief,
    *,
    current_question: str | None,
    model_questions: list[str] | None = None,
    count: int = 3,
) -> list[str]:
    current_stage = stage_of(current_question)
    if current_question:
        from app.pipeline.lab_parameters import match_lab_keys

        # The test the member is asking about now: its next questions come first.
        brief.focus_keys |= {k for k in match_lab_keys(current_question) if k}
    chosen: list[str] = []
    stages_used: set[str] = set()
    for text in model_questions or []:
        text = re.sub(r"\s+", " ", (text or "").strip())
        if valid_question(text, brief, current=current_question, chosen=chosen):
            chosen.append(text)
            stages_used.add(stage_of(text) or "")
        if len(chosen) >= count:
            return chosen
    ranked = sorted(
        _candidates(brief),
        key=lambda c: -(c[2] + _stage_weight(c[1], brief, current_stage)),
    )
    per_test: dict[str, int] = {}
    focus_names = {f.name for f in brief.findings if f.key in brief.focus_keys}
    for allow_covered in (False, True):
        for text, stage, _priority in ranked:
            if len(chosen) >= count:
                break
            if stage in stages_used or stage == current_stage:
                continue  # the answer just covered this kind of question
            if stage in brief.covered and not allow_covered:
                continue  # earlier steps come back only when nothing new is left
            subject = next((f.name for f in brief.findings if f.name in text), text)
            if per_test.get(subject, 0) >= (2 if subject in focus_names else 1):
                continue
            if not valid_question(text, brief, current=current_question, chosen=chosen):
                continue
            chosen.append(text)
            stages_used.add(stage)
            per_test[subject] = per_test.get(subject, 0) + 1
    if len(chosen) < min(2, count):
        chosen += fallback_questions(brief, count=count, current=current_question, chosen=chosen)
    return chosen


def to_suggestions(questions: list[str], *, personal: bool = True) -> list[FollowUpSuggestion]:
    return [
        FollowUpSuggestion(
            text=q,
            category=f"journey_{stage_of(q) or 'next'}",
            requires_personal_context=personal,
            knowledge_scope="personal" if personal else "general",
            handling_path="CONTINUE_INTERPRETATION",
        )
        for q in questions
    ]


def document_followups(facts, *, message: str | None, count: int = 3) -> list[FollowUpSuggestion]:
    """Grounded follow-ups for an uploaded report, from its extracted values."""
    from app.contracts.blood import BloodMarker

    markers = []
    for fact in facts or []:
        if not isinstance(getattr(fact, "value", None), (int, float)):
            continue
        status = (getattr(fact, "status", "") or "").lower()
        flag = status if status in {"high", "low", "critical", "normal"} else "unknown"
        markers.append(BloodMarker(
            id=fact.canonical_code or fact.display_name, key=fact.canonical_code or fact.display_name.lower(),
            name=fact.display_name, value=float(fact.value), unit=fact.unit, flag=flag,
            reference_low=fact.reference_low, reference_high=fact.reference_high,
        ))
    if not markers:
        # Nothing could be read as a measurement: say what can be done next.
        return [
            item.model_copy(update={"source": "user_uploaded"})
            for item in to_suggestions(fallback_questions(FollowUpBrief(), count=count, current=message, kind="unreadable"))
        ]
    brief = build_brief(markers=markers)
    return [
        item.model_copy(update={"source": "user_uploaded"})
        for item in to_suggestions(select_followups(brief, current_question=message, count=count))
    ]
