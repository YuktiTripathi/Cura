# Phase 4 conversational intelligence

The conversation pipeline was inspected and left in place. The landing screen and the health exploration screens were not changed.

## Current flow

A message goes through safety classification, Jev when it is enabled, then `build_query_plan`. The plan decides personal versus general, which records to read, and whether history is needed. Personal facts come from the provider registry. When MemberSnapshot is on, a health card is only a hint: a general question stays general, and a newly named marker replaces the card. V2.3 passages come from `medical_registry.chat_passages`. The house system prompt in `prompt_modules.py` is the stable instruction prefix. The model returns the answer and its own follow-up questions. Those questions are filtered and placed ahead of the template generator, up to four. Streaming, numeric grounding, and emergency handling are unchanged.

## What changed

- A blood-result card no longer pulls related markers into the plan for a plain lookup. Related markers are added only when the question asks why, how things are connected, or for a comparison.
- A V2.3 passage for a definition includes the short description, what happens in the body, and why the test matters. A high or low question includes that side's interpretation and the limitations, not both sides at once.
- `tests/unit/test_phase4_routing.py` checks 14 questions. General education, a hypothetical "if my thyroid is high", and "what should I know about diabetes" do not request personal records. Questions about the person's own result, risk score, or report do.

## What was already in place

- Jev remains the classifier, with the deterministic planner as the fallback.
- The house prompt already asks for plain language, exact personal values, no diagnosis, no prescriptions, and Bio-AI as a prediction.
- Follow-up questions from the answer model stay first. The generator fills only the remaining slots. Exploration screens still use curated V2.3 questions and do not call a model.
- Questionnaire lifestyle claims stay off until production question keys are confirmed.
- Prompt caching was not newly verified against OpenRouter. No token, cost, or latency figures were measured in this pass.

## Tests

The 14 routing tests passed. The full backend and frontend suites were not re-run for this change. The last full backend result remains 31 failed, 2110 passed, 4 skipped. No live member conversation was sent to OpenRouter.

## Limits

This is not a new answer-quality evaluation of 100 generated replies. Clinical approval of V2.3 is still pending. Production must keep unapproved content hidden.
