"""Multi-entity uploaded-document retrieval. No per-biomarker special cases."""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

from app.contracts.query import QueryPlan
from app.core.config import settings
from app.documents.facts import attach_conflicts, dedupe_identical, extract_facts_from_pages, facts_from_extracted
from app.documents.lookup import AMBIGUOUS, FOUND, MISSING, cover_requested_entities, format_coverage
from app.main import app
from app.pipeline.lab_parameters import canonicalize_marker_name, match_lab_keys, resolve_biomarker
from app.pipeline.ontology import requested_metrics_from_message
from app.pipeline.planner import EntityResolver
from tests.helpers.pdf_fixtures import make_text_pdf

client = TestClient(app)

REPORT = [
    "SERUM HDL CHOLESTEROL 57 mg/dL Reference Range 40-60",
    "Haemoglobin (Hb) 11.7 g/dL Reference Range 12.0-15.0",
    "Fasting Blood Glucose 98 mg/dL HbA1c 5.3 % LDL-C 94 mg/dL Triglycerides 82 mg/dL",
    "TSH 2.1 µIU/mL Free T3 3.1 pg/mL Free T4 1.1 ng/dL",
]


@pytest.fixture
def storage_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "document_storage_path", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "document_ocr_provider", "none")
    return tmp_path / "uploads"


@pytest.mark.parametrize(
    "message,expected",
    [
        ("What are my HDL and Hb?", {"hdl", "hemoglobin"}),
        ("Show HDL cholesterol and haemoglobin.", {"hdl", "hemoglobin"}),
        ("What is my serum HDL cholesterol and HGB?", {"hdl", "hemoglobin"}),
        ("What is my HDL cholesterol & Hemoglobin level?", {"hdl", "hemoglobin"}),
        ("this is the report, I have attached, I want to know my Sodium & Chloride level", {"sodium", "chloride"}),
        ("Show glucose, HbA1c, LDL and triglycerides.", {"glucose", "hba1c", "ldl", "triglycerides"}),
        ("What are my TSH, T3 and T4?", {"tsh", "t3", "t4"}),
    ],
)
def test_multi_entity_query_extracts_all(message, expected):
    assert set(match_lab_keys(message)) >= expected
    assert set(requested_metrics_from_message(message)) >= expected
    codes = {item.code for item in EntityResolver().resolve(message)}
    assert expected <= codes


@pytest.mark.parametrize(
    "label,code",
    [
        ("HDL-C", "hdl"),
        ("SERUM HDL CHOLESTEROL", "hdl"),
        ("HDL CHOLESTEROL - DIRECT", "hdl"),
        ("HIGH DENSITY LIPOPROTEIN", "hdl"),
        ("Haemoglobin", "hemoglobin"),
        ("Hemoglobin", "hemoglobin"),
        ("HGB", "hemoglobin"),
        ("Hb", "hemoglobin"),
        ("Iron Serum", "iron"),
        ("Serum Iron", "iron"),
        ("PCV", "hematocrit"),
        ("Hematocrit", "hematocrit"),
        ("PLT", "platelets"),
        ("TLC", "wbc"),
        ("WBC", "wbc"),
        ("Sodium", "sodium"),
        ("Serum Sodium", "sodium"),
        ("Chloride", "chloride"),
        ("Na+", "sodium"),
    ],
)
def test_provider_labels_map_to_canonical(label, code):
    assert canonicalize_marker_name(label) == code
    assert resolve_biomarker(label).canonical_code == code


def test_coverage_all_found():
    pages = extract_pdf_pages_safe(REPORT)
    extracted = extract_facts_from_pages("doc-multi", pages)
    facts = facts_from_extracted(extracted)
    ctx = _ctx(facts)
    rows = cover_requested_entities([ctx], ["hdl", "hemoglobin"])
    assert [row.status for row in rows] == [FOUND, FOUND]
    answer = format_coverage(rows)
    assert "57" in answer and "11.7" in answer
    assert "hdl" in answer.lower() and "haemoglobin" in answer.lower() or "hemoglobin" in answer.lower()


def test_coverage_one_missing():
    pages = extract_pdf_pages_safe(["Haemoglobin (Hb) 11.7 g/dL"])
    facts = facts_from_extracted(extract_facts_from_pages("doc-hb", pages))
    rows = cover_requested_entities([_ctx(facts)], ["hdl", "hemoglobin"])
    assert {row.code: row.status for row in rows} == {"hdl": MISSING, "hemoglobin": FOUND}
    answer = format_coverage(rows).lower()
    assert "11.7" in answer
    assert "couldn't find" in answer and "hdl" in answer
    assert "57" not in answer


def test_coverage_all_missing():
    pages = extract_pdf_pages_safe(["No lab table on this page"])
    facts = facts_from_extracted(extract_facts_from_pages("doc-empty", pages))
    rows = cover_requested_entities([_ctx(facts)], ["hdl", "hemoglobin"])
    assert all(row.status == MISSING for row in rows)
    assert "couldn't find" in format_coverage(rows).lower()


def test_identical_duplicates_are_merged():
    pages = extract_pdf_pages_safe(
        [
            "Summary HDL cholesterol 57 mg/dL",
            "Detail SERUM HDL CHOLESTEROL 57 mg/dL",
        ]
    )
    facts = facts_from_extracted(extract_facts_from_pages("doc-dup", pages))
    hdl = [item for item in facts if item.canonical_code == "hdl"]
    assert len(hdl) == 1
    assert hdl[0].conflict_group is None


def test_conflicting_values_are_preserved():
    pages = extract_pdf_pages_safe(
        [
            "HDL cholesterol 57 mg/dL",
            "HDL cholesterol 41 mg/dL",
        ]
    )
    extracted = extract_facts_from_pages("doc-conflict", pages)
    values = sorted(
        item.value
        for item in extracted.biomarkers
        if item.normalized_name == "hdl" and item.value is not None
    )
    assert values == [41.0, 57.0]
    facts = attach_conflicts(facts_from_extracted(extracted))
    hdl = [item for item in facts if item.canonical_code == "hdl"]
    assert any(item.conflict_group for item in hdl)
    rows = cover_requested_entities([_ctx(hdl)], ["hdl"])
    assert rows[0].status == AMBIGUOUS


def test_punctuation_and_spacing_aliases():
    assert canonicalize_marker_name("  HDL-C  ") == "hdl"
    assert canonicalize_marker_name("hdl   cholesterol") == "hdl"
    assert "hdl" in match_lab_keys("hdl-c, haemoglobin")
    assert "hemoglobin" in match_lab_keys("hdl-c, haemoglobin")


def test_chat_multi_entity_does_not_drop_hdl(storage_dir):
    pdf = make_text_pdf(REPORT)
    uploaded = client.post(
        "/api/v1/documents",
        headers={"X-Cura-User-Id": "user-multi"},
        files={"file": ("labs.pdf", io.BytesIO(pdf), "application/pdf")},
    )
    did = uploaded.json()["document_id"]
    chat = client.post(
        "/api/v1/chat",
        headers={"X-Cura-User-Id": "user-multi"},
        json={"message": "What is my HDL cholesterol & Hemoglobin level?", "document_ids": [did]},
    ).json()
    answer = chat["answer"]
    assert "57" in answer
    assert "11.7" in answer
    assert "hdl" in answer.lower()
    assert "haemoglobin" in answer.lower() or "hemoglobin" in answer.lower()


def test_chat_sodium_chloride_columnar_table_does_not_return_vitamin_d(storage_dir):
    pdf = make_text_pdf(
        [
            [
                "Vitamin D Total 25 ng/ml",
                "KIDNEY FUNCTION & ELECTROLYTES",
                "Sodium",
                "137",
                "mmol/L",
                "136 - 146",
                "Chloride",
                "105",
                "mmol/L",
                "101 - 109",
            ]
        ]
    )
    uploaded = client.post(
        "/api/v1/documents",
        headers={"X-Cura-User-Id": "user-electrolytes"},
        files={"file": ("electrolytes.pdf", io.BytesIO(pdf), "application/pdf")},
    )
    did = uploaded.json()["document_id"]
    chat = client.post(
        "/api/v1/chat",
        headers={"X-Cura-User-Id": "user-electrolytes"},
        json={
            "message": "this is the report, I have attached, I want to know my Sodium & Chloride level",
            "document_ids": [did],
        },
    ).json()
    answer = chat["answer"].lower()
    assert "137" in chat["answer"]
    assert "105" in chat["answer"]
    assert "sodium" in answer
    assert "chloride" in answer
    assert "vitamin d" not in answer
    assert "25" not in chat["answer"]


def extract_pdf_pages_safe(lines: list[str]):
    from app.documents.extraction import extract_pdf_pages

    return extract_pdf_pages(make_text_pdf(lines))


def _ctx(facts):
    from app.contracts.uploaded_document import (
        DocumentKind,
        DocumentSubtype,
        PageIndexStatus,
        ProcessingStatus,
        UploadedDocumentContext,
    )

    return UploadedDocumentContext(
        document_id="doc",
        document_name="labs.pdf",
        document_kind=DocumentKind.text_based,
        document_type=DocumentSubtype.lab_report,
        processing_status=ProcessingStatus.ready,
        pageindex_status=PageIndexStatus.ready,
        structured_facts=facts,
    )
