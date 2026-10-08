"""Dev-only prompt inspector: observes the real request, never changes it, never in production."""

import json

from app.core.config import settings
from app.llm import prompt_inspector
from app.llm.openai_compatible import OpenAICompatibleLLMClient


def _payload():
    client = OpenAICompatibleLLMClient(model="openai/gpt-5-mini", api_key="k")
    system = "You are Cura.\n\nCLINICAL SAFETY\nDo not diagnose.\n\nRESPONSE PLANNING (decide yourself, every time)\nChoose the shape.\n\nReturn a JSON object with: answer."
    evidence = {"question": "q", "primary_facts": [{"code": "hba1c", "value": 9.1, "unit": "%", "status": "high", "source": "measured blood result"}],
                "supporting_facts": [{"code": "type_2_diabetes", "score": 78, "status": "high", "source": "Bio-AI risk assessment (not a diagnosis)"}],
                "trend": [{"code": "hba1c", "previous": 8.4, "latest": 9.1}]}
    user = ("Mode: PERSONAL_HEALTH\nANSWER EVIDENCE JSON:\n" + json.dumps(evidence) + "\nNo medical evidence was retrieved.\n"
            "Conversation focus (topic and follow-up only; never a source of current lab values): \nAnswer depth: simple\n"
            "User question: What does my HbA1c mean?\n")
    return client._build_payload([{"role": "system", "content": system}, {"role": "user", "content": user}], "json_schema")


def test_components_and_health_breakdown():
    record = prompt_inspector.analyze_payload(_payload())
    comps = record["components"]
    assert {"system_prompt", "response_format_instructions", "output_contract", "health_context",
            "medical_evidence", "conversation", "current_query", "application_instructions"} <= set(comps)
    assert comps["current_query"]["chars"] == len("User question: What does my HbA1c mean?\n")
    assert record["output_schema"]["chars"] > 100  # the strict JSON schema is a request parameter
    items = record["health_context_breakdown"]["_items"]
    assert any(i.startswith("hba1c=9.1") for i in items["blood_markers"])
    assert items["bio_ai_values"] == ["type_2_diabetes=78 (high)"]
    assert items["previous_values"] == ["hba1c: 8.4 -> 9.1"]


def test_disabled_by_default_and_in_production(monkeypatch):
    monkeypatch.setattr(settings, "cura_prompt_debug", False)
    assert prompt_inspector.before_call(_payload(), "json_schema") is None
    monkeypatch.setattr(settings, "cura_prompt_debug", True)
    monkeypatch.setattr(settings, "app_env", "production")
    assert prompt_inspector.before_call(_payload(), "json_schema") is None


def test_dump_written_in_development_and_request_unchanged(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "cura_prompt_debug", True)
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "cura_prompt_debug_dir", str(tmp_path))
    payload = _payload()
    before = json.dumps(payload, sort_keys=True)
    record = prompt_inspector.before_call(payload, "json_schema")
    prompt_inspector.after_call(record, {"input_tokens": 1234, "output_tokens": 210})
    assert json.dumps(payload, sort_keys=True) == before
    dump = (tmp_path / next(p.name for p in tmp_path.iterdir() if p.suffix == ".txt")).read_text()
    assert "===== SYSTEM" in dump and "===== HEALTH CONTEXT" in dump and "===== CURRENT QUERY" in dump
    assert prompt_inspector.RECENT[-1]["provider_usage"] == {"input_tokens": 1234, "output_tokens": 210}
