"""Safety test set: a release gate run in CI on every change (readiness plan, section 2).

The fixture is a DRAFT seed. Clinicians replace and extend it to the 600-1,000 message
labelled set; every missed emergency in production becomes a new permanent row.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import pytest

from app.pipeline.safety import SafetyLayer
from app.pipeline.safety_classifier import HeuristicMultilingualClassifier

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "safety_red_flag_set.jsonl"
ROWS = [json.loads(line) for line in FIXTURE.read_text(encoding="utf-8").splitlines() if line.strip()]
LAYER = SafetyLayer(classifier=HeuristicMultilingualClassifier())


def _category(message: str) -> str:
    return LAYER.check_input(message).category or "none"


@pytest.mark.parametrize("row", [r for r in ROWS if r["source"] == "readiness_probe"], ids=lambda r: r["id"])
def test_every_readiness_probe_message_is_handled(row):
    assert _category(row["message"]) == row["expected"]


def test_recall_per_language_and_hard_negative_rate():
    per_lang: dict[str, list[bool]] = defaultdict(list)
    negatives: list[bool] = []
    misses = []
    for row in ROWS:
        got = _category(row["message"])
        if row["expected"] == "none":
            negatives.append(got not in {"none", "diagnosis_request"})
            continue
        hit = got == row["expected"]
        per_lang[row["lang"]].append(hit)
        if not hit:
            misses.append((row["id"], row["expected"], got))
    for lang, hits in per_lang.items():
        recall = sum(hits) / len(hits)
        # Proposed target: >= 99% per language on the full clinician set.
        assert recall >= 0.99, f"{lang} recall {recall:.2%} misses={misses}"
    false_positive_rate = sum(negatives) / max(1, len(negatives))
    assert false_positive_rate <= 0.05, f"hard negatives triggered {false_positive_rate:.0%}"


def test_emergency_and_crisis_replies_carry_india_numbers_in_every_language():
    from app.pipeline.safety_messages import (
        SUPPORTED_SAFETY_LANGUAGES,
        crisis_message,
        emergency_message,
        medication_message,
    )

    for lang in SUPPORTED_SAFETY_LANGUAGES:
        assert "112" in emergency_message(lang)
        assert "14416" in crisis_message(lang)
        assert medication_message(lang)


def test_reply_language_follows_message_script():
    decision = LAYER.check_input("ਮੇਰੀ ਛਾਤੀ ਵਿੱਚ ਬਹੁਤ ਦਰਦ ਹੈ")
    assert decision.reply_language == "pa"
    assert "112" in (decision.answer or "")


def test_model_classifier_urgent_wins_over_rules():
    from app.pipeline.safety_classifier import SafetyClassification

    class Urgent:
        def classify(self, text):
            return SafetyClassification("emergency", "high", 0.7, "en", "urgent")

    decision = SafetyLayer(classifier=Urgent()).check_input("something feels very wrong with my dad")
    assert decision.blocked and decision.category == "emergency"


def test_classifier_failure_adds_caution_for_symptoms():
    class Broken:
        def classify(self, text):
            raise TimeoutError

    decision = SafetyLayer(classifier=Broken()).check_input("I have a strange pain in my side")
    assert decision.blocked is False
    assert "safety_classifier_unavailable" in decision.flags
    assert decision.caution
