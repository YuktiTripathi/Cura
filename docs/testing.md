# Testing and evaluation (Phase 10)

Run the full suite from `backend/`:

```bash
cd backend
source .venv/bin/activate
pytest -q
```

Default: `ENABLE_LLM=false` (LOOKUP-only stays deterministic; multi-entity
reasoning uses a stubbed LLM in tests). Tests assert **entities, operations,
sources, values, and safety**, not exact wording or a single `expected_intent`.

## Matrix

| Area | Example | Expected |
| --- | --- | --- |
| General | What is Vitamin D? | `general`, no SuperShyft labs |
| Personal | What is my HbA1c? | `supershyft` |
| Document | What does this PDF say? | `user_uploaded` |
| Cross-source | Compare uploaded vs SuperShyft | both sources labeled |
| Follow-up | What about LDL? | same source mode |
| General → mine | What is HbA1c? → What is mine? | switches to SuperShyft |
| Document → compare | How does that compare with SuperShyft? | cross-source |
| Cross → general | What does HbA1c actually measure? | general |
| Missing iron tests | Low Hb/MCV/iron, no ferritin | ferritin gap; **Iron Studies with Ferritin** from catalog |
| Recent adequate labs | Do I need another cholesterol package? | `NOT_RECOMMENDED_NOW` card; compare-first, no purchase push |
| Stale Vitamin D | Has my Vitamin D improved? | updated measurement + **Vitamin Profile** if catalog matches |
| Acute fever | I feel feverish, should I get tested? | guidance; no package |
| Explicit catalog | Which SuperShyft package includes ferritin? | deterministic catalog name |

Evaluation fixtures:

- `backend/tests/fixtures/eval_cases.json`: production answer/evidence cases.
- `backend/tests/fixtures/cura_capability_eval.jsonl`: compositional routing
  (entities / operations / sources), not a frozen intent taxonomy.
- `backend/tests/fixtures/cura_routing_eval_500.jsonl`: 533 synthetic routing
  cases covering general/personal pairs, context, history, Bio-AI, documents,
  ambiguity, negative cases, and six supported languages.
- `backend/tests/unit/test_compositional_reasoning.py`: paraphrases of
  multi-marker pattern, metabolic cluster, and multi-source review questions.

The production golden suite parametrizes this dataset and verifies sources,
markers, evidence, escalation, follow-ups, and prohibited claims:

```bash
pytest tests/golden/test_production_eval.py -q
pytest tests/unit/test_compositional_reasoning.py tests/unit/test_capability_eval.py -q
python scripts/benchmark_routing.py
```

The routing benchmark always reports the deterministic baseline. Live Jev and
Jev+CURA-validation measurements are opt-in because they use OpenRouter:

```bash
python scripts/eval_assistant_40.py
python scripts/eval_reasoner_models.py
```

The 40-question assistant eval (`tests/fixtures/cura_assistant_eval_40.jsonl`) uses synthetic
users only, including `eval-user-iron` (low haemoglobin/MCV/MCH/iron, normal lipids,
unchanged HbA1c 5.3%). `eval_reasoner_models.py` scores retrieval coverage,
grounding, synthesis, restraint, and latency against the same fixtures.
De-identified JSONL is written under `tests/fixtures/eval_runs/` (gitignored).
Live model comparison (`answer_model_standard_medical`, `answer_model_deep_medical`,
`eval_candidate_model`) is opt-in via `CURA_LIVE_MODEL_EVAL=1` and is not run
in CI. Production model choice stays “not run” until a live ZDR-compliant run
exists. `data_collection=deny` is not ZDR.

`OPENROUTER_DATA_COLLECTION_DENY` sets `provider.data_collection = "deny"`. That is
not by itself proof of zero retention. `OPENROUTER_ZERO_DATA_RETENTION` additionally
requests OpenRouter ZDR routing. Confirm current OpenRouter ZDR endpoint controls
before production personal-health LLM calls, and set
`REQUIRE_ZDR_FOR_PERSONAL_HEALTH=true` to fail closed when ZDR is not configured.

Feature flag: `ASSISTANT_QUALITY_V2` (default true). Set false to roll back
quality-gate, diagnosis-restraint retrieval, and JSON-schema structured output.

Unit and integration tests mock the typed `/api/alpha/decisions` response. They
also assert that general LDL advice performs no personal provider lookup.

Production architecture coverage includes compositional TaskPlan routing,
recommendation policy, contextual Ask Cura authorization, pre-safety, grounding fallback,
idempotency, SSE, and production rejection of mock auth.

Frontend verification:

```bash
cd ../frontend
npm run build
```

Known limitation: this suite is not a clinical validation and is not a production-readiness certificate.
