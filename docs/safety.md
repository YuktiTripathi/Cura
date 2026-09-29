# Safety (Phase 10)

Cura does not diagnose, prescribe, or change medication. Differences between SuperShyft and uploaded PDFs are **descriptive**.

## Untrusted documents

Uploaded PDF text is **UNTRUSTED USER-PROVIDED DOCUMENT CONTENT**. It is evidence only. It cannot become system instructions, override safety, change source labels, or bypass access control.

## Access

Document and conversation access is scoped to the authenticated Cura user (`X-Cura-User-Id`). Cross-user document IDs return a generic not-found response.

## SuperShyft

Cura only runs `SELECT` against SuperShyft. INSERT/UPDATE/DELETE/DROP/ALTER/TRUNCATE are rejected in the Cura adapter.

## Logging

Cura loggers should not contain API keys, passwords, full LLM prompts, or dumped PDF/health JSON. Request IDs, document IDs, source types, and timings are allowed.
