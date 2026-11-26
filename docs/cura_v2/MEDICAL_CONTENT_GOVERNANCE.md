# Medical content governance

Medical Knowledge Library V2.3 is the only curated medical source CURA reads. The SuperShyft medical team owns the library and authorises releases outside CURA. CURA does not decide, per entry, whether that writing is clinically approved.

## What was removed

These no longer control whether an explanation is shown:

- `review_status`
- `pending_clinical_review`
- `human_clinically_approved`
- `MEDICAL_REQUIRE_REVIEWED`
- `MEDICAL_CONTENT_PREVIEW`

A library row is used when it exists and is not marked `rejected`. Development, test, and production use that same rule. Entries were not rewritten and were not marked approved. Historical `review_status` values can remain in the JSON as a record.

The library manifest is `backend/app/medical_content/library/manifest.json`. It names the library, version 2.3, the SuperShyft Medical Team, and inventory coverage of 330. The cache key uses a hash of the library files (`library_revision`) instead of a preview or approved label.

## What stayed

Medical references, limitations, relationships, assay checks, emergency handling, numeric grounding, diagnosis and prescription limits, and member isolation stay. Unresolved provider mappings and unconfirmed assays are still not treated as confirmed interpretations. Lifestyle personalisation stays off until questionnaire keys are confirmed. The older article index is still limited to entries that pass the existing servable check. It is not the curated source for screens or chat.

## Tests

`test_medical_content_registry.py` checks that a row without `review_status` is usable and that a confirmed marker still attaches. Current results are under "Tests (27 Nov 2026)" below.

## Limits

Evidence gaps in the library files are unchanged. A missing or ambiguous assay still must not be given an interpretation the library does not support. Release decisions are a SuperShyft medical-team process, not a CURA setting or a per-entry workflow.


## Chat access to library content (revised 27 Nov 2026)

The approval-based chat setting added on 26 Nov 2026 has been removed. Chat now uses the same rule as
every other part of CURA, in development, test and production: any library row that is not `rejected`
is used. There is no `MEDICAL_LIBRARY_CHAT_ACCESS` setting, no approved-only mode, no "pending clinical
review" line in the prompt and no "Awaiting clinical review" notice on screen.

No row was marked approved. `review_status` and `evidence_status` stay in the JSON as a record of how each
entry was checked.

Removing approval did not remove these safeguards:

- Rejected rows are excluded.
- Every personal fact comes from the member's own data.
- Assay notices, grounding, privacy and medical safety rules are unchanged.
- Unsupported high-stakes claims are not sent as established fact. A note that separates a lab range from a
  clinical threshold reaches the model only when `evidence/claim_evidence_map.json` shows a source page
  was read and supports it. Today 12 of 13 such notes meet that bar; the ferritin note does not and is
  withheld.

## Evidence verification

`evidence/claim_evidence_map.json` holds one row per reader-facing claim. A claim is marked
`page_read_supports_claim` only when a source page was opened, read and states it. Candidate sources are
never marked verified without that check. MetSights product information is marked separately and is not
treated as medical evidence. Coverage is reported in `MEDICAL_LIBRARY_2_4_EDUCATION_UPGRADE.md`.

## Retrieval

`chat_passages` ranks library fields by relevance to the question and the member's results, then keeps
them within a token budget. The budget depends on the question type: about 220 tokens for a definition,
up to 620 for food, plus 200 for each extra result involved and 300 for a whole-report question, capped
at 1,600. Entries are never sent whole.

## Tests (27 Nov 2026)

Backend suite: 2,313 passed, 0 failed, 4 skipped. These test files check the assembled model request and
retrieval:

- `test_library_reaches_llm_request.py`: same retrieval in every environment, no approval notice,
  rejected rows excluded, unverified threshold notes withheld, and budget scaling.
- `test_education_reaches_contrasting_profiles.py`: different members get their own values.
