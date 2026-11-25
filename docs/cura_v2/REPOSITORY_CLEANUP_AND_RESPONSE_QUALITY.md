# Repository cleanup and response quality

Branch: main. Commits in this pass (ordinary commits, no history rewrite, no force push):
`1a61c4d` unified personal context and V2.3 retrieval, `d644e7d` nutrition relevance, `bfe9086` repository cleanup, `5e8a796` Explore UI. The final commit id is in the git log; this document is committed with it.

## 1. Live model verification: blocker

No OpenRouter key is configured in this environment (`settings.llm_api_key` is empty and no `OPENROUTER` or `LLM_API` variable is set). I did not substitute deterministic answers for model answers, and I did not invent model output. What I verified instead:

* The nine brief questions were sent through the real `/api/v1/chat` endpoint with a synthetic member, with the model client intercepted after the final outgoing safety guard. The exact request that would reach the model is saved in `docs/cura_v2/request_capture/01.md` to `09.md` (system prompt, user message, model name).
* No answers, validated answers or rendered responses from a live model exist yet. Once a key is supplied, rerun the capture with the interception removed.

| Question | Model calls | User message chars | Personal context | "No evidence" line | V2.3 passages | Handoff screen context |
|---|---|---|---|---|---|---|
| 1 Why is my Vitamin B12 low? | 3 | 3086 | True | False | True | False |
| 2 What can I do to protect my nutrition? | 3 | 7451 | True | False | True | False |
| 3 What does my Vitamin D result mean? | 3 | 2856 | True | False | True | False |
| 4 Why is my HDL low? | 3 | 3458 | True | False | True | False |
| 5 How does my physical activity relate to my cholesterol? | 3 | 6039 | True | False | True | False |
| 6 What does my thyroid Bio-AI assessment mean? | 0 | 0 | False | False | False | False |
| 7 What is haemoglobin? | 3 | 1611 | False | False | True | False |
| 8 What should I eat if I follow a vegetarian diet? | 3 | 6960 | True | False | True | False |
| 9 Explain that more simply. | 3 | 4282 | True | False | True | False |

Question 6 (thyroid Bio-AI) makes no model call in this fixture because the synthetic member has two same date Bio-AI reports and the request carries no `report_id`. The handoff must send the report id and risk code; the server then resolves the facts. Not yet fixed.

## 2. Files removed and why

| Removed | Why it was safe |
|---|---|
| `backend/app/biomarkers/content/v2/` | Legacy 2.1 copy. Only `content_registry._biomarkers/_risks` read it and nothing called those. |
| `backend/app/biomarkers/content/v2_3/` | Byte for byte duplicate of `backend/app/medical_content/library/` (only `validate_content.py` differed). Nothing read it. |
| `backend/app/medical_content/registry.py`, `mapping.py`, `attach.py` | A second loader of the same library, used only by one test. |
| `backend/app/biomarkers/canonical_mapping.py` | Unreferenced mapping report generator. |
| `backend/app/biomarkers/content_registry.py` | Renamed to `education_notes.py` and stripped of its legacy file reads. It now only turns a library row into an education note. Three imports updated. |
| `frontend/src/prototype/` and its route in `App.tsx` | Prototype behind `?prototype=1`. Landing, Explore, chat, voice, documents untouched. |
| `frontend/src/components/overview/` (whole folder), `messages/NextSteps.tsx` | Old overview screens replaced by ExploreJourney. Nothing outside their own tests imported them. |

Kept on purpose: auth, provider integrations (mock and SuperShyft), DB migrations, voice (`useSpeechInput`), PDF and document handling, safety, grounding, `DoctorSummary` (not currently mounted, a user facing feature), `apiContract.ts` (compile time drift check), questionnaire identity matcher, and all meaningful regression tests.

Dependency verification: grep for every removed module path and name across `backend`, `frontend/src`, scripts and docs found no remaining runtime reference; `tsc --noEmit`, the production build and the full backend suite pass as before.

## 3. Active architecture

* One medical library: `backend/app/medical_content/library/`, loaded once by `backend/app/biomarkers/medical_registry.py`. No clinical approval workflow was restored and V2.3 content was not rewritten.
* One prompt core (`HOUSE_CORE`) plus short intent modules chosen by turn kind. The JSON contract and safety rules are unchanged.
* One personal context projection (`backend/app/pipeline/personal_projection.py`), called in all three prompt branches of `prompt_builder.py`.

## 4. Prompt conflicts removed

* `plan_prompt()` no longer forces an opener, a seven part bullet order, severity from numeric distance, or an automatic retest. It now adds short notes only (list of out of range results, "exactly N points" when asked, already explained, within range wording, waste marker safety line).
* The old `NOT_RETRIEVED` instruction in `prompt_builder` contradicted the core prompt. It now says to follow each entry's availability status.
* `RESULT_WALKTHROUGH` and the plan text are appended independently.
* `BIO_AI_RULES` explicitly allows a blood versus Bio-AI comparison when asked.
* `FOCUS_SHAPE` no longer requires exactly three bullets.
* Follow up brief no longer sends `stages_in_order` scaffolding.
* `QUIET_UPDATE` no longer overwrites a prose answer the model wrote.
Not removed: legacy prompt variants still selectable by `cura_prompt_variant`, and the card layout modules (`RISK_EXPLAINER`, `NUTRITION_OVERVIEW`) which feed parsers for cards.

## 5. Unified personal context

Every personal request sends one block, built from the member snapshot already on the context (nothing is fetched again), only with fields that exist and are relevant to the question:

* age band and sex only when recorded, never inferred from a name; no names, contact details, identifiers or dates of birth;
* dietary preference, allergies, medicines, activity, sleep, alcohol, smoking when the questions relevant to the results being discussed need them, each with source and recording date when known;
* goals tied to the discussed results; recent statements from the chat; screen context from the handoff;
* a stated diet in the question ("if I follow a vegetarian diet") wins over the recorded one;
* anything not listed is unknown, not negative. General questions (for example "What is haemoglobin?") send no personal block.

Bug fixed on the way: lifestyle fields were only fetched when the planner set `needs_lifestyle`, so diet never reached the model for "why" questions. The same relevance decision that fetches the questionnaire now also fetches lifestyle. Bio-AI level words were also being sent as bare "conditions"; removed.

Example, "Why is my Vitamin B12 low?" (synthetic member):

```
PERSONAL CONTEXT (verified, selected for this question; anything not listed is unknown, not negative):
{"about_member":{"age_band":"26-35","sex":"male"},"dietary_preference":{"value":"non_vegetarian","source":"supershyft_lifestyle"},"personalization":{"communication_preference":"STANDARD"}}
FOLLOW-UP BRIEF JSON:
{"findings":[{"test":"vitamin B12","direction":"low","earlier_report_available":true}]}
BACKGROUND NOTES for your reasoning only. Do not quote them, name the organization, or mention a source pointer. Answer the user's question in your own words.
Vitamin B12, what a low result may reflect: Low B12 may reflect low intake or difficulty absorbing it. A borderline B12 result may need other tests to assess functional deficiency.
Vitamin B12, possible influencing factors: Dietary intake. absorption in the stomach and gut. supplements. metformin.
Relationship with mcv: A shortage of vitamin B12 can make red cells larger. The two findings provide context but cannot establish a diagnosis or prove a cause.
Relationship with homocysteine: Vitamin B12 helps your body process homocysteine.
Conversation focus (topic and follow-up only; never a source of current lab values):
```

## 6. V2.3 passages in the final request

Personal report questions previously skipped the library (gate on `report_use_knowledge_base`), which is why the model saw "No medical evidence was retrieved". They now receive the fields that answer the question: what a low or high result may reflect, possible influencing factors, up to three relationship lines. Identity mismatches (CURA key `hdl` versus library id `hdl_cholesterol_direct`) are bridged by `canonical_key`. Food questions get, per result outside its range, what that result may reflect and its influencing factors, and no unrelated related markers.

Example, "Why is my HDL low?":

```
PERSONAL CONTEXT (verified, selected for this question; anything not listed is unknown, not negative):
{"about_member":{"age_band":"26-35","sex":"male"},"dietary_preference":{"value":"non_vegetarian","source":"supershyft_lifestyle"},"lifestyle":{"activity_level":{"value":"moderate","source":"supershyft_lifestyle"},"sleep_quality":{"value":"fair","source":"supershyft_lifestyle"}},"personalization":{"communication_preference":"STANDARD"},"goals":[{"goal":"improve_metabolic_health","label":"Improve metabolic health","target_metrics":["hba1c","fasting_blood_glucose","glucose","triglycerides","hdl","bmi"]}]}
FOLLOW-UP BRIEF JSON:
{"findings":[{"test":"triglycerides","direction":"high","earlier_report_available":true},{"test":"LDL","direction":"high","earlier_report_available":true}]}
BACKGROUND NOTES for your reasoning only. Do not quote them, name the organization, or mention a source pointer. Answer the user's question in your own words.
HDL (good cholesterol), what a low result may reflect: Low HDL can be linked with a greater risk of heart disease. A high HDL value does not cancel out the risk of high LDL.
HDL (good cholesterol), possible influencing factors: Physical activity. smoking. inherited traits. triglyceride levels.
Relationship with cholesterol total: Total cholesterol includes HDL cholesterol. HDL helps carry cholesterol back to the liver. The two findings provide context but cannot establish a diagnosis or prove a cause.
Relationship with non hdl cholesterol: Non-HDL excludes cholesterol carried in HDL particles.
Conversation focus (topic and follow-up only; never a source of current lab values):
```

## 7. Nutrition relevance

"What can I do to protect my nutrition?" now sends only the results food can influence (vitamins, iron, lipids, glucose, calcium and similar) instead of the whole 18 marker report, and passages for the low vitamin D, low B12 and high LDL results. The user message fell from 10,269 to about 7,450 characters. The captured request is in `request_capture/02.md`. Not done: the ranked generic next steps in `answer_evidence.rank_next_steps` still exist for the deterministic path; allergies are passed to the model when recorded.

## 8. Deterministic wording

"higher/lower than the normal range" became "above/below/within the range on your report" in `report_explainer.py`; the matching test and section regex were updated.

## 9. UI corrections (Explore)

Category icons render as SVG (`components/LineIcon.tsx`) instead of literal names; the duplicate in page Back and Home controls were removed because the header Back already steps back one level; empty "Bio-AI assessments" and "Blood results" sections are hidden; the fixed 210px card height is gone; headings are smaller; room is left under the last item so the composer never covers it; the Bio-AI detail now lists the related measured results labelled as measured, not predicted. Not done: repeated Bio-AI classification in chat cards, "previous retrieved result" wording in chat, unavailable result consistency, and the T3 not reported check (not verified in this pass).

## 10. Questionnaire export needed from SuperShyft

The current read joins `questionnaire_responses` with `questionnaire_definitions` and assessment instances. For reliable personalization SuperShyft should export, per answer:

* `question_id` and the production `question_key` (the V2.3 staging export has no production keys, so matching is by the verified identity matcher in `medical_content/questionnaire_identity.py`, never by text alone);
* `question_text` and `question_type`, the option list for choice questions, and the selected option value;
* `answered_at` (recording date) and `assessment_instance_id`, so a newer answer supersedes an older one;
* an answer state: answered, skipped, unknown or "prefer not to say", and an explicit negative (for example "No" to tobacco) kept distinct from missing.

Today the code keeps the source and recording date and omits missing answers (they are never sent as negatives). It does not yet carry skipped, unknown or explicit negative states, because the current export does not provide them.

## 11. Tests

* Full backend suite: 30 failed, 2242 passed, 4 skipped. The failing set is identical to the baseline of 30 recorded before this work (diff of test ids is empty); no test was newly broken. Cause of the 30, from their assertion messages: about 14 assert phrases from the retired system prompt that the product feedback brief replaced (for example "Medical accuracy and safety.", "Blood Report Interpretation Specialist"); the rest assert older answer shapes or fixtures (for example a package name "Iron Studies with Ferritin", a follow up chip, "RESULT_LIST"). I did not rewrite these to match, because that would hide real drift; they need an owner decision.
* Frontend: `tsc --noEmit` clean, vitest 143 passed (the drop from 176 is the deleted overview and prototype tests), production build passes.
* Tests changed: `test_vitamin_d_lookup...` (vitamin D now maps to diet for "why" questions; plain lookups still never fetch the questionnaire), `test_report_explainer` wording, `test_medical_content_registry` rewritten against the single loader, `test_answer_plan`.

## 12. Remaining blockers and open items

* Live model answers: blocked, see section 1.
* Bio-AI handoff with two same date reports needs `report_id` in the context reference.
* Chat UI items listed under section 9.
* Post generation steps (`polish_answer`, `drop_unverified_claims`) were audited and kept: they strip leaked labels, enforce grounding and urgent notes, and do not rewrite valid prose beyond label cleanup.
