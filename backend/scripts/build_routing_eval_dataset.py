"""Generate CURA's versioned routing evaluation dataset.

The generated cases contain no real patient data. They intentionally emphasize
near-identical general/personal pairs and contextual follow-ups.
"""

from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "cura_routing_eval_500.jsonl"

TOPICS = [
    ("hba1c", "HbA1c"),
    ("ldl", "LDL"),
    ("hdl", "HDL"),
    ("cholesterol", "cholesterol"),
    ("triglycerides", "triglycerides"),
    ("vitamin_d", "Vitamin D"),
    ("vitamin_b12", "Vitamin B12"),
    ("tsh", "TSH"),
    ("ferritin", "ferritin"),
    ("crp", "CRP"),
    ("creatinine", "creatinine"),
    ("hemoglobin", "hemoglobin"),
    ("bilirubin", "bilirubin"),
    ("uric_acid", "uric acid"),
    ("fasting_blood_glucose", "fasting blood glucose"),
]

rows: list[dict] = []


def add(
    message: str,
    *,
    intent: str,
    source: str = "none",
    operation: str = "general_answer",
    personal: bool = False,
    historical: bool = False,
    document: bool = False,
    time_scope: str = "none",
    previous_message: str | None = None,
    previous_intent: str | None = None,
    previous_personal: bool = False,
    topic: str | None = None,
    document_available: bool = False,
    language: str = "en",
) -> None:
    rows.append(
        {
            "id": f"routing-{len(rows) + 1:04d}",
            "language": language,
            "current_message": message,
            "previous_user_message": previous_message,
            "previous_intent": previous_intent,
            "previous_personal_data_used": previous_personal,
            "current_topic": topic,
            "uploaded_document_available": document_available,
            "expected": {
                "intent": intent,
                "source": source,
                "operation": operation,
                "requires_personal_data": personal,
                "requires_historical_data": historical,
                "requires_document_search": document,
                "requires_clarification": intent == "clarification",
                "time_range": time_scope,
            },
        }
    )


for key, name in TOPICS:
    for template in [
        "What is {x}?",
        "What does {x} do in the body?",
        "Why can {x} become high?",
        "Why can {x} become low?",
        "What is a healthy {x} level?",
        "What are common causes of abnormal {x}?",
        "How does exercise affect {x}?",
        "How does sleep affect {x}?",
        "What foods can help improve {x}?",
        "How can someone improve {x}?",
        "What lifestyle changes can help lower my {x}?",
        "Explain {x} in simple terms.",
    ]:
        add(
            template.format(x=name),
            intent="general_health_question",
            topic=key,
        )
    for template in [
        "What is my {x}?",
        "Show me my latest {x}.",
        "What was my most recent {x} result?",
        "Can you retrieve my {x} value?",
    ]:
        add(
            template.format(x=name),
            intent="lab_result_lookup",
            source="lab_results",
            operation="lookup",
            personal=True,
            time_scope="latest",
            topic=key,
        )
    for template in [
        "Is my {x} high?",
        "What does my {x} result mean?",
        "Please interpret my latest {x}.",
        "Based on my {x} result, what should I discuss with my clinician?",
    ]:
        add(
            template.format(x=name),
            intent="lab_result_interpretation",
            source="lab_results",
            operation="interpret",
            personal=True,
            time_scope="latest",
            topic=key,
        )
    for template, scope in [
        ("What was my {x} previously?", "previous"),
        ("Has my {x} changed over time?", "historical"),
        ("How has my {x} changed over the last 3 months?", "3_months"),
        ("How has my {x} changed over the last 6 months?", "6_months"),
        ("Show my 12-month {x} trend.", "12_months"),
    ]:
        add(
            template.format(x=name),
            intent="health_trend_analysis",
            source="blood_reports",
            operation="trend" if scope != "previous" else "compare",
            personal=True,
            historical=True,
            time_scope=scope,
            topic=key,
        )

for report_name in [
    "Bio-AI report",
    "metabolic score",
    "metabolic age",
    "cardiac risk assessment",
    "oxidative stress assessment",
    "dyslipidemia assessment",
]:
    add(
        f"Show me my latest {report_name}.",
        intent="bio_ai_report_lookup",
        source="bio_ai_report",
        operation="lookup",
        personal=True,
        time_scope="latest",
    )
    add(
        f"Explain my {report_name}.",
        intent="bio_ai_report_interpretation",
        source="bio_ai_report",
        operation="retrieve_and_explain",
        personal=True,
        time_scope="latest",
    )
    add(
        f"How has my {report_name} changed?",
        intent="health_trend_analysis",
        source="bio_ai_trends",
        operation="trend",
        personal=True,
        historical=True,
        time_scope="historical",
    )

for noun in ["PDF", "uploaded report", "selected document", "lab document", "scan"]:
    for question in [
        f"What does this {noun} say about LDL?",
        f"Summarize this {noun}.",
        f"Explain the abnormal values in this {noun}.",
        f"Find my HbA1c in this {noun}.",
    ]:
        add(
            question,
            intent="uploaded_document_query",
            source="uploaded_documents",
            operation="retrieve_and_explain",
            document=True,
            document_available=True,
        )

for key, name in TOPICS[:10]:
    add(
        "Is that high?",
        intent="lab_result_interpretation",
        source="lab_results",
        operation="interpret",
        personal=True,
        time_scope="latest",
        previous_message=f"What is my {name}?",
        previous_intent="latest_result",
        previous_personal=True,
        topic=key,
    )
    add(
        "What was the previous one?",
        intent="health_trend_analysis",
        source="lab_results",
        operation="compare",
        personal=True,
        historical=True,
        time_scope="previous",
        previous_message=f"What is my {name}?",
        previous_intent="latest_result",
        previous_personal=True,
        topic=key,
    )
    add(
        "Why can it become high?",
        intent="general_health_question",
        previous_message=f"What is {name}?",
        previous_intent="general_health_question",
        topic=key,
    )
    add(
        f"What lifestyle changes can help lower {name}?",
        intent="general_health_question",
        previous_message=f"What is my {name}?",
        previous_intent="latest_result",
        previous_personal=True,
        topic=key,
    )

for message, intent in [
    ("What foods support heart health?", "nutrition_question"),
    ("How much exercise is generally recommended?", "fitness_question"),
    ("What is metformin commonly used for?", "medication_question"),
    ("What are common symptoms of iron deficiency?", "symptom_question"),
    ("When is cholesterol screening recommended?", "preventive_health_question"),
    ("What generally increases diabetes risk?", "medical_risk_question"),
    ("Hello Cura", "casual_conversation"),
    ("Thank you", "casual_conversation"),
]:
    for suffix in ["", " Please keep it simple.", " Give me a short explanation."]:
        add(message + suffix, intent=intent)

for message in [
    "Tell me about my cholesterol.",
    "Show me my report.",
    "Compare those results.",
    "What about that one?",
    "Use my assessment.",
    "Check the report I mentioned.",
]:
    add(message, intent="clarification", operation="clarify")

MULTILINGUAL = [
    ("hi", "LDL क्या है?", "What is my LDL?"),
    ("mr", "LDL म्हणजे काय?", "माझा LDL किती आहे?"),
    ("pa", "LDL ਕੀ ਹੈ?", "ਮੇਰਾ LDL ਕਿੰਨਾ ਹੈ?"),
    ("gu", "LDL શું છે?", "મારું LDL કેટલું છે?"),
    ("bn", "LDL কী?", "আমার LDL কত?"),
]
for language, general, personal in MULTILINGUAL:
    for index in range(5):
        add(
            general + (" সাধারণভাবে বলুন।" if language == "bn" and index else ""),
            intent="general_health_question",
            topic="ldl",
            language=language,
        )
        add(
            personal,
            intent="lab_result_lookup",
            source="lab_results",
            operation="lookup",
            personal=True,
            time_scope="latest",
            topic="ldl",
            language=language,
        )


def main() -> None:
    if len(rows) < 500:
        raise SystemExit(f"Dataset too small: {len(rows)}")
    if len({row["id"] for row in rows}) != len(rows):
        raise SystemExit("Duplicate IDs")
    OUT.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    print(f"wrote {len(rows)} cases to {OUT}")


if __name__ == "__main__":
    main()
