import json
from pathlib import Path

from app.routing.schemas import JevDecision


DATASET = Path(__file__).resolve().parents[1] / "fixtures" / "cura_routing_eval_500.jsonl"


def _rows():
    return [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines() if line]


def test_routing_dataset_has_500_unique_schema_valid_cases():
    rows = _rows()
    assert len(rows) >= 500
    assert len({row["id"] for row in rows}) == len(rows)
    for row in rows:
        JevDecision.model_validate(row["expected"])


def test_routing_dataset_contains_required_boundaries():
    rows = _rows()
    messages = {row["current_message"].lower(): row for row in rows}
    assert any("lifestyle changes" in message and "my ldl" in message for message in messages)
    assert any(message == "what is my ldl?" for message in messages)
    assert any(row["expected"]["requires_document_search"] for row in rows)
    assert any(row["expected"]["requires_historical_data"] for row in rows)
    assert any(row["previous_personal_data_used"] for row in rows)
    assert {"en", "hi", "mr", "pa", "gu", "bn"}.issubset({row["language"] for row in rows})


def test_near_identical_general_personal_pairs_are_labeled_differently():
    rows = _rows()
    general = next(row for row in rows if row["current_message"] == "What is LDL?")
    personal = next(row for row in rows if row["current_message"] == "What is my LDL?")
    assert general["expected"]["requires_personal_data"] is False
    assert personal["expected"]["requires_personal_data"] is True
