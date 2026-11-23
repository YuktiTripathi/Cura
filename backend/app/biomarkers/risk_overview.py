"""Bio-AI predicted-risk overview. A separate registry from the blood biomarker mapping.

Only risks the member's Bio-AI report actually returns are shown. A predicted risk is not a
measured blood value and not a diagnosis, and no risk is ever inferred from blood results.
"""

from __future__ import annotations

from app.contracts.risk_status import risk_status_key

import json
import re
from collections import defaultdict
from functools import lru_cache

from app.biomarkers.registry import DATA_DIR
from app.biomarkers.overview import ReportNotFound
from app.contracts.bio_ai import BioAIReport, BioAIRisk
from app.contracts.body_systems import (
    ReportRef,
    RiskGroupSummary,
    RiskHistoryPoint,
    RiskKeyFinding,
    RiskOverview,
    RiskReportRef,
    RiskResult,
    RiskTotals,
)

DISCLAIMER = (
    "These are predicted risks from your Bio-AI assessment. They are not measured blood results "
    "and they are not diagnoses."
)
OTHER_RISKS_ID = "other_risks"
OTHER_RISKS_NAME = "Other predicted risks"


@lru_cache(maxsize=1)
def _registry() -> dict:
    data = json.loads((DATA_DIR / "risk_registry_v1.json").read_text(encoding="utf-8"))
    group_of: dict[str, str] = {}
    names: dict[str, str] = {}
    for group in data["groups"]:
        names[group["id"]] = group["name"]
        for code in group["codes"]:
            if code in group_of:
                raise ValueError(f"risk code {code!r} appears in more than one group")
            group_of[code] = group["id"]
    data["_group_of"] = group_of
    data["_names"] = names
    data["_about"] = {group["id"]: group.get("about", "") for group in data["groups"]}
    data["_topic"] = {group["id"]: group.get("topic", "") for group in data["groups"]}
    data["_order"] = {group["id"]: index for index, group in enumerate(data["groups"])}
    data["_raised"] = {s.lower() for s in data["raised_statuses"]}
    data["_rank"] = {s.lower(): index for index, s in enumerate(data["status_order"])}
    return data


def _display(reg: dict, code: str, report_name: str | None) -> dict:
    """Everyday name first. A risk the registry does not know keeps the report's own name."""
    entry = (reg.get("display") or {}).get(code)
    if entry:
        return entry
    return {"name": report_name or code.replace("_", " ").title()}


def _code(risk: BioAIRisk) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (risk.code or risk.name or "").lower()).strip("_") or "risk"


def _day(value) -> str | None:
    return str(value)[:10] if value else None


def _level(status: str | None) -> str:
    if not status:
        return "unknown"
    return "raised" if risk_status_key(status) in _registry()["_raised"] else "not_raised"


def _collapse(risks: list[BioAIRisk]) -> tuple[list[tuple[BioAIRisk, int]], int]:
    """One entry per risk code. A repeat keeps the first one that has a score."""
    kept: dict[str, tuple[BioAIRisk, int]] = {}
    for risk in risks:
        code = _code(risk)
        if code not in kept:
            kept[code] = (risk, 0)
            continue
        current, repeats = kept[code]
        if current.score is None and risk.score is not None:
            current = risk
        kept[code] = (current, repeats + 1)
    return list(kept.values()), sum(repeats for _, repeats in kept.values())


def _ref(report: BioAIReport) -> ReportRef:
    return ReportRef(report_id=report.report_id, report_date=str(report.report_date), source_line=report.source_line)


def build_risk_overview(reports: list[BioAIReport], report_id: str | None = None) -> RiskOverview:
    reg = _registry()
    base = {"registry_version": str(reg["registry_version"]), "disclaimer": DISCLAIMER}
    ordered = sorted(reports or [], key=lambda r: (r.report_date, str(r.completed_at or ""), r.report_id))
    if not ordered:
        return RiskOverview(available=False, state="no_report", **base)
    refs = [_ref(r) for r in reversed(ordered)]
    if report_id:
        selected = next((r for r in ordered if r.report_id == report_id), None)
        if selected is None:
            raise ReportNotFound(report_id)
    else:
        selected = ordered[-1]
    same_day = any(r.report_id != selected.report_id and r.report_date == selected.report_date for r in ordered)
    ref = RiskReportRef(**_ref(selected).model_dump(), metabolic_age=selected.metabolic_age, metabolic_score=selected.metabolic_score)

    entries, repeats = _collapse(list(selected.risks or []))
    if not entries:
        return RiskOverview(
            available=True, state="no_results", report=ref, available_reports=refs, same_day_alternatives=same_day, **base
        )

    earlier = [r for r in ordered if r.report_date < selected.report_date]
    earlier_by_code: dict[str, list[tuple[str, BioAIRisk]]] = defaultdict(list)
    for report in earlier:
        collapsed, _ = _collapse(list(report.risks or []))
        for risk, _ in collapsed:
            earlier_by_code[_code(risk)].append((str(report.report_date), risk))

    results: list[RiskResult] = []
    for risk, repeated in entries:
        code = _code(risk)
        past = [
            RiskHistoryPoint(date=date, score=item.score, status=item.status)
            for date, item in earlier_by_code.get(code, [])
        ]
        previous = next((p for p in reversed(past) if p.score is not None), None)
        change = None
        if previous is not None and risk.score is not None:
            change = "unchanged" if risk.score == previous.score else "increased" if risk.score > previous.score else "decreased"
        measured = _day(risk.measured_at) or str(selected.report_date)
        history = past + [RiskHistoryPoint(date=measured, score=risk.score, status=risk.status)] if past else []
        results.append(
            RiskResult(
                code=code,
                name=risk.name or code.replace("_", " ").title(),
                group_id=reg["_group_of"].get(code, OTHER_RISKS_ID),
                score=risk.score,
                status=risk.status,
                level=_level(risk.status),
                about=str((reg.get("risk_about") or {}).get(code, "")),
                display_name=_display(reg, code, risk.name).get("name", ""),
                medical_name=_display(reg, code, risk.name).get("medical", ""),
                explain=_display(reg, code, risk.name).get("explain", ""),
                percentile=risk.percentile,
                lifestyle_contribution=risk.lifestyle_contribution,
                contributing_factors=list(risk.contributing_factors or []),
                measured_on=measured,
                report_id=risk.report_id or selected.report_id,
                previous_score=previous.score if previous else None,
                previous_on=previous.date if previous else None,
                change=change,
                history=history,
                duplicates_collapsed=repeated,
            )
        )

    by_group: dict[str, list[RiskResult]] = defaultdict(list)
    for item in results:
        by_group[item.group_id].append(item)
    groups: list[RiskGroupSummary] = []
    for group_id, items in by_group.items():
        breakdown: dict[str, int] = defaultdict(int)
        for item in items:
            breakdown[(item.status or "unknown").strip().lower() or "unknown"] += 1
        raised = [item for item in items if item.level == "raised"]
        raised.sort(key=lambda i: (reg["_rank"].get(risk_status_key(i.status), 99), -(i.score or 0), i.name.lower()))
        groups.append(
            RiskGroupSummary(
                id=group_id,
                name=reg["_names"].get(group_id, OTHER_RISKS_NAME),
                about=reg["_about"].get(group_id, reg.get("other_about", "")),
                topic=reg["_topic"].get(group_id, ""),
                risk_count=len(items),
                raised_count=len(raised),
                status_breakdown=dict(breakdown),
                key_findings=[RiskKeyFinding(code=i.code, name=i.name, score=i.score, status=i.status) for i in raised[:3]],
                risk_codes=[i.code for i in items],
                needs_mapping_review=group_id == OTHER_RISKS_ID,
            )
        )
    groups.sort(key=lambda g: (g.id == OTHER_RISKS_ID, g.raised_count == 0, reg["_order"].get(g.id, 999)))
    return RiskOverview(
        available=True,
        state="ready",
        report=ref,
        available_reports=refs,
        same_day_alternatives=same_day,
        totals=RiskTotals(
            risk_count=len(results), raised_count=sum(1 for r in results if r.level == "raised"), duplicates_collapsed=repeats
        ),
        groups=groups,
        risks=results,
        **base,
    )
