from types import SimpleNamespace

from app.contracts.personalization import KnownLifestyle, RecentContext
from app.pipeline.personal_projection import project_personalization


def _perso():
    return SimpleNamespace(
        primary_health_goal="energy",
        communication_preference=SimpleNamespace(value="simple"),
        dietary_preferences=["non_vegetarian"],
        known_lifestyle=KnownLifestyle(sleep="6 hours", activity="rarely", diet="non_vegetarian", alcohol="never", smoking="never"),
        recent_user_context=RecentContext(),
        compact_longitudinal=SimpleNamespace(model_dump=lambda mode="json": {"x": 1}),
        improved_domains=["a"],
        reassuring_domains=["b"],
    )


def test_only_fields_that_can_change_the_answer_are_sent():
    out = project_personalization(_perso(), entities=["vitamin_b12"])
    assert "alcohol" not in out.get("known_lifestyle", {}) and "smoking" not in out.get("known_lifestyle", {})
    assert "longitudinal" not in out


def test_a_general_question_sends_no_lifestyle_at_all():
    out = project_personalization(_perso(), entities=[])
    assert "known_lifestyle" not in out and "dietary_preferences" not in out


def test_food_question_sends_the_diet_and_history_only_when_asked():
    out = project_personalization(_perso(), entities=[], food_question=True)
    assert out["known_lifestyle"] == {"diet": "non_vegetarian"}
    assert out["dietary_preferences"] == ["non_vegetarian"]
    assert "longitudinal" in project_personalization(_perso(), entities=[], wants_history=True)
