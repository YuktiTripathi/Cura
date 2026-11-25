# Phase 4.5 — Factual consistency and final corrections

Targeted fixes on the existing chat pipeline. No new architecture, no V2.3 rewrite, and no landing-screen change.

## HDL was in the report and missing from the answer's evidence

"How is it connected to LDL?" names LDL. `apply_to_query_plan` treated any newly named test as a topic switch and dropped the previous entity, so the model was given LDL without HDL. The prompt then tells the model to say a fact is not in the report when it is not in the supplied context. The model followed that instruction. HDL was present on the selected report. It was not absent, not ambiguous, and the provider was available. It was simply not included in that turn's context.

The relationship branch now keeps the active lab entity alongside the newly named one. `correct_false_absence` also treats "does not include" as an absence claim and replaces it when that marker is in the context.

On the corrected 18-turn run, turn 2 reported HDL 41.0 mg/dL (range 40–60). Turn 4 explained HDL and LDL and did not claim HDL was missing.

## General ferritin text was rewritten after the model

"What is ferritin?" was a general answer. `review_clinical_output` rewrote any sentence matching "ferritin … serum iron" into "ferritin is not available in the retrieved results" whenever the topic was ferritin, including general questions. That substitution now runs only when the question is personal and ferritin is actually on the missing list.

The corrected general answer explains ferritin and serum iron. It does not say the member's report lacks ferritin. The next turn, "What does my ferritin result mean?", still says ferritin is not in `demo-user-001`'s reports.

## Model tier for simple definitions

"What is Bio-AI?" scored as an explanation plus a Bio-AI source, which crossed the fast-tier limit and selected gpt-5-mini (28.3s in Phase 4.4). A definition that does not say "my" and is not a relationship question now stays on the fast tier. The corrected run answered it with gpt-5.6-luna in 7.3 seconds. Model IDs were not changed.

## Deterministic lookups

A pure "what is my {marker}" question can be answered from the matching marker without a model. The HDL lookup in the 18-turn run still called luna (6.3s) because more than one HDL row was in context, so the single-marker shortcut did not apply. The answer was factually correct and now has four on-topic follow-ups (what HDL does, why it matters, how it connects, what influences it). Deterministic answers remain in use for missing ferritin and the two-report cardiac clarification.

## Privacy refusal

"Show me another member's blood results" previously continued into a health-scenario answer, which attached a next-day caution and diet advice. The chat path now returns before retrieval:

> I can only use the health records for the member who is signed in. I can't show another person's results.

No follow-up chips are added. This was checked on the live endpoint.

## Safety timeout

The classifier timeout is 3 seconds (`safety_classifier_timeout_seconds`). Live degraded calls in this phase logged `waited_ms` of 3138 and 3854. The overhead is that client timeout. The classifier is not disabled. Local rules still block emergencies and medication changes. A symptom-like message that is not a recognised emergency still receives the existing see-a-doctor caution when classification fails. Ordinary education is not labelled as a symptom.

## First token

When the answer JSON is streamed, the time until the answer field starts is stored as `first_visible_ms` and copied onto the response timing. The HDL and Bio-AI turns in this run did not populate `first_token_ms` on the public timing object, so a first-token improvement is not claimed. Prompt caching was already observed in Phase 4.4. The system prompt was not lengthened.

## Corrected 18-turn run

Same synthetic member and question list. Jev off. Selected results:

| Turn | Result |
| --- | --- |
| HDL value | 41.0 mg/dL, range 40–60, luna, four HDL follow-ups |
| What does my result mean? | HDL only |
| HDL connected to LDL | Both carriers explained. No false "HDL is missing" |
| What is ferritin? | General definition. No personal absence sentence |
| My ferritin | Honest absence for this member |
| What is Bio-AI? | luna, 7.3s, general |
| Cardiac risk | Scores 30 and 48. Not a diagnosis |
| Heart-disease follow-up | Does not confirm and does not rule out |
| Vitamin D | 12.6 ng/mL, range 30–100 |
| What is diabetes? | luna, general |

## Tests

Continuity, safety/Jev fallback, and provenance tests: 25 passed.

The full backend suite was not re-run. The last completed full result remains 33 failed, 2235 passed, 4 skipped. Frontend files were not changed in this phase.

MemberSnapshot stays off in `tests/conftest.py`. These chat fixes run on the request path with the mock provider, which does not require the snapshot flag.

## Remaining limits

- A simple HDL lookup still used the fast model when more than one HDL row was in context.
- Some relationship answers can still discuss only the markers that were retrieved if the user names a pair the fixture does not contain.
- Safety-classifier timeouts of about 3–4 seconds still sit in front of ordinary answers.
- Jev remains variable. The deterministic fallback and the 0.80 confidence gate are unchanged.
- 33 backend failures from the last full run are still open.
- This is synthetic-fixture evidence, not a production-member or clinical review.
