# Answer-model prompt audit (observability only; nothing changed)

Tooling:

- `CURA_PROMPT_DEBUG=true` is development only and ignored in production. It writes one
  sectioned dump (`.txt`) and one record (`.json`) per answer-model call to
  `CURA_PROMPT_DEBUG_DIR`. Implementation: `app/llm/prompt_inspector.py`.
- `python scripts/prompt_audit.py --offline` (or `--user <id>` live) runs the four audit
  questions and writes the component sizes.

## Where the request is sent

Every answer model goes through one function:

```
ChatService._execute_chat (app/pipeline/service.py)
  → ReasoningService.run (app/pipeline/reasoning.py)
      messages = PromptBuilder.build(context, conversation_summary, message, …)  # app/pipeline/prompt_builder.py
  → ChatService._complete_answer → get_llm_client(model_tier=…)               # tier → model id (app/llm/registry.py)
  → OpenAICompatibleLLMClient.complete_structured → _complete_structured_uncached → complete
  → _post_once → _build_payload → httpx POST {OPENROUTER}/chat/completions      # app/llm/openai_compatible.py
```

Gemini 3.8 Flash, GPT-5 mini and GPT-5.6 Luna all go through OpenRouter's
OpenAI-compatible endpoint. No native Gemini request format is used. The payload is:

```
{"model": "...", "messages": [{"role": "system", ...}, {"role": "user", ...}],
 "stream": false, "temperature": 0, "max_tokens": 800 (1200 for gpt-5*),
 "reasoning": {"effort": "low"}           # gpt-5* models only
 "response_format": {json_schema cura_answer, strict},
 "provider": {"allow_fallbacks": false, "only": [...], "data_collection": "deny"}}
```

The request always has exactly two messages, `system` and `user`. Conversation history is
not sent as message turns. It is a one-line summary inside the user message.

## Tokens

The numbers below are offline estimates (chars/4) on the mock user `eval-user-companion`.
`tiktoken` is used automatically when it can load `o200k_base`, and live runs record the
provider's reported tokens. Latency here excludes the model, which was a stand-in.

### "What does my HbA1c mean?" (routed to openai/gpt-5-mini)

| Component | Chars | ~Tokens | % of input |
|---|---|---|---|
| System prompt (identity, fact boundaries, safety, quality, editing, reasoning, questionnaire) | 6,438 | 1,610 | 48% |
| Response / format instructions (RESPONSE PLANNING, depth, brief) | 2,184 | 546 | 16% |
| Application instructions (mode, source boundaries, evidence rules) | 839 | 210 | 6% |
| Medical-evidence block (3 CDC/NIDDK summaries) | 1,326 | 332 | 10% |
| **Health context** (answer-evidence JSON) | 1,552 | 388 | 12% |
| Output contract (text in the system prompt) | 345 | 87 | 3% |
| JSON schema (`response_format`) | 495 | 124 | 4% |
| Conversation (empty summary on the first turn) | 86 | 22 | 1% |
| Current query | 40 | 10 | 0.3% |
| **Total input** | **13,305** | **~3,327** | |
| Output | max_tokens 1,200 (800 visible plus reasoning) | | |

**What the health context contains:**

| Area | Included |
|---|---|
| Profile | nothing (no profile or personalization fields) |
| Blood | HbA1c 9.1 % (high, primary); glucose 214.47 (high) and triglycerides 266 (high) as supporting facts |
| Bio-AI | nothing |
| Questionnaire | nothing |
| Previous reports | HbA1c 8.4 → 9.1 |
| Conversation | 0 turns (an empty one-line summary) |

So it is **HbA1c plus closely related markers, not the whole report.**

### Four questions compared

| | Simple: Vitamin D | Focus: HbA1c mean | Medium: TG high | Complex: Bio-AI metabolic |
|---|---|---|---|---|
| Model | gemini-3.8-flash | gpt-5-mini | gpt-5-mini | gpt-5.6-luna |
| Total input tokens | ~2,880 | ~3,327 | ~3,546 | ~3,914 |
| Instructions (system + format + app + contract + schema) | ~2,596 (90%) | ~2,577 (77%) | ~2,578 (73%) | ~2,578 (66%) |
| Health-context tokens | ~176 | ~388 | ~653 | ~996 |
| Medical-evidence block | ~80 | ~332 | ~285 | ~296 |
| Conversation tokens | ~22 | ~22 | ~22 | ~22 |
| Calls | 1 | 1 | 1 | 1 |

About 2,600 tokens of fixed instructions are sent on every call, whatever the question.
For a value lookup that is 90% of the input.

## Structured output

One schema is sent: `response_format = json_schema "cura_answer"` (strict), 495 chars,
~124 tokens:

```json
{"type":"json_schema","json_schema":{"name":"cura_answer","strict":true,"schema":{"type":"object","additionalProperties":false,
 "properties":{"answer":{"type":"string"},"claims":{"type":"array","items":{"type":"object"}},"recommendation_candidates":{"type":"array"},
 "follow_up_questions":{"type":"array","items":{"type":"string"}},"safety_flags":{"type":"array","items":{"type":"string"}},
 "escalation":{"type":["string","null"]}},"required":["answer"]}}}
```

The same contract is also written in prose at the end of the system prompt ("Return a JSON
object with: …", 345 chars). If a provider rejects the schema, the fallback is
`{"type":"json_object"}` and then plain text. A malformed answer triggers one repair call;
both of these happen only on failure.

## Repeated guidance

These are counts in the assembled HbA1c request. The complex query has more.

| Guidance | Times stated | Where |
|---|---|---|
| Use the report's own range / not a generic one | 6 | system FACT BOUNDARIES, system REASONING ×2, evidence `report_range` |
| Do not diagnose / possibilities are not diagnoses | 5 (7 in complex) | system ×3, app SOURCE BOUNDARIES, depth line |
| No emergency language for routine labs / red flags | 5 | system ×3, REASONING |
| Do not prescribe / medication | 4 | system SAFETY, CONVERSATIONAL, medical block |
| Do not invent data | 4 | system intro, FACT BOUNDARIES, app instructions, medical block |
| Lead with the direct answer | 4 | system intro, RESPONSE QUALITY, CONVERSATIONAL EDITING, depth line |
| Don't list unrelated markers | 4 | RESPONSE QUALITY, CONVERSATIONAL EDITING ×2, RESPONSE BRIEF |
| Questionnaire is self-reported, not a cause | 4 (7 when sent) | FACT BOUNDARIES, QUESTIONNAIRE section ×2, app SOURCE BOUNDARIES (plus the evidence `use` field) |
| Be concise | 4 | system intro, CONVERSATIONAL, RESPONSE PLANNING, brief |
| Missing data: mention only if it matters | 3 | RESPONSE QUALITY, REASONING, depth line |
| Keep numbers/terms unchanged | 2 | FACT BOUNDARIES, app instructions |
| Don't repeat what was already explained | 2 | RESPONSE QUALITY, brief |

Instructions written for the older context path are still sent on the answer-evidence path
(every personal answer):

- **FACT BOUNDARIES** names labels that do not appear in this payload: MEASURED_DATA,
  QUESTIONNAIRE_RESPONSE, USER_STATED…, MEDICAL_EVIDENCE.
- **"For complex health reviews, group findings into themes"** overlaps with RESPONSE PLANNING.
- **"Answer depth: simple"**, **"Depth: interpret …"** and the **RESPONSE BRIEF** sit next to
  `how_to_answer`, which says the same thing. For the Vitamin D lookup, "Depth: interpret"
  conflicts with "Keep the answer compact". The INTERPRET operation the router adds for
  model lookups is what selects that depth line.

## Possibly unnecessary health context

- **HbA1c:**
  - No basophils, platelets, thyroid, liver, kidney or iron markers are sent.
  - Duplication: HbA1c, glucose and triglycerides each appear twice, once as facts and once
    inside `patterns` (~110 tokens).
  - Triglycerides arrive through the related-marker map (`health_patterns.related_markers`)
    and as the "blood fats" pattern. They are defensible context for "what does it mean
    for me", but they are the main candidate to drop.
  - The **medical-evidence block** (~332 tokens) is three CDC/NIDDK topic summaries, two of
    them about eating and activity for diabetes management, which is more than a meaning
    question needs.
- **Vitamin D:** only Vitamin D plus 3 pattern names (`other_notable_findings`) are sent.
  That is minimal.
- **Triglycerides:**
  - Sent: triglycerides, HbA1c, glucose, HDL (normal), the triglycerides trend and
    3 questionnaire answers (activity, sitting, refined grains; 174 tokens).
  - All of these are relevant to "why".
  - The same values are duplicated inside `patterns`.
- **Complex (Bio-AI metabolic):**
  - Sent: T2D 78 and NAFLD 48 as facts; dyslipidemia appears only as a pattern tag.
  - Also sent: glucose, HbA1c, HDL, triglycerides, the reassuring "liver enzymes: ALT"
    group, the glucose trend and 3 questionnaire answers.
  - NAFLD (moderate) and the ALT reassurance are borderline for "metabolic risk".

## Behaviour issues found by the audit (not fixed)

1. **Complex query premise check:** `premise_check` says *"metabolic score is high — this
   result was not found in the member's records. Say that, and do not guess a value"*,
   while the Bio-AI type 2 diabetes risk (78, high) is in the same prompt. "Metabolic risk"
   resolves to the `metabolic_score` topic, which this user's report lacks. The instruction
   pushes the model to say "not found" for a question the data can answer.
2. **Complex query uncertainty:** the uncertainty list asks the model to mention that
   *fasting insulin was not in reports*, an expanded entity the member never asked about.
3. **Vitamin D lookup:** it gets "Depth: interpret …" alongside "Keep the answer compact"
   (see above).
