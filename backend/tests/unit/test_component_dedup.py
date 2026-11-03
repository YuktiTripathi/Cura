"""Structured biomarker cards and Bio-AI notices stay beside the answer, not inside it."""

from app.contracts.presentation import PresentedFinding, StructuredResponse
from app.contracts.semantic_response import ResolvedValue, ResponseBlock, SemanticResponse
from app.pipeline.semantic_blocks import (
    BIO_AI_CLARIFICATION,
    ensure_bio_ai_clarification,
    suppress_duplicate_findings,
)


def _response(answer: str, presentation, semantic):
    class Response:
        pass

    item = Response()
    item.answer = answer
    item.presentation = presentation
    item.semantic = semantic
    return item


def test_same_biomarker_is_kept_on_the_metric_block_only():
    answer = "Your HbA1c is above the report range.\n\nThat reflects average glucose."
    semantic = SemanticResponse(
        summary=answer,
        blocks=[
            ResponseBlock(
                type="metric",
                evidence=["blood.hba1c.latest"],
                values=[ResolvedValue(key="blood.hba1c.latest", label="HbA1c", kind="blood", value=8.2, unit="%", reference_high=5.6)],
            )
        ],
    )
    presentation = StructuredResponse(
        findings=[
            PresentedFinding(label="HbA1c", canonical_key="hba1c", value="8.2", unit="%"),
            PresentedFinding(label="LDL cholesterol", canonical_key="ldl", value="140", unit="mg/dL"),
            PresentedFinding(label="A note without an id", value="kept"),
        ]
    )
    suppress_duplicate_findings(presentation, semantic)
    assert [item.canonical_key for item in presentation.findings] == ["ldl", None]
    assert semantic.blocks[0].evidence == ["blood.hba1c.latest"]
    assert semantic.blocks[0].values[0].value == 8.2
    assert semantic.blocks[0].values[0].reference_high == 5.6


def test_bio_ai_clarification_is_added_once_and_the_answer_stays():
    answer = "Your PCOS risk score is in the higher group."
    semantic = SemanticResponse(
        summary=answer,
        blocks=[ResponseBlock(type="risk", evidence=["bioai.pcos"], values=[ResolvedValue(key="bioai.pcos", label="PCOS", kind="bio_ai", value=72)])],
    )
    response = _response(answer, StructuredResponse(), semantic)
    ensure_bio_ai_clarification(response)
    ensure_bio_ai_clarification(response)
    assert response.answer == answer
    notes = [block.text for block in semantic.blocks if block.type == "warning"]
    assert notes == [BIO_AI_CLARIFICATION]


def test_clarification_is_skipped_when_the_answer_already_says_it():
    answer = "This PCOS score is a risk estimate, not a diagnosis."
    semantic = SemanticResponse(
        summary=answer,
        blocks=[ResponseBlock(type="risk", evidence=["bioai.pcos"], values=[ResolvedValue(key="bioai.pcos", label="PCOS", kind="bio_ai", value=72)])],
    )
    response = _response(answer, None, semantic)
    ensure_bio_ai_clarification(response)
    assert [block.type for block in semantic.blocks] == ["risk"]
    assert response.answer == answer
