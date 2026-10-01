"""Biomarker routing when the sentence is in an Indic language Cura supports.

Before the fix, 'मेरा एलडीएल क्या है?' (LDL spelled in Devanagari) routed to a broad health summary:
lab aliases are Latin and nothing mapped Indic spellings of abbreviations to them. Possessive-free
status questions ('Vitamin D कम है क्या?') and follow-ups ('और HDL का क्या?') also missed the
personal lookup that their English equivalents get.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.pipeline.indic_terms import canonicalize_biomarker_terms
from app.pipeline.language import normalize_for_intent
from app.routing.jev_router import resolve_plan

client = TestClient(app)
H = {"X-Cura-User-Id": "demo-user-001"}


def _route(message: str):
    plan, _ = resolve_plan(canonicalize_biomarker_terms(message))
    return plan


@pytest.mark.parametrize(
    "message, topic",
    [
        ("मेरा एलडीएल क्या है?", "ldl"),
        ("मेरा LDL क्या है?", "ldl"),
        ("मेरा HDL कैसा है?", "hdl"),
        ("मेरा HbA1c कितना है?", "hba1c"),
        ("मेरा एचबीए1सी कितना है?", "hba1c"),
        ("मेरा एचएस-सीआरपी कितना है?", "crp"),
        ("मेरा hs-CRP कितना है?", "crp"),
        ("मेरा विटामिन डी कितना है?", "vitamin_d"),
        ("Vitamin D कम है क्या?", "vitamin_d"),
        ("विटामिन डी कम है क्या?", "vitamin_d"),
        ("मेरा टीएसएच ठीक है क्या?", "tsh"),
        ("माझा एलडीएल किती आहे?", "ldl"),
        ("ਮੇਰਾ ਐਲਡੀਐਲ ਕਿੰਨਾ ਹੈ?", "ldl"),
        ("મારું એલડીએલ કેટલું છે?", "ldl"),
        ("আমার এলডিএল কত?", "ldl"),
    ],
)
def test_biomarker_questions_in_indic_languages_are_personal_lookups(message, topic):
    plan = _route(message)
    assert plan.topic == topic, (message, plan.intent, plan.topic)
    assert plan.needs_personal_data, (message, plan.intent)
    assert plan.intent.value != "broad_health_summary"


@pytest.mark.parametrize(
    "message",
    ["LDL क्या होता है?", "एलडीएल क्या होता है?", "मुझे बुखार है", "What is vitamin D?", "Is vitamin D low?"],
)
def test_general_questions_stay_general(message):
    # "what is X" in any language, unrelated sentences, and English without "my" are unchanged.
    assert not _route(message).needs_personal_data, message


def test_rewrites_only_known_biomarkers():
    assert canonicalize_biomarker_terms("मेरा एलडीएल क्या है?") == "मेरा LDL क्या है?"
    assert canonicalize_biomarker_terms("विटामिन डी") == "Vitamin D"
    # Letter-name spellings that are not a biomarker, and ordinary words, are left alone.
    assert canonicalize_biomarker_terms("एबी पॉजिटिव") == "एबी पॉजिटिव"
    assert canonicalize_biomarker_terms("मुझे एक सवाल पूछना है") == "मुझे एक सवाल पूछना है"
    assert canonicalize_biomarker_terms("What is my LDL?") == "What is my LDL?"


def test_english_normalization_is_untouched():
    for message in ["What is my LDL?", "Is vitamin D low?", "And HDL?", "What about HDL?", "Compare my HbA1c with my previous report"]:
        assert normalize_for_intent(message) == message


def _conversation(turns):
    cid, answers = None, []
    for message in turns:
        body = client.post("/api/v1/chat", headers=H, json={"message": message, "conversation_id": cid}).json()
        cid = body["conversation_id"]
        answers.append(body)
    return answers


def test_spelled_ldl_answers_with_the_users_value():
    body = _conversation(["मेरा एलडीएल क्या है?"])[0]
    assert body["meta"]["intent"] == "latest_result"
    assert "138" in body["answer"]  # demo user's latest LDL


@pytest.mark.parametrize(
    "turns, expected",
    [
        (["मेरा एलडीएल क्या है?", "और HDL का क्या?"], "41"),
        (["मेरा LDL क्या है?", "एचडीएल के बारे में?"], "41"),
        (["What is my LDL?", "विटामिन डी का क्या?"], "12.6"),
        (["माझा LDL किती आहे?", "आणि HDL चं काय?"], "41"),
        (["আমার LDL কত?", "আর HDL এর কী?"], "41"),
    ],
)
def test_mixed_language_follow_ups_look_up_the_new_marker(turns, expected):
    follow_up = _conversation(turns)[-1]
    assert follow_up["meta"]["intent"] == "latest_result"
    assert expected in follow_up["answer"]


def test_change_since_previous_report_in_hindi_is_a_trend():
    follow_up = _conversation(["मेरा LDL क्या है?", "पिछली रिपोर्ट से बदला क्या?"])[-1]
    assert follow_up["meta"]["intent"] == "trend"
    assert "142" in follow_up["answer"]
