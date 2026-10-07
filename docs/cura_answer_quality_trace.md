# CURA answer-quality trace: where the answer was being lost

Offline trace on the mock user `eval-user-companion` (HbA1c 9.1 %, glucose 214.47 mg/dL without a fasting label, triglycerides 266, LDL 162, iron / red-cell pattern, borderline vitamin D, liver / kidney / thyroid in range, high Bio-AI diabetes / dyslipidemia / cardiac risk, sedentary questionnaire).

A stand-in model returns a recognisable paragraph (shown as **[model answer]**, followed by the facts it was given), so everything else in a final answer was produced by the pipeline. Real model prose must be captured with `scripts/trace_answers.py --user <id> --mode plain` against the live configuration.

## Findings: where quality was lost (old build)

| Stage | What happened |
|---|---|
| Routing | "top 3 things" matched the bare-number clarification; "what are ..." with *I* was treated as general; "matter less", "most attention", "is that because of" were not recognised. |
| Model tier | Follow-ups planned as explanations kept the lookup's DETERMINISTIC tier, so the model was never called ("Is that because of my sugar?" -> "Your latest Glucose is 214.47 mg/dL"). |
| Validator: numeric grounding | Any number within 80 characters after a marker name ("over the last 2-3 months", "Type 2") counted as an unsupported value and the whole model answer was replaced by a deterministic template: 5 of 15 reasoning questions ended as "the main pattern that stands out is Lipids". |
| Validator: entity coverage | Every domain-expanded entity the answer did not mention was appended as "X was not in reports" (fasting insulin, metabolic score, obesity, hypertension). |
| Composer | Spliced stock text into model answers ("The highest-yield next step is to review this lipids pattern with a clinician.") and sent cards, tables, chips and missing-data blocks alongside. |
| Context selection | "Why are my triglycerides high?" gave the model triglycerides alone (no glucose story, no reassuring HDL); priorities were ranked per marker, so HbA1c and glucose took two of three slots. |

## After

- Every reasoning question's final answer is exactly the model's answer after safety. Lookups and "show me my report" stay deterministic.
- `CURA_RESPONSE_MODE=plain` returns only the conversational answer (no presentation, chips, testing card or recommendations) and skips card assembly; `rich` keeps the old UI.
- Grounding removes only a sentence that states an unsupported personal value; explanatory numbers pass.
- The model receives ranked patterns (glucose regulation, blood fats, iron / red cells; vitamins last), reassuring systems (liver, kidney, thyroid) and, for a named marker, the markers that change its interpretation.

## Before / after (same data, same questions)

### Show me my latest blood report.

**Old** (`report_explanation`; UI extras: cards=True, chips=3)

> I found your latest blood report from 28 Sep 2026. It contains 20 reported results; 11 are outside the reported reference range; 9 are within range. The results worth reviewing first are HbA1c, Glucose, Triglycerides.

**New** (`report_explanation`, goal LOOKUP, plain mode)

> I found your latest blood report from 28 Sep 2026. It contains 20 reported results; 11 are outside the reported reference range; 9 are within range. The results worth reviewing first are HbA1c, Glucose, Triglycerides.
> 
> Outside your report's range:
> - HbA1c: 9.1 % (high, range 4.0–5.6)
> - Glucose: 214.47 mg/dL (high, range 70.0–140.0)
> - Triglycerides: 266.0 mg/dL (high, range 0.0–150.0)
> - LDL: 162.0 mg/dL (high, range 0.0–100.0)
> - Total Cholesterol: 248.0 mg/dL (high, range 0.0–200.0)
> - Hemoglobin: 11.9 g/dL (low, range 13.0–17.0)
> - MCV: 76.0 fL (low, range 80.0–100.0)
> - MCH: 24.0 pg (low, range 27.0–33.0)
> - RDW: 15.8 % (high, range 11.5–14.5)
> - Ferritin: 12.0 ng/mL (low, range 30.0–400.0)
> - Vitamin D: 27.0 ng/mL (low, range 30.0–100.0)
> 
> Within range: HDL 44.0 mg/dL, ALT 28.0 U/L, AST 24.0 U/L, Uric Acid 6.1 mg/dL, BUN 13.0 mg/dL, Creatinine 0.9 mg/dL, eGFR 98.0 mL/min/1.73m2, Calcium 9.4 mg/dL, TSH 2.1 uIU/mL.

### What should I actually pay attention to in my latest report?

**Old** (`broad_health_summary`; UI extras: cards=True, chips=1)

> [model answer] It discusses: HbA1c, LDL, Glucose, Triglycerides. The highest-yield next step is to review this lipids pattern with a clinician.

**New** (`broad_health_summary`, goal SYNTHESIZE, plain mode)

> [model answer] It discusses: HbA1c, LDL, Glucose, Triglycerides.

### What are the top 3 things I should work on?

**Old** (`ambiguous_clarification`; UI extras: cards=False, chips=0)

> Which test is that number from (for example fasting glucose, LDL or blood pressure)? Tell me and I will check it against its usual range.

**New** (`health_scenario`, goal PRIORITIZE, plain mode)

> [model answer] It discusses: HbA1c, Triglycerides, MCH, Glucose.

### Why is my Bio-AI metabolic risk high?

**Old** (`bio_ai_explanation`; UI extras: cards=True, chips=1)

> Your latest Bio-AI assessment shows: • **Type 2 diabetes:** 78 (high)
> • **Fatty liver (NAFLD):** 48 (moderate)
> • **Dyslipidemia:** 71 (high) Across the previous and latest Bio-AI assessments, the score moved from 190.0 to 214.47 (increased, 12.88%). These scores are from your Bio-AI assessment and are not a medical diagnosis. Fasting Blood Sugar Glucose was not in reports. Fasting insulin was not in reports. metabolic score was not found in the retrieved records. obesity was score not available. hypertension was score not available. Fasting Blood Sugar Glucose was not available in the retrieved report. Fasting insulin was not available in the retrieved report.

**New** (`bio_ai_explanation`, goal CAUSES, plain mode)

> [model answer] It discusses: Glucose, HbA1c, HDL, Triglycerides.

### Why are my triglycerides high?

**Old** (`blood_marker_explanation`; UI extras: cards=True, chips=1)

> [model answer] It discusses: Triglycerides.

**New** (`blood_marker_explanation`, goal CAUSES, plain mode)

> [model answer] It discusses: Triglycerides, HbA1c, Glucose, HDL.

### Is that because of my sugar?

**Old** (`latest_result`; UI extras: cards=True, chips=3)

> Your latest Glucose is 214.47 mg/dL. Latest blood report · 28 Sep 2026.

**New** (`blood_marker_explanation`, goal EXPLAIN, plain mode)

> [model answer] It discusses: Glucose, Triglycerides, HbA1c.

### What should I change first?

**Old** (`health_scenario`; UI extras: cards=True, chips=3)

> Most of your major health areas look reassuring, but the main pattern that stands out is Lipids. This is a reading of your records, not a diagnosis. The highest-yield next step is to review this lipids pattern with a clinician.

**New** (`health_scenario`, goal PRIORITIZE, plain mode)

> [model answer] It discusses: HbA1c, Triglycerides, MCH, Glucose.

### What is reassuring in my report?

**Old** (`broad_health_summary`; UI extras: cards=True, chips=1)

> Most of your major health areas look reassuring, but the main pattern that stands out is Lipids. This is a reading of your records, not a diagnosis. The highest-yield next step is to review this lipids pattern with a clinician.

**New** (`broad_health_summary`, goal EXPLAIN, plain mode)

> [model answer] It discusses: HbA1c, Glucose, Type 2 diabetes, Triglycerides.

### Do my blood report and Bio-AI report tell the same story?

**Old** (`health_scenario`; UI extras: cards=True, chips=3)

> Most of your major health areas look reassuring, but the main pattern that stands out is Lipids. This is a reading of your records, not a diagnosis. The highest-yield next step is to review this lipids pattern with a clinician.

**New** (`health_scenario`, goal EXPLAIN, plain mode)

> [model answer] It discusses: HbA1c, Glucose, Type 2 diabetes, Triglycerides.

### What changed compared with my previous report?

**Old** (`broad_health_summary`; UI extras: cards=True, chips=1)

> [model answer] It discusses: HbA1c, Glucose, Triglycerides. The highest-yield next step is to review this lipids pattern with a clinician.

**New** (`broad_health_summary`, goal COMPARE, plain mode)

> [model answer] It discusses: HbA1c, Glucose, Triglycerides, Type 2 diabetes.

### What should I focus on first?

**Old** (`health_scenario`; UI extras: cards=True, chips=3)

> Most of your major health areas look reassuring, but the main pattern that stands out is Lipids. This is a reading of your records, not a diagnosis. The highest-yield next step is to review this lipids pattern with a clinician.

**New** (`health_scenario`, goal PRIORITIZE, plain mode)

> [model answer] It discusses: HbA1c, Triglycerides, MCH, Glucose.

### Could my lifestyle be contributing?

**Old** (`health_scenario`; UI extras: cards=True, chips=3)

> [model answer] It discusses: HbA1c, LDL.

**New** (`health_scenario`, goal EXPLAIN, plain mode)

> [model answer] It discusses: HbA1c, LDL, Glucose, Type 2 diabetes.

### Which result needs the most attention?

**Old** (`health_scenario`; UI extras: cards=True, chips=3)

> Most of your major health areas look reassuring, but the main pattern that stands out is Lipids. This is a reading of your records, not a diagnosis. The highest-yield next step is to review this lipids pattern with a clinician.

**New** (`health_scenario`, goal PRIORITIZE, plain mode)

> [model answer] It discusses: HbA1c, Triglycerides, MCH, Glucose.

### Which abnormal values probably matter less?

**Old** (`latest_result`; UI extras: cards=True, chips=0)

> Results outside range Results outside range from your retrieved records. HBA1C: 9.1 % · high
> Glucose: 214.47 mg/dL · high
> Triglycerides: 266.0 mg/dL · high
> LDL Cholesterol: 162.0 mg/dL · high
> Cholesterol: 248.0 mg/dL · high
> Hemoglobin: 11.9 g/dL · low
> MCV: 76.0 fL · low
> MCH: 24.0 pg · low
> RDW: 15.8 % · high
> Ferritin: 12.0 ng/mL · low
> Vitamin D: 27.0 ng/mL · low Latest blood report

**New** (`latest_result`, goal PRIORITIZE, plain mode)

> [model answer] It discusses: HbA1c, Triglycerides, MCH, Glucose.

### What should I discuss with my doctor?

**Old** (`broad_health_summary`; UI extras: cards=True, chips=1)

> [model answer] It discusses: Type 2 diabetes, Dyslipidemia, Cardiac health, Fatty liver (NAFLD). The highest-yield next step is to review this lipids pattern with a clinician.

**New** (`broad_health_summary`, goal EXPLAIN, plain mode)

> [model answer] It discusses: Type 2 diabetes, Dyslipidemia, Cardiac health, Fatty liver (NAFLD).

### Why is my risk high even though some markers are normal?

**Old** (`bio_ai_score`; UI extras: cards=True, chips=1)

> [model answer] It discusses: Type 2 diabetes, Dyslipidemia, Cardiac health. requested score was not available in the retrieved report. These scores are from your Bio-AI assessment and are not a medical diagnosis.

**New** (`bio_ai_score`, goal CAUSES, plain mode)

> [model answer] It discusses: Type 2 diabetes, Dyslipidemia, Cardiac health.

### What is my HbA1c?

**Old** (`latest_result`; UI extras: cards=True, chips=1)

> Your latest HBA1C is 9.1 % (high). Latest blood report · 28 Sep 2026

**New** (`latest_result`, goal LOOKUP, plain mode)

> Your HbA1c is 9.1% on your report from 28 Sep 2026, which is above your report's range (4.0–5.6%).
