"""Readiness plan 3.7: approved glossary."""

from __future__ import annotations

import re

from app.i18n import glossary
from app.pipeline.translation import _prompt


def test_every_term_has_hindi_hinglish_and_plain_english():
    for key, entry in glossary.terms().items():
        assert entry.get("hi") and entry.get("hinglish") and entry.get("plain_en"), key


def test_local_names_contain_no_standalone_numbers():
    # The translation step rejects output whose numbers differ from the English answer.
    # Digits inside a marker code (HbA1c, B12) are fine: the English answer carries the same code.
    for key, entry in glossary.terms().items():
        for lang in ("hi", "hinglish"):
            without_codes = re.sub(r"\b[A-Za-z]+\d+[A-Za-z0-9]*\b", "", entry[lang])
            assert not re.search(r"\d", without_codes), (key, lang)


def test_terms_are_found_by_name_and_alias():
    found = glossary.terms_in("Your hemoglobin and A1C, plus good cholesterol")
    assert {"haemoglobin", "hba1c", "hdl"} <= set(found)


def test_translation_prompt_carries_approved_names():
    prompt = _prompt("hi", "Your ferritin is low.")
    assert "ferritin -> " + glossary.local_name("ferritin", "hi") in prompt
