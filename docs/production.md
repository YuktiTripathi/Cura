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
| Structured LLM output | Missing | PARTIAL | JSON contract is validated; free-text answers degrade safely with no candidate recommendations |
| Jev orchestration | Chat-completion JSON prompt | COMPLETE | OpenRouter typed Decisions API + CURA validation + deterministic fallback |
| Conversation meaning | Topic only | PARTIAL | Semantic state/report/topic persistence; no fact caching |
| Production auth | Missing | COMPLETE for shared-secret JWT | JWT provider; OIDC/JWKS remains deployment-specific |
| Redis controls | Missing | COMPLETE when configured | Rate limit/idempotency; bounded dev fallback |
| SSE | Missing | COMPLETE | `/api/v1/chat/stream` status/token/complete events |
| Cura PostgreSQL | Models only | COMPLETE, not live-verified | Alembic baseline; separate DB guard |
| SuperShyft canonical API | DB bridge | DEFERRED | Awaiting canonical upstream API contract |
| Native provider token streaming | Missing | PARTIAL | SSE chunks complete output; provider-native stream hook exists |
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
cd /Users/yuks/Desktop/Cura
./backend/.venv/bin/python -m pytest backend/tests -q
cd frontend && npm run build
```

## Security invariants

- Production never trusts `X-Cura-User-Id`.
- `context_ref` never accepts medical values.
- Every provider query is scoped by the authenticated principal.
- SuperShyft SQL is parameterized and SELECT-only.
- PDFs are owner-scoped and treated as untrusted evidence.
- The LLM has no provider, SQL, filesystem, credential, or identity access.
- Recommendations are not visible until deterministic policy approval.
- Current health facts are never sourced from conversation memory.
