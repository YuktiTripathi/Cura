from fastapi.testclient import TestClient

from app.contracts.common import AnswerDepth, IntentType, KnowledgeScope
from app.contracts.evidence import EvidenceRecord
from app.contracts.health_context import HealthContext, MissingItem
from app.main import app
from app.pipeline.provenance import build_user_provenance
from app.pipeline.query_planner import build_query_plan
from app.pipeline.renderer import DeterministicRenderer, render_missing_blood_marker
from app.providers.registry import set_registry
from integrations.supershyft.ihr import reset_ihr_cache

client = TestClient(app)
H1 = {"X-Cura-User-Id": "demo-user-001"}


def _names(body) -> list[str]:
    names = [item["name"] for item in (body.get("provenance") or {}).get("sources") or []]
    mapped = []
    for name in names:
        low = name.lower()
        if "blood report" in low:
            mapped.append("Blood Report")
        elif "bio-ai" in low or "bio ai" in low:
            mapped.append("Bio-AI Report")
        else:
            mapped.append(name)
    return mapped


def test_ldl_present_returns_value_and_blood_report_source():
    body = client.post("/api/v1/chat", headers=H1, json={"message": "What is my LDL?"}).json()
    assert "138" in body["answer"] or "142" in body["answer"]
    assert "not found" not in body["answer"].lower()
    assert "dyslipidemia" not in body["answer"].lower()
    assert _names(body) == ["Blood Report"]
    assert body["evidence"]
    assert any(item.get("report_type") == "blood_report" for item in body["evidence"])
    assert body["meta"]["llm_called"] is False
    assert body["meta"]["llm_mode"] == "structured_blood"


def test_present_lab_lookup_uses_the_model_when_enabled(monkeypatch):
    from app.core.config import settings
    from app.llm.models import LLMStructuredOutput
    from app.llm.openai_compatible import OpenAICompatibleLLMClient

    monkeypatch.setattr(settings, "enable_llm", True)
    calls = []

    def complete_structured(self, messages):
        calls.append(self.model)
        return LLMStructuredOutput(answer="The stored result is on your report.")

    monkeypatch.setattr(OpenAICompatibleLLMClient, "complete_structured", complete_structured)
    for message in ("What is my LDL?", "What is my HbA1c?"):
        body = client.post("/api/v1/chat", headers=H1, json={"message": message}).json()
        assert body["meta"]["llm_called"] is True
    missing = client.post("/api/v1/chat", headers=H1, json={"message": "What is my hemoglobin level?"}).json()
    assert missing["meta"]["llm_called"] is False
    assert missing["meta"]["llm_mode"] == "structured_blood"
    assert len(calls) == 2


def test_hba1c_present_returns_value_and_blood_report_source():
    body = client.post("/api/v1/chat", headers=H1, json={"message": "What is my HbA1c?"}).json()
    assert "5.5" in body["answer"] or "5.4" in body["answer"]
    assert "not found" not in body["answer"].lower()
    assert _names(body) == ["Blood Report"]
    assert body["meta"]["llm_called"] is False
    assert body["meta"]["llm_mode"] == "structured_blood"


def test_ferritin_absent_from_existing_blood_report():
    body = client.post("/api/v1/chat", headers=H1, json={"message": "What is my ferritin?"}).json()
    answer = body["answer"].lower()
    assert "ferritin" in answer
    assert "not available" in answer or "not present" in answer
    assert "Blood Report" not in _names(body)
    assert "dyslipidemia" not in answer


def test_chat_ldl_from_blood_bookings(monkeypatch):
    from app.core.config import settings
    from tests.unit.test_blood_bookings import _booking_row
    from tests.unit.test_ihr_live_schema import _live_row, _stub_profile

    monkeypatch.setattr(settings, "health_provider", "supershyft")
    monkeypatch.setattr(settings, "enable_llm", False)
    monkeypatch.setattr(settings, "jev_enabled", False)
    _stub_profile(monkeypatch)
    monkeypatch.setattr(
        "integrations.supershyft.ihr.fetch_ihr_rows",
        lambda principal: [_live_row(user_id=int(principal.subject_id))],
    )
    monkeypatch.setattr(
        "integrations.supershyft.blood.fetch_blood_booking_rows",
        lambda principal: [_booking_row(user_id=int(principal.subject_id))],
    )
    reset_ihr_cache()
    set_registry(None)
    try:
        body = client.post(
            "/api/v1/chat",
            headers={"X-Cura-User-Id": "2"},
            json={"message": "What is my LDL?"},
        ).json()
        assert "94.92" in body["answer"]
        assert "Blood Report" in _names(body)
        hba1c = client.post(
            "/api/v1/chat",
            headers={"X-Cura-User-Id": "2"},
            json={"message": "What is my HbA1c?"},
        ).json()
        assert "5.3" in hba1c["answer"]
        assert "Blood Report" in _names(hba1c)
    finally:
        set_registry(None)
        reset_ihr_cache()


def test_no_blood_report_does_not_claim_blood_source(monkeypatch):
    from app.core.config import settings
    from app.contracts.user import UserProfile
    from app.llm.models import LLMStructuredOutput
    from app.llm.openai_compatible import OpenAICompatibleLLMClient

    monkeypatch.setattr(settings, "health_provider", "supershyft")
    monkeypatch.setattr(settings, "enable_llm", True)
    monkeypatch.setattr(settings, "jev_enabled", False)
    monkeypatch.setattr(
        "integrations.supershyft.providers.SuperShyftUserProvider.get_profile",
        lambda self, principal: UserProfile(subject_id=str(principal.subject_id), display_name=""),
    )

    called = {"llm": 0}

    def boom(self, messages):
        called["llm"] += 1
        return LLMStructuredOutput(answer="Your LDL value was not found in the available data.")

    monkeypatch.setattr(OpenAICompatibleLLMClient, "complete_structured", boom)
    monkeypatch.setattr(
        "integrations.supershyft.ihr.fetch_ihr_rows",
        lambda principal: [
            {
                "report_id": 1,
                "user_id": int(principal.subject_id),
                "assessment_instance_id": 19,
                "engagement_id": 15,
                "reports": {
                    "diseases": [
                        {"code": "dyslipidemia", "name": "Dyslipidemia", "risk_score_scaled": 3}
                    ]
                },
                "created_at": None,
                "report_url": None,
            }
        ],
    )
    reset_ihr_cache()
    set_registry(None)
    try:
        for message in ("What is my LDL?", "What is my HbA1c?"):
            body = client.post(
                "/api/v1/chat",
                headers={"X-Cura-User-Id": "2"},
                json={"message": message},
            ).json()
            answer = body["answer"].lower()
            assert "no matching blood result is available" in answer
            assert "was not found in the available data" not in answer
            assert "3" not in body["answer"]
            assert "dyslipidemia" not in answer
            assert "Blood Report" not in _names(body)
            assert called["llm"] == 0
            assert body["meta"]["llm_called"] is False
            assert body["meta"]["llm_mode"] == "structured_blood"
    finally:
        set_registry(None)
        reset_ihr_cache()


def test_blood_report_without_ldl_says_not_present(monkeypatch):
    from app.core.config import settings
    from tests.unit.test_ihr_live_schema import _live_row, _stub_profile

    monkeypatch.setattr(settings, "health_provider", "supershyft")
    monkeypatch.setattr(settings, "enable_llm", False)
    monkeypatch.setattr(settings, "jev_enabled", False)
    _stub_profile(monkeypatch)
    monkeypatch.setattr(
        "integrations.supershyft.ihr.fetch_ihr_rows",
        lambda principal: [
            _live_row(
                user_id=int(principal.subject_id),
                reports={
                    "blood_report_raw": {
                        "digital_data": [
                            {"test_name": "HDL Cholesterol Direct", "value": "55", "unit": "mg/dl"},
                        ]
                    }
                },
            )
        ],
    )
    reset_ihr_cache()
    set_registry(None)
    try:
        body = client.post(
            "/api/v1/chat",
            headers={"X-Cura-User-Id": "2"},
            json={"message": "What is my LDL?"},
        ).json()
        assert "not available" in body["answer"].lower() or "not present" in body["answer"].lower()
        assert "55" not in body["answer"]
        assert "Blood Report" not in _names(body)
        hba1c = client.post(
            "/api/v1/chat",
            headers={"X-Cura-User-Id": "2"},
            json={"message": "What is my HbA1c?"},
        ).json()
        assert "not available" in hba1c["answer"].lower() or "not present" in hba1c["answer"].lower()
        assert "Blood Report" not in _names(hba1c)
    finally:
        set_registry(None)
        reset_ihr_cache()


def test_provenance_omits_blood_report_without_marker_fact():
    from datetime import date

    plan = build_query_plan("What is my LDL?")
    assert [item.name for item in build_user_provenance(plan, [], []).sources] == []
    evidence = [
        EvidenceRecord(
            evidence_id="ev-1",
            report_id="1",
            report_type="blood_report",
            report_date=date(2026, 9, 24),
            source="supershyft",
        )
    ]
    assert [item.name for item in build_user_provenance(plan, evidence, []).sources] == []


def test_missing_copy_distinguishes_no_report_vs_absent_marker():
    none = HealthContext(
        intent=IntentType.latest_result,
        answer_depth=AnswerDepth.simple,
        knowledge_scope=KnowledgeScope.personal,
        resolved_topic_name="LDL",
        missing=[MissingItem(key="ldl", name="LDL", reason="no_reports")],
    )
    assert render_missing_blood_marker(none) == "No matching blood result is available for LDL."
    absent = none.model_copy(
        update={"missing": [MissingItem(key="ldl", name="LDL", reason="not_in_reports")]}
    )
    assert "not available" in render_missing_blood_marker(absent).lower()
    rendered = DeterministicRenderer().render("What is my LDL?", none)
    assert rendered == "No matching blood result is available for LDL."
