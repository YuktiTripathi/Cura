# Medical Knowledge Library V2.3, education upgrade (revision 2.4)

Status: general education pending clinical review. Nothing in this revision is clinically approved, and no
claim is marked evidence verified. Production chat still receives only rows that are clinically approved
with verified evidence (`medical_library_chat_access = approved_only`).

## What changed

The authoritative V2.3 files were rewritten in place. There is no second library. The build is
reproducible from main before the upgrade (a61785d):

```
python backend/app/medical_content/library/tools/education_upgrade/apply.py   # content, relationships, evidence map
python backend/app/medical_content/library/tools/education_upgrade/audit.py   # writing and coverage audit
python backend/app/medical_content/library/validate_content.py                # structural validation
```

The base text comes from the revision 2.3.1 modules in `tools/education_upgrade/`. The `*_x.py` modules add the
education standard and the corrections from the sample review. Identifiers, provider test names, canonical
mappings, result states and assay notices are carried over unchanged.

## Content coverage

| Area | Entries | Coverage |
| --- | --- | --- |
| Biomarkers | 119 of 119 | Every entry explains how each influencing factor acts (561 factor explanations). 117 have common misconceptions (2 record why none apply). 44 have keeping_healthy and 75 record why habits do not set the result. 24 have lowering_risk. 47 have everyday improvement steps and 72 record why lifestyle advice does not apply. 13 have a note separating the lab range from clinical thresholds. |
| Allergens | 211 of 211 | Every entry describes the substance and where it is met in India. 114 have established cross-reactivity, 97 record that none is established, and 20 carry a severity note. |
| Bio-AI | 12 of 12, including PCOS and metabolic age | Every entry has factor explanations, keeping_healthy, a risk band meaning that invents no target, horizon or probability, and misconceptions. |
| Health categories | 15 of 15 | Organ and system education and why it matters. 11 have keeping_healthy, 6 lowering_risk and 13 misconceptions. Card short descriptions are unchanged. |
| Biomarker relationships | 219 directed (113 pairs) | Every pair has `reading_together`, which explains what the combination shows. |
| Lifestyle relationships | 31 of 31 | Individual explanation and limitation for each. |

Lifestyle advice was not manufactured where it does not apply. Tumour markers, white cell types, bilirubin
fractions, ratios, ESR, most urine findings and similar results record a reason instead.

## Corrections applied across the library

- One result below a diagnostic threshold does not rule out diabetes.
- An encouraging HbA1c does not end health maintenance and says nothing about cholesterol, blood pressure or liver fat.
- HDL concentration is not the same as how well HDL works.
- Low B12 is one possible cause of large red cells, not the confirmed cause.
- Fortified foods are included as sources of B12.
- ALP is normally higher in pregnancy, which is explained separately from bone building.
- MASLD and MASH terminology and criteria replace NAFLD and NASH, including the requirement for a metabolic risk factor.
- The oxidative stress and all other Bio-AI bands are described without an invented target or probability.
- Metabolic age makes no claim about method, comparison group or the meaning of the gap.
- Every ESR factor is explained, including thyroid disease and the conditions that lower ESR.
- Lab reference ranges are kept apart from clinical thresholds for HbA1c, fasting sugar, HDL, lipids, eGFR, vitamin D, TSH, ferritin and Lp(a).
- These claims were corrected against source pages read for this revision:
  - eGFR: NIDDK says below 60 may mean kidney disease. No three-month rule was found on that page.
  - Fasting sugar: diabetes is usually confirmed with a second test.
  - Vitamin D: the NIH ODS cut-offs are used, and toxicity is described as nausea, kidney stones and kidney damage.
  - Triglycerides: the fasting wording follows MedlinePlus.
  - CK and biotin interference.

## Evidence coverage

`evidence/claim_evidence_map.json` has one row for each of the 6,392 reader-facing claims. Each row records
the claim type: mechanism, interpretation, influencing factor, threshold, prevention, practical guidance,
escalation or relationship.

| Status | Claims |
| --- | --- |
| page_read_supports_claim (a source page was opened, read and states it) | 93 |
| candidate_sources_unverified | 6,297 |
| metsights_product_information_not_medical_evidence | 2 |

29 source pages read during this review are registered in `evidence/content_sources.json`. A claim that a
page supports is still not clinically approved. Claim-level verification of the remaining 6,297 claims is
the largest release blocker.

## Retrieval and the model request

`chat_passages` still returns at most eight lines and uses the same eligibility and draft labelling as
before. Each type of question receives only the fields it needs:

- **Why or cause questions:** up to four factors, each with how it acts.
- **Food questions:** factors, plus everyday steps for an out-of-range result or keeping_healthy for an in-range one.
- **Result questions:** the member's own result state, the lab range versus threshold note, one misconception and, for Bio-AI, the band meaning.
- **Relationship questions:** how the two results connect and what they show together.

The system prompt, MemberSnapshot, routing and the CURA 1.0 follow-ups are unchanged.

Tests capture the real model request at the network edge:

- `tests/unit/test_library_reaches_llm_request.py`: in evaluation mode the request carries explained factors, thresholds and pair readings, and production withholds them.
- `tests/unit/test_education_reaches_contrasting_profiles.py`: synthetic members with low and normal vitamin D, a prediabetes range HbA1c and an iron pattern each get their own values and matching education, never another member's.

## Validation results

- Structural validation passed: 330 entries, 114 mapped IDs, 219 directed relationships.
- Audit (`audit/education_audit_2_4.json`):
  - No missing education fields and no dash characters in written content.
  - No allergen description is shared by more than one entry.
  - Two term flags are false positives, because the term is explained in the same sentence.
  - 23 repeated sentences sit outside the shared register for review. Most are system-level guidance shared within one family.
- Backend suite: 2,299 passed, 11 failed, 4 skipped. The same 11 fail on unchanged main, and the upgrade causes no new failures.

### The 11 failing tests

10 have failed since the repository's first commit. They are not caused by the library:

- **Three questionnaire tests:** the planner sets `needs_blood` or `needs_questionnaire` more broadly than the tests expect.
- **`test_phase4_quality_scenarios` q52 and q91:** general cholesterol questions are planned with personal blood data.
- **`test_house_prompt` broad nutrition:** a focused LDL question also requests Bio-AI.
- **`test_capability_eval`:** a general exercise question is routed to personal lookup.
- **`test_conversation_state`:** an ALT continuation produces no follow-up chips.
- **`test_phase10_general_starters`:** no follow-up is produced for a general second turn.
- **`test_theme_followups`:** two chips are returned instead of four.

One began failing at commit 0b591ae ("Kb updated"). `test_dynamic_format::test_follow_ups_are_the_models_own_and_specific` now receives no follow-ups after that commit's follow-up generator and prompt change.

These tests describe routing and follow-up behaviour that the brief asked to preserve, so neither the
tests nor the routing were changed. The product owner should decide whether the tests or the behaviour
reflect the intended design.

## Remaining release blockers

1. Clinical review and sign-off of every entry. All 607 rows are pending_clinical_review.
2. Claim-level evidence verification of 6,297 claims, starting with thresholds, escalation advice and Bio-AI wording.
3. 216 unresolved production canonical IDs (`inventory/unresolved_mappings.json`).
4. 234 entries need assay or result-format confirmation (all allergens and many urine items).
5. Production questionnaire keys are unconfirmed. The staging question IDs are not production keys, so lifestyle personalisation stays limited.
6. MetSights has not published the formula, prediction target, time horizon or reference population for any Bio-AI score.
7. Independent semantic writing review, including the 23 repeated sentences listed by the audit.
8. A decision on the 11 failing routing and follow-up tests.
