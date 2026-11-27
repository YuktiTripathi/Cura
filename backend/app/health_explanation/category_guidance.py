"""One cached explanation for a whole health category.

The model may only phrase influences and next steps from the verified findings and habits
it is given. If it is unavailable, the category still shows its results and static education.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re

from app.contracts.unified_health import CategoryDetail, CategoryGuidance, GuidancePoint
from app.health_explanation.category_story import CategoryProfile
from app.health_explanation.safety_validator import safety_problems

logger = logging.getLogger("cura.unified")

GENERATION = "guide-v1"
_SKIP = {"allergy"}
_NUMBER = re.compile(r"\d")

_FOCUS = {
    "heart_circulation": "Heart and blood vessels. Do not assume abnormal cholesterol means unhealthy food. Lp(a) is mostly inherited.",
    "liver_health": "Look at liver results together. Do not assume alcohol, fatty liver or diet caused a raised result.",
    "kidney_urinary": "Do not assume low water intake caused creatinine or urine results. Do not recommend extra water, protein restriction or mineral changes automatically.",
    "blood_iron": "Do not diagnose iron deficiency from serum iron alone. Do not give diet advice for unrelated white cell or platelet results.",
    "blood_sugar_metabolism": "Do not say sweets alone caused high sugar. Do not promise a Bio-AI score or metabolic age will fall by a set amount.",
    "thyroid_health": "Do not blame stress, food or exercise. Do not suggest iodine or that lifestyle alone corrects a thyroid disorder.",
    "vitamins_nutrition": "Use the stated food preference. Do not prescribe supplement doses.",
    "immunity_inflammation": "Keep inflammation measurements separate from oxidative-stress risk. Do not say a habit caused that score or that food alone will fix a marker.",
    "hormonal_health": "A predicted PCOS risk is not a diagnosis. Do not assume weight loss. Do not recommend hormone treatments.",
    "bone_mineral": "A normal blood calcium result does not prove bones are strong.",
    "cancer_related": "An abnormal marker does not confirm cancer and an in-range marker does not rule it out. Do not suggest lifestyle changes to lower a tumour marker.",
    "other_unmapped": "Do not invent a link between tests only because they share this category. Do not assume exercise caused CK or LDH.",
}


def _payload(detail: CategoryDetail, profile: CategoryProfile) -> dict:
    findings = []
    for item in detail.findings:
        findings.append({
            "name": item.name,
            "kind": "measured" if item.source_type == "measured" else "bio_ai",
            "status": item.status_label,
        })
    return {
        "category_id": detail.id,
        "focus": _FOCUS.get(detail.id, "Use only the findings supplied."),
        "age_band": profile.age_band,
        "sex": profile.sex,
        "findings": findings[:16],
        "reported_habits": [f"{factor.key}: {factor.value}" for factor in profile.factors[:8]],
    }


def _points(raw, *, purpose: bool) -> list[GuidancePoint]:
    out = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        text = " ".join(str(item.get("text") or "").split())
        if not text or len(text) > 220 or _NUMBER.search(text) or safety_problems(text):
            continue
        out.append(GuidancePoint(
            text=text,
            evidence_ids=[str(x) for x in (item.get("evidence_ids") or [])][:4],
            basis="" if purpose else str(item.get("basis") or "")[:48],
            purpose=str(item.get("purpose") or "")[:48] if purpose else "",
        ))
    return out[:3]


def _fit(raw: dict) -> CategoryGuidance:
    if not isinstance(raw, dict):
        return CategoryGuidance()
    return CategoryGuidance(
        influencing_factors=_points(raw.get("influencing_factors"), purpose=False),
        health_guidance=_points(raw.get("health_guidance"), purpose=True),
    )


def category_guidance(
    detail: CategoryDetail,
    profile: CategoryProfile,
    subject_id: str,
    *,
    allow_model: bool = False,
    client=None,
) -> CategoryGuidance:
    if detail.id in _SKIP or not allow_model or not detail.findings:
        return CategoryGuidance()
    payload = _payload(detail, profile)
    from app.biomarkers.medical_registry import library_revision
    from app.core.request_controls import request_controls
    from app.providers.cache import member_token

    material = json.dumps([GENERATION, library_revision(), detail.provenance.model_dump(mode="json"), payload], sort_keys=True, default=str)
    key = f"cura:category-guide:{member_token(subject_id)}:{hashlib.sha256(material.encode()).hexdigest()[:24]}"
    try:
        cached = request_controls._get(key)
        if cached:
            return _fit(json.loads(cached))
    except Exception:
        cached = None
    system = (
        "Write for an ordinary adult with no medical background, at a 12-year-old reading level. "
        "Use only the findings and reported habits in the data. A habit is something the person reported, not a proven cause. "
        "Never invent a habit, symptom, medicine or family history. If no habit was reported, do not pretend one was. "
        "Return at most three short sentences for influences and three for guidance. Omit a list rather than pad it. "
        "Do not write numbers. Do not give supplement doses. "
        'Return only JSON: {"influencing_factors":[{"text":"","evidence_ids":[],"basis":"verified_context_or_general_possibility"}],'
        '"health_guidance":[{"text":"","evidence_ids":[],"purpose":"maintain_improve_reduce_risk_or_medical_review"}]}'
    )
    try:
        if client is None:
            from app.llm.factory import get_llm_client

            client = get_llm_client(personal_health=True)
        text = client.complete(
            [{"role": "system", "content": system}, {"role": "user", "content": json.dumps(payload)}],
            json_mode=True,
        )
        start, end = text.find("{"), text.rfind("}")
        raw = json.loads(text[start : end + 1])
    except Exception as exc:
        logger.info("category_guidance_unavailable error=%s", type(exc).__name__)
        return CategoryGuidance()
    fitted = _fit(raw)
    try:
        request_controls._set(key, fitted.model_dump_json(), 7 * 24 * 3600)
    except Exception:
        pass
    return fitted
