import io
from datetime import date

from fastapi.testclient import TestClient

from app.contracts.common import KnowledgeScope
from app.core.config import settings
from app.documents.value_extraction import extract_marker_from_text
from app.main import app
from app.pipeline.cross_source import CrossSourceComparator, SourceValue, render_comparison
from app.pipeline.query_planner import build_query_plan
from tests.helpers.pdf_fixtures import make_text_pdf

H = {"X-Cura-User-Id": "demo-user-001"}
client = TestClient(app)

HBA1C_PDF = make_text_pdf(
    ["Lipid Profile HbA1c: 6.2 % Collection date: 20 Aug 2026 LDL cholesterol 150 mg/dL Reference Range 0-100"]
)


def test_routing_supershyft_only():
    plan = build_query_plan("What does my latest SuperShyft report say about HbA1c?")
    assert plan.needs_supershyft
    assert not plan.needs_user_uploaded
    assert not plan.needs_cross_source


def test_routing_document_only():
    plan = build_query_plan("What does my uploaded report say about HbA1c?", document_ids=["d1"])
    assert plan.needs_user_uploaded
    assert not plan.needs_cross_source
    assert not plan.needs_supershyft


def test_routing_general_only():
    plan = build_query_plan("What is HbA1c?")
    assert plan.knowledge_scope == KnowledgeScope.general
    assert plan.needs_general
    assert not plan.needs_cross_source
    assert not plan.needs_personal_data


def test_routing_cross_source():
    plan = build_query_plan(
        "Compare my uploaded report with my latest SuperShyft report.",
        document_ids=["d1"],
    )
    assert plan.needs_cross_source
    assert plan.needs_user_uploaded
    assert plan.needs_supershyft


def test_extraction_skips_recommended_and_keeps_current():
    skip = extract_marker_from_text("Recommended HbA1c below 5.7", "hba1c")
    assert skip is None or skip.value is None or skip.confidence == "low"
    prev = extract_marker_from_text("Previous HbA1c: 5.4", "hba1c")
    assert prev is None or prev.confidence == "low" or prev.value is None
    current = extract_marker_from_text("HbA1c: 6.2 % Collection date: 20 Aug 2026", "hba1c")
    assert current and current.value == 6.2
    assert current.date == date(2026, 8, 20)


def test_comparator_difference_no_winner():
    result = CrossSourceComparator().compare(
        "hba1c",
        "HbA1c",
        SourceValue(source="user_uploaded", value=6.2, unit="%", date=date(2026, 8, 20), page=1, document_id="d"),
        SourceValue(source="supershyft", value=5.8, unit="%", date=date(2026, 9, 15)),
    )
    assert result.difference == -0.4
    assert result.direction == "lower"
    text = render_comparison(result)
    assert "6.2" in text and "5.8" in text
    assert "winner" not in text.lower()
    assert "diagnos" not in text.lower()
    assert "Uploaded report" in text
    assert "SuperShyft" in text


def test_comparator_missing_date_and_missing_value():
    result = CrossSourceComparator().compare(
        "ldl",
        "LDL",
        SourceValue(source="user_uploaded", value=150, unit="mg/dL", date=None, excerpt="LDL 150"),
        SourceValue(source="supershyft", value=None, unit="mg/dL", date=date(2026, 8, 18)),
    )
    text = render_comparison(result)
    assert "don't have a matching" in text.lower() or "not found" in text.lower()
    assert "does not show a clear test date" in text


def test_different_reference_ranges_called_out():
    result = CrossSourceComparator().compare(
        "ldl",
        "LDL",
        SourceValue(source="user_uploaded", value=150, unit="mg/dL", date=date(2026, 8, 1), reference_low=0, reference_high=130),
        SourceValue(source="supershyft", value=138, unit="mg/dL", date=date(2026, 8, 18), reference_low=0, reference_high=100),
    )
    text = render_comparison(result)
    assert "different reference ranges" in text


def test_chat_cross_source_hba1c(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "document_storage_path", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "enable_llm", False)
    up = client.post(
        "/api/v1/documents",
        headers=H,
        files={"file": ("hba1c.pdf", io.BytesIO(HBA1C_PDF), "application/pdf")},
    )
    did = up.json()["document_id"]
    res = client.post(
        "/api/v1/chat",
        headers=H,
        json={
            "message": "Compare my uploaded report with SuperShyft for HbA1c.",
            "document_ids": [did],
        },
    )
    body = res.json()
    assert body["meta"]["status"] == "cross_source_comparison"
    assert "supershyft" in body["meta"]["sources_used"]
    assert "user_uploaded" in body["meta"]["sources_used"]
    assert any(e["source"] == "user_uploaded" for e in body["evidence"])
    assert any(e["source"] == "supershyft" for e in body["evidence"])
    assert "6.2" in body["answer"]
    assert "5.5" in body["answer"]
    assert "diabetes" not in body["answer"].lower()
    assert "prescribe" not in body["answer"].lower()
    cid = body["conversation_id"]
    ldl = client.post(
        "/api/v1/chat",
        headers=H,
        json={"message": "What about LDL?", "conversation_id": cid, "document_ids": [did]},
    ).json()
    assert ldl["meta"]["status"] == "cross_source_comparison"
    assert "LDL" in ldl["answer"] or "ldl" in ldl["answer"].lower()
    newer = client.post(
        "/api/v1/chat",
        headers=H,
        json={"message": "Which one is newer?", "conversation_id": cid, "document_ids": [did]},
    ).json()
    assert "newer" in newer["answer"].lower() or "later" in newer["answer"].lower()
    why = client.post(
        "/api/v1/chat",
        headers=H,
        json={"message": "Why is this different?", "conversation_id": cid, "document_ids": [did]},
    ).json()
    assert "laborator" in why["answer"].lower() or "collection" in why["answer"].lower()


def test_multiple_documents_clarification(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "document_storage_path", str(tmp_path / "uploads"))
    for name in ("a.pdf", "b.pdf"):
        client.post(
            "/api/v1/documents",
            headers=H,
            files={"file": (name, io.BytesIO(HBA1C_PDF), "application/pdf")},
        )
    res = client.post(
        "/api/v1/chat",
        headers=H,
        json={"message": "Compare my reports with SuperShyft."},
    )
    assert "Which uploaded report" in res.json()["answer"]
    assert res.json()["meta"]["status"] == "cross_source_ambiguous"


def test_general_question_does_not_use_upload(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "document_storage_path", str(tmp_path / "uploads"))
    client.post(
        "/api/v1/documents",
        headers=H,
        files={"file": ("hba1c.pdf", io.BytesIO(HBA1C_PDF), "application/pdf")},
    )
    body = client.post("/api/v1/chat", headers=H, json={"message": "What is HbA1c?"}).json()
    assert body["meta"]["intent"] == "general_health_question"
    assert "6.2" not in body["answer"]
    assert body["meta"].get("sources_used") == ["general"] or body["meta"]["status"] != "cross_source_comparison"


def test_cross_user_document_blocked(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "document_storage_path", str(tmp_path / "uploads"))
    did = client.post(
        "/api/v1/documents",
        headers=H,
        files={"file": ("hba1c.pdf", io.BytesIO(HBA1C_PDF), "application/pdf")},
    ).json()["document_id"]
    res = client.post(
        "/api/v1/chat",
        headers={"X-Cura-User-Id": "demo-user-002"},
        json={"message": "Compare my uploaded report with SuperShyft.", "document_ids": [did]},
    )
    assert res.status_code == 404
