"""Retrieval ontology: health domains expand to entities and sources.

This is not a diagnostic engine. Optional entities that are absent do not fail a domain.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.pipeline.lab_parameters import (
    DERIVED_ENTITY_KEYS,
    FAMILY_QUERY_KEYS,
    canonicalize_marker_name,
    is_lab_key,
)
from app.pipeline.language import normalize_for_intent


@dataclass(frozen=True)
class HealthDomain:
    code: str
    aliases: tuple[str, ...]
    primary_entities: tuple[str, ...] = ()
    supporting_entities: tuple[str, ...] = ()
    contextual_entities: tuple[str, ...] = ()
    derived_entities: tuple[str, ...] = ()
    sources: tuple[str, ...] = ("blood",)
    bioai_domains: tuple[str, ...] = ()
    related_domains: tuple[str, ...] = ()
    virtual: bool = False


_LIFESTYLE = ("questionnaire", "profile", "goals")
_GLYCEMIC = ("fasting_blood_glucose", "glucose", "hba1c")
_LIPIDS = ("cholesterol", "ldl", "hdl", "triglycerides")

DOMAINS: tuple[HealthDomain, ...] = (
    HealthDomain(
        "glycemic_health",
        ("glycemic", "glycaemic", "blood sugar control", "diabetes-related", "glucose control"),
        primary_entities=_GLYCEMIC,
        supporting_entities=("fasting_insulin",),
        contextual_entities=("bmi", "waist", "triglycerides", "hdl", "activity", "diet"),
        sources=("blood", "profile", "questionnaire"),
        bioai_domains=("type_2_diabetes",),
        related_domains=("metabolic_health", "weight_body_composition"),
    ),
    HealthDomain(
        "metabolic_health",
        ("metabolic health", "metabolic picture", "metabolic cluster", "metabolic"),
        primary_entities=_GLYCEMIC + ("fasting_insulin",) + _LIPIDS[2:] + ("alt", "uric_acid"),
        supporting_entities=("cholesterol", "ldl"),
        contextual_entities=("bmi", "weight", "waist", "activity", "diet", "sleep", "alcohol", "smoking"),
        sources=("blood", "profile", "questionnaire", "bio_ai"),
        bioai_domains=("type_2_diabetes", "obesity", "nafld", "hypertension", "dyslipidemia"),
        related_domains=("glycemic_health", "lipid_health", "weight_body_composition"),
    ),
    HealthDomain(
        "lipid_health",
        ("lipid", "lipids", "cholesterol panel", "lipid panel", "dyslipidemia"),
        primary_entities=_LIPIDS,
        supporting_entities=("vldl", "non_hdl", "apob", "apoa1", "lipoprotein_a"),
        derived_entities=("cholesterol",),
        sources=("blood", "bio_ai"),
        bioai_domains=("dyslipidemia",),
        related_domains=("cardiovascular_health", "metabolic_health"),
    ),
    HealthDomain(
        "cardiovascular_health",
        ("cardiovascular", "cardiac health", "heart health", "heart"),
        primary_entities=_LIPIDS + ("blood_pressure", "systolic", "diastolic", "crp", "hba1c", "glucose"),
        supporting_entities=("bmi", "waist"),
        contextual_entities=("smoking", "activity", "family_history"),
        sources=("blood", "bio_ai", "questionnaire", "profile"),
        bioai_domains=("cardiac_health", "hypertension", "dyslipidemia"),
        related_domains=("lipid_health", "blood_pressure_health", "glycemic_health"),
    ),
    HealthDomain(
        "blood_pressure_health",
        ("blood pressure", "bp health", "hypertension"),
        primary_entities=("blood_pressure", "systolic", "diastolic"),
        supporting_entities=("creatinine", "egfr", "sodium", "potassium"),
        sources=("blood", "bio_ai", "profile"),
        bioai_domains=("hypertension",),
        related_domains=("cardiovascular_health", "kidney_health"),
    ),
    HealthDomain(
        "kidney_health",
        (
            "kidney health",
            "kidney markers",
            "kidney marker",
            "renal markers",
            "renal function",
            "kidney function",
            "kidney results",
            "kidneys",
            "kidney",
        ),
        primary_entities=("creatinine", "egfr"),
        supporting_entities=("urea", "uric_acid", "albumin", "sodium", "chloride", "potassium"),
        contextual_entities=("blood_pressure", "hba1c", "glucose"),
        sources=("blood",),
        related_domains=("blood_pressure_health", "glycemic_health"),
    ),
    HealthDomain(
        "liver_health",
        ("liver health", "liver markers", "liver function", "lft", "liver panel", "liver"),
        primary_entities=("alt", "ast", "bilirubin"),
        supporting_entities=("albumin", "total_protein"),
        contextual_entities=("triglycerides", "glucose", "hba1c", "bmi", "waist", "alcohol"),
        sources=("blood",),
        bioai_domains=("nafld",),
        related_domains=("metabolic_health",),
    ),
    HealthDomain(
        "thyroid_health",
        (
            "thyroid health",
            "thyroid markers",
            "thyroid marker",
            "thyroid function",
            "thyroid hormones",
            "thyroid results",
            "thyroid panel",
            "thyroid labs",
            "thyroid",
        ),
        primary_entities=("tsh", "t4"),
        supporting_entities=("t3",),
        contextual_entities=("anti_tpo", "anti_thyroglobulin", "trab"),
        sources=("blood",),
    ),
    HealthDomain(
        "red_cell_anaemia_health",
        ("anaemia", "anemia", "red cell", "cbc anaemia", "blood count anaemia"),
        primary_entities=("hemoglobin", "rbc", "mcv", "mch", "mchc"),
        supporting_entities=("ferritin", "iron", "tibc", "transferrin", "vitamin_b12", "folate", "hematocrit", "rdw"),
        sources=("blood",),
        related_domains=("iron_status", "vitamin_b12_folate_status"),
    ),
    HealthDomain(
        "iron_status",
        ("iron status", "iron studies", "iron panel", "iron stores"),
        primary_entities=("ferritin", "iron", "tibc", "transferrin"),
        supporting_entities=("hemoglobin", "mcv", "mch", "mchc", "rbc"),
        derived_entities=("mentzer",),
        contextual_entities=("crp", "diet"),
        sources=("blood", "questionnaire"),
        related_domains=("red_cell_anaemia_health",),
    ),
    HealthDomain(
        "vitamin_b12_folate_status",
        ("b12 and folate", "vitamin b12 folate", "b12 folate", "folate status"),
        primary_entities=("vitamin_b12", "folate"),
        supporting_entities=("mcv", "mch", "hemoglobin"),
        contextual_entities=("diet",),
        sources=("blood", "questionnaire"),
    ),
    HealthDomain(
        "vitamin_d_bone_mineral_health",
        ("bone mineral", "bone health", "vitamin d status"),
        primary_entities=("vitamin_d", "calcium", "alp"),
        supporting_entities=("phosphorus", "pth", "magnesium"),
        contextual_entities=("diet", "activity"),
        sources=("blood", "questionnaire"),
        related_domains=("kidney_health",),
    ),
    HealthDomain(
        "inflammation",
        ("inflammation", "inflammatory markers", "inflammatory"),
        primary_entities=("crp", "esr"),
        supporting_entities=("ferritin", "wbc"),
        sources=("blood",),
    ),
    HealthDomain(
        "white_cell_immune_profile",
        ("white cell", "immune profile", "wbc differential", "differential count"),
        primary_entities=("wbc",),
        supporting_entities=("neutrophils", "lymphocytes", "monocytes", "eosinophils", "basophils"),
        sources=("blood",),
    ),
    HealthDomain(
        "platelet_coagulation_health",
        ("platelet health", "coagulation", "clotting profile", "coagulation profile"),
        primary_entities=("platelets",),
        supporting_entities=("mpv", "pt", "inr", "aptt", "fibrinogen", "d_dimer"),
        sources=("blood",),
    ),
    HealthDomain(
        "nutrition_micronutrient_health",
        ("micronutrient", "nutrition status", "nutrient status"),
        primary_entities=("iron", "ferritin", "vitamin_b12", "folate", "vitamin_d", "calcium", "magnesium"),
        supporting_entities=("albumin",),
        contextual_entities=("diet",),
        sources=("blood", "questionnaire", "goals"),
    ),
    HealthDomain(
        "weight_body_composition",
        ("body composition", "weight health", "obesity"),
        primary_entities=("bmi", "waist"),
        supporting_entities=("weight", "height"),
        contextual_entities=("glucose", "ldl", "hdl", "triglycerides", "blood_pressure", "diet", "activity"),
        sources=("profile", "blood", "questionnaire", "goals", "bio_ai"),
        bioai_domains=("obesity",),
        related_domains=("metabolic_health",),
    ),
    HealthDomain(
        "lifestyle_recovery",
        ("lifestyle", "sleep and exercise", "recovery habits", "daily habits"),
        primary_entities=("activity", "sleep", "diet", "smoking", "alcohol", "stress", "hydration"),
        sources=_LIFESTYLE,
        related_domains=("energy_fatigue_context",),
    ),
    HealthDomain(
        "overall_health",
        (
            "complete health",
            "overall health",
            "full health review",
            "review my health",
            "health overview",
            "biggest health concerns",
            "current health concerns",
        ),
        sources=("blood", "bio_ai", "questionnaire", "profile", "goals"),
        virtual=True,
    ),
    HealthDomain(
        "energy_fatigue_context",
        ("energy", "fatigue", "tiredness", "tired", "low energy"),
        primary_entities=("hemoglobin", "mcv", "iron", "ferritin", "vitamin_b12", "vitamin_d", "tsh", "glucose"),
        contextual_entities=("sleep", "activity", "diet"),
        sources=("blood", "questionnaire"),
        virtual=True,
    ),
)

DOMAIN_CODES = frozenset(item.code for item in DOMAINS)
_BY_CODE = {item.code: item for item in DOMAINS}
_FAMILY_TO_DOMAIN = {
    "thyroid_function": "thyroid_health",
    "kidney_function": "kidney_health",
    "liver_function": "liver_health",
    "blood_pressure": "blood_pressure_health",
}
_BIO_TO_DOMAIN = {
    "thyroid": "thyroid_health",
    "cardiac_health": "cardiovascular_health",
    "type_2_diabetes": "glycemic_health",
    "dyslipidemia": "lipid_health",
    "hypertension": "blood_pressure_health",
    "nafld": "liver_health",
    "obesity": "weight_body_composition",
}
_LIFESTYLE_KEYS = frozenset(
    {"activity", "sleep", "diet", "smoking", "alcohol", "stress", "hydration", "physical_activity"}
)
_PROFILE_KEYS = frozenset({"bmi", "waist", "weight", "height", "body_fat", "lean_mass"})
_BIO_CUE = re.compile(r"\b(scores?|bio-?ai|assessment|risks?)\b", re.I)
_LABS_CUE = re.compile(r"\b(labs?|blood (?:report|test|result)|markers?|results?)\b", re.I)


def domain_for_code(code: str | None) -> HealthDomain | None:
    if not code:
        return None
    if code in _BY_CODE:
        return _BY_CODE[code]
    mapped = _FAMILY_TO_DOMAIN.get(code) or _BIO_TO_DOMAIN.get(code)
    return _BY_CODE.get(mapped) if mapped else None


def domain_for_entity(key: str | None) -> HealthDomain | None:
    """Map a biomarker onto its primary health domain. Not a diagnosis."""
    if not key:
        return None
    canonical = canonicalize_entity(key)
    for domain in DOMAINS:
        if domain.virtual:
            continue
        if canonical in domain.primary_entities or key in domain.primary_entities:
            return domain
    for domain in DOMAINS:
        if domain.virtual:
            continue
        if canonical in domain.supporting_entities or key in domain.supporting_entities:
            return domain
    return domain_for_code(canonical)


def match_domains(message: str) -> list[HealthDomain]:
    text = normalize_for_intent(message).lower()
    hits: list[tuple[int, int, HealthDomain]] = []
    for domain in DOMAINS:
        best = None
        for alias in domain.aliases:
            if alias in {"thyroid", "kidney", "liver", "heart", "cardiac health"} and re.search(
                rf"\b{re.escape(alias)} (stimulating|hormone|score|risk|attack)\b", text, re.I
            ):
                continue
            if (
                domain.code == "lifestyle_recovery"
                and alias == "lifestyle"
                and re.search(r"\blifestyle changes?\b", text)
                and not re.search(r"\bmy lifestyle\b", text)
            ):
                continue
            match = re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", text, re.I)
            if not match:
                continue
            span = (match.start(), match.end(), domain)
            if best is None or (span[1] - span[0]) > (best[1] - best[0]):
                best = span
        if best:
            hits.append(best)
    hits.sort(key=lambda row: (row[0], -(row[1] - row[0])))
    picked: list[HealthDomain] = []
    occupied: list[tuple[int, int]] = []
    seen: set[str] = set()
    for start, end, domain in hits:
        if domain.code in seen:
            continue
        if any(start < other_end and end > other_start for other_start, other_end in occupied):
            continue
        seen.add(domain.code)
        occupied.append((start, end))
        picked.append(domain)
    return picked


def canonicalize_entity(code: str) -> str:
    raw = (code or "").strip()
    if not raw:
        return raw
    mapped = {
        "fasting_glucose": "fasting_blood_glucose",
        "random_glucose": "glucose",
        "ogtt_glucose": "glucose",
        "serum_creatinine": "creatinine",
        "blood_urea": "urea",
        "bun": "urea",
        "vitamin_d_25oh": "vitamin_d",
        "waist_circumference": "waist",
        "serum_iron": "iron",
        "mentzer_index": "mentzer",
        "platelet_count": "platelets",
        "tlc": "wbc",
        "pcv": "hematocrit",
        "serum_albumin": "albumin",
        "hs_crp": "crp",
        "total_cholesterol": "cholesterol",
        "physical_activity": "activity",
        "free_t4": "t4",
        "free_t3": "t3",
        "total_t4": "t4",
        "total_t3": "t3",
    }.get(raw, raw)
    return canonicalize_marker_name(mapped.replace("_", " ")) or mapped


def _blood_keys(codes: tuple[str, ...]) -> list[str]:
    out: list[str] = []
    for code in codes:
        key = canonicalize_entity(code)
        if key in DERIVED_ENTITY_KEYS or is_lab_key(key) or key in FAMILY_QUERY_KEYS:
            if key not in out:
                out.append(key)
    return out


class DomainExpansion:
    def __init__(self) -> None:
        self.domains: list[str] = []
        self.primary: list[str] = []
        self.supporting: list[str] = []
        self.optional: list[str] = []
        self.derived: list[str] = []
        self.lifestyle: list[str] = []
        self.profile: list[str] = []
        self.bioai: list[str] = []
        self.sources: list[str] = []
        self.virtual: bool = False

    def blood_entities(self) -> list[str]:
        return list(dict.fromkeys([*self.primary, *self.supporting]))

    def display_entities(self) -> list[str]:
        return self.blood_entities()

    def reasoning_context(self) -> list[str]:
        return list(dict.fromkeys([*self.optional, *self.derived, *self.lifestyle, *self.profile]))

    def all_optional(self) -> list[str]:
        return list(dict.fromkeys([*self.optional, *self.derived]))


class HealthDomainResolver:
    """Expand domains to candidate entities and sources after planning."""

    def expand(
        self,
        message: str,
        *,
        score_cue: bool | None = None,
        extra_domain_codes: list[str] | None = None,
    ) -> DomainExpansion:
        text = message or ""
        cue = bool(_BIO_CUE.search(text)) if score_cue is None else bool(score_cue)
        expansion = DomainExpansion()
        domains = list(match_domains(text))
        for code in extra_domain_codes or []:
            domain = domain_for_code(code)
            if domain and domain.code not in {item.code for item in domains}:
                domains.append(domain)
        for domain in domains:
            if cue and domain.code in set(_BIO_TO_DOMAIN.values()):
                continue
            expansion.domains.append(domain.code)
            expansion.virtual = expansion.virtual or domain.virtual
            for source in domain.sources:
                if source not in expansion.sources:
                    expansion.sources.append(source)
            expansion.bioai.extend(domain.bioai_domains)
            if domain.code == "lifestyle_recovery":
                expansion.lifestyle.extend(list(domain.primary_entities))
                if _LABS_CUE.search(text) and "blood" not in expansion.sources:
                    expansion.sources.append("blood")
                if not _LABS_CUE.search(text):
                    continue
            expansion.primary.extend(_blood_keys(domain.primary_entities))
            expansion.supporting.extend(_blood_keys(domain.supporting_entities))
            for item in domain.contextual_entities:
                key = canonicalize_entity(item)
                if key in _LIFESTYLE_KEYS:
                    expansion.lifestyle.append(key)
                elif key in _PROFILE_KEYS:
                    expansion.profile.append(key)
                elif is_lab_key(key) or key in DERIVED_ENTITY_KEYS:
                    expansion.optional.append(key)
            expansion.derived.extend([canonicalize_entity(item) for item in domain.derived_entities])
        expansion.primary = list(dict.fromkeys(expansion.primary))
        expansion.supporting = [key for key in dict.fromkeys(expansion.supporting) if key not in expansion.primary]
        expansion.optional = [
            key
            for key in dict.fromkeys(expansion.optional)
            if key not in expansion.primary and key not in expansion.supporting
        ]
        expansion.derived = list(dict.fromkeys(expansion.derived))
        expansion.lifestyle = list(dict.fromkeys(expansion.lifestyle))
        expansion.profile = list(dict.fromkeys(expansion.profile))
        expansion.bioai = list(dict.fromkeys(expansion.bioai))
        return expansion


def domain_aliases_occupied(message: str) -> list[tuple[int, int]]:
    text = normalize_for_intent(message).lower()
    spans: list[tuple[int, int]] = []
    for domain in match_domains(message):
        for alias in domain.aliases:
            match = re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", text, re.I)
            if match:
                spans.append((match.start(), match.end()))
                break
    return spans
