# CURA request path, latency findings and how to measure

## Architecture trace (unchanged pipeline)

```
POST /api/v1/chat  (app/api/routes/chat.py)
→ ChatService.chat  (app/pipeline/service.py)         per-request perf trace begins (app/core/perf.py)
  → SafetyStage.run                                  rules first; model classifier (if enabled) runs beside routing
  → ConversationStateResolver / FollowUpMemory       turn type, active entities, previous topic
  → RouteStage → jev_router.resolve_plan             deterministic QueryPlan (query_planner/intent)
                                                     + Jev decisions call, skipped for obvious lookups (jev_fast_path)
  → build_semantic_plan + reconcile_query_plan       goal x topics x personalization x time → validated sources
  → ContextBuilder.build                             profile read ∥ retrieval:
      HealthRetrievalRouter.retrieve                 IHR (blood + Bio-AI) ∥ lifestyle ∥ questionnaire  (threads)
      SuperShyft: integrations/supershyft/ihr.py     report ranges/flags mapped from each report (mapping.py)
      health_scenario reuses this turn's reports     (no second read)
  → medical knowledge lookup (general questions)
  → ReasoningService.run → PromptBuilder.build       ANSWER EVIDENCE (answer_evidence.py), not the full record
      → OpenAICompatibleLLMClient.complete_structured   one model call; answer cache (identical prompt only)
  → ResponseValidator.validate                       grounding + safety review
  → urgency guard                                    removes same-day/emergency wording without a red flag
  → testing options / follow-ups (recommendation)
  → ResponseComposer.compose → presentation policy   chat text de-duplicated, cards, chips
  → persistence, evaluation record, cura_perf log line (numbers only)
```

What the model sees for a personal question: the question, the reasoning goal, a strategy
(fact → interpretation → connection → action), 1–3 primary facts with the report's own
ranges, up to 2–3 supporting facts (other markers, Bio-AI risks), at most 2–4 relevant
questionnaire answers, trend facts with dates and exact change, a premise check, and the
conversation turn. Irrelevant sources are not sent.

## Long-tail latency: root cause (from the code path)

Old worst case for one answer:

| step | wait |
|---|---|
| Jev decisions call, timeout then retry | 10 s + 10 s |
| answer call, json_schema format: timeout then HTTP retry | 30 s + 30 s |
| format fallback json_object after a *timeout* (same wait again) | 30 s + 30 s |
| repair call / plain-text fallback | up to 30 s |
| "escalate to deep" — same model id as standard, so the call is repeated | + one full answer |

A single slow provider minute therefore became 60–180 s, matching the evaluation max (136 s)
and P95 (51 s). Medium questions also paid a second full model call through escalation.

Fixed:
- one wall-clock budget per answer (`llm_timeout_seconds`) across HTTP retries, formats and repair;
- a format fallback only after a *format* error, never after a timeout or provider error;
- deep escalation only when the deep tier is a different model;
- a Jev timeout is not retried (the deterministic planner is the fallback);
- obvious lookups ("What is my HbA1c?") skip the Jev call;
- independent provider reads run concurrently; the scenario path reuses the turn's reports.

Measured offline (mock data, model simulated at 2 000 ms, answer cache off, 2 runs × 15 questions,
`scripts/latency_suite.py`): model calls 28 → 20 for 30 requests; medium P50 4 365 → 2 448 ms;
simple P90 4 384 → 2 459 ms; complex P50 2 740 → 2 798 ms (unchanged: one call before and after).
Real provider latency must be measured with the live suite below.

## Streaming

The backend already streams tokens for low-risk general answers (`CHAT_STREAMING_MODE=tokens_low_risk`,
first-token time recorded as `first_token_ms`). Personal answers are structured JSON that is grounded
and safety-checked before display, so they are not token-streamed; streaming them would show text
before the safety layer runs. The frontend shows stage progress during that wait.

## Measuring

```
cd backend
python scripts/latency_suite.py --user <subject_id> --runs 3          # live, cold (cache off)
```

Every response carries `meta.timing.stages` and the log line `cura_perf {...}` with:
`total_ms, intent_ms, safety_precheck_ms, profile_fetch_ms, blood_bioai_fetch_ms (SuperShyft IHR),
blood_fetch_ms, bioai_fetch_ms, lifestyle_fetch_ms, questionnaire_fetch_ms, scenario_fetch_ms,
retrieval_ms, context_build_ms, context_only_ms, knowledge_lookup_ms, prompt_build_ms, llm_ms,
safety_ms, recommendation_ms, persistence_ms, retry_count, provider_attempts, llm_calls,
prompt_tokens, completion_tokens, prompt_chars, cache_hit, jev_called, jev_ms, intent, goal,
execution_path`. No names, messages or health values are logged.
