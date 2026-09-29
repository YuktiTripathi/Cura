# Security

- Mock header auth is development-only (`APP_ENV=development`, `DEV_AUTH_HEADER=true`).
- Production uses `AUTH_PROVIDER=supershyft_jwt`; client-supplied user IDs are ignored.
- Conversation rows are scoped by `AuthenticatedPrincipal.subject_id`.
- Do not log API keys, raw reports, full HealthContext, or full LLM prompts.
- Subject ids in audit logs are hashed.
- Errors return `{error:{code,message,details}}` without stack traces.
- LLM sees a minimal, identifier-reduced serialization of HealthContext only.
- Pre-safety blocks urgent, diagnosis, medication/dosage, prompt-injection, and
  out-of-scope requests before provider/LLM calls where appropriate.
- Post-safety, numeric grounding, and recommendation policy validation run
  independently of the LLM.
- `context_ref` carries identifiers only. The backend re-fetches data and
  enforces ownership.
- Redis rate limits and idempotency keys are principal-scoped and short-lived.
- SuperShyft's connection is SELECT-only, parameterized, pool-limited, and
  separate from Cura persistence.
- Critical escalation uses canonical `critical` status; Cura does not invent
  clinical thresholds.
