# CURA V2: Unified medical education, personalisation and conversational experience

This document records what changed, why, and what is still open. It follows the order of the V2 brief. Nothing here claims live model quality: no model credential is present in the build environment, so every live claim is left to the local commands in section 14.

## 1. Outcome in one paragraph

The V2.3 library is now the primary source of medical education in chat, on the category and detail screens and on the model unavailable path. The model connects that education with the member's own results and habits. One resolved intent now drives Jev routing, deterministic planning, the answer plan, evidence selection, the prompt contract and the fallback, so a question is no longer answered by one path and described by another.

## 2. One authoritative resolved intent

* `intent.classify_intent` gained a food branch (nutrition guidance) and relationship words on the marker branch.
* `evidence_planner.reconcile_query_plan` turns a health scenario with food words into nutrition guidance unless the member asked about the whole report.
* `task_contract.stamp_answer_spec` records goal, breadth and primary source once. The Blood Report button now also restores its entry point and response type, and keeps the whole latest report.
* `prompt_builder` prints one TASK object (empty values dropped). The answer contract says "answer the TASK above and nothing else". No new classifier was added.

## 3. The nine scenarios

| # | Question | What now happens |
|---|---|---|
| 1 | Why is my B12 low | Library causes and the member's diet and habits only when relevant. Model unavailable: library explanation with an honest limitation, not a history comparison. |
| 2 | Protect my nutrition | Food relevant results only, no fixed sunlight duration, no supplement dose, no food alone claim. |
| 3 | Vitamin D meaning | Library education plus the member's value against the report's own range. |
| 4 | Why is my HDL low | If the latest value (41 mg/dL) is inside the report's 40 to 60 range, the answer says the premise does not match the result. |
| 5 | Activity and cholesterol | One resolved relationship intent. Activity is retrieved because the member named it. |
| 6 | Thyroid Bio-AI | Report identity travels with the question, linked T3, T4 and TSH are read, screen context says what the member already saw. |
| 7 | What is haemoglobin | General education, no personal retrieval. |
| 8 | Vegetarian diet | A hypothetical scenario: no fish, chicken or meat, no assumed eggs or dairy, and no permanent profile change. |
| 9 | Explain that more simply | Keeps scenario and subject; the previous answer travels with the request, including on general topics. |

Request captures for all nine are in `docs/cura_v2/request_capture/`.

## 4. V2.3 as a primary asset

Library text is retrieved by intent (meaning, causes, relationship, nutrition) and side (low, high, normal). It is never invented, and unavailable or qualitative states are said as such. Detail and category screens show library text first and reveal more on request. Bio-AI detail uses library content without diagrams or invented thresholds, and never claims that a low score rules out a disease.

## 5. Supporting content contract (new)

The answer may reference supporting content by ID. The model never writes it.

| Content | How it is referenced | Resolved by the backend from |
|---|---|---|
| measured_result | `blood.<code>.latest` | the member's report |
| predicted_assessment | `bioai.<code>` | the member's Bio-AI record |
| historical_comparison | `blood.<code>.trend` | the member's earlier reports |
| medical_education | block `medical_education`, ref `edu.<id>` | V2.3 entry, with the side that matches the member's result |
| medical_relationship | block `medical_relationship`, ref `rel.<a>.<b>` | V2.3 relationship row, only when both results are on record |
| lifestyle_education | block `lifestyle_education`, ref `life.<id>` | V2.3 influencing factors, stated as general |

`supporting_content.py` validates the reference against what this member has and resolves the lines. An unknown or absent reference is dropped and never changes the answer. The prompt carries an ID only menu (`LIBRARY_REFS`). The frontend renders the lines with an existing section component. There is no A2UI and no model generated interface.

## 6. Unified personal context

Relevant facts only, drawn from the member snapshot. A named habit is always retrieved, whatever the relevance matcher thinks. No full snapshot is sent and nothing is inferred from names. Stored, reported and hypothetical information are kept apart: the vegetarian scenario suppresses the recorded diet for that answer and does not write to the profile.

## 7. Questionnaire mappings remain unresolved

No mapping was invented. What SuperShyft must supply before more of the questionnaire can drive answers: the stable question key and answer code for each question, the unit and period of each frequency answer, and an explicit state for unanswered versus declined. Until then the answer says what the member reported in their own words.

## 8. Model context and prompt

* One authoritative question context, with references rather than repeated facts.
* The system prompt is shorter (about 3,190 tokens, under the 3,200 budget) and static, so the cacheable prefix is unchanged. Duplicated format lines and the blood plus Bio-AI template were removed. How far and universal Bio-AI band guidance stay out.
* The general health branch now carries the rewrite and tone brief too.

## 9. Educational continuity and handoff

A Bio-AI detail screen hands the model the report identity, the linked results and the sections already shown. A follow up continues the same subject. "Explain that more simply" re-answers the previous answer without adding facts.

## 10. Deterministic path

Deterministic text no longer competes with the model. When the model is unavailable the member gets library education with their value against their range, the verified cards, and one line saying a personalised explanation could not be written. Follow ups are grounded: up to four, model first, no extra model call. Food questions keep grounded food follow ups, and a single marker answer always offers on topic follow ups.

## 11. Model calls, latency and tokens

The "three calls" seen in captures are the model fallback chain for one answer (gpt-5-mini, then gpt-5.6-luna, then gemini-3.8-flash) because the capture interceptor raises on every attempt. A normal turn makes one answer call. No caching or model change was made.

Request size per question, including the static system prompt (system prompt about 3.2k tokens): B12 3.6k, nutrition 4.7k, vitamin D 3.6k, HDL 3.7k, activity and cholesterol 4.2k, thyroid Bio-AI 5.6k, haemoglobin 3.1k, vegetarian 5.4k, simplify 4.2k. Wall time and cost need a live run (section 14).

## 12. Tests

The 30 baseline failures were resolved as follows.

* Real regressions fixed: Blood Report button contract, whole report and dated history, report listing detection, per result retrieval for a Bio-AI explanation (linked results were dropped by named result narrowing, by retrieval and by the relevance pass), cross source evidence selection, missing follow ups on a single marker answer and on food questions, general topic rewrite.
* Obsolete wording tests replaced by behavioural assertions: system prompt phrases, the four versus five follow up cap (brief says four), ambiguity answers that list each score with its own source label, catalog display names, value repair that no longer edits the model's words.
* Kept unchanged: safety, privacy, grounding and routing tests.
* New: `test_supporting_content.py`, `test_contrasting_profiles.py` (same lipid result with low and high activity, same B12 result with vegetarian and non vegetarian diet), a frontend test for library blocks.

## 13. UI

Library blocks render as plain sections. Duplicate findings are suppressed when a semantic view exists, so a result is shown once. No new components were added.

## 14. Local live verification

Do this on your own machine, with your own credentials in the environment. The script never prints, logs or writes the key.

```
cd backend
export OPENROUTER_API_KEY=...        # or LLM_API_KEY
ENABLE_LLM=true MEMBER_SNAPSHOT_ENABLED=true PYTHONPATH=..:. \
  python scripts/live_eval_nine.py --user demo-user-001 --out /tmp/live_eval.md
```

Read the report against section 3. Wall time per question is in the report. Token use and cost come from your provider dashboard.

## 15. Open items

* Live answer quality is unverified here.
* Questionnaire mappings (section 7).
* Clinical review of V2.3 content is still pending, so evidence status remains "pending clinical review" in the data.

## 16. Final integration and verification (follow up brief)

### 16.1 V2.3 in the normal journey, not only on failure

The backend now chooses essential education from the resolved intent and the selected evidence, before and independent of the model (`supporting_content.essential`):

* a result explanation or a food question about a result on the record gets one `medical_education` block for that result;
* a question about a connection ("related", "why", "affect") gets one `medical_relationship` block;
* a plain value lookup gets nothing, so answers are not padded;
* the model may add further eligible references by ID. Duplicates are dropped and at most four blocks are shown;
* nothing is added for an ambiguous Bio-AI report, a safety block or an escalation.

The first line is shown and the rest sits behind "Read more". Each block says "General information, not a finding about you". The education text is library text and is not repeated inside the conversational answer.

### 16.2 General relationships versus personal comparisons

General V2.3 relationships and education need no measurement of either end. They only need to concern what is being discussed (a result on the record or one the question names). A personal comparison still needs verified measurements and still comes only from `blood.<code>.trend` or the comparison cards. A missing value is never invented and a relationship never prompts a suggestion to test.

### 16.3 Report specific references

References resolve against the context for the report being discussed, so a historical question uses that report's flag and not the latest one. Unknown biomarkers, relationships unrelated to the discussion and invented IDs are rejected. Same date Bio-AI ambiguity returns no supporting content and still asks which report. Regression tests: `tests/test_supporting_content.py` (historical flag, unrelated and unmeasured cases) and `tests/unit/test_education_in_chat.py`.

### 16.4 Product inspection (desktop and mobile)

Inspected in the running app at 1280 and 390 pixel widths, screenshots in `docs/cura_v2/screenshots/`: a biomarker opened from the explore journey and a suggested question tapped, a Bio-AI starter tapped, a general question, a personal nutrition question, the vegetarian scenario and "Explain that more simply". The original landing screen and navigation are unchanged. Three defects found by looking, all fixed:

* A general question ("What is haemoglobin?") answered "I can't access the general medical knowledge service" when the service was unreachable. It now answers from V2.3 with a line that a fuller answer is available later.
* "Explain that more simply" with no model blamed the knowledge service. It now says it cannot rewrite right now.
* Library blocks touched each other. They now have spacing.

Not covered: opening a specific historical report and a specific Bio-AI assessment through the explore screens were not separately captured. The tapped Bio-AI starter was.

### 16.5 Semantic personalisation

Cannot be judged here. The contrasting profile tests prove the model receives different personal context for identical results (activity level, diet, unavailable lifestyle) and identical measurements. Whether the written answers differ meaningfully needs a live model. The mock data has no outdoor or sun exposure field, so a verified outdoor context profile cannot be built. The context now says "time outdoors" was asked about and is not on record, and the sunlight answer is not inferred. SuperShyft needs to supply that attribute before a vitamin D answer can use it.

### 16.6 Live nine question evaluation: blocked

No model credential exists in this environment, so `scripts/live_eval_nine.py` was not run, and no intercepted or deterministic output is presented as a live result. Run it locally as in section 14. The report records answer, latency, follow ups and status per question. Still to capture on your side from the provider: selected model, token use and cached tokens. Retrieved V2.3 passages, personal context and rendered cards can be read from `docs/cura_v2/request_capture/` and the chat response.

### 16.7 Governance

No runtime clinical approval mechanism was restored. Content ownership, versioning, evidence traceability, rejected content handling and assay limitations are untouched. Review metadata still reads pending clinical review.
