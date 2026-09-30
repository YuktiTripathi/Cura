"""Compact longitudinal health-story for the reasoner. Does not diagnose."""

from __future__ import annotations

from app.contracts.common import MarkerFlag
from app.contracts.health_context import HealthContext
from app.contracts.personalization import HealthStory, HealthStoryPattern, LongitudinalClass, PersonalBaseline
from app.pipeline.health_domains import domain_for_entity
from app.pipeline.lab_parameters import display_name_for

_ABNORMAL = {MarkerFlag.low, MarkerFlag.high, MarkerFlag.critical, "low", "high", "critical"}


def build_health_story(
    context: HealthContext,
    baselines: list[PersonalBaseline] | None = None,
) -> HealthStory:
    rows = baselines if baselines is not None else list(context.baselines or [])
    by_entity = {item.entity: item for item in rows}
    groups: dict[str, list[str]] = {}
    stable: list[str] = []
    improving: list[str] = []
    worsening: list[str] = []
    new_findings: list[str] = []
    returned: list[str] = []
    for marker in context.markers or []:
        key = marker.key
        if not key:
            continue
        domain = domain_for_entity(key)
        code = domain.code if domain else "other"
        flag = getattr(getattr(marker, "flag", None), "value", getattr(marker, "flag", None))
        baseline = by_entity.get(key)
        if flag in _ABNORMAL:
            groups.setdefault(code, []).append(key)
        elif str(flag) == "normal":
            if code not in stable:
                stable.append(code)
        if baseline:
            if baseline.classification in {
                LongitudinalClass.improved,
                LongitudinalClass.improved_but_still_abnormal,
                LongitudinalClass.returned_to_range,
            }:
                if key not in improving:
                    improving.append(key)
            if baseline.classification == LongitudinalClass.worsened:
                worsening.append(key)
            if baseline.classification == LongitudinalClass.newly_abnormal:
                new_findings.append(f"{key}_{baseline.latest_flag or 'abnormal'}")
            if baseline.classification == LongitudinalClass.returned_to_range:
                returned.append(key)
    persistent = [
        HealthStoryPattern(domain=code, supporting_entities=list(dict.fromkeys(keys))[:6])
        for code, keys in groups.items()
        if len(keys) >= 2
        or any(by_entity.get(key) and by_entity[key].persistent_abnormality for key in keys)
    ]
    missing = []
    profile_keys = {"bmi", "waist", "activity", "sleep", "diet"}
    for item in context.missing or []:
        key = getattr(item, "key", None) or ""
        if key in profile_keys:
            continue
        name = getattr(item, "name", None) or key
        if name:
            missing.append(str(name))
    if "ferritin" not in {m.key for m in context.markers or []} and any(
        m.key in {"hemoglobin", "mcv", "mch", "iron"} and str(getattr(getattr(m, "flag", None), "value", m.flag)) == "low"
        for m in context.markers or []
    ):
        if "ferritin" not in [display_name_for("ferritin")] and "ferritin" not in missing:
            missing.insert(0, "ferritin")
    return HealthStory(
        stable_reassuring=stable[:8],
        persistent_patterns=persistent[:4],
        improving=improving[:6],
        worsening=worsening[:6],
        new_findings=new_findings[:6],
        important_missing=list(dict.fromkeys(missing))[:6],
        returned_to_range=returned[:6],
    )
