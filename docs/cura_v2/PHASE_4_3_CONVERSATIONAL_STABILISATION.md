# Phase 4.3 — Conversational stabilisation

Targeted fixes after the first 18 synthetic chats. Medical Knowledge Library V2.3, MemberSnapshot, HealthView, the original landing screen, and the existing chat pipeline stay in place. The 100-answer evaluation was not started.

Synthetic member: `demo-user-001` with `HEALTH_PROVIDER=mock`. Every answer below came from `POST /api/v1/chat`, not a direct model call.

## Root causes

**"What does my result mean?" left HDL.** `ConversationStateResolver._classify` treated that sentence as a new question, so `follow_up_topic` never reached intent classification and the planner fell through to a whole-report summary.

**Cardiac questions became blood-report essays.** `demo-user-001` has two Bio-AI reports on the same day (cardiac health 30, moderate, and 48, elevated). Ambiguous selection cleared `bio_ai_risks`. "What does my cardiac health risk mean?" was classified as a score lookup, then the model answered from blood markers alone. "Does this prediction mean I have heart disease?" later pulled in every heart-related score (hypertension, dyslipidemia), not only cardiac health.

**Off-topic follow-ups survived filtering.** Generic and unrelated-score chips were removed, then the composer rebuilt chips from the unfiltered model list.

## What changed

- `conversation_state.py`: "my result", "this result", "this prediction", and "the prediction" continue the active entity when the message names nothing new.
- `intent.py`: a personal Bio-AI question that asks what something means, or refers to a prediction, is `bio_ai_explanation`.
- `context_builder.py`: when two reports disagree on the named assessment, both scores stay on the context. Other scores are not added.
- `reasoning.py` and `renderer.py`: that case returns a deterministic clarification with both scores and an explicit "not a diagnosis". A "do I have heart disease?" follow-up starts with "No."
- `service.py`: the same generic-question and off-topic-score filters run again after composition.
- `scripts/e2e_synthetic_chat.py`: prints intent, whether the model ran, and stage timings already stored on the response.

## 18-turn run (Jev off)

| # | Question | Intent | Model | Result |
| --- | --- | --- | --- | --- |
| 1 | What is HDL? | general | gpt-5.6-luna, 8.4s, 16 words | Definition only. Sources: general. |
| 2 | What is my HDL level? | latest_result | luna, 7.9s | HDL and the report range. |
| 3 | What does my result mean? | blood_marker_explanation | gpt-5-mini, 13.9s | HDL only. Previously a multi-system report essay. |
| 4 | How is it connected to LDL? | latest_result | luna | HDL and LDL. |
| 5 | What can influence HDL? | general | luna | General factors. Personal HDL not required. |
| 6 | What is ferritin? | general | luna | Definition. No personal retrieval. |
| 7 | What does my ferritin result mean? | blood_marker_explanation | deterministic | Ferritin is not in the fixture. No invented value. |
| 8–10 | Ferritin and haemoglobin | blood_marker_explanation | luna | Stayed on iron and haemoglobin. No cardiac-score chip. |
| 11 | What is Bio-AI? | general | luna | General. |
| 12 | What does my cardiac health risk mean? | bio_ai_explanation | deterministic, 2.5s | Both cardiac scores, asks which report. Not a blood list. |
| 13 | Does this prediction mean I have heart disease? | bio_ai_explanation | deterministic | In this full run, the answer still listed hypertension and dyslipidemia. Fixed after the run; see below. |
| 14 | Cholesterol report | blood_marker_explanation | gpt-5-mini | LDL, HDL, triglycerides. |
| 15 | What about my vitamin D? | latest_result | luna | Vitamin D only. |
| 16 | What is diabetes? | general | luna, 8.0s, 162 words | Fast tier. Previously 32s and 258 words on gpt-5-mini. |
| 17 | Has my HbA1c changed? | trend | gpt-5-mini | Uses both fixture values. |
| 18 | What should I eat based on my blood report? | nutrition_guidance | luna | Short diet answer. |

After the turn-13 filter, the same two cardiac questions were sent again on a new conversation:

- "What does my cardiac health risk mean?" — cardiac 30 (moderate) and cardiac 48 (elevated). Not a diagnosis. Asks which report.
- "Does this prediction mean I have heart disease?" — starts with "No." and repeats only those two cardiac scores.

The full 18-question script was not repeated after that one-line filter. Turns 1–12 and 14–18 are from the completed run above.

## Deterministic shortcuts

Used when the records answer the question completely:

- Missing ferritin: says the marker is absent.
- Two different cardiac scores: lists both, says a score is not a diagnosis, asks which report.

HDL interpretation, vitamin D, HbA1c change, and definitions went to the configured model. The old ambiguous Bio-AI path that substituted a blood-report list is not used when a topic is set.

## Follow-ups

After ferritin and haemoglobin, chips stayed on iron, anaemia, and symptoms. The earlier "Cardiac health score of 48" and "Dyslipidemia score of 46" chips did not return. HDL follow-ups no longer include "What stands out most in my results?" or "Is everything in my report healthy?" One remaining chip, "What should I focus on improving?", is still broad.

## Jev

The 18-turn run kept Jev off, matching the previous evaluation. A separate three-question sample with Jev on:

| Question | Jev | Intent | Model |
| --- | --- | --- | --- |
| What is HDL? | called, 499ms, then `JevDecisionValidationError` (personal decision with a non-personal source) and deterministic-planner fallback | general_health_question | luna |
| What is my HDL level? | not called (fast path) | latest_result | luna |
| Cardiac health risk | called, 517ms | bio_ai_explanation | deterministic clarification |

Jev did not override the safety classifier. A full 18-turn Jev-on pass was not run. Low-confidence and unavailable-Jev paths were not given their own 18-turn scripts; the validation error above is the observed safe fallback.

## Safety classifier

Several turns logged `safety_classifier status=degraded error=ReadTimeout` and continued. Measured `safety_ms` on the 18-turn run was usually 0–6ms, with one turn at 203ms. The classifier was not disabled. Emergency and unsafe-medication behaviour under a forced timeout was not replayed as its own script in this pass.

## Latency and caching

Stage timings already on the chat meta were printed. Generation dominates (about 6–14s). Retrieval on the mock provider was about 0–1ms. Jev, when called, was about 0.5s. First-token time was not populated on these responses. Cached-token counts were not reported by these chat responses, so prompt caching is not claimed. The house system prompt was not lengthened.

One earlier pipeline call in this phase logged `llm_truncated` at the 1200-token budget on `gpt-5.6-luna` and fell back. None of the 18 turns in the run above truncated, and no answer was raw JSON.

## Backend failures

The suite is still 34 failed / 2122 passed against a 31-failure baseline. The three added failures are in `tests/unit/test_provenance_and_routing.py` (`test_hypertension_general_uses_retrieved_who`, `test_hyperthyroidism_symptoms_use_retrieved_evidence`, `test_hba1c_foods_question_is_general_and_has_nutrition_evidence`). They expect passages from the retired unreviewed index. That index stays filtered by `is_servable`. The assertions were not weakened and the legacy index was not turned back on.

## Remaining limits

- The completed 18-turn transcript still has the pre-fix turn 13. The corrected cardiac pair was verified on its own conversation.
- Jev was compared on three questions, not on all 18, and not under a forced low-confidence or unavailable response.
- Safety-timeout behaviour for emergency symptoms and unsafe medication requests was not re-scripted.
- One generic follow-up ("What should I focus on improving?") can still appear after a single result.
- "What can influence HDL?" stays a general answer and does not restate the member's HDL.
- Per-stage timings do not yet include a separate V2.3 retrieval span or time-to-first-token.
- Frontend production build and the snapshot-enabled backend suite were not re-run for these backend-only edits.
