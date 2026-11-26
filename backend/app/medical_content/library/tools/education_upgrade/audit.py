"""Content audit for revision 2.4: repetition, unexplained terms, generic advice, missing education fields.

Writes audit/education_audit_2_4.json and prints a summary. Findings are for human review; the
audit does not approve anything.

    python tools/education_upgrade/audit.py
"""

from __future__ import annotations

import collections
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEXT_FIELDS = ["short_description", "what_happens_inside_my_body", "why_this_test_matters", "why_it_matters", "result_explanations", "keeping_healthy",
               "lowering_risk", "everyday_support", "common_misconceptions", "reference_range_note", "when_to_seek_medical_advice", "clinical_limitations"]
# Technical words a lay reader may not know. Flagged when the same sentence gives no plain explanation.
JARGON = ["hepatic", "renal", "erythrocyte", "glomerular", "idiopathic", "aetiology", "etiology", "steatotic", "parvalbumin", "tropomyosin", "immunoassay",
          "lipoprotein", "haemolysis", "hemolysis", "cholestasis", "sensitisation", "androgen", "phytate", "myoglobin", "polycythaemia", "hypophosphatasia"]
EXPLAINERS = re.compile(r"\(|, a |, an |, the |, which |called |means |is a |are a |, often ")
GENERIC = ["eat a healthy diet", "live a healthy lifestyle", "exercise regularly", "stay healthy", "drink plenty of water"]


def load(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def sentences(row):
    for field in TEXT_FIELDS:
        v = row.get(field)
        vals = [x for xs in v.values() for x in (xs if isinstance(xs, list) else [xs])] if isinstance(v, dict) else (v if isinstance(v, list) else [v] if v else [])
        for line in vals:
            for s in re.split(r"(?<=[.!?])\s+", str(line)):
                if s.strip():
                    yield field, s.strip()
    for fx in row.get("factor_explanations") or []:
        yield "factor_explanations", fx["how_it_acts"]


def main():
    bio = load("content/biomarker_content.json")
    risks = load("content/bio_ai_content.json")
    cats = load("content/health_category_content.json")
    allergens = load("content/allergy_content.json")
    shared = {r["sentence"] for r in load("audit/shared_sentence_register.json")["sentences"]}
    rows = [("biomarker", r["content_key"], r) for r in bio] + [("bio_ai", r["risk_id"], r) for r in risks] + [("category", r["health_category"], r) for r in cats]

    use = collections.defaultdict(set)
    jargon, generic, dashes = [], [], []
    for table, key, row in rows:
        for field, s in sentences(row):
            use[s].add(key)
            low = s.lower()
            for term in JARGON:
                if re.search(rf"\b{term}", low) and not EXPLAINERS.search(s):
                    jargon.append({"id": key, "field": field, "term": term, "sentence": s})
            for g in GENERIC:
                if g in low:
                    generic.append({"id": key, "field": field, "phrase": g, "sentence": s})
            if re.search("[–—]", s):
                dashes.append({"id": key, "sentence": s})
    repeated = sorted(({"sentence": s, "entries": sorted(k)} for s, k in use.items() if len(k) > 3 and s not in shared), key=lambda x: -len(x["entries"]))

    missing = []
    for r in bio:
        na = r.get("not_applicable") or {}
        for field in ("factor_explanations", "keeping_healthy", "common_misconceptions"):
            if not r.get(field) and field.replace("common_", "") not in na and field not in na:
                missing.append({"id": r["content_key"], "field": field})
        if len(r.get("factor_explanations") or []) != len(r.get("possible_influencing_factors") or []):
            missing.append({"id": r["content_key"], "field": "factor_explanations does not cover every factor"})
    for r in risks:
        for field in ("factor_explanations", "keeping_healthy", "risk_meaning"):
            if not r.get(field):
                missing.append({"id": r["risk_id"], "field": field})
    for r in allergens:
        if not r.get("about_this_substance"):
            missing.append({"id": r["content_key"], "field": "about_this_substance"})
    allergen_about = collections.Counter(r.get("about_this_substance") for r in allergens)

    report = {
        "revision": "2.4",
        "entries_audited": {"biomarkers": len(bio), "bio_ai": len(risks), "categories": len(cats), "allergens": len(allergens)},
        "repeated_sentences_outside_register": repeated,
        "possible_unexplained_terms": jargon,
        "generic_lifestyle_phrases": generic,
        "dash_characters": dashes,
        "missing_education_fields": missing,
        "allergen_descriptions_shared_by_more_than_one_entry": [a for a, n in allergen_about.items() if n > 1],
        "note": "Heuristic audit for human review. Unexplained-term checks look for an explanation in the same sentence only.",
    }
    (ROOT / "audit/education_audit_2_4.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print({k: len(v) if isinstance(v, list) else v for k, v in report.items() if k != "note"})


if __name__ == "__main__":
    main()
