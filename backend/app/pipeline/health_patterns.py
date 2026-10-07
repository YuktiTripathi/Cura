"""Group a member's results into the few health patterns that explain them.

Deterministic, config-driven. A pattern is a body system whose markers can tell one story
(HbA1c + glucose = glucose regulation; MCV + MCH + ferritin + RDW = iron / red cells).
The answer model receives patterns ranked by how strongly they stand out, plus the systems
that are reassuringly in range, so it can synthesize and prioritize instead of listing
markers. Patterns describe where results point; they are never diagnoses, and the ranking
is a reasonable order to discuss, not a clinical risk score.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    code: str
    label: str
    markers: tuple[str, ...]
    bio_ai: tuple[str, ...] = ()
    weight: float = 0.0  # small clinical-importance nudge when ranking themes


THEMES: tuple[Theme, ...] = (
    Theme("glucose", "glucose regulation", ("hba1c", "glucose", "fasting_blood_glucose", "postprandial_glucose",
                                            "fasting_insulin"), ("type_2_diabetes", "metabolic_score"), 0.35),
    Theme("lipids", "blood fats (lipids)", ("triglycerides", "ldl", "cholesterol", "hdl", "non_hdl", "vldl"),
          ("dyslipidemia", "cardiac_health"), 0.3),
    Theme("iron_red_cells", "iron and red blood cells", ("hemoglobin", "mcv", "mch", "mchc", "rdw", "ferritin", "iron",
                                                         "transferrin_saturation", "rbc"), (), 0.2),
    Theme("liver", "liver enzymes", ("alt", "ast", "ggt", "alp", "bilirubin"), ("nafld",), 0.15),
    Theme("kidney", "kidney function", ("creatinine", "egfr", "bun", "urea", "uric_acid"), (), 0.15),
    Theme("thyroid", "thyroid", ("tsh", "t3", "t4"), ("thyroid",), 0.1),
    Theme("body_weight", "body weight", ("bmi", "waist"), ("obesity",), 0.15),
    Theme("blood_pressure", "blood pressure", ("systolic", "diastolic"), ("hypertension",), 0.25),
    Theme("vitamins", "vitamins", ("vitamin_d", "vitamin_b12", "folate"), (), -0.1),
)

_ABNORMAL = {"low", "high", "critical"}


def _flag(marker) -> str:
    raw = getattr(getattr(marker, "flag", None), "value", getattr(marker, "flag", None))
    return str(raw or "").lower()


def _deviation(marker) -> float:
    """How far outside the report's own range, relative to the range (0 when in range)."""
    try:
        value = float(marker.value)
    except (TypeError, ValueError):
        return 0.0
    low, high = marker.reference_low, marker.reference_high
    span = (high - low) if (low is not None and high is not None and high > low) else max(abs(value), 1.0)
    if high is not None and value > high:
        return min((value - high) / span, 3.0)
    if low is not None and value < low:
        return min((low - value) / span, 3.0)
    return 0.0


def _elevated(risk) -> bool:
    status = (getattr(risk, "status", "") or "").lower()
    return any(w in status for w in ("high", "elevated", "moderate", "attention", "risk")) and "low" not in status


def _fact(marker) -> dict:
    out = {"code": marker.key, "name": marker.name, "value": marker.value, "unit": marker.unit,
           "status": _flag(marker) or None}
    if marker.reference_low is not None or marker.reference_high is not None:
        out["report_range"] = [marker.reference_low, marker.reference_high]
    return {k: v for k, v in out.items() if v is not None}


def find_patterns(markers, risks, *, trend_codes: dict[str, str] | None = None) -> tuple[list[dict], list[dict]]:
    """(patterns ranked by how much they stand out, reassuring systems)."""
    by_key = {m.key: m for m in markers or [] if m.value is not None}
    patterns: list[tuple[float, dict]] = []
    reassuring: list[dict] = []
    for theme in THEMES:
        present = [by_key[k] for k in theme.markers if k in by_key]
        if not present:
            continue
        abnormal = sorted((m for m in present if _flag(m) in _ABNORMAL), key=_deviation, reverse=True)
        normal = [m for m in present if _flag(m) not in _ABNORMAL]
        aligned = [r for r in risks or [] if r.code in theme.bio_ai and _elevated(r)]
        if not abnormal:
            reassuring.append({"system": theme.label, "in_range": [m.name or m.key for m in normal][:4]})
            continue
        score = max(_deviation(m) for m in abnormal) + 0.25 * (len(abnormal) - 1) + 0.35 * bool(aligned) + theme.weight
        if any(_flag(m) == "critical" for m in abnormal):
            score += 5
        worsening = [k for k in (m.key for m in abnormal) if (trend_codes or {}).get(k) == "worse"]
        if worsening:
            score += 0.2
        entry = {
            "pattern": theme.label,
            "out_of_range": [_fact(m) for m in abnormal],
            "in_range_in_same_system": [m.name or m.key for m in normal][:3],
            "related_bio_ai": [{"name": r.name, "status": r.status} for r in aligned],
            "points_in_same_direction": len(abnormal) >= 2 or bool(aligned),
            "worsening_since_previous": worsening,
        }
        patterns.append((score, entry))
    patterns.sort(key=lambda item: item[0], reverse=True)
    ranked = []
    for rank, (_score, entry) in enumerate(patterns, start=1):
        ranked.append({"rank": rank, **entry})
    return ranked, reassuring


def theme_codes_for(codes: set[str]) -> set[str]:
    """Theme labels that contain any of these marker or Bio-AI codes."""
    return {t.label for t in THEMES if codes & set(t.markers) or codes & set(t.bio_ai)}


# Markers that change the interpretation of another marker ("why are my triglycerides high?"
# is answered alongside glucose control, HDL and weight). Context, never causes.
RELATED: dict[str, tuple[str, ...]] = {
    "triglycerides": ("hba1c", "glucose", "fasting_blood_glucose", "hdl", "ldl", "bmi"),
    "hba1c": ("glucose", "fasting_blood_glucose", "triglycerides", "bmi"),
    "glucose": ("hba1c", "fasting_blood_glucose", "triglycerides"),
    "fasting_blood_glucose": ("hba1c", "glucose", "triglycerides"),
    "ldl": ("cholesterol", "hdl", "triglycerides"),
    "cholesterol": ("ldl", "hdl", "triglycerides"),
    "hdl": ("triglycerides", "ldl", "hba1c"),
    "hemoglobin": ("mcv", "mch", "ferritin", "rdw"),
    "ferritin": ("hemoglobin", "mcv", "mch"),
    "mcv": ("hemoglobin", "mch", "ferritin", "rdw"),
    "alt": ("ast", "triglycerides", "hba1c"),
    "ast": ("alt",),
    "creatinine": ("egfr", "bun", "urea"),
    "egfr": ("creatinine",),
    "tsh": ("t4", "t3"),
    "uric_acid": ("creatinine", "triglycerides"),
}


def related_markers(codes: list[str], limit: int = 4) -> list[str]:
    out: list[str] = []
    for code in codes:
        for other in RELATED.get(code, ()):
            if other not in codes and other not in out:
                out.append(other)
    return out[:limit]
