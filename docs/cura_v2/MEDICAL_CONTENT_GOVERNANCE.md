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

`test_medical_content_registry.py` checks that a row without `review_status` is usable and that a confirmed marker still attaches. The frontend suite passed, 175 tests, and the production build succeeded. The full backend suite was started after this change. Its finished count is recorded when that run completes.

## Limits

Evidence gaps in the library files are unchanged. A missing or ambiguous assay still must not be given an interpretation the library does not support. Release approval is a medical-team process, not a CURA setting.


## Chat access to library content (revised 26 Nov 2026)

Commit c09cc7d made chat accept only rows that are clinically approved and evidence-verified, to keep draft
text from being used as checked evidence for personal reasoning. No row met that rule, so chat received no
V2.3 content. The prompt then told the model it could answer from general knowledge, which is less safe
than labelled curated content. The rule also checked `approved` and `clinically_approved`, while this document
names the approved state `human_clinically_approved`.

Chat access is now an explicit setting, `MEDICAL_LIBRARY_CHAT_ACCESS`:

| Value | Rows chat may receive | Default in |
|---|---|---|
| `evaluation` | Clinically released rows, plus rows pending clinical review. When a passage comes from a pending row, the prompt labels the passages as general education pending clinical review and tells the model to take every personal fact from the member's own data. | development, test |
| `approved_only` | Only rows whose `review_status` is `human_clinically_approved` (older spellings `clinically_approved` and `approved` are accepted) and whose `evidence_status` is `verified`. | every other environment, including production |

Rejected rows are never used. An unknown value falls back to `approved_only`. No row's review or evidence
metadata is changed by this. A production release that uses pending content needs a decision by the
SuperShyft medical team; until then production receives no unreviewed library text.

`tests/unit/test_library_reaches_llm_request.py` checks the assembled model request itself: in evaluation the
V2.3 passages and their draft label are present, and under approved_only they are absent.
