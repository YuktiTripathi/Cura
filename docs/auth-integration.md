# SuperShyft identity and CURA health-data access

CURA does not have its own login. SuperShyft authenticates the member (phone and/or email). CURA reads the same access token and uses that server-side identity for every personal-data lookup.

This repository is the CURA service plus read-only SuperShyft adapters. Phone/OTP/email login, token issuance, and refresh stay in the existing SuperShyft app/webapp. CURA only **validates** those tokens.

## 1. Authentication architecture

```
SuperShyft web/mobile
  phone and/or email login (existing SuperShyft auth; not in this repo)
  → SuperShyft issues access JWT + refresh (existing)
  → Authorization: Bearer <access token>
CURA FastAPI
  → get_current_user / get_principal
  → SuperShyftJWTAuthProvider (production)
  → AuthenticatedPrincipal.subject_id == SuperShyft users.user_id
  → HealthDataGateway / RetrievalExecutor(user_id=subject_id)
```

| Concern | Location | Behavior |
| --- | --- | --- |
| Token validation | `backend/app/auth/jwt.py` | HS256 (`AUTH_JWT_ALGORITHM`) with `AUTH_JWT_SECRET`. Requires `exp`. Optional `iss` / `aud`. |
| Subject claim | `AUTH_SUBJECT_CLAIM` (default `sub`), then `user_id` / `userId` | Must be the internal SuperShyft `users.user_id`. Phone/email claims are ignored as identity. |
| Recommended dependency | `get_current_user` (`backend/app/auth/deps.py`) | Alias of `get_principal`. Chat uses this. |
| Development only | `AUTH_PROVIDER=mock` + `MOCK_USER_ID` or `X-Cura-User-Id` | Disabled in production. Header overrides require `ALLOW_MOCK_HEADER_OVERRIDE`. |
| Session cookie | `POST /api/v1/auth/session` | Stores the same Bearer token in httpOnly `cura_session`. |
| Chat body | `{ message, conversation_id? }` | `user_id` / phone / email in the body are dropped and never used. |

Phone and email resolve to one SuperShyft `users` row in the existing product. CURA never re-resolves phone/email; it only accepts the numeric (or string) `user_id` already inside the SuperShyft token.

Refresh tokens are not issued by CURA. The SuperShyft app refreshes, then sends a new access token.

Protected CURA APIs already used `Depends(get_principal)`: chat, conversations, documents, me, voice, feedback, context.

## 2. User → health data relationships (actual)

Authoritative SuperShyft user: `users.user_id`.

```
users.user_id
├── individual_health_report.user_id
│     ├── reports JSON  → nested blood when present
│     ├── reports JSON  → Bio-AI / MetSights (diseases, metabolic_age, metabolic_score)
│     ├── assessment_instance_id
│     └── engagement_id
├── engagement_participants.user_id
│     └── participant_blood_bookings
│           ├── blood_parameters
│           └── blood_report_raw.digital_data
├── assessment_instances.user_id
│     ├── questionnaire_responses → questionnaire_definitions / questionnaire_options
│     └── assessment_packages
├── user_preferences.user_id
│     ├── diet_preference
│     └── allergies
└── (height / weight / BMI / pregnancy / medications)
      not first-class columns in the current read adapters;
      height/weight/BMI and some lifestyle answers arrive via questionnaire keys
      when present. Medical history / meds appear only if those questionnaire
      or preference fields exist.

CURA SQLite (not SuperShyft)
├── conversations.subject_id = authenticated user_id
├── documents.user_id = authenticated user_id
└── user_health_goals.subject_id = authenticated user_id
```

There is no `ReportsService` / `AssessmentService` class in this repo. Reuse:

| Need | Existing adapter |
| --- | --- |
| Profile | `SuperShyftUserProvider.get_profile` → `users` |
| Blood | `IhrRepository` + `participant_blood_bookings` via `SuperShyftBloodProvider` |
| Bio-AI | same IHR rows via `SuperShyftBioAIProvider` |
| Questionnaire | `fetch_questionnaire_instances` (`ai.user_id = :uid`) |
| Lifestyle | `user_preferences` then questionnaire |
| Goals / uploads | CURA `GoalStore` / `DocumentService` scoped by subject |

`HealthDataGateway` wraps those providers. Jev and the LLM never receive a DB session.

## 3. Request / response flow

```
POST /cura/chat   or   POST /api/v1/chat
Authorization: Bearer <SuperShyft access token>
{ "message": "How is my liver?", "conversation_id": "optional" }

1. get_current_user → principal.subject_id
2. ConversationRepository.get_for_subject / create(subject_id)
3. Jev TaskPlan names sources/entities only (no user id)
4. RetrievalExecutor.execute(user_id=principal.subject_id, task_plan=plan)
5. HealthDataGateway + existing IHR/questionnaire/document adapters
6. HealthContext.source_status per source (available / not_available)
7. Medical model receives sanitized HealthContext (no phone/email/JWT/user_id)
8. Response provenance is human-readable dates, not raw PKs
```

If the token is missing or invalid, CURA returns the existing 401/403 authentication error. A missing blood report does not abort Bio-AI or questionnaire retrieval.

## 4. Ownership / IDOR

| Resource | Enforcement |
| --- | --- |
| Conversation | `get_for_subject(id, subject_id)` → 404 if other user's |
| Document | `DocumentService.get_owned` / `assert_owned` |
| IHR / bookings / questionnaire | SQL `WHERE user_id = :uid` plus row-level uid check |
| `plan.report_id` | Dropped unless it belongs to the authenticated user |
| Client `user_id` | Stripped from `ChatRequest` |

Caches (`individual_health_report`, blood bookings) are keyed by authenticated `user_id` with a 2s TTL. Auth tokens are never stored in health-context objects.

## 5. Frontend / mobile

SuperShyft apps already send `Authorization: Bearer <access token>` to protected APIs. CURA uses the same header.

**Do not send `user_id` in the chat body.**  
**Do not send `X-Cura-User-Id` in production.**

Optional: `POST /api/v1/auth/session` after login so the token can live in `cura_session`.

Local CURA UI may still use `VITE_CURA_USER_ID` → `X-Cura-User-Id` in development only.

## 6. Observability

Development (`APP_ENV=development`) logs `AUTH`, `PLAN`, `RETRIEVAL`, `CONTEXT`, and `MODEL PAYLOAD` field names via `cura.trace`. Production does not emit those traces. Audit lines record hashed user id, conversation id, requested sources, record counts, model tier, and success — never JWTs, phones, emails, or full health records.
