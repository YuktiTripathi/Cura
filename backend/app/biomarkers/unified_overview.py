"""Deterministic core of the unified health overview. No model call in this file.

It joins the blood body-system overview and the Bio-AI risk overview on their shared category
ids, copies every value from them, and decides each category's status by fixed rules. Wording
(summary, interpretation, actions, follow ups) comes from `Wording`, which is either the model's
text or the rules text in `unified_wording.py`. A status never depends on the wording.
"""

from __future__ import annotations

from collections import defaultdict

from app.biomarkers.health_categories import REGISTRY_VERSION, category_for
from app.contracts.body_systems import BiomarkerResult, BodySystemOverview, RiskOverview, RiskResult, SystemSummary
from app.contracts.unified_health import (
    CategoryCard,
    CategoryDetail,
    CategoryStatus,
    Completeness,
    Finding,
    MeasuredCounts,
    OverviewTotals,
    PrimaryAction,
    Provenance,
    RiskCounts,
    Scenario,
    UnifiedOverview,
)
from app.biomarkers.education import education_for, first_sentence
from app.pipeline.gap_words import how_far

STATUS_LABELS: dict[str, str] = {
    "looking_good": "Looking good",
    "worth_attention": "Worth paying attention to",
    "needs_closer_attention": "Needs closer attention",
    "not_assessed": "Not yet assessed",
}
_STATUS_RANK = {"needs_closer_attention": 0, "worth_attention": 1, "looking_good": 2, "not_assessed": 3}
_MEASURED_STATUS = {"normal": "within_range", "high": "above_range", "low": "below_range", "critical": "critical", "no_range": "no_range", "no_value": "no_value"}
_MEASURED_LABEL = {
    "within_range": "Within range",
    "above_range": "Above range",
    "below_range": "Below range",
    "critical": "Critical",
    "no_range": "No reference range",
    "no_value": "Unavailable",
}
_OUT = {"above_range", "below_range", "critical"}
# A predicted risk the report itself calls high is closer attention; a moderate one is worth attention.
_STRONG_RISK = {"critical", "very high", "high"}


def _measured_finding(item: BiomarkerResult) -> Finding:
    status = _MEASURED_STATUS[item.status]
    far = how_far(item.value, item.reference_low, item.reference_high) if status in _OUT else None
    label = _MEASURED_LABEL[status]
    if far == "slightly" and status != "critical":
        label = "Slightly " + ("high" if status == "above_range" else "low")
    note = education_for(item.canonical_id, item.original_name, item.display_name)
    return Finding(
        id=item.result_id,
        source_type="measured",
        explain=first_sentence(note.what_it_is) if note else "",
        education=note,
        name=item.display_name,
        medical_name=item.original_name if item.original_name != item.display_name else "",
        status=status,
        status_label=label,
        value=item.value,
        unit=item.unit,
        reference_low=item.reference_low,
        reference_high=item.reference_high,
        how_far=far,
        measured_on=item.measured_on,
        report_id=item.report_id,
        important=status in _OUT,
    )


def _risk_finding(risk: RiskResult) -> Finding:
    status = {"raised": "risk_raised", "not_raised": "risk_healthy"}.get(risk.level, "risk_unknown")
    label = {"risk_raised": f"{risk.status or 'Raised'} predicted risk", "risk_healthy": "Healthy predicted risk"}.get(status, "Risk not classified")
    name = risk.display_name or risk.name
    return Finding(
        id=f"risk:{risk.code}",
        source_type="predicted_risk",
        name=name,
        medical_name=risk.medical_name if risk.medical_name and risk.medical_name.lower() != name.lower() else "",
        explain=risk.explain or risk.about,
        status=status,
        status_label=label,
        score=risk.score,
        classification=risk.status,
        measured_on=risk.measured_on,
        report_id=risk.report_id,
        important=status == "risk_raised",
    )


def _rank(f: Finding) -> tuple:
    order = {"critical": 0, "risk_raised": 1, "above_range": 2, "below_range": 2}
    far = {"clearly": 0, "moderately": 1, "slightly": 2, None: 3}[f.how_far]
    return (order.get(f.status, 9), far, f.name.lower())


def decide_status(measured: list[Finding], risks: list[Finding]) -> CategoryStatus:
    """Fixed rules. Clinical significance counts, not how many results are abnormal."""
    out = [f for f in measured if f.status in _OUT]
    raised = [f for f in risks if f.status == "risk_raised"]
    assessed = [f for f in measured if f.status in {"within_range", *_OUT}] + [f for f in risks if f.status != "risk_unknown"]
    if not assessed:
        return "not_assessed"
    if any(f.status == "critical" for f in out):
        return "needs_closer_attention"
    if any((f.classification or "").strip().lower() in _STRONG_RISK for f in raised):
        return "needs_closer_attention"
    if any(f.how_far == "clearly" for f in out) or (out and raised):
        return "needs_closer_attention"
    if out or raised:
        return "worth_attention"
    return "looking_good"


def decide_scenario(measured: list[Finding], risks: list[Finding]) -> Scenario:
    assessed_blood = [f for f in measured if f.status in {"within_range", *_OUT}]
    assessed_risk = [f for f in risks if f.status != "risk_unknown"]
    out = any(f.status in _OUT for f in assessed_blood)
    raised = any(f.status == "risk_raised" for f in assessed_risk)
    if assessed_blood and assessed_risk:
        return {(False, False): "both_reassuring", (True, False): "blood_out_risk_ok", (False, True): "blood_ok_risk_up", (True, True): "both_out"}[(out, raised)]
    if assessed_blood:
        return "blood_only"
    if assessed_risk:
        return "risk_only"
    return "incomplete" if measured or risks else "none"


def _counts(measured: list[Finding]) -> MeasuredCounts:
    c = MeasuredCounts()
    for f in measured:
        if f.status == "no_value":
            c.unavailable += 1
            continue
        c.total += 1
        if f.status == "within_range":
            c.within_range += 1
        elif f.status in _OUT:
            c.outside_range += 1
        else:
            c.no_range += 1
    return c


def _plural(n: int, one: str, many: str | None = None) -> str:
    return f"{n} {one if n == 1 else (many or one + 's')}"


def _count_line(m: MeasuredCounts, r: RiskCounts) -> str:
    parts = []
    shown = m.total + m.unavailable if m.total == 0 else m.total
    if shown:
        parts.append(_plural(shown, "blood test"))
    if r.assessed:
        parts.append(_plural(r.assessed, "risk") + " assessed")
    return " · ".join(parts)


def _detail_line(m: MeasuredCounts, r: RiskCounts, risks: list[Finding]) -> str:
    parts = []
    if m.outside_range:
        parts.append(_plural(m.outside_range, "blood result") + " outside range")
    raised = [f for f in risks if f.status == "risk_raised"]
    if raised:
        parts.append((raised[0].name + " risk") if len(raised) == 1 else f"{len(raised)} risks raised")
    if m.unavailable:
        parts.append(f"{m.unavailable} unavailable")
    if m.no_range:
        parts.append(f"{m.no_range} without a reference range")
    if not parts and (m.within_range or r.assessed):
        parts.append("All assessed results in range" if not r.raised else "")
    return " · ".join(p for p in parts if p)


def _completeness(m: MeasuredCounts, r: RiskCounts, system: SystemSummary | None) -> Completeness:
    if not (m.total or r.assessed):
        return "none"
    partial = bool(m.unavailable or m.no_range) or bool(system and any(g.partial for g in system.group_coverage))
    return "partial" if partial else "complete"


def _provenance(blood: BodySystemOverview | None, bio: RiskOverview | None) -> Provenance:
    b = blood.report if blood and blood.available else None
    a = bio.report if bio and bio.available else None
    return Provenance(
        blood_report_id=b.report_id if b else None,
        blood_report_date=b.report_date if b else None,
        bio_ai_report_id=a.report_id if a else None,
        bio_ai_report_date=a.report_date if a else None,
        reports_linked=False,
        dates_differ=bool(a and b and a.report_date != b.report_date),
    )


class _Parts:
    """Everything the rules know about one category before wording is applied."""

    def __init__(self, cid: str):
        self.cid = cid
        self.meta = category_for(cid)
        self.system: SystemSummary | None = None
        self.measured: list[Finding] = []
        self.risks: list[Finding] = []
        self.raw_measured: list[BiomarkerResult] = []

    @property
    def status(self) -> CategoryStatus:
        return decide_status(self.measured, self.risks)

    @property
    def scenario(self) -> Scenario:
        return decide_scenario(self.measured, self.risks)


def gather(blood: BodySystemOverview | None, bio: RiskOverview | None) -> dict[str, _Parts]:
    parts: dict[str, _Parts] = {}
    if blood and blood.available:
        systems = {s.id: s for s in blood.systems}
        by_system: dict[str, list[BiomarkerResult]] = defaultdict(list)
        for r in blood.results:
            if r.system_id != "allergy":
                by_system[r.system_id].append(r)
        for sid, rows in by_system.items():
            p = parts.setdefault(sid, _Parts(sid))
            p.system = systems.get(sid)
            p.raw_measured = rows
            p.measured = [_measured_finding(r) for r in rows if not r.is_derived or r.status != "no_value"]
    if bio and bio.available:
        for risk in bio.risks:
            p = parts.setdefault(risk.group_id, _Parts(risk.group_id))
            p.risks.append(_risk_finding(risk))
    parts.pop("sleep_recovery", None) if not (parts.get("sleep_recovery") and parts["sleep_recovery"].measured) else None
    return parts


def _card(p: _Parts, wording: dict | None) -> CategoryCard:
    m = _counts(p.measured)
    r = RiskCounts(assessed=sum(1 for f in p.risks if f.status != "risk_unknown"), raised=sum(1 for f in p.risks if f.status == "risk_raised"))
    status = p.status
    important = [f.model_copy(update={"education": None}) for f in sorted([f for f in p.measured + p.risks if f.important], key=_rank)[:3]]
    summary = (wording or {}).get("summary", "")
    return CategoryCard(
        id=p.cid,
        name=p.meta.name,
        icon=p.meta.icon,
        description=p.meta.description,
        status=status,
        status_label=STATUS_LABELS[status],
        completeness=_completeness(m, r, p.system),
        scenario=p.scenario,
        summary=summary,
        important_findings=important,
        measured=m,
        risks=r,
        count_line=_count_line(m, r),
        detail_line=_detail_line(m, r, p.risks),
        primary_action=PrimaryAction(label=p.meta.action_label, question=f"What do my {p.meta.topic} results mean for me?"),
    )


def build_unified_overview(blood: BodySystemOverview | None, bio: RiskOverview | None, wording: "Wording | None" = None) -> UnifiedOverview:
    from app.pipeline.unified_wording import Wording, rules_wording

    parts = gather(blood, bio)
    prov = _provenance(blood, bio)
    if not parts:
        return UnifiedOverview(available=False, state="no_reports", provenance=prov, registry_version=REGISTRY_VERSION)
    cards = [_card(p, None) for p in parts.values()]
    cards.sort(key=lambda c: (c.id in {"other_unmapped", "other_risks"}, _STATUS_RANK[c.status], category_for(c.id).order))
    w: Wording = wording or rules_wording(cards, parts, prov)
    for card in cards:
        card.summary = w.categories.get(card.id, {}).get("summary") or rules_wording([card], parts, prov).categories[card.id]["summary"]
    totals = OverviewTotals(
        blood_within=sum(c.measured.within_range for c in cards),
        blood_outside=sum(c.measured.outside_range for c in cards),
        blood_no_range=sum(c.measured.no_range for c in cards),
        blood_unavailable=sum(c.measured.unavailable for c in cards),
        risks_assessed=sum(c.risks.assessed for c in cards),
        risks_raised=sum(c.risks.raised for c in cards),
        metabolic_age=bio.report.metabolic_age if bio and bio.available and bio.report else None,
    )
    return UnifiedOverview(
        available=True,
        state="ready",
        opening=w.opening,
        totals=totals,
        priorities=w.priorities,
        categories=cards,
        provenance=prov,
        registry_version=REGISTRY_VERSION,
        insights_source=w.source,
    )


def build_category_detail(category_id: str, blood: BodySystemOverview | None, bio: RiskOverview | None, wording: "Wording | None" = None) -> CategoryDetail | None:
    from app.pipeline.unified_wording import rules_wording

    parts = gather(blood, bio)
    p = parts.get(category_id)
    if p is None:
        return None
    prov = _provenance(blood, bio)
    card = _card(p, None)
    fallback = rules_wording([card], parts, prov, detail=True)
    mine = (wording.categories.get(category_id) if wording else None) or {}
    base = fallback.categories[category_id]

    def pick(key):
        return mine.get(key) or base.get(key)

    findings = sorted(p.measured + p.risks, key=lambda f: (f.status in {"no_value"}, _rank(f)))
    from app.contracts.unified_health import ActionItem

    actions = [ActionItem(**a) for a in (pick("actions") or [])][:4]
    return CategoryDetail(
        **{**card.model_dump(), "summary": pick("summary")},
        about=pick("about") or p.meta.about,
        findings=findings,
        interpretation=list(pick("interpretation") or []),
        insight=pick("insight") or "",
        actions=actions,
        follow_ups=list(pick("follow_ups") or [])[:4],
        context=list(mine.get("context") or []),
        provenance=prov,
        caveat=p.system.caveat if p.system else None,
    )


def prepare(blood: BodySystemOverview | None, bio: RiskOverview | None):
    """Cards, the parts behind them and provenance: what the wording step needs."""
    parts = gather(blood, bio)
    cards = [_card(p, None) for p in parts.values()]
    return cards, parts, _provenance(blood, bio)
