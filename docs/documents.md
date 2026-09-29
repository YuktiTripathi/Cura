# User-uploaded medical documents

Phase 8 enables Cura to extract and retrieve information from user-uploaded PDFs. Phase 9 can **compare** those extracts with SuperShyft structured data when the user asks, without merging sources.

**SuperShyft remains the source of truth for SuperShyft-originated data. User-uploaded documents remain independent sources.**

## Flow

Uploaded PDF → validate → extract selectable text (pypdf) → OCR fallback if text is insufficient → normalize → page-aware chunks → lexical retrieval.

## OCR

`DOCUMENT_OCR_PROVIDER=none` (default) or `local`.

OCR runs only when total extracted characters are below `DOCUMENT_MIN_TEXT_CHARS` **or** most pages are nearly empty. A single short page does not trigger OCR if the rest of the document has usable text.

If OCR is not configured and the PDF is image-only, extraction fails with a truthful message. No fabricated text.

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

## Chunking and retrieval

Chunks keep `source=user_uploaded`, `document_id`, `user_id`, and page range. Retrieval is in-process TF-IDF (no vector database). Queries with explicit `document_ids` search only those documents. Ownership is always `user_id`.

## Chat

With `document_ids` only, Cura retrieves uploaded-document evidence.

With an explicit comparison request, Cura builds a source-separated comparison (uploaded vs SuperShyft). It does not pick a winner, invent dates, or apply SuperShyft reference ranges to an external lab.

General questions such as "What is HbA1c?" stay on the general-knowledge path.

## Provenance

Extracted chunks are never labeled SuperShyft and are never written to SuperShyft PostgreSQL.
