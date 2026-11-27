import json

from app.contracts.unified_health import CategoryDetail, Finding, Provenance
from app.health_explanation.category_guidance import category_guidance
from app.health_explanation.category_story import CategoryProfile
from app.contracts.unified_health import SelfReportedFactor


class Fake:
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0
        self.seen = []

    def complete(self, messages, json_mode=False):
        self.calls += 1
        self.seen.append(messages[-1]["content"])
        data = json.loads(messages[-1]["content"])
        habit = (data.get("reported_habits") or ["general"])[0]
        status = data["findings"][0]["status"] if data["findings"] else "missing"
        return json.dumps({
            "influencing_factors": [{"text": f"Reported context {habit} with {status}.", "evidence_ids": ["f1"], "basis": "verified_context"}],
            "health_guidance": [{"text": f"Next step for {status}.", "evidence_ids": ["f1"], "purpose": "medical_review"}],
        })


def _detail(status="Within range", category="heart_circulation"):
    return CategoryDetail.model_construct(
        id=category,
        name="Heart",
        provenance=Provenance(blood_report_id="b1", bio_ai_report_id="r1"),
        findings=[Finding(id="m1", source_type="measured", name="LDL", status="within_range" if "Within" in status else "above_range", status_label=status)],
    )


def _profile(habit):
    return CategoryProfile("30s", "female", [SelfReportedFactor(key="diet", label="Diet", value=habit)])


def test_different_contexts_stay_different_and_cache():
    client = Fake({})
    calm = category_guidance(_detail("Within range"), _profile("walks daily"), "member-a", allow_model=True, client=client)
    active = category_guidance(_detail("Above range"), _profile("fried food most days"), "member-a", allow_model=True, client=client)
    assert calm.influencing_factors[0].text != active.influencing_factors[0].text
    assert "walks daily" in calm.influencing_factors[0].text
    assert "fried food" in active.influencing_factors[0].text
    again = category_guidance(_detail("Within range"), _profile("walks daily"), "member-a", allow_model=True, client=client)
    assert again.influencing_factors[0].text == calm.influencing_factors[0].text
    assert client.calls == 2


def test_members_do_not_share_a_cache_entry():
    client = Fake({})
    one = category_guidance(_detail(), _profile("member-a walks"), "iso-a", allow_model=True, client=client)
    two = category_guidance(_detail(), _profile("member-b walks"), "iso-b", allow_model=True, client=client)
    assert client.calls == 2
    assert "member-a" in one.influencing_factors[0].text
    assert "member-b" in two.influencing_factors[0].text
    category_guidance(_detail(), _profile("member-a walks"), "iso-b", allow_model=True, client=client)
    assert client.calls == 3


def test_model_failure_adds_no_personal_advice():
    class Boom:
        def complete(self, messages, json_mode=False):
            raise RuntimeError("down")

    guide = category_guidance(_detail("Above range"), _profile("walks daily"), "member-a", allow_model=True, client=Boom())
    assert guide.influencing_factors == []
    assert guide.health_guidance == []


def test_numbers_and_allergy_are_dropped():
    class Numbered:
        def complete(self, messages, json_mode=False):
            return json.dumps({"influencing_factors": [{"text": "Your score is 80."}], "health_guidance": [{"text": "Ask your doctor to review this result."}]})

    numbered = category_guidance(_detail(), _profile("walks daily"), "member-c", allow_model=True, client=Numbered())
    assert numbered.influencing_factors == []
    assert numbered.health_guidance[0].text.startswith("Ask your doctor")
    skipped = category_guidance(_detail(category="allergy"), _profile("walks daily"), "member-c", allow_model=True, client=Numbered())
    assert skipped.health_guidance == []
