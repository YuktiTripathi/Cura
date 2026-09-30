from __future__ import annotations

from app.contracts.blood import BloodReport
from app.contracts.facts import FactKind, ProvenancedFact
from app.contracts.goals import GOAL_LABELS, GOAL_METRICS, GoalProgress, HealthGoal
from app.pipeline.trend_engine import compute_trend


def compute_goal_progress(
    goals: list[HealthGoal],
    blood_reports: list[BloodReport] | None = None,
) -> list[GoalProgress]:
    reports = sorted(blood_reports or [], key=lambda r: (r.report_date, r.report_id))
    out: list[GoalProgress] = []
    for goal in goals:
        metrics = GOAL_METRICS.get(goal.goal_code, ())
        facts: list[ProvenancedFact] = []
        for key in metrics:
            hits: list[tuple[BloodReport, object]] = []
            for report in reports:
                for marker in report.markers:
                    if marker.key == key and marker.value is not None:
                        hits.append((report, marker))
            if len(hits) < 2:
                continue
            prev_report, prev = hits[-2]
            curr_report, curr = hits[-1]
            _delta, _pct, direction = compute_trend(prev.value, curr.value)
            facts.append(
                ProvenancedFact(
                    fact=key,
                    value=curr.value,
                    unit=curr.unit,
                    source=curr.source or "SuperShyft",
                    report_id=curr_report.report_id,
                    measured_at=curr_report.report_date,
                    fact_type=FactKind.measured_data,
                    subject_id=goal.subject_id,
                    notes=[f"previous={prev.value}", f"direction={direction}"],
                )
            )
        if not metrics:
            summary = (
                "This goal has no stored biomarker series in SuperShyft, so progress cannot be calculated."
            )
            out.append(
                GoalProgress(
                    goal_code=goal.goal_code,
                    label=goal.label or GOAL_LABELS.get(goal.goal_code, goal.goal_code),
                    status=goal.status,
                    summary=summary,
                    sufficient_history=False,
                    missing_metrics=list(metrics),
                )
            )
            continue
        if not facts:
            summary = "Not enough stored history to calculate progress for this goal."
            out.append(
                GoalProgress(
                    goal_code=goal.goal_code,
                    label=goal.label or GOAL_LABELS.get(goal.goal_code, goal.goal_code),
                    status=goal.status,
                    summary=summary,
                    sufficient_history=False,
                    missing_metrics=list(metrics),
                )
            )
            continue
        better = 0
        worse = 0
        improving: list[str] = []
        worsening: list[str] = []
        stable: list[str] = []
        for fact in facts:
            direction = next((n.split("=", 1)[-1] for n in fact.notes if n.startswith("direction=")), None)
            if fact.fact == "hdl":
                if direction == "increased":
                    better += 1
                    improving.append(fact.fact)
                elif direction == "decreased":
                    worse += 1
                    worsening.append(fact.fact)
                else:
                    stable.append(fact.fact)
            else:
                if direction == "decreased":
                    better += 1
                    improving.append(fact.fact)
                elif direction == "increased":
                    worse += 1
                    worsening.append(fact.fact)
                else:
                    stable.append(fact.fact)
        present = {fact.fact for fact in facts}
        missing = [key for key in metrics if key not in present]
        if better and not worse:
            overall = "improved"
        elif worse and not better:
            overall = "worsened"
        elif better or worse:
            overall = "mixed"
        else:
            overall = "unchanged"
        summary = (
            f"Progress for {goal.label} is {overall} based on {len(facts)} stored biomarker comparison(s)."
        )
        out.append(
            GoalProgress(
                goal_code=goal.goal_code,
                label=goal.label or GOAL_LABELS.get(goal.goal_code, goal.goal_code),
                status=goal.status,
                direction=overall,
                summary=summary,
                metrics=facts,
                sufficient_history=True,
                improving=improving,
                stable=stable,
                worsening=worsening,
                missing_metrics=missing,
            )
        )
    return out
