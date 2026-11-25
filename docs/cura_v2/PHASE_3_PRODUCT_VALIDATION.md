# Phase 3 product validation

The existing CURA page is what runs. No second app was added.

## Original landing screen

CURA opens on the existing `WelcomeExperience` again: the same greeting, lead line, capability cards, starter chips, composer, history, voice, and PDF attachment. That component was not rewritten.

My Health Overview on that screen opens the new exploration at My Health. It does not show the newer home screen. Back from My Health returns to the original landing screen. Deeper screens still use `ExploreJourney`.

Conversational follow-ups now put the model's own questions first, after the existing personal-data and generic-question filters, then fill up to four with the current generator. Category and biomarker screens still use the curated V2.3 questions and do not call a model. No earlier education file was switched back on.

## The three extra backend failures

Compared with the 29-failure list in `docs/cura_v2/TESTING_STRATEGY.md`, the extra three were:

- `test_refresh_returns_the_same_shape_and_category_and_finding_endpoints_work`. The local `.env` turned MemberSnapshot on, so the category payload had no generated story. The suite now pins `member_snapshot_enabled` off, which is the shipped default. The test passes.
- `test_ask_cura_context_ref_retrieves_server_value`. Same flag. With the snapshot planner on, "Explain this" stayed a general question and did not read the blood report. With the flag pinned off, the test passes.
- `test_every_question_and_chain_gives_the_same_response_on_both_engines`. The two engines differed by one follow-up and a safety-flag count while the safety classifier timed out (`ReadTimeout`). That is an environment failure, not an assertion to edit. It still fails.

## What is ready

- Home, My Health, a category, a biomarker, and a Bio-AI risk all render from HealthView.
- A biomarker shows the result, unit, status, collection date, a two-sided range bar when both limits exist, and plain text for a one-sided range, a missing range, or a result with no number.
- The biological explanation, the result interpretation, and why the test matters come from the eligible V2.3 fields. Missing text says it is unavailable.
- A previous result is shown only when the view already has one. No trend is invented.
- Related biomarkers link to the other finding in the same view.
- Suggested questions stay at four.
- A Bio-AI page uses the four requested headings, the curated explanation, the reported classification and score, and an Ask CURA action. It does not draw a diagram or invent a cause.
- Blood results and Bio-AI risks stay on one category page, labelled Measured and Predicted.
- Lifestyle text stays off because questionnaire mappings are not verified.
- Back from chat returns to the same place and restores the scroll position that was saved. The conversation stays in memory.
- An assistant message with no text and no loading state is not rendered. A loading state still shows while processing events are present.
- The composer, voice button, and PDF attachment stay on the page.

## Local run

The development `.env` now has `APP_ENV=development`, `HEALTH_PROVIDER=supershyft`, `MEMBER_SNAPSHOT_ENABLED=true`, `MEDICAL_REQUIRE_REVIEWED=false`, `ENABLE_LLM=true`, and `LLM_PROVIDER=openrouter`. Credentials were not printed or copied into this document.

```bash
cd backend && PYTHONPATH=.. .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
cd frontend && npx vite --host 127.0.0.1 --port 5173
```

Open http://127.0.0.1:5173/. For fixture data instead of SuperShyft, start the API with `HEALTH_PROVIDER=mock`.

A mock API is currently serving port 8000, and Vite is on 5173. Restart the API without that override to use SuperShyft.

## Live connectivity

SuperShyft accepted a read-only probe: configured, reachable, query ok, about 193 ms. The earlier failure was the URL scheme `postgresql+asyncpg`. The app rewrites that to `postgresql+psycopg` before connecting. `psycopg` is installed. `asyncpg` is not, and it does not need to be.

The database has 2,791 individual health report rows across 1,662 members. `MOCK_USER_ID` is empty, so development falls through to subject `2`, and that subject has no report rows. Set `MOCK_USER_ID` to your own authorised numeric SuperShyft user id before expecting personal results. No member id was written into the app or this document.

OpenRouter returned HTTP 200 for a four-token check. No health data was sent.

## Journey checked

With the mock provider, the open app loaded a HealthView (HTTP 200) and My Health showed Heart & Circulation with the fixture report dates. Home, the composer, voice, and PDF attachment were on the page. HDL, bilirubin, creatinine, ferritin, HbA1c, a live chat reply, PDF upload, and voice capture were not each clicked through. The configured live member has no reports, so those paths were not filled with invented results.

## Tests

Frontend after restoring the landing screen: 41 files, 175 tests, all passed. The production build succeeded. The full backend suite then finished in 9 minutes 25 seconds: 31 failed, 2110 passed, 4 skipped. That is two fewer failures than the run with MemberSnapshot left on. The remaining extra failure against the 29-failure baseline is the LangChain engine comparison, plus `test_routing_and_classifier_overlap`, which failed while the safety classifier timed out. The previous localStorage failures were the test environment (`localStorage.getItem` missing). A setup file supplies storage only when the environment does not. The empty assistant assertion now passes because an empty assistant message is not rendered.

Production frontend build succeeded.

The backend suite finished in 9 minutes: 32 failed, 2109 passed, 4 skipped. The earlier baseline was 29 failed. The new failures are prompt, follow-up, and routing assertions, not the health-view screens. They were not each reclassified in this pass.

## Layout

Desktop home was inspected in the browser. The introduction line was clipped by the main column. The exploration sections now use `min-width: 0` and a max width that stays inside the column. The 375, 390, 430, 768, and 1440 sizes were not each measured after that fix.

## Screenshots

Screenshots were not added to the repository. The browser session showed a real display name and existing conversation titles. Those images would identify someone.

## Release blockers

- V2.3 content is still pending clinical review. Preview is on only because this environment sets `MEDICAL_REQUIRE_REVIEWED=false`.
- The development subject has no SuperShyft reports until `MOCK_USER_ID` is an authorised member who has them.
- Provider parameter ids for the identity extension are still unconfirmed.
- Phase 4 has not started.
