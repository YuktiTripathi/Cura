from app.contracts.evidence import EvidenceRecord
from app.pipeline.narrative import format_unit, format_units_in_text, spoken_count
from app.pipeline.prompt_builder import _selected_upload_block
from datetime import date


def test_selected_upload_block_keeps_each_document():
    from app.contracts.health_context import HealthContext
    from app.contracts.common import AnswerDepth, IntentType

    ctx = HealthContext(
        intent=IntentType.broad_health_summary,
        answer_depth=AnswerDepth.focused,
        evidence=[
            EvidenceRecord(
                evidence_id="c1",
                report_id="DOC_A",
                report_type="uploaded_document",
                report_date=date(2026, 1, 1),
                source="user_uploaded",
                document_id="DOC_A",
                chunk_id="c1",
                page_start=1,
                excerpt="HbA1c 5.6 % LDL 199",
            )
        ],
    )
    block = _selected_upload_block(ctx)
    assert "DOC_A" in block and "5.6" in block and "199" in block
    assert "not in the selected document" in block


def test_scientific_unit_faces():
    assert format_unit("10^3/uL") == "10³/µL"
    assert format_unit("10^6/uL") == "10⁶/µL"
    assert format_unit("10^9/L") == "10⁹/L"
    assert format_unit("mg/dl") == "mg/dL"
    assert format_unit("ug/dl") == "µg/dL"
    assert format_unit("mmol/l") == "mmol/L"


def test_count_keeps_the_value_and_adds_a_times_sign():
    assert format_units_in_text("The count is 0.01 10^3/uL.") == "The count is 0.01 × 10³/µL."
    assert format_units_in_text("0.01 x10^3/µL") == "0.01 × 10³/µL"
    assert spoken_count(0.01, "10^3/uL") == "10 cells per microliter"


def test_formatting_does_not_invent_a_round_cell_count():
    assert spoken_count(0.0123, "10^3/uL") is None
