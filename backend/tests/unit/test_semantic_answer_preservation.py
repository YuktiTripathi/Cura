"""Semantic mode keeps the safety-approved answer and only adds verified cards."""

from types import SimpleNamespace

from app.contracts.blood import BloodMarker
from app.contracts.chat import ChatMeta, ChatResponse
from app.contracts.common import AnswerDepth, IntentType, MarkerFlag
from app.contracts.followup import FollowUpSuggestion
from app.contracts.health_context import Comparison, HealthContext
from app.pipeline.followup_generator import FollowUpBrief, valid_question
from app.pipeline.semantic_blocks import build_semantic_response
from app.pipeline.visible_output import finalize_response

LONG = (
    "## Blood sugar\n\n"
    "Your HbA1c is above the range on this report. That is a screening signal, not a diagnosis.\n\n"
    "- It reflects average glucose over about three months.\n"
    "- Glucose on the same report points the same way.\n"
    "- A single result does not confirm diabetes.\n\n"
    "The next useful step is to look at the pattern with your doctor, not to start a medicine from this chat."
)


def _marker():
    return BloodMarker(
        id="hba1c", key="hba1c", name="HbA1c", value=9.1, unit="%",
        flag=MarkerFlag.high, reference_low=4.0, reference_high=5.6,
    )


def _context(**kwargs):
    return HealthContext(
        intent=kwargs.pop("intent", IntentType.blood_marker_explanation),
        answer_depth=AnswerDepth.simple,
        markers=kwargs.pop("markers", [_marker()]),
        **kwargs,
    )


def _response(answer=LONG, **meta):
    return SimpleNamespace(
        answer=answer,
        follow_ups=[
            FollowUpSuggestion(text="How can I lower it?", category="suggested"),
            FollowUpSuggestion(text="What foods help?", category="suggested"),
        ],
        evidence=[],
        meta=ChatMeta(response_mode="semantic", **meta),
    )


def _llm(**kwargs):
    data = {"answer": LONG, "summary": "Short summary that must not replace the answer.", "blocks": []}
    data.update(kwargs)
    return SimpleNamespace(**data)


def test_long_answer_is_the_summary_unchanged():
    semantic = build_semantic_response(_response(), _context(), _llm())
    assert semantic.summary == LONG
    assert "Short summary" not in semantic.summary
    assert semantic.summary.count(".") > 3


def test_summary_field_does_not_replace_the_answer():
    semantic = build_semantic_response(
        _response(), _context(), _llm(blocks=[{"type": "text", "text": "A side note."}])
    )
    assert semantic.summary == LONG
    assert semantic.blocks[0].text == "A side note."


def test_report_and_lookup_paths_keep_the_full_answer():
    context = _context(intent=IntentType.report_explanation)
    report = build_semantic_response(_response(), context, _llm(), path="structured_report_overview")
    lookup = build_semantic_response(_response(), context, _llm(), path="structured_blood")
    assert report.summary == LONG and lookup.summary == LONG
    assert any(block.type == "metric_group" for block in report.blocks)
    assert any(block.type == "metric" for block in lookup.blocks)
    assert report.blocks[0].values[0].value == 9.1


def test_missing_evidence_drops_the_card_and_keeps_the_answer():
    semantic = build_semantic_response(
        _response(),
        _context(),
        _llm(blocks=[
            {"type": "metric", "evidence": ["blood.not_a_marker.latest"]},
            {"type": "insight", "text": "Glucose points the same way.", "evidence": ["blood.missing.latest"]},
            {"type": "metric", "evidence": ["blood.hba1c.latest"], "values": [{"value": 1.0}]},
        ]),
    )
    assert semantic.summary == LONG
    assert [block.type for block in semantic.blocks] == ["insight", "metric"]
    assert semantic.blocks[0].evidence == []
    assert semantic.blocks[1].values[0].value == 9.1


def test_comparison_without_history_is_omitted():
    semantic = build_semantic_response(
        _response(),
        _context(),
        _llm(blocks=[{"type": "comparison", "evidence": ["blood.hba1c.trend"], "text": "It rose."}]),
    )
    assert semantic.summary == LONG
    assert semantic.blocks == []


def test_comparison_uses_recorded_history_only():
    context = _context(comparisons=[Comparison(topic="hba1c", previous_value=8.0, current_value=9.1, direction="increased")])
    semantic = build_semantic_response(
        _response(),
        context,
        _llm(blocks=[{"type": "comparison", "evidence": ["blood.hba1c.trend"]}]),
    )
    assert semantic.blocks[0].values[0].previous == 8.0
    assert semantic.blocks[0].values[0].value == 9.1


def test_safety_block_hides_model_cards_and_keeps_the_safe_answer():
    semantic = build_semantic_response(
        _response("Please seek urgent care.", status="safety_block"),
        _context(),
        _llm(blocks=[{"type": "text", "text": "Stop your statin tonight."}]),
    )
    assert semantic.summary == "Please seek urgent care."
    assert semantic.blocks == []


def test_finalize_does_not_rewrite_a_semantic_answer():
    answer = f"{LONG}\n\nThis is not a diagnosis. This is not a diagnosis."
    response = ChatResponse(conversation_id="c", answer=answer, meta=ChatMeta(response_mode="semantic"))
    response.semantic = build_semantic_response(response, _context(), _llm())
    before = response.answer
    finalize_response(response, "Why is my HbA1c high?")
    assert response.answer == before
    assert response.semantic.summary == before


def test_follow_ups_are_capped_once_and_unsafe_ones_stay_rejected():
    suggestions = [
        FollowUpSuggestion(text=f"What does point {i} mean?", category="suggested") for i in range(5)
    ]
    response = ChatResponse(
        conversation_id="c",
        answer=LONG,
        follow_ups=suggestions,
        meta=ChatMeta(response_mode="semantic"),
    )
    response.semantic = build_semantic_response(response, _context(), _llm())
    assert len(response.semantic.follow_ups) == 5
    finalize_response(response, "Why is my HbA1c high?")
    assert len(response.follow_ups) == 5
    assert response.semantic.follow_ups == [item.text for item in response.follow_ups]
    brief = FollowUpBrief()
    assert not valid_question("Should I start a statin?", brief)
    assert not valid_question("Should I take a medicine?", brief)
