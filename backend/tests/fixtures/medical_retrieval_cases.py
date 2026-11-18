"""Offline retrieval evaluation questions. No personal health data or expected patient values."""

CASES = [
    {"query": "What does HbA1c measure?", "expected_topics": ["hba1c"]},
    {"query": "What does LDL cholesterol mean?", "expected_topics": ["ldl", "cholesterol"]},
    {"query": "Why is vitamin D important?", "expected_topics": ["vitamin_d"]},
    {"query": "What does a creatinine blood test show?", "expected_topics": ["creatinine", "kidney_function"]},
    {"query": "What is eGFR used for?", "expected_topics": ["egfr", "kidney_function"]},
    {"query": "What does TSH measure?", "expected_topics": ["tsh", "thyroid"]},
    {"query": "What is hypertension?", "expected_topics": ["hypertension"]},
    {"query": "What is a Bio-AI risk score?", "expected_topics": ["bio_ai_default"]},
    {"query": "Who won the football game yesterday?", "expected_topics": []},
    {"query": "Explain insulin resistance", "expected_topics": ["type_2_diabetes", "hba1c"]},
]
