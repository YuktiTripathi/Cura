"""Backend validation/enrichment of the semantic response.

The answer model decides meaning and hierarchy (summary, which blocks, what they say,
which evidence backs them). This module guarantees data correctness:

* unknown block types and malformed blocks are dropped; at most 4 blocks, 6 items each;
* evidence keys are resolved from the member's normalized health context; a key that
  does not resolve is dropped (the model never supplies a displayed value);
* block text passes the same number-grounding check as the answer: a sentence with a
  number that is not in the member's data is removed;
* deterministic paths (report listing, a plain value lookup) get blocks built from data;
* when safety or validation replaced the model's answer, no model block is shown.

No medical decisions are made here and nothing is invented: a block can only be removed,
never added, except the deterministic data views above.
"""

from __future__ import annotations

import re

from app.contracts.semantic_response import (
    BLOCK_TYPES,
    BlockItem,
    ResolvedValue,
    ResponseBlock,
    ResponseSource,
    SemanticResponse,
)

MAX_BLOCKS = 4
MAX_ITEMS = 6
MAX_VALUES = 4  # conversational blocks; the report view is built separately
_KEY = re.compile(r"^(?:(blood|bioai|bio_ai)\.)?([a-z0-9_]+)(?:\.(latest|trend))?$")
_VALUE_BLOCKS = {"metric", "metric_group", "risk", "comparison"}
_TEXT_BLOCKS = {"text", "insight", "reassurance", "warning"}
_LIST_BLOCKS = {"priority_list", "action_list"}


def _flag(marker) -> str | None:
    flag = getattr(marker, "flag", None)
    return getattr(flag, "value", flag)


def _date(value) -> str | None:
    return str(value)[:10] if value else None


class _Index:
    """Values the backend can vouch for in this turn's context."""

    def __init__(self, context, reports=None):
        self.markers = {m.key: m for m in (getattr(context, "markers", None) or []) if m.key and m.value is not None}
        self.risks = {r.code: r for r in (getattr(context, "bio_ai_risks", None) or []) if r.code}
        self.trends: dict[str, dict] = {}
        for c in getattr(context, "comparisons", None) or []:
            if c.topic and c.current_value is not None:
                self.trends[c.topic] = {"previous": c.previous_value, "latest": c.current_value, "previous_date": _date(c.previous_date),
                                        "date": _date(c.current_date), "direction": c.direction}
        for b in getattr(context, "baselines", None) or []:
            if b.entity and b.latest is not None and b.previous is not None and b.entity not in self.trends:
                self.trends[b.entity] = {"previous": b.previous, "latest": b.latest, "direction": b.direction}

    def resolve(self, key: str, *, want_trend: bool = False) -> ResolvedValue | None:
        match = _KEY.match((key or "").strip().lower())
        if not match:
            return None
        source, code, view = match.groups()
        if source in {"bioai", "bio_ai"} or (source is None and code in self.risks and code not in self.markers):
            risk = self.risks.get(code)
            if risk is None:
                return None
            return ResolvedValue(key=f"bioai.{code}", label=risk.name or code, kind="bio_ai", value=risk.score,
                                 status=risk.status, date=_date(risk.measured_at))
        marker = self.markers.get(code)
        trend = self.trends.get(code)
        if marker is None and trend is None:
            return None
        value = ResolvedValue(
            key=f"blood.{code}.{'trend' if (view == 'trend' or want_trend) and trend else 'latest'}",
            label=(marker.name if marker else code.replace("_", " ")),
            kind="blood",
            value=marker.value if marker else trend["latest"],
            unit=marker.unit if marker else None,
            status=_flag(marker) if marker else None,
            reference_low=marker.reference_low if marker else None,
            reference_high=marker.reference_high if marker else None,
            date=_date(getattr(marker, "measured_at", None)) if marker else trend.get("date"),
        )
        if trend and (view == "trend" or want_trend):
            value.previous = trend["previous"]
            value.previous_date = trend.get("previous_date")
            value.direction = trend.get("direction")
        return value


def _clean_text(text, context) -> str | None:
    """Same treatment as the answer: report ranges win, no internal ids, no unsupported numbers."""
    if not isinstance(text, str) or not text.strip():
        return None
    from app.pipeline.grounding import GroundingChecker
    from app.pipeline.presentation import prefer_report_range, sanitize_internal_ids
    from app.pipeline.validator import _drop_unsupported

    cleaned = sanitize_internal_ids(prefer_report_range(text.strip(), context))
    issues = GroundingChecker().unsupported_number_sentences(cleaned, context)
    if issues:
        cleaned = _drop_unsupported(cleaned, issues)
    return cleaned.strip() or None


def _keys(raw) -> list[str]:
    if isinstance(raw, str):
        raw = [raw]
    return [str(k) for k in raw or [] if isinstance(k, (str, int))][:MAX_VALUES]


def _resolve_all(index: _Index, keys: list[str], *, want_trend: bool = False, only: str | None = None) -> tuple[list[str], list[ResolvedValue]]:
    kept, values, seen = [], [], set()
    for key in keys:
        value = index.resolve(key, want_trend=want_trend)
        if value is None or value.key in seen or (only and value.kind != only):
            continue
        seen.add(value.key)
        kept.append(value.key)
        values.append(value)
    return kept, values


def _strings(raw, limit=8) -> list[str]:
    return [str(x).strip() for x in (raw or []) if isinstance(x, (str, int, float)) and str(x).strip()][:limit]


def validate_block(raw: dict, index: _Index, context) -> ResponseBlock | None:
    kind = str(raw.get("type") or "").strip().lower()
    if kind not in BLOCK_TYPES:
        return None
    title = _clean_text(raw.get("title"), context)
    title = title[:80] if title else None
    text = _clean_text(raw.get("text"), context)
    block = ResponseBlock(type=kind, title=title)
    if kind in _VALUE_BLOCKS:
        evidence, values = _resolve_all(
            index, _keys(raw.get("evidence")), want_trend=kind == "comparison", only="bio_ai" if kind == "risk" else None
        )
        if kind == "comparison":
            values = [v for v in values if v.previous is not None]
            evidence = [v.key for v in values]
        if not values:
            return None
        block.evidence, block.values, block.text = evidence, values[: 1 if kind == "metric" else MAX_VALUES], text
        return block
    if kind in _TEXT_BLOCKS:
        if not text:
            return None
        block.text = text
        block.evidence, block.values = _resolve_all(index, _keys(raw.get("evidence")))
        return block
    if kind in _LIST_BLOCKS:
        items = []
        for item in raw.get("items") or []:
            if isinstance(item, str):
                item = {"title": item}
            if not isinstance(item, dict):
                continue
            item_title = _clean_text(item.get("title"), context)
            item_text = _clean_text(item.get("text"), context)
            if not (item_title or item_text):
                continue
            keys, values = _resolve_all(index, _keys(item.get("evidence")))
            items.append(BlockItem(title=item_title, text=item_text, evidence=keys, values=values))
        if not items:
            return None
        block.items, block.text = items[:MAX_ITEMS], text
        return block
    if kind == "nutrition":
        block.increase, block.reduce = _strings(raw.get("increase")), _strings(raw.get("reduce"))
        block.text = text or _clean_text(raw.get("why_it_matters"), context)
        if not (block.increase or block.reduce):
            return None
        return block
    return None


# ---------------------------------------------------------------- deterministic views

def _report_blocks(index: _Index) -> list[ResponseBlock]:
    values = [index.resolve(f"blood.{key}.latest") for key in index.markers]
    values = [v for v in values if v is not None]
    flagged = [v for v in values if (v.status or "") in {"high", "low", "critical"}]
    blocks = []
    if flagged:
        blocks.append(ResponseBlock(type="metric_group", title="Outside your report's range", values=flagged, evidence=[v.key for v in flagged]))
    if values:
        blocks.append(ResponseBlock(type="metric_group", title=f"All {len(values)} results", values=values,
                                    evidence=[v.key for v in values], collapsed=True))
    return blocks


def _lookup_blocks(index: _Index, context) -> list[ResponseBlock]:
    asked = [k for k in (getattr(context, "display_entity_codes", None) or []) if k in index.markers] or list(index.markers)[:1]
    values = [index.resolve(f"blood.{k}.latest") for k in asked[:4]]
    values = [v for v in values if v is not None]
    if not values:
        return []
    kind = "metric" if len(values) == 1 else "metric_group"
    return [ResponseBlock(type=kind, values=values, evidence=[v.key for v in values])]


def _first_paragraph(text: str) -> str:
    parts = [p.strip() for p in re.split(r"\n\s*\n", text or "") if p.strip()]
    if not parts:
        return ""
    first = parts[0]
    if first.startswith(("-", "*", "1.", "#", "|")):
        return first
    sentences = re.split(r"(?<=[.!?])\s+", first)
    return " ".join(sentences[:3]).strip()


_SOURCE_TYPES = {
    "blood_report": "blood_report", "bio_ai_report": "bio_ai", "bio_ai": "bio_ai", "questionnaire": "questionnaire",
    "uploaded_document": "uploaded_document", "user_uploaded": "uploaded_document",
}
_POINTER = re.compile(r"source pointer:\s*([A-Za-z][\w .&-]{1,40}),\s*(https?://\S+?)\)")


def _sources(response, context) -> list[ResponseSource]:
    seen, out = set(), []
    for item in getattr(response, "evidence", None) or []:
        kind = _SOURCE_TYPES.get(str(getattr(item, "report_type", None) or getattr(item, "source_type", None) or "").lower())
        if not kind:
            continue
        date = _date(getattr(item, "report_date", None))
        if (kind, date) in seen:
            continue
        seen.add((kind, date))
        out.append(ResponseSource(type=kind, date=date))
    for passage in getattr(context, "medical_passages", None) or []:
        for name, _url in _POINTER.findall(passage):
            if ("medical_reference", name) not in seen:
                seen.add(("medical_reference", name))
                out.append(ResponseSource(type="medical_reference", label=name.strip()))
    return out[:8]


def _model_answer_shown(response, llm_result) -> bool:
    """Model blocks are only shown with the model's own answer, never next to a safety or
    validation replacement."""
    if llm_result is None or not (llm_result.answer or "").strip():
        return False
    meta = response.meta
    if getattr(meta, "escalation", None) or getattr(meta, "status", None) in {"safety_block", "clarification_required"}:
        return False
    final, raw = (response.answer or "").strip(), llm_result.answer.strip()
    probe = re.sub(r"\W+", " ", raw[:80]).strip().lower()[:50]
    return bool(probe) and probe in re.sub(r"\W+", " ", final).lower()


def build_semantic_response(response, context, llm_result=None, path: str | None = None) -> SemanticResponse:
    index = _Index(context)
    follow_ups = [f.text for f in (getattr(response, "follow_ups", None) or []) if getattr(f, "text", None)][:3]
    sources = _sources(response, context)
    answer = (response.answer or "").strip()

    if path == "structured_report_overview":
        head = answer.split("\n\n")[0].strip()
        return SemanticResponse(summary=head or answer, blocks=_report_blocks(index), follow_ups=follow_ups, sources=sources)
    if path == "structured_blood":
        return SemanticResponse(summary=answer, blocks=_lookup_blocks(index, context), follow_ups=follow_ups, sources=sources)

    blocks: list[ResponseBlock] = []
    summary = None
    if _model_answer_shown(response, llm_result):
        summary = _clean_text(llm_result.summary, context)
        for raw in llm_result.blocks or []:
            block = validate_block(raw, index, context)
            if block is not None:
                blocks.append(block)
            if len(blocks) >= MAX_BLOCKS:
                break
        goal = ((getattr(context, "semantic_plan", None) or {}).get("primary_goal") or "").upper()
        asked = [k for k in (getattr(context, "display_entity_codes", None) or []) if k in index.markers]
        value_question = getattr(getattr(context, "intent", None), "value", "") == "latest_result" or goal in {"LOOKUP", "ASSESS"}
        if not blocks and value_question and 0 < len(asked) <= 2:
            blocks = _lookup_blocks(index, context)  # "What is my Vitamin D?" / "Is my TSH normal?" show the value
    if not blocks:
        summary = answer  # summary only: the whole conversational answer, nothing hidden
    return SemanticResponse(
        summary=summary or _first_paragraph(answer) or answer,
        blocks=blocks,
        follow_ups=follow_ups,
        sources=sources,
    )
