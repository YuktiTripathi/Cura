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
from app.contracts.blood import BloodMarker
from app.contracts.risk_status import risk_status_key
from app.pipeline.clinical_thresholds import clinical_note
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


def plain_measured_label(status: str, far: str | None) -> str:
    """Plain wording for a measured value. Distance only: it says how far outside the range, not how serious."""
    if status == "above_range":
        return {"slightly": "A little above range", "clearly": "Well above range"}.get(far or "", "Above range")
    if status == "below_range":
        return {"slightly": "A little below range", "clearly": "Well below range"}.get(far or "", "Below range")
    return _MEASURED_LABEL[status]


def _measured_finding(item: BiomarkerResult) -> Finding:
    status = _MEASURED_STATUS[item.status]
    far = how_far(item.value, item.reference_low, item.reference_high) if status in _OUT else None
    label = plain_measured_label(status, far)
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
    """Order for display only: a critical result, then a raised risk, then results outside range.
    How far a number sits from its range is never used. Within a tier the order is by name, which is not a ranking."""
    order = {"critical": 0, "risk_raised": 1, "above_range": 2, "below_range": 2}
    return (order.get(f.status, 9), f.name.lower())


def urgent_threshold_hit(item: BiomarkerResult) -> bool:
    """True when a guideline cut-off marks the result as one to raise with a doctor soon (see clinical_thresholds).
    These cut-offs are guideline thresholds, not laboratory reference ranges, and they have not had clinical sign off here."""
    if item.value is None:
        return False
    marker = BloodMarker(
        id=item.result_id, key=item.cura_key or item.canonical_id or item.display_name,
        name=item.display_name, value=item.value, unit=item.unit,
    )
    note = clinical_note(marker)
    return bool(note and note.urgent)


def decide_status(measured: list[Finding], risks: list[Finding], urgent: bool = False) -> CategoryStatus:
    """Fixed rules. Distance from a reference range never raises a status.
    Closer attention needs one of: a critical flag, a guideline urgent threshold, a Bio-AI class the report
    calls high or worse, or a blood result outside range together with a raised predicted risk."""
    out = [f for f in measured if f.status in _OUT]
    raised = [f for f in risks if f.status == "risk_raised"]
    assessed = [f for f in measured if f.status in {"within_range", *_OUT}] + [f for f in risks if f.status != "risk_unknown"]
    if not assessed:
        return "not_assessed"
    if urgent or any(f.status == "critical" for f in out):
        return "needs_closer_attention"
    if any(risk_status_key(f.classification) in _STRONG_RISK for f in raised):
        return "needs_closer_attention"
    if out and raised:
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
        return decide_status(self.measured, self.risks, urgent=any(urgent_threshold_hit(r) for r in self.raw_measured))

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


def _limitations(totals: OverviewTotals, bio: RiskOverview | None) -> list[str]:
    """Plain statements of what is missing. Each comes from a count, none from a guess."""
    out: list[str] = []
    if totals.blood_no_range:
        out.append(f"{totals.blood_no_range} blood result{'s have' if totals.blood_no_range != 1 else ' has'} no reference range, so {'they were' if totals.blood_no_range != 1 else 'it was'} not judged as in or out of range.")
    if totals.blood_unavailable:
        out.append(f"{totals.blood_unavailable} blood result{'s were' if totals.blood_unavailable != 1 else ' was'} not available.")
    if totals.risks_assessed == 0:
        out.append("No Bio-AI risk assessment is available, so nothing here is based on predicted risk.")
    if not (totals.blood_within or totals.blood_outside):
        out.append("No blood results with a reference range are available, so nothing here is based on measured results.")
    return out


def _versions() -> dict[str, str]:
    from app.health_explanation.relationship_engine import action_library, rules
    from app.pipeline.unified_wording import PROMPT_VERSION

    return {
        "categories": REGISTRY_VERSION,
        "relationships": rules()["rules_version"],
        "actions": action_library()["actions_version"],
        "wording": PROMPT_VERSION,
    }


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
        limitations=_limitations(totals, bio),
        versions=_versions(),
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
    from app.health_explanation.relationship_engine import build_relationships

    canonical = {r.result_id: r.canonical_id for r in p.raw_measured}
    relationships = build_relationships(category_id, card.scenario, p.measured, p.risks, canonical)
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
        relationships=relationships,
    )


def prepare(blood: BodySystemOverview | None, bio: RiskOverview | None):
    """Cards, the parts behind them and provenance: what the wording step needs."""
    parts = gather(blood, bio)
    cards = [_card(p, None) for p in parts.values()]
    return cards, parts, _provenance(blood, bio)
