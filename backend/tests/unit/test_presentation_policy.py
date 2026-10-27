from app.contracts.common import AnswerDepth, IntentType, KnowledgeScope
from app.contracts.health_context import HealthContext
from app.pipeline.answer_shape import omit_duplicate_closing_offer, presentation_note, separate_answer_layout
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


def test_closing_offer_starts_its_own_paragraph():
    raw = "Vitamin D is slightly low and less central to the above picture. Would you like a plain-language summary focused on blood sugar, iron status, or your lipid levels?"
    laid = separate_answer_layout(raw)
    assert laid.endswith("lipid levels?")
    assert "\n\nWould you like a plain-language summary" in laid
    assert "picture. Would you like" not in laid


def test_closing_offer_leaves_a_bullet_list():
    raw = "- Iron is low.\n- Lipids need context. Would you like a summary of the lipid results?"
    laid = separate_answer_layout(raw)
    assert laid.index("lipid results?") > laid.index("Lipids need context.")
    assert "\n\nWould you like a summary" in laid
    assert not laid.strip().splitlines()[-1].lstrip().startswith("-")


def test_bracketed_offer_leaves_the_bullet():
    raw = "- Vitamin D is slightly low, chloride and creatinine are below the report's reference range, and MPV is mildly high. [Would you like this summarized for your clinician or explained in simpler terms?]"
    laid = separate_answer_layout(raw)
    assert laid.endswith("simpler terms?")
    assert "[Would you like" not in laid
    assert "\n\nWould you like this summarized" in laid
    assert not laid.strip().splitlines()[-1].lstrip().startswith("-")


def test_already_separated_offer_keeps_one_break():
    raw = "The lipid pattern is the main finding.\n\nWould you like this explained in simpler terms?"
    assert separate_answer_layout(raw) == raw


def test_citations_and_ranges_stay_bracketed():
    raw = "The cited result is unchanged [1]. The report range is [70-100]."
    assert separate_answer_layout(raw) == raw


def test_duplicate_chip_is_removed_from_the_answer():
    raw = "These shifts are not emergencies.\n\nWould you like this summarized for your clinician?"
    chip = "Would you like this summarized for your clinician?"
    assert omit_duplicate_closing_offer(raw, [chip]) == "These shifts are not emergencies."
    assert "Would you like" in omit_duplicate_closing_offer(raw, ["What changed since last time?"])


def test_explanation_without_an_offer_is_unchanged():
    raw = "HbA1c reflects average glucose over about three months."
    assert separate_answer_layout(raw) == raw


def test_questions_inside_an_explanation_stay_inline():
    raw = "What is HbA1c? It reflects average glucose. A higher value means more sugar was in the blood."
    assert separate_answer_layout(raw) == raw


def test_structured_follow_up_is_not_inserted_into_the_answer():
    raw = "Your lipid pattern is the main finding."
    assert separate_answer_layout(raw) == raw
    assert "Would you like" not in raw


def test_general_prompt_includes_the_note():
    ctx = HealthContext(
        intent=IntentType.general_health_question,
        answer_depth=AnswerDepth.simple,
        knowledge_scope=KnowledgeScope.general,
    )
    messages = PromptBuilder().build(ctx, "", "What is heart health?")
    assert "PRESENTATION:" in messages[1]["content"]
    assert "NARRATIVE LENGTH:" in messages[1]["content"]
    assert "about 30 to 60 words" in messages[1]["content"]
    assert "The whole answer is bullets" in messages[0]["content"]
    assert "Do not end the answer with a question" in messages[0]["content"]
    assert "PLAIN LANGUAGE" in messages[0]["content"]
    assert "higher-than-expected blood sugar" in messages[0]["content"]
    assert "Never invent a fact" in messages[0]["content"]
    assert "without bold labels" in messages[1]["content"]


def test_personal_prompt_uses_the_same_plain_language_policy():
    from app.pipeline.prompt_builder import PLAIN_LANGUAGE, SAFETY_INSTRUCTIONS

    assert "Assume the person has no medical background" in PLAIN_LANGUAGE
    assert PLAIN_LANGUAGE in SAFETY_INSTRUCTIONS
    assert "prediction is not a diagnosis" in SAFETY_INSTRUCTIONS
    assert "Do not change a calculated amount." in SAFETY_INSTRUCTIONS
    assert "everyday food names" in presentation_note("What should I eat for dinner?")
