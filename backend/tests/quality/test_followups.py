"""Follow-up suggestions: grounded in the member's findings, moving the conversation along."""

from app.contracts.bio_ai import BioAIRisk
from app.contracts.blood import BloodMarker
from app.contracts.common import MarkerFlag as F
from app.pipeline.followup_generator import build_brief, select_followups, stage_of, valid_question
from tests.quality.test_conversation_quality import ask

M = [
    BloodMarker(id="1", key="hba1c", name="Hba1c", value=9.1, unit="%", flag=F.high),
    BloodMarker(id="2", key="triglycerides", name="Triglycerides", value=265.9, unit="mg/dl", flag=F.high),
    BloodMarker(id="3", key="ferritin", name="Ferritin", value=22.6, unit="ng/ml", flag=F.low),
    BloodMarker(id="4", key="mcv", name="MCV", value=80.1, unit="fL", flag=F.low),
    BloodMarker(id="5", key="hdl", name="HDL", value=45, unit="mg/dl", flag=F.normal),
]
R = [
    BioAIRisk(code="type_2_diabetes", name="Type 2 diabetes", score=70, status="High"),
    BioAIRisk(code="hypertension", name="Hypertension", score=17, status="Healthy"),
]


def test_opening_questions_lead_with_the_most_important_finding():
    qs = select_followups(build_brief(markers=M, risks=R), current_question=None, count=4)
    assert len(qs) == 4
    assert "HbA1c" in qs[0]
    assert len({stage_of(q) for q in qs}) == 4  # one per step, not four of a kind


def test_suggestions_move_forward_and_skip_what_was_asked():
    asked = ["Help me understand my latest blood report", "Why is my HbA1c high?"]
    qs = select_followups(build_brief(markers=M, risks=R, asked=asked), current_question=asked[-1], count=3)
    assert all(stage_of(q) not in {"overview", "abnormal"} for q in qs)
    assert not any("Why is my HbA1c high" in q for q in qs)


def test_earlier_suggestions_are_not_repeated():
    shown = ["Should I see a doctor about my HbA1c?", "How serious is my HbA1c of 9.1%?"]
    qs = select_followups(build_brief(markers=M, risks=R, shown=shown), current_question="What can I eat?", count=3)
    assert not set(qs) & set(shown)


def test_model_questions_are_validated_against_the_members_data():
    brief = build_brief(markers=M, risks=R)
    assert valid_question("Is my HbA1c linked to my Type 2 diabetes score?", brief)
    assert not valid_question("Why is my PSA high?", brief)  # not in this report
    assert not valid_question("Does my NAFLD score matter?", brief)  # assessment not in the report
    assert not valid_question("What dose of metformin should I take?", brief)
    assert not valid_question("Do you have any new symptoms?", brief)
    assert not valid_question("Is my HbA1c of 7.2% ok?", brief)  # wrong value
    assert not valid_question("Could you please explain in detail everything about every single result in my report?", brief)


def test_connections_pair_tests_from_the_same_body_system():
    qs = select_followups(build_brief(markers=M, risks=[]), current_question="Why is my ferritin low?",
                          count=3)
    assert any("ferritin" in q.lower() and "mcv" in q.lower() for q in qs)


def test_chat_follow_ups_are_personal_and_change_over_the_conversation():
    first = ask("demo-user-001", "Help me understand my latest blood report")
    texts1 = [f["text"] for f in first["follow_ups"]]
    assert 3 <= len(texts1) <= 4
    assert all("?" in t for t in texts1)
    assert not any(t in {"What should I do next?", "Explain this pattern", "What is missing?"} for t in texts1)
    second = ask("demo-user-001", texts1[0], first["conversation_id"])
    texts2 = [f["text"] for f in second["follow_ups"]]
    assert 2 <= len(texts2) <= 3
    assert not set(texts2) & set(texts1[:1])


def test_welcome_suggestions_are_built_from_findings():
    from app.pipeline.starters import HealthSnapshot
    from app.pipeline.suggestion_engine import choose_suggestions

    snap = HealthSnapshot(available=True, markers=M, bio_risks=R, has_blood=True, has_bio=True)
    picked = choose_suggestions(snap)
    assert len(picked) == 4
    assert "HbA1c" in picked[0].text
    assert all(item.category.startswith("journey_") for item in picked)
