"""Follow-ups spread across different areas of the member's results (breadth first)."""

from app.pipeline.followup_generator import Finding, FollowUpBrief, Risk, select_followups, theme_questions


def _f(key, name, theme, direction="low", value=10.0, unit="mg/dL"):
    return Finding(key=key, name=name, value=value, unit=unit, direction=direction, theme=theme)


def _brief(**kw):
    findings = [
        _f("glucose", "fasting glucose", "sugar", "high", 115),
        _f("triglycerides", "triglycerides", "lipids", "high", 206),
        _f("vitamin_d", "vitamin D", "vitamins", "low", 18.3, "ng/mL"),
        _f("iron", "serum iron", "iron", "low", 57, "ug/dL"),
    ]
    return FollowUpBrief(findings=findings, has_lifestyle=True, **kw)


def test_one_question_per_area_in_mixed_kinds():
    pairs = theme_questions(_brief())
    areas = [area for _q, area in pairs]
    assert len(areas) == len(set(areas)) == 4
    texts = [q for q, _a in pairs]
    assert any(t.startswith("What lifestyle changes") for t in texts)
    assert any(t.startswith("What does") for t in texts)
    assert any(t.startswith("What symptoms") for t in texts)


def test_diet_preference_shapes_the_food_question():
    pairs = theme_questions(_brief(diet="Vegetarian"))
    assert any(q.startswith("Which vegetarian foods can help my") for q, _a in pairs)


def test_areas_the_answer_did_not_explain_come_first_after_the_top_one():
    brief = _brief(answer_text="Your fasting glucose is high and vitamin D is low.")
    areas = [area for _q, area in theme_questions(brief)]
    assert areas[0] == "sugar"
    assert set(areas[1:3]) == {"lipids", "iron"}  # not named in the answer


def test_raised_bio_ai_scores_are_their_own_area():
    brief = FollowUpBrief(risks=[Risk("ox", "oxidative stress", 64.0, "high", True)], has_lifestyle=True)
    pairs = theme_questions(brief)
    assert pairs and pairs[0][1] == "bio:ox"
    assert "oxidative stress" in pairs[0][0]


def test_selection_gives_three_questions_without_repeating_an_area_or_a_whole_report_question():
    from app.pipeline.followup_generator import _area_of

    picks = select_followups(_brief(), current_question="Explain my report", count=3)
    assert len(picks) == 3
    areas = [_area_of(q, _brief()) for q in picks]
    named = [a for a in areas if a]
    assert len(named) == len(set(named))
    assert areas.count(None) <= 1


def test_food_questions_use_the_diet_on_record():
    picks = select_followups(_brief(diet="Vegetarian"), current_question="Explain my report", count=3)
    assert not any(q.startswith("What can I eat to") for q in picks)
    assert any(q.startswith("Which vegetarian foods can help my") for q in picks)


def test_general_follow_ups_use_the_models_on_topic_questions_and_drop_stock_ones():
    from app.pipeline.followup_generator import general_follow_ups

    model = [
        "What causes kidney function to drop over time?",
        "Which signs mean I should see a doctor?",
        "What foods are kinder to the kidneys?",
        "What does a routine blood test usually check?",
        "How is my creatinine doing?",
        "What does kidney function tests look at?",
    ]
    out = general_follow_ups(model, message="What do kidney function tests look at?", asked=[], shown=[])
    assert out == model[:3]


def test_general_follow_ups_return_nothing_when_fewer_than_two_are_usable():
    from app.pipeline.followup_generator import general_follow_ups

    assert general_follow_ups(["What does a routine blood test usually check?", "Anything else?"], message="What is iron?") == []
    assert general_follow_ups(None, message="What is iron?") == []


def test_general_answer_chips_are_four_and_on_topic():
    from app.pipeline.followup_generator import general_follow_ups

    out = general_follow_ups(
        ["How does fatty liver form?", "What are early signs of fatty liver?"],
        message="What is fatty liver?",
    )
    assert len(out) == 4
    assert all("fatty liver" in q.lower() for q in out)


def test_blood_versus_bio_ai_comparison_is_never_a_chip():
    from app.pipeline.followup_generator import is_cross_source

    assert is_cross_source("How does my Bio-AI report compare with my blood results?")
    assert is_cross_source("Why are my blood and Bio-AI cardiac health values different?")
    assert not is_cross_source("What does my Bio-AI score mean?")


def test_bio_ai_versus_blood_questions_are_never_offered():
    from app.pipeline.followup_generator import is_cross_source

    assert is_cross_source("Why are my blood and Bio-AI cardiac health values different?")
    assert is_cross_source("How does my Bio-AI report compare with my blood results?")
    assert not is_cross_source("What does a Healthy Cardiac Health Bio-AI score mean?")
