# CURA 2.0 Product and UX Specification

Purpose: make health information understandable and useful to an ordinary person, not to build a prettier chatbot.

Status: draft for review. All people, values and answers below are synthetic. The example answers are the target wording. They are not captured model output, and none has had clinical review. Clinical sign off is a precondition for release (see section 9).

Guiding rules
1. Say what matters first, in words a 12 year old could follow.
2. One health story per health area. Blood results and Bio-AI predictions are told together, but never blurred.
3. Use a picture or a badge only when it says something faster than a sentence.
4. Never invent a conclusion. Keep uncertainty. No causes, no probabilities from model scores.
5. Every personal answer ends at something the person can reasonably do, or says plainly that nothing is needed.

Synthetic person used throughout: Meena, 55, no medical background, phone user.

Her synthetic results
- HbA1c 5.9 % (report range up to 5.7). Fasting glucose 104 mg/dL (70 to 99). LDL 142 mg/dL (under 100). HDL 38 mg/dL (50 or more). Triglycerides 168 mg/dL (under 150). Vitamin D 12.6 ng/mL (30 to 100). Haemoglobin 12.8 g/dL (12 to 15, in range). TSH 2.1 (in range). Creatinine 0.8 (in range). No liver panel in the report.
- Bio-AI: Type 2 diabetes risk in the "high" band. Heart disease risk in the "moderate" band. Fatty liver risk in the "low" band.
- Conflicts and gaps built in: Bio-AI diabetes is high while her blood sugar is only slightly above range. Fatty liver risk is low but there is no liver blood test to compare with.

---

## 1. Complete user journey

### 1.1 Opening the app (first visit, report available)
Meena sees one screen, no menu to learn:

```
Hello Meena

Your latest blood report and Bio-AI report are ready.

[ See my health at a glance ]        <- the one big button

Or ask me anything about your health
[ Type your question...        ] [mic]

Questions people often ask
  Why is my vitamin D low?
  What should I look at first?
  What can I eat for better blood sugar?
```

Rules: one primary action. Report specific suggestions appear only because the reports exist. No capability grid of three equal cards. Nutrition appears as a chip, not a card, unless nutrition data exists. The greeting uses the first name only.

### 1.2 Returning visit
```
Welcome back, Meena

Last time we talked about your vitamin D.
[ Continue ]   [ Start something new ]
```
Shown only when a recent conversation exists. If not, the first visit screen is shown with "Welcome back" as the first line. (Stage 2 already shows the "Welcome back" line from a device flag. The "Continue" link is not built.)

### 1.3 Health at a glance (one screen, no reading required)
```
Your health at a glance

Most of your results are in range.        <- one sentence, counts only
A few things deserve attention.

Start here
 1. Vitamin D is low            [ Read more ]
 2. Cholesterol is higher       [ Read more ]
 3. Blood sugar is edging up    [ Read more ]

Explore by area
  Heart and circulation    Worth attention     >
  Blood sugar              Worth attention     >
  Vitamins and minerals    Needs a closer look >
  Liver                    Not checked yet     >
  ...
```
Rules: at most three "Start here" items. Whole row is tappable. Each area shows one plain status. No score, no pie, no traffic light array. This is the existing unified overview, with "Start here" kept to three and wording per section 4.

### 1.4 An area (for example Blood sugar)
Order, top to bottom, nothing repeated:
1. One sentence answer ("Your blood sugar is a little above the usual range, and the risk estimate agrees that it deserves attention.")
2. "What we measured" (blood tests) with each value and its plain label.
3. "What the Bio-AI estimate adds" (prediction, labelled as such).
4. "What you can do" (one to three items).
5. Up to four follow-up questions, all different from what is already on the page.

### 1.5 Asking a question
Typed, spoken, or tapped from a suggestion. While waiting she sees "Looking at your results..." and nothing about internal steps. The answer starts at once; long answers show the first part and a "Show more" link.

### 1.6 Knowing what to do next
Every personal answer ends with a "What you can do" line, or says "Nothing is needed right now". It never ends with a generic "consult your doctor". A doctor is mentioned only with a reason and a time frame (section 4).

Clicks and reading budget
- Open the app to a useful answer about her own results: 2 taps (glance, area).
- A typical answer is read in under 20 seconds: about 60 to 90 words before "Show more".
- No screen asks her to read the same finding twice.

---

## 2. Response patterns with realistic examples

Conventions: **Short answer** is always the first line. "Details" are collapsed after the first screenful. Labels are plain words, never colour alone, and each has a small text label.

Plain status labels for a measured value (used everywhere)
- In range
- A little above range / A little below range (just outside the report's own range)
- Above range / Below range
- Well above range / Well below range
- Needs medical attention soon (only for values the clinical thresholds file marks critical; unchanged from the existing deterministic rules)

"A little" versus "well" is decided by the existing deterministic rules, never by the model. How far past the limit a number is does not say how serious it is, so the label describes distance only, and the next step line carries any urgency.

Colour: neutral for "In range", amber for outside range, and a stronger tone only for "Needs medical attention soon". Never red for a minor deviation.

### 2.1 General health question (no personal data needed)
Question: "What is HbA1c?"
```
HbA1c shows your average blood sugar over the last 2 to 3 months.

A higher number means your blood sugar has been running higher than usual.
It is one of the main tests doctors use to check for diabetes.

Want to see yours?   [ Show my HbA1c ]
```
Structure: short answer, one extra idea, one optional personal link. No disclaimer. The "Show my HbA1c" chip appears only if a result exists.

### 2.2 Single biomarker, personal
Question: "Why is my vitamin D low?"
```
Your vitamin D is 12.6 ng/mL. That is well below the usual 30 to 100.     [ Well below range ]

Why it matters
Vitamin D helps your body use calcium, so low levels can affect bones and muscles over time.

What may be behind it
Common reasons are little sun exposure or low intake. Your report cannot tell which applies to you.

What you can do
 - Ask your doctor about a supplement, because 12.6 is low enough that food and sun alone are unlikely to fix it.
 - Retest in about 3 months to see if it has moved.

[ What foods have vitamin D? ]  [ Is this why I feel tired? ]
```
Structure: value and label in the first sentence (found, and what it means), why it matters, a hedged "may be" cause line, what to do. Source line in small text: "From your blood report of 18 Aug 2026".

The range picture is a single horizontal bar with her value marked, shown only when a numeric range exists (see section 3, S3). Text already states the range, so the bar is optional and collapses on small screens to the label.

### 2.3 Single biomarker, mildly outside range
Question: "Is my fasting sugar ok?"
```
Your fasting blood sugar is 104 mg/dL, a little above the usual limit of 99.   [ A little above range ]

This is a small difference. One reading does not mean you have diabetes.

What you can do
 - Nothing urgent. Your next regular check will show if it stays above range.
```
Note the absence of a doctor referral. The reason is stated ("one reading, small difference"). If the same marker is above range on two reports, the pattern changes (section 6).

### 2.4 Complete blood report summary
Question: "Explain my blood report"
```
Most of your results are fine. 3 of 9 are outside the report's range.   <- counts from the data

What stands out
 - Vitamin D is well below range (12.6).
 - LDL cholesterol is above range (142), and HDL "good" cholesterol is below (38).
 - Blood sugar is a little above range (HbA1c 5.9, fasting 104).

In range
 Haemoglobin, thyroid (TSH) and kidney (creatinine).

Not in this report
 No liver tests were included.

What you can do
 - Start with vitamin D, as it is furthest from range.
 - Heart and blood sugar numbers are worth tracking at your next test.

[ Why is my cholesterol high? ] [ What should I eat? ] [ Compare with my Bio-AI report ]
```
Rules: three "stands out" items at most; everything in range collapses into one line; the tests that were not done are named once.

### 2.5 Bio-AI risk prediction
Question: "What does my diabetes risk mean?"
```
Your Bio-AI report puts your type 2 diabetes risk in the high band.   [ Risk estimate: High ]

This is a prediction from your health data. It is not a diagnosis and it is not a percentage chance.

What fed into it
Your blood sugar, weight and family history were among the inputs.  <- only inputs the report itself lists

What you can do
 - Your blood sugar tests are the real check. Yours are a little above range, so keep tracking them.
 - Walking after meals and cutting sugary drinks help blood sugar for most people.

[ What is the difference between this and my HbA1c? ] [ How can I lower it? ]
```
Rules: the prediction label is a "band" word only. The raw score number is not shown (decision needed, section 9). Never "you have a 68% chance". Never "this is caused by".

### 2.6 Unified Blood plus Bio-AI, one health area
Question tapped from the Blood sugar area: "What is going on with my blood sugar?"
```
Your blood sugar is a little above range, and the Bio-AI estimate also flags diabetes risk as high.

What your blood test shows (measured)
 HbA1c        5.9 %    A little above range
 Fasting      104      A little above range

What the Bio-AI estimate shows (predicted)
 Type 2 diabetes risk    High band

Putting it together
Both point the same way, but they are different kinds of information. The blood tests are measurements. The estimate is a prediction that also uses other details. The measurements are only slightly above range, so a high band does not mean you have diabetes.

What you can do
 - Ask your doctor whether to repeat HbA1c and fasting sugar. Two readings together are more reliable than one.
 - Keep walking after meals if you can.
```
Rules: "(measured)" and "(predicted)" headings are always shown. "Putting it together" is one short paragraph, written only when both exist. It states agreement or disagreement, never a cause.

When they conflict (Bio-AI heart risk moderate, but cholesterol is above range and HDL low): "Your cholesterol numbers are above range. The Bio-AI heart estimate is moderate, not high. These do not contradict each other, because the estimate uses more than cholesterol."

### 2.7 Nutrition and lifestyle
Question: "What can I eat for better blood sugar?"
```
Foods that help most are the ones that digest slowly.

Eat more
 - Dal, chana, rajma and other pulses
 - Vegetables, especially leafy ones
 - Whole grains like jowar and bajra instead of white rice

Eat less
 - Sugary drinks and sweets
 - White bread and maida snacks

A walk of 10 to 15 minutes after meals also helps.

[ Give me a one day meal idea ] [ What about fruit? ]
```
Rules: name foods first, in everyday words and local foods when region is known. Link to her data only in one clause ("Your sugar is a little above range, so this is worth doing"). No list of lab values.

### 2.8 Multi turn follow ups
```
Meena:  Why is my vitamin D low?
CURA:   (answer 2.2)
Meena:  Will sunlight be enough?
CURA:   Probably not on its own at 12.6. Sun helps, but at this level a supplement is usually advised.
        Ask your doctor about the dose.
Meena:  explain simply
CURA:   Your body is very short of vitamin D. Sun and food may not be enough to fill the gap, so a doctor
        will probably suggest a supplement.
```
Rules: a follow up answers the new question in two to four sentences, uses the value only if it changes the answer, does not repeat the earlier explanation, and "explain simply" rewrites the previous answer, shorter, no new facts.

---

## 3. Screen by screen UI specification

S1 Welcome (section 1.1). One primary button, one input, three question chips.
S2 Health at a glance (1.3). Sentence, at most three "Start here" rows, area list with one status each.
S3 Area screen (1.4). Sections in order: Answer sentence, Measured, Predicted, Putting it together, What you can do, Follow ups.
- Biomarker row: name, value with unit, plain label. Tap to open "About this test" (existing reviewed education text, not model generated). A range bar (already built as `RangeBar`) appears only when the report range has numeric bounds and the screen is wider than 360 px; it is not the only carrier of meaning.
S4 Chat. Messages as bubbles; the answer's first line is bold. Follow ups below the answer, at most four. "Show more" after about 90 words.
S5 Uploaded document. Plain summary, values with the same labels, a clear line for what could not be read, and "Compare with my results" only if both exist.
S6 Errors and empty states. One calm sentence, what happened, what to do, Try again button, draft kept (Stage 1 done). "No report yet" screens say what to do ("Your report will appear here once SuperShyft uploads it") and still allow general questions.
S7 Processing. "Looking at your results..." then the answer streams. No stage names.

Visual limits: no charts except the optional range bar; no more than one badge per row; no badge for "in range" items inside lists (they collapse to one line).

---

## 4. Health literacy and tone standard

The four part pattern (use where it applies, never forced)
1. What CURA found: the fact, with number and unit.
2. What it means: one plain sentence.
3. Why it matters: only when it changes what the person does or feels.
4. What she can do: realistic, optional, specific.
A simple "What is HbA1c?" has only part 2. A single mildly high marker has parts 1, 2 and 4.

Language
- Target reading level: about grade 6. Sentences under 20 words. One idea per sentence.
- Define a medical word in the same sentence or replace it: "blood sugar", "good cholesterol (HDL)".
- Numbers always carry the unit and the person's own report range.
- No "elevated", "suboptimal", "dyslipidemia", "glycaemic" in answers. Allowed once with a plain gloss if the report uses it.
- Hindi and Hinglish: same rules; sentences even shorter; native reviewer required before release.

Disclaimers and referrals
- One short qualifier maximum per answer, and only where the content could be misread: "a risk estimate, not a diagnosis" (Bio-AI) or "a reading of your results, not a diagnosis" (blood).
- No stock "consult your doctor" closer. Mention a doctor only with a reason and a time frame: "Ask your doctor about a supplement, because 12.6 is low enough that food and sun alone are unlikely to fix it."
- Emergency symptoms: the safety action is the first line.

Uncertainty
- Say what the report cannot tell her ("Your report cannot tell which applies to you").
- Use "may be linked to", "one common reason is". Never "because of", "caused by".
- Say plainly when data is missing, once ("No liver tests were included").

Empathy without drama
- Neutral, calm first line. No praise openers, no "Don't worry", no "Unfortunately".
- Good news is said plainly ("Most of your results are fine").

Repetition
- Never state the same value twice in an answer. Never repeat a follow up suggestion that was already asked in the conversation.

---

## 5. Blood plus Bio-AI combined experience

Principles
1. One area, one story. The user never has to open "Blood" and "Bio-AI" separately.
2. Always label the type: "measured" (a blood test) or "predicted" (a Bio-AI estimate). Same two words everywhere.
3. A prediction is shown as a band (low, moderate, high). No percentages and no conversion of the score into a chance. The raw score is hidden by default; if product wants it, show it under "Details" with "This is a model score, not a probability".
4. Never infer cause either way ("high cholesterol is why your heart risk is moderate" is not allowed). Say what each shows, then say whether they agree.
5. Reports from different dates are separate facts. Do not comment on the date difference in the main story.

Scenario text (existing deterministic scenarios, new wording)
- Both reassuring: "Your results and your risk estimate both look good for this area."
- Blood outside, risk fine: "Your blood test is outside range. The risk estimate is not raised, which is reassuring but does not replace the test."
- Blood fine, risk raised: "Your blood tests are in range. The Bio-AI estimate still flags this area, so it is worth keeping an eye on."
- Both raised: "Both your blood test and the risk estimate flag this area, so it deserves attention."
- Blood only / risk only: say which one exists. "This area has no Bio-AI estimate."
- Incomplete: name the missing test once.

Where wording comes from: status and scenario are deterministic (unchanged). The model only words the single "Putting it together" paragraph and the answer sentence, and may not add numbers or statuses. Education text is reviewed copy.

---

## 6. Follow up conversation behavior

- At most four follow ups. They must be: relevant to this answer, different from each other, not already asked, and answerable from available data. Generic follow ups ("Tell me more") are never shown.
- Pattern: one "go deeper" (why), one "what can I do", one "connect" (another area or the Bio-AI side), one optional "compare" if two reports exist.
- If the answer already contains the action, do not offer "what can I do".
- A follow up question replaces, not extends, the earlier explanation. It must not restate the earlier value unless it changes the answer.
- Memory in the session: the last biomarker or area stays "in focus" so "Is it serious?" and "Will sunlight help?" resolve to it.
- If the question is vague ("what about the other one?"), ask one short clarifying question with two tappable choices.
- When a topic repeats across reports (HbA1c above range twice), say so in one sentence: "It was also above range in your June report." Do not call it worsening or improving unless the numbers show direction.
- "More simply" shortens the last answer and adds no facts.

---

## 7. Accessibility and mobile

- WCAG 2.2 AA. Text contrast 4.5 to 1, large text 3 to 1, UI parts 3 to 1.
- Status is never colour alone: each has a text label, and the label comes before the badge in reading order.
- Touch targets at least 44 by 44 CSS px on touch screens (Stage 1 added this for chips and buttons).
- Clinical text at least 14 px (Stage 1). Body 16 px. Support 200 percent zoom without horizontal scroll.
- Focus ring visible on every control (exists). Skip link (exists). Answers announced politely; errors use `role="alert"` (Stage 1).
- Reduced motion respected everywhere (Stage 1). No motion needed to understand anything.
- Range bar, if shown, has a text alternative: "12.6 ng/mL. Usual range 30 to 100. Well below range."
- Mobile first: single column; the answer's first line visible without scrolling; follow ups wrap and never overlap the composer; composer stays above the keyboard; draft preserved on error (Stage 1).
- Screen reader order: short answer, label, details, what you can do, follow ups.
- Voice input stays optional and its errors are plain sentences.

---

## 8. Usability acceptance criteria

These are targets to test with a small group of non clinical adults (aim for people aged 45 to 65). None has been measured yet.

Comprehension
- After reading an area answer, at least 8 of 10 participants can say in their own words: what was found, whether it is serious, and what they will do.
- At least 8 of 10 can correctly say which result was a blood measurement and which was a prediction.
- No participant concludes "I have diabetes" from a high Bio-AI band alone.

Effort
- From app open to an answer about their own top finding: at most 2 taps.
- First screenful of any answer is 90 words or fewer.
- No finding appears twice on one screen.

Language
- Every answer passes an automated check: no banned terms, sentence length under 20 words on average, no stock "consult your doctor", at most one qualifier.
- Every answer states units and the report's own range for each value mentioned.

Safety
- No answer states a cause, a diagnosis, or a probability derived from a Bio-AI score.
- Any value in an answer exists in the trusted data; numbers are checked after the model writes (existing guards).
- Red flag symptoms always put the safety action first.

Robustness
- Every state in section 3 (loading, empty, error, partial, offline) has been viewed on a phone width.
- Keyboard only and screen reader pass on S1 to S4.

Test matrix: the 15 scenarios from the CURA 2.0 brief, run against synthetic reports for Meena (conflicting, abnormal, incomplete), a person with all results in range, a person with no Bio-AI report, and a person with no reports. Results will be recorded as run, with pass or fail per scenario.

---

## 9. Prioritized implementation roadmap

Done: Stage 1 (errors, retry, draft, accessibility base), Stage 2 (welcome and returning), crash fix in `drop_routine_doctor`, baseline test triage (`docs/BASELINE_TEST_TRIAGE.md`).

Next, in order of value to the person:
1. Plain status labels everywhere (section 2). Done for the health overview and category screens ("A little above range", "Above range", "Well above range", and the same for below). Not yet done: answer value cards and the range bar, which need distance in the answer data. The "Critical" label is unchanged pending clinical sign off on "Needs medical attention soon". Replace "(low)" style tags with the five labels, derived from the existing deterministic status. Frontend plus a small mapping.
2. Biomarker answer structure: found, means, may be behind it, what you can do. Prompt and card changes. Blocked on triage item 3 (single value findings are empty), so the card reads the value from the trusted structured data.
3. Fix the "date with no report" answer (triage item 2). Must be fixed before release.
4. "Start here" capped at three on the glance screen and "what we measured / what Bio-AI shows / putting it together" in the area screen.
5. Remove generic doctor referral from deterministic fallback text ("It is worth discussing with your doctor at your next visit" appears today in the fallback answer for low vitamin D).
6. Follow up rules: four max, distinct, not already asked (also triage items 5 and the cap tests).
7. Bio-AI wording: band only, remove score numbers from answers; update or retire the score tests after the decision below.
8. Nutrition pattern (foods first, local foods).
9. Uploaded document pattern.
10. Hindi and Hinglish pass with a native reviewer. Test matrix run and report.

Decisions needed from you or clinical reviewers before release
- Show the raw Bio-AI score anywhere, or band only? Spec assumes band only.
- Approve the five status labels and the "A little" versus "Well" distinction.
- Clinical review of the example wording in sections 2 and 5, and of the "what you can do" statements (for example vitamin D and supplement advice, which is a clinician decision).
- Who reviews Hindi and Hinglish text.
- Whether the range bar is worth keeping at all after the first usability round.
