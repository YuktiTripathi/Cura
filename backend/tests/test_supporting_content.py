from types import SimpleNamespace

from app.pipeline import supporting_content
from app.pipeline.semantic_blocks import _Index, validate_block


def _marker(key, flag="low"):
    return SimpleNamespace(key=key, value=1.0, name=key, unit="u", flag=flag, reference_low=0, reference_high=2, measured_at=None)


def _index(*keys):
    ctx = SimpleNamespace(markers=[_marker(k) for k in keys], bio_ai_risks=[], comparisons=[], baselines=[])
    return _Index(ctx), ctx


def test_education_block_resolves_from_library_not_model_text():
    index, ctx = _index("cholesterol_total")
    block = validate_block({"type": "medical_education", "ref": "edu.cholesterol_total", "text": "invented 999"}, index, ctx)
    assert block and block.lines and all("999" not in line for line in block.lines)


def test_unknown_or_absent_reference_is_dropped():
    index, ctx = _index("cholesterol_total")
    assert validate_block({"type": "medical_education", "ref": "edu.not_a_marker"}, index, ctx) is None
    assert validate_block({"type": "medical_education", "ref": "edu.hemoglobin_hb"}, index, ctx) is None
    assert validate_block({"type": "medical_relationship", "ref": "rel.a.b"}, index, ctx) is None


def test_candidates_list_ids_only_for_markers_on_record():
    index, _ = _index("cholesterol_total")
    refs = {m["ref"] for m in supporting_content.candidates(index)}
    assert "edu.cholesterol_total" in refs and not any("hemoglobin" in r for r in refs)



def test_general_relationship_needs_no_measurement_of_either_end():
    index, _ = _index("cholesterol_total")
    index.focus = ("hdl_cholesterol_direct",)  # asked about, not measured
    block = validate_block({"type": "medical_relationship", "ref": "rel.cholesterol_total.hdl_cholesterol_direct"}, index, _)
    assert block and block.scope == "general" and block.lines


def test_relationship_unrelated_to_the_discussion_is_rejected():
    index, ctx = _index("ferritin")
    assert validate_block({"type": "medical_relationship", "ref": "rel.cholesterol_total.hdl_cholesterol_direct"}, index, ctx) is None


def test_education_for_an_unmeasured_result_is_general_only():
    index, ctx = _index("cholesterol_total")
    index.focus = ("hdl_cholesterol_direct",)
    block = validate_block({"type": "medical_education", "ref": "edu.hdl_cholesterol_direct"}, index, ctx)
    assert block and block.scope == "general"
    assert not any(ch.isdigit() for line in block.lines[:1] for ch in line)  # no personal value invented


def test_essential_education_follows_the_resolved_intent_without_the_model():
    index, _ = _index("hdl_cholesterol_direct")
    index.focus = ("hdl_cholesterol_direct",)
    assert supporting_content.essential(index, "blood_marker_explanation", "Why is my HDL low?") == [
        ("medical_education", "edu.hdl_cholesterol_direct")
    ] or supporting_content.essential(index, "blood_marker_explanation", "Why is my HDL low?")[0][0] == "medical_education"
    assert supporting_content.essential(index, "latest_result", "What is my HDL?") == []


def test_historical_report_education_uses_that_reports_flag():
    index, ctx = _index("hdl_cholesterol_direct")
    index.markers["hdl_cholesterol_direct"].flag = "high"  # the discussed (historical) report's flag
    block = validate_block({"type": "medical_education", "ref": "edu.hdl_cholesterol_direct"}, index, ctx)
    from app.biomarkers import medical_registry as r
    high = r.entry_for("hdl_cholesterol_direct")["result_explanations"]["high"][0]
    assert high in block.lines
