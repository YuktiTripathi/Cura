"""A panel question uses the matching section, not the first same-named result."""

from app.contracts.uploaded_document import DocumentHealthFact, UploadedDocumentContext
from app.documents.lookup import cover_requested_entities, format_coverage
from app.pipeline.document_answer import DocumentAnswer, _maybe_explain


def _fact(code, value, page, section, kind="measured"):
    return DocumentHealthFact(
        canonical_code=code,
        display_name=code,
        value=value,
        unit="mg/dL",
        page_number=page,
        section=section,
        source_document_id="doc-a",
        measurement_kind=kind,
        resolution_status="verified",
    )


def test_kft_uses_kidney_section_not_cystatin_page():
    facts = [
        _fact("creatinine", 1.03, 3, "GFR WITH CYSTATIN C"),
        _fact("creatinine", 1.06, 8, "KIDNEY FUNCTION TEST"),
        _fact("egfr", 90.01, 8, "KIDNEY FUNCTION TEST", kind="calculated"),
        _fact("ldl", 140, 5, "LIPID PROFILE"),
    ]
    ctx = UploadedDocumentContext(document_id="doc-a", structured_facts=facts)
    body = format_coverage(cover_requested_entities([ctx], ["kidney_function"], "Explain my Kidney Function Test"))
    assert "1.06" in body and "page 8" in body
    assert "1.03" not in body
    assert "140" not in body
    assert "90.01" in body


def test_same_name_without_a_matching_section_stays_separate():
    facts = [
        _fact("creatinine", 1.03, 3, "GFR WITH CYSTATIN C"),
        _fact("creatinine", 1.06, 8, "KIDNEY FUNCTION TEST"),
    ]
    ctx = UploadedDocumentContext(document_id="doc-a", structured_facts=facts)
    body = format_coverage(cover_requested_entities([ctx], ["creatinine"], "what is my creatinine"))
    assert "1.03" in body and "1.06" in body
    assert "page 3" in body and "page 8" in body


def test_other_document_and_unresolved_stay_out():
    verified = _fact("ldl", 90, 4, "LIPID PROFILE")
    other = _fact("ldl", 200, 9, "LIPID PROFILE")
    other.source_document_id = "doc-b"
    unresolved = DocumentHealthFact(
        canonical_code=None,
        display_name="Specific IgE D1",
        value=3.2,
        unit="kUA/L",
        page_number=12,
        section="BIO-ALLERGY PLUS",
        source_document_id="doc-a",
        resolution_status="unresolved",
    )
    ctx = UploadedDocumentContext(document_id="doc-a", structured_facts=[verified, unresolved])
    body = format_coverage(cover_requested_entities([ctx], ["lipid_profile"]))
    assert "90" in body and "200" not in body and "3.2" not in body


def test_explanation_rejects_a_number_the_evidence_does_not_contain(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "enable_llm", True)
    monkeypatch.setattr(settings, "require_zdr_for_personal_health", True)
    monkeypatch.setattr(settings, "openrouter_zero_data_retention", True)

    class _Client:
        def complete(self, *_a, **_k):
            return "Your creatinine is 9.99 mg/dL."

    monkeypatch.setattr("app.llm.factory.get_llm_client", lambda **_k: _Client())
    out = _maybe_explain(DocumentAnswer(answer="Creatinine 1.06 mg/dL page 8"), "Explain my Kidney Function Test")
    assert "1.06" in out.answer and "9.99" not in out.answer


def test_explanation_keeps_model_text_when_every_number_is_backed(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "enable_llm", True)
    monkeypatch.setattr(settings, "require_zdr_for_personal_health", True)
    monkeypatch.setattr(settings, "openrouter_zero_data_retention", True)

    class _Client:
        def complete(self, *_a, **_k):
            return "The kidney panel creatinine is 1.06 mg/dL, which is inside 0.7-1.4."

    monkeypatch.setattr("app.llm.factory.get_llm_client", lambda **_k: _Client())
    evidence = "Creatinine 1.06 mg/dL page 8 0.7-1.4"
    out = _maybe_explain(DocumentAnswer(answer=evidence), "Explain my kidney results")
    assert out.answer.startswith("The kidney panel")
