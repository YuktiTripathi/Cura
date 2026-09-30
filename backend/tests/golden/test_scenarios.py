from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
H = {"X-Cura-User-Id": "demo-user-001"}


def chat(message: str, conversation_id: str | None = None):
    return client.post("/api/v1/chat", headers=H, json={"message": message, "conversation_id": conversation_id})


def test_latest_vitamin_d():
    res = chat("What is my latest Vitamin D?")
    assert res.status_code == 200
    body = res.json()
    assert "12.6" in body["answer"]
    assert "18 Aug 2026" in body["answer"] or "2026-08-18" in str(body.get("presentation") or {})
    assert body["evidence"]
    assert body["evidence"][0]["report_id"] == "blood-002"
    assert "blood-002" not in body["answer"]
    assert "42.0" not in body["answer"]


def test_previous_vitamin_d():
    res = chat("What was my previous Vitamin D result?")
    body = res.json()
    assert res.status_code == 200
    assert "18.0" in body["answer"]
    assert "9 Jul 2026" in body["answer"] or "2026-07-09" in str(body.get("presentation") or {})
    assert body["evidence"][0]["report_id"] == "blood-001"
    assert "blood-001" not in body["answer"]


def test_vitamin_d_changed():
    res = chat("Has my Vitamin D changed?")
    body = res.json()
    assert "12.6" in body["answer"]
    assert "18.0" in body["answer"]
    assert "decreased" in body["answer"]
    assert "-5.4" in body["answer"] or "absolute" in body["answer"].lower()


def test_cardiac_score_ambiguous_and_retrieved():
    res = chat("What is my cardiac health score?")
    body = res.json()
    assert res.status_code == 200
    assert body["meta"]["status"] == "ambiguous"
    assert "bioai-a" not in body["answer"]
    assert "bioai-b" not in body["answer"]
    assert "which report" in body["answer"].lower()
    assert body["evidence"]
    assert any(e["risk_code"] == "cardiac_health" for e in body["evidence"])
    assert {e["report_id"] for e in body["evidence"]} >= {"bioai-a", "bioai-b"} or any(
        s.get("source_id") in {"bioai-a", "bioai-b"} for s in body["provenance"]["sources"]
    )


def test_cardiac_why_increased():
    res = chat("Why is my cardiac score increased?")
    body = res.json()
    assert "diagnos" not in body["answer"].lower() or "not a medical diagnosis" in body["answer"].lower()
    assert "30" in body["answer"] and "48" in body["answer"]
    assert body["evidence"]


def test_nafld():
    res = chat("What is my NAFLD risk?")
    body = res.json()
    assert body["meta"]["status"] == "ambiguous" or "NAFLD" in body["answer"]
    assert body["evidence"]
    assert any(e.get("risk_code") == "nafld" for e in body["evidence"])


def test_compare_cardiac_scores():
    res = chat("Compare my cardiac scores.")
    body = res.json()
    assert body["meta"]["status"] != "ambiguous"
    assert "30" in body["answer"] and "48" in body["answer"]
    assert "bioai-a" not in body["answer"]
    assert "bioai-b" not in body["answer"]


def test_same_date_ambiguity():
    res = chat("What is my cardiac score?")
    body = res.json()
    assert body["meta"]["status"] == "ambiguous"
    assert "not pick" in body["answer"].lower() or "which report" in body["answer"].lower()


def test_risk_scores_same_date_clarifies_without_llm_fallback():
    res = chat("What are my risk scores?")
    body = res.json()
    assert res.status_code == 200
    assert body["meta"]["status"] == "ambiguous"
    assert body["meta"]["llm_called"] is False
    assert "which report" in body["answer"].lower()
    assert "bioai-a" not in body["answer"]
    assert "bioai-b" not in body["answer"]
    assert "I had trouble formatting that answer." not in body["answer"]
    assert "30" not in body["answer"]
    assert "48" not in body["answer"]


def test_follow_up_that():
    first = chat("What is my Vitamin D?")
    cid = first.json()["conversation_id"]
    second = chat("Is that normal?", cid)
    body = second.json()
    assert "Vitamin D" in body["answer"] or "vitamin d" in body["answer"].lower()
    assert "12.6" in body["answer"]


def test_cross_user_isolation():
    a = chat("What is my latest Vitamin D?").json()
    other = client.post(
        "/api/v1/chat",
        headers={"X-Cura-User-Id": "demo-user-002"},
        json={"message": "What is my latest Vitamin D?"},
    ).json()
    assert "12.6" in a["answer"]
    assert "42.0" in other["answer"]
    assert "42.0" not in a["answer"]
    assert "12.6" not in other["answer"]
    listed = client.get("/api/v1/conversations", headers={"X-Cura-User-Id": "demo-user-002"})
    ids = {row["id"] for row in listed.json()}
    assert a["conversation_id"] not in ids
    stolen = client.get(f"/api/v1/conversations/{a['conversation_id']}", headers={"X-Cura-User-Id": "demo-user-002"})
    assert stolen.status_code == 404
