# Semantic response contract

```
User question → CURA reasoning (one answer-model call) → semantic response
             → backend validation/enrichment → response blocks → generic frontend renderer
```

CURA decides what matters, the backend guarantees the data, and the frontend makes it
understandable.

Turn it on with `CURA_RESPONSE_MODE=semantic`. `plain` and `rich` are unchanged.
In semantic mode:

- `ChatResponse.answer` stays the complete conversational Markdown (exactly the plain-mode
  answer).
- `ChatResponse.semantic` carries the structured view of the **same** answer.
- Development builds (`VITE_CURA_DEBUG=true`) show a "Show raw answer / Show structured
  view" switch for comparing the two.

Files:

- `backend/app/contracts/semantic_response.py`: the models.
- `backend/app/pipeline/semantic_blocks.py`: validation and value resolution.
- `frontend/src/types/semantic.ts`: the TypeScript mirror.
- `frontend/src/components/messages/SemanticAnswer.tsx`: the one generic renderer.

## Contract

```ts
type BlockType = "text" | "metric" | "metric_group" | "priority_list" | "risk" | "comparison"
               | "insight" | "reassurance" | "action_list" | "nutrition" | "warning";

interface SemanticResponse { summary: string; blocks: ResponseBlock[]; follow_ups: string[]; sources: ResponseSource[] }

interface ResponseBlock {
  type: BlockType; title?: string; text?: string;          // text is safe Markdown
  items?: BlockItem[];                                      // priority_list, action_list
  evidence?: string[]; values?: ResolvedValue[];            // keys from the model; values from the backend
  increase?: string[]; reduce?: string[];                   // nutrition
  collapsed?: boolean;                                      // metric_group starts folded
}
interface BlockItem { title?: string; text?: string; evidence?: string[]; values?: ResolvedValue[] }
interface ResolvedValue {
  key: string; label: string; kind: "blood" | "bio_ai"; value?: number | string; unit?: string; status?: string;
  reference_low?: number; reference_high?: number; date?: string;
  previous?: number | string; previous_date?: string; direction?: string;
}
interface ResponseSource { type: "blood_report" | "bio_ai" | "questionnaire" | "uploaded_document" | "medical_reference"; date?: string; label?: string }
```

The Pydantic models in `semantic_response.py` have the same shape:

```
SemanticResponse(summary, blocks: list[ResponseBlock], follow_ups: list[str], sources: list[ResponseSource])
ResponseBlock(type: BlockType, title, text, items: list[BlockItem], evidence, values: list[ResolvedValue], increase, reduce, collapsed)
```

**Evidence keys:**

| Key | Meaning |
|---|---|
| `blood.<code>.latest` | the latest measured value |
| `blood.<code>.trend` | previous vs latest |
| `bioai.<code>` | a Bio-AI risk |

The model only references keys. The backend fills `values` from the member's normalized
context for this turn. A key that does not resolve is dropped, and so is any value the
model wrote into a block.

## Who does what

| Layer | Responsibility |
|---|---|
| Answer model (same single call) | `answer` (full Markdown), `summary` (1–3 standalone sentences) and 0–3 `blocks` with titles, text and evidence keys. It chooses whether to use blocks at all; a simple question gets none. |
| Backend (`semantic_blocks.py`) | Drops unknown types and empty blocks; caps at 4 blocks and 6 items. Resolves keys to values. Runs the answer's number-grounding check on every block sentence. Applies report-range precedence and removes internal ids. Shows no model block when safety or validation replaced the answer. Builds the deterministic views: the report listing and value lookups. |
| Frontend (`SemanticAnswer.tsx`) | One `switch (block.type)`: summary, then blocks, then a compact Sources disclosure. Follow-ups render as the existing chips. Unknown types render nothing. Markdown is converted to React elements, never HTML. No medical logic. |

If there are no blocks, `summary` is the whole answer, so nothing is hidden. The block
instructions are sent to the model only in semantic mode, which adds about 250 tokens of
system prompt.

## One example per block type (backend output)

```json
{"type":"text","title":"A note on fasting","text":"The report doesn't say whether this glucose was fasting."}
{"type":"metric","evidence":["blood.tsh.latest"],"values":[{"key":"blood.tsh.latest","label":"TSH","kind":"blood","value":2.1,"unit":"uIU/mL","status":"normal","reference_low":0.4,"reference_high":4.0,"date":"2026-09-28"}]}
{"type":"metric_group","title":"Outside your report's range","values":[{"key":"blood.hba1c.latest","label":"HbA1c","value":9.1,"unit":"%","status":"high"}, "…"]}
{"type":"metric_group","title":"All 20 results","collapsed":true,"values":["… 20 resolved values …"]}
{"type":"priority_list","title":"Your top 3","items":[{"title":"Bring blood sugar down","evidence":["blood.hba1c.latest"],"values":["…HbA1c 9.1 %…"]},{"title":"Lower triglycerides and LDL"},{"title":"Rebuild iron stores"}]}
{"type":"risk","title":"Risk overview","values":[{"key":"bioai.type_2_diabetes","label":"Type 2 diabetes","kind":"bio_ai","value":78.0,"status":"high"},{"key":"bioai.dyslipidemia","label":"Dyslipidemia","kind":"bio_ai","value":71.0,"status":"high"}]}
{"type":"comparison","title":"Since your last report","values":[{"key":"blood.hba1c.trend","label":"HbA1c","value":9.1,"unit":"%","previous":8.4,"previous_date":"2026-04-10","direction":"increased"}]}  // gitleaks:allow
{"type":"insight","title":"Why this may be happening","text":"Your HbA1c, glucose and triglycerides are all above range and point the same way.","values":["…3 resolved values…"]}
{"type":"reassurance","title":"Within range","text":"Liver enzymes, kidney function and thyroid markers are all within your report's ranges.","values":["…"]}
{"type":"action_list","title":"A first step for each","items":[{"title":"A 10–15 minute walk after meals"},{"title":"Swap refined grains for whole grains"}]}
{"type":"nutrition","title":"Where I'd focus","increase":["Vegetables and pulses","Whole grains"],"reduce":["Refined grains and sugary drinks"],"text":"These support both your blood sugar and your blood fats."}
{"type":"warning","text":"Please talk to your doctor about this result soon."}
```

## Validation (same user, `scripts/semantic_examples.py --offline`)

This run used a scripted stand-in for the answer model. The summaries and block choices
below are scripted. Every value was resolved by the backend from the mock records, and
the report and lookup views are deterministic. For CURA's own block choices, run
`CURA_RESPONSE_MODE=semantic python scripts/semantic_examples.py --user <id>`.

| Kind | Question | Rendered |
|---|---|---|
| Blood report | Show me my latest blood report. | summary · metric_group "Outside your report's range" (11) · metric_group "All 20 results" (collapsed) |
| Simple marker lookup | Is my TSH normal? | summary · metric (TSH 2.1 uIU/mL, normal, range bar) |
| Ask anything | What does my HbA1c mean? | summary · metric (HbA1c) · insight "It isn't a one-off" (glucose, HbA1c 8.4 → 9.1) |
| Health scenario | What should I actually pay attention to? | summary · priority_list (blood sugar / blood fats / iron, each with its values) · reassurance |
| Priorities | What are the top 3 things I should work on? | summary · priority_list (ranked) · action_list |
| Bio-AI | Why is my Bio-AI metabolic risk high? | summary · risk (T2D high, dyslipidemia high) · insight (HbA1c, glucose, TG) · reassurance |
| Reassurance | What is reassuring in my health data? | summary · reassurance (HDL, TSH, ALT) |
| Lifestyle | Could my lifestyle be contributing? | summary · action_list |
| Nutrition | What nutrition changes make sense for my current results? | summary · nutrition (more of / less of / why) |
| Trend comparison | Has my HbA1c improved? | summary · comparison (HbA1c 8.4 → 9.1, increased) |
| Symptom | Why am I feeling tired? | summary · insight (haemoglobin, ferritin low) · reassurance (TSH normal) |
| Style | Give me the short version. | summary only |

The same eleven-type library covered every question, and each question got a different
structure. None of the shapes is tied to an intent.

## Not covered yet

- **Reloaded conversations:** stored messages keep only `answer`, so they render as Markdown.
- **Streaming:** shows the existing preview, and the structured view replaces it when the
  turn completes.
- **Out-of-scope keys:** a key outside this turn's selected context does not resolve. That
  is by design, since the backend only shows values it retrieved for this turn.
