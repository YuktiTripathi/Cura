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
