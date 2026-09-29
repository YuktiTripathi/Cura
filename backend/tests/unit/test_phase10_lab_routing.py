import io

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings

from app.contracts.common import IntentType, KnowledgeScope
from app.documents.value_extraction import extract_marker_from_text
from app.main import app
from app.pipeline.intent import classify_intent
from app.pipeline.lab_parameters import primary_lab_key
from app.pipeline.query_planner import build_query_plan
from tests.helpers.pdf_fixtures import make_text_pdf

client = TestClient(app)
H = {"X-Cura-User-Id": "demo-user-001"}


@pytest.fixture(autouse=True)
def _storage(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "document_storage_path", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "document_ocr_provider", "none")

BLOOD_PDF = make_text_pdf(
    [
        "LH ovulation luteinizing hormone physiology ESR creatinine uric acid calcium sodium",
        "Fasting Blood Sugar Glucose 76.73 mg/dL Reference range: 70 - 100 mg/dL",
    ]
)


def _upload():
    return client.post(
        "/api/v1/documents",
        headers=H,
        files={"file": ("Blood Report.pdf", io.BytesIO(BLOOD_PDF), "application/pdf")},
    ).json()["document_id"]


def test_normalize_sugar_aliases():
    for msg in (
        "What is my sugar level",
        "What is my blood sugar?",
        "What is my fasting glucose?",
        "Tell me my glucose level",
    ):
        assert primary_lab_key(msg) in {"glucose", "fasting_blood_glucose"}
        intent, topic, *_ = classify_intent(msg)
        assert intent == IntentType.latest_result
        assert topic in {"glucose", "fasting_blood_glucose"}


def test_personal_vs_general_sugar_and_vitamin_d():
    personal = build_query_plan("What is my blood sugar?")
    assert personal.needs_supershyft
    assert not personal.needs_user_uploaded
    assert personal.knowledge_scope == KnowledgeScope.personal
    general_v = build_query_plan("What is Vitamin D?")
    assert general_v.knowledge_scope == KnowledgeScope.general
    assert not general_v.needs_supershyft
    personal_d = build_query_plan("What is my Vitamin D?")
    assert personal_d.needs_supershyft
    normal = build_query_plan("What is normal blood sugar?")
    assert normal.knowledge_scope == KnowledgeScope.general
    assert not normal.needs_supershyft
    compare = build_query_plan(
        "Compare my uploaded glucose with my SuperShyft glucose",
        document_ids=["d1"],
    )
    assert compare.needs_cross_source


def test_blood_report_pdf_retrieves_fasting_glucose():
    did = _upload()
    body = client.post(
        "/api/v1/chat",
        headers=H,
        json={"message": "What is my sugar level", "document_ids": [did]},
    ).json()
    assert "76.73" in body["answer"]
    assert "70" in body["answer"] and "100" in body["answer"]
    assert "ovulation" not in body["answer"].lower()
    assert "luteinizing" not in body["answer"].lower()
    assert body["answer"].lower().count("user_uploaded") == 0
    pages = {e.get("page_start") for e in body["evidence"]}
    assert 2 in pages
    assert all(e["source"] == "user_uploaded" for e in body["evidence"])
    assert body["meta"]["sources_used"] == ["user_uploaded"]
    assert body["meta"]["supershyft_called"] is False
    ids = [e["document_id"] for e in body["evidence"]]
    assert len(ids) == len(set(ids))
    extracted = extract_marker_from_text(
        "Fasting Blood Sugar Glucose 76.73 mg/dL Reference range: 70 - 100 mg/dL",
        "fasting_blood_glucose",
        page=2,
    )
    assert extracted and extracted.value == 76.73
    assert extracted.reference_low == 70
    assert extracted.reference_high == 100
    assert extracted.page == 2


def test_duplicate_chunks_not_repeated():
    did = _upload()
    body = client.post(
        "/api/v1/chat",
        headers=H,
        json={"message": "What is my fasting glucose?", "document_ids": [did]},
    ).json()
    assert body["answer"].count("76.73") == 1
    assert len(body["evidence"]) == 1


def test_hba1c_personal_uses_health_provider():
    plan = build_query_plan("What is my HbA1c?")
    assert plan.needs_supershyft
    body = client.post("/api/v1/chat", headers=H, json={"message": "What is my HbA1c?"}).json()
    assert body["meta"]["supershyft_called"] is True
    assert body["meta"]["document_retrieval_called"] is False
    assert "5.5" in body["answer"]


def test_cholesterol_personal_plan():
    plan = build_query_plan("What is my cholesterol?")
    assert plan.topic in {"cholesterol", "ldl"}
    assert plan.needs_supershyft


def test_db_status_general_not_called():
    body = client.post("/api/v1/chat", headers=H, json={"message": "What is Vitamin D?"}).json()
    assert body["meta"]["db_status"] == "db_provider_not_called"
    assert body["meta"]["supershyft_called"] is False
    assert body["meta"]["llm_called"] is True
