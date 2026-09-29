from typing import Protocol

from app.auth.models import AuthenticatedPrincipal
from app.contracts.bio_ai import BioAIReport
from app.contracts.blood import BloodReport
from app.contracts.lifestyle import LifestyleContext
from app.contracts.query import QueryPlan
from app.contracts.user import UserProfile
from app.contracts.scenario import ScenarioContext


class UserProfileProvider(Protocol):
    def get_profile(self, principal: AuthenticatedPrincipal) -> UserProfile:
        ...


class BloodReportProvider(Protocol):
    def query(self, principal: AuthenticatedPrincipal, plan: QueryPlan) -> list[BloodReport]:
        ...


class BioAIProvider(Protocol):
    def query(self, principal: AuthenticatedPrincipal, plan: QueryPlan) -> list[BioAIReport]:
        ...


class LifestyleProvider(Protocol):
    def query(self, principal: AuthenticatedPrincipal, plan: QueryPlan) -> LifestyleContext | None:
        ...


class HealthScenarioProvider(Protocol):
    def query(self, principal: AuthenticatedPrincipal, plan: QueryPlan) -> ScenarioContext:
        ...

    def available_topics(self, principal: AuthenticatedPrincipal) -> list[str]:
        ...
