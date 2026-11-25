# Phase 2B knowledge migration

Medical Knowledge Library V2.3 at `backend/app/medical_content/library/` is now the only curated educational source on the active screen and chat paths. Older education files are no longer read as a fallback.

## Sources that used to supply education

| Source | Role before | Now |
| --- | --- | --- |
| `backend/app/biomarkers/data/biomarker_education_v1.json` | Fallback inside `education.py` | Not used by `education_for` |
| `backend/app/biomarkers/content/v2/` | Second fallback in `content_registry.py` | Not used for notes or risk text |
| `backend/app/biomarkers/content/v2_3/` | Duplicate copy of the library | Loader points at `medical_content/library` instead |
| `backend/app/retrieval/content/cura_biomarkers.json` and markdown articles | Chat `HybridMedicalKnowledgeProvider` | Chat no longer queries that provider for passages |
| `backend/app/retrieval/config/cura_biomarker_relationship_map.json` | Card related-marker expansion | Snapshot and card context use V2.3 relationships |
| `backend/app/biomarkers/health_categories.py` | Category sentences | Used for ids, names, and order. Description and about use V2.3 when the row is eligible |
| `backend/app/biomarkers/data/risk_registry_v1.json` | Operational risk codes and status grouping | Still used for grouping. Explanation text comes from V2.3 when eligible |

Authentication, SuperShyft adapters, numeric grounding, and safety rules are unchanged.

## Retrieval flow

1. Personal numbers still come from the provider snapshot.
2. `education_for` loads V2.3 through `biomarkers/medical_registry.py`.
3. A finding with no eligible V2.3 row keeps its value, unit, range, and status, and has no education note.
4. Chat, when knowledge is needed, calls `chat_passages` for the named markers and one hop of V2.3 relationships. It does not append legacy articles.
5. General questions that do not name a library entry get no curated passage. The model may answer from general knowledge under the existing safety checks.

`EducationNote` now carries `body`, `why_it_matters`, `limitations`, `content_version`, `review_status`, and `content_source=medical_knowledge_v2.3`. `what_it_is` is the V2.3 “what happens inside my body” text, not a shortened legacy line.

## Cache

Snapshot keys include content version `2.3` and `preview` or `approved`. An older payload cannot be served as the current snapshot.

## Eligibility

Historical note: this phase originally hid rows unless `review_status` was `human_clinically_approved`, with a development preview flag. That runtime gate has been removed. See `MEDICAL_CONTENT_GOVERNANCE.md`. The library text was not rewritten and was not marked approved.

Lifestyle personalisation stays off. Staging question ids are not treated as production keys.

## Mappings

`mapping_rows()` covers the 330 biomarker-file inventory rows.

- 114 exact canonical matches, where `biomarker_id` is already a registry id.
- 216 unresolved, including Ferritin (`WB-116`, `biomarker_id` null). `resolve_marker("Ferritin")` returns unmapped. The operational registry has no ferritin canonical id, so no id was invented.

Missing information for an unresolved row is a canonical id in `backend/app/biomarkers` that uniquely names that assay, or a provider parameter id from SuperShyft that matches one assay. Workbook keys are not used as production ids. No live SuperShyft parameter catalog was available in this run.

## Tests

`tests/unit/test_v23_exclusive.py`: 4 passed.

Full backend suite: **40 failed, 2100 passed, 4 skipped** in 356s. The previous baseline was 29 failed, 2104 passed. The same 29 remain. Eleven new failures are the tests that still expect the old education file, the old category sentences, or a legacy article in the prompt:

- `test_health_explanation_layer.py::test_story_validates_model_blocks_and_only_sends_category_context`
- `test_bio_ai_knowledge_base.py::test_why_my_risk_is_high_if_my_marker_is_normal_is_personal`
- `test_multi_source_context.py::test_medical_knowledge_only_hba1c_meaning`
- `test_provenance_and_routing.py`: `test_hypertension_general_uses_retrieved_who`, `test_hyperthyroidism_symptoms_use_retrieved_evidence`, `test_if_my_thyroid_is_high_does_not_query_supershyft`, `test_hba1c_foods_does_not_present_index_text_as_an_answer_when_llm_unavailable`, `test_lifestyle_hba1c_follow_up_stays_general`
- `test_unified_health.py`: `test_explanations_come_from_the_reviewed_file_and_attach_to_measured_findings_only`, `test_misspelt_lab_names_and_look_alike_tests_find_the_right_text`, `test_every_card_carries_its_fixed_description_from_the_registry`

The frontend suite was not re-run. A live SuperShyft database and a live OpenRouter call were not run.

## Local run

```bash
export APP_ENV=development MEMBER_SNAPSHOT_ENABLED=true
export MEDICAL_REQUIRE_REVIEWED=false
```

Production must leave `MEDICAL_REQUIRE_REVIEWED` on. Unapproved V2.3 text is then omitted and the older education file is still not used.
