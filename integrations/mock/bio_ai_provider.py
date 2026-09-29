from app.auth.models import AuthenticatedPrincipal
from app.contracts.bio_ai import BioAIReport
from app.contracts.query import QueryPlan
from integrations.mock.loader import load_json


class MockBioAIProvider:
    def __init__(self) -> None:
        self._rows = load_json("bio_ai_reports.json")

    def query(self, principal: AuthenticatedPrincipal, plan: QueryPlan) -> list[BioAIReport]:
        owned = [r for r in self._rows if r["subject_id"] == principal.subject_id]
        reports = [BioAIReport.model_validate({k: v for k, v in r.items() if k != "subject_id"}) for r in owned]
        reports.sort(key=lambda r: (r.report_date, r.report_id))
        if plan.report_id:
            reports = [report for report in reports if report.report_id == plan.report_id]
        return reports
