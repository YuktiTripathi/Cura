# CURA Routing & Retrieval Architecture

## Goal

CURA must safely handle four major classes of user requests:

1. **Personal blood/lab values** — retrieve the correct authenticated user's value/report.
2. **Personal Bio-AI reports** — retrieve the user's Bio-AI assessment from SuperShyft.
3. **Medical/diagnostic questions and guidance** — retrieve medical evidence first, then let the medical LLM explain it.
4. **Nutrition/lifestyle questions** — general LLM guidance, or personalized guidance only when the user explicitly asks for it.

## Routing contract

Jev is the **request classifier**, not the retrieval engine and not the medical answer generator.

Flow:

```text
User message
   |
   v
Conversation context + auth/document availability
   |
   v
JEV Decisions API
   |
   |  primary route + request_type confidence
   v
CURA validation
   |
   |  reject unsafe/inconsistent/low-confidence route -> deterministic fallback
   |  (deterministic path still uses attach_ontology + source_routing)
   v
Jev mapper -> QueryPlan
   |
   |  normalize_requested_metrics (names only; no source/intent rewrite)
   |
   +--> personal blood -> SuperShyft read-only IHR
   +--> personal Bio-AI -> SuperShyft read-only IHR
   +--> uploaded report -> owned-document retrieval
   +--> general medical/guidance -> medical evidence retrieval
   +--> nutrition/lifestyle -> LLM (+ personal context only when required)
   |
   v
Context + provenance
   |
   v
Medical/general LLM
   |
   v
Safety + grounding + renderer
```

### Important invariant

After a Jev decision passes validation, **do not run the legacy heuristic source router again**.

The previous design was:

```text
Jev -> mapper -> attach_ontology -> source_routing -> QueryPlan
```

This allowed a second heuristic layer to reinterpret a valid Jev decision (for example, flipping a blood lookup to an uploaded PDF because `document_ids` were present).

The target design is:

```text
Jev -> validation -> mapper -> QueryPlan
```

`normalize_requested_metrics` may still canonicalize marker/entity names (LDL Cholesterol → `ldl`, PCOD → `pcos`). It must not change the selected source, personal-data dependency, or operation.

`attach_ontology` and `apply_source_routing` remain on the **deterministic** path used when Jev is disabled, unavailable, invalid, or below the 0.80 `request_type` threshold.

## Confidence

The `confidence` field is the confidence of the **primary request classification** (`request_type`).

It is intentionally **not**:

```text
min(intent_confidence, source_confidence, operation_confidence, time_confidence)
```

Those are independent decisions. A low confidence in `time_scope`, for example, should not downgrade an otherwise high-confidence request classification.

CURA keeps auxiliary field confidences on `JevDecision.field_confidences` for observability.

Current acceptance rule:

```text
request_type confidence >= 0.80
```

Below 0.80, or if the decision is malformed/inconsistent, CURA falls back to the deterministic router. CURA must never manufacture a confidence value above 0.80.

## Personal blood values

For a query such as:

> What is my LDL?

the route must resolve to:

```text
intent: lab_result_lookup
source: lab_results
operation: lookup
requires_personal_data: true
time_range: latest
```

The authenticated principal supplies the SuperShyft `user_id`. The IHR repository performs a parameterized read scoped to that user. The selected marker is then chosen from the returned reports using the canonical marker key and latest report date.

The LLM is not allowed to invent or select the raw value.

## Bio-AI

For:

> What is my cardiac health score?

the route is:

```text
intent: bio_ai_report_lookup
source: bio_ai_report
operation: lookup
requires_personal_data: true
```

For:

> Why is my cardiac health risk high?

the route is:

```text
intent: bio_ai_report_interpretation
source: bio_ai_report
operation: retrieve_and_explain
requires_personal_data: true
```

The score itself should remain structured evidence from the database. The LLM explains it only after retrieval.

A validated Jev Bio-AI or blood classification is accepted as-is. CURA no longer overrides Jev with a legacy Bio-AI-vs-blood mismatch heuristic. When Jev is off, the deterministic planner still maps PCOD/PCOS risk questions to Bio-AI.

## Medical/diagnostic guidance

Examples:

> What is cystatin C?

> What does a high cystatin C mean?

> What should I do if my blood pressure is high?

If the question is general, no SuperShyft retrieval is needed.

CURA retrieves the relevant medical evidence corpus first. The LLM receives those source pointers/passages and is instructed not to invent guidelines, organizations, citations, diagnoses, or prescriptions.

For a personal interpretation:

> My cystatin C is 1.4. What does that mean?

CURA first retrieves the user's value, then adds medical evidence for the explanatory portion.

## Nutrition/lifestyle

General:

> What foods can help lower LDL?

This remains a general medical/nutrition answer and should not query SuperShyft merely because LDL is mentioned.

Personalized:

> Based on my LDL and Bio-AI report, what dietary changes should I consider?

This can request multiple personal sources. Blood/Bio-AI flags are set only when Jev selects `multiple_sources`. The route should explicitly indicate the personal dependency instead of allowing the source router to infer it later.

## Required regression coverage

The routing evaluation set should contain examples for:

- latest blood value
- previous blood value
- trend over time
- blood-marker interpretation
- Bio-AI score
- Bio-AI interpretation
- Bio-AI comparison
- general biomarker education
- general diagnostic guidance
- personal diagnostic interpretation
- general nutrition
- personalized nutrition
- general lifestyle
- personalized lifestyle
- uploaded diagnostic PDF
- cross-source comparison
- ambiguous questions
- conversational follow-ups
- pronoun follow-ups such as `Why?`, `What about mine?`, and `What about the previous one?`

For each case, evaluate at least:

- route intent
- personal-data dependency
- source
- operation
- historical dependency
- document dependency
- confidence
- final QueryPlan flags
- actual retrieval provider invoked
- provenance in the final answer

## Safety boundary

Jev decides **what operation is needed**.

CURA owns:

- authentication
- authorization
- user scoping
- retrieval
- medical evidence retrieval
- provenance
- safety
- grounding
- final answer generation

Jev must never receive database credentials, raw health records, or authority to execute SQL.
