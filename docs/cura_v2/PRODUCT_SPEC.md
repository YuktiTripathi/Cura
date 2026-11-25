# CURA 2.0 product specification

Status: Phase 0. This describes the product to build. It does not change runtime behaviour.

CURA is a personal health companion inside SuperShyft. It helps people with no medical background understand their blood biomarkers, Bio-AI risk predictions, and lifestyle context through interactive screens and short conversations.

The product has two experiences. Health exploration is deterministic. Conversation is the only place a language model writes for the user.

## People and jobs

A member opens CURA after SuperShyft already holds their identity and reports. They want to see what was measured, what was predicted, whether a result sits inside the report range, and what a test is for. They ask follow-up questions from a card or from the composer.

CURA does not diagnose, prescribe, or replace a clinician. It does not invent values, ranges, risk contributors, or diagnoses.

## Experience 1: Health exploration

Five screens, populated only from verified personal data and the curated content registry:

1. **CURA Home.** Entry. Shows whether blood results, Bio-AI risks, and lifestyle context exist. Offers My Health and a way to ask a question. Does not render a model-written health essay.
2. **My Health Overview.** Blood results and Bio-AI risks grouped by the same health categories. Measured and predicted items stay visually and structurally distinct.
3. **Health category.** One category. Lists that member's measured findings and predicted risks for the category, with status labels computed from report flags and reference ranges.
4. **Biomarker detail.** One measured test: purpose (registry), the member's result, unit, reference range, status, and related biomarkers that exist for this member.
5. **Bio-AI risk detail.** One predicted risk: what the prediction is (registry), the member's score and classification from the report, and the distinction from a blood measurement.

Opening a category or a finding is a client navigation over a snapshot already loaded for that member. It does not call a model and does not start a new database query per tap.

Empty and partial states are explicit: no report, marker present without a range, risk present without a classification.

## Experience 2: Conversation

The member types a question or starts from a card. Every card action sends structured context: health category id, biomarker id, or Bio-AI risk id, plus report id when one exists.

The backend loads only the facts required for that question, attaches reviewed registry text for those entities, and calls the medical model with one stable core system prompt. The model explains. It does not supply numbers. Grounding rejects personal numbers that were not in the supplied facts.

Answers stay short, conversational, and tied to this member. Unrelated conditions, markers, and registry articles are not retrieved.

## Boundaries

- A2UI is not used. No agent-generated UI schema drives these screens.
- Screen payloads are application code over provider DTOs and registry JSON.
- Personal numbers come from SuperShyft providers or a user-uploaded document the member selected. They are never hardcoded in production paths.
- Educational sentences that already exist in the content registry are served from that registry. The model is not asked to rewrite them for overview screens.
- Lifestyle and questionnaire answers may personalise a conversation. They are not shown as laboratory results.
- Uploaded PDFs stay a separate source (`user_uploaded`). They are not written back to SuperShyft.
- Hindi, Hinglish, and English UI strings stay in the existing i18n catalogs. Clinical review is still required before treating translations as medically signed off.

## Success for a local build

A developer can run the API and the web app, sign in as a development member, see that member's real SuperShyft-shaped data (mock provider or read-only SuperShyft database), open the five screens without a model call, and ask a question that reaches the configured live model with only the relevant facts.
