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
| 1.8 Asymmetric tokens | Code: with `AUTH_JWKS_URL` set, Cura verifies RS256 tokens against Supershyft's public keys, requires `exp`, `iss` and `aud`, and rejects HS256. **Owner action: Supershyft publishes a JWKS endpoint; httpOnly cookie on the web, Keychain/Keystore on Flutter** |
| 5.1 Containerize | Code: `Dockerfile` with several workers and no reload, running as non-root, with a health check. CI builds the image. **Owner action: ECS/Fargate service and autoscaling** |
| 5.3 Waiting model | Code: the model timeout is 30 s instead of 180 s, the thread pool is sized explicitly, and a full process returns 429 with `Retry-After`. Converting the handlers to async is still open |
| 5.6 Observability | Code: Prometheus `/metrics` with per-stage latency, outcomes, fallbacks, safety flags, tokens and cost; alerts are listed in `docs/operations.md` |
| 5.7 Load test | Code: k6 script `scripts/load/chat_mix.js` with the plan's targets as thresholds. **Owner action: run it on staging** |
| 5.8 Release hygiene | Code: `requirements.lock`, and CI installs from the lock file and builds the image |
| 3.3 Pivot translation | Code: the answer is written and checked in English, then translated by the fast tier. The translation is used only if every number matches; otherwise the member gets the checked English answer. Enabled languages come from `ANSWER_LANGUAGES` (default en, hi, Hinglish). **Owner action: confirm the launch languages; native clinicians review samples** |
| 4.3 Attributed passages | Code: entries carry `content_kind`, reviewer, review and expiry dates, licence and region. Cura summaries are labelled "Cura summary, not a quotation", and reviewed content files go in `app/retrieval/content/` |
| 4.4 Clinical review | Code: outside development, only reviewed or published entries that are in date (at most 12 months after review) are served. **Note: none of the 17 existing entries is reviewed, so production has no general medical evidence until content is added, and high-risk topics are redirected to a clinician** |
| 5.2 State out of process | Code: an S3 document store (KMS-encrypted, hashed keys, ap-south-1 by default). Production refuses to start with local storage, SQLite or without Redis. Alembic migrations, including the new `0002_consent_records`, were run on Postgres 16, and the full test suite passes against Postgres; CI now runs both. Separate extraction workers are still open |
| 6.6 Reasoning tokens | Code: `LLM_REASONING_EFFORT` and `LLM_REASONING_OUTPUT_CAP` |
| 6 lever 3 Prompt caching | Code: stable text and member data come first and the question last. **Owner action: confirm cache hits in the provider usage report** |
| 6.7 (part) Budgets | Code: each member has a daily model token budget (`MEMBER_DAILY_TOKEN_BUDGET`, default 200,000) and gets a clear message when it runs out. The monthly spend alert is still open |

## Still open

These need separate work or owner input: 1.8, 1.9, 2.8, 2.9, 3.4, 3.6 to 3.8, 4.1, 4.2, 4.5, 4.7, 4.8, sections 5 and 6, and the answers to the open questions in the plan.
