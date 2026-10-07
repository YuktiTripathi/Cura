"""User-facing copy. Keep technical details out of these strings.

The constants are the English source; the functions read the message catalog.
"""

from app.i18n.catalog import t

GENERAL_KNOWLEDGE_UNAVAILABLE = (
    "I can't access the general medical knowledge service right now. Please try again shortly."
)

PERSONAL_DATA_UNAVAILABLE = (
    "I can't access your personal SuperShyft health data right now, "
    "so I don't want to guess at your result. Please try again shortly."
)

GREETING_LOADING = "Hi 👋"
GREETING_FALLBACK = "Hi there 👋"

CASUAL_HELP = (
    "Hello. I can help with your blood report values, Bio-AI scores, "
    "general health questions, and nutrition or lifestyle guidance. What would you like to know?"
)


def casual_reply(_language=None) -> str:
    return t("casual_help", _language)


DOCUMENT_UNREAD = "I've received the document, but it is still being processed."
DOCUMENT_FAILED = "I couldn't read this document."
DOCUMENT_OCR = (
    "The document was uploaded, but its text could not be extracted because OCR is not configured."
)
DOCUMENT_NO_MATCH = "I couldn't find that information in the uploaded document."


def document_unread(_language=None) -> str:
    return t("document_unread", _language)


def document_failed(_language=None) -> str:
    return t("document_failed", _language)


def document_ocr_unavailable(_language=None) -> str:
    return t("document_ocr", _language)


def document_no_match(_language=None) -> str:
    return t("document_no_match", _language)


PERSONAL_DATA_NOT_FOUND = (
    "I couldn't find that result in your available health records, "
    "so I will not invent a value."
)

DOCUMENT_EXTRACTION_UNAVAILABLE = (
    "I couldn't extract structured data from that uploaded document, "
    "so I will not invent a personal health value from it."
)


def personal_data_not_found(_language=None) -> str:
    return t("personal_data_not_found", _language)


def document_extraction_unavailable(_language=None) -> str:
    return t("document_extraction_unavailable", _language)


def personal_data_unavailable(_language=None) -> str:
    return t("personal_data_unavailable", _language)


def general_knowledge_unavailable(_language=None) -> str:
    return t("general_knowledge_unavailable", _language)


def greeting_for_first_name(first_name: str | None, _language=None) -> str:
    name = (first_name or "").strip()
    if not name:
        return t("greeting_fallback", _language)
    return t("greeting_named", _language, name=name)
