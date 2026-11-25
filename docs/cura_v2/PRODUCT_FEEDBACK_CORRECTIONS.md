# CURA 2.0 Product Feedback Corrections

This document records what was found, why it happened, what was changed, and what is still open. All data in the examples and screenshots is synthetic (demo member "Alex"). Nothing here restores the clinical approval workflow, rebuilds the architecture, or adds A2UI. The landing design, MemberSnapshot, HealthView, Redis caching, Medical Knowledge Library V2.3 as the only curated source, SuperShyft integrations, Jev with its deterministic fallback, dynamic follow ups, prompt caching and the safety and grounding layers are all kept.

## 1. Issues and root causes

| Issue | Root cause | Fix |
| --- | --- | --- |
| Answer shown twice in chat (second copy with raw Markdown headings) | The server streamed the answer as text tokens and then also sent "semantic blocks" built from the same answer. The browser appended block text onto the streamed text, kept the provisional streamed text as the final answer, and rendered the blocks again under it. | Backend skips blocks once tokens were streamed (`ProgressEmitter.tokens_streamed`). Browser never appends block text to the answer, the final validated `answer` replaces the streamed text, and block rendering is shown only while no answer text exists. |
| Measured B12 shown under "Your Bio-AI scores" | The card title was chosen from the question intent, not from what the card held. | Title is chosen from the evidence in the card (`source_type`). Mixed evidence gets no shared title. Bio-AI findings are removed from answers that did not ask for Bio-AI. |
| Duplicate "View sources" | Two controls, one in the message actions and one in the provenance line. | One control: the provenance line shows only when there is no evidence group for the actions. |
| Explore rows looked like raw browser buttons | No styles for the new rows, cards and containers. | Reusable `ResultRow`, shared container width, touch targets of at least 56px, chevrons, icons on category cards. |
| B12 and T3 detail screens repeated the same text | `what_it_is` was filled from the biology paragraph and `why it matters` repeated sentences from the result explanation. | Each V2.3 field is used for its own purpose, a sentence is never shown twice, and empty or repeated sections are hidden. |
| Thyroid Bio-AI screen said content was unavailable | The snapshot attached education text to measured findings only. Predicted risks never received any. | `risk_note(code)` attaches V2.3 Bio-AI content by risk code. Empty sections are hidden. |
| Overview cards were long paragraphs | Cards used the full "what happens inside my body" text. | Cards use the V2.3 `short_description`. The full text stays on the category screen. |
| Irrelevant "Why this matters for you" goal sentence and "recheck in three months" on a B12 answer | Post processing added a goal sentence to every answer, and the deterministic explainer always closed with a retest schedule. | The goal sentence is limited to whole report answers. The retest closing is removed because retest schedules need an approved policy. |
| System prompt pushed fixed report layouts and conflicted with itself | See section 2. | Replaced by the CURA companion prompt. |

## 2. Prompt audit

Assembled prompts before and after are in `docs/cura_v2/prompt_audit/` (synthetic data only).

| Prompt | System characters before | System characters after |
| --- | --- | --- |
| "Why is my Vitamin B12 low?" | 12,037 | 11,378 |
| "What can I do to protect my nutrition?" | 18,162 | 11,550 |

Components traced: `HOUSE_CORE`, `WARM_VOICE`, no field names block, the turn kind module (nutrition overview, risk explainer, health area), the result walkthrough, the focus shape, Bio-AI rules, lifestyle focus, the answer plan, the ANSWER EVIDENCE JSON built in `prompt_builder.py`, and the document answer path.

Conflicts found and removed:

1. A fixed six part walkthrough (what the test is, what your result says, how far outside, what could explain it, should you worry, what to do now) was forced on every single result question. It is now one flexible paragraph that answers the exact question.
2. Whole report layouts (SHAPE 1A and 1B, with bullets and a "What to do next" heading) were part of the core prompt for every question. They are now a separate block added only for whole report intents.
3. The nutrition module required headings ("What your body needs", "Foods to include", "Foods to limit") and four to six bullets, which led to a report summary before food guidance. It now says answer the food question first, no exact quantities, no unrelated Bio-AI.
4. "Always give advice" lines conflicted with the evidence JSON line "do not add diet or next steps unless asked". The new prompt follows the question.
5. The tone block praised and encouraged in every answer. It is now limited to advice, with warmth never changing a number or a safety instruction.
6. Follow up rules asked for four fixed kinds of question every time. The new rule is up to four natural, personal questions, fewer when they would repeat.
7. Retest and package suggestions in the old prompt conflicted with the approved task policy. The new prompt forbids them unless a policy allows it.

The new core prompt is the supplied CURA personal health companion prompt, with a short application contract (JSON fields, language, exact numbers and units, no field names, Bio-AI scale 0 to 100 with its four bands, red flags first) so the output contract and safety behaviour are unchanged.

## 3. Duplicate answer fix

Trace: model tokens are streamed (`token` events) and the final response arrives as `complete` and `answer`. After the answer, the orchestrator emitted `experience_block` events whose text came from the same answer. The hook appended that text to the message, then replaced the message at the end with the streamed text instead of the final answer.

Now: one authoritative answer. Streamed text is provisional. The final validated `answer` replaces it. Blocks are not sent after tokens and never appended. Tests: `test_stream_no_duplicate.py`, and a MessageList test that fails if the answer appears twice. The non streaming path has no tokens, so blocks are used only while the answer is absent and are hidden once it arrives. A reloaded conversation renders from stored content only.

## 4. Evidence types

Measured blood results, predicted Bio-AI assessments, user reported answers and historical results are separated by section headings and by `source_type`. Type is never inferred from a number. On Explore screens the sections are "Blood results" and "Bio-AI assessments". In chat, a blood or food question carries no Bio-AI card unless Bio-AI was asked for.

## 5. Selective personal context

`app/pipeline/personal_projection.py` builds a small typed slice for each question. A lifestyle field (sleep, activity, diet, alcohol, smoking) is sent only when a questionnaire key it stands for is relevant to the results being discussed, or when the person asked about food. Goal and communication preference always travel. What the person said in this chat (symptoms, medicines, supplements, pregnancy, fasting) travels when present. History travels only for trend, previous result and comparison questions. The full snapshot and raw questionnaire are never sent, and no extra provider request is made.

## 6. Questionnaire mapping

The library registry has 91 questions and none has a production key (`with_production_key` is 0). The authoritative definitions are the `questionnaire_definitions` table in SuperShyft, which this environment cannot read. So no key was invented. `app/medical_content/questionnaire_identity.py` matches a stored question to a library question only when the wording is identical after normalising case and punctuation, and returns nothing otherwise. Unmatched means unknown, never "no" and never "not applicable". A fully verified mapping needs one export of `questionnaire_definitions` (id, key, text) from SuperShyft. The `diet_preference`, `sleeping_hours`, `physical_activity_frequency`, `alcohol_frequency` and `tobacco_frequency` keys used by the code are the stored keys the integration already reads.

The non vegetarian preference in the B12 answer comes from the stored `diet_preference` answer through the personalization context. It is now sent only on food or B12 relevant questions, and the prompt says a non vegetarian person is not assumed to eat enough animal foods.

## 7. Contextual question handoff

`ContextRef` already carried entry point, category, finding, report and snapshot version. Added: `suggested_question_id` and `displayed_sections` (labels only, checked against an allowed list). The server places them in `screen_context` for the prompt as `sections_already_shown`. The browser sends no personal values; the backend resolves them. The prompt says the latest question overrides stale card context and that showing a section is not proof it was understood, so essentials are repeated briefly when clarity or safety needs it.

## 8. UI improvements

Result rows with name, value, unit, status and chevron, a single container width, category cards with icons and a navigation affordance, singular and plural counts, friendly dates, no technical status text. The landing card is now "Understand my health better" and the food card reads "Explore food guidance for your results". The range bar draws a result outside the band outside the band, supports one sided ranges and missing ranges, and states the position in words using "the range on your report". Biomarker screens hide sections that are empty or repeat another section. Bio-AI screens show the reported classification and score, content only from V2.3, no diagrams, and a clear "Ask CURA about this" action.

## 9. Representative answers

With no model key in this environment the live answers below are from the deterministic path. The assembled model prompts are in `prompt_audit/`.

* "Why is my Vitamin B12 low?" shows one answer, one B12 card (154 pg/mL, below the range on the report, range 200 to 900), no Bio-AI card, one sources control, and follow ups about B12.
* "What can I do to protect my nutrition?" answers with food guidance first, no report summary, no Bio-AI card.

Screenshots (desktop and mobile) are in `docs/cura_v2/screenshots/`.

## 10. Test results

* Backend full suite: 2242 passed, 30 failed, 4 skipped. The same 30 tests failed before these changes (27 earlier baseline plus 3 golden and report selection cases that were already failing on main). No new failures; the final targeted run over answer, presentation and personalization tests also shows none.
* Frontend: `tsc` clean, 176 tests pass, build passes.
* New tests: house prompt contract, no duplicate stream, personal projection, questionnaire identity.

## 11. Limitations

* The live model path could not be run here because no model key is configured. The prompt is verified by assembly tests, not by model output. Please run the two sample questions with a key before release.
* The deterministic explainer still says "lower than the normal range"; the prompt tells the model to say "the range on your report". Changing the deterministic wording touches many tests and is left for a follow up.
* V2.3 content is still marked pending clinical review in its files. It is used as it is, as instructed, and no approval workflow was restored.
* Questionnaire mapping needs the SuperShyft definitions export described above.
* Immunity & Inflammation currently holds one Bio-AI item and no blood tests in the demo data, so that screen is short.
* The 30 failing tests are legacy prompt tests pinned to the old variant and three data dependent cases; they are unchanged by this work.
