# Diagnostic packages and testing suggestions

CURA does not own a diagnostic product catalog. SuperShyft Postgres is the system of record for packages, test groups, and individual tests. CURA reads that catalog after medical reasoning and never lets inventory choose the tests.

```
User question
→ conversation state / Jev / HealthContext
→ medical reasoning
→ HealthGapDetector          (provider-independent)
→ TestNeedGenerator          (canonical biomarkers only)
→ PackageMatcher             (deterministic SuperShyft catalog)
→ PackageRecommendationPolicy
→ ResponseComposer / testing_option DTO
```

Medical need is decided before any SuperShyft product is loaded into the reasoner. The matcher receives canonical test keys, not the raw question.

## A. Relevant database tables

CURA SQLite (`conversations`, `messages`, documents, audit) has **no** diagnostic catalog tables. The tables below are in SuperShyft (`SUPERSHYFT_DATABASE_URL`, read-only via `integrations/supershyft/db.py`). Models live in SuperShyft `modules/diagnostics/models.py`, not in this repo.

### `diagnostic_package`

| | |
| --- | --- |
| Model | SuperShyft `DiagnosticPackage` |
| PK | `diagnostic_package_id` |
| Important columns | `package_name`, `diagnostic_provider`, `external_package_id` (Healthians), `price`, `original_price`, `min_price`, `status` (`active`/`inactive`), `gender_suitability`, `package_for`, `collection_type` (includes `home_collection`), `health_areas_covered`, `about_text`, `report_duration_hours`, `bookings_count` |
| FKs | `created_by_user_id` → `users.user_id` |
| Active/inactive | yes (`status`) |
| Pricing | yes |
| Provider/vendor | yes (`diagnostic_provider`; Healthians id in `external_package_id`) |
| Package→test mapping | no direct tests; via `diagnostic_package_test_groups` |
| Gender/age restrictions | `gender_suitability`; no age column |
| City/pincode | **not on this table** (checked at booking against Healthians) |

### `diagnostic_test_groups`

| | |
| --- | --- |
| Model | SuperShyft `DiagnosticTestGroup` |
| PK | `group_id` |
| Important columns | `group_name`, `group_key` (unique), `price`, `original_price`, `gender_suitability`, `package_for`, `display_order` |
| FKs | none to packages (junction is separate) |
| Active/inactive | **no status column** |
| Pricing | yes |
| Healthians IDs | no (tests under the group may have `external_parameter_id`) |
| Gender | `gender_suitability` |

First-class panels such as Iron Studies, Iron Studies with Ferritin, Thyroid Profile, Lipid Profile, Liver Profile, Complete Hemogram, Vitamin Profile, Diabetes Profile.

### `health_parameters`

| | |
| --- | --- |
| Model | SuperShyft `HealthParameter` |
| PK | `test_id` |
| Important columns | `parameter_key` (maps to `blood_parameters` JSON keys), `test_name`, `parameter_type` (`test`/`metric`), `is_available`, `external_parameter_id` (Healthians), `unit`, `price`, `gender_suitability`, reference ranges |
| Package mapping | via `diagnostic_test_group_tests` |
| Availability | `is_available` boolean (not the same as package `status`) |

### Junctions

**`diagnostic_package_test_groups`** — `id`; `diagnostic_package_id` → `diagnostic_package`; `group_id` → `diagnostic_test_groups`.

**`diagnostic_test_group_tests`** — `id`; `group_id` → `diagnostic_test_groups`; `test_id` → `health_parameters`. Unique `(group_id, test_id)`.

Supporting package UI tables (not used for matching): `diagnostic_package_reasons`, `diagnostic_package_tags`, `diagnostic_package_samples`, `diagnostic_package_preparations`, `diagnostic_package_filters_chips`, `diagnostic_package_filter_chip_links`.

User blood **results** (already used by CURA) live in `participant_blood_bookings.blood_parameters`, joined through `engagement_participants.user_id`. That is result history, not the sellable catalog.

## B. Package → test relationship

Yes, the database can answer both questions.

**Which tests are in package X?**

```
diagnostic_package
  → diagnostic_package_test_groups
  → diagnostic_test_groups
  → diagnostic_test_group_tests
  → health_parameters.parameter_key
```

SuperShyft already implements this as `DiagnosticsRepository.list_distinct_parameter_keys_for_package` and `GET /diagnostic-packages/{id}/tests`.

**Which available packages contain Ferritin + Iron + TIBC?**

Same join, inverted: canonicalize `parameter_key` values, keep packages/groups whose included canonical keys cover the requested set, drop `status != active` packages and `is_available = false` tests.

CURA path: `integrations/supershyft/diagnostics.py` (live SELECT) or `integrations/mock/data/diagnostic_catalog.json` (development/tests, names copied from SuperShyft seed). `PackageMatcher` scores coverage; it does not query via the LLM.

## C. Test-group support

Test groups are **first-class SuperShyft objects** (`diagnostic_test_groups`), not frontend labels and not the same as packages.

- Packages **compose** groups.
- Groups have their own names, keys, and prices and can be sold independently.
- Examples from seed: `Iron Studies`, `Iron Studies with Ferritin`, `Thyroid Profile`, `Lipid Profile`, `Liver Profile`, `Kidney Function with K`, `Complete Hemogram`, `Vitamin Profile`, `Diabetes Profile`.
- CURA matching considers **both** active packages and test groups, and prefers the smallest covering catalog item (a focused group over a 90-test package).

## D. Test-name normalization

There is **no** second biomarker ontology. SuperShyft `health_parameters.parameter_key` is the vendor slug (e.g. `vitamin_d_total-25_hydroxy`, `iron_serum`). CURA maps those through existing `canonicalize_marker_name` in `backend/app/pipeline/lab_parameters.py`.

| SuperShyft `parameter_key` / name | CURA canonical key |
| --- | --- |
| `iron_serum` / Iron Serum | `iron` |
| `ferritin` | `ferritin` |
| `tibc` | `tibc` |
| `transferrin_saturation` | `transferrin` |
| `vitamin_d_total-25_hydroxy` | `vitamin_d` |
| `haemoglobin` | `hemoglobin` |
| `ldl_cholestrol` (seed spelling) | `ldl` |

Aliases for SuperShyft slugs were added to `_SLUG_ALIASES`. Do not add a parallel mapping table.

## E. Booking / ordering path

CURA does **not** create diagnostic orders.

| Step | SuperShyft API (prefix `/book`) |
| --- | --- |
| Serviceability (pincode / Healthians) | `POST /book/check-service-availability` (also `/book/public/...` and `/book/code/{engagement_code}/...`) |
| Slots | `POST /book/available-slots` |
| Lock | `POST /book/lock` |
| Pay | `POST /book/pay` |
| Finalize blood | `POST /book/blood-test` |

Catalog browsing (not checkout): `GET /diagnostic-packages`, `GET /diagnostic-packages/{id}`, `GET /diagnostic-packages/{id}/tests`.

**Identifier for navigation:** `diagnostic_package_id` (or `group_id` for a test group). CURA `testing_option.catalog_id` carries that id so the SuperShyft frontend can open the existing package/group screen. Availability by city/pincode is a Healthians booking-time check; CURA does not call Healthians and does not pre-check pincode before mentioning an option.

## Architecture rules

- Medical reasoner never receives package names, prices, or inventory.
- Package names, prices, and included tests always come from the catalog query / seed JSON copied from SuperShyft.
- Inactive packages (seed example: **Fatigue**, id 23) are never surfaced.
- Acute symptoms (fever, chest pain, shortness of breath, neurological emergencies) set `package_suggestion_allowed = false`. Fever is not a 911 chat block; it only suppresses commercial testing options.
- No universal retest cadence (“Vitamin D every 3 months”). Follow-up language is contextual (previous date, comparison question, prior abnormality).
- Do not implement `if conversation_count > X: recommend_package()`.
- Development traces (`HEALTH GAP`, `TEST NEED`, `PACKAGE LOOKUP`, `RECOMMENDATION POLICY`, `FINAL SURFACED PACKAGE`) are logs + `meta.debug.diagnostics` when `APP_ENV` is development/test. Not shown to production users.

## Gaps that do not block this feature

- No pincode column on packages — booking-time only; CURA still may show a catalog id.
- Test groups have no `status` — CURA treats groups with available tests as matchable.
- `diagnostic_provider` / Healthians ids may be empty in seed; matching does not require them.
- CURA has no checkout; that remains SuperShyft.

## Patient-facing recommendation UX

Package suggestions never interrupt the medical answer. Order is: answer the question, explain the user's situation, then attach a testing option only if it adds value.

The LLM may explain why a measurement would help. It must not invent package names, included tests, prices, availability, URLs, or booking actions, and it must not render buttons or markdown CTAs. Catalog metadata and actions come from `PackageCatalog` / `TestingOption`.

Replace internal “catalog match” language with these states:

| Relevance | Headline |
| --- | --- |
| `HIGH_RELEVANCE` | A test that may help clarify this |
| `MODERATE_RELEVANCE` | This test may be worth considering |
| `OPTIONAL` | This is an option, although your current data already covers part of it |
| `NOT_RECOMMENDED_NOW` | You probably don't need to repeat this test right now |

Each card includes: headline, catalog name, one-sentence reason tied to the user's data, the gap it helps answer, 2–4 relevant included tests, whether those tests are already recent, one primary CTA, and an optional secondary CTA.

Default disclosure: package name, why it may help, primary button. Expanded: included tests, gap, recent duplicates with dates, timing, secondary action.

| Action | UI |
| --- | --- |
| `OPEN_PACKAGE` | Clickable control. Opens SuperShyft package/test-group detail from catalog id (`cura:open_package` / optional `VITE_SUPERSHYFT_APP_URL`). |
| `COMPARE_WITH_EXISTING_RESULTS` | Clickable control. Shows included tests, tests the user already has with dates, and tests that would add information. |

`NOT_RECOMMENDED_NOW` still answers “do I need another test?” without pushing a purchase: compare-first, no “View test group” plain text. Acute/emergency symptoms suppress routine preventive packages entirely. Duplicate surfacing in the same topic is declined.

Frontend: `frontend/src/lib/packageActions.ts`, `MessageList` testing-option card. Do not render `cta_label` as markdown.

## Files

| Role | Path |
| --- | --- |
| DTOs | `backend/app/contracts/diagnostics.py`, `presentation.py`, `chat.py`, `conversation_state.py` |
| Gap / need / match / policy | `backend/app/pipeline/health_gaps.py`, `test_need.py`, `package_matcher.py`, `package_policy.py`, `testing_option.py` |
| Catalog adapter | `integrations/supershyft/diagnostics.py`, `integrations/mock/data/diagnostic_catalog.json` |
| Canonical aliases | `backend/app/pipeline/lab_parameters.py` |
| Chat wiring | `backend/app/pipeline/service.py`, `composer.py`, `safety.py`, `conversation_state.py`, `prompt_builder.py` |
| UI | `frontend/src/types/chat.ts`, `MessageList.tsx`, `useCuraChat.ts`, `lib/packageActions.ts`, `styles.css` |
| Tests | `backend/tests/unit/test_diagnostics_packages.py` |

## Seed names used in development (not invented)

Active packages include **Supershyft Basic**, **Supershyft Core**, **Peak Performance Women**. The smallest covering item for ferritin + iron + TIBC in seed data is the test group **Iron Studies with Ferritin** (group 31). **Iron Studies** (group 30) has iron/TIBC/transferrin but not ferritin. Among active *packages*, **Peak Performance Women** (id 12) is the one that includes ferritin. Inactive **Fatigue** (id 23) also contains ferritin and must never be recommended.

Vitamin D (`vitamin_d_total-25_hydroxy`) appears in **Vitamin Profile** (group 34) and in packages such as **Supershyft Core**. Metabolic/glycemic panels include **Diabetes Profile** and **Diabetes Profile Pro**.

## Examples (catalog names from SuperShyft seed only)

**Missing iron information.** Low haemoglobin, MCV, MCH, and serum iron, no ferritin → medical rationale names ferritin → matcher surfaces **Iron Studies with Ferritin**, not inactive **Fatigue**, and not **Peak Performance Women** unless that group is unavailable.

**Stale Vitamin D.** Previous low Vitamin D and “Has my Vitamin D improved?” → updated measurement language with the last date → **Vitamin Profile** if it covers Vitamin D.

**Metabolic testing.** HbA1c + fasting glucose → **Diabetes Profile Pro**. HbA1c alone → smaller **Diabetes Profile**.

**Explicit catalog question.** “Which SuperShyft package includes ferritin?” → deterministic lookup → **Iron Studies with Ferritin**. No diagnosis.

**Acute fever.** “I feel feverish today, should I get tested?” → guidance, `package_suggestion_allowed = false`, no catalog card.
