# Testing strategy

## How to run

Backend, from `backend/` with the project virtualenv:

```bash
source .venv/bin/activate
PYTHONPATH="/Users/yuks/Desktop/Cura/backend:/Users/yuks/Desktop/Cura" python -m pytest -q --tb=no
```

Frontend:

```bash
cd frontend
npm test
```

CI runs the same pytest job plus a Postgres migration job, and `npm test` with `npm run build` (`.github/workflows/ci.yml`). Tests default to `ENABLE_LLM=false` and mock providers (`docs/testing.md`). They are not clinical validation.

## Baseline for this audit

Commands were run on 2026-11-24 from this working tree. Results are filled in below when the processes finish. An earlier triage (`docs/BASELINE_TEST_TRIAGE.md`) recorded 2052 passed, 27 failed, 4 skipped, 1 expected failure. Those failures are mostly stale prompt-phrase assertions. Phase 1 does not "fix" them by editing expectations unless the assertion is wrong for the active contract.

### Backend

Command finished in 385.30s with exit code 1.

`29 failed, 2092 passed, 4 skipped, 1 warning`

Failed tests:

- `tests/quality/test_conversational_personal.py`: `test_active_defaults_are_the_legacy_rich_path`, `test_conflicts_resolved_in_system_prompt`, `test_safety_rules_are_kept`, `test_whole_report_score_note_skips_reassuring_scores`
- `tests/quality/test_simple_explanations.py`: `test_personal_prompt_asks_for_concept_first_simple_bullets`, `test_more_simply_reanswers_the_previous_question`, `test_personal_system_prompt_budget`
- `tests/unit/test_answer_tier_routing.py`: `test_tier_is_recalculated_per_turn_with_context_and_one_call_each`
- `tests/unit/test_audit_jev_confidence.py`: `test_pcod_risk_high_confidence_jev_lookup_is_not_overridden`
- `tests/unit/test_blood_report_overview.py`: `test_button_sets_overview_marker_and_plain_report_text_does_not`, `test_overview_keeps_the_whole_latest_report_and_dated_history`, `test_overview_prompt_is_added_without_replacing_safety`
- `tests/unit/test_brevity_and_relevance.py`: `test_report_table_appears_when_explicitly_requested`
- `tests/unit/test_conversation_state.py`: `test_alt_meaning_then_supplement_answer_continues_liver_interpretation`
- `tests/unit/test_diagnostics_packages.py`: `test_chat_iron_pattern_may_surface_iron_studies_with_ferritin`, `test_prompt_forbids_hallucinated_package_metadata`
- `tests/unit/test_dynamic_format.py`: `test_system_prompt_plans_format_dynamically`, `test_follow_ups_are_the_models_own_and_specific`
- `tests/unit/test_eval_dose_and_answer_shape.py`: `test_report_range_instruction_is_in_the_personal_prompt`
- `tests/unit/test_explanation_path.py`: `test_omitted_bio_ai_score_is_added_from_the_record`
- `tests/unit/test_followup_and_pageindex.py`: `test_prompt_package_keeps_history_and_questionnaire`
- `tests/unit/test_narrative_summary.py`: `test_chat_health_summary_does_not_dump_the_full_report`
- `tests/unit/test_pr10_completeness.py`: `test_follow_up_keeps_the_retrieved_value`
- `tests/unit/test_presentation_policy.py`: `test_personal_prompt_uses_the_same_plain_language_policy`
- `tests/unit/test_relationship_map.py`: `test_follow_up_cap_is_five_and_medication_is_still_rejected`
- `tests/unit/test_response_quality_regressions.py`: `test_food_question_is_told_to_name_foods_first`
- `tests/unit/test_semantic_answer_preservation.py`: `test_follow_ups_are_capped_once_and_unsafe_ones_stay_rejected`

Most of these match the earlier triage in `docs/BASELINE_TEST_TRIAGE.md`: assertions against retired prompt phrases, a follow-up cap of five versus the code cap of four, and a few chat-behaviour checks. They were not modified in this audit.

### Frontend

`npm test` in `frontend/` finished in 12.45s with exit code 1.

`Test Files  3 failed | 36 passed (39). Tests  9 failed | 163 passed (172).`

Failures:

- `src/lib/theme.test.ts` (3): `window.localStorage.clear` / `getItem` is not a function in this Vitest environment.
- `src/components/messages/Companion.test.tsx` (5): same `localStorage.clear` failure in `afterEach`.
- `src/components/MessageList.test.tsx`: `does not render an empty bubble for the assistant placeholder` expected 0 assistant articles and found 1.

No application code was changed to chase these failures.

## Phase 1 tests to add

| Case | Assertion |
| --- | --- |
| Snapshot from mock fixtures | Every value, unit, range, score, and classification equals the fixture row |
| Unknown marker | Education omitted; value still present if the lab row has it |
| Category open | No additional provider method call when the snapshot is warm |
| Finding open | Same |
| Wording flag | Screen builder does not call `get_llm_client` |
| Card context | Retrieval evidence ids are a subset of the card entity and its related markers that exist on the snapshot |
| Isolation | Principal A cannot read principal B's snapshot key |
| Chat regression | Existing golden and safety tests still pass with the flag off |

Safety tests under `backend/tests/safety` stay a release gate, as in CI.

## What not to test with production numbers

Do not paste real member rows into git. SuperShyft checks use the read-only adapter against a non-production database or the existing mock JSON in `integrations/mock/data/`.
