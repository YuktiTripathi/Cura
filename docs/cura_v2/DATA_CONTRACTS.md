# Data contracts

Existing types are the starting point. Phase 1 adds a snapshot envelope and a card context. It does not invent a second clinical store.

## Identity

`AuthenticatedPrincipal.subject_id` (`backend/app/auth/models.py`) is the only member key. Request bodies must not carry `user_id` (`backend/app/auth/identity.py`).

Health provider calls pass that subject into `BloodReportProvider`, `BioAIProvider`, `LifestyleProvider`, `QuestionnaireProvider`, and `UserProfileProvider` (`backend/app/providers/interfaces.py`).

## Personal facts (already canonical)

| Contract | Module | Notes |
| --- | --- | --- |
| Blood report and rows | `backend/app/contracts/blood.py` | Value, unit, reference bounds, flag, report id, collected date. Status comes from the report flag or the range, never from a model. |
| Bio-AI report | `backend/app/contracts/bio_ai.py` | Disease or risk code, score, classification, metabolic age and score when present. Same-date reports are not merged (`docs/architecture.md`). |
| Lifestyle | `backend/app/contracts/lifestyle.py` | Preferences or questionnaire-derived diet, sleep, activity. |
| Questionnaire | `backend/app/contracts/questionnaire.py` | Answer instances. Not lab results. |
| Profile | `backend/app/contracts/profile.py` | Display name and demographics the provider actually returns. |

Uploaded document facts stay on `source=user_uploaded` (`backend/app/contracts/uploaded_document.py`). They are not copied into the SuperShyft snapshot.

## Exploration payload (existing, to be snapshotted)

`UnifiedOverview`, `CategoryDetail`, and `Finding` in `backend/app/contracts/unified_health.py`.

Required invariants, already partly enforced by the biomarker package:

- Every numeric field is copied from a provider row.
- `source_type` is `measured` or `predicted_risk`.
- `status` is one of the literals on `FindingStatus`.
- `data_quality` is `verified`, `reference_unavailable`, or `unavailable`.
- `education` is optional and comes from `biomarker_education_v1.json`.
- Category ids match `HealthCategory.id` in `health_categories.py`.

`Finding.id` is the stable key for detail screens (`risk:` prefix is already used for predicted items in `unified_service.py`).

## MemberSnapshot (Phase 1 addition)

A versioned cache object, not a new medical database.

```
MemberSnapshot
  subject_hash          opaque, same scheme as providers/cache.py member_token
  built_at
  source_versions       blood report ids + bio-ai report ids used
  registry_version      health_categories.REGISTRY_VERSION
  overview              UnifiedOverview
  categories            map of category_id → CategoryDetail
  findings              map of finding_id → Finding
```

Built by one provider read (cache-aware). Category and finding GETs slice this object. They do not call SuperShyft again and they do not call a model.

Invalidation: provider cache TTL, report id set change, or `POST /health-explanation/refresh`. Refresh recomputes from providers. It does not ask a model to rewrite the screen.

## CardContext (Phase 1 addition)

Extends `ContextRef` in `backend/app/contracts/context_ref.py`. Today's ref requires marker, risk, or document identifiers and has entry points `blood_report_overview`, `risk_explainer`, `health_area`. It has no health category id.

Target fields the client must send from a card:

| Action | Required |
| --- | --- |
| Ask about a category | `category_id` |
| Ask about a biomarker | `category_id`, `marker_code` or finding id, `report_id` when known |
| Ask about a Bio-AI risk | `category_id`, `risk_code` or finding id |
| Free question | no card fields; server resolves named entities only |

The server re-loads those entities from the snapshot or providers. The client text is not trusted as a value source.

## Conversation facts sent to the model

Keep `HealthContext` (`backend/app/contracts/health_context.py`) as the only personal object in the prompt. Phase 1 narrows what is placed in it:

- Entities named in the question or `CardContext`
- Their registry education or risk-registry blurb
- Lifestyle or questionnaire rows only when the question is about behaviour, sleep, diet, or activity
- No unrelated condition articles from `backend/app/retrieval/content/`

The model output is prose. Numeric claims are checked by `pipeline/numeric_grounding.py` against the fact envelope.

## What must not appear

- Hardcoded personal values in `frontend/src` production components or `backend/app` screen builders
- Model-authored `value`, `unit`, `reference_low`, `reference_high`, `score`, or `classification`
- A second copy of labs inside `DATABASE_URL`
