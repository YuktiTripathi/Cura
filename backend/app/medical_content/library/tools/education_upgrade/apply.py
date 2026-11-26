"""Apply the education upgrade (revision 2.4) to the authoritative Medical Knowledge Library V2.3 files.

Base text comes from the revision 2.3.1 modules in this folder; the *_x modules add factor explanations,
health maintenance, modifiable risk, misconceptions, reference range notes and the corrections from the
sample review. Nothing here creates a second library: it rewrites the existing V2.3 files in place.

Preserves every identifier, provider mapping, relationship, result state and source id already in the
library. Rewrites the reader-facing text, adds the new fields, and records non-applicable fields with a
reason. Every entry stays pending clinical review.

    python tools/education_upgrade/apply.py
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

REVISION = "2.4"
BASELINE_COMMIT = "a61785d"  # main before the education upgrade
MODULES = ["heart", "liver", "kidney", "vitamins_thyroid", "blood", "sugar_inflammation", "urine", "hormones_cancer"]

PROPOSED = "proposed_2026-11-26_not_opened; URL and claim-level support require verification before clinical approval"
NEW_SOURCES = {
    "mlp_egfr": ("MedlinePlus: glomerular filtration rate (GFR) test", "https://medlineplus.gov/lab-tests/glomerular-filtration-rate-gfr-test/"),
    "mlp_uric": ("MedlinePlus: uric acid test", "https://medlineplus.gov/lab-tests/uric-acid-test/"),
    "mlp_electrolytes": ("MedlinePlus: electrolyte panel", "https://medlineplus.gov/lab-tests/electrolyte-panel/"),
    "mlp_calcium": ("MedlinePlus: calcium blood test", "https://medlineplus.gov/lab-tests/calcium-blood-test/"),
    "mlp_phosphate": ("MedlinePlus: phosphate in blood", "https://medlineplus.gov/lab-tests/phosphate-in-blood/"),
    "ods_magnesium": ("NIH Office of Dietary Supplements: magnesium consumer fact sheet", "https://ods.od.nih.gov/factsheets/Magnesium-Consumer/"),
    "ods_zinc": ("NIH Office of Dietary Supplements: zinc consumer fact sheet", "https://ods.od.nih.gov/factsheets/Zinc-Consumer/"),
    "ods_vitd": ("NIH Office of Dietary Supplements: vitamin D consumer fact sheet", "https://ods.od.nih.gov/factsheets/VitaminD-Consumer/"),
    "mlp_tsh": ("MedlinePlus: TSH (thyroid-stimulating hormone) test", "https://medlineplus.gov/lab-tests/tsh-thyroid-stimulating-hormone-test/"),
    "niddk_hypothyroid": ("NIDDK: hypothyroidism (underactive thyroid)", "https://www.niddk.nih.gov/health-information/endocrine-diseases/hypothyroidism"),
    "niddk_hyperthyroid": ("NIDDK: hyperthyroidism (overactive thyroid)", "https://www.niddk.nih.gov/health-information/endocrine-diseases/hyperthyroidism"),
    "niddk_nafld": ("NIDDK: NAFLD and NASH", "https://www.niddk.nih.gov/health-information/liver-disease/nafld-nash"),
    "mlp_esr": ("MedlinePlus: erythrocyte sedimentation rate (ESR)", "https://medlineplus.gov/lab-tests/erythrocyte-sedimentation-rate-esr/"),
    "mlp_crp": ("MedlinePlus: C-reactive protein (CRP) test", "https://medlineplus.gov/lab-tests/c-reactive-protein-crp-test/"),
    "mlp_homocysteine": ("MedlinePlus: homocysteine test", "https://medlineplus.gov/lab-tests/homocysteine-test/"),
    "mlp_insulin": ("MedlinePlus: insulin in blood", "https://medlineplus.gov/lab-tests/insulin-in-blood/"),
    "mlp_urinalysis": ("MedlinePlus: urinalysis", "https://medlineplus.gov/lab-tests/urinalysis/"),
    "mlp_testosterone": ("MedlinePlus: testosterone levels test", "https://medlineplus.gov/lab-tests/testosterone-levels-test/"),
    "mlp_cortisol": ("MedlinePlus: cortisol test", "https://medlineplus.gov/lab-tests/cortisol-test/"),
    "mlp_pth": ("MedlinePlus: parathyroid hormone (PTH) blood test", "https://medlineplus.gov/lab-tests/parathyroid-hormone-pth-blood-test/"),
    "mlp_prolactin": ("MedlinePlus: prolactin levels", "https://medlineplus.gov/lab-tests/prolactin-levels/"),
    "mlp_lh": ("MedlinePlus: luteinizing hormone (LH) levels test", "https://medlineplus.gov/lab-tests/luteinizing-hormone-lh-levels-test/"),
    "mlp_fsh": ("MedlinePlus: follicle-stimulating hormone (FSH) levels test", "https://medlineplus.gov/lab-tests/follicle-stimulating-hormone-fsh-levels-test/"),
    "mlp_dheas": ("MedlinePlus: DHEA sulfate test", "https://medlineplus.gov/lab-tests/dhea-sulfate-test/"),
    "mlp_cea": ("MedlinePlus: carcinoembryonic antigen (CEA) test", "https://medlineplus.gov/lab-tests/carcinoembryonic-antigen-cea-test/"),
    "mlp_ca125": ("MedlinePlus: CA-125 blood test", "https://medlineplus.gov/lab-tests/ca-125-blood-test/"),
    "mlp_ck": ("MedlinePlus: creatine kinase", "https://medlineplus.gov/lab-tests/creatine-kinase/"),
    "mlp_ldh": ("MedlinePlus: lactate dehydrogenase (LDH) test", "https://medlineplus.gov/lab-tests/lactate-dehydrogenase-ldh-test/"),
    "mlp_anaphylaxis": ("MedlinePlus: anaphylaxis", "https://medlineplus.gov/ency/article/000844.htm"),
    "who_cvd": ("WHO fact sheet: cardiovascular diseases", "https://www.who.int/news-room/fact-sheets/detail/cardiovascular-diseases-(cvds)"),
    "who_hypertension": ("WHO fact sheet: hypertension", "https://www.who.int/news-room/fact-sheets/detail/hypertension"),
    "who_diabetes": ("WHO fact sheet: diabetes", "https://www.who.int/news-room/fact-sheets/detail/diabetes"),
    "who_obesity": ("WHO fact sheet: obesity and overweight", "https://www.who.int/news-room/fact-sheets/detail/obesity-and-overweight"),
}

EXTRA_SOURCES = {
    **{k: ["lipids", "life_fat", "life_diet", "life_activity"] for k in ["WB-001", "WB-002", "WB-003", "WB-004", "WB-006", "WB-007", "WB-111"]},
    **{k: ["lipids"] for k in ["WB-005", "WB-008", "WB-009", "WB-110"]},
    **{k: ["liver", "life_liver"] for k in ["WB-014", "WB-016", "WB-017"]},
    "WB-012": ["bilirubin"], "WB-013": ["bilirubin"], "WB-018": ["bilirubin"],
    **{k: ["cmp"] for k in ["WB-010", "WB-015", "WB-019", "WB-020", "WB-022", "WB-027", "WB-029", "WB-030"]},
    "WB-023": ["cmp", "mlp_calcium"], "WB-103": ["mlp_calcium"], "WB-024": ["mlp_electrolytes"], "WB-026": ["mlp_electrolytes", "life_salt"],
    "WB-033": ["mlp_electrolytes"], "WB-025": ["creatinine"], "WB-031": ["creatinine", "mlp_egfr"], "WB-028": ["mlp_uric"],
    "WB-032": ["mlp_phosphate"], "WB-034": ["ods_magnesium"], "WB-035": ["ods_zinc"], "WB-036": ["life_b12"], "WB-037": ["ods_vitd"],
    "WB-038": ["life_c"], **{k: ["mlp_tsh", "niddk_hypothyroid"] for k in ["WB-039", "WB-040", "WB-041"]},
    **{k: ["cbc", "differential"] for k in ["WB-042", "WB-043", "WB-044", "WB-045", "WB-046", "WB-055", "WB-057", "WB-058", "WB-059", "WB-060", "WB-061"]},
    **{k: ["cbc", "rbc_indices"] for k in ["WB-049", "WB-050", "WB-051", "WB-052", "WB-053", "WB-056", "WB-062", "WB-063", "WB-064", "WB-065", "WB-066"]},
    "WB-048": ["hb", "life_iron"], "WB-054": ["cbc"], "WB-047": ["mlp_esr"], "WB-094": ["mlp_esr"],
    **{k: ["iron_tests", "life_iron"] for k in ["WB-112", "WB-113", "WB-114", "WB-115"]}, "WB-116": ["ferritin", "life_iron"],
    "WB-067": ["glucose", "life_glucose"], "WB-068": ["a1c", "life_glucose"], "WB-069": ["mlp_insulin", "life_glucose"], "WB-070": ["a1c"],
    **{f"WB-0{n}": ["mlp_urinalysis"] for n in range(71, 92)}, "WB-089": ["mlp_urinalysis", "life_urine"],
    "WB-092": ["mlp_homocysteine", "life_b12"], "WB-093": ["mlp_crp"], "WB-095": ["mlp_testosterone"], "WB-096": ["mlp_dheas"],
    "WB-098": ["mlp_cortisol"], "WB-099": ["mlp_pth"], "WB-100": ["mlp_prolactin"], "WB-101": ["mlp_lh"], "WB-102": ["mlp_fsh"],
    "WB-104": ["tumor", "psa_test"], "WB-105": ["tumor", "mlp_cea"], "WB-106": ["afp_test"], "WB-107": ["tumor"], "WB-108": ["tumor", "mlp_ca125"], "WB-109": ["tumor"],
    "WB-117": ["mlp_ck"], "WB-118": ["mlp_ldh"], "WB-330": ["allergy", "mlp_anaphylaxis"],
}


# Well-established companion results, added where the entry had none. Pending clinical review like the rest.
RELATED_ADD = {
    "WB-024": ["sodium", "potassium"], "WB-026": ["chlorides", "potassium"], "WB-028": ["creatinine"],
    "WB-073": ["urine_specific_gravity", "urine_bile_pigments"], "WB-074": ["urine_crystals", "urine_pus_cells", "urine_bacteria"],
    "WB-081": ["urine_urine_protein", "urine_rbc"], "WB-083": ["urine_sugar"], "WB-084": ["urine_leukocyte_esterase", "urine_bacteria"],
    "WB-096": ["total_testosterone"], "WB-330": ["absolute_eosinophils_count"],
}
RELATED_NA = {
    "WB-035": "No routine result on these panels is read alongside zinc.",
    "WB-038": "No routine result on these panels is read alongside vitamin C.",
    "WB-079": "Sample-quality finding; it is not read against other results.",
    "WB-090": "Describes the sample, not the body.",
    "WB-091": "Free-text lab notes; companions depend on what is written.",
    "WB-097": "Growth hormone itself is not on these panels.",
    "WB-098": "The tests read with cortisol are timed or dynamic tests not on these panels.",
    "WB-104": "No other prostate test is on these panels.",
    "WB-105": "Tumour markers are read with imaging and history, not with other panel results.",
    "WB-106": "Specimen unconfirmed; no companion result can be named.",
    "WB-108": "Tumour markers are read with imaging and history, not with other panel results.",
    "WB-109": "Tumour markers are read with imaging and history, not with other panel results.",
}

# Short subject used when a line would otherwise open with a pronoun. Derived from the display name.
SUBJECT = {"WB-053": "Haematocrit", "WB-064": "The red cell count", "WB-055": "The white cell count", "WB-054": "The platelet count",
           "WB-005": "The ratio", "WB-008": "The ratio", "WB-009": "The ratio", "WB-020": "The ratio", "WB-021": "The ratio",
           "WB-029": "The ratio", "WB-030": "The ratio", "WB-063": "The Mentzer index", "WB-065": "The GK index", "WB-066": "RDWI",
           "WB-070": "Average blood sugar", "WB-112": "Iron", "WB-023": "Calcium", "WB-103": "Calcium"}


def subject_for(row):
    import re as _re

    key = row.get("content_key") or row.get("risk_id")
    if key in SUBJECT:
        return SUBJECT[key]
    name = row.get("display_name") or ""
    m = _re.search(r"\(([^)]*)\)", name)
    if m and _re.fullmatch(r"[A-Za-z0-9.\-]{2,8}", m.group(1)) and any(ch.isupper() for ch in m.group(1)[1:] + m.group(1)[:1]):
        return m.group(1)
    base = name.split(" (")[0].strip()
    return base[:1].upper() + base[1:]


def resolve_openers(lines, subject):
    """A line shown on its own must not open with a pronoun that points at an unseen sentence."""
    out = []
    for line in lines or []:
        if line.startswith("It "):
            line = subject + line[2:]
        out.append(line)
    return out


def load(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def dump(rel, data):
    (ROOT / rel).write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def lower_name(row):
    name = row.get("display_name") or row.get("clinical_name") or ""
    # Keep abbreviations and proper names; lower only a leading ordinary word.
    if name[:1].isupper() and not name[:2].isupper() and name.split(" ")[0] not in {"HbA1c", "Lipoprotein(a)"}:
        return name[0].lower() + name[1:]
    return name


def merge_sources(row, extra):
    out = list(row.get("source_ids") or [])
    for s in extra:
        if s not in out:
            out.append(s)
    return out


def review_dims(row):
    dims = dict(row.get("review_dimensions") or {})
    dims.update({
        "draft_completeness": "education_upgrade_2_4",
        "structural_validation": "passed_at_revision_2_4",
        "writing_quality": "education_standard_2_4_pending_independent_review",
        "medical_evidence": "pending_claim_verification",
        "human_clinical_review": "pending_clinical_review",
        "integration_readiness": dims.get("integration_readiness", "blocked"),
    })
    return dims


def _na_check(key, c, na):
    if c.get("life") is None and "lifestyle_relationships" not in na:
        raise SystemExit(f"{key}: lifestyle omitted without a non-applicable reason")
    if not c.get("support") and "practical_guidance" not in na:
        raise SystemExit(f"{key}: practical guidance omitted without a non-applicable reason")


UPGRADES: dict = {}
X_MODULES = [m + "_x" for m in MODULES]


def upgrades():
    out = {}
    for m in X_MODULES:
        mod = importlib.import_module(m)
        dup = set(out) & set(mod.X)
        if dup:
            raise SystemExit(f"duplicate upgrade keys {dup}")
        out.update(mod.X)
    return out


def corrected(key, c):
    """2.3.1 text with the sample review corrections applied."""
    x = UPGRADES.get(key) or {}
    c = dict(c)
    for field, value in (x.get("fix") or {}).items():
        c[field] = value
    return c


def apply_education(out, key, na):
    x = UPGRADES.get(key)
    if not x:
        raise SystemExit(f"{key}: no education upgrade")
    fx = x["fx"]
    if not fx or any(not f or not how for f, how in fx):
        raise SystemExit(f"{key}: every influencing factor needs an explanation")
    out["possible_influencing_factors"] = [f for f, _ in fx]
    out["factor_explanations"] = [{"factor": f, "how_it_acts": how} for f, how in fx]
    na.update(x.get("na") or {})
    if x.get("keep"):
        out["keeping_healthy"] = list(x["keep"])
    elif "keeping_healthy" not in na:
        raise SystemExit(f"{key}: keeping_healthy omitted without a reason")
    if x.get("risk"):
        out["lowering_risk"] = list(x["risk"])
    if x.get("myth"):
        out["common_misconceptions"] = list(x["myth"])
    elif "misconceptions" not in na:
        na["misconceptions"] = "No common misconception specific to this result was identified."
    if x.get("thr"):
        out["reference_range_note"] = x["thr"]
    out["not_applicable"] = na


def build_biomarker(row, c):
    key = row["content_key"]
    c = corrected(key, c)
    name = lower_name(row)
    na = dict(c.get("not_applicable") or {})
    _na_check(key, c, na)
    states = list(row["result_explanations"])
    results, questions = {}, {}
    for state in states:
        if state == "assay_unconfirmed":
            text = c.get("assay")
            if not text:
                raise SystemExit(f"{key}: assay_unconfirmed state needs assay text")
            results[state] = [text]
            questions[state] = c["q"]["assay_unconfirmed"][:4]
        elif state == "reference_unavailable":
            results[state] = [f"Your report did not include a reference range for {name}, so CURA cannot say whether it is high or low."]
            questions[state] = ([f"Why does my report not show a range for {name}?"] + c["q"].get("normal", []))[:4]
        else:
            results[state] = [c[state]]
            questions[state] = c["q"][state][:4]
    subject = subject_for(row)
    fix = lambda lines: resolve_openers(lines, subject)
    related = list(row.get("related_biomarkers") or [])
    for extra in RELATED_ADD.get(key, []):
        if extra not in related:
            related.append(extra)
    if not related and key in RELATED_NA:
        na["related_biomarkers"] = RELATED_NA[key]
    out = dict(row)
    out.update(
        related_biomarkers=related,
        short_description=c["d"],
        what_happens_inside_my_body=fix(c["body"]),
        why_this_test_matters=fix(c["why"]),
        result_explanations=results,
        possible_influencing_factors=c["factors"],
        diet_and_lifestyle=c.get("life") or [],
        everyday_support=c.get("support") or [],
        when_to_seek_medical_advice=c["seek"],
        clinical_limitations=c["limits"],
        suggested_questions=questions,
        not_applicable=na,
        source_ids=merge_sources(row, EXTRA_SOURCES.get(key, [])),
        content_version="2.3",
        content_revision=REVISION,
        draft_status="education_upgrade_2_4",
        evidence_status="pending_claim_verification",
        review_status="pending_clinical_review",
        review_dimensions=review_dims(row),
    )
    apply_education(out, key, na)
    if c.get("cond") is not None:
        out["conditional_result_explanations"] = c["cond"]
    elif "assay_unconfirmed" in states and c.get("high"):
        out["conditional_result_explanations"] = {"if_method_confirmed": {s: [c[s]] for s in ("high", "low", "normal") if c.get(s)}}
    return out


def build_allergen(row):
    from allergens import ASSAY, BODY, COND, EMERGENCY, GROUP, GROUPS, LIMITS

    group = GROUPS[row["test_profile"]]
    g = GROUP[group]
    n = row["display_name"].replace(" \u2013 ", ", ").replace("\u2013", "-")
    fill = lambda items: [s.format(n=n) for s in items]
    na = {"related_biomarkers": "Each allergen test is read with symptoms; total IgE gives background where it was tested."}
    na.update(g.get("na") or {})
    out = dict(row)
    out["display_name"] = n  # lab label without the long dash, e.g. "House Dust, IFCI 1"
    out.update(
        short_description=_allergen_about(n)[0] + " This test looks for IgE, the allergy antibody, against it. It shows whether your immune system recognises it, not whether you are allergic.",
        what_happens_inside_my_body=BODY,
        why_this_test_matters=[g["why"].format(n=n)],
        result_explanations={"assay_unconfirmed": [ASSAY.format(n=n)]},
        conditional_result_explanations={"specific_ige_only": {k: fill(v) for k, v in COND.items()}},
        diet_and_lifestyle=fill(g["life"] or []),
        everyday_support=fill(g["support"]),
        when_to_seek_medical_advice=fill(g["seek"]),
        clinical_limitations=LIMITS,
        suggested_questions={"assay_unconfirmed": [f"Where might I come across {n}?"] + fill(g["q"])},
        not_applicable=na,
        allergen_group=group,
        possible_influencing_factors=["Exact test method and material used", "Timing and type of symptoms after contact", "Antibodies to similar substances"],
        source_ids=merge_sources(row, ["allergy"] + (["food"] if group == "food" else ["drug"] if group == "drug" else []) + ["mlp_anaphylaxis"] * (group != "parasite")),
        content_version="2.3",
        content_revision=REVISION,
        draft_status="rewritten_2_3_1_group_shared",
        evidence_status="pending_claim_verification",
        review_status="pending_clinical_review",
        review_dimensions=review_dims(row),
    )
    out["suggested_questions"]["assay_unconfirmed"] = out["suggested_questions"]["assay_unconfirmed"][:4]
    about, cross = _allergen_about(n)
    out["about_this_substance"] = about
    if cross:
        out["cross_reactivity"] = cross
    else:
        out["not_applicable"]["cross_reactivity"] = "No well-established cross-reaction is recorded for this substance."
    from allergens_x import SEVERE, SEVERE_NOTE

    if row["display_name"] in SEVERE or n in SEVERE:
        out["severity_note"] = SEVERE_NOTE
    out["draft_status"] = "education_upgrade_2_4_individual"
    return out


def _allergen_about(n):
    from allergens_x import N

    key = n if n in N else n.replace(", ", " \u2013 ")
    if key not in N:
        raise SystemExit(f"allergen {n!r}: no individual content")
    return N[key]


def build_risk(row, r):
    from bio_ai_x import FACTORS_NOTE as _NOT_CAUSE, RISK_MEANING as _RISK_MEANING, X as BX

    x = BX.get(row["risk_id"])
    if not x:
        raise SystemExit(f"{row['risk_id']}: no education upgrade")
    r = dict(r)
    fix = dict(x.get("fix") or {})
    add = fix.pop("misconceptions_add", [])
    r.update(fix)
    r["misconceptions"] = list(r["misconceptions"]) + add
    r["factors"] = [f for f, _ in x["fx"]]
    out = dict(row)
    context = []
    for item in row.get("relevant_biomarker_context") or []:
        item = dict(item)
        if item.get("content_key") in r.get("reasons", {}):
            item["reason"] = r["reasons"][item["content_key"]]
        context.append(item)
    na = dict(r.get("na") or {})
    if not r.get("symptoms"):
        na.setdefault("symptoms", "A prediction about metabolic patterns; it has no symptoms of its own.")
    if not context:
        na.setdefault("blood_test_relationships", "The provider has not published which blood tests feed this estimate.")
    relevant = list(row.get("relevant_biomarkers") or [])
    relevant = ["hdl_cholesterol_direct" if b == "hdl" else b for b in relevant]
    subject = subject_for(row)
    fix = lambda lines: resolve_openers(lines, subject)
    out.update(
        short_description=r["short"],
        what_happens_inside_my_body=fix(r["body"]),
        why_it_matters=fix(r["why"]),
        common_symptoms=r.get("symptoms") or [],
        influencing_factors=r["factors"],
        influencing_factors_note=_NOT_CAUSE,
        diet_and_lifestyle=r["life"],
        long_term_implications=r["long_term"],
        everyday_support=r["support"],
        when_to_seek_medical_advice=r["seek"],
        risk_meaning=r.get("risk_meaning") or _RISK_MEANING,
        common_misconceptions=r["misconceptions"],
        clinical_limitations=r["limits"],
        suggested_questions=r["q"][:4],
        relevant_biomarkers=relevant,
        relevant_biomarker_context=context,
        not_applicable=na,
        source_ids=merge_sources(row, r.get("src") or []),
        content_version="2.3",
        content_revision=REVISION,
        draft_status="rewritten_2_3_1",
        evidence_status="pending_claim_verification",
        review_status="pending_clinical_review",
    )
    out["factor_explanations"] = [{"factor": f, "how_it_acts": how} for f, how in x["fx"]]
    out["keeping_healthy"] = list(x["keep"])
    out["draft_status"] = "education_upgrade_2_4"
    if "relevant_biomarker_context" not in row and not context:
        out.pop("relevant_biomarker_context")
    return out


def write_shared_register():
    """Sentences deliberately shared within a family of tests. Anything else repeated across entries is flagged."""
    import blood, bio_ai, bio_ai_x, heart_x, hormones_cancer, kidney, kidney_x, liver, liver_x, sugar_inflammation, sugar_inflammation_x, urine, urine_x

    families = {
        "white_cell_types": ("The five white cell types share the same background and the same reason for testing.",
                             blood.C["WB-042"]["body"] + blood.C["WB-057"]["body"][2:] + blood.C["WB-042"]["why"] + blood.C["WB-057"]["limits"] + blood.C["WB-042"]["limits"]),
        "urine_method_unconfirmed": ("Urine items whose lab method is not confirmed carry the same method notice.", [urine._ASSAY, urine._UTI_SEEK, urine._URINE_LIMIT]),
        "tumour_markers": ("Tumour markers share the same purpose, limitation and advice.", [hormones_cancer._TUMOUR_LIMIT, hormones_cancer._TUMOUR_SEEK,
                           "This marker is mainly used to follow people already being treated for certain cancers, and sometimes to help investigate symptoms.", "A low result is expected and is not a concern."]),
        "kidney_hydration": ("Kidney and salt results share the same hydration guidance and referral advice.", [kidney._HYDRATE, kidney._KIDNEY_SEEK]),
        "liver_enzymes": ("Liver enzyme results share liver-support guidance.", liver._LIVER_SUPPORT),
        "blood_sugar": ("Blood sugar results share the same guidance and referral advice.", sugar_inflammation_x.SUGAR_SUPPORT + sugar_inflammation._SUGAR_SEEK),
        "iron": ("Iron results share iron guidance.", blood._IRON_SUPPORT + blood._IRON_SEEK),
        "bio_ai_risk_meaning": ("Every Bio-AI prediction carries the same explanation of what a predicted score means.", bio_ai_x.RISK_MEANING),
        "heart_guidance": ("Cholesterol results share heart maintenance, risk and lab cut-off guidance.", heart_x._HEART_KEEP + heart_x._HEART_RISK + [heart_x._LIPID_TARGET]),
        "kidney_guidance": ("Kidney and salt results share kidney maintenance guidance and the filtering mechanism.", kidney_x._KIDNEY_KEEP + kidney_x._KIDNEY_RISK + [kidney_x._KIDNEY_FX[1], kidney_x._HYD[1]]),
        "liver_guidance": ("Liver enzyme results share liver maintenance and risk guidance.", liver_x._LIVER_KEEP + liver_x._LIVER_RISK + [liver_x._ENZ_MYTH]),
        "urine_infection": ("Urine infection and contamination factors are shared across urine findings.", [urine_x._UTI[1], urine_x._CONTAM[1]]),
        "assay_unconfirmed_notice": ("Items whose lab method is unconfirmed share the same notice.", []),
    }
    rows = [{"family": fam, "reason": why, "sentence": line} for fam, (why, lines) in families.items() for line in lines]
    (ROOT / "audit").mkdir(exist_ok=True)
    dump("audit/shared_sentence_register.json", {"revision": REVISION, "note": "Deliberately shared sentences. The audit flags any other sentence used by more than three entries.", "sentences": rows})


def build_categories():
    from categories_x import C

    rows = load("content/health_category_content.json")
    if {r["health_category"] for r in rows} != set(C):
        raise SystemExit("category education does not cover every category")
    for r in rows:
        c = C[r["health_category"]]
        na = dict(r.get("not_applicable") or {})
        r["what_happens_inside_my_body"] = c["body"]
        r["why_it_matters"] = c["why"]
        if c.get("keep"):
            r["keeping_healthy"] = c["keep"]
        else:
            na["keeping_healthy"] = "Results in this area follow illness, treatment or sample details rather than everyday habits."
        if c.get("risk"):
            r["lowering_risk"] = c["risk"]
        if c.get("myth"):
            r["common_misconceptions"] = c["myth"]
        if na:
            r["not_applicable"] = na
        r.update(content_revision=REVISION, draft_status="education_upgrade_2_4", review_status="pending_clinical_review")
    dump("content/health_category_content.json", rows)


def build_relationships():
    from lifestyle_x import L
    from relationships_x import T

    rel = load("relationships/biomarker_relationships.json")
    pairs = {"|".join(sorted((r["source_content_key"], r["related_content_key"]))) for r in rel}
    if pairs != set(T):
        raise SystemExit(f"relationship education mismatch: missing {sorted(pairs - set(T))}, extra {sorted(set(T) - pairs)}")
    for r in rel:
        r["reading_together"] = T["|".join(sorted((r["source_content_key"], r["related_content_key"])))]
        r["content_revision"] = REVISION
    dump("relationships/biomarker_relationships.json", rel)

    life = load("relationships/lifestyle_relationships.json")
    if {r["relationship_id"] for r in life} != set(L):
        raise SystemExit("lifestyle education does not cover every relationship")
    for r in life:
        how, limit = L[r["relationship_id"]]
        r["user_explanation"] = how
        r["clinical_limitations"] = [limit] + [x for x in r.get("clinical_limitations") or [] if x != limit]
        r["content_revision"] = REVISION
    dump("relationships/lifestyle_relationships.json", life)


def main():
    import subprocess

    global UPGRADES
    UPGRADES = upgrades()

    # Always rebuild from the 2.3 baseline commit, so re-running is safe and never rewrites rewritten text.
    lib = ROOT.relative_to(ROOT.parents[3]).as_posix()
    for rel in ("content/biomarker_content.json", "content/allergy_content.json", "content/bio_ai_content.json", "evidence/content_sources.json",
                "content/health_category_content.json", "relationships/biomarker_relationships.json", "relationships/lifestyle_relationships.json"):
        text = subprocess.run(["git", "show", f"{BASELINE_COMMIT}:{lib}/{rel}"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
        (ROOT / rel).write_text(text, encoding="utf-8")
    content = {}
    for m in MODULES:
        mod = importlib.import_module(m)
        dup = set(content) & set(mod.C)
        if dup:
            raise SystemExit(f"duplicate keys {dup}")
        content.update(mod.C)
    biomarkers = load("content/biomarker_content.json")
    missing = {r["content_key"] for r in biomarkers} - set(content)
    if missing:
        raise SystemExit(f"no 2.3.1 content for {sorted(missing)}")
    dump("content/biomarker_content.json", [build_biomarker(r, content[r["content_key"]]) for r in biomarkers])

    dump("content/allergy_content.json", [build_allergen(r) for r in load("content/allergy_content.json")])

    from bio_ai import R

    risks = load("content/bio_ai_content.json")
    if {r["risk_id"] for r in risks} != set(R):
        raise SystemExit("Bio-AI content does not cover every assessment")
    dump("content/bio_ai_content.json", [build_risk(r, R[r["risk_id"]]) for r in risks])

    build_categories()
    build_relationships()

    sources = load("evidence/content_sources.json")
    have = {s["source_id"] for s in sources}
    for sid, (title, url) in NEW_SOURCES.items():
        if sid not in have:
            sources.append({"source_id": sid, "title": title, "url": url, "verification": PROPOSED})
    dump("evidence/content_sources.json", sources)
    write_shared_register()
    import evidence_map

    evidence_map.main()  # the evidence register is rebuilt from baseline above, so re-register the pages read
    print(f"applied {REVISION}: {len(biomarkers)} biomarkers, 211 allergens, {len(risks)} Bio-AI entries, {len(NEW_SOURCES)} proposed sources")


if __name__ == "__main__":
    main()
