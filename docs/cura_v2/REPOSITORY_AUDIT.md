# Repository audit

Date: 2026-11-24. Method: read the tree, routers, providers, contracts, and frontend entry. Nothing was deleted. Baseline test commands are recorded in `TESTING_STRATEGY.md`.

There is no A2UI module in this repository.

## Frontend

Stack: Vite, React 18, TypeScript, TanStack Query, Vitest. Entry: `frontend/src/main.tsx` → `frontend/src/App.tsx` → `frontend/src/pages/CuraPage.tsx`.

`CuraPage` owns chat, document selection, and three overview modes (`blood`, `bio_ai`, `unified`) plus a marker side panel. Navigation state is local React state (`overviewKind`, `openGroupId`, `markerKey`), not a router.

| Path | Role |
| --- | --- |
| `frontend/src/hooks/useCuraChat.ts` | Streaming chat, history, edit-and-resend |
| `frontend/src/hooks/useHealthOverview.ts` | Unified overview and category queries, 5 minute stale time |
| `frontend/src/hooks/useOverview.ts`, `useReportOverviews.ts`, `useMe.ts` | Older overview and profile fetches |
| `frontend/src/lib/api.ts` | HTTP client, dev user header |
| `frontend/src/components/overview/HealthOverviewView.tsx` | Unified category list |
| `frontend/src/components/overview/SystemDetail.tsx`, `BiomarkerDetail.tsx` | Category and marker UI |
| `frontend/src/components/overview/BodySystemOverviewView.tsx`, `RiskOverviewView.tsx` | Separate blood and Bio-AI overviews |
| `frontend/src/components/marker/MarkerPanel.tsx` | Marker history panel |
| `frontend/src/components/documents/*` | PDF upload and value review |
| `frontend/src/hooks/useSpeechInput.ts`, `frontend/src/lib/speech.ts` | Microphone |
| `frontend/src/i18n/` | en / hi / hinglish catalogs |
| `frontend/src/prototype/CompanionPrototype.tsx`, `demoData.ts` | Prototype with local demo data, not the production page |
| `frontend/openapi/cura.json`, `frontend/src/types/api.generated.ts` | Generated API types |

## Backend

FastAPI app: `backend/app/main.py`. Router: `backend/app/api/router.py` prefix `/api/v1`.

Chat path (documented in `docs/architecture.md`, implemented under `backend/app/pipeline/`): auth → safety → planner / optional Jev (`backend/app/routing/`) → retrieval (`backend/app/pipeline/health_gateway.py`, `backend/app/retrieval/`) → `HealthContext` → reasoning or deterministic lookup → grounding and safety → composer. SSE: `POST /api/v1/chat/stream`. JSON: `POST /api/v1/chat`.

Screen path: `GET /api/v1/health-explanation/overview|categories/{id}|findings/{id}` in `backend/app/api/routes/health_explanation.py`, built by `backend/app/pipeline/unified_service.py` and `backend/app/biomarkers/unified_overview.py`. Parallel older routes live on `backend/app/api/routes/me.py`: `/me`, `/me/overview`, `/me/body-systems`, `/me/bio-ai-risks`, `/me/health-overview`.

`unified_overview` serves a cached payload when present. On a cache miss it returns numbers without waiting for the model (`with_wording=False`) and schedules `schedule_overview_precompute`, which calls `build_overview` and `build_category` with wording enabled. `build_category` can call `build_story` with the model when `ENABLE_LLM` and consent allow it. That conflicts with the product rule that overview and category screens are not model-generated. The deterministic numbers themselves are built in `biomarkers/unified_overview.py` from provider rows.

The `backend/app/pipeline/` package is very large (planners, composers, narrative, nutrition, packages, quality gates). Much of it serves chat quality, not the five screens. It stays until a smaller chat path is proven.

## SuperShyft data

`integrations/supershyft/` is a read-only SELECT bridge. `HEALTH_PROVIDER=supershyft` wires it in `backend/app/providers/registry.py`. Mock JSON lives in `integrations/mock/data/` and is the default local provider.

| Data | Adapter | Tables / files |
| --- | --- | --- |
| Profile | `integrations/supershyft/providers.py` `SuperShyftUserProvider` | `users` |
| Blood | `integrations/supershyft/blood.py` | `participant_blood_bookings` via `engagement_participants`; JSON in `blood_parameters` and `blood_report_raw.digital_data` |
| Bio-AI | `integrations/supershyft/ihr.py` | `individual_health_report.reports` |
| Questionnaire | `integrations/supershyft/questionnaire.py` | `questionnaire_responses` and related definition tables |
| Lifestyle | `SuperShyftLifestyleProvider` | `user_preferences`, else diet/sleep/activity from questionnaire tables |
| Diagnostic catalog | `integrations/supershyft/diagnostics.py` | package names for gap recommendations |

Canonical DTOs: `backend/app/contracts/blood.py`, `bio_ai.py`, `lifestyle.py`, `questionnaire.py`, `profile.py`. Pipeline code depends on provider interfaces in `backend/app/providers/interfaces.py`, not on SQL.

## Authentication and isolation

- Production: `AUTH_PROVIDER=supershyft_jwt`, `backend/app/auth/jwt.py`. Subject comes from token `sub` / `user_id`.
- Development: `AUTH_PROVIDER=mock`, header `X-Cura-User-Id`. Rejected when production invariants in `backend/app/core/invariants.py` apply.
- `backend/app/auth/identity.py` strips client-supplied user ids from bodies.
- Health reads are scoped to `AuthenticatedPrincipal.subject_id`. Health-explanation routes have no member id in the path.
- Cura's own database (`DATABASE_URL`) stores conversations and document metadata. It does not store SuperShyft lab rows. See `backend/app/db/models.py`.

## Caching

| Mechanism | Path | What it stores |
| --- | --- | --- |
| Provider cache | `backend/app/providers/cache.py` | Blood, Bio-AI, lifestyle, questionnaire payloads. Opaque member hash. TTL. Not a model answer. |
| Overview screen cache | `backend/app/pipeline/overview_cache.py` | Unified overview and per-category JSON, 600s, via `request_controls`. Precompute can include model wording. |
| Unified wording cache | `backend/app/pipeline/unified_wording.py` | Model sentences, 7 days, keyed by member and report versions. |
| Answer cache | `backend/app/llm/answer_cache.py` | Chat answers. |
| Frontend | TanStack Query `staleTime` 5 minutes in `useHealthOverview.ts` | HTTP responses. Category open still issues `getHealthCategory` when that query is cold. |
| Finding route | `unified_finding` | Reloads blood and Bio-AI on every call. No finding cache. |

Chat still re-reads providers per turn through the gateway, with the provider cache in front. Screen navigation is not yet a single snapshot served entirely from memory.

## Registries and knowledge

| Asset | Path |
| --- | --- |
| Health categories (15 ids) | `backend/app/biomarkers/health_categories.py` |
| Blood system assignment | `backend/app/biomarkers/systems.py`, `registry.py`, `data/registry_overlay_v1.json` |
| Biomarker education | `backend/app/biomarkers/data/biomarker_education_v1.json`, loader `education.py` |
| Bio-AI risk registry | `backend/app/biomarkers/data/risk_registry_v1.json` |
| Relationship map | `backend/app/retrieval/config/cura_biomarker_relationship_map.json` |
| Retrieved medical articles | `backend/app/retrieval/content/` including `cura_biomarkers.json`, `cura_bio_ai_conditions.json`, markdown knowledge base |
| Explanation knowledge | `backend/app/health_explanation/knowledge/relationships.json`, `actions.json` |
| Status rules | `backend/app/contracts/unified_health.py`, `backend/app/pipeline/clinical_thresholds.py` |

Education notes on findings are attached from the education file. Category card prose can still be replaced by `unified_wording.py`.

## LLM and routing

OpenRouter only (`backend/app/llm/factory.py`, `openai_compatible.py`). No local Ollama fallback (`README.md`).

- Jev (`backend/app/routing/jev_router.py`) returns a routing decision for chat. Fallback is the deterministic planner.
- Answer tiers: `backend/app/routing/model_tier.py` and `docs/model_routing.md` (fast, standard, deep).
- Screen wording: `unified_wording.py` and category `build_story` in the health explanation package.

## Chat storage

SQLite or Postgres via `DATABASE_URL`. Tables in `backend/app/db/models.py`: `conversations` (subject, summary, state JSON, last marker), `messages`, `feedback`, `interactions` (telemetry; new writes avoid duplicating transcript text), consent and document metadata tables further in the same file. Repositories: `backend/app/db/repositories.py`. Routes: `backend/app/api/routes/conversations.py`, `feedback.py`.

## PDF upload

`backend/app/documents/` extracts, chunks, OCRs, and stores bytes outside SuperShyft (`docs/documents.md`, `DocumentStore`). Routes: `backend/app/api/routes/documents.py`. Frontend: `useDocumentUpload.ts`, `DocumentPanel.tsx`, `ReviewValues.tsx`. Answers tag source `user_uploaded`.

## Voice and language

`POST /api/v1/voice/transcribe` (`backend/app/api/routes/voice.py`, `backend/app/voice/`). Audio is transcribed and discarded; the transcript uses the same chat pipeline (`docs/voice.md`). UI catalogs: `frontend/src/i18n/messages/{hi,hinglish}.json` and `backend/app/i18n/`. Glossary: `backend/app/i18n/glossary.json`.

## Tests

Backend: `backend/tests/` (unit, acceptance, quality, safety, golden). Frontend: Vitest next to components. CI: `.github/workflows/ci.yml` (pytest, Postgres migrations, frontend test and build, Docker image, gitleaks). Prior triage of known failures: `docs/BASELINE_TEST_TRIAGE.md` (2052 passed, 27 failed on that earlier run). This audit re-runs the suites; see `TESTING_STRATEGY.md`.

## Module disposition

### Retain

- `integrations/supershyft/**` and `backend/app/providers/interfaces.py`, `registry.py`, `cache.py`
- `backend/app/auth/**` (JWT, mock gated by env, identity stripping)
- `backend/app/db/**` conversation, feedback, consent, document metadata
- `backend/app/documents/**` and document routes
- `backend/app/voice/**` and voice routes
- `backend/app/i18n/**`, `frontend/src/i18n/**`
- `backend/app/contracts/blood.py`, `bio_ai.py`, `lifestyle.py`, `questionnaire.py`, `unified_health.py` (numbers and status)
- `backend/app/biomarkers/data/**`, `health_categories.py`, `education.py`, `registry.py`, `systems.py`, `unified_overview.py` (deterministic assembly)
- Chat safety that blocks invented personal numbers: `pipeline/grounding.py`, `numeric_grounding.py`, `safety.py`, `claim_check.py`
- Frontend chat shell pieces that already work: `useCuraChat.ts`, `Composer.tsx`, `MessageList.tsx`, document upload, speech input, conversation sidebar
- `contracts/openapi.yaml` as the HTTP contract until routes are versioned

### Refactor

- `pipeline/unified_service.py` and `overview_cache.py`: one member snapshot, no model on the screen path, finding lookup from that snapshot
- `api/routes/health_explanation.py` and the overlapping `/me/*` overview routes: one exploration API
- `contracts/context_ref.py`: add category id and make card actions carry category, marker, or risk only
- `pipeline/retrieval_executor.py` and `relevant_context.py`: retrieve the entities named by the question and context ref, not a broad medical dump
- `frontend/src/pages/CuraPage.tsx`: five-screen flow over one snapshot query
- `pipeline/prompt_builder.py` / `prompt_modules.py`: one stable core system prompt for conversation

### Replace

- Model-written overview and category prose (`pipeline/unified_wording.py` on the screen path, `health_explanation` story generation when it writes screen copy). Registry text and deterministic status labels replace it.
- The three parallel overview UIs (`BodySystemOverviewView`, `RiskOverviewView`, and the unified view as separate products). One category model that shows measured and predicted together, distinguished by `source_type`.
- `frontend/src/prototype/demoData.ts` as a source of health numbers. It is not a production path today; it must not become one.

### Remove after migration

Only after the replacement is tested and the current app still runs from the old routes during the switch:

- Duplicate overview endpoints on `/me` once the client uses the snapshot API
- Screen-path calls into wording and story models
- Unused prototype route if nothing imports it in the shipping shell
- Pipeline modules that only existed to narrate overview screens, after tests show chat no longer imports them

Do not remove SuperShyft adapters, auth, documents, voice, or conversation storage as part of that cleanup.
