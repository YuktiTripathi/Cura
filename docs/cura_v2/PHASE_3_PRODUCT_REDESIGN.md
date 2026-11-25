# Phase 3 product redesign

The live CURA page now opens on a home screen and walks through My Health, a category, a biomarker, and a Bio-AI risk using the HealthView already loaded for the member. The composer stays on the page. Chat opens when a question is sent and Back returns to the health screen without clearing it.

## What changed

- `frontend/src/components/explore/ExploreJourney.tsx` renders the five exploration screens.
- `frontend/src/pages/CuraPage.tsx` uses that journey instead of the separate blood, Bio-AI, and welcome overview modes.
- `frontend/src/styles.css` adds the home, result card, and touch-target styles.
- Older overview components remain in the repo for their existing tests. They are no longer the entry path.

Personal numbers and education text are read from the HealthView. The screens do not call a model and do not hardcode lab values. Suggested questions are capped at four and come from the view. A missing education note says the content is unavailable.

## Navigation

Home → My health → category → biomarker or Bio-AI risk. Asking a question hides the journey and shows the existing message list. Back shows the journey again at the same place.

## Tests

`ExploreJourney.test.tsx` covers home, category source labels, and biomarker education plus the reference range. The shell test still renders `CuraPage`.

The full frontend suite was not re-run after the syntax fix in this note. The previous full run was 9 failed, 165 passed. Those 9 are the existing localStorage and empty-bubble failures.

No live SuperShyft or OpenRouter smoke test was run for this UI pass. No screenshots were captured in this session.

## Limits

Lifestyle answers are not shown, because questionnaire mappings are still unconfirmed. Quantitative range bars are a text range, not a chart. Scroll position is not restored. Production still must not enable unapproved V2.3 content.

## Run

```bash
cd frontend && npm run dev
```

Set `MEMBER_SNAPSHOT_ENABLED=true` on the API so the health view returns data. Without that flag the home still loads and says health information is unavailable, and the composer still works.
