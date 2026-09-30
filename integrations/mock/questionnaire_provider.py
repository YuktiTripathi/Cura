from app.auth.models import AuthenticatedPrincipal
from app.contracts.questionnaire import QuestionnaireAnswer, QuestionnaireInstance
from app.contracts.query import QueryPlan
from app.pipeline.questionnaire_topics import keys_for_plan
from integrations.mock.loader import load_json


class MockQuestionnaireProvider:
    def __init__(self) -> None:
        self._rows = load_json("questionnaires.json")

    def query(self, principal: AuthenticatedPrincipal, plan: QueryPlan) -> list[QuestionnaireInstance]:
        subject = (principal.subject_id or "").strip()
        wanted = keys_for_plan(plan.topic, plan.requested_metrics, plan.raw_message or "")
        wanted_set = set(wanted)
        keep_history = bool(plan.history or plan.compare or plan.time_operation in {"trend", "previous", "compare"})
        instances: list[QuestionnaireInstance] = []
        for row in self._rows:
            if row.get("subject_id") != subject:
                continue
            owned = []
            for raw in row.get("instances") or []:
                answers = [
                    QuestionnaireAnswer(
                        response_id=str(item["response_id"]),
                        assessment_instance_id=str(raw["assessment_instance_id"]),
                        question_id=str(item["question_id"]),
                        question_key=item["question_key"],
                        question=item["question"],
                        value=item.get("value"),
                        unit=item.get("unit"),
                        response_type=item.get("response_type") or "text",
                        recorded_at=raw.get("recorded_at"),
                        subject_id=subject,
                    )
                    for item in raw.get("answers") or []
                    if item.get("question_key") in wanted_set
                ]
                owned.append(
                    QuestionnaireInstance(
                        assessment_instance_id=str(raw["assessment_instance_id"]),
                        subject_id=subject,
                        package_code=raw.get("package_code"),
                        status=raw.get("status"),
                        recorded_at=raw.get("recorded_at"),
                        answers=answers,
                    )
                )
            owned.sort(key=lambda item: (str(item.recorded_at or ""), item.assessment_instance_id))
            if not keep_history:
                owned = owned[-1:]
            instances.extend(owned)
        return instances
