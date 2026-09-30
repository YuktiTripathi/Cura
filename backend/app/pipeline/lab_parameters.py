"""Canonical lab-parameter aliases for routing and retrieval. Not an answer dictionary."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class LabParameter:
    key: str
    display_name: str
    aliases: tuple[str, ...]
    family: str


# Longer aliases must be listed first within each parameter.
PARAMETERS: tuple[LabParameter, ...] = (
    LabParameter(
        "fasting_blood_glucose",
        "Fasting Blood Sugar Glucose",
        (
            "fasting blood sugar glucose",
            "fasting blood glucose",
            "fasting blood sugar",
            "fasting glucose",
            "fasting sugar",
            "fbs",
        ),
        "glucose",
    ),
    LabParameter(
        "postprandial_glucose",
        "Postprandial Glucose",
        ("postprandial glucose", "pp glucose", "ppbs", "post prandial sugar"),
        "glucose",
    ),
    LabParameter(
        "glucose",
        "Glucose",
        (
            "blood glucose",
            "blood sugar",
            "sugar level",
            "glucose level",
            "glucose",
            "sugar",
        ),
        "glucose",
    ),
    LabParameter("hba1c", "HbA1c", ("hba1c", "hb a1c", "a1c", "glycated hemoglobin", "glycosylated hemoglobin"), "hba1c"),
    LabParameter(
        "hemoglobin",
        "Hemoglobin",
        ("haemoglobin (hb)", "haemoglobin", "hemoglobin", "hgb", "hb"),
        "hemoglobin",
    ),
    LabParameter(
        "fasting_insulin",
        "Fasting insulin",
        ("fasting insulin", "fasting serum insulin", "serum insulin", "insulin fasting"),
        "insulin",
    ),
    LabParameter("magnesium", "Magnesium", ("serum magnesium", "magnesium", "mg level"), "mineral"),
    LabParameter("mcv", "MCV", ("mean corpuscular volume", "mean corp volume", "mcv"), "cbc"),
    LabParameter(
        "mch",
        "MCH",
        ("mean corpuscular hemoglobin", "mean corp hb", "mean corp haemoglobin", "mch"),
        "cbc",
    ),
    LabParameter("mchc", "MCHC", ("mean corpuscular hemoglobin concentration", "mchc"), "cbc"),
    LabParameter("rbc", "RBC", ("red blood cell count", "red blood cells", "rbc"), "cbc"),
    LabParameter(
        "wbc",
        "WBC",
        ("total leukocyte count", "total leucocyte count", "white blood cell count", "white blood cells", "tlc", "wbc"),
        "cbc",
    ),
    LabParameter("platelets", "Platelets", ("platelet count", "platelets", "plt"), "cbc"),
    LabParameter(
        "hematocrit",
        "Hematocrit",
        ("packed cell volume", "haematocrit", "hematocrit", "pcv", "hct"),
        "cbc",
    ),
    LabParameter("iron", "Iron", ("iron serum", "serum iron", "iron"), "iron"),
    LabParameter("tibc", "TIBC", ("total iron binding capacity", "tibc"), "iron"),
    LabParameter("transferrin", "Transferrin", ("transferrin saturation", "transferrin"), "iron"),
    LabParameter(
        "cholesterol",
        "Cholesterol",
        ("total cholesterol", "serum cholesterol", "cholesterol"),
        "cholesterol",
    ),
    LabParameter("ldl", "LDL", ("ldl cholesterol", "ldl-c", "ldl"), "lipid"),
    LabParameter("hdl", "HDL", ("hdl cholesterol", "hdl-c", "hdl"), "lipid"),
    LabParameter("triglycerides", "Triglycerides", ("triglycerides", "triglyceride", "tg"), "lipid"),
    LabParameter(
        "kidney_function",
        "Kidney function",
        (
            "kidney function",
            "renal function",
            "kidney results",
            "kidney result",
            "kidney markers",
            "kidney marker",
            "renal markers",
            "kidney panel",
            "kidney health",
        ),
        "kidney",
    ),
    LabParameter(
        "thyroid_function",
        "Thyroid function",
        (
            "thyroid function",
            "thyroid hormones",
            "thyroid results",
            "thyroid result",
            "thyroid panel",
            "thyroid labs",
            "thyroid lab",
            "thyroid markers",
            "thyroid marker",
            "thyroid health",
        ),
        "thyroid_labs",
    ),
    LabParameter(
        "liver_function",
        "Liver function",
        ("liver function", "liver results", "liver result", "lft", "liver panel"),
        "liver",
    ),
    LabParameter(
        "creatinine",
        "Creatinine",
        ("serum creatinine", "creatinine", "creat"),
        "kidney",
    ),
    LabParameter(
        "egfr",
        "eGFR",
        ("estimated glomerular filtration rate", "estimated gfr", "gfr estimated", "egfr", "e-gfr", "gfr"),
        "kidney",
    ),
    LabParameter("urea", "Urea", ("blood urea nitrogen", "blood urea", "urea", "bun"), "kidney"),
    LabParameter("uric_acid", "Uric Acid", ("uric acid",), "kidney"),
    LabParameter(
        "tsh",
        "TSH",
        ("thyroid-stimulating hormone", "thyroid stimulating hormone (tsh)", "thyroid stimulating hormone", "tsh ultrasensitive", "tsh"),
        "thyroid_labs",
    ),
    LabParameter("t3", "T3", ("free t3", "serum t3", "total t3", "ft3", "t3"), "thyroid_labs"),
    LabParameter("t4", "T4", ("free t4", "serum t4", "total t4", "ft4", "t4"), "thyroid_labs"),
    LabParameter(
        "vitamin_d",
        "Vitamin D",
        (
            "25 hydroxy vitamin d",
            "25-oh vitamin d",
            "vitamin d 25 hydroxy",
            "vitamin d total",
            "vitamin d",
            "vit d",
            "25 oh",
            "25-oh",
        ),
        "vitamin",
    ),
    LabParameter("vitamin_b12", "Vitamin B12", ("vitamin b12", "vit b12", "b12"), "vitamin"),
    LabParameter("ferritin", "Ferritin", ("ferritin",), "iron"),
    LabParameter("esr", "ESR", ("erythrocyte sedimentation", "esr"), "inflammation"),
    LabParameter("crp", "CRP", ("c-reactive protein", "c reactive protein", "crp"), "inflammation"),
    LabParameter("alt", "ALT", ("sgpt (alt)", "sgpt alt", "alanine aminotransferase", "sgpt", "alt"), "liver"),
    LabParameter("ast", "AST", ("sgot (ast)", "sgot ast", "aspartate aminotransferase", "sgot", "ast"), "liver"),
    LabParameter(
        "blood_pressure",
        "Blood pressure",
        ("blood pressure",),
        "blood_pressure",
    ),
    LabParameter(
        "bilirubin",
        "Bilirubin",
        ("serum bilirubin total", "bilirubin total", "total bilirubin", "serum bilirubin", "bilirubin"),
        "liver",
    ),
    LabParameter("albumin", "Albumin", ("serum albumin", "albumin"), "liver"),
    LabParameter(
        "systolic",
        "Systolic pressure",
        ("systolic pressure", "systolic bp", "sbp", "systolic"),
        "blood_pressure",
    ),
    LabParameter(
        "diastolic",
        "Diastolic pressure",
        ("diastolic pressure", "diastolic bp", "dbp", "diastolic"),
        "blood_pressure",
    ),
    LabParameter("mentzer", "Mentzer index", ("mentzer index", "mentzer"), "derived"),
    LabParameter("bmi", "BMI", ("body mass index", "bmi"), "derived"),
    LabParameter("waist", "Waist circumference", ("waist circumference", "waist"), "derived"),
)

DERIVED_ENTITY_KEYS = frozenset({"mentzer", "bmi", "waist"})

FAMILY_MEMBERS = {
    "glucose": ("fasting_blood_glucose", "postprandial_glucose", "glucose"),
    "cholesterol": ("ldl", "hdl", "cholesterol"),
    "blood_pressure": ("systolic", "diastolic"),
    "kidney": ("creatinine", "egfr", "urea", "uric_acid"),
    "thyroid_labs": ("tsh", "t3", "t4"),
    "liver": ("alt", "ast", "bilirubin"),
    "cbc": ("hemoglobin", "mcv", "mch", "mchc", "rbc", "wbc", "platelets", "hematocrit"),
    "iron": ("iron", "ferritin", "tibc", "transferrin"),
}

FAMILY_QUERY_KEYS = {"kidney_function", "thyroid_function", "liver_function", "blood_pressure"}
_SLUG_ALIASES = {
    "serum_creatinine": "creatinine",
    "creatinine": "creatinine",
    "free_t3": "t3",
    "serum_t3": "t3",
    "total_t3": "t3",
    "ft3": "t3",
    "t3": "t3",
    "free_t4": "t4",
    "serum_t4": "t4",
    "total_t4": "t4",
    "ft4": "t4",
    "t4": "t4",
    "thyroid_stimulating_hormone": "tsh",
    "thyroid_stimulating_hormone_tsh": "tsh",
    "tsh": "tsh",
    "sgpt": "alt",
    "sgpt_alt": "alt",
    "alanine_aminotransferase": "alt",
    "alt": "alt",
    "sgot": "ast",
    "sgot_ast": "ast",
    "aspartate_aminotransferase": "ast",
    "ast": "ast",
    "estimated_gfr": "egfr",
    "e_gfr": "egfr",
    "egfr": "egfr",
    "gfr": "egfr",
    "blood_urea_nitrogen": "urea",
    "blood_urea": "urea",
    "bun": "urea",
    "haemoglobin": "hemoglobin",
    "haemoglobin_hb": "hemoglobin",
    "hemoglobin_hb": "hemoglobin",
    "hb": "hemoglobin",
    "hgb": "hemoglobin",
    "serum_albumin": "albumin",
    "albumin": "albumin",
    "bilirubin_total": "bilirubin",
    "serum_bilirubin_total": "bilirubin",
    "serum_bilirubin": "bilirubin",
    "total_bilirubin": "bilirubin",
    "iron_serum": "iron",
    "pcv": "hematocrit",
    "hct": "hematocrit",
    "haematocrit": "hematocrit",
    "hematocrit": "hematocrit",
    "platelet_count": "platelets",
    "plt": "platelets",
    "tlc": "wbc",
    "total_leukocyte_count": "wbc",
    "total_leucocyte_count": "wbc",
    "hba1c_glycosylated_hemoglobin": "hba1c",
    "fasting_insulin": "fasting_insulin",
    "serum_insulin": "fasting_insulin",
    "serum_magnesium": "magnesium",
    "serum_iron": "iron",
    "transferrin_saturation": "transferrin",
    "vitamin_d_total_25_hydroxy": "vitamin_d",
    "vitamin_d_total": "vitamin_d",
    "25_hydroxy_vitamin_d": "vitamin_d",
    "ubic": "tibc",
    "unsaturated_iron_binding_capacity": "tibc",
    "fasting_sugar": "fasting_blood_glucose",
    "average_blood_glucose": "glucose",
    "mean_corp_hb": "mch",
    "mean_corp_volume": "mcv",
    "ldl_cholesterol": "ldl",
    "ldl_cholesterol_calculated": "ldl",
    "hdl_cholesterol": "hdl",
    "hdl_cholesterol_direct": "hdl",
    "serum_hdl_cholesterol": "hdl",
    "fasting_blood_sugar": "fasting_blood_glucose",
    "fasting_glucose": "fasting_blood_glucose",
    "fbs": "fasting_blood_glucose",
    "blood_sugar": "glucose",
    "total_cholesterol": "cholesterol",
    "cholesterol_total": "cholesterol",
    "serum_triglycerides": "triglycerides",
}

_BY_KEY = {p.key: p for p in PARAMETERS}


def parameter_alias_map() -> dict[str, str]:
    out: dict[str, str] = {}
    for param in PARAMETERS:
        out[param.key.replace("_", " ")] = param.key
        for alias in param.aliases:
            out[alias] = param.key
    return out


def _alias_span(alias: str, text: str):
    value = (alias or "").strip().lower()
    if not value:
        return None
    match = re.search(rf"(?<!\w){re.escape(value)}(?!\w)", text, re.I)
    if not match:
        return None
    return match.start(), match.end()


def match_lab_keys(text: str) -> list[str]:
    """Return canonical lab keys using word boundaries and longest non-overlapping aliases."""
    lowered = (text or "").lower()
    found: list[tuple[int, int, str]] = []
    for param in PARAMETERS:
        best = None
        for alias in param.aliases:
            span = _alias_span(alias, lowered)
            if span is None:
                continue
            start, end = span
            length = end - start
            if best is None or length > best[0] or (length == best[0] and start < best[1]):
                best = (length, start, end, param.key)
        if best:
            _, start, end, key = best
            found.append((start, end, key))
    found.sort(key=lambda row: (row[0], -(row[1] - row[0])))
    picked: list[str] = []
    occupied: list[tuple[int, int]] = []
    seen: set[str] = set()
    for start, end, key in found:
        if key in seen:
            continue
        if any(start < other_end and end > other_start for other_start, other_end in occupied):
            continue
        seen.add(key)
        occupied.append((start, end))
        picked.append(key)
    return picked


def normalize_lab_query(text: str) -> list[LabParameter]:
    return [_BY_KEY[key] for key in match_lab_keys(text) if key in _BY_KEY]


def primary_lab_key(text: str) -> str | None:
    keys = match_lab_keys(text)
    return keys[0] if keys else None


def canonicalize_marker_name(name: str) -> str:
    """Map a SuperShyft / lab display name onto a CURA canonical biomarker key."""
    slug = re.sub(r"[^a-z0-9]+", "_", (name or "").lower()).strip("_")
    slug = slug.replace("cholestrol", "cholesterol")
    if slug in _SLUG_ALIASES:
        return _SLUG_ALIASES[slug]
    if slug in _BY_KEY:
        return slug
    lowered = (name or "").lower()
    best_key = None
    best_len = 0
    for param in PARAMETERS:
        if param.key in FAMILY_QUERY_KEYS:
            continue
        for alias in param.aliases:
            span = _alias_span(alias, lowered)
            if span is None:
                continue
            length = len(alias)
            if length > best_len:
                best_len = length
                best_key = param.key
    if best_key:
        return best_key
    return _SLUG_ALIASES.get(slug, slug or "marker")


def expand_requested_keys(keys: list[str] | None) -> list[str]:
    out: list[str] = []
    for key in keys or []:
        for item in retrieval_keys(key):
            if item not in out:
                out.append(item)
    return out


def display_name_for(key: str) -> str:
    if key in _BY_KEY:
        return _BY_KEY[key].display_name
    from app.pipeline.intent import NAMES

    return NAMES.get(key, key.replace("_", " "))


def family_for(key: str | None) -> str | None:
    if not key:
        return None
    if key in _BY_KEY:
        return _BY_KEY[key].family
    return None


def related_keys(key: str | None) -> set[str]:
    return set(related_keys_ordered(key))


def related_keys_ordered(key: str | None) -> list[str]:
    if not key:
        return []
    if key in FAMILY_QUERY_KEYS:
        fam = family_for(key) or "kidney"
        return list(FAMILY_MEMBERS.get(fam, ()))
    fam = family_for(key)
    if fam in {"glucose", "cholesterol", "blood_pressure"}:
        return list(FAMILY_MEMBERS[fam])
    return [key]


def retrieval_keys(key: str | None) -> list[str]:
    if not key:
        return []
    if key in DERIVED_ENTITY_KEYS:
        return []
    if key in FAMILY_QUERY_KEYS:
        return related_keys_ordered(key)
    return [key]


def is_lab_key(key: str) -> bool:
    return key in _BY_KEY and key not in FAMILY_QUERY_KEYS


def aliases_for(key: str) -> list[str]:
    param = _BY_KEY.get(key)
    if not param:
        return [key.replace("_", " ")]
    return list(param.aliases) + [param.display_name.lower(), key.replace("_", " ")]
