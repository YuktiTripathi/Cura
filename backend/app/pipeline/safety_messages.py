"""Static safety replies in Cura's six languages plus romanized Hinglish.

DRAFT translations: every string must be reviewed by a native speaking clinician before
the pilot (docs/clinical/red_flag_taxonomy.md). Phone numbers come from settings so the
clinical team can confirm them without a code change.
"""

from __future__ import annotations

import re

from app.core.config import settings

SUPPORTED_SAFETY_LANGUAGES = ("en", "hi", "hinglish", "mr", "pa", "gu", "bn")

_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_GURMUKHI = re.compile(r"[਀-੿]")
_GUJARATI = re.compile(r"[઀-૿]")
_BENGALI = re.compile(r"[ঀ-৿]")
_MARATHI_MARKERS = re.compile(r"(आहे|नाही|मला|खूप|माझ|करू|झाल|येत|आणि|काय|होत\s*आहे)")
_HINGLISH_TOKENS = (
    "mein", "mujhe", "nahi", "nahin", "dawai", "dawa", "saans", "jeena", "bahut", "dard",
    "seene", "kya", "hai", "kar", "bukhar", "goli", "chahta", "chahti", "raha", "rahi",
)


def detect_safety_language(text: str) -> str:
    value = text or ""
    if _GURMUKHI.search(value):
        return "pa"
    if _GUJARATI.search(value):
        return "gu"
    if _BENGALI.search(value):
        return "bn"
    if _DEVANAGARI.search(value):
        return "mr" if _MARATHI_MARKERS.search(value) else "hi"
    words = set(re.findall(r"[a-z]+", value.lower()))
    if len(words & set(_HINGLISH_TOKENS)) >= 1:
        return "hinglish"
    return "en"


_EMERGENCY = {
    "en": "This may be a medical emergency. Call {emergency} now or go to the nearest emergency department. "
    "If someone is with you, ask them to help. Cura cannot assess emergencies.",
    "hinglish": "Yeh medical emergency ho sakti hai. Abhi {emergency} par call karein ya sabse paas ke emergency "
    "hospital jaayein. Paas mein koi ho to unki madad lein. Cura emergency ki jaanch nahi kar sakta.",
    "hi": "यह मेडिकल इमरजेंसी हो सकती है। अभी {emergency} पर कॉल करें या नज़दीकी इमरजेंसी विभाग में जाएँ। "
    "कोई पास हो तो उनसे मदद लें। Cura इमरजेंसी का आकलन नहीं कर सकता।",
    "mr": "ही वैद्यकीय आणीबाणी असू शकते. आत्ताच {emergency} वर कॉल करा किंवा जवळच्या आपत्कालीन विभागात जा. "
    "जवळ कोणी असल्यास त्यांची मदत घ्या. Cura आणीबाणीचे मूल्यांकन करू शकत नाही.",
    "pa": "ਇਹ ਮੈਡੀਕਲ ਐਮਰਜੈਂਸੀ ਹੋ ਸਕਦੀ ਹੈ। ਹੁਣੇ {emergency} 'ਤੇ ਕਾਲ ਕਰੋ ਜਾਂ ਨੇੜਲੇ ਐਮਰਜੈਂਸੀ ਵਿਭਾਗ ਵਿੱਚ ਜਾਓ। "
    "ਜੇ ਕੋਈ ਨੇੜੇ ਹੈ ਤਾਂ ਉਨ੍ਹਾਂ ਦੀ ਮਦਦ ਲਓ। Cura ਐਮਰਜੈਂਸੀ ਦਾ ਮੁਲਾਂਕਣ ਨਹੀਂ ਕਰ ਸਕਦਾ।",
    "gu": "આ તબીબી કટોકટી હોઈ શકે છે. હમણાં જ {emergency} પર કૉલ કરો અથવા નજીકના ઇમરજન્સી વિભાગમાં જાઓ. "
    "નજીકમાં કોઈ હોય તો તેમની મદદ લો. Cura કટોકટીનું મૂલ્યાંકન કરી શકતું નથી.",
    "bn": "এটি একটি চিকিৎসা জরুরি অবস্থা হতে পারে। এখনই {emergency} নম্বরে ফোন করুন বা নিকটতম জরুরি বিভাগে যান। "
    "কাছে কেউ থাকলে তাঁর সাহায্য নিন। Cura জরুরি অবস্থার মূল্যায়ন করতে পারে না।",
}

_CRISIS = {
    "en": "I'm really sorry you're feeling this way. You don't have to go through this alone. "
    "Please call the Tele-MANAS mental health helpline at {crisis} (free, 24x7), or {emergency} if you are in "
    "immediate danger. If you can, reach out to someone you trust right now.",
    "hinglish": "Mujhe sach mein afsos hai ki aap aisa mehsoos kar rahe hain. Aap akele nahi hain. "
    "Kripya Tele-MANAS helpline {crisis} par call karein (muft, 24x7), ya turant khatre mein hon to {emergency} par. "
    "Ho sake to abhi kisi bharosemand vyakti se baat karein.",
    "hi": "मुझे सच में दुख है कि आप ऐसा महसूस कर रहे हैं। आप अकेले नहीं हैं। "
    "कृपया Tele-MANAS हेल्पलाइन {crisis} पर कॉल करें (मुफ़्त, 24x7), या तुरंत ख़तरे में हों तो {emergency} पर। "
    "हो सके तो अभी किसी भरोसेमंद व्यक्ति से बात करें।",
    "mr": "तुम्हाला असं वाटतंय याचं मला खरंच वाईट वाटतं. तुम्ही एकटे नाही. "
    "कृपया Tele-MANAS हेल्पलाइन {crisis} वर कॉल करा (मोफत, 24x7), किंवा तात्काळ धोका असल्यास {emergency} वर. "
    "शक्य असल्यास आत्ताच विश्वासू व्यक्तीशी बोला.",
    "pa": "ਮੈਨੂੰ ਸੱਚਮੁੱਚ ਅਫ਼ਸੋਸ ਹੈ ਕਿ ਤੁਸੀਂ ਇਸ ਤਰ੍ਹਾਂ ਮਹਿਸੂਸ ਕਰ ਰਹੇ ਹੋ। ਤੁਸੀਂ ਇਕੱਲੇ ਨਹੀਂ ਹੋ। "
    "ਕਿਰਪਾ ਕਰਕੇ Tele-MANAS ਹੈਲਪਲਾਈਨ {crisis} 'ਤੇ ਕਾਲ ਕਰੋ (ਮੁਫ਼ਤ, 24x7), ਜਾਂ ਤੁਰੰਤ ਖ਼ਤਰੇ ਵਿੱਚ ਹੋ ਤਾਂ {emergency} 'ਤੇ। "
    "ਹੋ ਸਕੇ ਤਾਂ ਹੁਣੇ ਕਿਸੇ ਭਰੋਸੇਮੰਦ ਵਿਅਕਤੀ ਨਾਲ ਗੱਲ ਕਰੋ।",
    "gu": "તમે આવું અનુભવો છો તેનું મને ખરેખર દુઃખ છે. તમે એકલા નથી. "
    "કૃપા કરીને Tele-MANAS હેલ્પલાઇન {crisis} પર કૉલ કરો (મફત, 24x7), અથવા તાત્કાલિક જોખમ હોય તો {emergency} પર. "
    "શક્ય હોય તો હમણાં જ કોઈ વિશ્વાસુ વ્યક્તિ સાથે વાત કરો.",
    "bn": "আপনি এমন অনুভব করছেন জেনে আমি সত্যিই দুঃখিত। আপনি একা নন। "
    "অনুগ্রহ করে Tele-MANAS হেল্পলাইন {crisis} নম্বরে ফোন করুন (বিনামূল্যে, ২৪x৭), বা তাৎক্ষণিক বিপদে থাকলে {emergency} নম্বরে। "
    "সম্ভব হলে এখনই বিশ্বস্ত কারও সঙ্গে কথা বলুন।",
}

_MEDICATION = {
    "en": "I can't advise on medication doses, or on starting, stopping, skipping, changing or combining medicine. "
    "Please check with the clinician or pharmacist who manages your medication before making any change. "
    "I'm happy to explain what a medicine is generally used for.",
    "hinglish": "Main dawai shuru, band, skip, badalne ya dose ke baare mein salah nahi de sakta. "
    "Koi bhi badlav karne se pehle apne doctor ya pharmacist se zaroor poochhein. "
    "Main bata sakta hoon ki koi dawai aam taur par kis liye hoti hai.",
    "hi": "मैं दवा शुरू करने, बंद करने, छोड़ने, बदलने, मिलाने या खुराक के बारे में सलाह नहीं दे सकता। "
    "कोई भी बदलाव करने से पहले अपने डॉक्टर या फार्मासिस्ट से ज़रूर पूछें। "
    "मैं बता सकता हूँ कि कोई दवा आम तौर पर किस लिए होती है।",
    "mr": "औषध सुरू करणे, बंद करणे, चुकवणे, बदलणे, एकत्र घेणे किंवा डोस याबद्दल मी सल्ला देऊ शकत नाही. "
    "कोणताही बदल करण्यापूर्वी तुमच्या डॉक्टर किंवा फार्मासिस्टला विचारा. "
    "एखादे औषध सामान्यतः कशासाठी वापरले जाते हे मी सांगू शकतो.",
    "pa": "ਮੈਂ ਦਵਾਈ ਸ਼ੁਰੂ ਕਰਨ, ਬੰਦ ਕਰਨ, ਛੱਡਣ, ਬਦਲਣ, ਮਿਲਾਉਣ ਜਾਂ ਖੁਰਾਕ ਬਾਰੇ ਸਲਾਹ ਨਹੀਂ ਦੇ ਸਕਦਾ। "
    "ਕੋਈ ਵੀ ਬਦਲਾਅ ਕਰਨ ਤੋਂ ਪਹਿਲਾਂ ਆਪਣੇ ਡਾਕਟਰ ਜਾਂ ਫਾਰਮਾਸਿਸਟ ਨੂੰ ਪੁੱਛੋ। "
    "ਮੈਂ ਦੱਸ ਸਕਦਾ ਹਾਂ ਕਿ ਕੋਈ ਦਵਾਈ ਆਮ ਤੌਰ 'ਤੇ ਕਿਸ ਲਈ ਹੁੰਦੀ ਹੈ।",
    "gu": "હું દવા શરૂ કરવા, બંધ કરવા, છોડવા, બદલવા, ભેગી લેવા કે ડોઝ વિશે સલાહ આપી શકતો નથી. "
    "કોઈ પણ ફેરફાર કરતા પહેલા તમારા ડૉક્ટર અથવા ફાર્માસિસ્ટને પૂછો. "
    "કોઈ દવા સામાન્ય રીતે શેના માટે વપરાય છે તે હું સમજાવી શકું છું.",
    "bn": "আমি ওষুধ শুরু, বন্ধ, বাদ দেওয়া, পরিবর্তন, একসঙ্গে খাওয়া বা ডোজ নিয়ে পরামর্শ দিতে পারি না। "
    "কোনো পরিবর্তনের আগে আপনার ডাক্তার বা ফার্মাসিস্টের সঙ্গে কথা বলুন। "
    "কোনো ওষুধ সাধারণত কীসের জন্য ব্যবহৃত হয় তা আমি বুঝিয়ে বলতে পারি।",
}

_SOON = {
    "en": "Some of what you describe should be checked by a doctor within the next day. "
    "If it gets worse, or you develop chest pain, breathing trouble or confusion, call {emergency}.",
    "hinglish": "Aapne jo bataya uski jaanch agle ek din mein doctor se karwa lein. "
    "Agar haalat bigde, ya seene mein dard, saans ki takleef ya confusion ho, to {emergency} par call karein.",
    "hi": "आपने जो बताया उसकी जाँच अगले एक दिन में डॉक्टर से करवा लें। "
    "अगर हालत बिगड़े, या सीने में दर्द, साँस की तकलीफ़ या भ्रम हो, तो {emergency} पर कॉल करें।",
    "mr": "तुम्ही सांगितलेल्या लक्षणांची पुढील एका दिवसात डॉक्टरांकडून तपासणी करून घ्या. "
    "त्रास वाढल्यास, किंवा छातीत दुखणे, श्वासाचा त्रास किंवा गोंधळ झाल्यास {emergency} वर कॉल करा.",
    "pa": "ਤੁਸੀਂ ਜੋ ਦੱਸਿਆ ਉਸਦੀ ਅਗਲੇ ਇੱਕ ਦਿਨ ਵਿੱਚ ਡਾਕਟਰ ਤੋਂ ਜਾਂਚ ਕਰਵਾਓ। "
    "ਜੇ ਹਾਲਤ ਵਿਗੜੇ, ਜਾਂ ਛਾਤੀ ਵਿੱਚ ਦਰਦ, ਸਾਹ ਦੀ ਤਕਲੀਫ਼ ਜਾਂ ਉਲਝਣ ਹੋਵੇ, ਤਾਂ {emergency} 'ਤੇ ਕਾਲ ਕਰੋ।",
    "gu": "તમે જે જણાવ્યું તેની આવતા એક દિવસમાં ડૉક્ટર પાસે તપાસ કરાવો. "
    "જો તકલીફ વધે, અથવા છાતીમાં દુખાવો, શ્વાસની તકલીફ કે ગૂંચવણ થાય, તો {emergency} પર કૉલ કરો.",
    "bn": "আপনি যা বলেছেন তা আগামী এক দিনের মধ্যে ডাক্তারকে দেখান। "
    "অবস্থা খারাপ হলে, বা বুকে ব্যথা, শ্বাসকষ্ট বা বিভ্রান্তি হলে {emergency} নম্বরে ফোন করুন।",
}


def _numbers() -> dict[str, str]:
    return {
        "emergency": (settings.emergency_number or "112").strip(),
        "crisis": (settings.crisis_helpline_number or "14416").strip(),
    }


def _pick(table: dict[str, str], language: str | None) -> str:
    return table.get(language or "en", table["en"]).format(**_numbers())


def emergency_message(language: str | None) -> str:
    return _pick(_EMERGENCY, language)


def crisis_message(language: str | None) -> str:
    return _pick(_CRISIS, language)


def medication_message(language: str | None) -> str:
    return _pick(_MEDICATION, language)


def see_doctor_soon_message(language: str | None) -> str:
    return _pick(_SOON, language)


def emergency_contacts() -> list[dict[str, str]]:
    """Numbers the web and Flutter clients render as call buttons."""
    numbers = _numbers()
    return [
        {"kind": "emergency", "label": "Emergency", "number": numbers["emergency"]},
        {"kind": "mental_health", "label": "Tele-MANAS", "number": numbers["crisis"]},
    ]
