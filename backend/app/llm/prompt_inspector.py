"""Development-only view of exactly what an answer-model call sends (observability only).

Hooked into ``OpenAICompatibleLLMClient._post_once`` — the single place every answer
model (Gemini 3.8 Flash, GPT-5 mini, GPT-5.6 Luna; all via OpenRouter
``/chat/completions``) receives its request. It never changes the request.

Enabled only when ``CURA_PROMPT_DEBUG=true`` AND the app is not in production. Then, per
call, it:
  * splits the real payload into logical components (system prompt, application
    instructions, health context with blood / Bio-AI / questionnaire / profile / previous
    values, conversation, medical-evidence instructions, response-format instructions,
    output contract, current question, response_format schema, request parameters);
  * counts characters and tokens per component (tiktoken ``o200k_base`` when it can be
    loaded, otherwise an estimate of chars/4, labelled as such);
  * after the call, adds the provider-reported input/output tokens and latency;
  * writes a readable sectioned dump and a JSON record to ``CURA_PROMPT_DEBUG_DIR``.

The dump contains the member's health values: it is for local development only and is
never produced in production (``settings.is_development`` gate).
"""

from __future__ import annotations

import json
import logging
import re
import time
from collections import deque
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger("cura.prompt_debug")

RECENT: deque = deque(maxlen=50)  # last audits in this process (dev tooling reads these)

_ENCODER = None
_ENCODER_TRIED = False


def enabled() -> bool:
    return bool(settings.cura_prompt_debug) and settings.is_development


def _encoder():
    global _ENCODER, _ENCODER_TRIED
    if not _ENCODER_TRIED:
        _ENCODER_TRIED = True
        try:
            import tiktoken  # optional dev dependency

            _ENCODER = tiktoken.get_encoding("o200k_base")
        except Exception:  # noqa: BLE001 - not installed or encoding file unavailable
            _ENCODER = None
    return _ENCODER


def token_method() -> str:
    return "tiktoken:o200k_base" if _encoder() is not None else "estimate:chars/4"


def count_tokens(text: str) -> int:
    enc = _encoder()
    if enc is not None:
        return len(enc.encode(text or ""))
    return (len(text or "") + 3) // 4


def _size(text: str) -> dict:
    return {"chars": len(text or ""), "tokens": count_tokens(text or "")}


# ---------------------------------------------------------------- message splitting

# System prompt: headed sections. RESPONSE PLANNING is format guidance; the trailing
# "Return a JSON object ..." block is the output contract.
_SYSTEM_FORMAT_HEADINGS = {"RESPONSE PLANNING"}
_HEADING = re.compile(r"^([A-Z][A-Z /()-]{3,})(?:\s*\(.*\))?$")

# User message: each line belongs to the component of the last recognised prefix.
_USER_PREFIXES: tuple[tuple[str, str], ...] = (
    ("User question:", "current_query"),
    ("Conversation focus", "conversation"),
    ("Routing (not medical evidence)", "routing_note"),
    ("ANSWER EVIDENCE JSON:", "health_context"),
    ("PERSONAL HEALTH CONTEXT JSON:", "health_context"),
    ("PERSONAL BLOOD DATA", "health_context"),
    ("QUESTIONNAIRE RESPONSES JSON", "health_context"),
    ("BIO-AI DATA JSON", "health_context"),
    ("DERIVED FACTS JSON", "health_context"),
    ("USER_STATED_HEALTH_INFORMATION JSON", "health_context"),
    ("USER PROFILE/GOALS JSON", "health_context"),
    ("USER_PROVIDED_DATA_AND_PREFERENCES JSON", "health_context"),
    ("PERSONAL_HEALTH_TIMELINE JSON", "health_context"),
    ("GOAL_PROGRESS JSON", "health_context"),
    ("SOURCE CONFLICTS JSON", "health_context"),
    ("MODEL_INTERPRETATION and MODEL_RECOMMENDATION", "application_instructions"),
    ("If SOURCE CONFLICTS are present", "application_instructions"),
    ("No medical evidence was retrieved", "medical_evidence"),
    ("RETRIEVED SOURCE POINTERS", "medical_evidence"),
    ("HIGH RISK TOPIC", "medical_evidence"),
    ("LOW RISK EDUCATION", "medical_evidence"),
    ("Answer depth:", "response_format_instructions"),
    ("Depth:", "response_format_instructions"),
    ("RESPONSE BRIEF:", "response_format_instructions"),
    ("The Bio-AI scores are already shown", "response_format_instructions"),
    ("Topic:", "application_instructions"),
)


def _split_system(text: str) -> dict[str, str]:
    parts = {"system_prompt": [], "response_format_instructions": [], "output_contract": []}
    current = "system_prompt"
    for line in (text or "").splitlines(keepends=True):
        stripped = line.strip()
        if stripped.startswith("Return a JSON object"):
            current = "output_contract"
        elif _HEADING.match(stripped):
            current = "response_format_instructions" if stripped.split(" (")[0] in _SYSTEM_FORMAT_HEADINGS else "system_prompt"
        parts[current].append(line)
    return {k: "".join(v) for k, v in parts.items()}


def _split_user(text: str) -> dict[str, str]:
    parts: dict[str, list[str]] = {}
    current = "application_instructions"
    for line in (text or "").splitlines(keepends=True):
        stripped = line.strip()
        for prefix, component in _USER_PREFIXES:
            if stripped.startswith(prefix):
                current = component
                break
        parts.setdefault(current, []).append(line)
    return {k: "".join(v) for k, v in parts.items()}


# ---------------------------------------------------------------- health-context breakdown

_EVIDENCE_GROUPS = {
    # answer-evidence payload (personal answers)
    "primary_facts": "facts", "supporting_facts": "facts",
    "checked_and_within_range": "blood", "patterns": "blood", "other_notable_findings": "blood",
    "reassuring_systems": "blood", "reassuring_groups": "blood", "checked_without_concern": "blood",
    "trend": "previous_reports", "comparisons": "previous_reports",
    "questionnaire_context": "questionnaire", "already_doing": "questionnaire",
    "personalization_context": "profile", "profile": "profile", "personalization": "profile", "goals": "profile",
    "next_steps": "recommendations", "approved_recommendations": "recommendations",
    "already_explained_in_this_conversation": "conversation",
    # minimal-context payload (older personal path)
    "markers": "blood", "bio_ai_risks": "bio_ai", "questionnaire": "questionnaire", "lifestyle": "questionnaire",
    "facts": "facts", "health_story": "profile",
}


def _health_json(component_text: str) -> dict | None:
    for line in component_text.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except ValueError:
                return None
    return None


def _is_bio(fact: dict) -> bool:
    return "score" in fact or "Bio-AI" in str(fact.get("source") or "")


def _fact_label(fact: dict) -> str:
    code = fact.get("code") or fact.get("key") or fact.get("name") or "?"
    if "value" in fact:
        return f"{code}={fact.get('value')}{(' ' + fact['unit']) if fact.get('unit') else ''} ({fact.get('status') or fact.get('flag') or '-'})"
    if "score" in fact:
        return f"{code}={fact.get('score')} ({fact.get('status') or '-'})"
    return str(code)


def health_breakdown(payload: dict) -> dict:
    """Split the health-context JSON into blood / Bio-AI / questionnaire / profile /
    previous reports / conversation / meta, with sizes and the exact items included."""
    groups: dict[str, list[tuple[str, object]]] = {}
    for key, value in payload.items():
        groups.setdefault(_EVIDENCE_GROUPS.get(key, "evidence_meta"), []).append((key, value))
    # Facts are split by source.
    facts = [v for k, v in groups.pop("facts", [])]
    blood_facts, bio_facts = [], []
    for block in facts:
        for fact in block if isinstance(block, list) else []:
            (bio_facts if isinstance(fact, dict) and _is_bio(fact) else blood_facts).append(fact)
    if blood_facts:
        groups.setdefault("blood", []).insert(0, ("facts(measured)", blood_facts))
    if bio_facts:
        groups.setdefault("bio_ai", []).insert(0, ("facts(bio_ai)", bio_facts))

    out: dict = {}
    for group, items in groups.items():
        text = json.dumps(dict(items), ensure_ascii=False, separators=(",", ":"), default=str)
        out[group] = {**_size(text), "keys": [k for k, _ in items]}

    blood_items: list[str] = []
    for fact in blood_facts:
        blood_items.append(_fact_label(fact) + " [fact]")
    for key in ("checked_and_within_range", "other_notable_findings"):
        for item in payload.get(key) or []:
            blood_items.append(f"{item if isinstance(item, str) else _fact_label(item)} [{key}]")
    for pattern in payload.get("patterns") or []:
        for fact in pattern.get("out_of_range") or []:
            blood_items.append(f"{_fact_label(fact)} [pattern:{pattern.get('pattern')}]")
        for name in pattern.get("in_range_in_same_system") or []:
            blood_items.append(f"{name} (in range) [pattern:{pattern.get('pattern')}]")
    for row in payload.get("reassuring_systems") or payload.get("reassuring_groups") or []:
        names = row.get("in_range") or row.get("within_range") or []
        blood_items.append(f"{row.get('system') or row.get('area')}: {', '.join(map(str, names))} [reassuring]")
    for marker in payload.get("markers") or []:
        blood_items.append(_fact_label(marker) + " [markers]")
    bio_items = [_fact_label(f) for f in bio_facts] + [_fact_label(r) for r in payload.get("bio_ai_risks") or []]
    for pattern in payload.get("patterns") or []:
        for risk in pattern.get("related_bio_ai") or []:
            bio_items.append(f"{risk.get('name')} ({risk.get('status')}) [pattern:{pattern.get('pattern')}]")
    previous = [
        f"{t.get('code') or t.get('metric')}: {t.get('previous')} -> {t.get('latest')}"
        for t in (payload.get("trend") or []) + (payload.get("comparisons") or []) if isinstance(t, dict)
    ]
    questionnaire = payload.get("questionnaire_context") or payload.get("questionnaire") or []
    if isinstance(questionnaire, str):
        try:
            questionnaire = json.loads(questionnaire)
        except ValueError:
            questionnaire = [questionnaire]
    q_fields = [
        (f"{q.get('area') or q.get('question') or q.get('key')}: {q.get('reported') or q.get('answer') or q.get('value')}"
         if isinstance(q, dict) else str(q))
        for q in questionnaire
    ] + [f"already_doing: {x}" for x in payload.get("already_doing") or []]
    profile = payload.get("personalization_context") or payload.get("profile") or payload.get("personalization") or {}
    out["_items"] = {
        "blood_markers": blood_items,
        "bio_ai_values": bio_items,
        "questionnaire_fields": q_fields,
        "profile_fields": sorted(profile.keys()) if isinstance(profile, dict) else [],
        "profile_values": profile,
        "previous_values": previous,
        "already_explained_in_conversation": payload.get("already_explained_in_this_conversation") or [],
    }
    return out


# ---------------------------------------------------------------- one call

def analyze_payload(payload: dict) -> dict:
    """Component sizes for one provider request (the real dict that is POSTed)."""
    messages = payload.get("messages") or []
    components: dict[str, str] = {}
    roles = []
    for message in messages:
        role, content = message.get("role"), str(message.get("content") or "")
        roles.append({"role": role, **_size(content)})
        split = _split_system(content) if role == "system" else _split_user(content)
        for name, text in split.items():
            components[name] = components.get(name, "") + text
    schema = payload.get("response_format")
    schema_text = json.dumps(schema, ensure_ascii=False) if schema else ""
    params = {k: v for k, v in payload.items() if k not in {"messages", "response_format"}}
    params_text = json.dumps(params, ensure_ascii=False, default=str)
    record = {
        "model": payload.get("model"),
        "token_method": token_method(),
        "messages": roles,
        "components": {name: _size(text) for name, text in components.items() if text},
        "output_schema": {**_size(schema_text), "type": (schema or {}).get("type")} if schema else None,
        "request_parameters": {**_size(params_text), "values": params},
    }
    health = _health_json(components.get("health_context", ""))
    if health is not None:
        record["health_context_breakdown"] = health_breakdown(health)
    message_tokens = sum(r["tokens"] for r in roles)
    record["estimated_input_tokens"] = message_tokens + (record["output_schema"] or {}).get("tokens", 0)
    record["total_input_chars"] = sum(r["chars"] for r in roles) + len(schema_text)
    record["_components_text"] = components
    record["_schema_text"] = schema_text
    return record


def before_call(payload: dict, fmt: str) -> dict | None:
    if not enabled():
        return None
    try:
        record = analyze_payload(payload)
    except Exception:  # noqa: BLE001 - observability never breaks a call
        logger.debug("prompt_audit_failed", exc_info=True)
        return None
    record["format"] = fmt
    record["started"] = time.perf_counter()
    return record


def after_call(record: dict | None, usage: dict | None, *, error: str | None = None) -> None:
    if record is None:
        return
    record["latency_ms"] = int((time.perf_counter() - record.pop("started")) * 1000)
    record["provider_usage"] = dict(usage or {}) or None
    record["error"] = error
    texts = record.pop("_components_text")
    schema_text = record.pop("_schema_text")
    RECENT.append(record)
    _write(record, texts, schema_text)
    logger.info(
        "PROMPT AUDIT model=%s format=%s est_input_tokens=%s provider_input=%s provider_output=%s components=%s",
        record["model"], record["format"], record["estimated_input_tokens"],
        (usage or {}).get("input_tokens"), (usage or {}).get("output_tokens"),
        {k: v["tokens"] for k, v in record["components"].items()},
    )


_ORDER = (
    ("system_prompt", "SYSTEM"),
    ("application_instructions", "APPLICATION INSTRUCTIONS"),
    ("conversation", "CONVERSATION"),
    ("health_context", "HEALTH CONTEXT"),
    ("medical_evidence", "MEDICAL EVIDENCE / KNOWLEDGE INSTRUCTIONS"),
    ("routing_note", "ROUTING NOTE"),
    ("current_query", "CURRENT QUERY"),
    ("response_format_instructions", "RESPONSE / FORMAT INSTRUCTIONS"),
    ("output_contract", "OUTPUT CONTRACT (in system prompt)"),
)
_IDENTIFIER = re.compile(r"\b(?:subject_id|user_id|member_id)\"?\s*[:=]\s*\"?[\w-]+", re.I)


def _redact(text: str) -> str:
    """Identifiers only; health values stay visible (that is what this view audits)."""
    return _IDENTIFIER.sub("<identifier>", text or "")


def render(record: dict, texts: dict[str, str], schema_text: str) -> str:
    lines = [f"# model={record['model']} format={record['format']} tokens={record['token_method']}", ""]
    for key, title in _ORDER:
        if texts.get(key):
            size = record["components"].get(key, {})
            lines += [f"===== {title} ({size.get('chars')} chars, ~{size.get('tokens')} tokens) =====", _redact(texts[key]).rstrip(), ""]
    for key, text in texts.items():
        if key not in dict(_ORDER):
            lines += [f"===== {key.upper()} =====", _redact(text).rstrip(), ""]
    if schema_text:
        lines += [f"===== RESPONSE_FORMAT (JSON schema sent as a request parameter, {record['output_schema']['chars']} chars) =====", schema_text, ""]
    lines += ["===== REQUEST PARAMETERS =====", json.dumps(record["request_parameters"]["values"], indent=1, default=str), ""]
    return "\n".join(lines)


def _write(record: dict, texts: dict[str, str], schema_text: str) -> None:
    try:
        directory = Path(settings.cura_prompt_debug_dir or ".prompt_debug")
        directory.mkdir(parents=True, exist_ok=True)
        stem = f"{time.strftime('%Y%m%d-%H%M%S')}-{int(time.time() * 1000) % 1000:03d}-{(record['model'] or 'model').replace('/', '_')}"
        (directory / f"{stem}.txt").write_text(render(record, texts, schema_text))
        (directory / f"{stem}.json").write_text(json.dumps(record, indent=1, default=str))
        record["dump"] = str(directory / f"{stem}.txt")
    except OSError:
        logger.debug("prompt_debug_write_failed", exc_info=True)
