# Baseline backend test failures (31): triage

Method: I ran the 31 failing tests alone and read each failure message and the code path it exercises. I traced the root cause in depth only for the items marked "traced". The rest are classified from the assertion, so treat those as likely, not proven. No test was edited to make it pass.

Environment note: the sandbox has no model or safety classifier access (`safety_classifier status=degraded error=ProxyError`), so any test that needs a live model result depends on fallbacks.

## A. Stale tests: they check old prompt wording (12)
The active prompt is the "house" prompt in `app/pipeline/prompt_builder.py`. Tests still look for phrases from the legacy prompt. The house prompt carries the same safety rules in its own words (traced: not a diagnosis, never invent values, report range decides, questionnaire answers are not lab results). Needs a decision: replace these with one test of the active prompt's safety contract.
- test_conversational_personal: active_defaults, conflicts_resolved, safety_rules_are_kept
- test_simple_explanations: more_simply, concept_first_simple_bullets
- test_blood_report_overview: overview_prompt_is_added_without_replacing_safety
- test_diagnostics_packages: prompt_forbids_hallucinated_package_metadata
- test_dynamic_format: system_prompt_plans_format_dynamically
- test_eval_dose_and_answer_shape: report_range_instruction
- test_presentation_policy: same_plain_language_policy
- test_response_quality_regressions: food_question_is_told_to_name_foods_first
- test_narrative_summary: wants the phrase "not a diagnosis", answer says "not diagnoses" (wording only)

## B. Stale against the new spec (2)
Follow-ups are capped at four now; tests expect five. The CURA 2.0 brief says at most four. Update the tests to four.
- test_relationship_map: follow_up_cap_is_five
- test_semantic_answer_preservation: follow_ups_are_capped_once

## C. Real findings that affect the redesign (must decide or fix before release)
1. Fixed in this change (traced): `drop_routine_doctor` crashed on any non-bullet line containing a routine "see your doctor" sentence, which failed the whole chat turn (for example "What is my latest Vitamin D?" in the fallback path). Regression test added.
2. test_requested_date_that_has_no_report_is_said_plainly (traced): asking for a HbA1c on 2020-01-01 returns "Stored results for the requested dates: HbA1c 5.5 on 2026-08-18" and never says there is no 2020 result. Misleading. Fix before release.
3. test_presentation findings (internal_ids_hidden, presented_findings_carry_numeric_reference_bounds) (traced): a single value answer has `presentation.findings == []`, so the numeric range is not available to a biomarker card from that field. The card must be built from another trusted field, or findings must be filled. Blocks the range visual.
4. test_pr10_completeness follow_up_keeps_the_retrieved_value and test_explanation_path omitted_bio_ai_score_is_added: when the model leaves out a number, the backstop does not add it back for follow-ups, and the Bio-AI score is no longer added. Whether to show the raw Bio-AI score at all is a product decision (see spec section 5). Decide, then fix or retire the test.
5. test_dynamic_format follow_ups_are_the_models_own_and_specific: follow-ups came back generic. Affects follow-up relevance.
6. test_blood_report_overview (KeyError entry_point; whole report not kept): the old blood overview path. Probably superseded by the unified overview; confirm before deleting.
7. test_answer_tier_routing, test_audit_jev_confidence (PCOD risk now plans Bio-AI), test_conversation_state (ALT then supplement), test_conversation_quality iron pattern, test_diagnostics_packages iron studies name, test_brevity report table, test_followup_and_pageindex (110 vs 130): behaviour changed or data differs. Not traced. Investigate individually; none is known to be release blocking.

## D. Prompt size
test_personal_system_prompt_budget: the personal prompt is 3409 characters against a 3200 budget. A genuine budget overrun, not a wording issue. Cost and latency only.

## Summary
Unrelated baseline noise: groups A, B, and D. Could affect the redesign: items 3, 4, 5. Fix before release: items 1 (done), 2, 3. Everything in item 7 is open.
