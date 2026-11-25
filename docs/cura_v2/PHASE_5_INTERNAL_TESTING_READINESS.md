# Phase 5 — Internal testing readiness

The local working tree on `main` is what you run. No new architecture was added. Nothing was committed, pushed, or force-updated.

## Git

- Branch: `main`
- HEAD: `c23404a434563692f2a842e3e9f39c24efb0985a` — "Document live OpenRouter preview for CURA health explanations"
- Remote: `origin` `https://github.com/YuktiTripathi/Cura.git`
- `main` is **ahead of `origin/main` by 7 commits**
- The CURA 2.0 work (V2.3 library, health exploration, MemberSnapshot, conversational fixes) is in the **uncommitted working tree** on `main`, including untracked files under `backend/app/medical_content/`, `backend/app/snapshot/`, `frontend/src/components/explore/`, and `docs/cura_v2/`
- A clean checkout of `origin/main` does not contain that work. Do not reset or clean the tree before testing.

## How to run it locally

Backend, from `backend/`:

```bash
cd /Users/yuks/Desktop/Cura/backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

Frontend, from `frontend/`:

```bash
cd /Users/yuks/Desktop/Cura/frontend
npm run dev
```

Open http://localhost:5173. The landing screen is the original welcome. The exploration entry is the button **My Health Overview** (not a separate "Understand my health better" label). Back from the overview returns to that landing screen.

`backend/.env` already has the live development profile. These are the values that matter, without secrets:

| Variable | Local value |
| --- | --- |
| APP_ENV | development |
| AUTH_PROVIDER | mock |
| ALLOW_MOCK_AUTH_WITH_REAL_HEALTH | true |
| ALLOW_MOCK_HEADER_OVERRIDE | true |
| DEV_AUTH_HEADER | true |
| HEALTH_PROVIDER | supershyft |
| MEMBER_SNAPSHOT_ENABLED | true |
| ENABLE_LLM | true |
| LLM_PROVIDER | openrouter |
| JEV_ENABLED | true |
| JEV_MODEL | typesafe/jev-1.13 |
| MOCK_USER_ID | empty |

Answer models: fast and deep `openai/gpt-5.6-luna`, standard `openai/gpt-5-mini`. `OPENROUTER_API_KEY` and `SUPERSHYFT_DATABASE_URL` are set in `backend/.env` and are not recorded here.

## Choosing the member

Development auth uses the header `X-Cura-User-Id`. The Vite dev server sends `VITE_CURA_USER_ID` from `frontend/.env` as that header. `MOCK_USER_ID` is empty, so the header is the identity.

Set `VITE_CURA_USER_ID` in `frontend/.env` to the numeric SuperShyft user id you are authorised to use, then restart `npm run dev`. Do not put that id in git.

The id currently in `frontend/.env` is numeric. For that member, the read-only SuperShyft connection returned **1 blood report (66 markers)** and **1 Bio-AI report (8 risks)**. With MemberSnapshot enabled, `assemble_snapshot` produced a HealthView in state `ready`: **9 categories, 71 findings**. Library version **2.3**, content revision `eb4c71f82c4e`. No result values were copied into this document.

Five assay labels were logged as still needing a mapping review: Absolute Lymphocyte Count (ALC), Calculation, MENTZER INDEX 9MCV/RCC, MPV, RDW-SD. They are not treated as confirmed identities.

## What was verified, and what was not

Verified from the running code and the live read-only database:

- Settings match the requested development profile, including Jev on.
- SuperShyft is reachable and the configured member has blood and Bio-AI rows.
- HealthView assembly uses Medical Knowledge Library V2.3.
- Frontend unit tests: 41 files, 175 passed.
- Frontend production build succeeded.

Not done in this pass:

- A browser session through landing, categories, biomarkers, Bio-AI, chat, back-navigation, PDF upload, voice, or history. Those screens are in the current UI, but they were not clicked.
- A live chat turn against this SuperShyft member. Earlier conversational evidence used synthetic `demo-user-001`.

If the database is unavailable, the app should say the health information is unavailable. It should not fill the screen with mock personal values while `HEALTH_PROVIDER=supershyft`.

## Regression

Full backend suite on this tree, before one follow-up correction:

**50 failed, 2218 passed, 4 skipped** (8m 11s).

That is worse than the previous completed baseline of 33 failed / 2235 passed / 4 skipped. A cluster of the new failures expected a stored lookup to use the existing `structured_blood` path. A Phase 4.5 deterministic lookup shortcut was returning `deterministic_lookup` instead. That shortcut was removed so lookups keep the existing path when the model is enabled. After that removal, these passed:

- `test_ldl_present_returns_value_and_blood_report_source`
- `test_hba1c_present_returns_value_and_blood_report_source`
- `test_missing_ferritin_not_substituted`

The full suite was **not** run again after that removal, so 50 failed is the last complete count, not the count after the shortcut was taken out.

`tests/conftest.py` still pins `member_snapshot_enabled` off, so the default suite does not exercise the snapshot flag. The live check above called `assemble_snapshot` with the flag on in the process settings.

Failures that were already present include LangChain engine parity, follow-up prompt wording, same-day Bio-AI selection, report-overview shape, and user-isolation chat cases. They were not edited to force a pass.

## Known limits

- Safety-classifier read timeouts still occur. The configured timeout is 3 seconds. Measured waits in Phase 4.5 were about 3.1–3.9 seconds. The classifier stays on. Local rules still block recognised emergencies and medication changes.
- Time to first user-visible token is still not populated on ordinary chat responses.
- Questionnaire keys, provider parameter identifiers, and allergy assay formats remain unconfirmed. Lifestyle personalisation stays off.
- V2.3 rows stay `pending_clinical_review`. The approval workflow was not restored.
- Jev is enabled and still variable. The deterministic planner and the 0.80 confidence fallback remain the guard.
- The 2.0 product is only on this working tree until it is committed. That commit was not made.

## Production blockers

- Uncommitted `main` working tree, and `origin/main` does not contain it.
- Backend suite still has the failures above.
- Unconfirmed assay and questionnaire mappings.
- No browser pass and no live-model chat against the authorised SuperShyft member in this phase.
- Classifier timeouts and missing first-token timings.
