# Phase 1 implementation

The snapshot path is implemented and wired into the existing API and React app. It is off unless `MEMBER_SNAPSHOT_ENABLED=true`. With the flag off, overview routes keep the previous behaviour, including model wording.

## Files

Created:

- `backend/app/contracts/member_snapshot.py`
- `backend/app/snapshot/assemble.py`
- `backend/app/snapshot/cache.py`
- `backend/app/snapshot/__init__.py`
- `backend/tests/unit/test_member_snapshot.py`
- `frontend/src/hooks/useHealthOverview.test.tsx`

Modified:

- `backend/app/core/config.py`
- `backend/app/core/metrics.py`
- `backend/app/contracts/context_ref.py`
- `backend/app/api/routes/health_explanation.py`
- `backend/app/pipeline/query_planner.py`
- `contracts/openapi.yaml`
- `frontend/src/types/api.generated.ts`
- `frontend/src/types/chat.ts`
- `frontend/src/lib/api.ts`
- `frontend/src/lib/queryClient.ts`
- `frontend/src/hooks/useHealthOverview.ts`
- `frontend/src/pages/CuraPage.tsx`
- `frontend/src/components/overview/HealthOverviewView.tsx`
- `frontend/src/components/overview/HealthOverview.test.tsx`

## Architecture

`assemble_snapshot` reads blood, Bio-AI, lifestyle, questionnaire, and profile through the existing provider interfaces, concurrently. It reuses `build_body_system_overview`, `build_risk_overview`, `build_unified_overview`, and `build_category_detail`. It does not call `unified_wording`, `build_story`, Jev, or `get_llm_client`. Category `story` is cleared.

Reports are ordered by date and then report id. The last is latest and the one before it is previous. Same-day reports stay separate rows.

`HealthView` is that snapshot without raw questionnaire answers. Findings live on category details and in a finding map. Overview cards still carry the existing summary fields the current screen reads.

`GET /api/v1/health-explanation/view` returns the view when the flag is on, and 404 when it is off. Overview, category, finding, and refresh on that router slice the snapshot when the flag is on. `/me/*` routes are unchanged.

The React app prefetches the view when CURA opens (`CuraPage` calls `useHealthView`). The composer does not wait on it. If the view is present, category screens read it from TanStack Query and do not call `getHealthCategory`. If the server returns 404, the previous overview and category requests run. Query keys include the member id from `/me`. Changing that id drops the other member's `health-view` cache. The snapshot is not written to localStorage.

`ContextRef` gained optional `category_id`, `finding_id`, and `snapshot_version`. Category follow-up buttons send the category id and snapshot version. The server still loads values itself.

With the flag on, `build_query_plan` keeps a general question off the personal providers, lets a newly named marker replace the open card, adds related marker keys for a blood-marker card, and sets history when the message asks for a comparison. With the flag off, card handling is the previous `_apply_context_ref` path.

## Cache

| Setting | Default |
| --- | --- |
| `MEMBER_SNAPSHOT_ENABLED` | `false` |
| `MEMBER_SNAPSHOT_TTL_SECONDS` | `600` |
| `MEMBER_SNAPSHOT_LOCK_SECONDS` | `20` |
| `MEMBER_SNAPSHOT_WAIT_SECONDS` | `5` |
| `MEMBER_SNAPSHOT_SCHEMA_VERSION` | `1` |

Key: `cura:snapshot:{sha256(subject)[:32]}:{schema}:{registry version}`. Registry version is `unified-1` from `health_categories.py`. The raw member id is not in the key or in snapshot logs.

One lock per key. The waiter reads the finished payload. Lock expiry is the lock TTL. Refresh deletes the snapshot key and the provider health cache, then rebuilds. A TTL of 0 skips the cache. A Redis read or lock error builds from providers and does not serve an expired body. There is no SuperShyft write event, so a new report is picked up on TTL expiry or `POST /api/v1/health-explanation/refresh`. The in-process `request_controls` store remains the development fallback and is not a shared production cache.

## Feature flag

```bash
export MEMBER_SNAPSHOT_ENABLED=true
```

Unset or `false` keeps the current overview path. Mock and SuperShyft providers both flow through `ProviderRegistry`.

## Local run

```bash
cd backend && source .venv/bin/activate
export APP_ENV=development AUTH_PROVIDER=mock HEALTH_PROVIDER=mock
export MEMBER_SNAPSHOT_ENABLED=true ENABLE_LLM=true LLM_PROVIDER=openrouter
python /Users/yuks/Desktop/Cura/run_backend.py
```

```bash
cd frontend && VITE_CURA_USER_ID=demo-user-001 npm run dev
```

## Observability

Prometheus counters and histograms: `cura_member_snapshot_cache_total`, `cura_member_snapshot_build_seconds`, `cura_member_snapshot_payload_bytes`, `cura_member_snapshot_navigation_seconds`, `cura_exploration_llm_calls_total`. The exploration LLM counter is not incremented on this path. Logs record provider call counts, cache hit age in seconds, payload outcome, and evidence entity keys. They do not record result values.

Measured in unit tests, not under a production load: a warm `load_snapshot` did not increment the fake provider call count; four concurrent callers shared one provider read when the lock was available. No separate cold/warm latency benchmark was run against SuperShyft.

## Tests executed

Backend full suite, flag off, 368s: **29 failed, 2104 passed, 4 skipped**. Phase 0 was 29 failed, 2092 passed, 4 skipped. The 12 additional passes are `tests/unit/test_member_snapshot.py`. The 29 failure names match Phase 0. No new backend regression.

Frontend full suite, 9.45s: **9 failed, 165 passed** (40 files). Phase 0 was 9 failed, 163 passed (39 files). The two new passes are the health-view cache tests. The same 9 failures remain: `theme.test.ts` and `Companion.test.tsx` (`localStorage` is not a function in this environment) and one `MessageList` placeholder assertion.

Not executed: a live OpenRouter call, a live SuperShyft database, and a timed cold-versus-warm benchmark against Postgres.

## Known limits

- Flag defaults off, so a stock checkout still uses the model wording path until the env var is set.
- Overview cards still repeat a short finding summary that also appears on the category detail.
- Lifestyle text is stored as a presence flag for the snapshot, not rendered on the current screens.
- Final biomarker copy replacement is Phase 2. Missing education stays empty.
- Visual redesign was not started.

## Phase 2

Replace registry copy, fold the blood-only and Bio-AI-only screens into the five-screen flow, and turn the snapshot flag on by default after the full suites stay at the Phase 0 failure set.
