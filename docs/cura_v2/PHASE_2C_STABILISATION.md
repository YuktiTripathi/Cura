# Phase 2C stabilisation

V2.3 remains the only curated education source. This phase adds canonical identities for the inventory rows the older registry did not name, and updates the tests that still expected the retired knowledge base.

## Biomarker identities

`backend/app/biomarkers/data/identity_extension_v2.json` adds one canonical id per inventory row whose `biomarker_id` was missing from the operational registry. The id is a slug of the laboratory name. Workbook keys stay on `content_key` and are not canonical ids. Provider parameter codes are null. Nothing was fuzzy-matched.

| Status | Count |
| --- | --- |
| Already in the operational registry | 114 |
| New canonical identity, provider code unconfirmed | 216 |
| Ambiguous slug collision | 0 |
| Inventory rows | 330 |

Ferritin is `ferritin`, linked to `WB-116`, category `blood_iron`. Its V2.3 text is what `education_for("ferritin")` returns. The provider id is still unconfirmed.

Allergy rows received distinct `allergen_…` ids when the clinical name was unique. Assay method stays whatever the library already recorded. Unconfirmed assays do not gain a new interpretation.

## Questionnaire

The 91 staging questions were not mapped to production keys. No local questionnaire definition export was treated as production. `lifestyle_personalisation_enabled()` stays false, so personalised lifestyle interpretations are not activated.

## HealthView

Education notes now carry the V2.3 body, why-it-matters, limitations, version, and review status. Category descriptions use the V2.3 category text when the row is eligible. Personal numbers are still copied from the provider payload. Exploration does not call a model.

## The 11 new failures

| Test | Class | Action |
| --- | --- | --- |
| Explanations attach to measured findings | Obsolete legacy sentence | Assert V2.3 ALT text and source |
| Misspelt and look-alike names | Obsolete display names | Assert V2.3 names and that urine sugar and fasting sugar stay different |
| Fixed category description | Obsolete hardcoded sentence | Assert the V2.3 liver description |
| HbA1c meaning provenance publishers | Obsolete legacy articles | Assert no blood-report source and no WHO/MedlinePlus article |
| Hypertension WHO citation | Obsolete legacy articles | Assert no blood report and no WHO article; still no SuperShyft call |
| Hyperthyroidism publisher list | Obsolete legacy articles | Assert no blood-report source |
| Thyroid “if high” empty provenance | Obsolete requirement that a legacy article be attached | Keep the no-SuperShyft assertions |
| HbA1c foods publisher list | Obsolete legacy articles | Assert the blood report is not cited |
| Lifestyle follow-up publisher list | Obsolete legacy articles | Assert the blood report is not cited |
| Bio-AI contrast provenance names | Obsolete guide title in provenance | Keep the personal-record classification; assert WHO/MedlinePlus are absent |
| Story influence sentence | Obsolete action-library sentence | Assert the V2.3 influence text is present |

`ContextMerger` still runs after V2.3 passages are attached, so personal context is not dropped with the old articles.

Two further tests expected Ferritin and Average Blood Glucose to stay unmapped. They now assert the new identity, and that a nonsense assay stays unmapped and that no provider id was invented.

## Suites

Backend, mock provider: **31 failed, 2110 passed, 4 skipped**. The previous run was 40 failed, 2104 passed. The 11 legacy-knowledge failures are gone. Two tests that forbade new identities were updated. The remaining 31 are the earlier prompt and routing failures plus `test_tests_outside_the_supplied_registry` and `test_exact_matches_only` if either is still listed after the assertion update. This run was started before that last assertion update, so those two names are in this 31. They were updated immediately after.

Frontend: **9 failed, 165 passed**. Same localStorage and MessageList failures as the previous frontend run.

## Cache and performance

Snapshot keys already include content version `2.3` and the preview or approved policy.

Measured on the mock provider, member `demo-user-001`, in-process cache:

- Cold `load_snapshot`: 0.836 s
- Warm `load_snapshot`: 0.002 s
- Exploration LLM calls on that path: 0

No separate HTTP timing, chat time-to-first-token, or Redis timing was recorded.

## Live integration

`SUPERSHYFT_DATABASE_URL` and `OPENROUTER_API_KEY` are present in the local environment. A provider read attempted while the process was pointed at SuperShyft returned unavailable for blood, Bio-AI, lifestyle, questionnaire, and profile. No live member scenario was completed, and no live model answer was checked. This is not a passing live test.

## Local run

```bash
export APP_ENV=development HEALTH_PROVIDER=mock MEMBER_SNAPSHOT_ENABLED=true
export MEDICAL_REQUIRE_REVIEWED=false
```

Production must keep `MEDICAL_REQUIRE_REVIEWED` on. Pending V2.3 rows stay pending. They are not marked clinically approved.
