from app.contracts.query import QueryPlan
from app.contracts.task_plan import TaskOperation
from app.documents.facts import extract_facts_from_pages
from app.documents.pageindex import build_pageindex, retrieve_pageindex
from app.documents.query_policy import wants_document_narrative, wants_document_structured
from app.documents.type_detect import detect_document_kind, detect_document_subtype
from app.pipeline.planner import infer_operations
from app.pipeline.query_planner import build_query_plan
from tests.helpers.pdf_fixtures import make_text_pdf
from app.documents.extraction import extract_pdf_pages
from app.contracts.uploaded_document import DocumentKind, DocumentSubtype
from fastapi.testclient import TestClient
from app.main import app
import io

from app.core.config import settings
import pytest

client = TestClient(app)


@pytest.fixture
def storage_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "document_storage_path", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "document_ocr_provider", "none")
    return tmp_path / "uploads"


def test_type_detect_lab_text_based():
    pages = extract_pdf_pages(make_text_pdf(["Lipid Profile LDL 140 mg/dL HDL 45 Reference Range HbA1c 5.4"]))
    assert detect_document_kind(pages) == DocumentKind.text_based
    assert detect_document_subtype(pages) == DocumentSubtype.lab_report


def test_pageindex_retrieves_impression_without_embeddings():
    pages = extract_pdf_pages(
        make_text_pdf(
            [
                "IMPRESSION mild hepatomegaly. No focal lesion.",
                "LDL cholesterol 140 mg/dL",
            ]
        )
    )
    tree = build_pageindex("doc-1", pages)
    hits = retrieve_pageindex(tree, "What did the radiologist impression say about the liver?")
    assert hits
    assert "hepatomegaly" in hits[0].text.lower()
    assert hits[0].page_start == 1


def test_structured_facts_keep_conflicting_values():
    pages = extract_pdf_pages(
        make_text_pdf(
            [
                "Vitamin D Total 20 ng/ml",
                "25-OH Vitamin D 28 ng/ml",
            ]
        )
    )
    extracted = extract_facts_from_pages("doc-1", pages)
    values = sorted({round(item.value, 1) for item in extracted.biomarkers if item.normalized_name == "vitamin_d" and item.value is not None})
    assert values == [20.0, 28.0]


def test_query_policy_does_not_use_pageindex_for_ldl_lookup():
    plan = build_query_plan("What is my LDL in this uploaded report?", document_ids=["doc-1"])
    assert wants_document_structured(plan.raw_message, plan) is True
    assert wants_document_narrative(plan.raw_message, plan) is False


def test_planner_document_operations():
    structured = build_query_plan("What is my Vitamin D in this uploaded report?", document_ids=["x"])
    ops = infer_operations(structured, structured.raw_message)
    assert TaskOperation.document_structured_lookup in ops
    narrative = build_query_plan("What did the radiologist say about my liver?", document_ids=["x"])
    ops = infer_operations(narrative, narrative.raw_message)
    assert TaskOperation.document_narrative_retrieval in ops


def test_chat_structured_lookup_uses_page_provenance(storage_dir):
    pdf = make_text_pdf(["Lipid Profile LDL cholesterol 140 mg/dL HDL 45 Reference Range 0-100"])
    res = client.post(
        "/api/v1/documents",
        headers={"X-Cura-User-Id": "user-pdf"},
        files={"file": ("lipid.pdf", io.BytesIO(pdf), "application/pdf")},
    )
    assert res.status_code == 200
    did = res.json()["document_id"]
    got = client.get(f"/api/v1/documents/{did}", headers={"X-Cura-User-Id": "user-pdf"}).json()
    assert got["extraction_status"] == "completed"
    assert got["structured_facts_ready"] is True
    assert got["pageindex_status"] in {"READY", "BUILDING", "FAILED"}
    chat = client.post(
        "/api/v1/chat",
        headers={"X-Cura-User-Id": "user-pdf"},
        json={"message": "What is my LDL?", "document_ids": [did]},
    ).json()
    answer = chat["answer"].lower()
    assert "140" in chat["answer"]
    assert "page" in answer
    assert "chunk" not in answer
    assert chat["meta"]["llm_mode"] == "none"


def test_chat_narrative_uses_section_not_chunk_id(storage_dir):
    pdf = make_text_pdf(["IMPRESSION mild fatty liver. No mass lesion.", "LDL cholesterol 140 mg/dL"])
    res = client.post(
        "/api/v1/documents",
        headers={"X-Cura-User-Id": "user-pdf"},
        files={"file": ("rad.pdf", io.BytesIO(pdf), "application/pdf")},
    )
    did = res.json()["document_id"]
    chat = client.post(
        "/api/v1/chat",
        headers={"X-Cura-User-Id": "user-pdf"},
        json={"message": "What did the radiologist say?", "document_ids": [did]},
    ).json()
    answer = chat["answer"].lower()
    assert "fatty liver" in answer or "impression" in answer
    assert "chunk" not in answer
    assert "diagnos" not in answer or "not a diagnosis" in answer


def test_ocr_facts_are_lower_confidence():
    from app.documents.extraction import ExtractedPage

    pages = [
        ExtractedPage(
            page_number=2,
            text="Vitamin D Total 18 ng/ml",
            character_count=24,
            method="ocr",
        )
    ]
    extracted = extract_facts_from_pages("doc-ocr", pages)
    assert extracted.biomarkers
    assert extracted.biomarkers[0].extraction_method == "ocr"
    assert extracted.biomarkers[0].confidence == "low"
    from app.documents.facts import facts_from_extracted

    facts = facts_from_extracted(extracted)
    assert facts[0].extraction_method == "ocr"
    assert facts[0].page_number == 2
    assert (facts[0].extraction_confidence or 1) < 0.6


def test_planner_cross_source_document_ops():
    plan = build_query_plan(
        "Compare my uploaded report with my latest SuperShyft report.",
        document_ids=["x"],
    )
    ops = infer_operations(plan, plan.raw_message)
    assert TaskOperation.document_structured_lookup in ops
    assert TaskOperation.document_cross_source_compare in ops


def test_chat_report_summary_is_not_a_dump(storage_dir):
    pdf = make_text_pdf(
        [
            "IMPRESSION mild hepatomegaly. No focal lesion.",
            "LDL cholesterol 140 mg/dL HDL 45 Reference Range 0-100 HbA1c 5.4",
        ]
    )
    res = client.post(
        "/api/v1/documents",
        headers={"X-Cura-User-Id": "user-pdf-sum"},
        files={"file": ("sum.pdf", io.BytesIO(pdf), "application/pdf")},
    )
    did = res.json()["document_id"]
    chat = client.post(
        "/api/v1/chat",
        headers={"X-Cura-User-Id": "user-pdf-sum"},
        json={"message": "Explain this whole report.", "document_ids": [did]},
    ).json()
    answer = chat["answer"].lower()
    assert "overall picture" in answer
    assert "chunk" not in answer
    assert "not a diagnosis" in answer
    texts = [item.get("text", "") for item in chat.get("follow_ups") or []]
    assert any("extracted" in text.lower() for text in texts)
    listed = client.post(
        "/api/v1/chat",
        headers={"X-Cura-User-Id": "user-pdf-sum"},
        json={"message": "View all extracted results", "document_ids": [did], "conversation_id": chat["conversation_id"]},
    ).json()
    assert "140" in listed["answer"]
    assert "all extracted" in listed["answer"].lower() or "ldl" in listed["answer"].lower()
