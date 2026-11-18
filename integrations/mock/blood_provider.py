from app.auth.models import AuthenticatedPrincipal
from app.contracts.blood import BloodReport
from app.contracts.query import QueryPlan
from app.pipeline.lab_parameters import related_keys, distinct_neighbours
from app.pipeline.ontology import retrieval_metric_keys
from app.pipeline.personal_selection import retain_blood_reports
from integrations.mock.loader import load_json


class MockBloodProvider:
    def __init__(self) -> None:
        self._rows = load_json("blood_reports.json")

    def load_for_cache(self, principal: AuthenticatedPrincipal, scope: str) -> list[BloodReport]:
        """Load unfiltered member reports; a prior query must not poison later cache hits.

        Keep the mock's historical behavior of exposing all reports even for latest
        marker lookups. Production providers own their separate latest/history policy.
        """
        owned = [r for r in self._rows if r["subject_id"] == principal.subject_id]
        reports = [BloodReport.model_validate({k: v for k, v in r.items() if k != "subject_id"}) for r in owned]
        return sorted(reports, key=lambda r: (r.report_date, r.report_id))

    def apply_plan(self, reports: list[BloodReport], plan: QueryPlan) -> list[BloodReport]:
        reports = list(reports)
        if plan.report_id:
            reports = [report for report in reports if report.report_id == plan.report_id]
        wanted_keys = retrieval_metric_keys(plan)
        if wanted_keys:
            wanted = set(wanted_keys)
            for key in wanted_keys:
                wanted |= related_keys(key) | distinct_neighbours(key)
            reports = retain_blood_reports(reports, wanted)
        if plan.time_operation == "latest_report" and reports:
            return reports[-1:]
        if plan.history or plan.time_operation in {"latest_marker", "trend", "previous", "compare"}:
            return reports
        return reports[-1:] if reports else reports

    def query(self, principal: AuthenticatedPrincipal, plan: QueryPlan) -> list[BloodReport]:
        return self.apply_plan(self.load_for_cache(principal, "history" if plan.history else "latest"), plan)
