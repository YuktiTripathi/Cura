"""Message catalog (readiness plan 3.4)."""

from __future__ import annotations

import re

import pytest

from app.core import copy
from app.i18n import catalog
from app.pipeline import translation

PLACEHOLDER = re.compile(r"\{(\w+)\}")


@pytest.mark.parametrize("language", [lang for lang in catalog.languages() if lang != "en"])
def test_every_language_has_the_english_keys_and_placeholders(language):
    english, other = catalog.messages("en"), catalog.messages(language)
    assert set(other) == set(english), set(english) ^ set(other)
    for key, text in english.items():
        assert set(PLACEHOLDER.findall(other[key])) == set(PLACEHOLDER.findall(text)), key


@pytest.mark.parametrize(
    "constant, key",
    [
        ("CASUAL_HELP", "casual_help"),
        ("DOCUMENT_UNREAD", "document_unread"),
        ("DOCUMENT_FAILED", "document_failed"),
        ("DOCUMENT_OCR", "document_ocr"),
        ("DOCUMENT_NO_MATCH", "document_no_match"),
        ("PERSONAL_DATA_UNAVAILABLE", "personal_data_unavailable"),
        ("PERSONAL_DATA_NOT_FOUND", "personal_data_not_found"),
        ("GENERAL_KNOWLEDGE_UNAVAILABLE", "general_knowledge_unavailable"),
        ("DOCUMENT_EXTRACTION_UNAVAILABLE", "document_extraction_unavailable"),
        ("GREETING_FALLBACK", "greeting_fallback"),
    ],
)
def test_english_catalog_matches_the_source_constants(constant, key):
    assert getattr(copy, constant) == catalog.t(key)


def test_unknown_language_and_enum_values_fall_back_to_english():
    assert catalog.t("document_failed", "xx") == copy.DOCUMENT_FAILED
    assert copy.document_failed(object()) == copy.DOCUMENT_FAILED


def test_catalog_text_is_localized_without_a_model_call(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "enable_llm", False)
    text, lang, flags = translation.translate_answer(copy.DOCUMENT_FAILED, "hi")
    assert lang == "hi" and flags == [] and text == catalog.t("document_failed", "hi")
