import json
from collections import defaultdict
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "cura_assistant_eval_40.jsonl"
client = TestClient(app)


def _cases():
    rows = []
    for line in FIXTURE.read_text().splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def test_assistant_eval_40_capability_pass_rate():
    conversations = {}
    results = []
    by_cap = defaultdict(lambda: {"pass": 0, "fail": 0})
    for case in _cases():
        headers = {"X-Cura-User-Id": case["user"]}
        payload = {"message": case["message"]}
        parent = case.get("follow_up_of")
        if parent and parent in conversations:
            payload["conversation_id"] = conversations[parent]
        body = client.post("/api/v1/chat", headers=headers, json=payload).json()
        if case.get("setup") or case["id"] in {row.get("follow_up_of") for row in _cases()}:
            conversations[case["id"]] = body["conversation_id"]
        ok, reason = _check(case, body)
        results.append((case["id"], case["capability"], ok, reason, body["answer"][:180]))
        bucket = by_cap[case["capability"]]
        bucket["pass" if ok else "fail"] += 1
        if not ok:
            print(f"FAIL {case['id']} [{case['capability']}]: {reason} :: {body['answer'][:160]}")
    passed = sum(1 for item in results if item[2])
    assert passed >= 32, f"capability pass {passed}/40 buckets={dict(by_cap)}"
    for cap, counts in by_cap.items():
        total = counts["pass"] + counts["fail"]
        assert counts["pass"] / total >= 0.5, f"{cap} {counts}"


def _check(case, body) -> tuple[bool, str]:
    answer = body.get("answer") or ""
    low = answer.lower()
    meta = body.get("meta") or {}
    if case.get("expected_status") and meta.get("status") != case["expected_status"]:
        return False, f"status {meta.get('status')}"
    if case.get("expected_personal") is False:
        if meta.get("supershyft_called") is True and case["capability"] == "explain":
            return False, "personal retrieval on general question"
    for phrase in case.get("must_include") or []:
        if phrase.lower() not in low and phrase not in answer:
            return False, f"missing {phrase}"
    if case.get("must_include_any"):
        if not any(p.lower() in low or p in answer for p in case["must_include_any"]):
            return False, f"missing any {case['must_include_any']}"
    for phrase in case.get("forbidden") or []:
        if phrase.lower() in low:
            return False, f"forbidden {phrase}"
    if "I had trouble formatting that answer" in answer:
        return False, "formatting leak"
    if case.get("expected_llm_called") is False and meta.get("llm_called") is True:
        return False, "llm called on lookup"
    if case.get("expected_operation"):
        want = str(case["expected_operation"]).upper()
        ops = {str(item).upper() for item in (meta.get("operations") or [])}
        aliases = {"LOOKUP": {"LOOKUP", "RETRIEVE"}, "SUMMARIZE": {"SUMMARIZE"}}
        allowed = aliases.get(want, {want})
        if ops and not (ops & allowed) and want not in {str(meta.get("question_type") or "").upper()}:
            if want == "LOOKUP" and meta.get("question_type") == "personal_lookup":
                pass
            elif ops and not (ops & allowed):
                return False, f"operation {ops}"
    if case.get("expect_sources"):
        blob = " ".join(
            str(row.get("source") or "") for row in (meta.get("source_outcomes") or [])
        ).lower()
        for src in case["expect_sources"]:
            token = {"blood": "blood", "bio_ai": "bio", "questionnaire": "questionnaire", "goals": "goal"}.get(src, src)
            requested = False
            for row in meta.get("source_outcomes") or []:
                if token in str(row.get("source") or "").lower() and str(row.get("status") or "") != "not_requested":
                    requested = True
            if not requested and token not in blob and not meta.get("supershyft_called"):
                return False, f"missing source {src}"
    return True, "ok"
