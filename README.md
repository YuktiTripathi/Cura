# Cura

Cura is SuperShyft's conversational health-intelligence layer. SuperShyft remains
the source of truth for SuperShyft health data; Cura owns orchestration,
conversation meaning, safety, evidence, recommendations, and presentation.

The local development profile uses mock providers and SQLite. The production
profile supports SuperShyft read-only canonical adapters, JWT authentication,
Cura-owned PostgreSQL persistence, Redis request controls, SSE chat, and an
OpenAI-compatible LLM provider (including local Ollama/Qwen).

## Layout

- `backend/` — FastAPI pipeline, contracts, SQLite conversation store
- `frontend/` — Vite + React + TypeScript chat UI
- `integrations/mock/` — fictional demo health data and providers
- `integrations/supershyft/` — temporary read-only bridge to canonical DTOs
- `contracts/` — OpenAPI for the Cura HTTP API
- `docs/` — architecture and handover

## Backend

From the **backend** folder (required — `app` lives in `backend/`):

```bash
cd /Users/yuks/Desktop/Cura/backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

From the **Cura repo root**:

```bash
source backend/.venv/bin/activate
python run_backend.py
```

Do not run `uvicorn app.main:app` from `/Users/yuks/Desktop/Cura` without `--app-dir backend`.

Dev auth (development only): send `X-Cura-User-Id: demo-user-001`.
Production rejects mock authentication and requires `AUTH_PROVIDER=supershyft_jwt`.

## Frontend

```bash
cd frontend
npm install
npm run dev
```

The UI calls `http://127.0.0.1:8000` by default (`VITE_CURA_API_URL`).

## Tests

See [docs/testing.md](docs/testing.md) and [docs/safety.md](docs/safety.md).

```bash
cd backend
source .venv/bin/activate
PYTHONPATH="/Users/yuks/Desktop/Cura/backend:/Users/yuks/Desktop/Cura" pytest --rootdir=/Users/yuks/Desktop/Cura/backend
```

Tests use mock providers by default (`ENABLE_LLM=false`). No SuperShyft writes. This is not clinical validation.

## LLM

OpenRouter is the only inference gateway. **Jev** (`JEV_MODEL`) returns a structured routing decision. A separate **medical LLM** (`MEDICAL_LLM_MODEL`) writes the user-facing answer after retrieval. There is no Qwen/Ollama/local fallback.

```
ENABLE_LLM=true
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=your-key
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
JEV_ENABLED=true
JEV_MODEL=typesafe/jev-1.13
MEDICAL_LLM_MODEL=openai/gpt-4o-mini
```

If Jev is unavailable, Cura falls back to the deterministic query planner (not another generative model). With `ENABLE_LLM=false` personal answers can still be rendered from HealthContext.

Do not put `OPENROUTER_API_KEY` in the frontend.

## Voice input (optional)

See [docs/voice.md](docs/voice.md). The microphone sends audio to `POST /api/v1/voice/transcribe`; the **transcript** is then processed by the same `/api/v1/chat` pipeline as typed text.

```
VOICE_ENABLED=false
STT_PROVIDER=none
```

Typed chat does not require STT. To use a local OpenAI-compatible Whisper server:

```
VOICE_ENABLED=true
STT_PROVIDER=local
STT_BASE_URL=http://127.0.0.1:8001/v1
STT_MODEL=whisper-1
```

## User-uploaded documents and cross-source comparison

Phase 8 extracts and retrieves PDF text. Phase 9 can compare an uploaded report with SuperShyft **when asked**, keeping sources labeled.

SuperShyft remains the source of truth for SuperShyft-originated data. User-uploaded documents remain independent sources.

See [docs/documents.md](docs/documents.md).

```
DOCUMENT_STORAGE_BACKEND=local
DOCUMENT_STORAGE_PATH=./data/uploads
DOCUMENT_MAX_UPLOAD_BYTES=20000000
DOCUMENT_OCR_PROVIDER=none
```

Composer: 📎 PDF attach (upload is separate from sending a chat message), then 🎙, then Send.

## Production controls

- `POST /api/v1/chat` supports `Idempotency-Key`.
- `POST /api/v1/chat/stream` emits SSE `status`, `token`, and `complete` events.
- `GET /api/v1/capabilities` exposes only capabilities backed by available data.
- `GET /api/v1/context/{type}/{id}` validates contextual Ask Cura references.
- Redis is used for short-term rate limiting/idempotency when configured.
- Run Cura-owned PostgreSQL migrations with `alembic -c alembic.ini upgrade head`
  from `backend/`. Never use the SuperShyft database URL as `DATABASE_URL`.

See [docs/production.md](docs/production.md) and [docs/architecture.md](docs/architecture.md).

## SuperShyft read-only database

Keep Cura chat history on SQLite. Point SuperShyft at a **separate** URL:

```
DATABASE_URL=sqlite:///./cura.db
HEALTH_PROVIDER=supershyft
SUPERSHYFT_DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@HOST:5432/DBNAME
```

Cura converts `+asyncpg` to a sync driver and only runs parameterized `SELECT`.
It never creates Cura tables in SuperShyft. The direct bridge is temporary;
production should replace it with SuperShyft's canonical resolver/API provider
without changing the Cura pipeline.

Dev auth header must be the SuperShyft numeric `user_id`:

`X-Cura-User-Id: 123`

If the host is not reachable from this laptop (VPN/firewall), health reads will time out until network access exists. Mock mode still works: `HEALTH_PROVIDER=mock`.

## Demo users (mock health only)

- `demo-user-001` — Alex (primary golden dataset)
- `demo-user-002` — Jordan (isolation tests)
