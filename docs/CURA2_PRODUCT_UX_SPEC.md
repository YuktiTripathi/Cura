# CURA 2.0 Product and UX Specification

Purpose: help a person with no medical background understand their health information correctly, without being overwhelmed or misled. The aim is not a prettier chatbot.

## How to read this document

Every section and example carries one of these tags. If nothing is tagged, treat it as Proposed.

- [Implemented and tested] Exists in the code and has an automated test. It has not been clinically reviewed or tested with real users unless a tag says so.
- [Proposed] Designed here, not built.
- [Unreviewed] Wording or rules that contain clinical content. None of it has had clinical review. All of it needs sign off before release.
- [Open decision] A product or clinical choice nobody has made yet.
- [Release blocking] Must be fixed or decided before this can be released.

Evidence status: there is no clinical validation and no usability testing behind any of this. The synthetic people and answers are written by the authors. The example answers are target wording, not captured model output. Automated tests run with the chat model switched off, so they cover the deterministic behaviour only.

## The synthetic person used in all examples

Meena, 55, no medical background, uses a phone.

Blood report of 21 Aug 2026, nine markers. Six are outside the report's reference range. Three are inside.

| Marker | Result | Report range | Status |
|---|---|---|---|
| HbA1c | 5.9 % | up to 5.7 | A little above |
| Fasting glucose | 104 mg/dL | 70 to 99 | A little above |
| LDL cholesterol | 142 mg/dL | under 100 | Above |
| HDL cholesterol | 38 mg/dL | 50 or more | Below |
| Triglycerides | 168 mg/dL | under 150 | A little above |
| Vitamin D | 12.6 ng/mL | 30 to 100 | Well below |
| Haemoglobin | 12.8 g/dL | 12 to 15 | In range |
| TSH | 2.1 mIU/L | 0.4 to 4.0 | In range |
| Creatinine | 0.8 mg/dL | 0.6 to 1.1 | In range |

Bio-AI report of 25 Aug 2026, using the report labels from the Bio-AI knowledge base: type 2 diabetes 72 out of 100 (High Risk), cardiac health 48 (Increased Risk), fatty liver 12 (Healthy). The scores are made up.

Counts that must always be stated correctly
- Markers: 9 measured, 6 outside range, 3 inside range.
- Health areas holding the six outside markers: 3 (blood sugar has 2, heart and circulation has 3, vitamins has 1).
- Bio-AI estimates: 3 assessed, 2 raised (High Risk and Increased Risk), 1 Healthy.
- Never present a count of markers as a count of areas, or the reverse.

Built in on purpose: the Bio-AI diabetes category is high while the blood sugar tests are only a little above range; the fatty liver estimate is low but there is no liver blood test to compare it with; two reports are four days apart.

[Implemented and tested] The count rules above are checked in `tests/acceptance/test_product_acceptance.py` against this same report.

---

## 1. Complete user journey

### 1.1 Opening the app (first visit, reports available) [Implemented and tested in part]
Welcome copy that names only what exists, and a "Welcome back" line on a returning device, are built and tested. The single big button and question chips below are the target layout [Proposed].

```
Hello Meena

I can help you understand your blood report and your Bio-AI report in plain language.
You can also ask any general health question.

[ See my health at a glance ]        <- one big button

Or ask me anything about your health
[ Type your question...        ] [mic]

Questions people often ask
  Why is my vitamin D low?
  What do my cholesterol results mean?
  What can I eat for better blood sugar?
```

Rules: one primary action. Suggestions appear only because the data exists. First name only.

### 1.2 Returning visit [Proposed beyond the greeting]
"Welcome back" is built. A "Continue where you left off" link is not.

### 1.3 Health at a glance [Implemented and tested in part, wording Unreviewed]
The overview screen exists. What it must say for Meena:

```
Your health at a glance

Blood tests (21 Aug 2026): 6 of your 9 are outside the report's range.
They sit in 3 areas: blood sugar, heart and circulation, and vitamins.
Bio-AI estimates (25 Aug 2026): 2 of 3 are raised.

Areas to look at                      (shown in a fixed order, not ranked)
  Heart and circulation     Needs closer attention   >
  Blood sugar               Needs closer attention   >
  Vitamins and minerals     Worth attention          >

Everything else
  Thyroid                   Looking good             >
  Kidney                    Looking good             >
  Blood                     Looking good             >
  Liver                     Looking good (risk estimate only, no liver blood test)   >
```

Rules
- The heading says "Areas to look at", never "Most important". See section 6 on prioritization.
- Both report dates are shown and labelled. They are separate reports, not one moment in time.
- "Needs closer attention" appears only for the reasons listed in section 6, and the area screen says which reason applied.
- No overall score.

### 1.4 An area (for example Blood sugar) [Implemented and tested in part]
Order, nothing repeated:
1. One sentence on what this area shows, written from the data.
2. What was measured, with value, unit, report range, plain label and date.
3. What the Bio-AI estimate adds, labelled as a prediction, with its date.
4. How the two relate (section 7), only when both exist.
5. What the person can reasonably do, with items needing professional review flagged (section 5).
6. Up to four follow up questions that are relevant and different from what is on the page.

### 1.5 Asking a question [Implemented and tested in part]
"Looking at your results..." appears while waiting, with no internal steps. The error and retry behaviour (calm message, Try again, draft kept) is built and tested.

### 1.6 Knowing what to do next [Proposed]
Every personal answer ends with something the person can reasonably do, or says plainly that no action is needed for what was asked. A doctor is mentioned only with a reason. Today's fallback answers still contain generic lines (see section 10, release blocking).

### Reading and click budget
Aims, not measurements: an answer about a person's own results in at most two taps from opening the app; no finding stated twice on one screen. Answer length follows the question (section 3).

---

## 2. Plain status labels for a measured value [Implemented and tested for the health overview, answer cards not yet]

Labels describe distance from the report's own range. They do not say how serious a result is.

- Within range
- A little above range / A little below range (within 10 percent of the limit)
- Above range / Below range (10 to 50 percent past the limit)
- Well above range / Well below range (more than 50 percent past the limit)
- Critical (unchanged; "Needs medical attention soon" is proposed wording that needs clinical review [Unreviewed])

Never red for a minor deviation. Status is never colour alone.

The 10 and 50 percent cut offs are an existing engineering choice, not a clinical standard [Unreviewed].

---

## 3. Response patterns with realistic examples

All examples are target wording for the synthetic Meena [Proposed, Unreviewed]. Anything under "What you can do" that is a clinical recommendation is marked with (review) and must be approved by a clinician before release.

Length rule [Proposed]: length follows the question. A short question gets a short answer. A complex question gets enough explanation to be understood. There is no word limit. Progressive disclosure is allowed for background and detail. It is never used to hide something medically important: any result outside range, any urgent flag, any missing test that matters, and the next step are always visible without opening anything.

### 3.1 General health question
Question: "What is HbA1c?"
```
HbA1c shows your average blood sugar over the last 2 to 3 months.

Doctors use it, along with other tests, to check for diabetes and to see how
blood sugar is being controlled.

[ Show my HbA1c ]
```

### 3.2 Single biomarker, personal: vitamin D
Question: "Why is my vitamin D low?"
```
Your vitamin D is 12.6 ng/mL. Your report's range is 30 to 100.     [ Well below range ]
From your blood report of 21 Aug 2026.

Vitamin D helps your body use calcium, so low levels can affect bones and muscles over time.

Common reasons include little sun exposure or low intake. Your report cannot tell
which applies to you.

What you can do
 - Talk to your doctor about whether you need treatment. (review)
 - Your doctor may suggest repeating the test after some time. (review)
```
The shape is adaptive. A simpler question, "What is my vitamin D?", gets two sentences with the value, range, label and date.

### 3.3 Fasting glucose read together with HbA1c
Question: "Is my fasting sugar ok?"
A fasting glucose is never explained alone when HbA1c exists. [Implemented and tested in the deterministic path: the answer lists both.]
```
Your fasting blood sugar is 104 mg/dL. Your report's range is 70 to 99.   [ A little above range ]
Your HbA1c is 5.9 %. Your report's range is up to 5.7.                    [ A little above range ]
Both from your blood report of 21 Aug 2026.

What this means
Both results are above the lab's range, and both point the same way. Guidelines
use separate cut offs from the lab range: fasting glucose of 100 to 125 mg/dL and
HbA1c of 5.7 to 6.4 % are both called the prediabetes range. (review)
This is not a diagnosis. A doctor decides what these results mean for you,
and usually looks at repeat tests.

What you can do
 - Ask your doctor whether to repeat these tests. (review)
```
This example replaces the earlier draft, which read fasting glucose on its own and said "nothing urgent".

Distinguish two kinds of cut off in every answer [Proposed]: the lab reference range printed on the person's report, and guideline thresholds used by doctors (for example prediabetes or diabetes ranges). The first says "outside this lab's range". The second says "in a range doctors use for a condition", never "you have it".

### 3.4 Complete blood report summary (correct counts)
Question: "Explain my blood report"
```
6 of your 9 blood tests are outside the report's range. 3 are inside.
(Blood report of 21 Aug 2026)

Results outside range, by area
 Blood sugar:   HbA1c 5.9 % (a little above), fasting glucose 104 mg/dL (a little above)
 Heart:         LDL 142 mg/dL (above), HDL 38 mg/dL (below), triglycerides 168 mg/dL (a little above)
 Vitamins:      Vitamin D 12.6 ng/mL (well below)

Inside range
 Haemoglobin, thyroid (TSH) and kidney (creatinine).

Not in this report
 No liver tests were included.

How these fit together
 Your blood sugar results are read together, and your cholesterol results are read together.
 Ask about an area to see what it means.

What you can do
 - Go through the three areas with your doctor. (review)
```
Rules: nothing here is ranked, because the findings are grouped by area (section 6). The six outside markers sit in three areas, and the summary says so without mixing the two counts.

### 3.5 Bio-AI risk prediction [score transparency retained]
Question: "What does my diabetes risk mean?"
```
Your Bio-AI report places your type 2 diabetes risk at 72 out of 100, which is High Risk.   [ High Risk ]
Bio-AI report of 25 Aug 2026. This is a prediction, not a diagnosis.

[ View the score and how to read it ]    <- expands:
    Score: 72
    Score: 72 out of 100
    Category in your report: High Risk
    Scale: 0 to 25 Healthy, 26 to 50 Increased Risk, 51 to 75 High Risk, 76 to 100 Very High Risk.
           If your report uses different labels, your report's labels apply.
    What to keep in mind: a model estimate, not a diagnosis; not a percentage chance of having
           the condition; a low score does not rule the condition out; scores for different
           conditions should not be compared as if the gap meant the same thing.

What you can do
 - Your blood sugar tests are the measured part. Yours are a little above range;
   see the blood sugar area. (review)
```
Rules
- The official category is the headline. The raw score is always inspectable, never hidden by default policy.
- The scale and limits come from the Bio-AI knowledge base `cura.kb.bio_ai.explainer` version 1.0 (18 Nov 2026), section 3. The bands are those of the sample MetSights report. The knowledge base says the person's own report and the approved production configuration take priority, so production thresholds and labels must be confirmed. [Implemented and tested for the display; production confirmation is an Open decision]
- A score is never turned into a probability or a percent unless the model explicitly supports that reading.
- The inputs that fed a prediction are named only if the report itself lists them. They are never guessed.

### 3.6 Unified Blood plus Bio-AI, one area
Question tapped from Blood sugar: "What is going on with my blood sugar?"
```
Blood sugar: needs closer attention
Reason: a blood result is outside range and the Bio-AI estimate is raised for the same area.

Measured (blood report, 21 Aug 2026)
 HbA1c            5.9 %      Report range up to 5.7      A little above range
 Fasting glucose  104 mg/dL  Report range 70 to 99       A little above range

Predicted (Bio-AI report, 25 Aug 2026)
 Type 2 diabetes risk       High Risk (72 out of 100)       [ View score ]

How they relate
 Both point toward higher blood sugar, but they are different kinds of information.
 The blood tests are measurements from one day. The Bio-AI result is a prediction made
 separately, four days later. Neither shows that the other caused it, and a High
 category does not mean you have diabetes.

What you can do
 - Ask your doctor whether to repeat HbA1c and fasting glucose. (review)
```
Rules
- "Measured" and "Predicted" headings, each with its own source and date, are always shown.
- Two reports from different dates are never described as the same moment.
- "How they relate" says whether the two agree or differ and never states a cause.

Conflict example: cholesterol is outside range while the Bio-AI cardiac health score is 48, Increased Risk. "Your cholesterol tests are outside range. Your Bio-AI cardiac health score is 48 out of 100, Increased Risk. These are different kinds of information and do not cancel each other."

### 3.7 Nutrition and lifestyle [Proposed, Unreviewed]
Question: "What can I eat for better blood sugar?" Foods first, in everyday words, then one clause linking to her data. No list of lab values. All dietary advice here needs review.

### 3.8 Multi turn follow ups [Implemented and tested in part]
Tested: a follow up such as "Why is it low?" keeps the vitamin D value, unit, date and source. A question about the previous answer is never wrapped in a template ("What does is it serious mean?" is fixed and tested). Not yet fixed: after several turns the personal suggestions run out and generic ones appear (section 10).

---

## 4. Connected evidence principle [Proposed except where tagged]

No single result is interpreted alone when related results exist. Each group lists what is read together. None of the group rules below has been clinically reviewed.

| Group | Read together | Status |
|---|---|---|
| Metabolic | HbA1c, fasting glucose, triglycerides, HDL, Bio-AI diabetes category | Glucose with HbA1c in the same answer: [Implemented and tested]. The rest: [Proposed] |
| Heart | LDL, HDL, triglycerides (and total or non HDL cholesterol when present), Bio-AI heart category | [Proposed] |
| Liver | ALT, AST, GGT, ALP, bilirubin, albumin. A normal enzyme does not prove a healthy liver | [Proposed] |
| Kidney | Creatinine with eGFR, urea, urine protein. One creatinine is not a kidney verdict | [Proposed] |
| Iron | Haemoglobin, MCV, MCH, ferritin, TIBC, serum iron read as one pattern, no diagnosis | [Implemented and tested in the deterministic path] |

Rules for all groups
- State the pattern with uncertainty ("often seen when", "a doctor can confirm"), never "you have".
- Say what is missing when the group is incomplete.
- Distinguish lab reference ranges from guideline or diagnostic thresholds in the wording.
- Anything that suggests treatment or testing is marked for professional review.

---

## 5. Recommendations needing professional review [Proposed]

Every clinical recommendation shown to a person must be one of: (a) in a reviewed content file, or (b) generated by the model within rules and marked as needing review in the content register. The register of items needing sign off starts here and must be completed by a clinician before release.

(review) items in this document: referral and repeat testing wording in 3.2, 3.3, 3.4, 3.5, 3.6; the prediabetes ranges in 3.3; any supplement, diet or exercise advice; the status rules in section 6; the 10 and 50 percent label cut offs in section 2; the Critical label wording.

---

## 6. Clinical prioritization [Implemented and tested, Unreviewed, Release blocking until reviewed]

Principle: findings are never ranked by how far they sit outside the laboratory range. Distance is shown in the label for information only.

What the code now does (`app/biomarkers/unified_overview.py`, `app/pipeline/unified_wording.py`)
1. An area is "Needs closer attention" only if one of these is true:
   - a result carries a critical flag from the report;
   - a guideline urgent threshold applies (`app/pipeline/clinical_thresholds.py`, for example HbA1c 6.5 % or higher, fasting glucose 126 mg/dL or higher, triglycerides 500 or higher, LDL 190 or higher);
   - a Bio-AI category the report calls high or worse;
   - a blood result outside range together with a raised Bio-AI estimate in the same area.
2. Otherwise an area with any outside range result or raised estimate is "Worth attention". Otherwise "Looking good" or "Not yet assessed".
3. Areas listed under "Areas to look at" are ordered by status tier first, then by a fixed registry order. That order is stable and not a ranking, and the screen says so.
4. The model cannot add, remove or reorder priorities. It may only reword their text.
5. If no reviewed justification exists to order two findings, they are shown together in a fixed order with no ranking language.

Open issues
- The rule list above is engineering's draft. A clinician must review and own it. [Release blocking]
- "Increased Risk" (the second band) plus any blood result outside range currently counts as the closer attention tier. Whether that band should do that is an [Open decision].
- Guideline thresholds cover only five markers today.
- The "Areas to look at" heading and "not ranked" note are [Proposed]; the screen still says "priorities" in places.

---

## 7. Blood plus Bio-AI combined experience

Principles [Proposed, partly Implemented]
1. One area, one story. The Bio-AI estimate and blood tests for the same area appear together. [Implemented for the overview and area screens.]
2. Always label the type: "Measured" for blood tests, "Predicted" for Bio-AI. [Implemented in the data model; UI wording as above.]
3. Show the official category prominently. The raw score is inspectable with its documented scale and limits (section 3.5). No percent, no probability. [Implemented and tested: the category is the row's label, and "View the score" shows the score, the report's category, the documented scale and the limits.]
4. Never state a cause between a measured result and a prediction.
5. Show the source and date of every measured and predicted item. Do not imply two reports describe the same moment. [Implemented and tested on each finding row in the area screen: "Measured, blood report 21 Aug 2026" and "Predicted, Bio-AI report 25 Aug 2026". Separate Measured and Predicted headings are not built.]
6. The registry descriptions no longer use "chances", which could read as a probability. The new wording needs review. [Implemented, Unreviewed]

Scenario wording [Unreviewed]
- Both reassuring: "Your results and your risk estimate both look good for this area."
- Blood outside range, estimate not raised: "Your blood test is outside range. The estimate is not raised, which does not cancel the test."
- Blood in range, estimate raised: "Your blood tests are in range. The estimate still flags this area."
- Both raised: "Both your blood test and the estimate flag this area."
- Only one source: say which one exists.
- Incomplete: name the missing test once.

---

## 8. Follow up conversation behaviour

- At most four follow ups. [Implemented: the cap is four.] They must be relevant, different from each other and from what was already asked or shown. [Partly implemented. Defect: after several turns the personal ones run out and generic ones appear. Release blocking.]
- Never a template that wraps the person's own words. [Implemented and tested.]
- The last topic stays in focus so "Is it serious?" resolves to it. [Tested for the vitamin D case.]
- "Explain more simply" rewrites the last answer shorter with no new facts. [Needs the live model; not verifiable offline.]
- A vague question gets one short clarifying question.
- Repeating results across reports: say a result was also outside range earlier, and say worse or better only if the numbers show direction. [Proposed]

---

## 9. Health literacy and tone standard [Proposed]

The four part pattern, used where it applies and never forced on simple questions
1. What CURA found, with value, unit, report range and date.
2. What it means in one plain sentence.
3. Why it matters, only if it changes what the person does or feels.
4. What the person can reasonably do, with (review) items flagged.

Language
- Plain words. Define a medical word in the same sentence or replace it.
- No "elevated", "suboptimal", "dyslipidemia" without a plain gloss.
- Numbers always carry the unit and the person's own report range.
- Hindi and Hinglish: same rules, shorter sentences, native reviewer required. [Open decision]

Disclaimers and referrals
- One short qualifier at most, only where content could be misread: "a risk estimate, not a diagnosis" for Bio-AI, "a reading of your results, not a diagnosis" for blood.
- No stock closing "consult your doctor". Mention a doctor only with a reason. Today's fallback answers still contain generic lines (section 10).
- Emergency symptoms: the safety action is the first line.

Uncertainty
- Say what the report cannot tell, say when data is missing, once. Use "may be linked to". Never "caused by".

Repetition: no value stated twice in one answer; no follow up repeated.

---

## 10. Known problems found in the current system

Release blocking [Release blocking]
1. The prioritization rules in section 6 and every (review) item have no clinical sign off.
2. The Bio-AI scale comes from the sample report. Production labels, thresholds and the strings the live feed sends are not confirmed (see section 10 below, "Found while applying the knowledge base").
3. The replacement wording for the removed lines below is engineering's draft and needs clinical review.

Fixed in this round, wording still Unreviewed [Implemented and tested]
- "Results a little outside the range are common and often settle on their own" is removed. It is replaced by "One result outside the range does not show what is behind it. A doctor can read it alongside your other results."
- "Everything here is within your lab's normal range, so there is nothing that needs action" is removed. It is replaced by "These results are within your report's range, so no action is needed because of them alone. One reading does not rule out a problem."
- The generic "worth discussing with your doctor at your next visit" is replaced by a specific line per result: repeat the test (HbA1c, fasting glucose), ask what the result means and whether action is needed (triglycerides), ask whether treatment is needed (vitamin D). Each of these is a clinical recommendation and is marked for review.
- Follow up suggestions no longer fall back to stock questions such as "How much exercise do I need each week?" for a person with results on record. When grounded questions run out, fewer are shown, possibly none.

Found while applying the Bio-AI knowledge base [Implemented and tested]
- The code compared exact short words ("high", "very high"). The report's labels are "Increased Risk", "High Risk" and "Very High Risk". With those labels a High Risk result would have counted as not raised. All comparisons now use one normaliser (`app/contracts/risk_status.py`). Whether the live feed sends labels or short words is not known, so both are handled.
- The ordering of raised risks put "increased" first, ahead of Very High Risk. "Increased Risk" is the lowest raised band. Fixed in the registry order.
- The presentation code ranked "Increased Risk" the same as a healthy result. Fixed.

Not yet shown to the person, though the knowledge base defines them [Proposed]: the health rank or percentile, the lifestyle contribution, the overall metabolic risk score, and metabolic age. The overview shows metabolic age as "an estimate of your body's metabolic health". The knowledge base says to explain it as a model estimate, not biological age, a diagnosis or a lifespan measure, and not to mix it up with the other elements. That wording needs checking.

The registry text said "Your chances of developing excess fat in your liver" and "Your chances of hormone related conditions". The knowledge base says a score is not a probability, so both are reworded ("Whether fat may be building up in your liver", "Whether hormone related conditions may need attention"). The new wording is Unreviewed. [Implemented]

Other open problems
- Answer cards and the range bar do not show the "A little above" distance labels yet. The range bar itself exists.
- "Explain more simply" returns a service unavailable message when the model is off; with the model on it is untested.
- The personal prompt is over its own size budget (3409 against 3200 characters).
- Hindi and Hinglish copy has no reviewer.

Fixed in this round [Implemented and tested]
- A crash in the answer cleaner on any non bullet line with a routine "see your doctor" sentence.
- A requested date with no report now says so plainly.
- A follow up was turned into "What does is it serious mean in everyday terms?"; HbA1c lost its capital letters in suggestions.
- Category status no longer rises because a number is far from its range.
- The model can no longer choose or reorder the priority areas.

---

## 11. Accessibility and mobile [Implemented in part]

Implemented: visible focus ring, skip link, clinical text at least 14 px, 44 px touch targets on touch screens for chips and buttons, reduced motion everywhere, errors announced as alerts, draft kept after a failed send. Not yet verified on a real phone or with a screen reader.

Proposed: status never by colour alone, range bar with a text alternative, single column, first line visible without scrolling, follow ups never overlapping the composer, 200 percent zoom without horizontal scroll.

---

## 12. Acceptance criteria

Automated, run with synthetic data and the model off [Implemented and tested, 19 passing]
- Summaries count markers correctly (6 outside, 3 inside, 9 total) and do not confuse markers with areas.
- Related measurements are read together where implemented (glucose with HbA1c, iron pattern).
- Findings carry the actual value, unit, report range, date and source.
- Predicted risks are labelled predictions and never described as diagnoses; the raw score and category are both kept.
- A status never rises only because a value is far from its range; priority order is by tier, then fixed order; the model cannot change it.
- A follow up keeps the trusted value and context, and never falls back to stock questions.
- A high LDL, an in range ALT and a low vitamin D answer contain no unsupported reassurance or generic referral.
- A requested date with no report is said plainly.

Not yet done [Proposed]
- Testing with a live model.
- Testing with real people aged about 45 to 65: can they say what was found, whether it is serious, what to do, and which result was measured and which predicted.
- Screen reader and keyboard checks on a phone.
- Clinical review of every (review) item.

No usability scores exist. None may be reported until real sessions are run.

---

## 13. Roadmap

Done: errors, retry and draft; accessibility base; welcome copy and returning greeting; distance labels in the overview; date with no report; follow up template guard; deterministic prioritization; acceptance suite; this specification and `docs/BASELINE_TEST_TRIAGE.md`.

Next
1. Clinical review of the rules and (review) items (blocks release).
2. Bio-AI score screen with documented scale and limits (needs documentation).
3. Clinical review of the replacement wording (section 10).
4. Separate Measured and Predicted headings in the area screen.
5. Source and date on answer cards, not only the area screen.
6. Distance labels on answer cards and the range bar.
7. Connected evidence for the heart, liver and kidney groups.
8. Nutrition and uploaded document patterns.
9. Hindi and Hinglish review, usability sessions, screen reader pass.

## 14. Open decisions

- Who owns clinical review, and the review process.
- Whether Increased Risk (26 to 50) plus any blood result outside range should count as closer attention.
- The Critical label wording ("Needs medical attention soon").
- Confirm that production Bio-AI labels, thresholds and feed strings match the sample report in the knowledge base.
- Who reviews Hindi and Hinglish.
