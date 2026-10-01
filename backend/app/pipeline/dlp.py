"""Second-layer DLP: block credentials, redact leftover identifiers. Keep clinical content."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.core.errors import CuraError

_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")
_BEARER = re.compile(r"\bBearer\s+[A-Za-z0-9._\-]{12,}\b", re.I)
_OPENAI = re.compile(r"\bsk-[A-Za-z0-9]{16,}\b")
_ANTHROPIC = re.compile(r"\bsk-ant-[A-Za-z0-9\-_]{16,}\b")
_GEMINI = re.compile(r"\bAIza[0-9A-Za-z\-_]{20,}\b")
_OPENROUTER = re.compile(r"\bsk-or-[A-Za-z0-9\-_]{16,}\b")
_OTP = re.compile(r"\b(?:otp|one[- ]time(?: password| code)?)\s*[:=]\s*\d{4,8}\b", re.I)
_AUTH_HEADER = re.compile(r"\bAuthorization\s*:\s*\S+", re.I)

_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_PHONE = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?){2}\d{4}\b")
_INTERNAL_ID = re.compile(
    r"\b(?:user_id|subject_id|assessment_instance_id|assessment_id|report_id|record_id)\s*[:=]\s*\S+",
    re.I,
)

_SECRET_PATTERNS = (_JWT, _BEARER, _OPENAI, _ANTHROPIC, _GEMINI, _OPENROUTER, _OTP, _AUTH_HEADER)


class SecurityBlockedError(CuraError):
    def __init__(self, message: str = "The request could not be processed securely."):
        super().__init__("SECURITY_BLOCKED", message, 500)


@dataclass
class DlpResult:
    blocked: bool = False
    redacted: Any = None
    flags: list[str] | None = None


def contains_secret(value: Any) -> bool:
    if isinstance(value, dict):
        return any(contains_secret(item) for item in value.values())
    if isinstance(value, list):
        return any(contains_secret(item) for item in value)
    if isinstance(value, str):
        return any(pattern.search(value) for pattern in _SECRET_PATTERNS)
    return False


def redact_identifiers(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: redact_identifiers(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_identifiers(item) for item in value]
    if not isinstance(value, str):
        return value
    text = _EMAIL.sub("[redacted-email]", value)
    text = _PHONE.sub("[redacted-phone]", text)
    text = _INTERNAL_ID.sub("[redacted-id]", text)
    return text


def scan_model_payload(value: Any) -> DlpResult:
    if contains_secret(value):
        return DlpResult(blocked=True, flags=["credential_in_model_payload"])
    return DlpResult(blocked=False, redacted=redact_identifiers(value), flags=[])


def assert_messages_safe(messages: list[dict]) -> list[dict]:
    result = scan_model_payload(messages)
    if result.blocked:
        raise SecurityBlockedError()
    cleaned = result.redacted
    return cleaned if isinstance(cleaned, list) else messages
