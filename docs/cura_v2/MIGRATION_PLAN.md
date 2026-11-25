# Migration plan

The running application stays on its current routes until the replacement passes the tests in `TESTING_STRATEGY.md`. No working SuperShyft integration is removed during the audit or during Phase 1 scaffolding.

## Principles

- Feature-flag the new snapshot reader. Default remains current `unified_service` behaviour until the flag is turned on in development.
- Old `/me/overview`, `/me/body-systems`, and `/me/bio-ai-risks` stay mounted until the client no longer calls them.
- Chat `POST /chat` and `/chat/stream` stay. Phase 1 only tightens evidence selection when a `CardContext` is present.
- No A2UI, no mock values on production code paths, no model calls on exploration reads.

## Phase 1 — data architecture (next)

1. Add `MemberSnapshot` assembly beside `build_unified_overview` in `backend/app/biomarkers/unified_overview.py` and `pipeline/unified_service.py`.
2. Build it from provider cache reads only. Pass `with_wording=False` and `allow_model=False` on this path. Do not call `unified_wording` or `build_story`.
3. Store the snapshot with the existing `overview_cache` key scheme, extended so category and finding slices are inside one payload.
4. Change `health_explanation` category and finding handlers to slice the snapshot. On miss, build the snapshot once, then slice.
5. Extend `ContextRef` with optional `category_id`. Plumb it through `AskCuraActions` and `useCuraChat` without changing the answer pipeline's safety gates.
6. When `category_id` or a finding id is present, restrict retrieval to those entities plus their registry entries. Leave free-text questions on the current planner.
7. Tests: snapshot contains no field that is absent from provider fixtures; navigation tests do not count extra provider calls; biomarkers package still does not import an LLM client.

Frontend in Phase 1 reads the snapshot once in `useHealthOverview` and selects category and finding locally when the payload includes them. Visual redesign waits.

## Phase 2 — five screens on the snapshot

Replace the `overviewKind` union in `CuraPage.tsx` with home, overview, category, biomarker, risk. Reuse the components listed in `SCREEN_SPECIFICATIONS.md`. Hide body-system and risk-only overviews behind the same flag, then delete their entry points after the unified screens cover both `source_type` values.

## Phase 3 — conversation narrowing

One core system prompt module. Card and free-text questions share it. Retrieval uses the relationship map only to add related markers that are in the snapshot. Drop screen-wording caches (`unified_wording` TTL) once no caller remains.

## Phase 4 — remove after green tests

Delete unused overview routes, prototype demo data if still unreferenced, and pipeline modules that only produced overview prose. Re-run the full backend and frontend suites. Keep adapters, auth, documents, voice, and conversation storage.

## Rollback

Flag off restores current handlers. Provider adapters and chat routes are untouched, so rollback does not require a data migration. Snapshot cache keys are new or versioned; old overview keys expire by the 600 second TTL.

## Out of scope until the snapshot is live

- New visual language
- Rewriting the entire `pipeline/` package
- Translating the clinical registry
- Writing health facts into SuperShyft
