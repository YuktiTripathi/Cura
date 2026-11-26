"""Build the claim-level evidence map for revision 2.4 and register the source pages read for it.

Every reader-facing claim in the library gets one row: where it lives, what kind of claim it is, which
sources are candidates, and an honest status. A claim is marked `page_read_supports_claim` only when a
source page was opened and read during the 2.4 review and states it; everything else stays
`candidate_sources_unverified`. MetSights product information is marked separately. None of this is
clinical approval.

    python tools/education_upgrade/evidence_map.py
"""

from __future__ import annotations

import collections
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
READ = "opened_and_read_2026-11-26; supports the claims mapped to it in evidence/claim_evidence_map.json; not clinical approval"

SOURCES = {
    "niddk_a1c_test": ("NIDDK: The A1C test and diabetes", "https://www.niddk.nih.gov/health-information/diagnostic-tests/a1c-test"),
    "niddk_diabetes_tests": ("NIDDK: Diabetes tests and diagnosis", "https://www.niddk.nih.gov/health-information/diabetes/overview/tests-diagnosis"),
    "niddk_insulin_resistance": ("NIDDK: Insulin resistance and prediabetes", "https://www.niddk.nih.gov/health-information/diabetes/overview/what-is-diabetes/prediabetes-insulin-resistance"),
    "cdc_activity_diabetes": ("CDC: Physical activity and diabetes", "https://www.cdc.gov/diabetes/living-with/physical-activity.html"),
    "niddk_ckd_tests": ("NIDDK: Tests and diagnosis of chronic kidney disease", "https://www.niddk.nih.gov/health-information/kidney-disease/chronic-kidney-disease-ckd/tests-diagnosis"),
    "niddk_nafld_treatment": ("NIDDK: Treatment for NAFLD and NASH", "https://www.niddk.nih.gov/health-information/liver-disease/nafld-nash/treatment"),
    "niddk_nafld_diet": ("NIDDK: Eating, diet and nutrition for NAFLD and NASH", "https://www.niddk.nih.gov/health-information/liver-disease/nafld-nash/eating-diet-nutrition"),
    "mlp_alp_ency": ("MedlinePlus: ALP blood test", "https://medlineplus.gov/ency/article/003470.htm"),
    "mlp_osteomalacia": ("MedlinePlus: Osteomalacia", "https://medlineplus.gov/ency/article/000376.htm"),
    "mlp_esr_ency": ("MedlinePlus: Sed rate (ESR)", "https://medlineplus.gov/ency/article/003638.htm"),
    "mlp_triglycerides": ("MedlinePlus: Triglycerides test", "https://medlineplus.gov/lab-tests/triglycerides-test/"),
    "mlp_vitd_test": ("MedlinePlus: Vitamin D test", "https://medlineplus.gov/lab-tests/vitamin-d-test/"),
    "harvard_bilirubin": ("Harvard Health: What does a high bilirubin level mean?", "https://www.health.harvard.edu/digestive-health/what-does-a-high-bilirubin-level-in-my-blood-test-actually-mean"),
    "ods_b12_hp": ("NIH ODS: Vitamin B12 fact sheet for health professionals", "https://ods.od.nih.gov/factsheets/VitaminB12-HealthProfessional/"),
    "ods_b12_consumer": ("NIH ODS: Vitamin B12 fact sheet for consumers", "https://ods.od.nih.gov/factsheets/VitaminB12-Consumer/"),
    "livertox_hds": ("LiverTox: Herbal and dietary supplements", "https://www.ncbi.nlm.nih.gov/books/NBK548441/"),
    "mayo_hdl": ("Mayo Clinic: HDL cholesterol", "https://www.mayoclinic.org/diseases-conditions/high-blood-cholesterol/in-depth/hdl-cholesterol/art-20046388"),
    "medlineplus_hdl": ("MedlinePlus: HDL, the good cholesterol", "https://medlineplus.gov/hdlthegoodcholesterol.html"),
    "nccih_antioxidants": ("NCCIH: Antioxidant supplements, what you need to know", "https://www.nccih.nih.gov/health/antioxidant-supplements-what-you-need-to-know"),
    "cdc_lpa": ("CDC: Lipoprotein (a)", "https://cdc.gov/heart-disease-family-history/about/about-lipoprotein-a.html"),
    "aha_lpa": ("American Heart Association: Lipoprotein (a)", "https://www.heart.org/en/health-topics/cholesterol/genetic-conditions/lipoprotein-a"),
    "hsa_biotin_thyroid": ("Health Sciences Authority Singapore: Biotin interference with thyroid function tests", "https://www.hsa.gov.sg/announcements/biotin-interference-with-thyroid-function-tests/"),
    "health_canada_biotin": ("Health Canada: Biotin and the risk of false lab test results", "https://www.canada.ca/en/health-canada/services/drugs-health-products/medical-devices/biotin-risk-false-lab-test-results.html"),
    "pmc_nafld_normal_enzymes": ("Normal liver enzymes in NAFLD (PMC11299156)", "https://pmc.ncbi.nlm.nih.gov/articles/PMC11299156"),
    "pubmed_nafld_india": ("NAFLD prevalence in India, meta-analysis (PubMed 35677499)", "https://pubmed.ncbi.nlm.nih.gov/35677499"),
    "pmc_lean_nafld_south_asia": ("Non-obese NAFLD in South Asia (PMC10442973)", "https://pmc.ncbi.nlm.nih.gov/articles/PMC10442973"),
    "mlp_cholesterol_levels": ("MedlinePlus: Cholesterol levels", "https://medlineplus.gov/lab-tests/cholesterol-levels/"),
    "mlp_ferritin_test": ("MedlinePlus: Ferritin blood test", "https://medlineplus.gov/lab-tests/ferritin-blood-test/"),
    "mlp_allergy_blood": ("MedlinePlus: Allergy blood test", "https://medlineplus.gov/lab-tests/allergy-blood-test/"),
    "mlp_beta_thalassemia": ("MedlinePlus Genetics: Beta thalassemia", "https://medlineplus.gov/genetics/condition/beta-thalassemia/"),
    "niddk_nafld_definition": ("NIDDK: Definition and facts of NAFLD and NASH", "https://www.niddk.nih.gov/health-information/liver-disease/nafld-nash/definition-facts"),
    "mlp_potassium_test": ("MedlinePlus: Potassium blood test", "https://medlineplus.gov/lab-tests/potassium-blood-test/"),
    "mlp_creatinine_test": ("MedlinePlus: Creatinine test", "https://medlineplus.gov/lab-tests/creatinine-test/"),
    "mlp_alt_test": ("MedlinePlus: ALT blood test", "https://medlineplus.gov/lab-tests/alt-blood-test/"),
    "mlp_ast_test": ("MedlinePlus: AST test", "https://medlineplus.gov/lab-tests/ast-test/"),
    "mlp_bun_test": ("MedlinePlus: BUN (blood urea nitrogen)", "https://medlineplus.gov/lab-tests/bun-blood-urea-nitrogen/"),
    "mlp_hemoglobin_test": ("MedlinePlus: Hemoglobin test", "https://medlineplus.gov/lab-tests/hemoglobin-test/"),
    "mlp_albumin_test": ("MedlinePlus: Albumin blood test", "https://medlineplus.gov/lab-tests/albumin-blood-test/"),
    "mlp_ggt_test": ("MedlinePlus: Gamma-glutamyl transferase (GGT) test", "https://medlineplus.gov/lab-tests/gamma-glutamyl-transferase-ggt-test/"),
}
# Proposed in 2.3.1 and now opened and read.
NOW_READ = {"ods_vitd": "NIH ODS: vitamin D consumer fact sheet", "mlp_ck": "MedlinePlus: creatine kinase", "mlp_crp": "MedlinePlus: C-reactive protein (CRP) test",
            "mlp_tsh": "MedlinePlus: TSH test", "mlp_anaphylaxis": "MedlinePlus: anaphylaxis", "mlp_uric": "MedlinePlus: uric acid test",
            "mlp_homocysteine": "MedlinePlus: homocysteine test"}

# (content key or risk/category id, field, substring of the claim, source ids). Only claims checked against a page read in the 2.4 review.
VERIFIED = [
    ("WB-068", "factor_explanations", "Very low iron can make HbA1c read falsely high", ["niddk_a1c_test"]),
    ("WB-068", "factor_explanations", "Kidney failure can make HbA1c", ["niddk_a1c_test"]),
    ("WB-068", "clinical_limitations", "Very low iron can make HbA1c read falsely high", ["niddk_a1c_test"]),
    ("WB-068", "reference_range_note", "5.7 to 6.4%", ["niddk_diabetes_tests"]),
    ("WB-067", "reference_range_note", "100 to 125 mg/dL", ["niddk_diabetes_tests"]),
    ("WB-067", "result_explanations", "does not rule out diabetes on its own", ["niddk_diabetes_tests"]),
    ("WB-068", "result_explanations", "does not rule out diabetes on its own", ["niddk_diabetes_tests"]),
    ("*", "everyday_support", "Physical activity helps your body manage blood sugar", ["cdc_activity_diabetes"]),
    ("*", "everyday_support", "may help prevent insulin resistance", ["niddk_insulin_resistance"]),
    ("*", "factor_explanations", "may help prevent insulin resistance", ["niddk_insulin_resistance"]),
    ("*", "factor_explanations", "Not being active is a risk factor for insulin resistance", ["niddk_insulin_resistance"]),
    ("WB-031", "reference_range_note", "below 60 may mean kidney disease", ["niddk_ckd_tests"]),
    ("WB-011", "factor_explanations", "ALP is normally higher during pregnancy", ["mlp_alp_ency"]),
    ("WB-011", "factor_explanations", "osteomalacia", ["mlp_alp_ency", "mlp_osteomalacia"]),
    ("WB-011", "result_explanations", "hypophosphatasia", ["mlp_alp_ency"]),
    ("WB-011", "what_happens_inside_my_body", "normally higher during pregnancy", ["mlp_alp_ency"]),
    ("WB-013", "factor_explanations", "It is not dangerous", ["harvard_bilirubin"]),
    ("WB-013", "result_explanations", "Gilbert syndrome", ["harvard_bilirubin"]),
    ("WB-018", "factor_explanations", "Gilbert syndrome", ["harvard_bilirubin"]),
    ("WB-036", "what_happens_inside_my_body", "Fortified foods", ["ods_b12_consumer"]),
    ("WB-036", "factor_explanations", "B12 occurs naturally only in animal foods", ["ods_b12_consumer"]),
    ("WB-036", "factor_explanations", "Metformin", ["ods_b12_consumer"]),
    ("WB-036", "result_explanations", "not known to be harmful", ["ods_b12_consumer"]),
    ("WB-036", "common_misconceptions", "red cells become large", ["ods_b12_hp"]),
    ("*", "keeping_healthy", "Some herbal and dietary supplements can injure the liver", ["livertox_hds"]),
    ("*", "factor_explanations", "herbal or dietary supplements can injure liver cells", ["livertox_hds"]),
    ("WB-002", "common_misconceptions", "Raising HDL with medicines has not lowered heart attacks", ["mayo_hdl"]),
    ("WB-002", "keeping_healthy", "no reason to start to raise HDL", ["mayo_hdl"]),
    ("WB-002", "reference_range_note", "above 40 mg/dL for men and above 50 mg/dL for women", ["medlineplus_hdl"]),
    ("WB-002", "result_explanations", "above about 100 mg/dL", ["mayo_hdl"]),
    ("WB-047", "factor_explanations", "", ["mlp_esr_ency"]),
    ("WB-094", "factor_explanations", "", ["mlp_esr_ency"]),
    ("WB-047", "result_explanations", "thyroid disease", ["mlp_esr_ency"]),
    ("WB-094", "result_explanations", "thyroid disease", ["mlp_esr_ency"]),
    ("WB-047", "result_explanations", "polycythaemia", ["mlp_esr_ency"]),
    ("WB-094", "result_explanations", "polycythaemia", ["mlp_esr_ency"]),
    ("WB-003", "lowering_risk", "500 mg/dL", ["mlp_triglycerides"]),
    ("WB-003", "factor_explanations", "fast for 9 to 12 hours", ["mlp_triglycerides"]),
    ("WB-037", "reference_range_note", "20 ng/mL or above as adequate", ["ods_vitd"]),
    ("WB-037", "common_misconceptions", "above 50 ng/mL as too high", ["ods_vitd"]),
    ("WB-037", "result_explanations", "above 50 ng/mL as too high", ["ods_vitd"]),
    ("WB-037", "factor_explanations", "Darker skin makes vitamin D more slowly", ["ods_vitd"]),
    ("WB-037", "factor_explanations", "people with more body fat", ["ods_vitd"]),
    ("WB-110", "factor_explanations", "Lp(a) is set mostly by genes", ["cdc_lpa", "aha_lpa"]),
    ("WB-110", "lowering_risk", "Diet and exercise do not change Lp(a) much", ["cdc_lpa", "aha_lpa"]),
    ("WB-110", "reference_range_note", "above 50 mg/dL or 125 nmol/L", ["cdc_lpa"]),
    ("WB-040", "factor_explanations", "biotin", ["hsa_biotin_thyroid", "health_canada_biotin"]),
    ("WB-041", "factor_explanations", "Biotin can interfere", ["hsa_biotin_thyroid", "health_canada_biotin"]),
    ("WB-117", "factor_explanations", "Statins can occasionally irritate muscles", ["mlp_ck"]),
    ("WB-117", "factor_explanations", "Hard or unaccustomed exercise", ["mlp_ck"]),
    ("WB-093", "factor_explanations", "Any infection, even a cold", ["mlp_crp"]),
    ("nafld", "everyday_support", "Losing 3 to 5% of body weight", ["niddk_nafld_treatment"]),
    ("nafld", "everyday_support", "Activity helps the liver even when weight does not change", ["niddk_nafld_treatment"]),
    ("nafld", "everyday_support", "NIDDK advises limiting simple sugars", ["niddk_nafld_diet"]),
    ("*", "lowering_risk", "Losing 3 to 5% of body weight can reduce liver fat", ["niddk_nafld_treatment"]),
    ("*", "lowering_risk", "About one in three Indian adults has fat in the liver", ["pubmed_nafld_india", "pmc_lean_nafld_south_asia"]),
    ("*", "common_misconceptions", "Normal liver enzymes do not rule out fatty liver", ["pmc_nafld_normal_enzymes"]),
    ("oxidative_stress", "common_misconceptions", "beta-carotene", ["nccih_antioxidants"]),
    # Batch 2 (pages read 27 Nov 2026)
    ("*", "reference_range_note", "depends on your overall heart risk", ["mlp_cholesterol_levels"]),
    ("WB-041", "reference_range_note", "often a little low in the first three months of pregnancy", ["mlp_tsh"]),
    ("WB-041", "factor_explanations", "often a little low during the first three months of pregnancy", ["mlp_tsh"]),
    ("WB-041", "factor_explanations", "When the thyroid is underactive, TSH rises", ["mlp_tsh"]),
    ("WB-041", "result_explanations", "thyroid is underactive", ["mlp_tsh"]),
    ("WB-041", "result_explanations", "thyroid is overactive", ["mlp_tsh"]),
    ("WB-116", "common_misconceptions", "Inflammation, liver disease, obesity and alcohol can also raise it", ["mlp_ferritin_test"]),
    ("WB-116", "factor_explanations", "Ferritin rises during inflammation", ["mlp_ferritin_test"]),
    ("WB-116", "factor_explanations", "Fatty liver and other liver strain raise ferritin", ["mlp_ferritin_test"]),
    ("WB-116", "factor_explanations", "Regular drinking raises ferritin", ["mlp_ferritin_test"]),
    ("WB-116", "result_explanations", "iron stores are low", ["mlp_ferritin_test"]),
    ("*", "clinical_limitations", "An allergy antibody test cannot confirm an allergy on its own or predict how severe a reaction might be", ["mlp_allergy_blood"]),
    ("*", "when_to_seek_medical_advice", "swelling of the face, eyes or tongue, a hoarse or whispered voice", ["mlp_anaphylaxis"]),
    ("WB-048", "factor_explanations", "Thalassaemia trait, common in India, can give a mildly low haemoglobin", ["mlp_beta_thalassemia"]),
    ("nafld", "what_happens_inside_my_body", "not caused by heavy alcohol use", ["niddk_nafld_definition"]),
    ("nafld", "short_description", "replaced the older name NAFLD", ["niddk_nafld_definition"]),
    ("WB-033", "factor_explanations", "Clenching your fist hard during the blood draw", ["mlp_potassium_test"]),
    ("WB-033", "factor_explanations", "Fluid loss from the gut can lower potassium", ["mlp_potassium_test"]),
    ("WB-033", "factor_explanations", "Some medicines and supplements raise potassium", ["mlp_potassium_test"]),
    ("WB-028", "factor_explanations", "Purines in red meat, organ meat and some seafood", ["mlp_uric"]),
    ("WB-028", "factor_explanations", "Fructose in sugary drinks", ["mlp_uric"]),
    ("WB-028", "factor_explanations", "Alcohol makes the body produce more uric acid", ["mlp_uric"]),
    ("WB-028", "common_misconceptions", "many people with high levels have no health problems", ["mlp_uric"]),
    ("WB-025", "factor_explanations", "Creatinine comes from normal muscle wear", ["mlp_creatinine_test"]),
    ("WB-025", "factor_explanations", "Cooked meat contains creatine", ["mlp_creatinine_test"]),
    ("WB-025", "factor_explanations", "Some medicines stop the kidneys", ["mlp_creatinine_test"]),
    ("WB-025", "factor_explanations", "Being short of water", ["mlp_creatinine_test"]),
    ("WB-014", "factor_explanations", "Regular drinking makes liver cells produce more GGT", ["mlp_ggt_test"]),
    ("WB-014", "factor_explanations", "GGT sits in the cells lining the bile ducts", ["mlp_ggt_test"]),
    ("WB-014", "common_misconceptions", "GGT is not only an alcohol test", ["mlp_ggt_test"]),
    ("WB-092", "common_misconceptions", "Lowering homocysteine has not been shown to reduce the risk", ["mlp_homocysteine"]),
    ("WB-092", "factor_explanations", "The body needs B12 and folate to break down homocysteine", ["mlp_homocysteine"]),
    ("WB-092", "factor_explanations", "The kidneys clear homocysteine", ["mlp_homocysteine"]),
]
VERIFIED += [
    # Batch 3
    ("WB-017", "factor_explanations", "Hepatitis B and C infect liver cells", ["mlp_alt_test"]),
    ("WB-016", "clinical_limitations", "AST is not specific to the liver", ["mlp_ast_test"]),
    ("WB-016", "factor_explanations", "Hard workouts strain muscles, which also contain AST", ["mlp_ast_test"]),
    ("WB-022", "factor_explanations", "Being short of water", ["mlp_bun_test"]),
    ("WB-022", "factor_explanations", "a high-protein diet raises it a little", ["mlp_bun_test"]),
    ("WB-022", "factor_explanations", "The liver makes urea, so severe liver disease can lower BUN", ["mlp_bun_test"]),
    ("WB-022", "factor_explanations", "Healthy kidneys keep this level steady", ["mlp_bun_test"]),
    ("WB-048", "factor_explanations", "Losing blood, often slowly through heavy periods", ["mlp_hemoglobin_test"]),
    ("WB-048", "factor_explanations", "Dehydration concentrates the blood and makes haemoglobin read higher", ["mlp_hemoglobin_test"]),
    ("WB-048", "factor_explanations", "Carbon monoxide from smoke", ["mlp_hemoglobin_test"]),
    ("WB-048", "factor_explanations", "Living high up, where air has less oxygen", ["mlp_hemoglobin_test"]),
    ("WB-048", "result_explanations", "lung conditions", ["mlp_hemoglobin_test"]),
    ("WB-010", "factor_explanations", "Albumin is made only in the liver", ["mlp_albumin_test"]),
    ("WB-010", "factor_explanations", "Damaged kidney filters can leak albumin", ["mlp_albumin_test"]),
    ("WB-010", "factor_explanations", "When you are short of water the blood is more concentrated", ["mlp_albumin_test"]),
    ("WB-010", "factor_explanations", "Very low protein intake", ["mlp_albumin_test"]),
    ("WB-010", "result_explanations", "dehydrated", ["mlp_albumin_test"]),
]
# Relationship readings checked against a page read in the review: (pair id, source ids).
VERIFIED_PAIRS = {
    "WB-011|WB-014": ["mlp_ggt_test"],
    "WB-012|WB-018": ["harvard_bilirubin"],
    "WB-013|WB-018": ["harvard_bilirubin"],
    "WB-036|WB-092": ["mlp_homocysteine"],
    "WB-093|WB-116": ["mlp_ferritin_test"],
    "WB-040|WB-041": ["mlp_tsh"],
}

FIELD_TYPE = {
    "short_description": "biological_mechanism", "what_happens_inside_my_body": "biological_mechanism", "why_this_test_matters": "interpretation",
    "why_it_matters": "interpretation", "result_explanations": "interpretation", "conditional_result_explanations": "interpretation",
    "factor_explanations": "influencing_factor", "reference_range_note": "threshold", "common_misconceptions": "interpretation",
    "clinical_limitations": "interpretation", "keeping_healthy": "prevention", "lowering_risk": "prevention", "everyday_support": "practical_guidance",
    "diet_and_lifestyle": "practical_guidance", "when_to_seek_medical_advice": "medical_escalation", "risk_meaning": "interpretation",
    "long_term_implications": "interpretation", "common_symptoms": "interpretation", "about_this_substance": "background", "cross_reactivity": "interpretation",
    "severity_note": "medical_escalation", "user_explanation": "relationship", "reading_together": "relationship", "product_inputs": "product_information",
}


def load(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def dump(rel, data):
    (ROOT / rel).write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def claims(row, key):
    for field, kind in FIELD_TYPE.items():
        value = row.get(field)
        if value is None:
            continue
        if field == "factor_explanations":
            for x in value:
                yield field, kind, f"{x['factor']}: {x['how_it_acts']}"
        elif isinstance(value, dict):
            for state, lines in value.items():
                for line in lines if isinstance(lines, list) else [lines]:
                    if isinstance(line, dict):
                        for sub in line.values():
                            for s in sub if isinstance(sub, list) else [sub]:
                                yield field, kind, str(s)
                    else:
                        yield field, kind, str(line)
        else:
            for line in value if isinstance(value, list) else [value]:
                yield field, kind, str(line)


def main():
    sources = load("evidence/content_sources.json")
    have = {s["source_id"]: s for s in sources}
    for sid, (title, url) in SOURCES.items():
        if sid in have:
            have[sid]["verification"] = READ
        else:
            sources.append({"source_id": sid, "title": title, "url": url, "verification": READ})
    for sid in NOW_READ:
        if sid in have:
            have[sid]["verification"] = READ
    dump("evidence/content_sources.json", sources)

    tables = [
        ("biomarker", "content_key", load("content/biomarker_content.json")),
        ("allergen", "content_key", load("content/allergy_content.json")),
        ("bio_ai", "risk_id", load("content/bio_ai_content.json")),
        ("health_category", "health_category", load("content/health_category_content.json")),
    ]
    rel = load("relationships/biomarker_relationships.json")
    life = load("relationships/lifestyle_relationships.json")
    rows, used = [], collections.Counter()
    for table, idf, items in tables:
        for row in items:
            key = row[idf]
            for field, kind, text in claims(row, key):
                status, sids = "candidate_sources_unverified", list(row.get("source_ids") or [])
                if kind == "product_information":
                    status = "metsights_product_information_not_medical_evidence"
                for i, (vk, vf, sub, vs) in enumerate(VERIFIED):
                    if vk in (key, "*") and vf == field and sub in text:
                        status, sids = "page_read_supports_claim", vs
                        used[i] += 1
                        break
                rows.append({"table": table, "id": key, "field": field, "claim_type": kind, "claim": text, "source_ids": sids, "status": status})
    for r in rel:
        pair = "|".join(sorted((r["source_content_key"], r["related_content_key"])))
        for field in ("user_explanation", "reading_together"):
            if r.get(field):
                ok = field == "reading_together" and pair in VERIFIED_PAIRS
                rows.append({"table": "biomarker_relationship", "id": f"{r['source_content_key']}>{r['related_content_key']}", "field": field, "claim_type": "relationship",
                             "claim": r[field], "source_ids": VERIFIED_PAIRS[pair] if ok else (r.get("source_ids") or []),
                             "status": "page_read_supports_claim" if ok else "candidate_sources_unverified"})
    for r in life:
        rows.append({"table": "lifestyle_relationship", "id": r["relationship_id"], "field": "user_explanation", "claim_type": "relationship",
                     "claim": r["user_explanation"], "source_ids": r.get("source_ids") or [], "status": "candidate_sources_unverified"})
    unused = [VERIFIED[i][:3] for i in range(len(VERIFIED)) if not used[i]]
    if unused:
        raise SystemExit(f"verified claims that no longer match library text: {unused}")
    known = {s["source_id"] for s in sources}
    missing = sorted({s for r in rows for s in r["source_ids"]} - known)
    if missing:
        raise SystemExit(f"unknown source ids {missing}")
    summary = collections.Counter(r["status"] for r in rows)
    by_type = collections.Counter((r["claim_type"], r["status"]) for r in rows)
    dump("evidence/claim_evidence_map.json", {
        "revision": "2.4",
        "note": "One row per reader-facing claim. page_read_supports_claim means a source page was opened, read and states the claim; it is not clinical approval. Every row remains pending clinical review.",
        "summary": dict(summary),
        "by_claim_type": {f"{k[0]}|{k[1]}": v for k, v in sorted(by_type.items())},
        "claims": rows,
    })
    print(dict(summary), len(rows))


if __name__ == "__main__":
    main()
