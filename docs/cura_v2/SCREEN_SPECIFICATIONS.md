# Screen specifications

Implementation note: do not restyle components until the snapshot in `DATA_CONTRACTS.md` is the only source for these screens. Current UI pieces to reuse, not rewrite blindly:

- `frontend/src/components/overview/HealthOverviewView.tsx`
- `frontend/src/components/overview/SystemDetail.tsx`
- `frontend/src/components/overview/BiomarkerDetail.tsx`
- `frontend/src/components/overview/AskCuraActions.tsx`
- `frontend/src/components/risk/RiskExplanationView.tsx`

`BodySystemOverviewView` and `RiskOverviewView` fold into the category model. They are not a second product.

## 1. CURA Home

Data: snapshot flags (`has_blood`, `has_bio_ai`, category count) plus profile display name from `/me` when present. Welcome copy already branches on returning visits in `CuraPage` and `WelcomeExperience.tsx`.

Actions: open My Health Overview; focus the composer. No generated summary paragraph.

Empty: no reports. Say so. Do not show sample numbers.

## 2. My Health Overview

Data: `UnifiedOverview.categories` from the snapshot.

Each category row shows the registry name and description, measured counts, and predicted counts, using `MeasuredCounts` and `RiskCounts`. Rows with no findings for this member are omitted.

Measured and predicted are labelled separately on the row. Colour is not the only status signal (existing gap recorded in `docs/CURA2_AUDIT.md`).

Action: open category. Ask action sends `CardContext.category_id`.

## 3. Health category

Data: `categories[id]` from the snapshot. Opening it does not call the network if the snapshot already contains the detail.

Two groups:

- Measured. Name, value, unit, status label.
- Predicted. Name, classification or score, status label.

`build_story` model text is not rendered. Registry `about` and finding education are.

Action per row: open detail. Ask action includes `category_id` and the finding id.

Missing category: the empty state from the API 404 copy ("That health category has no results."), without a substitute essay.

## 4. Biomarker detail

Data: `Finding` with `source_type=measured`.

Show, in order: registry `what_it_is`; value, unit, reference range, date, report id; status label and `how_far` when the builder set it; `if_high` or `if_low` only for the matching status; related markers present on this snapshot.

If `data_quality` is `reference_unavailable`, say the report did not include a range. Do not invent one.

Ask action: `category_id`, marker code, report id.

## 5. Bio-AI risk detail

Data: `Finding` with `source_type=predicted_risk` plus the risk registry entry.

Show the registry description, the report score and classification, the date, and a fixed line that this is a prediction from the Bio-AI report, not a blood measurement and not a diagnosis.

Do not list causal "contributors" unless those contributors are fields on the provider DTO. They are not invented from the model.

Ask action: `category_id`, risk code.

## Conversation handoff

`AskCuraActions` already builds a `ContextRef`. Phase 1 extends that payload per `DATA_CONTRACTS.md` and keeps the user on the chat thread owned by `useCuraChat`. The overview stays mounted in memory so Back returns to the same snapshot.

## Accessibility already in the shell

Skip link, focus ring, and 44px touch targets were adjusted in earlier work (`docs/CURA2_AUDIT.md`). New screens keep those. Status is text plus colour.
