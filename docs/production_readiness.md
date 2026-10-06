# Production readiness: implementation status

Tracks the Cura Production Readiness Plan (Oct 6, 2026). "Code" means the change is in this repo.
"Owner action" means a person has to do it; code cannot.

## P0 (before the closed pilot)

| Plan item | Status | Where |
| --- | --- | --- |
| 1.1 Rotate and remove secrets | Code: production refuses to start with empty or placeholder secrets; gitleaks secret scan runs in CI. **Owner action: rotate the Supershyft DB password and the OpenRouter key that were in the archive, and move secrets to a secret manager** | `app/core/invariants.py`, `.github/workflows/ci.yml` |
| 1.2 Zero data retention | Code: production with `ENABLE_LLM=true` refuses to start unless `OPENROUTER_ZERO_DATA_RETENTION` and `REQUIRE_ZDR_FOR_PERSONAL_HEALTH` are true. The safety classifier uses the same policy. **Owner action: confirm the ZDR routes for each model** | `app/core/invariants.py`, `app/llm/openrouter_policy.py` |
| 1.3 Read only at the database | Code: every session runs with `default_transaction_read_only=on`, a `statement_timeout`, and an idle timeout. A role script grants SELECT on the 15 tables Cura reads. **Owner action: create the role and point `SUPERSHYFT_DATABASE_URL` at it** | `integrations/supershyft/db.py`, `integrations/supershyft/readonly_role.sql` |
| 1.4 Consent and notice | Code: versioned `consent_records` table, `GET/POST /api/v1/consent`, chat refuses with `CONSENT_REQUIRED` until consent is given (enforced outside dev), and an interim prompt in the web app. **Owner action: counsel review under DPDP, processor agreements, and deciding on an India region** | `app/core/consent.py`, `app/api/routes/consent.py`, `frontend/src/lib/api.ts` |
| 2.1 Red flag taxonomy | Draft written. **Owner action: clinician sign-off** | `docs/clinical/red_flag_taxonomy.md` |
| 2.2 Rule layer rewrite | Code: normalization, misspellings, third person wording, negation, six languages and Hinglish. All 16 probe messages are now handled | `app/pipeline/red_flags.py` |
| 2.3 Model backed classifier | Code: `LLMSafetyClassifier` with schema-constrained output and a 3 s timeout. Urgent from either layer wins, and Cura adds a caution if the model fails. It runs before JEV rather than alongside it (a follow-up once the handlers are async) | `app/pipeline/safety_classifier.py` |
| 2.4 Medication intent | Code: start, stop, skip, change, double, combine and "instead of" intents, plus a drug lexicon of generics and Indian brands | `app/pipeline/safety.py` |
| 2.5 Reply text with India numbers | Code: 112 and Tele-MANAS 14416 (configurable), replies in six languages and Hinglish, and call buttons in the web app. **Owner action: native clinician review; Flutter call button** | `app/pipeline/safety_messages.py`, `frontend/src/components/messages/MessageExtras.tsx` |
| 3.1 Launch languages | **Owner action: product decision** | — |
| 3.2 Safety replies in six languages | Code (draft translations) | `app/pipeline/safety_messages.py` |
| 4.6 No evidence policy by risk | Code: high risk topics without reviewed evidence get a redirect to a clinician, and low risk topics are labelled "General information" | `app/pipeline/topic_risk.py`, `app/pipeline/prompt_builder.py` |

## P1 items done early

| Plan item | Status |
| --- | --- |
| 1.5 Trim API meta | Code: production `/chat` responses carry only the public meta (`PUBLIC_META_FIELDS`), with no model, cost, token or routing fields |
| 2.6 Safe mode | Code: once a conversation escalates, later turns are flagged `safe_mode`, start with a caution, and get no package suggestions |
| 5.8 CI | Code: CI runs the safety gate, the backend tests and the secret scan |
| 1.6 Voice under the same policy | Code: OpenRouter voice calls use the model allowlist, data_collection=deny and ZDR, and voice is refused when ZDR is required but not configured |
| 1.7 Retention and deletion | Code: deleting a conversation or document also removes extracted facts, interactions, feedback and jobs, with an audit row. `scripts/purge_expired.py` deletes documents after 90 days and conversations after 365 (`CONVERSATION_RETENTION_DAYS`). **Owner action: schedule it daily** |
| 2.7 Output check | Code: dose, stop, skip and switch instructions in model answers are removed (negated advice is kept), and a failed check returns a safe fallback |
| 3.5 Local digits | Code: Devanagari, Gurmukhi, Gujarati and Bengali digits are normalized before the numeric grounding check |
| 5.3 (part) Model timeout | Code: the default chat model timeout is 30 s instead of 180 s |
| 6.7 (part) Budgets | Code: each member has a daily model token budget (`MEMBER_DAILY_TOKEN_BUDGET`, default 200,000) and gets a clear message when it runs out. The monthly spend alert is still open |

## Still open

These need separate work or owner input: 1.8, 1.9, 2.8, 2.9, 3.3, 3.4, 3.6 to 3.8, all of section 4 except 4.6, sections 5 and 6, and the answers to the open questions in the plan.
