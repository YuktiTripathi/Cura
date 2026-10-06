"""Readiness plan: reviewed content (4.3, 4.4), translation pivot (3.3), object storage (5.2)."""

from __future__ import annotations

import json
from datetime import date

import boto3
import httpx
import pytest
from moto import mock_aws

from app.core.config import settings
from app.core.errors import InternalError
from app.documents.storage import S3DocumentStore, get_document_store
from app.pipeline import translation
from app.retrieval import medical
from app.retrieval.medical import MedicalEvidenceDoc, is_servable, passage_label


def _doc(**kw) -> MedicalEvidenceDoc:
    base = dict(
        name="ICMR", url="https://example.org/vitd", source_type="guideline", tier=1,
        topics=("vitamin_d",), keywords=("vitamin d",), excerpt="Vitamin D supports bone health.",
        review_status="published", reviewer="Dr A", reviewed_on="2026-09-01", expires_on="2027-08-31",
    )
    base.update(kw)
    return MedicalEvidenceDoc(**base)


TODAY = date(2026, 10, 6)


@pytest.mark.parametrize(
    "overrides, servable",
    [
        ({}, True),
        ({"review_status": "draft"}, False),
        ({"review_status": "unreviewed_index"}, False),
        ({"reviewer": None}, False),
        ({"reviewed_on": "2025-09-01", "expires_on": None}, False),
        ({"expires_on": "2030-01-01"}, True),  # capped at 12 months after review, still in date today
        ({"reviewed_on": "2025-01-01", "expires_on": "2030-01-01"}, False),
    ],
)
def test_only_reviewed_in_date_entries_are_servable(overrides, servable):
    assert is_servable(_doc(**overrides), TODAY) is servable


def test_unreviewed_index_is_not_served_when_review_required(monkeypatch):
    monkeypatch.setattr(settings, "medical_require_reviewed", True)
    assert medical.retrieve_medical_evidence("what is hypertension") == []
    monkeypatch.setattr(settings, "medical_require_reviewed", False)
    assert medical.retrieve_medical_evidence("what is hypertension")


def test_content_files_are_loaded(tmp_path, monkeypatch):
    (tmp_path / "vitd.json").write_text(json.dumps([{**_doc().__dict__, "topics": ["vitamin_d"], "keywords": ["vitamin d"]}]))
    monkeypatch.setattr(medical, "CONTENT_DIR", tmp_path)
    monkeypatch.setattr(settings, "medical_require_reviewed", True)
    monkeypatch.setattr(medical, "is_servable", lambda doc, today=None: doc.review_status == "published")
    hits = medical.retrieve_medical_evidence("is my vitamin d low")
    assert [d.name for d in hits] == ["ICMR"]


def test_cura_paraphrase_is_never_labelled_as_a_quote():
    assert passage_label(_doc()).startswith("Cura summary, not a quotation")
    assert passage_label(_doc(content_kind="quoted_passage")).startswith("Quoted from ICMR")


def test_target_language_follows_script_and_enabled_list(monkeypatch):
    monkeypatch.setattr(settings, "answer_languages", "en,hi")
    assert translation.target_language("मेरा HbA1c क्या है") == "hi"
    assert translation.target_language("ਮੇਰਾ HbA1c ਕੀ ਹੈ") == "en"  # pa not enabled yet
    assert translation.target_language("what is HbA1c", "hi", "manual") == "hi"


def _client(content: str) -> httpx.Client:
    def handler(request):
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    return httpx.Client(transport=httpx.MockTransport(handler))


@pytest.fixture()
def llm_on(monkeypatch):
    monkeypatch.setattr(settings, "enable_llm", True)
    monkeypatch.setattr(settings, "openrouter_api_key", "sk-or-test")
    monkeypatch.setattr(settings, "require_zdr_for_personal_health", False)


def test_translation_used_when_numbers_match(llm_on):
    text, lang, flags = translation.translate_answer(
        "Your HbA1c is 6.1% (range 4.0-5.6).", "hi", client=_client("आपका HbA1c ६.१% है (सीमा 4.0-5.6)।")
    )
    assert lang == "hi" and flags == [] and "HbA1c" in text


def test_translation_rejected_when_a_number_changes(llm_on):
    english = "Your HbA1c is 6.1%."
    text, lang, flags = translation.translate_answer(english, "hi", client=_client("आपका HbA1c 7.1% है।"))
    assert text == english and lang == "en" and flags == ["translation_number_mismatch"]


def test_translation_failure_falls_back_to_english(llm_on):
    def boom(request):
        raise httpx.ConnectTimeout("slow")

    client = httpx.Client(transport=httpx.MockTransport(boom))
    text, lang, flags = translation.translate_answer("Hello 5", "hi", client=client)
    assert (text, lang, flags) == ("Hello 5", "en", ["translation_failed"])


@mock_aws
def test_s3_store_round_trip_with_kms_and_hashed_keys(monkeypatch):
    s3 = boto3.client("s3", region_name="ap-south-1")
    s3.create_bucket(Bucket="cura-docs", CreateBucketConfiguration={"LocationConstraint": "ap-south-1"})
    store = S3DocumentStore(bucket="cura-docs", prefix="documents", client=s3)
    key = store.save("member-42", "doc-1", b"%PDF-1.4")
    assert "member-42" not in key
    assert store.exists(key) and store.read(key) == b"%PDF-1.4"
    head = s3.head_object(Bucket="cura-docs", Key=f"documents/{key}")
    assert head["ServerSideEncryption"] == "aws:kms"
    store.delete(key)
    assert not store.exists(key)


def test_unknown_storage_backend_fails_loudly(monkeypatch):
    monkeypatch.setattr(settings, "document_storage_backend", "ftp")
    with pytest.raises(InternalError):
        get_document_store()
