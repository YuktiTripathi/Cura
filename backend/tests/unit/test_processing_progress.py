from app.contracts.processing import ProcessingStage
from app.pipeline.observability import ProgressEmitter, request_family
from app.pipeline.query_planner import build_query_plan
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
H = {"X-Cura-User-Id": "demo-user-001"}


def test_progress_emitter_does_not_repeat_stage():
    emitter = ProgressEmitter()
    emitter.emit(ProcessingStage.planning)
    emitter.emit(ProcessingStage.planning)
    assert [item.stage for item in emitter.events] == [ProcessingStage.planning]


def test_request_family_followup_and_document():
    follow = build_query_plan("Why is that important?")
    assert request_family(follow, follow_up=True).value == "followup"
    doc = build_query_plan("What is my LDL in this uploaded report?", document_ids=["d1"])
    assert request_family(doc).value == "document"
    general = build_query_plan("What is hs-CRP?")
    assert request_family(general).value == "general"


def test_sse_progress_then_complete_without_delay():
    response = client.post(
        "/api/v1/chat/stream",
        headers={**H, "Idempotency-Key": "progress-1"},
        json={"message": "What is Vitamin D?"},
    )
    assert response.status_code == 200
    assert "event: progress" in response.text
    assert "PLANNING" in response.text or "CHECKING_MEDICAL_EVIDENCE" in response.text
    assert "event: complete" in response.text
    assert "Cura is thinking" not in response.text
    assert "PageIndex" not in response.text


def test_fast_lookup_is_not_padded_with_fake_stages():
    body = client.post("/api/v1/chat", headers=H, json={"message": "What is my Vitamin D?"}).json()
    assert body["answer"]
    timing = body["meta"].get("timing") or {}
    assert timing.get("total_ms") is not None
    assert timing["total_ms"] < 15000


def test_safety_chest_pain_still_blocks():
    body = client.post(
        "/api/v1/chat",
        headers=H,
        json={"message": "I have severe chest pain and difficulty breathing"},
    ).json()
    assert body["meta"]["status"] == "safety_block"
