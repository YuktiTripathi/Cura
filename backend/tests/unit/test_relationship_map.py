"""Relationship map: configuration checks and generic related-marker selection."""

import json

import pytest

from app.contracts.blood import BloodMarker
from app.contracts.common import MarkerFlag
from app.pipeline.evidence_inventory import _select_measurements
from app.retrieval.relationship_map import (
    RelationshipMapError,
    group_measurements,
    load_relationship_map,
    related_keys,
    unavailable_in_catalogue,
    unresolved_catalogue_ids,
)


def test_map_loads_and_marks_missing_inventory_ids():
    data = load_relationship_map()
    assert data["schema_version"]
    assert "ferritin" in unavailable_in_catalogue()
    assert "postprandial_glucose" in unavailable_in_catalogue()


def test_invalid_map_reports_a_missing_field(tmp_path, monkeypatch):
    from app.retrieval import relationship_map as module

    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"panels": []}), encoding="utf-8")
    monkeypatch.setattr(module, "_PATH", path)
    module.load_relationship_map.cache_clear()
    with pytest.raises(RelationshipMapError, match="missing"):
        module.load_relationship_map()
    module.load_relationship_map.cache_clear()


def test_unknown_relationship_target_is_rejected(tmp_path, monkeypatch):
    from app.retrieval import relationship_map as module

    data = json.loads(module._PATH.read_text(encoding="utf-8"))
    data["relationships"].append({"primary": "not_a_marker", "related": []})
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(module, "_PATH", path)
    module.load_relationship_map.cache_clear()
    with pytest.raises(RelationshipMapError, match="not_a_marker"):
        module.load_relationship_map()
    module.load_relationship_map.cache_clear()


def test_aliases_resolve_and_unresolved_ids_stay_unretrieved():
    assert "hdl" in related_keys(["ldl"], "Why is my LDL high?")
    assert "uibc" in unresolved_catalogue_ids() or "rdw" in unresolved_catalogue_ids()


def test_definition_does_not_expand_and_cause_question_does():
    assert related_keys(["ldl"], "What is LDL cholesterol?") == []
    extra = related_keys(["ldl"], "Why is my LDL high?")
    assert "hdl" in extra and "triglycerides" in extra
    assert "tsh" not in extra


def test_thyroid_relationship_includes_tsh_and_ordinary_ldl_does_not():
    linked = related_keys(["ldl"], "Is my LDL related to my thyroid?")
    assert "tsh" in linked
    assert "tsh" not in related_keys(["ldl"], "What does my LDL mean?")


def test_creatinine_selects_kidney_markers_not_lipids():
    extra = related_keys(["creatinine"], "Why is my creatinine high?")
    assert "egfr" in extra or "bun" in extra
    assert "ldl" not in extra
    assert len(extra) <= 6


def test_ferritin_selects_available_iron_markers_without_inventing_a_value():
    markers = [
        BloodMarker(id="ferritin", key="ferritin", name="Ferritin", value=8, unit="ng/mL", flag=MarkerFlag.low),
        BloodMarker(id="iron", key="iron", name="Iron", value=35, unit="ug/dL", flag=MarkerFlag.low),
        BloodMarker(id="ldl", key="ldl", name="LDL", value=162, unit="mg/dL", flag=MarkerFlag.high),
        BloodMarker(id="hemoglobin", key="hemoglobin", name="Hemoglobin", value=11, unit="g/dL", flag=MarkerFlag.low),
    ]
    chosen = _select_measurements("MARKER_LOOKUP", "Why is my ferritin low?", markers, broad=False)
    keys = {item.key for item in chosen}
    assert "ferritin" in keys and "iron" in keys and "hemoglobin" in keys
    assert "ldl" not in keys
    assert all(item.value is not None for item in chosen)


def test_groups_keep_values_and_do_not_duplicate():
    rows = [
        {"key": "ldl", "name": "LDL", "value": 162, "unit": "mg/dL", "reference_high": 100},
        {"key": "hdl", "name": "HDL", "value": 44, "unit": "mg/dL"},
        {"key": "hba1c", "name": "HbA1c", "value": 6.3, "unit": "%"},
    ]
    groups = group_measurements(rows)
    labels = [group["label"] for group in groups]
    assert any("Lipid" in label or "Heart" in label or "lipid" in label.lower() for label in labels)
    flat = [row["key"] for group in groups for row in group["measurements"]]
    assert flat.count("ldl") == 1
    assert groups[0]["measurements"][0]["value"] == 162 or any(
        row["value"] == 162 for group in groups for row in group["measurements"]
    )


def test_follow_ups_stay_on_the_latest_topic():
    from app.pipeline.followup_generator import on_topic

    crp = on_topic(
        [
            "Can a recent infection temporarily raise my CRP?",
            "What is the difference between CRP and ESR?",
            "Which fruits are suitable for my HbA1c?",
            "Can a recent infection temporarily raise my CRP?",
        ],
        "What is CRP?",
        "Your CRP is 7.3 mg/L.",
    )
    assert crp == [
        "Can a recent infection temporarily raise my CRP?",
        "What is the difference between CRP and ESR?",
    ]
    kidney = on_topic(
        [
            "What does my creatinine value indicate?",
            "What foods should I limit for triglycerides?",
        ],
        "How is my kidney profile?",
        "Creatinine is 0.85 mg/dL.",
    )
    assert kidney == ["What does my creatinine value indicate?"]


def test_follow_up_cap_is_five_and_medication_is_still_rejected():
    from app.contracts.chat import ChatMeta, ChatResponse
    from app.contracts.followup import FollowUpSuggestion
    from app.pipeline.followup_generator import FollowUpBrief, valid_question
    from app.pipeline.visible_output import finalize_response

    response = ChatResponse(
        conversation_id="c",
        answer="Your LDL is high.",
        follow_ups=[FollowUpSuggestion(text=f"What about point {i} now?", category="suggested") for i in range(6)],
        meta=ChatMeta(response_mode="rich"),
    )
    finalize_response(response, "Why is my LDL high?")
    assert len(response.follow_ups) == 5
    assert not valid_question("Should I start a statin?", FollowUpBrief())
