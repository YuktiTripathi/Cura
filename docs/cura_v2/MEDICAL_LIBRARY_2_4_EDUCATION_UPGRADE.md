# Medical Knowledge Library V2.3, education upgrade (revision 2.4)

Status (27 Nov 2026): CURA uses this library in every environment under one rule: any row that is not
rejected is used. There is no per-entry clinical approval workflow. No row is marked clinically approved,
and only claims checked against a source page are marked as supported by evidence. See
`MEDICAL_CONTENT_GOVERNANCE.md`.

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

`evidence/claim_evidence_map.json` has one row for each of the 6,393 reader-facing claim rows (4,316 distinct
claims). Each row records the claim type: mechanism, interpretation, influencing factor, threshold,
prevention, practical guidance, escalation or relationship.

| Status | Claim rows | Distinct claims |
| --- | --- | --- |
| page_read_supports_claim (a source page was opened, read and states it) | 576 | 123 |
| candidate_sources_unverified | 5,815 | about 4,190 |
| metsights_product_information_not_medical_evidence | 2 | 2 |

The verified claim rows outnumber the distinct claims because the allergen limitation and emergency
advice repeat across most of the 211 allergen entries.

46 source pages read during the review are registered in `evidence/content_sources.json`. Verification
was prioritised as follows:

| Area | Supported by a page read |
| --- | --- |
| Thresholds | 12 of 13 notes. The ferritin note is unverified and is not sent to the model. |
| Allergen limitation and emergency signs | Supported on the entries that carry them |
| Influencing factors | 77 claims |
| Result interpretations | 29 claims |
| Relationship readings | 6 pairs |
| Nutrition and prevention | 23 claims |

Claims corrected or removed because the page did not support them:

- **eGFR:** the three-month rule was removed.
- **Fasting sugar:** the wording on repeat tests was corrected.
- **Vitamin D:** the cut-offs and toxicity wording were corrected.
- **Triglycerides:** the fasting wording was corrected.
- **CK:** the injection factor was removed.
- **TSH:** the older-adult target was removed.
- **Ferritin:** the claim about the most common causes was removed.
- **Anaphylaxis:** the signs were corrected.
- **MASLD:** the alcohol wording was corrected.
- **Potassium:** the sample-handling and medicine factors were corrected.
- **Homocysteine:** the wording on lowering it and heart risk was corrected.

## Retrieval and the model request

The fixed eight-line cap was replaced. `chat_passages` ranks passages by relevance and keeps them within a
token budget set by question type:

- a definition: about 220 tokens
- how the body works: 380
- a result, cause or relationship question: 520
- improving health: 560
- food: 620

Each extra result the person names or that is out of range adds 200, and a whole-report question adds 300,
up to 1,600. Questions that name an organ get that health category's education. Threshold notes are sent
only when a source page supports them. Entries are never sent whole.

The system prompt, MemberSnapshot, routing and the CURA 1.0 follow-ups are unchanged.

`scripts/library_answer_quality.py` runs 12 questions from five contrasting synthetic members through the
real chat pipeline. It covers:

- how the body works
- what a test measures
- encouraging and abnormal personal results
- related findings
- maintenance, improvement and modifiable risk
- food

For each question it records the member values and curated knowledge in the exact model request, the final
answer and the follow-ups.

In capture mode every request carried the member's own values and matching knowledge, sized from 122 tokens
for "What does HbA1c measure?" to 1,446 for a three-result question. That run found and fixed two retrieval
gaps: organ questions and questions about what a test measures.

The configured model (openrouter.ai) is blocked by this environment's network proxy, so final model answers
were not generated here. Run the script with `--mode live` and your credential to read them.

## Validation results

- Structural validation passed: 330 entries, 114 mapped IDs, 219 directed relationships.
- Audit (`audit/education_audit_2_4.json`):
  - No missing education fields and no dash characters in written content.
  - No allergen description is shared by more than one entry.
  - Two term flags are false positives, because the term is explained in the same sentence.
  - 23 repeated sentences sit outside the shared register for review.
- Backend suite: 2,313 passed, 0 failed, 4 skipped.

### The 11 tests that were failing, now fixed

**Routing** (general questions no longer pull personal data; personal ones get what is relevant):

- **`test_phase4_quality_scenarios` q52 and q91, `test_capability_eval`:** "Tell me the biology" and "how much exercise should I get" had been read as personal habits.
- **Three `test_questionnaire` tests:**
  - "What did I answer about my sleep?" stays a questionnaire lookup.
  - "What is my sleep?" fetches only the questionnaire answer.
  - Missing questionnaire data is reported again.
- **`test_house_prompt` broad nutrition:** "What can I eat to lower my LDL?" no longer fetches every Bio-AI score, and a whole-body food question again reads all food-relevant results.

**Follow-ups** (CURA 1.0 dynamic generation, up to four, never padded with generic questions):

- **`test_dynamic_format`, the 0b591ae regression:** the generator returned early once the model offered any usable question. When a later check removed that question, the row was empty. It now refills only with next steps about the result asked about.
- **`test_conversation_state` ALT:** an in-range asked result gets its own library questions.
- **`test_phase10_general_starters`:** a definition answer gets on-topic general questions.
- **`test_theme_followups`:** the exactly-four assertion was obsolete and now accepts up to four.

Two assertions were updated as obsolete, with the reason written in the test. No safety, privacy, grounding
or member-isolation test was changed.

## Remaining medical accuracy limitations

1. About 4,190 distinct claims still have candidate sources only, and no source page has been read for them.
   They are general education, not checked fact. Threshold notes are the exception and are gated.
2. 216 production canonical IDs are unresolved (`inventory/unresolved_mappings.json`).
3. 234 entries need assay or result-format confirmation, including all allergens and many urine items, so
   they stay unlabelled.
4. Production questionnaire keys are unconfirmed, so lifestyle personalisation uses staging IDs.
5. MetSights has not published the formula, prediction target, time horizon or reference population for
   any Bio-AI score. CURA does not attribute scores or turn bands into probabilities.
6. 23 repeated sentences listed by the audit still need an independent writing review.
