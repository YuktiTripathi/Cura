"""Narrative health summaries. Presentation only; does not change retrieval."""

from __future__ import annotations

import re

from app.contracts.common import IntentType, MarkerFlag
from app.contracts.health_context import HealthContext
from app.contracts.presentation import (
    HealthTheme,
    PresentedFinding,
    SummaryStyle,
    ThemePriority,
    ThemeStatus,
)
from app.contracts.query import QueryPlan
from app.pipeline.health_domains import DOMAINS, domain_for_entity
from app.pipeline.lab_parameters import canonicalize_marker_name, display_name_for

_FLAG_STATUS = {
    "normal": "in_range",
    "high": "high",
    "low": "low",
    "critical": "critical",
    "missing": "missing",
    "unknown": "unknown",
}

_NARRATIVE_ASK = re.compile(
    r"\b(summarize my health|health scenario|how am i doing|what should i focus|"
    r"what matters most|complete health|overall health|biggest health concerns|"
    r"review my (?:complete |full )?health|important findings|"
    r"bigger-picture|comprehensive overview)\b",
    re.I,
)
_VIEW_ALL = re.compile(
    r"\b(view all results|show all (?:my )?(?:results|values|markers)|full (?:report|table))\b",
    re.I,
)
_ROBOTIC = re.compile(
    r"prioritized findings from the latest blood report|in range \d+, out of range \d+",
    re.I,
)
_ABNORMAL = {MarkerFlag.high, MarkerFlag.low, MarkerFlag.critical, "high", "low", "critical"}
_DOMAIN_TITLE = {
    "glycemic_health": "Blood sugar",
    "metabolic_health": "Metabolic picture",
    "lipid_health": "Lipids",
    "cardiovascular_health": "Heart and circulation",
    "blood_pressure_health": "Blood pressure",
    "kidney_health": "Kidney health",
    "liver_health": "Liver health",
    "thyroid_health": "Thyroid health",
    "red_cell_anaemia_health": "Red cell and iron findings",
    "iron_status": "Iron status",
    "vitamin_b12_folate_status": "Vitamin B12 and folate",
    "vitamin_d_bone_mineral_health": "Vitamin D",
    "nutrition_micronutrient_health": "Micronutrients",
    "inflammation": "Inflammation",
    "white_cell_immune_profile": "White cells",
    "platelet_coagulation_health": "Platelets",
    "weight_body_composition": "Body composition",
    "lifestyle_recovery": "Lifestyle and recovery",
}

_MICRONUTRIENT = {"vitamin_d_bone_mineral_health", "vitamin_b12_folate_status", "iron_status"}
_LIPID_KEYS = {
    "ldl",
    "hdl",
    "cholesterol",
    "triglycerides",
    "vldl",
    "non_hdl",
    "apob",
    "apoa1",
    "lipoprotein_a",
}
_GAP_ASK = re.compile(r"\b(missing|gaps?|what information|not (?:have|available))\b", re.I)


def canonical_marker_key(marker) -> str:
    raw = getattr(marker, "key", None) or getattr(marker, "name", "") or ""
    return canonicalize_marker_name(raw) or canonicalize_marker_name(getattr(marker, "name", "") or "") or raw


def canonical_display_label(marker) -> str:
    key = canonical_marker_key(marker)
    raw = display_name_for(key) if key else (getattr(marker, "name", None) or "Result")
    return format_marker_name(raw)


_ACRONYMS = {
    "rdw", "cv", "sd", "mcv", "mch", "mchc", "hdl", "ldl", "vldl", "tsh", "t3", "t4",
    "esr", "alc", "anc", "wbc", "rbc", "ast", "alt", "crp", "bmi", "pcv", "plt", "hba1c",
    "egfr", "bun", "ggt", "sgot", "sgpt", "hb", "hgb",
}
_SUPERSCRIPTS = str.maketrans("0123456789+-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻")


def format_marker_name(name: str) -> str:
    """Title-case a lab label and keep short codes uppercase (RDW, MCV, ALC)."""
    parts = re.split(r"(\s+)", (name or "").strip())
    out: list[str] = []
    for part in parts:
        if not part or not part.strip():
            out.append(part)
            continue
        token = re.sub(r"[^a-z0-9]", "", part.lower())
        if token in _ACRONYMS:
            out.append(token.upper())
        elif part[:1].isupper() and not part.islower():
            out.append(part)
        else:
            out.append(part[:1].upper() + part[1:])
    return "".join(out)


def format_unit(unit: str | None) -> str | None:
    """Render caret exponents as superscripts: 10^3/uL → 10³/uL."""
    if not unit:
        return unit
    return re.sub(r"\^([0-9+\-]+)", lambda match: match.group(1).translate(_SUPERSCRIPTS), unit)


def wants_raw_snapshot(message: str | None, plan: QueryPlan | None = None) -> bool:
    text = message or (plan.raw_message if plan else "") or ""
    return bool(_VIEW_ALL.search(text))


def wants_narrative_summary(message: str | None, plan: QueryPlan | None = None) -> bool:
    text = message or (plan.raw_message if plan else "") or ""
    if wants_raw_snapshot(text, plan):
        return False
    if plan is not None:
        selectors = {str(item).upper() for item in (plan.selectors or [])}
        if selectors & {"HIGH", "LOW", "ABNORMAL", "ALL", "NORMAL"} and not _NARRATIVE_ASK.search(text):
            return False
        domains = list(plan.domains or [])
        specific = [code for code in domains if code not in {"overall_health", "energy_fatigue_context"}]
        if "overall_health" in domains:
            return True
        if plan.intent in {IntentType.health_scenario, IntentType.broad_health_summary} and not specific:
            return True
    return bool(_NARRATIVE_ASK.search(text))


def summary_style_for(message: str | None, plan: QueryPlan | None = None) -> SummaryStyle | None:
    if wants_raw_snapshot(message, plan):
        return SummaryStyle.raw_health_snapshot
    if wants_narrative_summary(message, plan):
        return SummaryStyle.narrative_health_summary
    return None


def dedupe_markers(markers: list) -> list:
    """Collapse alias keys/names onto one canonical biomarker with a measured value."""
    chosen: dict[str, object] = {}
    order: list[str] = []
    for marker in markers or []:
        key = canonical_marker_key(marker)
        if not key:
            continue
        current = chosen.get(key)
        if current is None:
            chosen[key] = marker
            order.append(key)
            continue
        if _usable(marker) and not _usable(current):
            chosen[key] = marker
        elif _usable(marker) and _usable(current) and _severity(marker) > _severity(current):
            chosen[key] = marker
    return [chosen[key] for key in order]


def dedupe_missing(items: list, present_keys: set[str]) -> list:
    """Drop missing aliases when the canonical biomarker is already present."""
    out = []
    seen: set[str] = set()
    for item in items or []:
        key = canonicalize_marker_name(getattr(item, "key", "") or getattr(item, "name", "") or "")
        if not key or key in present_keys or key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _number(value) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def finding_from_marker(marker, *, latest: bool = True) -> PresentedFinding:
    when = getattr(marker, "measured_at", None)
    value = None if getattr(marker, "value", None) is None else f"{marker.value}"
    flag = _flag(marker)
    dated = str(when)[:10] if when else None
    return PresentedFinding(
        label=canonical_display_label(marker),
        value=value,
        unit=format_unit(getattr(marker, "unit", None)),
        status=_FLAG_STATUS.get(flag, flag or "unknown"),
        source_type="blood_report",
        source_date=dated,
        source_id=getattr(marker, "report_id", None),
        canonical_key=canonical_marker_key(marker),
        numeric_value=_number(getattr(marker, "value", None)),
        reference_low=_number(getattr(marker, "reference_low", None)),
        reference_high=_number(getattr(marker, "reference_high", None)),
    )


def build_narrative_summary(
    context: HealthContext,
    *,
    plan: QueryPlan | None = None,
    message: str | None = None,
    llm_overall: str | None = None,
    llm_themes: list[dict] | None = None,
) -> tuple[str, list[HealthTheme], list[PresentedFinding], str | None]:
    markers = dedupe_markers(list(context.markers or []))
    raw = [finding_from_marker(marker, latest=True) for marker in markers]
    present = {canonical_marker_key(marker) for marker in markers}
    groups = _group_markers(markers)
    groups = _merge_related_groups(groups)
    themes = _themes_from_groups(groups, context, present, message or (plan.raw_message if plan else "") or "")
    if llm_themes:
        themes = _overlay_llm_wording(themes, llm_themes, markers, raw)
    extra_missing = _question_missing(message or (plan.raw_message if plan else "") or "", context, present)
    if extra_missing and themes:
        target = next((item for item in themes if item.status != ThemeStatus.reassuring), themes[0])
        target.missing_information = list(dict.fromkeys([*target.missing_information, *extra_missing]))[:3]
    overall = (llm_overall or "").strip()
    if overall and _ROBOTIC.search(overall):
        overall = ""
    if not overall:
        overall = _overall_summary(themes)
    next_action = next((item.next_step for item in themes if item.next_step), None)
    return overall, themes[:5], raw, next_action


def usable_llm_overview(text: str | None) -> str | None:
    value = (text or "").strip()
    if not value or _ROBOTIC.search(value) or value.lower().startswith("going well:"):
        return None
    if value.count(":") >= 8 and "\n" in value:
        return None
    first = value.split("\n\n")[0].strip()
    if len(first) > 600:
        first = first[:600].rsplit(" ", 1)[0]
    return first or None


def flatten_narrative(
    overall: str,
    themes: list[HealthTheme],
    next_action: str | None = None,
) -> str:
    """Lead text only. Theme cards already show each pattern, so values are not repeated here."""
    del themes
    parts = [overall.strip()] if overall else []
    if next_action and next_action.lower() not in (overall or "").lower():
        parts.append(next_action)
    return "\n\n".join(part for part in parts if part).strip()


def _usable(marker) -> bool:
    return getattr(marker, "value", None) is not None


def _flag(marker) -> str:
    value = getattr(getattr(marker, "flag", None), "value", getattr(marker, "flag", None))
    return str(value or "")


def _severity(marker) -> int:
    flag = _flag(marker)
    return {"critical": 3, "high": 2, "low": 2, "unknown": 1, "missing": 0, "normal": 0}.get(flag, 0)


def _abnormal(marker) -> bool:
    flag = _flag(marker)
    return flag in {"high", "low", "critical"} or getattr(marker, "flag", None) in _ABNORMAL


def _theme_code(key: str) -> str:
    if key in _LIPID_KEYS:
        return "lipid_health"
    domain = domain_for_entity(key)
    if domain:
        return domain.code
    lowered = key.replace("_", " ")
    tokens = set(lowered.split())
    if tokens & {"rdw", "hematocrit", "mch", "mcv", "mchc"} or any(
        token in lowered for token in ("rdw", "hematocrit", "haemoglobin", "hemoglobin")
    ):
        return "red_cell_anaemia_health"
    if tokens & {"neutrophil", "lymphocyte", "eosinophil", "monocyte", "basophil"} or any(
        token in lowered for token in ("neutrophil", "lymphocyte", "eosinophil", "monocyte", "basophil", "leukocyte", "leucocyte")
    ):
        return "white_cell_immune_profile"
    return "other"


def _group_markers(markers: list) -> dict[str, list]:
    groups: dict[str, list] = {}
    for marker in markers:
        code = _theme_code(canonical_marker_key(marker))
        groups.setdefault(code, []).append(marker)
    return groups


def _merge_related_groups(groups: dict[str, list]) -> dict[str, list]:
    merged: dict[str, list] = dict(groups)
    # Red-cell + iron abnormalities are one pattern, not separate alerts.
    if _abnormal_count(merged.get("red_cell_anaemia_health")) and _abnormal_count(merged.get("iron_status")):
        merged.setdefault("red_cell_anaemia_health", []).extend(merged.pop("iron_status", []))
    # Two or more micronutrient issues become one nutrition theme.
    micro_codes = [code for code in _MICRONUTRIENT if _abnormal_count(merged.get(code))]
    if len(micro_codes) >= 2:
        bucket: list = []
        for code in micro_codes:
            bucket.extend(merged.pop(code, []))
        merged.setdefault("nutrition_micronutrient_health", []).extend(bucket)
    return merged


def _abnormal_count(markers: list | None) -> int:
    return sum(1 for marker in markers or [] if _abnormal(marker))


def _themes_from_groups(
    groups: dict[str, list],
    context: HealthContext,
    present: set[str],
    message: str,
) -> list[HealthTheme]:
    scored: list[tuple[int, HealthTheme]] = []
    reassuring_labels: list[str] = []
    for code, markers in groups.items():
        abn = [marker for marker in markers if _abnormal(marker)]
        if not abn:
            if any(_flag(marker) == "normal" for marker in markers):
                reassuring_labels.append(_title(code))
            continue
        scored.append(_score_theme(code, markers, abn, context, present, message))
    scored.sort(key=lambda row: (-row[0], row[1].title))
    themes = [item for _, item in scored[:4]]
    if reassuring_labels:
        labels = list(dict.fromkeys(reassuring_labels))[:4]
        if len(labels) == 1:
            interpretation = f"{labels[0]} currently looks reassuring on the available measurements."
        else:
            interpretation = (
                ", ".join(labels[:-1]) + f", and {labels[-1]} currently look reassuring on the available measurements."
            )
        themes.append(
            HealthTheme(
                title="Areas that look reassuring",
                priority=ThemePriority.low,
                status=ThemeStatus.reassuring,
                interpretation=interpretation,
            )
        )
    return themes


def _score_theme(
    code: str,
    markers: list,
    abnormal: list,
    context: HealthContext,
    present: set[str],
    message: str,
) -> tuple[int, HealthTheme]:
    related = len(abnormal)
    persistent = _persistent(abnormal, context)
    bio_support = _bio_support(code, context)
    question_hit = 1 if code.replace("_", " ") in (message or "").lower() else 0
    score = 3 * related + (2 if related >= 2 else 0) + persistent + bio_support + question_hit
    from app.pipeline.priority import theme_priority_score

    flags = [_flag(marker) for marker in abnormal]
    score = theme_priority_score(
        code=code,
        abnormal_count=related,
        flags=flags,
        context=context,
        persistent=bool(persistent),
        missing=len(_relevant_missing(code, present, context)),
        question_hit=bool(question_hit),
    ) + (2 if related >= 2 else 0)
    if related >= 2 or persistent:
        priority = ThemePriority.high
    elif related == 1:
        priority = ThemePriority.medium
    else:
        priority = ThemePriority.low
    findings = [finding_from_marker(marker) for marker in abnormal]
    missing = _relevant_missing(code, present, context)
    if missing and related:
        status = ThemeStatus.uncertain
    elif related >= 2 or persistent:
        status = ThemeStatus.needs_attention
    else:
        status = ThemeStatus.monitor
    interpretation = _interpret(code, findings, persistent, bio_support)
    next_step = _next_step(code, related)
    ids = [str(getattr(marker, "id", None) or canonical_marker_key(marker)) for marker in abnormal]
    return score, HealthTheme(
        title=_title(code),
        priority=priority,
        status=status,
        supporting_fact_ids=ids,
        interpretation=interpretation,
        missing_information=missing,
        next_step=next_step,
        related_findings=findings,
    )


def _title(code: str) -> str:
    if code == "other":
        return "Other results"
    return _DOMAIN_TITLE.get(code, code.replace("_", " ").replace(" health", "").title())


def _persistent(markers: list, context: HealthContext) -> int:
    keys = {canonical_marker_key(marker) for marker in markers}
    for row in context.comparisons or []:
        topic = canonicalize_marker_name(getattr(row, "topic", "") or "")
        if topic in keys and getattr(row, "direction", None) in {"increased", "decreased", "stable"}:
            if getattr(row, "direction", None) != "improved":
                return 1
    return 0


def _bio_support(code: str, context: HealthContext) -> int:
    domain = next((item for item in DOMAINS if item.code == code), None)
    if not domain:
        return 0
    allowed = {item.lower() for item in domain.bioai_domains}
    if any((risk.code or "").lower() in allowed for risk in context.bio_ai_risks or []):
        return 1
    return 0


def _relevant_missing(code: str, present: set[str], context: HealthContext) -> list[str]:
    domain = next((item for item in DOMAINS if item.code == code), None)
    if not domain:
        return []
    wanted = set(domain.primary_entities) | set(domain.supporting_entities[:2])
    rows: list[str] = []
    for item in dedupe_missing(list(context.missing or []), present):
        key = canonicalize_marker_name(getattr(item, "key", "") or "")
        if key not in wanted or key in present:
            continue
        if getattr(item, "reason", None) in {"not_in_reports", "not_present", "no_reports"}:
            label = display_name_for(key)
            rows.append(f"{label} is not available in this report, which would help interpret this pattern.")
    return rows[:2]


def _question_missing(message: str, context: HealthContext, present: set[str]) -> list[str]:
    if not _GAP_ASK.search(message or ""):
        return []
    rows: list[str] = []
    for item in dedupe_missing(list(context.missing or []), present):
        if getattr(item, "reason", None) not in {"not_in_reports", "not_present", "no_reports"}:
            continue
        key = canonicalize_marker_name(getattr(item, "key", "") or "")
        if not key or key in present:
            continue
        label = display_name_for(key)
        rows.append(f"{label} is not available in the retrieved records.")
        if len(rows) >= 2:
            return rows
    for row in getattr(context, "source_outcomes", None) or []:
        status = getattr(getattr(row, "status", None), "value", getattr(row, "status", None))
        if str(status) not in {"empty", "unavailable"}:
            continue
        source = str(getattr(row, "source", "a source") or "a source").replace("_", " ")
        rows.append(f"{source} is not available for this review.")
        if len(rows) >= 2:
            return rows
    if not rows:
        rows.append("Some supporting details are not available in the retrieved records.")
    return rows[:2]


def _interpret(code: str, findings: list[PresentedFinding], persistent: int, bio_support: int) -> str:
    del code
    bits = []
    for item in findings[:4]:
        name = format_marker_name(item.label or "Result")
        unit = f" {format_unit(item.unit)}" if item.unit else ""
        status = (item.status or "").replace("_", " ")
        value = item.value if item.value is not None else "not available"
        bits.append(f"{name} is {value}{unit} ({status})" if status else f"{name} is {value}{unit}")
    lead = "; ".join(bits) + "."
    if persistent:
        lead += " The same pattern is also present across recent reports."
    if bio_support:
        lead += " The Bio-AI assessment points in a similar direction."
    return lead


def _next_step(code: str, related: int) -> str:
    title = _title(code).lower()
    if related >= 2:
        return f"The highest-yield next step is to review this {title} pattern with a clinician."
    return f"Consider asking a clinician whether this {title} finding needs follow-up."


def _overall_summary(themes: list[HealthTheme]) -> str:
    attention = [
        item
        for item in themes
        if item.status in {ThemeStatus.needs_attention, ThemeStatus.uncertain, ThemeStatus.monitor}
    ]
    reassuring = [item for item in themes if item.status == ThemeStatus.reassuring]
    if attention and reassuring:
        focus = attention[0].title
        return (
            f"Most of your major health areas look reassuring, but the main pattern that stands out is {focus}. "
            "This is a reading of your records, not a diagnosis."
        )
    if attention:
        return (
            f"The main pattern that stands out is {attention[0].title}. "
            "This is a reading of your records, not a diagnosis."
        )
    if reassuring:
        return "Most of the available measurements look reassuring."
    return "Here is a concise reading of the health records currently available."


def _overlay_llm_wording(
    themes: list[HealthTheme],
    raw: list[dict],
    markers: list,
    findings: list[PresentedFinding],
) -> list[HealthTheme]:
    """Keep the grouped cards, and replace their sentences with the model's wording when it stays on those results."""
    grounded = _ground_llm_themes(raw, markers, findings)
    used: set[int] = set()
    for theme in themes:
        if theme.status == ThemeStatus.reassuring:
            continue
        best_index = None
        best_score = 0
        theme_ids = set(theme.supporting_fact_ids)
        title_words = {word for word in re.split(r"\W+", theme.title.lower()) if len(word) > 2}
        for index, item in enumerate(grounded):
            if index in used:
                continue
            shared = theme_ids & set(item.supporting_fact_ids)
            words = {word for word in re.split(r"\W+", item.title.lower()) if len(word) > 2}
            score = len(shared) * 3 + len(title_words & words)
            if score > best_score:
                best_index, best_score = index, score
        if best_index is None or best_score <= 0:
            continue
        chosen = grounded[best_index]
        if not _wording_stays_on_findings(chosen.interpretation, theme.related_findings):
            continue
        theme.interpretation = chosen.interpretation
        if chosen.next_step:
            theme.next_step = chosen.next_step
        used.add(best_index)
    return themes


def _wording_stays_on_findings(text: str, findings: list[PresentedFinding]) -> bool:
    """Reject a sentence that introduces a measurement the card does not contain."""
    allowed: set[str] = set()
    for item in findings:
        if item.value is not None:
            allowed.add(str(item.value).rstrip("0").rstrip(".") if "." in str(item.value) else str(item.value))
            allowed.add(str(item.value))
    for number in re.findall(r"\d+(?:\.\d+)?", text or ""):
        if number not in allowed and number.lstrip("0") not in {value.lstrip("0") for value in allowed}:
            return False
    return True


def _ground_llm_themes(raw: list[dict], markers: list, findings: list[PresentedFinding]) -> list[HealthTheme]:
    id_to_key: dict[str, str] = {}
    for marker in markers:
        key = canonical_marker_key(marker)
        id_to_key[key] = key
        mid = str(getattr(marker, "id", "") or "")
        if mid:
            id_to_key[mid] = key
    by_key = {item.canonical_key: item for item in findings if item.canonical_key}
    out: list[HealthTheme] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        interpretation = str(item.get("interpretation") or "").strip()
        if not title or not interpretation:
            continue
        ids = []
        related = []
        for code in item.get("supporting_fact_ids") or []:
            key = id_to_key.get(str(code))
            if not key:
                continue
            ids.append(key)
            if key in by_key:
                related.append(by_key[key])
        try:
            priority = ThemePriority(str(item.get("priority") or "medium"))
        except ValueError:
            priority = ThemePriority.medium
        try:
            status = ThemeStatus(str(item.get("status") or "monitor"))
        except ValueError:
            status = ThemeStatus.monitor
        missing = [str(row).strip() for row in (item.get("missing_information") or []) if str(row).strip()]
        out.append(
            HealthTheme(
                title=title,
                priority=priority,
                status=status,
                supporting_fact_ids=ids,
                interpretation=interpretation,
                missing_information=missing[:2],
                next_step=str(item.get("next_step") or "").strip() or None,
                related_findings=related,
            )
        )
    return out[:5]
