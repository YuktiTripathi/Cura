from app.contracts.common import IntentType
from app.pipeline.intent import classify_intent


def test_my_result_stays_on_hdl():
    intent, topic, _name, _depth = classify_intent(
        "What does my result mean?",
        follow_up_topic="hdl",
        prior_personal=True,
    )
    assert intent == IntentType.blood_marker_explanation
    assert topic == "hdl"


def test_this_prediction_stays_on_the_cardiac_score():
    intent, topic, _name, _depth = classify_intent(
        "Does this prediction mean I have heart disease?",
        follow_up_topic="cardiac_health",
        prior_personal=True,
    )
    assert intent == IntentType.bio_ai_explanation
    assert topic == "cardiac_health"


def test_cardiac_risk_question_is_bio_ai_not_a_blood_summary():
    intent, topic, _name, _depth = classify_intent(
        "What does my cardiac health risk mean?",
        prior_personal=True,
    )
    assert intent == IntentType.bio_ai_explanation
    assert topic == "cardiac_health"


def test_naming_vitamin_d_leaves_hdl():
    intent, topic, _name, _depth = classify_intent(
        "What about my vitamin D?",
        follow_up_topic="hdl",
        prior_personal=True,
    )
    assert topic != "hdl"
    assert intent != IntentType.broad_health_summary
