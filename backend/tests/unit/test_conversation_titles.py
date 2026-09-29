from fastapi.testclient import TestClient

from app.main import app
from app.pipeline.conversation_title import conversation_title

client = TestClient(app)
H = {"X-Cura-User-Id": "demo-user-001"}


def test_conversation_titles_are_useful():
    assert conversation_title("What is my HbA1c and why is it high compared to last year?") == "Understanding my HbA1c"
    assert conversation_title("Show me my latest blood report") == "Blood report review"
    assert conversation_title("Explain my cholesterol and LDL") == "My cholesterol questions"
    assert conversation_title("Explain my latest Bio-AI report") == "Bio-AI risk explanation"
    assert conversation_title("What should I know about my nutrition?") == "Nutrition guidance"
    assert conversation_title("What is my sugar level?") == "My blood sugar questions"


def test_conversation_title_truncates_long_generic_messages():
    long_msg = "Please help me understand this very long question about rest " * 4
    title = conversation_title(long_msg)
    assert title != "Cura conversation"
    assert len(title) <= 48
    assert title.endswith("…")


def test_conversation_title_fallback():
    assert conversation_title("   ") == "Cura conversation"


def test_chat_persists_useful_title_and_lists_it():
    res = client.post("/api/v1/chat", headers=H, json={"message": "What is my HbA1c?"})
    assert res.status_code == 200
    cid = res.json()["conversation_id"]
    listed = client.get("/api/v1/conversations", headers=H).json()
    row = next(item for item in listed if item["id"] == cid)
    assert row["title"] == "Understanding my HbA1c"
    stolen = client.get("/api/v1/conversations", headers={"X-Cura-User-Id": "demo-user-002"}).json()
    assert cid not in {item["id"] for item in stolen}
