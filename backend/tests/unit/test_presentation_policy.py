from app.contracts.common import AnswerDepth, IntentType, KnowledgeScope
from app.contracts.health_context import HealthContext
from app.pipeline.answer_shape import presentation_note, separate_answer_layout
from app.pipeline.prompt_builder import PromptBuilder


def test_emergency_note_puts_action_first():
    note = presentation_note("I have chest pain and trouble breathing.")
    assert "immediate safety action" in note
    assert "No analogy" in note


def test_follow_up_stays_short():
    assert "No headings" in presentation_note("Is that dangerous?")


def test_glued_heading_is_split_onto_its_own_line():
    raw = (
        "Heart health refers to the pump. **Key factors in heart health**\n"
        "* Blood pressure control: steady pressure.\n"
        "* Healthy nutrition: vegetables and grains."
    )
    laid = separate_answer_layout(raw)
    assert "\n\n**Key factors in heart health**\n\n* Blood pressure" in laid
    glued = "Smooth flow. **Key factors** * **Blood pressure:** Steady pressure."
    assert "\n\n**Key factors**\n\n* **Blood pressure:**" in separate_answer_layout(glued)
    assert "pump." in laid


def test_general_prompt_includes_the_note():
    ctx = HealthContext(
        intent=IntentType.general_health_question,
        answer_depth=AnswerDepth.simple,
        knowledge_scope=KnowledgeScope.general,
    )
    messages = PromptBuilder().build(ctx, "", "What is heart health?")
    assert "PRESENTATION:" in messages[1]["content"]
    assert "NARRATIVE LENGTH:" in messages[1]["content"]
    assert "fewer than 120 words is fine" in messages[1]["content"]
    assert "2 to 4 Markdown bullets" in messages[0]["content"]
    assert "without bold labels" in messages[1]["content"]
