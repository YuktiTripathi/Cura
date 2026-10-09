from types import SimpleNamespace

from app.contracts.common import MarkerFlag
from app.pipeline.starters import HealthSnapshot
from app.pipeline.suggestion_engine import candidates_for, choose_suggestions


def _marker(key, name, flag=MarkerFlag.normal):
    return SimpleNamespace(key=key, name=name, flag=flag, value=1)


def test_blood_only_does_not_suggest_bio_ai():
    snap = HealthSnapshot(available=True, has_blood=True, markers=[_marker("ldl", "LDL", MarkerFlag.high)])
    ids = {item.id for item in candidates_for(snap)}
    assert "blood.overview" in ids
    assert "bio.overview" not in ids
    assert "cross.blood_bio" not in ids


def test_trend_requires_history():
    snap = HealthSnapshot(available=True, has_blood=True, markers=[_marker("hdl", "HDL")], marker_history={"hdl": 1})
    assert "blood.trend" not in {item.id for item in candidates_for(snap)}
    snap.marker_history = {"hdl": 2}
    assert "blood.trend" in {item.id for item in candidates_for(snap)}


def test_empty_profile_uses_general_education():
    chosen = choose_suggestions(HealthSnapshot(), salt="a")
    assert len(chosen) == 4
    assert all(item.category == "general_education" for item in chosen)


def test_new_salt_changes_the_set_not_just_the_order():
    snap = HealthSnapshot(
        available=True,
        has_blood=True,
        has_bio=True,
        has_nutrition=True,
        markers=[_marker("ldl", "LDL"), _marker("hba1c", "HbA1c", MarkerFlag.high)],
        marker_history={"ldl": 2},
        lifestyle_topics={"sleep", "activity", "diet"},
    )
    first = [item.id for item in choose_suggestions(snap, salt="conv-1")]
    second = [item.id for item in choose_suggestions(snap, salt="conv-2", avoid_ids=set(first))]
    assert first != second
    assert set(first).isdisjoint(second)


def test_no_test_package_wording():
    snap = HealthSnapshot(available=True, has_blood=True, has_bio=True, markers=[_marker("ldl", "LDL")])
    blob = " ".join(item.text for item in candidates_for(snap)).lower()
    assert "package" not in blob and "retest" not in blob and "book a test" not in blob
