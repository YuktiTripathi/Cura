# CURA Routing & Retrieval Architecture

## Goal

CURA must safely handle compositional health questions: many entities, many sources, and many operations in one turn.

1. **Personal blood/lab values** — retrieve every requested authenticated marker, not the first match.
2. **Personal Bio-AI reports** — retrieve the user's Bio-AI assessment from SuperShyft.
3. **Medical/diagnostic questions and guidance** — retrieve medical evidence first, then let the medical LLM explain it.
4. **Nutrition/lifestyle questions** — general LLM guidance, or personalized guidance only when the user explicitly asks for it.
5. **Pattern / review questions** — retrieve the full entity set and sources; the model synthesizes; the validator grounds.

## Six-stage pipeline

```text
User message
   |
   v
SafetyStage
   |
   v
TaskPlanner  (Jev primary; EntityResolver fills entities[]; deterministic fallback never uses labs[0] as the only topic)
   |
   v
HealthRetrievalRouter  (blood, Bio-AI, questionnaire, goals, documents independently)
   |
   v
HealthContextBuilder  (all entities + derived Mentzer/BMI + user_stated + premise + missing)
   |
   v
ReasoningService  (LOOKUP-only single entity → renderer; otherwise LLM explains the supplied facts)
   |
   v
ResponseValidator + ResponseComposer
```

Rule: **the application determines facts; the model explains; the validator keeps the result grounded and safe.**

## TaskPlan

`TaskPlan` is the semantic contract:

- `question_type`: `general_education | personal_lookup | personal_health_reasoning | safety`
- `entities[]`: every mentioned biomarker/risk/derived code, not the first alias hit
- `operations[]`: `RETRIEVE | EXPLAIN | INTERPRET | COMPARE | TREND | SUMMARIZE | CORRELATE | PRIORITIZE | IDENTIFY_GAPS | VERIFY_PREMISE | RECOMMEND | ...`
- `sources[]`, `history_required`, `medical_evidence_required`, `user_stated[]`, `premise_claim`

`QueryPlan` remains a **derived compatibility view** (primary operation + `requested_metrics` + `needs_*`) so `ChatMeta.intent` and existing retrieval flags still work. There is not a second semantic router that mutates a validated TaskPlan.

Jev stays a decision layer. After validation, CURA maps `JevDecision` → TaskPlan and does **not** run `apply_source_routing` or rewrite intent to `health_scenario`.

Jev also assigns a provider-independent **model tier**. It must not name vendors or model IDs.

| Tier | Use | Configured model |
| --- | --- | --- |
| `DETERMINISTIC` | Lookup, lists, dates, reference-range status, deterministic trends | no answer LLM |
| `FAST_REASONING` | Internal planning only | GPT-5.6 Luna |
| `STANDARD_MEDICAL` | Default patient-facing medical reasoning | Gemini 3.8 Flash |
| `DEEP_MEDICAL_REASONING` | High-complexity multi-source / longitudinal synthesis | Claude Sonnet 5 |

FAST_REASONING is never used as the user-facing medical-answer model. STANDARD_MEDICAL may escalate to DEEP_MEDICAL_REASONING after the quality gate. Safety, grounding, and emergency detection stay deterministic.

## Before / after

| Question class | Before | After |
| --- | --- | --- |
| Hb + MCV + user-stated Mentzer | `topic = labs[0]`, structured blood dump of hemoglobin | all three entities in context; Mentzer is derived or user-stated, never invented as a lab |
| Glucose + HbA1c + lipids + waist | collapsed to one marker | all retrieved or scoped-missing; connections explained |
| Review everything that changed | hijack to `health_scenario` + one SUMMARIZE | blood + Bio-AI + questionnaire + goals retrieved; trends and gaps disclosed; LLM used when reasoning ops are present |

## Personal blood values

For a query such as:

> What is my LDL?

the route must resolve to a LOOKUP TaskPlan with entity `ldl`. The authenticated principal supplies the SuperShyft `user_id`. The IHR repository performs a parameterized read scoped to that user. The LLM is not allowed to invent or select the raw value.

## Confidence

The `confidence` field is the confidence of the **primary request classification** (`request_type`).

Current acceptance rule:

```text
request_type confidence >= 0.80
```

Below 0.80, or if the decision is malformed/inconsistent, CURA falls back to the deterministic planner. CURA must never manufacture a confidence value above 0.80.

`normalize_requested_metrics` may still canonicalize marker/entity names. It must not change the selected source, personal-data dependency, or collapse the entity list to `metrics[0]`.

`attach_ontology` and `apply_source_routing` remain on the **deterministic** path used when Jev is disabled, unavailable, invalid, or below the 0.80 `request_type` threshold.

After a Jev decision passes validation, do not run the legacy heuristic source router again.

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

A biomarker mention must not automatically force a latest-value answer.
`What does HbA1c measure?` is general EXPLAIN. `What is my HbA1c?` is LOOKUP.
`Why did my HbA1c increase?` is TREND with premise verification.

If a requested marker is absent, CURA returns a scoped missing result. It must
not dump the rest of the report.

Multi-source questions that name blood, Bio-AI, questionnaire, and/or goals must
attempt each requested available source independently. `provider.data_collection
= deny` is not sufficient evidence of zero retention.

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
