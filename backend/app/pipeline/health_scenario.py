from __future__ import annotations

from collections import defaultdict

from app.contracts.bio_ai import BioAIReport
from app.contracts.blood import BloodReport
from app.contracts.common import MarkerFlag
from app.contracts.evidence import EvidenceRecord
from app.contracts.lifestyle import LifestyleContext
from app.contracts.scenario import HealthScenario, ScenarioItem, ScenarioTrend
from app.pipeline.trend_engine import comparison


class HealthScenarioEngine:
    """Builds the health scenario deterministically from canonical provider DTOs."""

    def build(
        self,
        blood_reports: list[BloodReport],
        bio_reports: list[BioAIReport],
        lifestyle: LifestyleContext | None,
    ) -> HealthScenario:
        scenario = HealthScenario()
        evidence: list[EvidenceRecord] = []
        marker_history: dict[str, list[tuple[BloodReport, object]]] = defaultdict(list)

        for report in sorted(blood_reports, key=lambda r: (r.report_date, r.report_id)):
            for marker in report.markers:
                marker_history[marker.key].append((report, marker))

        if blood_reports:
            latest = sorted(blood_reports, key=lambda r: (r.report_date, r.report_id))[-1]
            for marker in latest.markers:
                ev = self._evidence(
                    report_id=latest.report_id,
                    report_date=latest.report_date,
                    marker=marker.name,
                    value=marker.value,
                    unit=marker.unit,
                )
                evidence.append(ev)
                item = ScenarioItem(
                    code=marker.key,
                    title=marker.name,
                    detail=self._marker_detail(marker),
                    source="supershyft",
                    evidence_ids=[ev.evidence_id],
                )
                if marker.flag in {MarkerFlag.low, MarkerFlag.high, MarkerFlag.critical}:
                    scenario.needs_attention.append(item)
                    scenario.focus_areas.append(marker.name)
                elif marker.flag == MarkerFlag.normal:
                    scenario.going_well.append(item)
                else:
                    scenario.missing_information.append(f"{marker.name} lacks a usable reference status.")

        for key, rows in marker_history.items():
            if len(rows) < 2:
                continue
            previous_report, previous = rows[-2]
            current_report, current = rows[-1]
            result = comparison(
                key,
                previous.value,
                current.value,
                previous_report.report_id,
                current_report.report_id,
                previous_report.report_date,
                current_report.report_date,
            )
            scenario.trends.append(
                ScenarioTrend(
                    code=key,
                    name=current.name,
                    direction=result.direction or "stable",
                    previous_value=result.previous_value,
                    current_value=result.current_value,
                    unit=current.unit,
                )
            )

        if bio_reports:
            latest_bio = sorted(bio_reports, key=lambda r: (r.report_date, r.report_id))[-1]
            for risk in latest_bio.risks:
                ev = EvidenceRecord(
                    evidence_id=f"bio:{latest_bio.report_id}:{risk.code}",
                    report_id=latest_bio.report_id,
                    report_type="bio_ai_report",
                    report_date=latest_bio.report_date,
                    marker=risk.name,
                    risk_code=risk.code,
                    source="supershyft",
                    value=risk.score,
                )
                evidence.append(ev)
                detail = f"{risk.name} assessment score {risk.score}"
                if risk.status:
                    detail += f" ({risk.status})"
                scenario.risk_drivers.append(
                    ScenarioItem(
                        code=risk.code,
                        title=risk.name,
                        detail=detail + ". This is a risk assessment, not a diagnosis.",
                        source="supershyft",
                        evidence_ids=[ev.evidence_id],
                    )
                )

        if lifestyle:
            if lifestyle.activity_level:
                scenario.focus_areas.append("activity")
            if lifestyle.sleep_quality:
                scenario.focus_areas.append("sleep")
            if not lifestyle.notes and not lifestyle.activity_level and not lifestyle.sleep_quality:
                scenario.missing_information.append("Lifestyle information is not available.")
        else:
            scenario.missing_information.append("Lifestyle information is not available.")

        if not blood_reports:
            scenario.missing_information.append("No blood report is available.")
        if not bio_reports:
            scenario.missing_information.append("No Bio-AI report is available.")

        scenario.focus_areas = list(dict.fromkeys(scenario.focus_areas))[:6]
        scenario.going_well = scenario.going_well[:6]
        scenario.needs_attention = scenario.needs_attention[:6]
        scenario.risk_drivers = scenario.risk_drivers[:6]
        scenario.trends = scenario.trends[:6]
        scenario.evidence = evidence
        return scenario

    @staticmethod
    def _marker_detail(marker) -> str:
        value = "not available" if marker.value is None else f"{marker.value:g} {marker.unit or ''}".strip()
        return f"{marker.name}: {value}; report status {marker.flag.value}."

    @staticmethod
    def _evidence(*, report_id, report_date, marker, value, unit) -> EvidenceRecord:
        return EvidenceRecord(
            evidence_id=f"blood:{report_id}:{marker}",
            report_id=report_id,
            report_type="blood_report",
            report_date=report_date,
            marker=marker,
            source="supershyft",
            value=value,
            unit=unit,
        )
