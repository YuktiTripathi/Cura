from __future__ import annotations

from app.contracts.common import LanguageCode
from app.contracts.followup import FollowUpSuggestion

_TEMPLATES: dict[str, dict[LanguageCode, str]] = {
    "explanation": {
        LanguageCode.en: "What does my {topic} result mean?",
        LanguageCode.hi: "मेरे {topic} परिणाम का क्या मतलब है?",
        LanguageCode.mr: "माझ्या {topic} निकालाचा अर्थ काय आहे?",
        LanguageCode.pa: "ਮੇਰੇ {topic} ਨਤੀਜੇ ਦਾ ਕੀ ਅਰਥ ਹੈ?",
        LanguageCode.gu: "મારા {topic} પરિણામનો અર્થ શું છે?",
        LanguageCode.bn: "আমার {topic} ফলাফলের অর্থ কী?",
    },
    "historical_trend": {
        LanguageCode.en: "Would you like to see how your {topic} has changed over time?",
        LanguageCode.hi: "क्या आप देखना चाहेंगे कि आपके {topic} स्तर में समय के साथ क्या बदलाव आया है?",
        LanguageCode.mr: "तुमच्या {topic} पातळीत कालांतराने काय बदल झाला हे पाहायचे आहे का?",
        LanguageCode.pa: "ਕੀ ਤੁਸੀਂ ਦੇਖਣਾ ਚਾਹੋਗੇ ਕਿ ਤੁਹਾਡੇ {topic} ਪੱਧਰ ਵਿੱਚ ਸਮੇਂ ਦੇ ਨਾਲ ਕੀ ਬਦਲਾਅ ਆਇਆ ਹੈ?",
        LanguageCode.gu: "શું તમે જોવા માંગો છો કે તમારા {topic} સ્તરમાં સમય સાથે શું ફેરફાર થયો છે?",
        LanguageCode.bn: "আপনি কি দেখতে চান সময়ের সঙ্গে আপনার {topic}-এর মাত্রায় কী পরিবর্তন হয়েছে?",
    },
    "related_marker": {
        LanguageCode.en: "Would you like me to explain how your {topic} relates to another result in your report?",
        LanguageCode.hi: "क्या आप जानना चाहेंगे कि आपका {topic} रिपोर्ट के किसी अन्य परिणाम से कैसे जुड़ा है?",
        LanguageCode.mr: "तुमचा {topic} अहवालातील इतर निकालाशी कसा संबंधित आहे हे समजून घ्यायचे आहे का?",
        LanguageCode.pa: "ਕੀ ਤੁਸੀਂ ਸਮਝਣਾ ਚਾਹੋਗੇ ਕਿ ਤੁਹਾਡਾ {topic} ਰਿਪੋਰਟ ਦੇ ਕਿਸੇ ਹੋਰ ਨਤੀਜੇ ਨਾਲ ਕਿਵੇਂ ਜੁੜਦਾ ਹੈ?",
        LanguageCode.gu: "શું તમે જાણવા માંગો છો કે તમારું {topic} રિપોર્ટના અન્ય પરિણામ સાથે કેવી રીતે જોડાયેલું છે?",
        LanguageCode.bn: "আপনি কি জানতে চান আপনার {topic} রিপোর্টের অন্য ফলাফলের সঙ্গে কীভাবে সম্পর্কিত?",
    },
    "bio_ai_relationship": {
        LanguageCode.en: "Would you like me to explain how your {topic} relates to your Bio-AI assessment?",
        LanguageCode.hi: "क्या आप चाहेंगे कि मैं बताऊँ कि आपका {topic} आपके Bio-AI आकलन से कैसे जुड़ा है?",
        LanguageCode.mr: "तुमचा {topic} तुमच्या Bio-AI मूल्यांकनाशी कसा संबंधित आहे हे समजावून सांगू का?",
        LanguageCode.pa: "ਕੀ ਤੁਸੀਂ ਜਾਣਨਾ ਚਾਹੋਗੇ ਕਿ ਤੁਹਾਡਾ {topic} ਤੁਹਾਡੇ Bio-AI ਮੁਲਾਂਕਣ ਨਾਲ ਕਿਵੇਂ ਜੁੜਦਾ ਹੈ?",
        LanguageCode.gu: "શું તમે જાણવા માંગો છો કે તમારું {topic} તમારા Bio-AI મૂલ્યાંકન સાથે કેવી રીતે સંકળાયેલું છે?",
        LanguageCode.bn: "আপনি কি জানতে চান আপনার {topic} আপনার Bio-AI মূল্যায়নের সঙ্গে কীভাবে সম্পর্কিত?",
    },
    "nutrition": {
        LanguageCode.en: "Would you like to look at your recorded nutrition preferences alongside your {topic}?",
        LanguageCode.hi: "क्या आप अपने दर्ज पोषण विकल्पों को अपने {topic} के साथ देखना चाहेंगे?",
        LanguageCode.mr: "तुमच्या नोंदवलेल्या पोषण पसंती {topic} सोबत पाहू का?",
        LanguageCode.pa: "ਕੀ ਤੁਸੀਂ ਆਪਣੀਆਂ ਰਿਕਾਰਡ ਕੀਤੀਆਂ ਪੋਸ਼ਣ ਪਸੰਦਾਂ {topic} ਨਾਲ ਦੇਖਣਾ ਚਾਹੋਗੇ?",
        LanguageCode.gu: "શું તમે તમારી નોંધાયેલ પોષણ પસંદગીઓ {topic} સાથે જોવા માંગો છો?",
        LanguageCode.bn: "আপনি কি আপনার রেকর্ড করা পুষ্টি পছন্দ {topic}-এর সঙ্গে দেখতে চান?",
    },
    "lifestyle": {
        LanguageCode.en: "Would you like to explore lifestyle factors that may be relevant to this result?",
        LanguageCode.hi: "क्या आप इस परिणाम से जुड़े जीवनशैली कारकों को समझना चाहेंगे?",
        LanguageCode.mr: "या निकालाशी संबंधित जीवनशैली घटक पाहू का?",
        LanguageCode.pa: "ਕੀ ਤੁਸੀਂ ਇਸ ਨਤੀਜੇ ਨਾਲ ਸੰਬੰਧਿਤ ਜੀਵਨਸ਼ੈਲੀ ਕਾਰਕਾਂ ਨੂੰ ਵੇਖਣਾ ਚਾਹੋਗੇ?",
        LanguageCode.gu: "શું તમે આ પરિણામ સાથે સંબંધિત જીવનશૈલી પરિબળો જોવા માંગો છો?",
        LanguageCode.bn: "আপনি কি এই ফলাফলের সঙ্গে সম্পর্কিত জীবনধারার বিষয়গুলো দেখতে চান?",
    },
    "general_education": {
        LanguageCode.en: "What are common reasons {topic} can be low or high?",
        LanguageCode.hi: "{topic} कम या अधिक होने के सामान्य कारण क्या हैं?",
        LanguageCode.mr: "{topic} कमी किंवा जास्त होण्याची सामान्य कारणे काय आहेत?",
        LanguageCode.pa: "{topic} ਘੱਟ ਜਾਂ ਵੱਧ ਹੋਣ ਦੇ ਆਮ ਕਾਰਨ ਕੀ ਹਨ?",
        LanguageCode.gu: "{topic} ઓછું કે વધુ થવાના સામાન્ય કારણો શું છે?",
        LanguageCode.bn: "{topic} কম বা বেশি হওয়ার সাধারণ কারণ কী?",
    },
    "g_explanation": {
        LanguageCode.en: "What does {topic} do in the body?",
        LanguageCode.hi: "शरीर में {topic} क्या करता है?",
        LanguageCode.mr: "शरीरात {topic} काय करतो?",
        LanguageCode.pa: "ਸਰੀਰ ਵਿੱਚ {topic} ਕੀ ਕਰਦਾ ਹੈ?",
        LanguageCode.gu: "શરીરમાં {topic} શું કરે છે?",
        LanguageCode.bn: "শরীরে {topic} কী করে?",
    },
    "general_foods": {
        LanguageCode.en: "What foods are commonly discussed in relation to {topic}?",
        LanguageCode.hi: "{topic} के संदर्भ में आमतौर पर किन खाद्य पदार्थों की चर्चा होती है?",
        LanguageCode.mr: "{topic} संबंधित कोणत्या पदार्थांची चर्चा होते?",
        LanguageCode.pa: "{topic} ਨਾਲ ਆਮ ਤੌਰ ਤੇ ਕਿਹੜੇ ਭੋਜਨਾਂ ਦੀ ਚਰਚਾ ਹੁੰਦੀ ਹੈ?",
        LanguageCode.gu: "{topic} સંબંધિત કયા ખોરાકની વાત થાય છે?",
        LanguageCode.bn: "{topic} সম্পর্কে কোন খাবারের কথা সাধারণত বলা হয়?",
    },
    "general_lifestyle": {
        LanguageCode.en: "How can lifestyle affect {topic}?",
        LanguageCode.hi: "जीवनशैली {topic} को कैसे प्रभावित कर सकती है?",
        LanguageCode.mr: "जीवनशैली {topic} वर कसा परिणाम करू शकते?",
        LanguageCode.pa: "ਜੀਵਨਸ਼ੈਲੀ {topic} ਨੂੰ ਕਿਵੇਂ ਪ੍ਰਭਾਵਿਤ ਕਰ ਸਕਦੀ ਹੈ?",
        LanguageCode.gu: "જીવનશૈલી {topic}ને કેવી રીતે અસર કરી શકે?",
        LanguageCode.bn: "জীবনধারা {topic}-কে কীভাবে প্রভাবিত করতে পারে?",
    },
    "clarification": {
        LanguageCode.en: "Would you like me to compare those Bio-AI reports?",
        LanguageCode.hi: "क्या आप चाहेंगे कि मैं उन Bio-AI रिपोर्टों की तुलना करूँ?",
        LanguageCode.mr: "त्या Bio-AI अहवालांची तुलना करू का?",
        LanguageCode.pa: "ਕੀ ਤੁਸੀਂ ਚਾਹੋਗੇ ਕਿ ਮੈਂ ਉਨ੍ਹਾਂ Bio-AI ਰਿਪੋਰਟਾਂ ਦੀ ਤੁਲਨਾ ਕਰਾਂ?",
        LanguageCode.gu: "શું તમે ઈચ્છો છો કે હું તે Bio-AI રિપોર્ટની સરખામણી કરું?",
        LanguageCode.bn: "আপনি কি চান আমি সেই Bio-AI রিপোর্টগুলোর তুলনা করি?",
    },
    "next_action": {
        LanguageCode.en: "If you'd like, I can also explain what your latest {topic} result shows.",
        LanguageCode.hi: "अगर आप चाहें, तो मैं आपके ताज़ा {topic} परिणाम के बारे में भी बता सकता हूँ।",
        LanguageCode.mr: "हवं असल्यास मी तुमच्या नवीनतम {topic} निकालाबद्दलही सांगू शकतो.",
        LanguageCode.pa: "ਜੇ ਤੁਸੀਂ ਚਾਹੋ, ਮੈਂ ਤੁਹਾਡੇ ਤਾਜ਼ਾ {topic} ਨਤੀਜੇ ਬਾਰੇ ਵੀ ਦੱਸ ਸਕਦਾ ਹਾਂ।",
        LanguageCode.gu: "જો તમે ઈચ્છો તો હું તમારા નવીનતમ {topic} પરિણામ વિશે પણ કહી શકું.",
        LanguageCode.bn: "চাইলে আমি আপনার সর্বশেষ {topic} ফলাফল নিয়েও বলতে পারি।",
    },
    "comparison": {
        LanguageCode.en: "Would you like to compare this with your other Bio-AI report?",
        LanguageCode.hi: "क्या आप इसकी तुलना अपनी दूसरी Bio-AI रिपोर्ट से करना चाहेंगे?",
        LanguageCode.mr: "याची तुलना तुमच्या दुसऱ्या Bio-AI अहवालाशी करू का?",
        LanguageCode.pa: "ਕੀ ਤੁਸੀਂ ਇਸਦੀ ਤੁਲਨਾ ਆਪਣੀ ਹੋਰ Bio-AI ਰਿਪੋਰਟ ਨਾਲ ਕਰਨਾ ਚਾਹੋਗੇ?",
        LanguageCode.gu: "શું તમે આની સરખામણી તમારા અન્ય Bio-AI રિપોર્ટ સાથે કરવા માંગો છો?",
        LanguageCode.bn: "আপনি কি এটি আপনার অন্য Bio-AI রিপোর্টের সঙ্গে তুলনা করতে চান?",
    },
    "cross_explain": {
        LanguageCode.en: "Would you like me to explain what {topic} measures?",
        LanguageCode.hi: "क्या आप चाहेंगे कि मैं बताऊँ {topic} क्या मापता है?",
        LanguageCode.mr: "{topic} काय मोजतो हे समजावून सांगू का?",
        LanguageCode.pa: "ਕੀ ਤੁਸੀਂ ਚਾਹੋਗੇ ਕਿ ਮੈਂ ਦੱਸਾਂ {topic} ਕੀ ਮਾਪਦਾ ਹੈ?",
        LanguageCode.gu: "શું તમે ઈચ્છો છો કે હું સમજાવું {topic} શું માપે છે?",
        LanguageCode.bn: "আপনি কি চান আমি বলি {topic} কী মাপে?",
    },
    "cross_newer": {
        LanguageCode.en: "Which report is newer?",
        LanguageCode.hi: "कौन सी रिपोर्ट नई है?",
        LanguageCode.mr: "कोणता अहवाल नवीन आहे?",
        LanguageCode.pa: "ਕਿਹੜੀ ਰਿਪੋਰਟ ਨਵੀਂ ਹੈ?",
        LanguageCode.gu: "કયો રિપોર્ટ નવો છે?",
        LanguageCode.bn: "কোন রিপোর্ট নতুন?",
    },
}


def localize_followups(
    items: list[FollowUpSuggestion],
    language: LanguageCode,
    topic_name: str | None,
) -> list[FollowUpSuggestion]:
    topic = topic_name or "this result"
    lang = LanguageCode.en if language == LanguageCode.auto else language
    out: list[FollowUpSuggestion] = []
    for item in items:
        cat = item.category
        if not item.requires_personal_context and cat == "explanation":
            cat = "g_explanation"
        template = _TEMPLATES.get(cat, {}).get(lang) or _TEMPLATES.get(cat, {}).get(LanguageCode.en)
        text = template.format(topic=topic) if template else item.text
        scope = "general" if not item.requires_personal_context else "personal"
        out.append(item.model_copy(update={"text": text, "knowledge_scope": scope}))
    return out
