import json

from app.llm.models import LLMStructuredOutput
from app.llm.openai_compatible import OpenAICompatibleLLMClient
from app.llm.structured import parse_llm_structured, public_answer_text


SAMPLE = {
    "answer": "HDL is often called good cholesterol; LDL is often called bad cholesterol.",
    "claims": [{"text": "HDL and LDL are different lipoproteins", "evidence_codes": []}],
    "recommendation_candidates": [
        {"category": "lifestyle_actions", "text": "Eat more fibre.", "evidence_codes": ["ldl"]}
    ],
    "follow_up_questions": ["What is a healthy HDL level?"],
    "safety_flags": [],
    "escalation": None,
}


def test_parse_object_and_json_string():
    from_obj = parse_llm_structured(SAMPLE)
    from_str = parse_llm_structured(json.dumps(SAMPLE))
    fenced = parse_llm_structured("```json\n" + json.dumps(SAMPLE) + "\n```")
    assert from_obj.answer == SAMPLE["answer"]
    assert from_str.answer == SAMPLE["answer"]
    assert fenced.answer == SAMPLE["answer"]
    assert from_obj.follow_up_questions == ["What is a healthy HDL level?"]
    assert len(from_obj.recommendation_candidates) == 1
    assert from_obj.claims[0].text.startswith("HDL")


def test_plain_text_passthrough():
    parsed = parse_llm_structured("HDL carries cholesterol to the liver.")
    assert parsed.answer == "HDL carries cholesterol to the liver."
    assert parsed.follow_up_questions == []


def test_missing_answer_does_not_dump_json():
    raw = json.dumps({"claims": [], "follow_up_questions": [], "safety_flags": []})
    parsed = parse_llm_structured(raw)
    assert "{" not in parsed.answer
    assert "claims" not in parsed.answer


def test_malformed_json_extracts_answer():
    raw = '{"answer": "HDL helps remove cholesterol.", "claims": [}'
    parsed = parse_llm_structured(raw)
    assert parsed.answer == "HDL helps remove cholesterol."


def test_invalid_recommendation_category_is_dropped_not_dumped():
    raw = json.dumps(
        {
            "answer": "Your HbA1c is 5.5%.",
            "recommendation_candidates": [{"category": "prescribe_drugs", "text": "Take metformin"}],
            "follow_up_questions": [],
            "claims": ["HbA1c is available"],
            "safety_flags": ["check"],
            "escalation": "clinician",
        }
    )
    parsed = parse_llm_structured(raw)
    assert parsed.answer == "Your HbA1c is 5.5%."
    assert parsed.recommendation_candidates == []
    assert parsed.claims[0].text == "HbA1c is available"
    assert parsed.escalation == "clinician"
    assert parsed.safety_flags == ["check"]


def test_nested_answer_object_unwraps():
    parsed = parse_llm_structured({"answer": SAMPLE})
    assert parsed.answer == SAMPLE["answer"]


def test_complete_structured_never_returns_raw_json(monkeypatch):
    client = OpenAICompatibleLLMClient(
        provider="openrouter", base_url="http://local", model="x", api_key="test"
    )
    monkeypatch.setattr(client, "complete", lambda messages, json_mode=False: json.dumps(SAMPLE))
    result = client.complete_structured([{"role": "user", "content": "q"}])
    assert isinstance(result, LLMStructuredOutput)
    assert result.answer == SAMPLE["answer"]
    assert "recommendation_candidates" not in result.answer


def test_public_answer_text_strips_implementation_json():
    text = public_answer_text(json.dumps(SAMPLE))
    assert text == SAMPLE["answer"]
    assert "follow_up_questions" not in text
