"""Read-only SuperShyft questionnaire responses. Always scoped to principal user_id."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import text

from app.auth.models import AuthenticatedPrincipal
from app.contracts.questionnaire import QuestionnaireAnswer, QuestionnaireInstance
from app.contracts.query import QueryPlan
from app.core.errors import ProviderUnavailableError
from app.pipeline.questionnaire_topics import keys_for_plan
from integrations.supershyft.db import DB_QUERY_FAILED, run_readonly
from integrations.supershyft.ihr import _user_id

_RESPONSE_SELECT = text(
    """
    SELECT
        qr.response_id,
        qr.assessment_instance_id,
        qr.question_id,
        qr.answer,
        qr.category_ids,
        qr.is_carried_forward,
        ai.user_id,
        ai.status,
        ai.completed_at,
        ai.assigned_at,
        ai.package_id,
        qd.question_key,
        qd.question_text,
        qd.question_type,
        ap.package_code
    FROM questionnaire_responses qr
    JOIN assessment_instances ai
      ON ai.assessment_instance_id = qr.assessment_instance_id
    JOIN questionnaire_definitions qd
      ON qd.question_id = qr.question_id
    LEFT JOIN assessment_packages ap
      ON ap.package_id = ai.package_id
    WHERE ai.user_id = :uid
    ORDER BY ai.completed_at ASC NULLS FIRST, ai.assessment_instance_id ASC, qr.response_id ASC
    """
)

_OPTIONS_SELECT = text(
    """
    SELECT question_id, option_value, display_name
    FROM questionnaire_options
    """
)

# Metsights lab-like questionnaire categories. Excluded unless explicitly requested.
_LAB_LIKE_CATEGORIES = {6, 7}

_option_cache: dict[tuple[int, str], str] | None = None


def _options() -> dict[tuple[int, str], str]:
    global _option_cache
    if _option_cache is not None:
        return _option_cache
    rows = run_readonly(_OPTIONS_SELECT) or []
    _option_cache = {}
    for row in rows:
        _option_cache[(int(row["question_id"]), str(row["option_value"]))] = row["display_name"]
    return _option_cache


def _display_value(question_id: int, answer, question_type: str) -> tuple[str | float | None, str | None]:
    if isinstance(answer, dict):
        return answer.get("value"), answer.get("unit")
    options = _options()
    if isinstance(answer, list):
        labels = [options.get((question_id, str(item)), str(item)) for item in answer]
        return ", ".join(labels), None
    if answer is None:
        return None, None
    if question_type in {"single_choice", "multiple_choice"}:
        return options.get((question_id, str(answer)), str(answer)), None
    return str(answer), None


def _as_recorded(value) -> date | datetime | str | None:
    if value is None:
        return None
    if isinstance(value, (date, datetime)):
        return value
    return str(value)


def _completed(row: dict) -> bool:
    if row.get("completed_at") is not None:
        return True
    status = row.get("status")
    if status in {2, "2"}:
        return True
    return str(status or "").strip().lower() in {"completed", "complete"}


def fetch_questionnaire_instances(
    principal: AuthenticatedPrincipal,
    plan: QueryPlan,
) -> list[QuestionnaireInstance]:
    uid = _user_id(principal)
    rows = run_readonly(_RESPONSE_SELECT, {"uid": uid}) or []
    owned = [row for row in rows if int(row.get("user_id") or 0) == uid]
    completed = [row for row in owned if _completed(row)]
    if not completed:
        return []

    by_instance: dict[int, list[dict]] = {}
    for row in completed:
        by_instance.setdefault(int(row["assessment_instance_id"]), []).append(row)
    ordered_ids = sorted(
        by_instance,
        key=lambda iid: (
            str(by_instance[iid][0].get("completed_at") or ""),
            iid,
        ),
    )
    if not (plan.history or plan.compare or plan.time_operation in {"trend", "previous", "compare"}):
        ordered_ids = ordered_ids[-1:]

    wanted = keys_for_plan(plan.topic, plan.requested_metrics, plan.raw_message or "")
    wanted_set = set(wanted)

    instances: list[QuestionnaireInstance] = []
    for instance_id in ordered_ids:
        answers: list[QuestionnaireAnswer] = []
        header = by_instance[instance_id][0]
        for row in by_instance[instance_id]:
            categories = _category_ids(row.get("category_ids"))
            if set(categories) & _LAB_LIKE_CATEGORIES and row["question_key"] not in wanted_set:
                continue
            if row["question_key"] not in wanted_set:
                continue
            value, unit = _display_value(int(row["question_id"]), row.get("answer"), row.get("question_type") or "")
            answers.append(
                QuestionnaireAnswer(
                    response_id=str(row["response_id"]),
                    assessment_instance_id=str(row["assessment_instance_id"]),
                    question_id=str(row["question_id"]),
                    question_key=row["question_key"],
                    question=row["question_text"],
                    value=value,
                    unit=unit,
                    response_type=row["question_type"],
                    category_keys=[str(item) for item in categories],
                    recorded_at=_as_recorded(row.get("completed_at") or row.get("assigned_at")),
                    subject_id=str(uid),
                    is_carried_forward=bool(row.get("is_carried_forward")),
                )
            )
        instances.append(
            QuestionnaireInstance(
                assessment_instance_id=str(instance_id),
                subject_id=str(uid),
                package_id=str(header["package_id"]) if header.get("package_id") is not None else None,
                package_code=header.get("package_code"),
                status=None if header.get("status") is None else str(header.get("status")),
                recorded_at=_as_recorded(header.get("completed_at") or header.get("assigned_at")),
                answers=answers,
            )
        )
    return instances


def _category_ids(raw) -> list[int]:
    if raw is None:
        return []
    if isinstance(raw, str):
        return [int(part) for part in raw.strip("{}[]").split(",") if part.strip().lstrip("-").isdigit()]
    out: list[int] = []
    for item in raw:
        try:
            out.append(int(item))
        except (TypeError, ValueError):
            continue
    return out


class SuperShyftQuestionnaireProvider:
    def query(self, principal: AuthenticatedPrincipal, plan: QueryPlan) -> list[QuestionnaireInstance]:
        if not (principal.subject_id or "").strip():
            raise ProviderUnavailableError("Authenticated user required", reason=DB_QUERY_FAILED)
        return fetch_questionnaire_instances(principal, plan)
