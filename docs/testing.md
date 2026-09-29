# Testing and evaluation (Phase 10)

Run the full suite from `backend/`:

```bash
cd /Users/yuks/Desktop/Cura/backend
source .venv/bin/activate
PYTHONPATH="/Users/yuks/Desktop/Cura/backend:/Users/yuks/Desktop/Cura" pytest --rootdir=/Users/yuks/Desktop/Cura/backend
```

Default: `ENABLE_LLM=false` (deterministic renderer). Tests assert **sources, values, safety, and query plans**, not exact wording.

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

Evaluation fixtures:

- `backend/tests/fixtures/eval_cases.json`: production answer/evidence cases.
- `backend/tests/fixtures/cura_routing_eval_500.jsonl`: 533 synthetic routing
  cases covering general/personal pairs, context, history, Bio-AI, documents,
  ambiguity, negative cases, and six supported languages.

The production golden suite parametrizes this dataset and verifies intent,
sources, markers, evidence, escalation, follow-ups, and prohibited claims:

```bash
pytest tests/golden/test_production_eval.py -q
python scripts/benchmark_routing.py
```

The routing benchmark always reports the deterministic baseline. Live Jev and
Jev+CURA-validation measurements are opt-in because they use OpenRouter:

```bash
python scripts/benchmark_routing.py --live --output /tmp/cura-jev-eval.json
```

Unit and integration tests mock the typed `/api/alpha/decisions` response. They
also assert that general LDL advice performs no personal provider lookup.

Production architecture coverage includes Health Scenario, recommendation
policy, contextual Ask Cura authorization, pre-safety, grounding fallback,
idempotency, SSE, and production rejection of mock auth.

Frontend verification:

```bash
cd ../frontend
npm run build
```

Known limitation: this suite is not a clinical validation and is not a production-readiness certificate.
