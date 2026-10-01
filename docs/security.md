# Security

- Mock header auth is development-only (`APP_ENV=development`, `DEV_AUTH_HEADER=true`).
- Production uses `AUTH_PROVIDER=supershyft_jwt`; client-supplied user IDs are ignored.
- Chat identity comes only from `Depends(get_current_user)`. Body fields `user_id`, phone, email, and OTP are dropped.
- See [auth-integration.md](auth-integration.md) for the SuperShyft token → UserId → health-data map.
- Clinical and OpenRouter privacy layers are documented in [cura-safety.md](cura-safety.md).
- Mock auth cannot start with a real SuperShyft health provider.
- Frontend `X-Cura-User-Id` is development-only. Production should call `POST /api/v1/auth/session` so the JWT is stored in an httpOnly `cura_session` cookie. Bearer tokens in `localStorage` remain a known development limitation.
- Conversation rows are scoped by `AuthenticatedPrincipal.subject_id`.
- Do not log API keys, raw reports, full HealthContext, or full LLM prompts.
- Subject ids in audit logs are hashed.
- Errors return `{error:{code,message,details}}` without stack traces.
- LLM sees a minimal, identifier-reduced serialization of HealthContext only.
- Pre-safety blocks urgent, medication/dosage, prompt-injection, and
  out-of-scope requests before provider/LLM calls. Diagnosis questions retrieve
  available HbA1c/Bio-AI facts, then refuse to diagnose.
- `provider.data_collection=deny` is not proof of zero retention. Production
  personal-health LLM should use a confirmed OpenRouter ZDR-capable route
  (`OPENROUTER_ZERO_DATA_RETENTION` plus `REQUIRE_ZDR_FOR_PERSONAL_HEALTH`).
- Post-safety, numeric grounding, and recommendation policy validation run
  independently of the LLM.
- `context_ref` carries identifiers only. The backend re-fetches data and
  enforces ownership.
- Redis rate limits and idempotency keys are principal-scoped and short-lived.
- Audio from the microphone is transcribed server-side and then discarded. CURA does not store recordings by default; only the resulting text follows the normal conversation retention policy.
- Critical escalation uses canonical `critical` status; Cura does not invent
  clinical thresholds.
