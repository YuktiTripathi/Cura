# Operations

## Run

```
docker build -t cura-api .
docker run -p 8000:8000 --env-file backend/.env -e WEB_CONCURRENCY=4 cura-api
```

The image runs several uvicorn workers without `--reload` as a non-root user. Wire the
load balancer to `GET /health/live` (liveness) and `GET /health/ready` (readiness).
Dependencies are pinned in `backend/requirements.lock`. To update them, edit
`requirements.txt` and run `pip-compile --strip-extras --no-header --output-file=requirements.lock requirements.txt`.

## Document workers

Outside development the API only queues uploaded documents (`DOCUMENT_WORKER_MODE=external`).
Run one or more workers from the same image:

```
docker run --env-file backend/.env cura-api python scripts/document_worker.py
```

Workers claim jobs atomically, so several can run at once. If a worker dies, its job is
picked up again after `DOCUMENT_JOB_LEASE_SECONDS`. After `DOCUMENT_JOB_MAX_ATTEMPTS`, the job
and its document are marked failed and the member sees a "please upload again" message.

## Capacity controls

| Setting | Default | Meaning |
| --- | --- | --- |
| `WEB_CONCURRENCY` | 4 | Worker processes per container |
| `MAX_IN_FLIGHT_CHATS` | 32 | Chats a single process handles at once. Beyond this, Cura returns 429 with a `Retry-After` header |
| `WORKER_THREADS` | 64 | Thread pool for sync handlers. Keep it above `MAX_IN_FLIGHT_CHATS` × 2, because streaming uses an extra thread |
| `LLM_TIMEOUT_SECONDS` | 30 | Model call timeout. The safe fallback answer is used after it |
| `MEMBER_DAILY_TOKEN_BUDGET` | 200000 | Daily model tokens per member |

Set these from the load test (`scripts/load/chat_mix.js`, run with k6), not by guesswork.

## Metrics and alerts

`GET /metrics` serves Prometheus metrics. Set `METRICS_TOKEN` and scrape it with that bearer token.

| Metric | Suggested alert |
| --- | --- |
| `cura_http_request_seconds{route="/api/v1/chat"}` | p95 above 8 s for 10 min |
| `cura_http_requests_total{status=~"5.."}` | over 1% of requests for 5 min |
| `cura_chat_total{fallback="yes"}` | over 5% of chats for 15 min |
| `cura_chat_shed_total` | any sustained increase (add capacity) |
| `cura_safety_flags_total{flag="safety_classifier_unavailable"}` | any increase (the safety model is down) |
| `cura_stage_seconds` | breakdown by stage (jev, retrieval, llm, validation, compose) |
| `cura_llm_cost_usd_total` | daily spend above budget (monthly spend alert, plan 6.7) |

## Scheduled jobs

- Run `python scripts/purge_expired.py` daily.
- Document and conversation retention use `DOCUMENT_RETENTION_DAYS` and
  `CONVERSATION_RETENTION_DAYS`.
- Terminal processing-job and operational-audit retention are disabled by
  default. Set `PROCESSING_JOB_RETENTION_DAYS` or `AUDIT_RECORD_RETENTION_DAYS`
  only after the applicable operational, medical-safety, and legal retention
  policies are approved.
