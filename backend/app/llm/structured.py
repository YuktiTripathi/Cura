"""Parse medical-LLM payloads into Cura's structured contract without leaking raw JSON."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.contracts.recommendation import RecommendationCandidate
from app.llm.models import LLMClaim, LLMStructuredOutput

logger = logging.getLogger("cura.llm.structured")

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.I)
_ANSWER_STRING = re.compile(r'"answer"\s*:\s*"((?:\\.|[^"\\])*)"', re.I)
_SCHEMA_KEYS = {
    "answer",
    "claims",
    "recommendation_candidates",
    "follow_up_questions",
    "safety_flags",
    "escalation",
}


def looks_like_structured_json(text: str) -> bool:
    stripped = (text or "").strip()
    if not stripped.startswith("{"):
        return False
    return any(f'"{key}"' in stripped for key in _SCHEMA_KEYS)


def public_answer_text(value: Any) -> str:
    parsed = parse_llm_structured(value)
    return parsed.answer


def parse_llm_structured(payload: Any) -> LLMStructuredOutput:
    obj, leftover_text = _to_object(payload)
    parse_error = None
    if obj is None:
        text = leftover_text.strip()
        if looks_like_structured_json(text):
            extracted = _regex_answer(text)
            if not extracted:
                parse_error = "unreadable_structured_payload"
                logger.error(
                    "llm_structured_output_contract_violation parse_error=%s payload_type=%s",
                    parse_error,
                    type(payload).__name__,
                )
            return LLMStructuredOutput(answer=extracted or _unreadable_fallback(), parse_error=parse_error)
        return LLMStructuredOutput(answer=text)

    answer, parse_error = _unwrap_answer(obj.get("answer"))
    if parse_error:
        logger.error(
            "llm_structured_output_contract_violation parse_error=%s answer_type=%s",
            parse_error,
            type(obj.get("answer")).__name__,
        )
    if not answer:
        if leftover_text and not looks_like_structured_json(leftover_text):
            answer = leftover_text.strip()
        else:
            extracted = _regex_answer(str(payload))
            if extracted:
                answer = extracted
            else:
                if not parse_error:
                    parse_error = "empty_or_non_string_answer"
                    logger.error(
                        "llm_structured_output_contract_violation parse_error=%s payload_type=%s",
                        parse_error,
                        type(payload).__name__,
                    )
                answer = _unreadable_fallback()

    return LLMStructuredOutput(
        answer=answer,
        claims=_parse_claims(obj.get("claims")),
        recommendation_candidates=_parse_recommendations(obj.get("recommendation_candidates")),
        follow_up_questions=_parse_strings(obj.get("follow_up_questions")),
        safety_flags=_parse_strings(obj.get("safety_flags")),
        escalation=_parse_escalation(obj.get("escalation")),
        parse_error=parse_error,
        overall_summary=_parse_optional_text(obj.get("overall_summary")),
        themes=_parse_themes(obj.get("themes")),
        summary=_parse_optional_text(obj.get("summary")),
        blocks=[b for b in obj.get("blocks") or [] if isinstance(b, dict)][:8] if isinstance(obj.get("blocks"), list) else [],
    )


def _unreadable_fallback() -> str:
    return ""


def _to_object(payload: Any) -> tuple[dict[str, Any] | None, str]:
    if payload is None:
        return None, ""
    if isinstance(payload, LLMStructuredOutput):
        return payload.model_dump(), payload.answer
    if isinstance(payload, dict):
        inner = payload.get("answer")
        if isinstance(inner, dict) and _SCHEMA_KEYS & inner.keys():
            return inner, ""
        return payload, ""
    if not isinstance(payload, str):
        return None, str(payload)
    text = _FENCE.sub("", payload.strip()).strip()
    if not text:
        return None, ""
    try:
        loaded = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            try:
                loaded = json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return None, text
        else:
            return None, text
    if isinstance(loaded, str):
        return _to_object(loaded)
    if isinstance(loaded, dict):
        inner = loaded.get("answer")
        if isinstance(inner, dict) and _SCHEMA_KEYS & inner.keys():
            return inner, ""
        if isinstance(inner, str) and inner.strip().startswith("{"):
            nested, _ = _to_object(inner)
            if nested:
                return nested, ""
        return loaded, ""
    return None, text


def _unwrap_answer(value: Any, depth: int = 0) -> tuple[str, str | None]:
    if depth > 3:
        return "", "unwrap_depth_exceeded"
    if value is None:
        return "", None
    if isinstance(value, dict):
        if "answer" in value:
            return _unwrap_answer(value.get("answer"), depth + 1)
        return "", f"non_string_answer:{type(value).__name__}"
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("{") and "answer" in stripped:
            obj, leftover = _to_object(stripped)
            if obj and "answer" in obj:
                return _unwrap_answer(obj.get("answer"), depth + 1)
            if leftover and not looks_like_structured_json(leftover):
                return leftover, None
            return "", "nested_non_string_answer"
        return stripped, None
    if isinstance(value, (list, tuple, dict)):
        return "", f"non_string_answer:{type(value).__name__}"
    return "", f"non_string_answer:{type(value).__name__}"


def _regex_answer(text: str) -> str:
    match = _ANSWER_STRING.search(text or "")
    if not match:
        return ""
    raw = match.group(1)
    try:
        return json.loads(f'"{raw}"')
    except json.JSONDecodeError:
        return raw.replace('\\"', '"').replace("\\n", "\n")


def _parse_claims(raw: Any) -> list[LLMClaim]:
    if not raw:
        return []
    if not isinstance(raw, list):
        raw = [raw]
    out: list[LLMClaim] = []
    for item in raw:
        if isinstance(item, str) and item.strip():
            out.append(LLMClaim(text=item.strip()))
        elif isinstance(item, dict):
            text = str(item.get("text") or item.get("claim") or "").strip()
            codes = item.get("evidence_codes") or item.get("codes") or []
            if not isinstance(codes, list):
                codes = []
            if text:
                out.append(LLMClaim(text=text, evidence_codes=[str(c) for c in codes]))
    return out


def _parse_recommendations(raw: Any) -> list[RecommendationCandidate]:
    if not isinstance(raw, list):
        return []
    out: list[RecommendationCandidate] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            out.append(RecommendationCandidate.model_validate(item))
        except (ValueError, TypeError):
            continue
    return out


def _parse_strings(raw: Any) -> list[str]:
    if not raw:
        return []
    if isinstance(raw, str):
        return [raw.strip()] if raw.strip() else []
    if not isinstance(raw, list):
        return []
    return [str(item).strip() for item in raw if str(item).strip()]


def _parse_optional_text(raw: Any) -> str | None:
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def _parse_themes(raw: Any) -> list[dict]:
    if not isinstance(raw, list):
        return []
    out: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        interpretation = str(item.get("interpretation") or "").strip()
        if not title or not interpretation:
            continue
        ids = item.get("supporting_fact_ids") or []
        if not isinstance(ids, list):
            ids = []
        missing = item.get("missing_information") or []
        if not isinstance(missing, list):
            missing = []
        out.append(
            {
                "title": title,
                "priority": str(item.get("priority") or "medium"),
                "status": str(item.get("status") or "monitor"),
                "supporting_fact_ids": [str(code) for code in ids if str(code).strip()],
                "interpretation": interpretation,
                "missing_information": [str(row).strip() for row in missing if str(row).strip()],
                "next_step": str(item.get("next_step") or "").strip(),
            }
        )
    return out[:5]


def _parse_escalation(raw: Any) -> str | None:
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None
