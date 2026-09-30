from dataclasses import dataclass

from app.auth.interface import AuthProvider
from app.auth.mock import MockAuthProvider
from app.core.config import settings
from app.core.errors import ProviderUnavailableError
from app.providers.interfaces import (
    BioAIProvider,
    BloodReportProvider,
    HealthScenarioProvider,
    LifestyleProvider,
    QuestionnaireProvider,
    UserProfileProvider,
)
from app.providers.scenario import CompositeHealthScenarioProvider


@dataclass
class ProviderRegistry:
    auth: AuthProvider
    users: UserProfileProvider
    blood: BloodReportProvider
    bio_ai: BioAIProvider
    lifestyle: LifestyleProvider
    questionnaires: QuestionnaireProvider
    scenarios: HealthScenarioProvider


_registry: ProviderRegistry | None = None


def get_registry() -> ProviderRegistry:
    global _registry
    if _registry is None:
        _registry = build_registry()
    return _registry


def set_registry(registry: ProviderRegistry | None) -> None:
    global _registry
    _registry = registry


def build_registry() -> ProviderRegistry:
    from app.core.invariants import assert_safe_auth_health_pairing

    assert_safe_auth_health_pairing(settings)
    health = (settings.health_provider or "mock").strip().lower()
    auth_name = (settings.auth_provider or "mock").strip().lower()
    if auth_name == "mock":
        auth = MockAuthProvider()
    elif auth_name in {"jwt", "supershyft_jwt"}:
        from app.auth.jwt import SuperShyftJWTAuthProvider

        auth = SuperShyftJWTAuthProvider()
    else:
        raise ProviderUnavailableError(f"Unknown AUTH_PROVIDER={settings.auth_provider}")

    if health in {"supershyft", "postgres", "readonly"}:
        from integrations.supershyft.providers import (
            SuperShyftBioAIProvider,
            SuperShyftBloodProvider,
            SuperShyftLifestyleProvider,
            SuperShyftUserProvider,
        )

        users = SuperShyftUserProvider()
        blood = SuperShyftBloodProvider()
        bio_ai = SuperShyftBioAIProvider()
        lifestyle = SuperShyftLifestyleProvider()
        from integrations.supershyft.questionnaire import SuperShyftQuestionnaireProvider

        questionnaires = SuperShyftQuestionnaireProvider()
        return ProviderRegistry(
            auth=auth,
            users=users,
            blood=blood,
            bio_ai=bio_ai,
            lifestyle=lifestyle,
            questionnaires=questionnaires,
            scenarios=CompositeHealthScenarioProvider(blood, bio_ai, lifestyle),
        )

    if health != "mock":
        raise ProviderUnavailableError(f"Unknown HEALTH_PROVIDER={settings.health_provider}")

    from integrations.mock.bio_ai_provider import MockBioAIProvider
    from integrations.mock.blood_provider import MockBloodProvider
    from integrations.mock.lifestyle_provider import MockLifestyleProvider
    from integrations.mock.questionnaire_provider import MockQuestionnaireProvider
    from integrations.mock.user_provider import MockUserProvider

    users = MockUserProvider()
    blood = MockBloodProvider()
    bio_ai = MockBioAIProvider()
    lifestyle = MockLifestyleProvider()
    questionnaires = MockQuestionnaireProvider()
    return ProviderRegistry(
        auth=auth,
        users=users,
        blood=blood,
        bio_ai=bio_ai,
        lifestyle=lifestyle,
        questionnaires=questionnaires,
        scenarios=CompositeHealthScenarioProvider(blood, bio_ai, lifestyle),
    )
