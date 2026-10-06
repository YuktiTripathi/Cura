# Red flag taxonomy (DRAFT, needs clinician sign-off)

Source of truth for the deterministic safety gate in `backend/app/pipeline/red_flags.py`.
Engineering drafted this so the code has something to run against. Nothing here counts as
clinically approved until the named clinical safety owner signs it off.

## Urgency levels

| Level | Meaning | What Cura does |
| --- | --- | --- |
| now | Call emergency services | Blocks the turn, replies in the member's language with 112 (and Tele-MANAS 14416 for self harm), shows call buttons, and keeps the conversation in safe mode |
| soon | See a doctor within a day | Answers, but puts a caution first and turns off package suggestions |

## Categories ("now" unless stated)

| Id | Covers |
| --- | --- |
| chest_pain | chest pain, pressure, tightness or heaviness; spread to the arm; sweating; Hinglish and Indic wording |
| stroke_signs | face droop, slurred speech, weakness on one side, sudden confusion or vision loss |
| breathing | breathing difficulty, gasping, blue lips (not negatable) |
| consciousness | unconscious, collapsed, not waking up or not responding, fainted |
| seizure | seizure or convulsion |
| heavy_bleeding | heavy bleeding, bleeding in pregnancy, vomiting blood, black or tarry stools |
| anaphylaxis | severe allergic reaction, swelling of the throat or tongue |
| poisoning_overdose | overdose, poisoning, too many tablets, a whole strip |
| glucose_extreme | sugar of 400 or more, or under 60, or high or low sugar with symptoms |
| infant_red_flags | a baby or infant with fever, lethargy, not responding or not feeding |
| self_harm | direct and indirect suicidal wording, self harm (not negatable) |
| see_doctor_soon (soon) | fever for 3 days or more, blood in urine or stool, persistent vomiting, BP of 180/xx or higher, jaundice |

## How matching works

1. The text is normalized: NFKC, lowercase, zero-width marks removed, common misspellings fixed.
2. Each category's patterns run against the normalized text.
3. A hit is ignored if a negation cue comes just before it ("no chest pain") or just after it ("dard nahi"). The breathing and self harm categories ignore negation, because their own wording often contains a negative.
4. The model classifier (`LLMSafetyClassifier`) runs on every turn when `ENABLE_LLM=true`. If either the rules or the model call it urgent, the turn is escalated. If the model times out, the rules still apply, and Cura adds a caution when the message mentions symptoms.

## Open items for the clinical owner

- Confirm or change every category and threshold above, especially the glucose cut-offs.
- Confirm 112 and Tele-MANAS 14416 (`EMERGENCY_NUMBER`, `CRISIS_HELPLINE_NUMBER`).
- Have native speakers review the reply text in `backend/app/pipeline/safety_messages.py` (hi, mr, pa, gu, bn, Hinglish).
- Replace the seed set in `backend/tests/fixtures/safety_red_flag_set.jsonl` with the 600 to 1,000 message set, labelled by two clinicians. CI runs it on every change (`tests/safety`).
- Review the drug lexicon (`DRUG_LEXICON` in `safety.py`).
