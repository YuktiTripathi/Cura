from __future__ import annotations

from app.contracts.health_context import Comparison
from app.contracts.insights import InsightCandidate


def build_insight_candidates(
    *,
    changes: list[Comparison] | None = None,
    missing: list[str] | None = None,
) -> list[InsightCandidate]:
    """Derived candidates for snapshot/API consumers. Never auto-injected into chat."""
    out: list[InsightCandidate] = []
    for row in changes or []:
        if row.direction in {None, "unavailable", "unchanged"}:
            continue
        if row.previous_value is None or row.current_value is None:
            continue
        out.append(
            InsightCandidate(
                insight_type="biomarker_change",
                topic=row.topic,
                summary=(
                    f"{row.topic} {row.direction} from {row.previous_value} to {row.current_value}"
                ),
                direction=row.direction,
                report_ids=[item for item in (row.previous_report_id, row.current_report_id) if item],
            )
        )
    if any(item == "questionnaire" or item.endswith("questionnaire") for item in (missing or [])):
        out.append(
            InsightCandidate(
                insight_type="overdue_assessment",
                topic="questionnaire",
                summary="No questionnaire data is stored for this user yet.",
                delivery="on_request",
            )
        )
    return out[:12]
