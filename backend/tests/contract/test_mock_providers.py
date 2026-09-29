from app.auth.models import AuthenticatedPrincipal
from app.contracts.bio_ai import BioAIReport
from app.contracts.blood import BloodReport
from app.contracts.query import QueryPlan
from app.contracts.common import IntentType, QuerySource
from integrations.mock.bio_ai_provider import MockBioAIProvider
from integrations.mock.blood_provider import MockBloodProvider
from integrations.mock.user_provider import MockUserProvider


def principal(uid="demo-user-001"):
    return AuthenticatedPrincipal(subject_id=uid, roles=["member"], consent_scopes=["health.read"])


def test_blood_provider_returns_canonical_dto():
    reports = MockBloodProvider().query(
        principal(),
        QueryPlan(intent=IntentType.latest_result, source=QuerySource.blood, topic="vitamin_d", needs_blood=True),
    )
    assert reports
    assert isinstance(reports[0], BloodReport)
    dumped = reports[0].model_dump()
    assert "raw" not in dumped
    assert "subject_id" not in dumped


def test_bio_ai_provider_canonical():
    reports = MockBioAIProvider().query(
        principal(),
        QueryPlan(intent=IntentType.bio_ai_score, source=QuerySource.bio_ai, topic="cardiac_health", needs_bio_ai=True),
    )
    assert all(isinstance(r, BioAIReport) for r in reports)
    assert {r.report_id for r in reports} == {"bioai-a", "bioai-b"}
    for r in reports:
        assert r.source_line in {"bio_ai", "advanced_bio_ai"}


def test_user_isolation_in_provider():
    a = MockBloodProvider().query(
        principal("demo-user-001"),
        QueryPlan(intent=IntentType.latest_result, source=QuerySource.blood, topic="vitamin_d"),
    )
    b = MockBloodProvider().query(
        principal("demo-user-002"),
        QueryPlan(intent=IntentType.latest_result, source=QuerySource.blood, topic="vitamin_d"),
    )
    assert {r.report_id for r in a} <= {"blood-001", "blood-002"}
    assert all(r.report_id.startswith("blood-j") or r.report_id == "blood-j-001" for r in b)
    assert 42.0 not in {m.value for r in a for m in r.markers}
    assert 12.6 not in {m.value for r in b for m in r.markers}


def test_profile_contract():
    profile = MockUserProvider().get_profile(principal())
    assert profile.subject_id == "demo-user-001"
    assert profile.display_name
