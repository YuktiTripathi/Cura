from app.pipeline.followup_generator import general_continuations


def test_real_topic_gets_topic_follow_ups():
    out = general_continuations("What is HbA1c?")
    assert out and all("HbA1c" in q for q in out)


def test_question_about_the_previous_answer_is_not_wrapped_in_a_template():
    for text in ("Is it serious?", "Why is it low?", "explain more simply", "Can I fix it with sunlight?", "Should I worry?"):
        assert general_continuations(text) == [], text
