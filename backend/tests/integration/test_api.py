from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json()["status"] == "ok"


def test_chat_requires_auth():
    res = client.post("/api/v1/chat", json={"message": "hi"})
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "UNAUTHORIZED"


def test_conversation_persistence_and_feedback():
    headers = {"X-Cura-User-Id": "demo-user-001"}
    res = client.post("/api/v1/chat", headers=headers, json={"message": "What is my latest Vitamin D?"})
    cid = res.json()["conversation_id"]
    detail = client.get(f"/api/v1/conversations/{cid}", headers=headers)
    assert len(detail.json()["messages"]) >= 2
    fb = client.post(
        "/api/v1/feedback",
        headers=headers,
        json={"conversation_id": cid, "rating": "up", "comment": "helpful"},
    )
    assert fb.status_code == 200
    deleted = client.delete(f"/api/v1/conversations/{cid}", headers=headers)
    assert deleted.status_code == 200


def test_rewind_keeps_earlier_messages_only():
    headers = {"X-Cura-User-Id": "demo-user-001"}
    first = client.post("/api/v1/chat", headers=headers, json={"message": "What is LDL?"})
    cid = first.json()["conversation_id"]
    client.post("/api/v1/chat", headers=headers, json={"message": "What is HDL?", "conversation_id": cid})
    before = client.get(f"/api/v1/conversations/{cid}", headers=headers).json()["messages"]
    assert len(before) >= 4
    rewind = client.post(f"/api/v1/conversations/{cid}/rewind", headers=headers, json={"keep": 2})
    assert rewind.status_code == 200
    after = client.get(f"/api/v1/conversations/{cid}", headers=headers).json()["messages"]
    assert len(after) == 2
    stolen = client.post(
        f"/api/v1/conversations/{cid}/rewind",
        headers={"X-Cura-User-Id": "demo-user-002"},
        json={"keep": 0},
    )
    assert stolen.status_code == 404
