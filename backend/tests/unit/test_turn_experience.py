from app.contracts.followup import FollowUpSuggestion
from app.contracts.presentation import PresentedFinding, ResponseMode, StructuredResponse
from app.contracts.turn_experience import ExperienceBlockKind, StreamPolicy
from app.pipeline.experience_orchestrator import ExperienceOrchestrator


def test_orchestrator_builds_ordered_semantic_blocks_from_validated_presentation():
    presentation = StructuredResponse(
        mode=ResponseMode.interpretation,
        summary="Your LDL is 138 mg/dL.",
        findings=[
            PresentedFinding(
                label="LDL cholesterol",
                value="138",
                unit="mg/dL",
                status="high",
                canonical_key="ldl",
            )
        ],
        interpretation="This is above the reference range in the retrieved report.",
        personal_relevance="This is relevant to your heart-health goal.",
        uncertainties=["One result alone does not establish a diagnosis."],
        next_steps=["Compare it with your previous LDL result."],
    )
    experience = ExperienceOrchestrator().build(
        answer="Your LDL is 138 mg/dL. This is above the reference range.",
        presentation=presentation,
        follow_ups=[FollowUpSuggestion(text="Would you like to see the trend?", category="suggested")],
        safety_mode="STANDARD",
    )

    assert experience.stream_policy == StreamPolicy.semantic_blocks
    assert experience.direct_answer == "Your LDL is 138 mg/dL."
    assert experience.key_facts[0].canonical_key == "ldl"
    kinds = [item.kind for item in experience.blocks]
    assert kinds[0] == ExperienceBlockKind.direct_answer
    # A single lookup already stated in the direct answer is intentionally not repeated.
    assert ExperienceBlockKind.key_facts not in kinds
    assert ExperienceBlockKind.interpretation in kinds
    assert ExperienceBlockKind.next_step not in kinds
    assert ExperienceBlockKind.continuation in kinds
    assert [item.sequence for item in experience.blocks] == list(range(len(experience.blocks)))


def test_high_risk_turns_are_complete_only():
    presentation = StructuredResponse(
        mode=ResponseMode.safety,
        summary="Please seek urgent medical care.",
    )
    experience = ExperienceOrchestrator().build(
        answer="Please seek urgent medical care.",
        presentation=presentation,
        safety_mode="EMERGENCY",
        escalation="emergency",
    )
    assert experience.stream_policy == StreamPolicy.complete_only
