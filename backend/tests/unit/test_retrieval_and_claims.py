"""Readiness plan 4.5 (hybrid retrieval) and 4.7 (claims tied to passages)."""

from __future__ import annotations

import pytest

from app.core.config import settings
from app.pipeline.claim_check import (
    map_claims_to_passages,
    revise_unsupported_answer,
    supporting_passages,
    unmapped_share,
)
from app.retrieval.hybrid import HybridMedicalKnowledgeProvider, ontology_topics, normalize_query
from app.retrieval.medical import MedicalEvidenceDoc


@pytest.fixture(autouse=True)
def allow_index(monkeypatch):
    monkeypatch.setattr(settings, "medical_require_reviewed", False)


@pytest.mark.parametrize(
    "question, topic",
    [
        ("what is hypertension", "hypertension"),
        ("is my bp ok", "hypertension"),
        ("what causes high sugar", "type_2_diabetes"),
        ("मेरा कोलेस्ट्रॉल कैसे कम करें", "cholesterol"),
        ("what does TSH measure", "tsh"),
    ],
)
def test_ontology_and_indic_questions_find_the_right_topic(question, topic):
    hits = HybridMedicalKnowledgeProvider().query(question)
    assert hits and any(topic in doc.topics for doc in hits)


def test_off_topic_question_returns_no_evidence():
    assert HybridMedicalKnowledgeProvider().query("who won the football match yesterday") == []


def test_generic_heart_health_does_not_retrieve_unrelated_condition_passages():
    hits = HybridMedicalKnowledgeProvider().query(
        "What do you mean by heart health in general terms?",
        topic="cardiac_health",
    )
    assert hits == []


def test_limit_is_three_by_default_and_capped_at_five():
    provider = HybridMedicalKnowledgeProvider(min_score=0.0)
    assert len(provider.query("diabetes cholesterol thyroid kidney blood pressure vitamin d")) <= 3
    assert len(provider.query("diabetes cholesterol thyroid kidney blood pressure vitamin d", limit=50)) <= 5


def test_query_is_normalized_to_english():
    assert "cholesterol" in normalize_query("मेरा कोलेस्ट्रॉल").lower()
    assert {"type_2_diabetes", "hba1c"} <= ontology_topics("my sugar is high")


def test_embedding_scorer_can_lift_a_passage():
    class Semantic:
        def scores(self, query, docs):
            return [1.0 if "vitamin_d" in d.topics else 0.0 for d in docs]

    hits = HybridMedicalKnowledgeProvider(embedder=Semantic()).query("why do I feel tired in winter")
    assert hits and "vitamin_d" in hits[0].topics


def _doc(name, text):
    return MedicalEvidenceDoc(name=name, url=f"https://x/{name}", source_type="guideline", tier=1,
                              topics=("t",), keywords=("k",), excerpt=text)


def test_each_claim_maps_to_its_supporting_passage():
    docs = [
        _doc("A", "Hypertension is high blood pressure and raises the risk of heart and kidney disease."),
        _doc("B", "Vitamin D deficiency can weaken bones and is linked to limited sunlight."),
    ]
    answer = (
        "Hypertension means high blood pressure and raises heart disease risk. "
        "Low vitamin D can weaken bones, often because of limited sunlight."
    )
    mapped = map_claims_to_passages(answer, docs)
    assert [index for _, _, index in mapped] == [0, 1]
    assert [d.name for d in supporting_passages(answer, docs)] == ["A", "B"]
    assert unmapped_share(answer, docs) == 0.0


def test_unrelated_claims_are_unmapped_and_their_source_is_not_cited():
    docs = [_doc("A", "Hypertension is high blood pressure.")]
    answer = "Regular sleep of seven to nine hours supports recovery and mood for most adults."
    assert supporting_passages(answer, docs) == []
    assert unmapped_share(answer, docs) == 1.0


def test_claim_repair_does_not_append_source_pointer_disclaimers():
    docs = [_doc("A", "The heart pumps blood around the body.")]
    answer, flags = revise_unsupported_answer(
        "The heart pumps blood around the body. Regular sleep supports recovery and mood.",
        docs,
    )
    assert flags
    assert "source pointer" not in answer.lower()
    assert "guideline quotation" not in answer.lower()
