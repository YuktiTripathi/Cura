# Handover

## Current implementation

Cura now includes mock and SuperShyft read-only providers, canonical
HealthContext, deterministic Health Scenario and trend engines, recommendation
policy validation, contextual Ask Cura, pre/post safety, numeric grounding,
SSE chat, JWT auth support, Redis rate/idempotency controls, PostgreSQL
migrations, golden evaluations, and a capability-aware UI.

## Intentionally deferred / deployment-specific

- Replace the temporary read-only SQL bridge with SuperShyft's canonical
  resolver/API when its contract is available.
- Configure production issuer/audience/secret or replace the JWT validator with
  SuperShyft's JWKS/OIDC adapter.
- Provider-native token streaming (`/chat/stream` returns status then the completed, validated answer).
- Clinical validation and governance; software safety tests are not clinical certification.
- Production infrastructure provisioning for PostgreSQL, Redis, object storage,
  monitoring, backups, and retention.

## Demo data

`demo-user-001` has blood reports `blood-001` (2026-07-09) and `blood-002` (2026-08-18), plus two Bio-AI reports on 2026-07-09 (`bioai-a`, `bioai-b`) with different cardiac scores (30 vs 48) to force disambiguation.

Synthetic eval user `eval-user-iron` has two blood reports with low haemoglobin/MCV/MCH/iron, normal lipids, and unchanged HbA1c 5.3%. It is for assistant-quality tests and missing-iron catalog matching.

Diagnostic catalog matching reads SuperShyft `diagnostic_package` / `diagnostic_test_groups` (mock seed JSON in development). See [diagnostics.md](diagnostics.md).
