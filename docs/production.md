# Production implementation and operations

## Gap matrix used for implementation

| Requirement | Before | Current status | Implementation |
| --- | --- | --- | --- |
| Blood / Bio-AI context | Present | COMPLETE | Canonical provider DTOs, minimal HealthContext, evidence |
| General health isolation | Present | COMPLETE | LLM-only general path; no personal/document retrieval |
| Health Scenario | Placeholder flag | COMPLETE | Composite provider + deterministic engine + evidence |
| Nutrition validation | Missing | COMPLETE | Candidate model + deterministic policy engine |
| Ask Cura | Missing | COMPLETE | Validated identifier-only `context_ref` and context endpoint |
| Pre/post safety | Partial | COMPLETE for defined policy | Pre-gate, post-review, critical-status escalation |
| Numeric grounding | Dead code | COMPLETE | Personal LLM output validated with deterministic fallback |
| Structured LLM output | Missing | COMPLETE | JSON Schema when supported; parse failures are internal; one repair retry; deterministic fallback |
| Jev orchestration | Chat-completion JSON prompt | COMPLETE | OpenRouter typed Decisions API + CURA validation + deterministic fallback |
| Conversation meaning | Topic only | PARTIAL | Semantic state/report/topic persistence; no fact caching |
| Production auth | Missing | COMPLETE for shared-secret JWT | JWT provider; OIDC/JWKS remains deployment-specific |
| Redis controls | Missing | COMPLETE when configured | Rate limit/idempotency; bounded dev fallback |
| SSE | Missing | COMPLETE | `/api/v1/chat/stream` emits `progress` stages then `complete`/`answer` |
| Cura PostgreSQL | Models only | COMPLETE, not live-verified | Alembic baseline; separate DB guard |
| SuperShyft canonical API | DB bridge | DEFERRED | Awaiting canonical upstream API contract |
| Native provider token streaming | Missing | DISABLED | `/chat/stream` emits status+complete after the full pipeline; not token streaming |
| Clinical validation | Not in scope | DEFERRED | Requires clinical governance outside software tests |

## Production environment

```dotenv
APP_ENV=production
AUTH_PROVIDER=supershyft_jwt
AUTH_JWT_SECRET=use-a-secret-manager
AUTH_JWT_ISSUER=https://your-supershyft-issuer
AUTH_JWT_AUDIENCE=cura
DEV_AUTH_HEADER=false

DATABASE_URL=postgresql+psycopg://cura_app:...@cura-db/cura
HEALTH_PROVIDER=supershyft
SUPERSHYFT_DATABASE_URL=postgresql+psycopg://read_only:...@supershyft-db/supershyft

REDIS_URL=redis://redis:6379/0
REDIS_REQUIRED=true
ENABLE_LLM=true
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=use-a-secret-manager
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
JEV_ENABLED=true
JEV_MODEL=typesafe/jev-1.13
MEDICAL_LLM_MODEL=openai/gpt-4o-mini
```

Secrets belong in a secret manager, never a tracked `.env`.

`OPENROUTER_BASE_URL` remains the normal `/api/v1` base used by the medical
LLM. The Jev adapter derives OpenRouter's official
`/api/alpha/decisions` endpoint; no second API key or configuration system is
required.

## Migrations and startup

```bash
cd backend
python -m pip install -r requirements.txt
alembic -c alembic.ini upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

For local development:

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run build
npm run dev
```

## Verification

```bash
cd backend
./.venv/bin/python -m pytest tests -q
cd ../frontend && npm run build
```

## Manual credential rotation (operators)

Do this outside the application. Cura cannot rotate provider secrets from code.

1. Rotate the OpenRouter API key.
2. Rotate the SuperShyft read-only database password.
3. Revoke the previous credentials.
4. Replace production secret-manager values (`OPENROUTER_API_KEY`, `SUPERSHYFT_DATABASE_URL`, `AUTH_JWT_SECRET`, `DOCUMENT_ENCRYPTION_KEY`).

## SuperShyft database role

Application-level `SELECT`-only checks are defense in depth. Production credentials must be a database role with:

- SELECT only
- no INSERT / UPDATE / DELETE
- no DDL (`CREATE` / `ALTER` / `DROP`)
- no schema modification

## Document retention

Uploaded PDFs are owner-scoped. `DOCUMENT_RETENTION_DAYS` (default 90) is the intended retention window. Production local storage requires `DOCUMENT_ENCRYPTION_KEY`. Durable extraction jobs are stored in `processing_jobs` and drained on startup.

## Streaming

`POST /api/v1/chat/stream` emits `status` then `complete` after the full safety/grounding pipeline. It is not native token streaming.

## Auth pairing

Startup always refuses `AUTH_PROVIDER=mock` with `HEALTH_PROVIDER=supershyft` when `APP_ENV=production`, even if `ALLOW_MOCK_AUTH_WITH_REAL_HEALTH=true`. Development/test may opt in with that flag plus `MOCK_USER_ID`.

## Security invariants

- Production never trusts `X-Cura-User-Id`.
- `context_ref` never accepts medical values.
- Every provider query is scoped by the authenticated principal.
- SuperShyft SQL is parameterized and SELECT-only.
- PDFs are owner-scoped and treated as untrusted evidence.
- The LLM has no provider, SQL, filesystem, credential, or identity access.
- Recommendations are not visible until deterministic policy approval.
- Current health facts are never sourced from conversation memory.

## Assistant quality flag

`ASSISTANT_QUALITY_V2` (default true) enables operation metadata, diagnosis-restraint
retrieval, JSON Schema structured output, and the answer-quality gate. Set
`ASSISTANT_QUALITY_V2=false` to roll back those paths without reverting Jev,
safety, or SuperShyft isolation. `LLM_JSON_SCHEMA_OUTPUT=false` keeps JSON-object
mode without a strict schema.

`OPENROUTER_DATA_COLLECTION_DENY` is not zero retention. Production personal-health
LLM should set `OPENROUTER_ZERO_DATA_RETENTION=true` only after confirming the
gateway's ZDR-eligible providers, and `REQUIRE_ZDR_FOR_PERSONAL_HEALTH=true` to
fail closed when that policy is missing.
