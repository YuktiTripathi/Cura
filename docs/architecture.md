# Production architecture

Cura is an independent product. SuperShyft remains the system of record for health data. Cura owns orchestration, conversation memory, evidence, safety, and LLM prompting.

```
Request
→ AuthProvider (SuperShyft JWT; mock header in development only)
→ Redis rate limit + idempotency
→ SafetyStage (pre-safety; emergency/medication/injection blocks)
→ TaskPlanner (Jev decision → TaskPlan; EntityResolver keeps every entity)
→ QueryPlan compatibility view (primary operation + needs_* flags)
→ RetrievalExecutor(user_id=authenticated subject only) → HealthDataGateway
→ HealthRetrievalRouter (independent sources; one empty source does not abort others)
→ HealthContextBuilder (all requested entities, derived Mentzer/BMI, user-stated facts)
→ ReasoningService (LOOKUP-only single entity is deterministic; multi-entity/multi-op uses the model)
→ ResponseValidator (grounding, claims, safety, fulfillment)
→ HealthGapDetector → TestNeed → PackageMatcher → PackageRecommendationPolicy
→ ResponseComposer (answer, evidence, 1–2 follow-ups, optional testing_option)
→ ChatResponse or SSE (`progress` stages, then `complete`)
```

The application determines facts. The model explains. The validator keeps the result grounded and safe.

## Rules

- Pipeline depends on provider **interfaces**, never mock classes.
- Jev is a routing-only dependency. It receives bounded semantic state, cannot
  access providers or credentials, and never creates SQL or user-facing prose.
- CURA owns validation and `QueryPlan`; invalid or unavailable Jev decisions
  fall back to the deterministic candidate and never default to retrieval.
  After a Jev decision is validated, CURA does not let the legacy source
  router reinterpret it. Confidence is Jev's primary `request_type`
  classification, accepted at ≥ 0.80. See
  [CURA_ROUTING_AND_RETRIEVAL_ARCHITECTURE.md](CURA_ROUTING_AND_RETRIEVAL_ARCHITECTURE.md).
- Cura SQLite stores conversations, messages, feedback, prompt versions, audit rows, and **document metadata**.
- Uploaded PDF bytes are stored via `DocumentStore` (local `data/uploads/` in development), not in SuperShyft.
- Health reports from SuperShyft are not copied into Cura tables.
- Uploaded documents are tagged `source=user_uploaded` and are never written back to SuperShyft.
- Trends are calculated in `trend_engine`, not by the LLM.
- Same-date Bio-AI reports are never silently merged.
- SSE `/api/v1/chat/stream` emits real `progress` stages, then `complete`. Microphone audio is transcribed with `gpt-transcribe` and discarded.
- Cross-source comparison (Phase 9) labels SuperShyft vs uploaded vs general separately. SuperShyft remains the source of truth for SuperShyft-originated data. User-uploaded documents remain independent sources.
- Uploaded PDF text is untrusted evidence, never system instructions. See [docs/safety.md](safety.md) and [docs/testing.md](testing.md).

## Before

The original runtime had a single JSON chat endpoint, development header auth,
free-form LLM output, partial post-safety, no contextual Ask Cura reference,
unused grounding code, no Health Scenario engine, no recommendation policy,
and no Redis request controls.

## After

- Canonical DTOs and `ProviderRegistry` remain the only health-data boundary.
- `TaskPlan` is the compositional contract: `entities[]`, `operations[]`, `sources[]`.
- `QueryPlan` is a derived compatibility view for `ChatMeta.intent` and retrieval flags.
- `HealthContext` is the only personal health object sent to the LLM.
- LOOKUP-only single-entity answers stay deterministic. Multi-entity or INTERPRET/CORRELATE/TREND/SUMMARIZE/RECOMMEND/IDENTIFY_GAPS/VERIFY_PREMISE uses `ReasoningService`.
- Derived Mentzer (MCV/RBC) and BMI are computed by the application. User-stated values are never stored as labs.
- `ContextRef` contains identifiers only; the server re-fetches owned data.
- `HealthContextBuilder` fills every requested source and derived metric.
  `trend_engine` and `RecommendationEngine` make deterministic decisions
  before explanation. Chat does not use `/me` snapshot paths.
- Pre-safety can short-circuit urgent, diagnostic, medication/dosage, injection,
  and out-of-scope requests.
- Structured LLM output is parsed and recommendations are treated as candidates.
- Grounding rejects unsupported personal numbers and falls back deterministically.
- Redis-backed rate limiting and idempotency are available; development uses a
  bounded in-process fallback.
- Chat supports JSON and SSE without creating a separate reasoning pipeline.
- Conversation persistence stores semantic state, not authoritative medical facts.
- Diagnostic package names come from the SuperShyft catalog after medical gap detection. See [diagnostics.md](diagnostics.md).
- Personalization overlays (`PersonalizationContext`, baselines, health story, quiet mode) summarize existing profile, goals, lifestyle, questionnaire, and history. They are not a second clinical store. Conversation-stated symptoms and supplements stay session-level. See [personalization.md](personalization.md).

## Data boundaries

`DATABASE_URL` owns Cura conversations, messages, feedback, audit metadata, and
document metadata. `SUPERSHYFT_DATABASE_URL` is read-only and separate. Uploaded
PDF bytes use `DocumentStore`. Redis stores short-lived request/conversation
controls. Current medical facts are re-read from providers on every relevant turn.

## Temporary integration

`integrations/supershyft/` is a controlled SELECT-only bridge. It normalizes
rows into canonical Cura DTOs. It is not the desired final semantic owner.
Replace this provider with a canonical SuperShyft API/resolver adapter when that
contract is available; no pipeline or prompt changes should be required.
