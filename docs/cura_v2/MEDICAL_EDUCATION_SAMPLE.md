# CURA V2.3 medical education sample

Status: content-design draft for clinical and product review. This document does not change the
authoritative Medical Knowledge Library and must not be presented as clinically approved copy.

## Purpose

This sample establishes how CURA should teach health concepts to someone with no medical
background before the same standard is applied across V2.3. It covers:

- Liver Health
- Alkaline phosphatase (ALP)
- Direct bilirubin
- Vitamin B12
- HDL cholesterol
- HbA1c
- ESR
- Oxidative stress
- Fatty liver
- Metabolic age

The sample uses the existing V2.3 facts and limitations. Substantially revised claims still require
claim-level source verification and clinical review.

## Writing standard

### Start with the body, not the test name

Explain an unfamiliar body process before using it to interpret a result. For example, explain that
bile is a fluid made by the liver that helps digest fats and carries waste out of the liver before
discussing “bile flow”.

### Make every paragraph independently understandable

- Define an enzyme as a substance that helps chemical reactions happen.
- Define a hormone as a chemical message that helps organs coordinate.
- Define metabolism as how the body turns food into energy and uses or stores it.
- Define inflammation as part of the body’s response to injury, infection or irritation.
- Do not begin with “this process”, “it”, or “these findings” when the preceding idea is absent.

### Separate four kinds of information

1. **General education:** established information about the body.
2. **Measured finding:** a value, unit, range, status and date from a laboratory report.
3. **Predicted risk:** a provider score and classification, not a diagnosis or probability.
4. **Self-reported context:** a habit or symptom the person reported, not an observed fact.

Possible influences must never be presented as confirmed causes. A related result must not be
presented as a model contributor unless provider attribution confirms it.

### Explain a relationship, do not list it

A relationship needs:

- the role of each measurement;
- why looking at them together adds context;
- what the combination can and cannot establish;
- personal values only when both results are verified and relevant.

### Support maintenance as well as improvement

For a result inside its report range:

- say what is encouraging about that specific test;
- state the limit of that reassurance;
- recognise an already verified healthy habit when relevant;
- do not manufacture a recommendation merely to fill a field.

For a result outside range:

- explain the direction in plain language;
- give the most relevant general possibilities;
- distinguish lifestyle support from findings that require medical investigation;
- never promise that lifestyle will normalise the result.

### Progressive depth

The first answer should resolve the question, not reproduce the entry. Retrieval may supply the
complete entry, but the model selects the few fields that help this turn. Further mechanisms,
relationships, factors, limitations and sources remain available for follow-up questions.

## Intended field usage

| V2.3 field | Intended role |
| --- | --- |
| `short_description` | Standalone definition, not a fragment |
| `what_happens_inside_my_body` | Ordered biological explanation; define unfamiliar concepts |
| `why_this_test_matters` / `why_it_matters` | What the measurement or condition adds to understanding |
| `result_explanations` | Direction-specific interpretation, including a meaningful normal state |
| `possible_influencing_factors` | General influences with an explanation of how they may matter |
| `relevant_lifestyle_factors` | General lifestyle relationships, never assumed personal contributors |
| `related_biomarkers` | Retrieval keys only; the user-facing relationship comes from a relationship entry |
| `clinical_limitations` | One topic-specific boundary selected for the answer |
| `suggested_questions` | Natural, state-appropriate candidates; no duplicated generic substitutions |
| `source_ids` | Claim traceability; empty or generic source mappings remain an evidence gap |
| `review_status` and `review_dimensions` | Governance metadata, never silently converted to approval |

## Representative educational content

The following is target prose for review, not an update to V2.3.

### Liver Health

Your liver is a large organ that processes nutrients from food, makes substances your body needs,
and helps remove waste. It also makes bile, a fluid that helps digest fats and carries some waste
out of the liver through small tubes called bile ducts.

Liver blood tests look at different parts of this work. ALT and AST can rise when liver cells are
irritated. ALP and GGT can give clues about the bile ducts, although ALP also comes from bone.
Bilirubin shows how the body processes waste from old red blood cells. Looking at the pattern is
more useful than treating one result as a complete picture.

Avoiding tobacco, limiting alcohol where relevant, eating a varied diet and staying active can
support general liver health. These habits do not explain every abnormal result, and some patterns
need medical investigation.

### Alkaline phosphatase (ALP)

ALP is an enzyme found mainly in the liver, bile ducts and bones. An enzyme is a substance that
helps chemical reactions happen. A small amount of ALP normally enters the blood.

ALP may rise when bile is not moving normally through the liver or when bone-building activity is
higher. GGT and bilirubin can add context: GGT is more closely linked to the liver and bile ducts,
while bilirubin shows how the liver processes and removes waste. These results can suggest a
direction, but they do not prove the cause.

A result inside its report range does not show increased ALP activity at that time. A high result
can come from liver, bile-duct or bone-related processes. A low result is less common and may have
little significance, although nutrition or bone-related conditions can sometimes contribute.

Limit: ALP alone cannot show whether the source is liver or bone.

### Direct bilirubin

The body continually replaces old red blood cells. Their breakdown produces bilirubin, a yellow
waste substance. The liver changes bilirubin into a form that can travel in bile and leave the
body. Direct bilirubin measures mainly this processed form.

Comparing direct bilirubin with total and indirect bilirubin helps show whether a change is more
consistent with bilirubin production, liver processing or bile drainage. A higher direct bilirubin
can occur when processed bilirubin is not being removed normally, but the complete liver pattern
and clinical context are needed.

A result inside its report range is encouraging for this part of bilirubin processing. It does not,
by itself, prove that every aspect of liver or bile-duct health is normal.

Limit: the laboratory “direct” fraction is not identical to conjugated bilirubin in every assay.

### Vitamin B12

Vitamin B12 is a nutrient the body needs to make healthy red blood cells and maintain nerves. It
comes mainly from animal-derived or fortified foods. The stomach and small intestine must release
and absorb it before the body can use it.

Low B12 may reflect low intake or difficulty absorbing it. Haemoglobin and MCV can show whether
blood cells have changed, but nerve symptoms can occur without anaemia. A borderline result may
need clinical interpretation or additional testing rather than food advice alone.

A result inside its report range is encouraging, but symptoms and factors that affect absorption
can still matter. A high result may reflect supplements; less commonly, it may need interpretation
with the wider health picture.

Limit: a blood B12 value does not always show whether cells are receiving enough usable B12.

### HDL cholesterol

Cholesterol is a waxy substance the body uses to build cells and make certain hormones. Because it
cannot travel freely in blood, it is carried inside particles. HDL particles help move cholesterol
from tissues back toward the liver, which is why HDL is often called “good cholesterol”.

HDL is interpreted with LDL, triglycerides, non-HDL cholesterol and other heart-risk information.
A higher HDL value does not cancel the effect of high LDL, and one HDL result cannot prove that the
arteries are healthy.

A low HDL result can sit alongside higher heart risk. Physical activity, smoking, inherited traits
and triglyceride patterns can influence HDL, but they are possible influences rather than a
confirmed explanation for one person’s result.

### HbA1c

Food containing carbohydrate is broken down partly into glucose, a sugar that cells use for
energy. Glucose travels in the blood, and some naturally attaches to haemoglobin inside red blood
cells. HbA1c measures that attachment, giving an estimate of the blood-sugar pattern over roughly
the previous two to three months.

Fasting glucose is a snapshot from one point in time; HbA1c reflects a longer period. A higher
HbA1c often means the average blood sugar has been higher. A result inside its report range is
encouraging for the period represented, but it does not rule out every glucose problem.

Limit: blood loss, transfusion, some haemoglobin variants and conditions that change red-cell
lifespan can make HbA1c less reliable.

### ESR

ESR measures how quickly red blood cells settle at the bottom of a tube. During some forms of
inflammation, proteins in the blood make the cells clump and settle faster. Inflammation is part
of the body’s response to infection, injury or irritation.

A result inside its report range does not show an elevated ESR at that time. A higher result can
occur with inflammation, anaemia, pregnancy and other conditions. ESR cannot show where the
problem is or what caused it. CRP and blood counts may add context because they reflect different
parts of the inflammatory and blood-cell picture.

Limit: a normal ESR does not rule out every type of inflammation.

### Oxidative stress

As cells make energy, they naturally produce reactive substances that can damage cell structures.
The body has protective systems that keep them in balance. Oxidative stress describes a situation
where those reactive substances exceed the protection available.

Persistent oxidative stress is studied in relation to inflammation and several long-term health
conditions. A Bio-AI score estimates risk; it does not directly measure cell damage and is not a
diagnosis.

Eating patterns, sleep, smoking, physical activity and ongoing stress are general factors studied
in relation to this balance. They are not confirmed reasons for an individual score unless
provider attribution says so.

### Fatty liver

The liver normally contains a small amount of fat. Fatty liver means that more fat than expected
has collected inside liver cells. This can happen when the liver receives or makes more fat than it
can use or send elsewhere.

Some people have no symptoms. In others, continued fat buildup can be associated with irritation
and, over time, scarring. Blood tests and a predicted risk assess different things: liver enzymes
can give clues about cell irritation or bile handling, while the Bio-AI score is a risk estimate.
Neither one alone confirms or rules out fatty liver.

Food patterns, physical activity, alcohol use where relevant, body-fat distribution and metabolic
health can be related. They must not be presented as confirmed contributors to a person’s score
without attribution.

### Metabolic age

Metabolic health describes how the body handles energy, blood sugar and fats. Metabolic age is an
estimate that compares parts of this health pattern with age-related patterns in a reference
population. It is not the age of the person’s organs, a measure of ageing speed or a prediction of
lifespan.

The MetSights assessment may consider relevant biomarkers, food and lifestyle information and
questionnaire responses. CURA does not have the formula, weights or reference population, so it
must not say which input caused the result.

Blood sugar, triglycerides, HDL, activity, sleep and food habits may help discuss metabolic health
when verified and relevant. They are not automatically model contributors.

## Example personalised responses

All values below are hypothetical test cases. They must be replaced with verified member evidence
at runtime.

### ALP, slightly above the report range

ALP is an enzyme found mainly in your liver, bile ducts and bones. Your result is above the range
on your report. That does not automatically mean liver damage, because bone activity can also
raise ALP.

Your GGT, ALT, AST and bilirubin results can add context if they are available. For example, ALP
and GGT rising together can point more toward the liver or bile ducts, while ALP without a similar
GGT change may leave a bone source more open. This pattern cannot diagnose the cause. A clinician
can decide whether the result needs repeat testing or further investigation.

### Direct bilirubin, above range with other liver findings available

Direct bilirubin is bilirubin your liver has processed so it can leave through bile. Your result is
above the range on your report. Your total bilirubin, ALP, GGT, ALT and AST help show whether the
pattern is more related to bilirubin processing, bile drainage or liver-cell irritation.

These blood tests can provide clues, but they do not identify a blockage or diagnose liver disease
on their own. Because the result is outside range, it is appropriate to discuss the overall pattern
with a clinician, especially if you have yellowing of the eyes or skin, dark urine, pale stools,
fever or significant abdominal pain.

### Vitamin B12, low

Vitamin B12 helps make healthy red blood cells and supports nerves. Your result is below the range
on your report. Low intake is one possibility, but difficulty absorbing B12 in the stomach or
intestine can also contribute.

Your haemoglobin and MCV can show whether your blood cells have changed, but normal blood counts do
not rule out B12-related nerve symptoms. Food choices may help when intake is low, but a clearly
low result may need medical assessment because food alone does not address every cause. CURA will
not recommend a supplement or dose.

### HDL, within range

HDL helps carry cholesterol back toward the liver. Your result is within the range on your report,
which is encouraging for this part of your cholesterol profile. It is still best understood with
LDL, triglycerides and non-HDL cholesterol because HDL alone cannot show whether the arteries are
healthy.

If regular activity or avoiding smoking is already part of your routine, those are useful habits
to continue. No new lifestyle change is needed solely to fill a recommendation field.

### HbA1c, high

HbA1c reflects the amount of sugar attached to red blood cells over roughly two to three months.
Your result is above the range on your report, which commonly reflects a higher average blood-sugar
pattern over that period.

Fasting glucose is a one-time snapshot and can differ from HbA1c. Conditions affecting red blood
cells can also change the result, so the two measurements and your clinical context should be
interpreted together. Food, activity and sleep may support glucose health, but an abnormal HbA1c
needs appropriate medical interpretation rather than a promise that lifestyle alone will correct
it.

### ESR, within range

ESR measures how quickly red blood cells settle in a tube. They may settle faster during some forms
of inflammation. Your result is within the range on your report, so this test does not show an
elevated ESR at this time.

A normal ESR does not rule out every type of inflammation. CRP and your symptoms may provide
different information when clinically relevant.

### Oxidative stress, raised prediction with ESR in range

Oxidative stress describes an imbalance between reactive substances made by cells and the body’s
protective systems. Your Bio-AI assessment is in the provider’s raised-risk band. This is a risk
estimate, not a direct measurement of cell damage or a diagnosis.

Your ESR is within the range on your report. ESR can rise with some forms of inflammation, but it
does not directly measure oxidative stress, so these findings do not necessarily contradict each
other. Eating patterns, sleep, smoking, activity and stress are general influences studied in this
area, not confirmed causes of your score.

### Fatty liver, lower prediction with abnormal liver blood results

Fatty liver means extra fat has collected inside liver cells. Your Bio-AI assessment is in the
provider’s lower-risk band, but that does not rule out fatty liver or make an abnormal liver blood
result unimportant.

The prediction estimates one health pattern. ALP, bilirubin, ALT, AST and GGT examine different
parts of liver and bile-duct health. The abnormal results should be interpreted on their own
merits. CURA should not claim they caused the score or that the lower score proves the liver is
healthy.

### Metabolic age above actual age

Your metabolic age estimate is above your actual age. This compares parts of your metabolic health,
such as how the body handles sugar and fats, with age-related patterns. It is not your biological
age, ageing speed or lifespan.

Verified blood sugar, HbA1c, triglycerides, HDL and relevant recorded habits can help explain your
metabolic-health picture. They must not be described as causes of the estimate because CURA does
not have the MetSights formula or individual feature attribution. The most useful next step is to
build on the habits already working and focus on the relevant findings that need attention.

## Review checklist

A reviewer should be able to answer yes to each item:

- Can a person understand every medical term without another search?
- Does the explanation begin with the concept needed to understand what follows?
- Are measured, predicted, self-reported and general statements clearly separated?
- Does each relationship explain why the measurements belong together?
- Are normal results encouraging without implying absence of disease?
- Are abnormal results explained without blame, diagnosis or lifestyle promises?
- Does every new claim have an appropriate source mapping?
- Are assay and provider limitations preserved?
- Are suggested questions natural and state-specific?
- Is review status still pending until clinical approval occurs outside CURA?

## Known blockers before library-wide migration

1. Most representative biomarker entries use `evidence_status: verification_incomplete`.
2. Several entries map to generic source ids such as `lab_results`; claim-level evidence is not yet
   sufficient for substantially revised prose.
3. The oxidative-stress entry has no source ids.
4. The metabolic-age formula, feature weights and reference population are undocumented in CURA.
5. Structural validation currently fails because metabolic age refers to the noncanonical
   biomarker id `hdl`; the canonical id is `hdl_cholesterol_direct`.
6. Screen eligibility accepts every non-rejected row, including `pending_clinical_review` and
   `integration_readiness: blocked` content. Conversational retrieval uses a different rule and
   requires approved plus verified content. None of the representative entries qualify, so their
   rich V2.3 passages are absent from personalised model prompts.
7. Influencing factors are labels, not structured relationships with mechanism, applicability and
   evidence.
8. `related_biomarkers` is a retrieval list. It is not a substitute for reviewed relationship
   content.
9. Governance files conflict: the CURA governance document says non-rejected rows are usable,
   while `REVIEW_REQUIRED.md` says there is no clinical sign-off and not to integrate the library
   into production.
10. The schemas only represent `pending_clinical_review`; they cannot record a clinically approved
    state. The manifest has no release date, while biomarker rows still identify their content
    version as 2.2.

These blockers should be resolved or explicitly accepted by the medical-content owner before this
sample is migrated into the authoritative V2.3 files.

## Full-library structural audit

The audit found:

- 330 biomarker and allergen rows: 119 non-allergen biomarkers and 211 allergens.
- 114 mapped canonical identifiers and 216 unresolved identifiers.
- 15 health categories, 12 Bio-AI entries and one shared education module.
- 219 directed biomarker relationships representing 113 undirected pairs.
- 31 lifestyle relationships covering 29 of 91 questionnaire questions.
- All 330 biomarker and allergen entries remain pending clinical review.
- 234 entries require assay confirmation, including every allergen.
- Practical guidance is present for Bio-AI entries but absent from all laboratory entries.
- Ten of twelve Bio-AI entries have no sources. All 38 Bio-AI biomarker-context links explicitly
  say the biomarker is not a confirmed model contributor.
- Ninety-one of 219 biomarker relationships and twelve of 31 lifestyle relationships lack sources.
- Every lifestyle relationship lacks a production questionnaire key and confirmed model
  contribution.

The most extensive duplication is in allergens, generic normal and reference-unavailable
interpretations, bidirectional relationship prose and lifestyle mappings. This confirms that a
library-wide rewrite must be accompanied by canonical identity resolution, source verification,
relationship normalisation and an approval-state design. Copy editing alone will not make V2.3
release-ready.
