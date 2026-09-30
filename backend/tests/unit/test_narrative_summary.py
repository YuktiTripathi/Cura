from fastapi.testclient import TestClient

from app.contracts.blood import BloodMarker
from app.contracts.common import AnswerDepth, IntentType, MarkerFlag
from app.contracts.health_context import HealthContext, MissingItem
from app.llm.structured import parse_llm_structured
from app.main import app
from app.pipeline.lab_parameters import canonicalize_marker_name, display_name_for
from app.pipeline.narrative import (
    build_narrative_summary,
    canonical_display_label,
    dedupe_markers,
    dedupe_missing,
    flatten_narrative,
    summary_style_for,
    wants_narrative_summary,
    wants_raw_snapshot,
)
from app.pipeline.query_planner import build_query_plan

client = TestClient(app)
H = {"X-Cura-User-Id": "demo-user-001"}
IRON = {"X-Cura-User-Id": "eval-user-iron"}

SUMMARY_QUESTIONS = [
    "Summarize my health scenario",
    "How am I doing?",
    "What should I focus on?",
    "What matters most?",
]


def _marker(**kwargs) -> BloodMarker:
    data = {
        "id": "m1",
        "key": "ldl",
        "name": "LDL",
        "value": 140.0,
        "unit": "mg/dL",
        "flag": MarkerFlag.high,
    }
    data.update(kwargs)
    return BloodMarker(**data)


def _context(markers: list[BloodMarker], missing: list[MissingItem] | None = None) -> HealthContext:
    return HealthContext(
        intent=IntentType.health_scenario,
        answer_depth=AnswerDepth.broad,
        markers=markers,
        missing=missing or [],
    )


def test_summary_questions_default_to_narrative():
    for message in SUMMARY_QUESTIONS:
        plan = build_query_plan(message)
        assert wants_narrative_summary(message, plan)
        assert summary_style_for(message, plan).value == "NARRATIVE_HEALTH_SUMMARY"
        assert not wants_raw_snapshot(message, plan)


def test_view_all_results_uses_raw_snapshot():
    message = "View all results from my latest report"
    plan = build_query_plan(message)
    assert wants_raw_snapshot(message, plan)
    assert not wants_narrative_summary(message, plan)
    assert summary_style_for(message, plan).value == "RAW_HEALTH_SNAPSHOT"


def test_canonical_aliases_dedupe_to_one_display_label():
    pairs = [
        (("albumin", "Albumin"), ("serum_albumin", "Serum Albumin")),
        (("bilirubin", "Bilirubin Total"), ("serum_bilirubin_total", "Serum Bilirubin Total")),
        (("iron", "Iron Serum"), ("serum_iron", "Serum Iron")),
        (("hematocrit", "PCV"), ("pcv", "Hematocrit")),
        (("platelets", "Platelet Count"), ("plt", "PLT")),
        (("wbc", "WBC"), ("tlc", "TLC")),
        (("hemoglobin", "Hb"), ("haemoglobin", "Haemoglobin")),
    ]
    for (key_a, name_a), (key_b, name_b) in pairs:
        canonical = canonicalize_marker_name(key_a)
        assert canonicalize_marker_name(key_b) == canonical
        assert canonicalize_marker_name(name_a) == canonical
        assert canonicalize_marker_name(name_b) == canonical
        rows = dedupe_markers(
            [
                _marker(id="a", key=key_a, name=name_a, value=12.0, flag=MarkerFlag.normal),
                _marker(id="b", key=key_b, name=name_b, value=None, flag=MarkerFlag.missing),
            ]
        )
        assert len(rows) == 1
        assert canonical_display_label(rows[0]) == display_name_for(canonical)
        present = {canonical}
        leftover = dedupe_missing(
            [MissingItem(key=key_b, name=name_b, reason="not_in_reports")],
            present,
        )
        assert leftover == []


def test_related_red_cell_and_iron_abnormalities_form_one_theme():
    markers = [
        _marker(id="hb", key="hb", name="Hb", value=10.5, unit="g/dL", flag=MarkerFlag.low),
        _marker(id="mcv", key="mcv", name="MCV", value=72.0, unit="fL", flag=MarkerFlag.low),
        _marker(id="mch", key="mch", name="MCH", value=24.0, unit="pg", flag=MarkerFlag.low),
        _marker(id="iron", key="iron_serum", name="Iron Serum", value=35.0, unit="µg/dL", flag=MarkerFlag.low),
        _marker(id="ldl", key="ldl", name="LDL", value=92.0, unit="mg/dL", flag=MarkerFlag.normal),
        _marker(id="hdl", key="hdl", name="HDL", value=52.0, unit="mg/dL", flag=MarkerFlag.normal),
    ]
    overall, themes, raw, next_action = build_narrative_summary(_context(markers), message="How am I doing?")
    attention = [item for item in themes if item.status != "reassuring"]
    assert len(attention) == 1
    labels = [item.label.lower() for item in attention[0].related_findings]
    assert len(labels) >= 3
    assert any("hemoglobin" in label or "haemoglobin" in label for label in labels)
    assert any("iron" in label for label in labels)
    reassuring = [item for item in themes if item.status == "reassuring"]
    assert reassuring
    assert "ldl" not in (reassuring[0].interpretation or "").lower()
    assert "hdl" not in (reassuring[0].interpretation or "").lower()
    text = flatten_narrative(overall, themes, next_action).lower()
    assert "the main pattern that stands out" in text or "look reassuring" in text
    assert "prioritized findings" not in text
    assert "going well:" not in text
    assert next_action
    assert raw
    assert "anaemia" not in text or "not a diagnosis" in text
    assert "iron deficiency" not in text


def test_missing_information_only_when_relevant():
    markers = [
        _marker(id="ldl", key="ldl", name="LDL", value=160.0, flag=MarkerFlag.high),
        _marker(id="tg", key="triglycerides", name="Triglycerides", value=180.0, flag=MarkerFlag.high),
    ]
    missing = [MissingItem(key="ferritin", name="Ferritin", reason="not_in_reports")]
    _, themes, _, _ = build_narrative_summary(
        _context(markers, missing),
        message="How am I doing?",
    )
    attention = next(item for item in themes if item.status != "reassuring")
    assert attention.missing_information == []
    _, iron_themes, _, _ = build_narrative_summary(
        _context(
            [
                _marker(id="hb", key="hemoglobin", name="Haemoglobin", value=10.5, unit="g/dL", flag=MarkerFlag.low),
                _marker(id="iron", key="iron", name="Serum Iron", value=35.0, unit="µg/dL", flag=MarkerFlag.low),
            ],
            missing,
        ),
        message="How am I doing?",
    )
    iron = next(item for item in iron_themes if item.status != "reassuring")
    assert any("ferritin" in row.lower() for row in iron.missing_information)


def test_chat_health_summary_does_not_dump_the_full_report():
    body = client.post("/api/v1/chat", headers=H, json={"message": "Summarize my health scenario"}).json()
    pres = body["presentation"]
    answer = body["answer"].lower()
    assert pres["summary_style"] == "NARRATIVE_HEALTH_SUMMARY"
    assert pres["findings"] == []
    assert pres["themes"]
    assert 3 <= len(pres["themes"]) <= 5
    assert pres["raw_findings"]
    assert len(pres["raw_findings"]) > len(pres["themes"])
    assert "prioritized findings from the latest blood report" not in answer
    assert "going well:" not in answer
    assert "urea" not in answer
    raw_labels = " ".join(item["label"].lower() for item in pres["raw_findings"])
    assert "urea" in raw_labels or "creatinine" in raw_labels
    reassuring = [item for item in pres["themes"] if item["status"] == "reassuring"]
    assert reassuring
    interp = f" {(reassuring[0].get('interpretation') or '').lower()} "
    assert " alt " not in interp
    assert " ast " not in interp
    assert "urea" not in interp
    assert "not a diagnosis" in answer
    assert pres["next_steps"]


def test_chat_view_all_results_exposes_raw_table():
    body = client.post("/api/v1/chat", headers=H, json={"message": "View all results"}).json()
    pres = body["presentation"]
    assert pres["summary_style"] == "RAW_HEALTH_SNAPSHOT"
    assert pres["findings"]
    assert len(pres["findings"]) >= 8
    labels = [item["label"] for item in pres["findings"]]
    assert len(labels) == len(set(labels))


def test_chat_related_iron_pattern_is_grouped():
    body = client.post("/api/v1/chat", headers=IRON, json={"message": "How am I doing?"}).json()
    pres = body["presentation"]
    attention = [item for item in pres["themes"] if item["status"] != "reassuring"]
    assert len(attention) == 1
    related = attention[0]["related_findings"]
    assert len(related) >= 3
    answer = body["answer"].lower()
    assert "the main pattern that stands out" in answer or "look reassuring" in answer
    assert "prioritized findings" not in answer
    labels = [item["label"].lower() for item in related]
    assert any("hemoglobin" in label or "haemoglobin" in label for label in labels)
    assert any("iron" in label for label in labels)


def test_llm_theme_payload_is_parsed():
    parsed = parse_llm_structured(
        {
            "answer": "Most of your major health areas look reassuring, but the main pattern that stands out is red cell findings.",
            "overall_summary": "Most of your major health areas look reassuring, but the main pattern that stands out is red cell findings.",
            "themes": [
                {
                    "title": "Red cell and iron findings",
                    "priority": "high",
                    "status": "needs_attention",
                    "supporting_fact_ids": ["hemoglobin", "iron"],
                    "interpretation": "Haemoglobin and iron are both low and sit together as one pattern.",
                    "missing_information": ["Ferritin is not available in this report, which would help interpret this pattern."],
                    "next_step": "Review this red cell and iron pattern with a clinician.",
                }
            ],
        }
    )
    assert parsed.overall_summary.startswith("Most of your major health areas")
    assert parsed.themes[0]["title"] == "Red cell and iron findings"
    assert parsed.themes[0]["supporting_fact_ids"] == ["hemoglobin", "iron"]
