"""User-facing copy. Keep technical details out of these strings."""

from app.contracts.common import LanguageCode

GENERAL_KNOWLEDGE_UNAVAILABLE = (
    "I can't access the general medical knowledge service right now. Please try again shortly."
)

_GENERAL_UNAVAILABLE = {
    LanguageCode.en: GENERAL_KNOWLEDGE_UNAVAILABLE,
    LanguageCode.hi: "मैं अभी सामान्य स्वास्थ्य जानकारी सेवा तक पहुँच नहीं पा रहा हूँ। कृपया थोड़ी देर बाद फिर कोशिश करें।",
    LanguageCode.mr: "मी सध्या सामान्य आरोग्य माहिती सेवा वापरू शकत नाही. कृपया थोड्या वेळाने पुन्हा प्रयत्न करा.",
    LanguageCode.pa: "ਮੈਂ ਇਸ ਵੇਲੇ ਆਮ ਸਿਹਤ ਜਾਣਕਾਰੀ ਸੇਵਾ ਤੱਕ ਨਹੀਂ ਪਹੁੰਚ ਸਕਦਾ। ਕਿਰਪਾ ਕਰਕੇ ਥੋੜ੍ਹੀ ਦੇਰ ਬਾਅਦ ਕੋਸ਼ਿਸ਼ ਕਰੋ।",
    LanguageCode.gu: "હું અત્યારે સામાન્ય આરોગ્ય જ્ઞાન સેવા મેળવી શકતો નથી. કૃપા કરીને થોડી વાર પછી ફરી પ્રયાસ કરો.",
    LanguageCode.bn: "আমি এখন সাধারণ স্বাস্থ্যজ্ঞান সেবায় পৌঁছাতে পারছি না। অনুগ্রহ করে কিছুক্ষণ পর আবার চেষ্টা করুন।",
}

PERSONAL_DATA_UNAVAILABLE = (
    "I can't access your personal SuperShyft health data right now, "
    "so I don't want to guess at your result. Please try again shortly."
)

_UNAVAILABLE = {
    LanguageCode.en: PERSONAL_DATA_UNAVAILABLE,
    LanguageCode.hi: (
        "मैं अभी आपकी व्यक्तिगत SuperShyft स्वास्थ्य जानकारी एक्सेस नहीं कर पा रहा हूँ, "
        "इसलिए मैं आपके परिणाम का अनुमान नहीं लगाऊँगा। कृपया थोड़ी देर बाद फिर कोशिश करें।"
    ),
    LanguageCode.mr: (
        "मी सध्या तुमची वैयक्तिक SuperShyft आरोग्य माहिती घेऊ शकत नाही, "
        "म्हणून मी तुमच्या निकालाचा अंदाज लावणार नाही. कृपया थोड्या वेळाने पुन्हा प्रयत्न करा."
    ),
    LanguageCode.pa: (
        "ਮੈਂ ਇਸ ਵੇਲੇ ਤੁਹਾਡੀ ਨਿੱਜੀ SuperShyft ਸਿਹਤ ਜਾਣਕਾਰੀ ਤੱਕ ਨਹੀਂ ਪਹੁੰਚ ਸਕਦਾ, "
        "ਇਸ ਲਈ ਮੈਂ ਤੁਹਾਡੇ ਨਤੀਜੇ ਦਾ ਅੰਦਾਜ਼ਾ ਨਹੀਂ ਲਗਾਵਾਂਗਾ। ਕਿਰਪਾ ਕਰਕੇ ਥੋੜ੍ਹੀ ਦੇਰ ਬਾਅਦ ਕੋਸ਼ਿਸ਼ ਕਰੋ।"
    ),
    LanguageCode.gu: (
        "હું અત્યારે તમારી વ્યક્તિગત SuperShyft આરોગ્ય માહિતી મેળવી શકતો નથી, "
        "તેથી હું તમારા પરિણામનો અંદાજ નહીં લગાડું. કૃપા કરીને થોડી વાર પછી ફરી પ્રયાસ કરો."
    ),
    LanguageCode.bn: (
        "আমি এখন আপনার ব্যক্তিগত SuperShyft স্বাস্থ্য তথ্যে পৌঁছাতে পারছি না, "
        "তাই আমি আপনার ফলাফল অনুমান করব না। অনুগ্রহ করে কিছুক্ষণ পর আবার চেষ্টা করুন।"
    ),
}

GREETING_LOADING = "Hi 👋"
GREETING_FALLBACK = "Hi there 👋"

_GREET = {
    LanguageCode.en: "Hi {name} 👋",
    LanguageCode.hi: "नमस्ते, {name} 👋",
    LanguageCode.mr: "नमस्कार, {name} 👋",
    LanguageCode.pa: "ਸਤ ਸ੍ਰੀ ਅਕਾਲ, {name} 👋",
    LanguageCode.gu: "નમસ્તે, {name} 👋",
    LanguageCode.bn: "নমস্কার, {name} 👋",
}

_GREET_FALLBACK = {
    LanguageCode.en: "Hi there 👋",
    LanguageCode.hi: "नमस्ते 👋",
    LanguageCode.mr: "नमस्कार 👋",
    LanguageCode.pa: "ਸਤ ਸ੍ਰੀ ਅਕਾਲ 👋",
    LanguageCode.gu: "નમસ્તે 👋",
    LanguageCode.bn: "নমস্কার 👋",
}


CASUAL_HELP = (
    "Hello. I can help with your blood report values, Bio-AI scores, "
    "general health questions, and nutrition or lifestyle guidance. What would you like to know?"
)


def casual_reply(language: LanguageCode | str | None = None) -> str:
    return CASUAL_HELP


DOCUMENT_UNREAD = (
    "I've received the document, but it is still being processed."
)
DOCUMENT_FAILED = "I couldn't read this document."
DOCUMENT_OCR = (
    "The document was uploaded, but its text could not be extracted because OCR is not configured."
)
DOCUMENT_NO_MATCH = "I couldn't find that information in the uploaded document."

_DOCUMENT_UNREAD = {
    LanguageCode.en: DOCUMENT_UNREAD,
    LanguageCode.hi: "दस्तावेज़ मिल गया है, लेकिन अभी प्रोसेस हो रहा है।",
    LanguageCode.mr: "दस्तऐवज मिळाला आहे, पण अजून प्रक्रिया सुरू आहे.",
    LanguageCode.pa: "ਦਸਤਾਵੇਜ਼ ਮਿਲ ਗਿਆ ਹੈ, ਪਰ ਹਾਲੇ ਪ੍ਰੋਸੈਸ ਹੋ ਰਿਹਾ ਹੈ।",
    LanguageCode.gu: "દસ્તાવેજ મળી ગયો છે, પણ હજુ પ્રક્રિયા થઈ રહી છે.",
    LanguageCode.bn: "নথি পেয়েছি, কিন্তু এখনও প্রক্রিয়াধীন।",
}


def document_unread(language: LanguageCode | str | None = None) -> str:
    return _pick(language, _DOCUMENT_UNREAD, DOCUMENT_UNREAD)


def document_failed(language: LanguageCode | str | None = None) -> str:
    return DOCUMENT_FAILED


def document_ocr_unavailable(language: LanguageCode | str | None = None) -> str:
    return DOCUMENT_OCR


def document_no_match(language: LanguageCode | str | None = None) -> str:
    return DOCUMENT_NO_MATCH


def _pick(language, table, default):
    try:
        code = language if isinstance(language, LanguageCode) else LanguageCode(language or "en")
    except ValueError:
        code = LanguageCode.en
    if code == LanguageCode.auto:
        code = LanguageCode.en
    return table.get(code, default)


PERSONAL_DATA_NOT_FOUND = (
    "I couldn't find that result in your available health records, "
    "so I will not invent a value."
)

DOCUMENT_EXTRACTION_UNAVAILABLE = (
    "I couldn't extract structured data from that uploaded document, "
    "so I will not invent a personal health value from it."
)


def personal_data_not_found(language: LanguageCode | str | None = None) -> str:
    return PERSONAL_DATA_NOT_FOUND


def document_extraction_unavailable(language: LanguageCode | str | None = None) -> str:
    return DOCUMENT_EXTRACTION_UNAVAILABLE


def personal_data_unavailable(language: LanguageCode | str | None = None) -> str:
    code = language if isinstance(language, LanguageCode) else LanguageCode.en
    if isinstance(language, str):
        try:
            code = LanguageCode(language)
        except ValueError:
            code = LanguageCode.en
    if code == LanguageCode.auto:
        code = LanguageCode.en
    return _UNAVAILABLE.get(code, PERSONAL_DATA_UNAVAILABLE)


def general_knowledge_unavailable(language: LanguageCode | str | None = None) -> str:
    return _pick(language, _GENERAL_UNAVAILABLE, GENERAL_KNOWLEDGE_UNAVAILABLE)


def greeting_for_first_name(first_name: str | None, language: LanguageCode | str | None = None) -> str:
    try:
        code = language if isinstance(language, LanguageCode) else LanguageCode(language or "en")
    except ValueError:
        code = LanguageCode.en
    if code == LanguageCode.auto:
        code = LanguageCode.en
    name = (first_name or "").strip()
    if not name:
        return _GREET_FALLBACK.get(code, GREETING_FALLBACK)
    return _GREET.get(code, _GREET[LanguageCode.en]).format(name=name)
