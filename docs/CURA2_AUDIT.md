# CURA 2.0 audit and plan

Status: written after Stages 1 and 2. Findings come from reading the code. Nothing here was measured with real users, and no quality scores are claimed.

## 1. Current architecture
- Backend: FastAPI (`backend/app`). A query planner builds a `QueryPlan`. `ContextRef` says where a question came from (blood report overview, risk explainer, health area). A `TurnKind` registry (`pipeline/turn_kinds.py`) picks the behaviour for general, Bio-AI risk, health area and nutrition turns. `turn_cards.py` attaches cards. SuperShyft data comes through `integrations/supershyft`, with a mock provider for development.
- Unified overview: deterministic status rules and scenarios in `biomarkers/unified_overview.py`, category registry in `biomarkers/health_categories.py`, reviewed biomarker education in `data/biomarker_education_v1.json`, one cached model request for wording in `pipeline/unified_wording.py`. The `biomarkers` package never calls a model (guarded by a test).
- Frontend: React, TanStack Query, Vite, vitest. `CuraPage` owns the chat. `useCuraChat` handles streaming, processing steps and errors. `Composer`, `WelcomeExperience`, `HealthOverviewView` and the answer components render the UI. Types are generated from the OpenAPI schema.

## 2. Features to preserve
Streaming answers with friendly progress text, document upload and review, voice input, conversation history and edit-and-resend, feedback, follow-ups, the unified My Health Overview with category screens, the "About this test" expander, i18n helper `t()`, the skip link and focus ring, and the deterministic status rules.

## 3. Ten most significant UX problems
1. Errors showed raw `err.message` (fixed in Stage 1).
2. A failed send lost the typed question (fixed in Stage 1).
3. Clinical text was below 14px in several places (fixed in Stage 1).
4. Touch targets under 44px on chips and buttons (fixed for touch screens in Stage 1).
5. Reduced motion only covered the assistant bubble (fixed in Stage 1).
6. The welcome promised reports the person might not have, and had no returning greeting (fixed in Stage 2).
7. Biomarker values have no range visual, so "where am I" needs reading text. Open.
8. Status relies on colour and wording that can feel alarming for small deviations. Open.
9. Bio-AI risk wording can read like a diagnosis in some answers. Open.
10. No trend or multi-report comparison block, and follow-ups are not checked for repetition. Open.

## 4. Proposed architecture
Keep the backend contract. Add a small set of typed response blocks (biomarker card, risk card, comparison, document summary) rendered by one block renderer from trusted backend values. The model writes only the explanation text, never numbers or statuses. Design tokens live in `styles.css` custom properties.

## 5. Screen by screen plan
Welcome (done) then Chat (answer first, one next step, at most four distinct follow-ups) then Biomarker card, Risk card, Overview and category (done) then Comparison, Uploaded document review, Empty and error states (partly done).

## 6. Reuse and migration
Staged, each stage shipped and tested alone. Reuse `HealthOverviewView` finding rows for the biomarker card. Reuse the education file for "what this means". No wholesale frontend rewrite.

## 7. Unresolved dependencies
- Clinical review of plain status labels and risk wording before release.
- Hindi and Hinglish copy needs a native reviewer.
- Trend data needs a stable source of prior values per marker.
- 31 backend tests were already failing before this work; they are not triaged.
- Allergy results are excluded from the unified overview by existing logic.
- Real device testing (screen readers, small phones) has not been done.
