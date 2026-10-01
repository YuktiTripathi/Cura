# Cura — effectiveness review and interactive frontend plan

Status: proposal · Scope: backend pipeline, codebase size, frontend

This review is based on a read of the code on `main` (5 commits), a full backend test run, and
profiling of `POST /api/v1/chat` with mock providers.

---

## 1. Is ~750 Python files too much?

**What is actually in the repo:** 297 tracked `.py` files, ~44.6k lines.

| Area | Files | Lines |
|---|---:|---:|
| `backend/app/pipeline` | 83 | 17,868 |
| `backend/app/contracts` | 33 | 2,233 |
| `backend/app/documents` | 23 | 2,277 |
| `backend/app/routing` | 7 | 1,779 |
| other `backend/app/*` | 63 | ~5,000 |
| `backend/tests` | 63 | — |
| `integrations/` | 16 | — |

If you see ~750 locally, the extra ~450 are almost certainly `backend/.venv/` or `__pycache__`
(both git-ignored). Exclude them from your editor/search.

**File count is not the problem. Shape is.** The real issues:

1. **One 1,000-line function.** `ChatService._execute_chat` (`backend/app/pipeline/service.py:203`)
   contains every route (safety block, clarification, cross-source, documents, casual, general,
   personal) as inline branches with ~15 early `return ChatResponse(...)` sites, each hand-building
   `ChatMeta`. This is where bugs and regressions will concentrate.
2. **Three overlapping routers.** Regex intent (`intent.py`) → `query_planner.py` → `planner.py`
   (TaskPlan) → Jev LLM → `validate_jev_decision` / `_maybe_demote_personal` overrides. The
   deterministic plan is always built *and* Jev is called, then reconciled.
3. **Layers that say the same thing in different files:**
   - safety: `safety.py`, `safety_classifier.py`, `clinical_postcheck.py`
   - answer checks: `validator.py`, `grounding.py`, `claim_check.py`, `quality_gate.py`
   - presentation: `renderer.py`, `presentation.py`, `composer.py`, `conversation_experience.py`
   - narrative: `narrative.py`, `health_narrative.py`, `health_story.py`, `health_snapshot.py`
4. **Dead code:** `pipeline/followups.py` (only raises), `llm/interface.py` (unused Protocol).
5. **276 module-level regexes** carry the language understanding. They are brittle to phrasing,
   typos, and non-English input.
6. **`ChatMeta` has ~72 fields**, most of them debug/telemetry, sent on every response.

### Target shape (~150–180 files, no behaviour change)

```
backend/app/pipeline/
  orchestrator.py        # thin: safety → route → handler → postcheck → persist
  handlers/              # one file per route, each returns a TurnResult
    safety_block.py  clarify.py  casual.py  general.py
    personal.py  document.py  cross_source.py
  routing/               # intent + query_planner + planner + Jev merged behind one Router
  safety/                # pre-check, post-check, classifier
  verification/          # validator + grounding + claim_check + quality_gate
  presentation/          # renderer + presentation + composer + experience
  health/                # narrative, story, snapshot, timeline, gaps, trends
  meta.py                # single ChatMeta builder (removes ~15 copies)
```

Do it incrementally: extract one handler at a time, keep the golden/contract tests green after each.

---

## 2. Making Cura more effective (prioritised)

### P0 — done in this branch: routing was ~450 ms of pure regex compilation

`lab_parameters._alias_span` built a new regex per alias (~1,000 aliases) on every call. Python's
regex cache holds 512 entries, so every request recompiled ~9,000 patterns.

| Query | Before | After |
|---|---:|---:|
| "what is my ldl" | 449 ms | 4 ms |
| "how is my vitamin d trending" | 457 ms | 6 ms |
| "summarize my health" | 379 ms | 63 ms |

Fix: `functools.lru_cache` on the compiled pattern. Same semantics.

### P0 — stream real tokens

`CHAT_STREAMING_MODE=complete_only`: the SSE endpoint emits progress stages, then the whole answer.
With Jev (up to 10 s) + answer LLM (12–28 s tier caps) in series, users stare at a spinner.

Plan:
1. Emit a **`block` SSE event** as soon as deterministic content exists (findings cards, values,
   ranges are known from retrieval before the LLM runs). Users see their numbers in < 1 s.
2. Stream the LLM narrative as `token` events. The answer model returns structured JSON, so stream
   only the `answer` field (incremental JSON parse) and run claim/safety post-checks on completion;
   if post-check rewrites the text, send a `replace` event.

### P1 — one routing decision, not three

- Use the deterministic planner when it is high-confidence (single known marker, explicit source).
  Only call Jev for low-confidence / multi-intent / follow-up turns. Removes an LLM hop from most
  personal lookups.
- When Jev is needed, **prefetch** SuperShyft data for the deterministic plan in parallel with the
  Jev call; discard if Jev disagrees.
- Log `deterministic_plan` vs `jev_plan` disagreements and review them weekly — that is your
  routing eval set.

### P1 — break up `_execute_chat`

Route → handler (strategy pattern), shared `TurnContext` in, `TurnResult` out, one `build_meta()`.
This makes each path testable on its own and makes the streaming change above tractable.

### P1 — evaluation loop

- There are golden tests (`tests/golden`) but no measured quality signal from real use. Persist
  thumbs up/down (already sent via `/feedback`) with `intent`, `router`, `answer_model_tier`, and
  build a weekly report: satisfaction by intent and by model tier.
- Turn disagreements, thumbs-down and `quality_gate` repairs into new golden cases.

### P2 — smaller wins

- **Prompt caching**: the system prompt and HealthContext preamble are stable per user/session;
  enable provider prompt caching through OpenRouter to cut cost and latency on follow-ups.
- **Trim `ChatMeta`**: send ~10 user-relevant fields; move routing/model telemetry to logs or a
  dev-only `debug` object (already partly done).
- **Stop computing what nobody renders**, or render it (see §3): `proactive_insights`,
  `health_journey`, `clinician_handoff`, `structured_next_steps`, `blocks`, `suggestion_chips` are
  built in the backend and ignored by the UI.
- **Typed contract**: these are `Record<string, unknown>` in `frontend/src/types/chat.ts`. Generate
  TS types from `contracts/openapi.yaml` (`openapi-typescript`) so the two sides cannot drift.
- Delete `pipeline/followups.py` and `llm/interface.py`.

---

## 3. Interactive frontend plan

### Where it is today

React 18 + Vite + TS, plain CSS, ~3.5k lines. A solid chat: sidebar, composer with PDF/voice,
progress state, findings cards, theme cards, testing-option card, follow-up chips, edit-and-resend.
Gaps: no token streaming, no charts, no visual reference ranges, evidence is not explorable,
half the backend's structured output is unused, no dark mode, a single 511-line `MessageList`.

### Experience goals

1. **Show my numbers instantly**, explain them while streaming.
2. **Every claim is one tap from its source** (report, date, page, excerpt).
3. **Ask about anything on screen** — every value, card and chart has "Ask Cura".
4. **It feels like a health companion, not a text box** — a home dashboard and a context panel.

### Layout

```
┌────────────┬───────────────────────────────┬──────────────────────┐
│ Sidebar    │ Conversation                  │ Context panel        │
│ • New chat │  user bubble                  │ (opens on demand)    │
│ • History  │  ┌ answer ──────────────────┐ │ • Source report view │
│ • Docs     │  │ progress stepper         │ │   (page + highlight) │
│ • Health   │  │ value cards w/ range bar │ │ • Marker history     │
│   overview │  │ trend chart              │ │   chart + table      │
│            │  │ streamed narrative       │ │ • "Ask about this"   │
│            │  │ [src chips] next steps   │ │                      │
│            │  └──────────────────────────┘ │                      │
│            │  follow-up chips              │                      │
│            │  composer: 📎 🎙 text  send     │                      │
└────────────┴───────────────────────────────┴──────────────────────┘
Mobile: sidebar = drawer, context panel = bottom sheet.
```

### Components (new or reworked)

| Component | What it does | Backend data |
|---|---|---|
| `ProgressStepper` | Live steps: "Reading your blood report (12 Mar)…" | existing `progress` SSE |
| `StreamingAnswer` | Renders `block` events then `token`s; markdown | new SSE events (§2) |
| `ValueCard` + `RangeBar` | Value, unit, status colour, position within reference range | `PresentedFinding`, `EvidenceItem.reference_range` |
| `TrendChart` | Sparkline in card, full chart in context panel | **new** `series` on findings (history already retrieved) |
| `ThemeCard` | Narrative themes, priority, expandable related findings | `themes` |
| `EvidenceChip` → `SourceViewer` | Opens report at page with excerpt highlighted | `EvidenceItem.page_start/excerpt/document_id` |
| `NextStepsChecklist` | Tickable next steps, persisted per conversation | `structured_next_steps` (unused today) |
| `InsightBanner` | Proactive "worth a look" insights | `proactive_insights` (unused today) |
| `DoctorSummary` | "Share with my doctor" — printable/PDF one-pager | `clinician_handoff` (unused today) |
| `TestingOptionCard` | Keep; add compare-with-existing table | `testing_option.comparison` |
| `SafetyBanner` | Distinct, non-dismissable emergency styling | `meta.escalation`, `safety_flags` |
| `HealthHome` | Replaces welcome: snapshot tiles, flagged markers, data gaps, personalised starters | `/me` + new `/me/snapshot` (`health_snapshot.py` exists) |
| `DocumentDropzone` | Drag-drop, extraction progress, extracted values preview, "compare with SuperShyft" | `/documents` |
| `MessageActions` | Copy, regenerate, 👍/👎 with reason | `/feedback` |

Everything with a value gets an **"Ask Cura"** affordance that sends a `context_ref` — the backend
already supports this (`/api/v1/context/{type}/{id}`).

### Tech choices

- Keep **React + Vite + TS**.
- **TanStack Query** for server state (conversations, documents, me); a small reducer for the
  streaming turn.
- **Radix UI primitives** (dialog, sheet, tooltip, tabs) for accessibility; **Tailwind** or CSS
  variables with light/dark tokens.
- **Recharts** (or visx) for trends; **react-markdown** for answer text.
- **openapi-typescript** to generate `types/` from `contracts/openapi.yaml`.
- Split `MessageList.tsx` into `messages/` (`UserMessage`, `AssistantMessage`, `blocks/*`).

### Backend changes the frontend needs

1. SSE: `block`, `token`, `replace` events (§2).
2. `PresentedFinding.series: [{date, value}]` and `reference_low/high` as numbers.
3. Typed models for `proactive_insights`, `structured_next_steps`, `clinician_handoff`,
   `health_journey`, `blocks` (discriminated union on `kind`).
4. `GET /api/v1/me/snapshot` for the home dashboard.
5. `GET /api/v1/documents/{id}/pages/{n}` (image or text) for the source viewer.

### Phases

| Phase | Scope | Exit criteria |
|---|---|---|
| 1. Foundation | Generated types, TanStack Query, design tokens + dark mode, split MessageList, `ProgressStepper` | No visual regression; tests green |
| 2. Rich answers | `block`/`token` streaming, ValueCard + RangeBar, EvidenceChip → SourceViewer, MessageActions | First content < 1 s on personal lookups |
| 3. Companion | HealthHome, TrendChart + context panel, NextSteps, InsightBanner, DoctorSummary | All backend structured fields rendered or removed |
| 4. Polish | Dropzone + compare flow, voice waveform, i18n, a11y audit, mobile bottom sheet | Lighthouse a11y ≥ 95 |

### Status (implemented on `claude/cura-chatbot-frontend-plan-5rlncr`)

- **Phase 1** – done: generated API types with drift checks, TanStack Query, design tokens + dark mode,
  MessageList split, progress stepper.
- **Phase 2** – done: early value preview over SSE (`preview` event; first values ~100 ms vs ~4 s for
  the answer with a simulated LLM delay), value cards with reference-range bars, message actions,
  sources viewer with highlighted PDF rows (`/documents/{id}/pages/{n}`). Token streaming of the LLM
  explanation was deliberately not done: safety/claim post-checks run on the finished answer.
- **Phase 3** – done: home dashboard and marker panel with trend chart (`/me/overview`), in-chat insight
  note, doctor summary (print/copy), tickable next steps, merged suggestion chips.

#### What happened to each backend `StructuredResponse` field

| Field | UI | Notes |
|---|---|---|
| `proactive_insights` | Rendered ("Worth a look" under the answer) | Suppressed items dropped; max 2; only what the backend attached to that answer. |
| `clinician_handoff` | Rendered ("Doctor summary" dialog, print/copy) | Shown when it has key findings. |
| `suggestion_chips` | Rendered (merged into follow-up chips) | De-duplicated against `follow_ups`, max 3. |
| `next_steps` | Rendered (tickable checklist) | Ticks stored per device in `localStorage`. |
| `topic_summary`, `themes`, `raw_findings`, `related_findings`, `testing_option` | Rendered (already before Phase 3) | |
| `health_journey` | Not rendered per answer | Mixes display names and internal codes (`iron_status`); the home dashboard computes "improving" from `/me/overview` histories instead. **Recommend removing from the chat response.** |
| `blocks` | Not rendered | Repeats the summary/headline with mostly empty `text` ("LDL LDL cholesterol …"). **Recommend removing.** |
| `structured_next_steps` | Not rendered | Always emptied (`pipeline/presentation.py` sets it to `[]`). **Recommend removing.** |

The three "recommend removing" fields were left in the API so this branch stays additive for any other
client; dropping them is a one-line change per field once confirmed unused elsewhere.

### How to tell it's working

- Time to first meaningful content (p50/p95).
- Follow-up chip and "Ask Cura" click-through rate.
- Evidence chip open rate (trust signal).
- 👍 rate by intent; 👎 reasons.
