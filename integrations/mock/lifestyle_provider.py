from app.auth.models import AuthenticatedPrincipal
from app.contracts.lifestyle import LifestyleContext
from app.contracts.query import QueryPlan
from integrations.mock.loader import load_json


class MockLifestyleProvider:
    def __init__(self) -> None:
        self._rows = load_json("lifestyle.json")

    def query(self, principal: AuthenticatedPrincipal, plan: QueryPlan) -> LifestyleContext | None:
        for row in self._rows:
            if row["subject_id"] == principal.subject_id:
                return LifestyleContext.model_validate(row)
        return None
