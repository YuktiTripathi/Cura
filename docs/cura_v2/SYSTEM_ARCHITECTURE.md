# System architecture (target, grounded in the current repo)

Phase 0 defines the target. Phase 1 implements the snapshot and leaves the current chat pipeline running.

## Current runtime

```
Browser (CuraPage)
  ├─ TanStack Query → GET /health-explanation/overview
  │                    GET /health-explanation/categories/{id}
  │                    GET /me, /me/overview, /me/body-systems, /me/bio-ai-risks
  ├─ useCuraChat → POST /chat and /chat/stream
  ├─ documents → /documents
  └─ voice → /voice/transcribe

API (FastAPI, backend/app/main.py)
  AuthProvider → AuthenticatedPrincipal.subject_id
  ProviderRegistry
    mock JSON  or  integrations/supershyft SELECT (read-only)
  Provider cache (blood, bio_ai, lifestyle, questionnaire)
  Overview cache + optional unified_wording / category story model
  Chat pipeline (planner, optional Jev, retrieval, HealthContext, medical LLM, grounding)
  DATABASE_URL: conversations, messages, feedback, document metadata
```

SuperShyft remains the system of record. CURA does not write health rows. Uploaded PDFs stay in `DocumentStore`.

## Target

```
Browser
  Health exploration: one snapshot fetch, then local screen state
  Conversation: question + CardContext → POST /chat

API
  Snapshot service (deterministic)
    reads providers once per snapshot version
    joins categories from health_categories.py
    attaches education and risk registry text
    writes MemberSnapshot to the existing provider/overview cache
    never calls an LLM
  Conversation service (existing pipeline, narrowed)
    CardContext selects entities
    retrieval returns those facts + matching registry entries only
    one core system prompt + fact envelope
    existing grounding and safety stay
```

Screen navigation after the snapshot is in memory:

| Screen | Data |
| --- | --- |
| Home | Snapshot presence flags and category count |
| Overview | `categories[]` with measured and predicted counts |
| Category | `categories[id].findings` |
| Biomarker | finding where `source_type=measured` |
| Bio-AI risk | finding where `source_type=predicted_risk` |

`Finding` already exists in `backend/app/contracts/unified_health.py` and separates the two kinds with `source_type`.

## What does not change in Phase 1

- `AUTH_PROVIDER` and `HEALTH_PROVIDER` selection in `providers/registry.py`
- SuperShyft SQL adapters
- Conversation tables and document pipeline
- OpenRouter client in `backend/app/llm/factory.py`
- Voice transcription in front of chat

## Dependencies to keep

Python: FastAPI, Pydantic, SQLAlchemy, httpx (see `backend/requirements.lock`). Frontend: React, TanStack Query, Vite. Redis when configured for `request_controls`; development already falls back to an in-process store (`docs/architecture.md`). No new UI framework. No A2UI.

## Failure behaviour

- Provider down and cache cold: exploration shows an explicit unavailable state. It does not fill numbers.
- Provider down and cache warm: serve the snapshot until TTL, same rule as `providers/cache.py`.
- Model down: screens still render. Chat returns the existing deterministic fallback for lookups and a clear failure for questions that need prose.
- Missing registry entry: show the measured value and status; omit educational prose rather than generating it.
