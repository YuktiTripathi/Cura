# Baseline backend test failures: triage

Last full run: 2052 passed, 27 failed, 4 skipped, 1 expected failure. The run began with 31 failures. No new failure appeared. No test was changed just to make it pass. Four tests were changed because they checked the wrong thing, and each change is explained below.

Tags: [Verified] I traced the cause. [Likely] classified from the failure message and code, not traced. [Open] not investigated.

Environment: the sandbox has no model or safety classifier access, so tests that depend on a live model result are covered only by fallbacks.

## Fixed or replaced since the first triage (4)

| Test | What was wrong | Action |
|---|---|---|
| test_requested_date_that_has_no_report_is_said_plainly | [Verified] Real defect. Asking for 2020-01-01 returned the 2026 result and never said there was no 2020 result. | Fixed the code. Test unchanged. |
| test_iron_deficiency_question_reads_the_whole_pattern | [Verified] The answer reads haemoglobin, MCV, ferritin and TIBC together with correct uncertainty. The test wanted the exact word "iron-deficiency". | Test replaced with a check that all four values appear, the answer says "taken together", says it cannot diagnose and leaves confirmation to a doctor. |
| test_presented_findings_carry_numeric_reference_bounds | [Verified] The trusted value, unit, range, date and source are in `experience.key_facts`. The old `presentation.findings` list is empty by design. | Test now reads `experience.key_facts`. |
| test_internal_ids_hidden_from_answers_but_kept_in_evidence | [Verified] Same cause. | Test now reads `experience.key_facts` and checks value, unit, range, date and source id. |

Correction to my earlier triage: I had said an empty `presentation.findings` might block the range visual. It does not. The data is complete in `experience.key_facts` and `semantic`.

Also fixed, not in the original list: a crash in `drop_routine_doctor`, and a follow up that turned "Is it serious?" into "What does is it serious mean in everyday terms?". Both have new tests.

## Remaining 27

### A. Check old prompt wording (about 11) [Likely]
The active prompt is the house prompt in `app/pipeline/prompt_builder.py`. These tests look for phrases from the legacy prompt. I checked that the house prompt contains the same safety rules in other words (not a diagnosis, never invent values, the report range decides, questionnaire answers are not lab results). I did not check every phrase. They should be replaced by one test of the active prompt's safety contract. This is a proposal, not done.
- test_conversational_personal: active_defaults, conflicts_resolved, safety_rules_are_kept, whole_report_score_note
- test_simple_explanations: more_simply, concept_first_simple_bullets
- test_blood_report_overview: overview_prompt_is_added_without_replacing_safety
- test_diagnostics_packages: prompt_forbids_hallucinated_package_metadata
- test_dynamic_format: system_prompt_plans_format_dynamically
- test_eval_dose_and_answer_shape: report_range_instruction
- test_presentation_policy: same_plain_language_policy
- test_response_quality_regressions: food_question_is_told_to_name_foods_first
- test_narrative_summary: expects "not a diagnosis"; the answer says "not diagnoses"

### B. Follow up cap (2) [Verified]
Code caps follow ups at four. Tests expect five. The CURA 2.0 brief says four. Update the tests to four.
- test_relationship_map: follow_up_cap_is_five
- test_semantic_answer_preservation: follow_ups_are_capped_once

### C. Behaviour that may matter for the redesign (open, not stale until proven)
- test_explanation_path omitted_bio_ai_score_is_added_from_the_record [Open]. If the model leaves out a Bio-AI score, the score is no longer added back. The product decision is to keep score transparency, so this test may describe wanted behaviour. Investigate first.
- test_pr10_completeness follow_up_keeps_the_retrieved_value [Likely]. The function is called without conversation context, so "it" resolves to nothing. End to end, a follow up keeps the value (acceptance test). The unit test should be rewritten with a resolved topic.
- test_dynamic_format follow_ups_are_the_models_own_and_specific [Open]. Follow ups were generic. Related to the open defect that personal follow ups run out after several turns.
- test_blood_report_overview (3 tests) [Likely]. They exercise the older blood overview path, probably replaced by the unified overview. Confirm and retire or update.
- test_audit_jev_confidence pcod_risk [Likely]. "Tell me my risk score for PCOD" now plans Bio-AI. The test expects blood only. The new behaviour looks right. Confirm.
- test_answer_tier_routing, test_conversation_state, test_diagnostics_packages iron studies name, test_brevity report table, test_followup_and_pageindex [Open]. Behaviour or data changed. Not traced.

### D. Prompt size [Verified]
test_personal_system_prompt_budget: 3409 characters against a budget of 3200. A real overrun that costs money and latency. Not a safety issue.

## Clinical content problems found while testing
Fixed, with tests in `tests/acceptance/test_product_acceptance.py`, wording still needs clinical review:
- Slightly high LDL: "often settle on their own" removed.
- In range ALT: "nothing that needs action" removed. The old test that required that phrase (`test_report_explainer`) was replaced, because it enforced an unsupported absolute.
- Low vitamin D: generic "at your next visit" referral replaced with a specific line.
- Follow ups no longer fall back to stock questions after several turns.

## Summary
- Release blocking: the unreviewed prioritization rules and replacement wording (see the UX spec sections 6 and 10).
- Could affect the redesign: C items on Bio-AI score, follow up relevance, and the older blood overview path.
- Unrelated baseline noise, to be cleaned up: A, B, D.
