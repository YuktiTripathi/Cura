# User-uploaded medical documents

Cura can extract facts from a user-uploaded PDF (typically up to 50 pages) and answer questions about it. SuperShyft blood reports remain a separate source. Uploaded values are never written into SuperShyft.

**Do not use a vector database.** Retrieval is structured facts plus a stored document tree (PageIndex-style section navigation).

## Flow

```text
PDF upload
  → validate
  → text/layout extraction (OCR only if needed)
  → structured health-fact extraction   ← first questions allowed here
  → PageIndex tree (async, same job after facts are stored)
  → CURA answers
```

States (internal): `UPLOADED` → `PARSING` → `STRUCTURED_FACTS_READY` / `PAGEINDEX_BUILDING` → `READY` (or `PARTIAL_FAILURE` / `FAILED`).

The UI may say “Measurements ready” while narrative indexing finishes. It does not mention PageIndex.

## Query policy

| Question | Path |
| --- | --- |
| “What is my Vitamin D / LDL / HbA1c?” | Deterministic `DocumentHealthFacts` lookup |
| High / low / abnormal lists | Structured lookup |
| “What did the radiologist say?” | PageIndex section retrieval, then explanation |
| Mixed | Structured + PageIndex |
| “Explain this whole report” | Structured summary (not a dump of every value) |
| “View all extracted results” | Progressive list of extracted measurements |
| Compare with SuperShyft | Normalize entities, compare values in app code, then reason |

PageIndex is not invoked for obvious lab lookups unless structured extraction missed the value.

## Provenance

User-facing source style: `Uploaded report · page 17` or `Uploaded report · Impression · page 8`.

Report wording stays report wording. Cura interpretation is labeled separately.

Task-plan operations: `DOCUMENT_STRUCTURED_LOOKUP`, `DOCUMENT_NARRATIVE_RETRIEVAL`, `DOCUMENT_SUMMARY`, `DOCUMENT_CROSS_SOURCE_COMPARE`.

## Configuration

```
DOCUMENT_STORAGE_BACKEND=local
DOCUMENT_STORAGE_PATH=./data/uploads
DOCUMENT_MAX_UPLOAD_BYTES=20000000
DOCUMENT_OCR_PROVIDER=none
DOCUMENT_MIN_TEXT_CHARS=80
DOCUMENT_SPARSE_PAGE_CHARS=40
DOCUMENT_MAX_PAGES=50
DOCUMENT_MAX_OCR_PAGES=20
DOCUMENT_MAX_EXTRACTED_CHARS=200000
DOCUMENT_OCR_TIMEOUT_SECONDS=60
DOCUMENT_CHUNK_SIZE=900
DOCUMENT_CHUNK_OVERLAP=100
DOCUMENT_RETRIEVE_LIMIT=5
```

Chunks remain a lexical fallback only. Ownership is always `user_id`.
