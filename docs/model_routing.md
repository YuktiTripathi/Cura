# Answer-model routing

CURA picks one of three answer models per turn. The pipeline is unchanged:

```
request → routing → semantic plan → [answer-tier policy] → retrieval → context → prompt
        → (optional one-step promotion) → ONE answer-model call → safety → recommendations → response
```

| Tier | Default model | Setting (env) | Timeout cap |
|---|---|---|---|
| FAST | `google/gemini-3.8-flash` | `CURA_FAST_MODEL` (or `ANSWER_MODEL_FAST_REASONING`) | 10 s |
| STANDARD | `openai/gpt-5-mini` | `CURA_STANDARD_MODEL` (or `ANSWER_MODEL_STANDARD_MEDICAL`) | 18 s |
| DEEP | `openai/gpt-5.6-luna` | `CURA_DEEP_MODEL` (or `ANSWER_MODEL_DEEP_MEDICAL`) | 25 s |

Model ids live only in `app/core/config.py` and `app/llm/registry.py`. Every cap sits
inside the one request budget, so a fallback only uses the time that is left.

Plain report lookups that need no wording ("What was my previous HbA1c?", list views)
are still answered **deterministically**, with no model call.

## The policy (`app/routing/model_tier.py`)

`assess_answer_complexity()` scores how much reasoning the answer needs. It uses cheap
signals known before retrieval: the semantic plan (goal, named markers, Bio-AI, lifestyle
concepts, time need), the wording and the conversation state. It does not use intent
alone, and it does not use clinical severity.

| Signal | Points |
|---|---|
| Goal: lookup / definition | 0 |
| Range check on one value ("is my TSH normal?"), or no reasoning cue | 1 |
| Goal: explain, causes, assess, risk, action, compare | 3 |
| Goal: prioritise, synthesise | 4 |
| Each further marker reasoned about (named or carried from the conversation) | +1 (max 3) |
| Blood **and** Bio-AI brought into one reasoning question | +3 |
| Bio-AI alone | +1 |
| Lifestyle / questionnaire context | +1 |
| Contrast or conflict ("even though", "but my", "despite", "how can both") | +3 |
| Whole-record breadth ("across", "overall", "fit together", "same story") | +3 |
| Whole-report comparison (compare with no named marker) | +3 |
| Trend combined with the current state | +1 |
| Nuanced prioritisation ("which are probably minor", "what can wait") | +2 |
| Relating 2 / 3+ things ("connected", "affect", "contributing") | +1 / +2 |
| Stated uncertainty | +1 |
| Follow-up that needs the earlier turns | +1 |
| Uploaded-document analysis | +3 |

**0–2 → FAST · 3–5 → STANDARD · 6+ → DEEP.** The score is recalculated on every turn. The
conversation, its memory and the selected context are shared across model switches, and
all three models get the same system prompt (identity, safety, dynamic format).

## Escalation, fallback, failure

- **Before generation:** retrieval can promote one tier (FAST→STANDARD, STANDARD→DEEP)
  on conflicting sources or cross-source evidence. This happens before the single call,
  so it costs nothing extra. Breadth alone (a whole report read for context) never promotes.
- **After generation:** one more call, one tier up, only when the answer left contradictions
  unaddressed, leaked backend text, or produced no usable output. Wording problems are the
  validator's job. Escalation is skipped when the next tier is the same model, or when a
  tier is forced.
- **Unavailable model:** each fallback is a different model.
  - FAST falls back to STANDARD.
  - STANDARD falls back to FAST if the score is ≤ 4, otherwise to DEEP.
  - DEEP falls back to STANDARD only if the score is ≤ 8. Above that, the member gets an
    honest "please try again" message instead of a weaker answer. Every fallback is logged.
- **Safety is model-independent.** Every answer passes the same safety layer.

## Telemetry (no PHI)

Every turn logs `cura_model_routing {json}` with:

- `intent`, `complexity_score`, `initial_tier`, `answer_tier`, `answer_model`
- `routing_reason`, `answer_model_ms`, `total_ms`
- `input_tokens`, `output_tokens`, `estimated_cost_usd`
- `escalated`, `escalation_reason`, `fallback_used`

Development only:

- `CURA_MODEL_ROUTING_DEBUG=true` logs a readable line and adds `meta.debug.model_routing`.
- `CURA_FORCE_ANSWER_TIER=fast|standard|deep` forces every model answer onto one tier.

Neither works in production, and neither is set by default. The chat UI never shows which
model answered.

## Evaluation

```
python scripts/model_routing_report.py --offline                               # routing + distribution
python scripts/model_routing_report.py --user <id>                             # live latency/tokens/cost per tier
python scripts/model_routing_report.py --user <id> --compare-models --sample 12  # same questions on all 3 models
```

The set is `backend/data/model_routing_set.json`: 20 FAST, 20 STANDARD and 20 DEEP
questions. It covers blood markers, Bio-AI, trends, lifestyle, priorities, follow-ups,
cross-report reasoning and conflicting data. Multi-turn cases run as real conversations.
The comparison output has empty score fields for manual rating: correctness,
personalization, reasoning depth and hallucination.

Prices in config are placeholders. Set your contracted prices (`MODEL_PRICE_*`) before
reading any cost numbers.
