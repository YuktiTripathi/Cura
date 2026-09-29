# Integration contract (for SuperShyft later)

Cura HTTP API is documented in `contracts/openapi.yaml`.

## Auth (future)

Replace `X-Cura-User-Id` with SuperShyft-issued identity mapped to `AuthenticatedPrincipal`. Never trust a browser-supplied user id as ownership.

## Health

SuperShyft adapters must map existing APIs/services into:

- UserProfile
- BloodReport / BloodMarker
- BioAIReport / BioAIRisk
- LifestyleContext

Cura will not query SuperShyft SQL, recreate Healthians normalization, or recompute Bio-AI scores.

## Chat

`POST /api/v1/chat` is the product surface. Evidence and follow-ups are first-class response fields, not LLM-authored SOURCE lines.
