# Phase 4 quality evaluation

This pass measured the existing pipeline. The landing screen, health exploration, follow-up order, and V2.3 library were not rebuilt. The clinical-approval flags were not restored.

## Routing dataset

`backend/tests/unit/test_phase4_quality_scenarios.py` contains 100 questions. They check whether the planner asks for personal records. They do not score the wording of an answer.

General questions and hypothetical “if my …” questions do not request blood or Bio-AI data. Questions about the person’s own result, score, or report do. All 100 passed.

## Live model answers

Two general questions were sent to the configured fast model, `openai/gpt-5.6-luna`, with the stable house system prompt and no personal health data.

| Question | Seconds | Prompt tokens | Output tokens | Cached tokens | Cost |
| --- | --- | --- | --- | --- | --- |
| What is haemoglobin? | 4.58 | 622 | 180 | 0 | 0.0003404 |
| What is creatinine? | 3.47 | 622 | 180 | 0 | 0.0003404 |

The provider reported `cached_tokens: 0` on the second call. Prompt caching was not shown to be active.

The visible first lines were plain: haemoglobin was described as a protein in red blood cells that carries oxygen, and creatinine as a waste product the kidneys filter. The raw model text is JSON because the system prompt requires a JSON object. The application is expected to show the `answer` field, not the raw object. Both replies were cut at 180 output tokens, so follow-up questions inside that JSON were not fully received.

No separate follow-up model call was added.

## Personal SuperShyft conversations

Not run. The database is reachable, but the configured development subject has no health-report rows. No other member was selected, and no personal values were sent to the model or written here.

## What was not measured

Jev time, snapshot cold and warm time, and per-stage chat latency were not timed in this pass. Model tiers were not changed. The last completed full backend suite, before the approval-flag removal, was 31 failed and 2110 passed. A newer full suite was still running when this note was written.

## Weaknesses seen

- The system prompt still requires JSON, so a direct model call is not the conversational prose the user sees.
- Prompt caching was not reported by the provider for this model on these two calls.
- Personal answer quality, follow-up quality on a real report, and historical comparison were not evaluated because no authorised member report was loaded.

## Limits

This is an engineering evaluation, not a medical-team review of the library. V2.3 text was not rewritten.
