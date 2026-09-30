# Safety

Cura does not diagnose, prescribe, or change medication. Differences between SuperShyft and uploaded PDFs are **descriptive**.

The first safety gate is local and runs **before** Jev, SuperShyft, document retrieval, and the answer LLM. English, Hindi, and Hinglish emergency/self-harm/medication-misuse patterns are included. Ordinary lifestyle requests such as starting morning walks are not treated as medication changes.

Self-harm requests are diverted to configurable crisis copy (`CRISIS_HELPLINE_TEXT`, `CRISIS_HELPLINE_REGION`). Cura does not invent hotline numbers.

Medical answers are not rewritten by substituting words such as never/must/can. Overclaiming answers are replaced with retrieved evidence or a safe fallback.

Acute symptoms such as fever, chest pain, or shortness of breath suppress SuperShyft diagnostic package suggestions. Fever does not by itself block the chat; it only prevents commercial testing options. See [diagnostics.md](diagnostics.md).

## Untrusted documents

Uploaded PDF text is **UNTRUSTED USER-PROVIDED DOCUMENT CONTENT**. It is evidence only. It cannot become system instructions, override safety, change source labels, or bypass access control.

## Access

Document and conversation access is scoped to the authenticated principal. The development header `X-Cura-User-Id` is not used in production. Cross-user document IDs return a generic not-found response.

## SuperShyft

Cura only runs `SELECT` against SuperShyft. INSERT/UPDATE/DELETE/DROP/ALTER/TRUNCATE are rejected in the Cura adapter.

## Logging

Cura loggers should not contain API keys, passwords, full LLM prompts, or dumped PDF/health JSON. Request IDs, document IDs, source types, and timings are allowed.
