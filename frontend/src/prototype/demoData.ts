/** Synthetic companion data. Not loaded from the API and not a patient record. */

export const DEMO_LABEL = "Synthetic demo · not a patient record";

export type DemoMarker = {
  name: string;
  value: string;
  unit: string;
  status: "in range" | "above range";
  date: string;
  source: string;
  plain: string;
  detail: string;
};

export const markers: DemoMarker[] = [
  {
    name: "HbA1c",
    value: "5.4",
    unit: "%",
    status: "in range",
    date: "6 Sep 2026",
    source: "Latest blood report",
    plain: "This is an average of blood sugar over about three months. 5.4% sits inside the usual lab range on this report.",
    detail: "The report lists a reference range of 4.0–5.6%. This number describes a current measurement. It is not the same thing as a predicted diabetes risk score.",
  },
  {
    name: "Creatinine",
    value: "0.9",
    unit: "mg/dL",
    status: "in range",
    date: "6 Sep 2026",
    source: "Latest blood report",
    plain: "Creatinine is a kidney-related blood measurement. 0.9 mg/dL is inside the range printed on this report.",
    detail: "This demo does not treat creatinine as proof of an oxidative-stress estimate. The two come from different sources.",
  },
];

export const risks = [
  {
    name: "Type 2 diabetes risk",
    score: "72",
    band: "Higher estimate",
    date: "6 Sep 2026",
    plain: "This is a Bio-AI estimate, not a blood sugar result. A higher estimate can exist even when today’s HbA1c is in range, because the two answer different questions.",
    detail: "The estimate uses the model’s inputs for this demo profile. It does not diagnose diabetes and it does not replace the measured HbA1c of 5.4%.",
  },
  {
    name: "Oxidative stress",
    score: "41",
    band: "Moderate estimate",
    date: "6 Sep 2026",
    plain: "This card is a predictive estimate. The creatinine result does not, by itself, confirm or explain this score.",
    detail: "No clinically established link is claimed here between creatinine and this estimate.",
  },
];

export const hba1cHistory = [
  { date: "2026-03-02", value: 5.6 },
  { date: "2026-06-04", value: 5.5 },
  { date: "2026-09-06", value: 5.4 },
];

export const reportRows = [
  { name: "HbA1c", value: "5.4 %", flag: "In range" },
  { name: "Fasting glucose", value: "92 mg/dL", flag: "In range" },
  { name: "LDL cholesterol", value: "128 mg/dL", flag: "Above range" },
  { name: "Creatinine", value: "0.9 mg/dL", flag: "In range" },
];

export const meals = [
  { name: "Breakfast", kcal: 420 },
  { name: "Lunch", kcal: 610 },
  { name: "Snack", kcal: 180 },
  { name: "Dinner", kcal: 540 },
];

export const followups = [
  "What does an in-range HbA1c mean next to a higher diabetes estimate?",
  "Which results on the 6 Sep report are above range?",
  "How has HbA1c changed across these three demo reports?",
];
