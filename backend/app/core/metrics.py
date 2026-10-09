"""Prometheus metrics (production readiness plan, 5.6).

Exposed at GET /metrics. Alert on p95 latency, error rate, fallback rate and safety
flag rate (see docs/operations.md). Labels never carry member ids or message text.
"""

from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

_LATENCY_BUCKETS = (0.05, 0.1, 0.25, 0.5, 1, 2, 4, 8, 12, 20, 30, 60)

HTTP_REQUESTS = Counter("cura_http_requests_total", "HTTP requests", ["method", "route", "status"])
HTTP_LATENCY = Histogram("cura_http_request_seconds", "HTTP latency", ["method", "route"], buckets=_LATENCY_BUCKETS)
IN_FLIGHT = Gauge("cura_chat_in_flight", "Chat requests being processed in this process")
SHED = Counter("cura_chat_shed_total", "Chat requests refused because the process was full")
STAGE_LATENCY = Histogram("cura_stage_seconds", "Pipeline stage latency", ["stage"], buckets=_LATENCY_BUCKETS)
CHAT_OUTCOMES = Counter("cura_chat_total", "Chat answers by outcome", ["status", "tier", "fallback"])
SAFETY_FLAGS = Counter("cura_safety_flags_total", "Safety flags raised", ["flag"])
TOKENS = Counter("cura_llm_tokens_total", "Model tokens", ["kind", "tier"])
ANSWER_CACHE = Counter("cura_answer_cache_total", "Model answer cache lookups", ["result"])
HEALTH_DATA_CACHE = Counter("cura_health_data_cache_total", "Supershyft read cache lookups", ["kind", "result"])
SPEND_SPIKE = Counter("cura_spend_spike_downgrades_total", "Deep answers sent to standard during a spend spike")
COST = Counter("cura_llm_cost_usd_total", "Estimated model cost in USD", ["tier"])

_KNOWN_FLAGS_LIMIT = 64


def observe_stage(stage: str, milliseconds: int) -> None:
    STAGE_LATENCY.labels(stage=stage[:32]).observe(max(0, milliseconds) / 1000.0)


def observe_chat(meta) -> None:
    tier = (getattr(meta, "answer_model_tier", None) or "none")[:32]
    status = (getattr(meta, "status", None) or "ok")[:32]
    fallback = "yes" if getattr(meta, "fallback_used", False) or getattr(meta, "model_fallback_used", False) else "no"
    CHAT_OUTCOMES.labels(status=status, tier=tier, fallback=fallback).inc()
    for flag in (getattr(meta, "safety_flags", None) or [])[:_KNOWN_FLAGS_LIMIT]:
        SAFETY_FLAGS.labels(flag=str(flag)[:48]).inc()
    if getattr(meta, "input_tokens", None):
        TOKENS.labels(kind="input", tier=tier).inc(meta.input_tokens)
    if getattr(meta, "output_tokens", None):
        TOKENS.labels(kind="output", tier=tier).inc(meta.output_tokens)
    if getattr(meta, "jev_input_tokens", None):
        TOKENS.labels(kind="jev_input", tier="jev").inc(meta.jev_input_tokens)
    if getattr(meta, "jev_output_tokens", None):
        TOKENS.labels(kind="jev_output", tier="jev").inc(meta.jev_output_tokens)
    if getattr(meta, "estimated_cost_usd", None):
        COST.labels(tier=tier).inc(meta.estimated_cost_usd)


def render() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
