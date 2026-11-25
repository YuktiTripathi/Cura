# Phase 2B — medical knowledge integration

The library in `backend/app/medical_content/library` is revision 2.3, copied from the supplied package. Explanations were not regenerated. Entries may still say `pending_clinical_review`. That text is historical. CURA no longer uses it to hide content. See `MEDICAL_CONTENT_GOVERNANCE.md`.

## Files

Created:

- `backend/app/medical_content/library/` — the supplied library
- `backend/app/medical_content/registry.py` — one-time load
- `backend/app/medical_content/mapping.py` — exact canonical matches
- `backend/app/medical_content/attach.py` — finding notes and short chat passages
- `backend/tests/unit/test_medical_content_registry.py`

Modified:

- `backend/app/core/config.py` — `medical_content_preview`
- `backend/app/snapshot/assemble.py` — attach a note when preview is on and the id matches
- `backend/app/pipeline/service.py` — add at most two matched passages after the existing knowledge lookup

## Registry

`load_registry()` reads the JSON files once and caches them. It exposes biomarkers, allergens, shared modules, Bio-AI conditions, categories, relationships, the questionnaire registry, lifestyle relationships, and the unresolved inventory. `invalidate()` clears the cache when the files change.

## Mappings

Exact match means `biomarker_id` is already a canonical id or a key-bridge target in `biomarker_registry_v1`. No fuzzy match.

| status | count |
|---|---|
| exact canonical match | 114 |
| unresolved | 216 |

Workbook keys such as `WB-070` stay unresolved. `production_canonical_id` in the supplied report is null for those rows. The missing information is an authoritative assay id in the biomarker registry, not a closer label.

## Questionnaire

`lifestyle/questionnaire_registry.json` has 91 questions. `question_key` was not exported. The numeric `question_id` values are staging ids. Option values stay opaque strings. Personalised lifestyle interpretations are not activated.

Q7-29, Q8-30, and Q9-31 are not resolved. The lifestyle relationship files disagree on those staging ids, and there is no production question key to choose between them.

## Health view

`assemble_snapshot` still builds the overview without an LLM call. When preview is on, a measured finding with no education note and an exact canonical id gets `EducationNote` from the matching entry. The note uses only the explanation for that result state. Unmatched assays keep the laboratory value and get no interpretation.

## Chat retrieval

After the existing medical lookup, at most two short descriptions are appended for requested markers that have an exact match. The full library and the full member snapshot are not added to the prompt.

## Preview and production

`medical_content_preview` defaults to on only when `APP_ENV` is `development` or `dev`. Tests and production stay off unless the flag is set. Production does not serve this library, because no entry is `approved`. Existing education, or no education, remains the production path.

## Tests

`tests/unit/test_medical_content_registry.py`: 3 passed. Load count, exact versus unresolved mapping, and preview on/off.

The full backend and frontend suites were not re-run for this change. The last full backend run in this workspace was not green.

## Limits

- 216 inventory rows still have no confirmed canonical id.
- Allergen entries are loaded but not mapped onto report rows.
- Questionnaire and lifestyle personalisation stay off.
- Within-range lines that repeat the same sentence were not rewritten.
- The library is not clinically approved in its own metadata.

## Run locally

From `backend`, with `APP_ENV=development`:

```bash
PYTHONPATH=.. .venv/bin/python -m pytest tests/unit/test_medical_content_registry.py -q
```

Set `MEDICAL_CONTENT_PREVIEW=true` to force the preview on, or `false` to force it off.
