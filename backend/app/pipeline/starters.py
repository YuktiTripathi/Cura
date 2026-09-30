from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from app.auth.models import AuthenticatedPrincipal
from app.contracts.common import IntentType, KnowledgeScope, LanguageCode, MarkerFlag
from app.contracts.query import QueryPlan
from app.contracts.starters import StarterQuestion, StarterQuestionSet
from app.core.errors import ProviderUnavailableError
from app.pipeline.intent import NAMES
from app.providers.registry import ProviderRegistry

GENERAL_POOL: list[tuple[str, str]] = [
    ("vitamin_d", "What is Vitamin D and why is it important?"),
    ("hba1c", "What does HbA1c measure?"),
    ("ldl", "What causes high LDL?"),
    ("hdl", "What is the difference between HDL and LDL?"),
    ("blood_pressure", "What causes high blood pressure?"),
    ("thyroid", "How does the thyroid work?"),
    ("insulin", "What is insulin resistance?"),
    ("b12", "Why is Vitamin B12 important?"),
    ("crp", "What does CRP measure?"),
    ("liver", "What is fatty liver?"),
    ("kidney", "What do kidney function tests look at?"),
    ("heart", "What is heart health in general terms?"),
    ("metabolic", "What is metabolic age?"),
]

_GENERAL_I18N: dict[str, dict[LanguageCode, str]] = {
    "vitamin_d": {
        LanguageCode.en: "What is Vitamin D and why is it important?",
        LanguageCode.hi: "Vitamin D क्या है और यह क्यों महत्वपूर्ण है?",
        LanguageCode.mr: "Vitamin D म्हणजे काय आणि ते का महत्त्वाचे आहे?",
        LanguageCode.pa: "Vitamin D ਕੀ ਹੈ ਅਤੇ ਇਹ ਕਿਉਂ ਮਹੱਤਵਪੂਰਨ ਹੈ?",
        LanguageCode.gu: "Vitamin D શું છે અને તે શા માટે મહત્વનું છે?",
        LanguageCode.bn: "Vitamin D কী এবং এটি কেন গুরুত্বপূর্ণ?",
    },
    "hba1c": {
        LanguageCode.en: "What does HbA1c measure?",
        LanguageCode.hi: "HbA1c क्या मापता है?",
        LanguageCode.mr: "HbA1c काय मोजतो?",
        LanguageCode.pa: "HbA1c ਕੀ ਮਾਪਦਾ ਹੈ?",
        LanguageCode.gu: "HbA1c શું માપે છે?",
        LanguageCode.bn: "HbA1c কী মাপে?",
    },
    "ldl": {
        LanguageCode.en: "What causes high LDL?",
        LanguageCode.hi: "LDL अधिक होने के सामान्य कारण क्या हैं?",
        LanguageCode.mr: "LDL जास्त होण्याची कारणे काय आहेत?",
        LanguageCode.pa: "LDL ਵੱਧ ਹੋਣ ਦੇ ਕਾਰਨ ਕੀ ਹਨ?",
        LanguageCode.gu: "LDL વધુ થવાનાં કારણો શું છે?",
        LanguageCode.bn: "LDL বেশি হওয়ার কারণ কী?",
    },
    "hdl": {
        LanguageCode.en: "What is the difference between HDL and LDL?",
        LanguageCode.hi: "HDL और LDL में क्या अंतर है?",
        LanguageCode.mr: "HDL आणि LDL यात काय फरक आहे?",
        LanguageCode.pa: "HDL ਅਤੇ LDL ਵਿੱਚ ਕੀ ਫਰਕ ਹੈ?",
        LanguageCode.gu: "HDL અને LDL વચ્ચે શું તફાવત છે?",
        LanguageCode.bn: "HDL ও LDL-এর মধ্যে পার্থক্য কী?",
    },
    "blood_pressure": {
        LanguageCode.en: "What causes high blood pressure?",
        LanguageCode.hi: "उच्च रक्तचाप के सामान्य कारण क्या हैं?",
        LanguageCode.mr: "उच्च रक्तदाबाची कारणे काय आहेत?",
        LanguageCode.pa: "ਉੱਚ ਬਲੱਡ ਪ੍ਰੈਸ਼ਰ ਦੇ ਕਾਰਨ ਕੀ ਹਨ?",
        LanguageCode.gu: "ઉચ્ચ બ્લડ પ્રેશરનાં કારણો શું છે?",
        LanguageCode.bn: "উচ্চ রক্তচাপের কারণ কী?",
    },
    "thyroid": {
        LanguageCode.en: "How does the thyroid work?",
        LanguageCode.hi: "थायरॉइड कैसे काम करता है?",
        LanguageCode.mr: "थायरॉइड कसे काम करते?",
        LanguageCode.pa: "ਥਾਇਰਾਇਡ ਕਿਵੇਂ ਕੰਮ ਕਰਦਾ ਹੈ?",
        LanguageCode.gu: "થાઇરોઇડ કેવી રીતે કામ કરે છે?",
        LanguageCode.bn: "থাইরয়েড কীভাবে কাজ করে?",
    },
    "insulin": {
        LanguageCode.en: "What is insulin resistance?",
        LanguageCode.hi: "इंसुलिन प्रतिरोध क्या है?",
        LanguageCode.mr: "इन्सुलिन रेझिस्टन्स म्हणजे काय?",
        LanguageCode.pa: "ਇਨਸੂਲਿਨ ਰੋਧਕਤਾ ਕੀ ਹੈ?",
        LanguageCode.gu: "ઇન્સ્યુલિન રેઝિસ્ટન્સ શું છે?",
        LanguageCode.bn: "ইনসুলিন রেজিস্ট্যান্স কী?",
    },
    "b12": {
        LanguageCode.en: "Why is Vitamin B12 important?",
        LanguageCode.hi: "Vitamin B12 क्यों महत्वपूर्ण है?",
        LanguageCode.mr: "Vitamin B12 का महत्त्वाचे आहे?",
        LanguageCode.pa: "Vitamin B12 ਕਿਉਂ ਮਹੱਤਵਪੂਰਨ ਹੈ?",
        LanguageCode.gu: "Vitamin B12 શા માટે મહત્વનું છે?",
        LanguageCode.bn: "Vitamin B12 কেন গুরুত্বপূর্ণ?",
    },
    "crp": {
        LanguageCode.en: "What does CRP measure?",
        LanguageCode.hi: "CRP क्या मापता है?",
        LanguageCode.mr: "CRP काय मोजतो?",
        LanguageCode.pa: "CRP ਕੀ ਮਾਪਦਾ ਹੈ?",
        LanguageCode.gu: "CRP શું માપે છે?",
        LanguageCode.bn: "CRP কী মাপে?",
    },
    "liver": {
        LanguageCode.en: "What is fatty liver?",
        LanguageCode.hi: "फैटी लिवर क्या है?",
        LanguageCode.mr: "फॅटी लिव्हर म्हणजे काय?",
        LanguageCode.pa: "ਫੈਟੀ ਲਿਵਰ ਕੀ ਹੈ?",
        LanguageCode.gu: "ફેટી લિવર શું છે?",
        LanguageCode.bn: "ফ্যাটি লিভার কী?",
    },
    "kidney": {
        LanguageCode.en: "What do kidney function tests look at?",
        LanguageCode.hi: "किडनी फंक्शन टेस्ट क्या देखते हैं?",
        LanguageCode.mr: "किडनी फंक्शन चाचण्या काय पाहतात?",
        LanguageCode.pa: "ਕਿਡਨੀ ਫੰਕਸ਼ਨ ਟੈਸਟ ਕੀ ਦੇਖਦੇ ਹਨ?",
        LanguageCode.gu: "કિડની ફંક્શન ટેસ્ટ શું જુએ છે?",
        LanguageCode.bn: "কিডনি ফাংশন টেস্ট কী দেখে?",
    },
    "heart": {
        LanguageCode.en: "What is heart health in general terms?",
        LanguageCode.hi: "सामान्य रूप से हृदय स्वास्थ्य क्या है?",
        LanguageCode.mr: "सामान्य अर्थाने हृदय आरोग्य म्हणजे काय?",
        LanguageCode.pa: "ਆਮ ਤੌਰ ਤੇ ਦਿਲ ਦੀ ਸਿਹਤ ਕੀ ਹੈ?",
        LanguageCode.gu: "સામાન્ય રીતે હૃદય આરોગ્ય શું છે?",
        LanguageCode.bn: "সাধারণ অর্থে হার্ট হেলথ কী?",
    },
    "metabolic": {
        LanguageCode.en: "What is metabolic age?",
        LanguageCode.hi: "metabolic age क्या है?",
        LanguageCode.mr: "metabolic age म्हणजे काय?",
        LanguageCode.pa: "metabolic age ਕੀ ਹੈ?",
        LanguageCode.gu: "metabolic age શું છે?",
        LanguageCode.bn: "metabolic age কী?",
    },
}

_PERSONAL_TEMPLATES = {
    "latest": {
        LanguageCode.en: "What is my latest {name}?",
        LanguageCode.hi: "मेरा ताज़ा {name} क्या है?",
        LanguageCode.mr: "माझे नवीनतम {name} किती आहे?",
        LanguageCode.pa: "ਮੇਰਾ ਤਾਜ਼ਾ {name} ਕੀ ਹੈ?",
        LanguageCode.gu: "મારું નવીનતમ {name} શું છે?",
        LanguageCode.bn: "আমার সর্বশেষ {name} কত?",
    },
    "meaning": {
        LanguageCode.en: "What does my {name} result mean?",
        LanguageCode.hi: "मेरे {name} परिणाम का क्या मतलब है?",
        LanguageCode.mr: "माझ्या {name} निकालाचा अर्थ काय?",
        LanguageCode.pa: "ਮੇਰੇ {name} ਨਤੀਜੇ ਦਾ ਕੀ ਅਰਥ ਹੈ?",
        LanguageCode.gu: "મારા {name} પરિણામનો અર્થ શું છે?",
        LanguageCode.bn: "আমার {name} ফলাফলের অর্থ কী?",
    },
    "how": {
        LanguageCode.en: "How is my {name} level?",
        LanguageCode.hi: "मेरा {name} स्तर कैसा है?",
        LanguageCode.mr: "माझी {name} पातळी कशी आहे?",
        LanguageCode.pa: "ਮੇਰਾ {name} ਪੱਧਰ ਕਿਵੇਂ ਹੈ?",
        LanguageCode.gu: "મારું {name} સ્તર કેવું છે?",
        LanguageCode.bn: "আমার {name} মাত্রা কেমন?",
    },
    "trend": {
        LanguageCode.en: "Has my {name} changed over time?",
        LanguageCode.hi: "क्या मेरा {name} समय के साथ बदला है?",
        LanguageCode.mr: "माझा {name} कालांतराने बदलला आहे का?",
        LanguageCode.pa: "ਕੀ ਮੇਰਾ {name} ਸਮੇਂ ਨਾਲ ਬਦਲਿਆ ਹੈ?",
        LanguageCode.gu: "શું મારું {name} સમય સાથે બદલાયું છે?",
        LanguageCode.bn: "সময়ের সঙ্গে আমার {name} কি বদলেছে?",
    },
    "bio": {
        LanguageCode.en: "What does my {name} score mean?",
        LanguageCode.hi: "मेरे {name} स्कोर का क्या मतलब है?",
        LanguageCode.mr: "माझ्या {name} स्कोअरचा अर्थ काय?",
        LanguageCode.pa: "ਮੇਰੇ {name} ਸਕੋਰ ਦਾ ਕੀ ਅਰਥ ਹੈ?",
        LanguageCode.gu: "મારા {name} સ્કોરનો અર્થ શું છે?",
        LanguageCode.bn: "আমার {name} স্কোরের অর্থ কী?",
    },
    "nutrition": {
        LanguageCode.en: "What should I know about my nutrition?",
        LanguageCode.hi: "मेरे पोषण के बारे में मुझे क्या जानना चाहिए?",
        LanguageCode.mr: "माझ्या पोषणाबद्दल मला काय माहिती हवे?",
        LanguageCode.pa: "ਮੇਰੇ ਪੋਸ਼ਣ ਬਾਰੇ ਮੈਨੂੰ ਕੀ ਪਤਾ ਹੋਣਾ ਚਾਹੀਦਾ ਹੈ?",
        LanguageCode.gu: "મારા પોષણ વિશે મારે શું જાણવું જોઈએ?",
        LanguageCode.bn: "আমার পুষ্টি নিয়ে আমার কী জানা দরকার?",
    },
}


def _lang(language: str | LanguageCode | None) -> LanguageCode:
    try:
        code = language if isinstance(language, LanguageCode) else LanguageCode(language or "en")
    except ValueError:
        code = LanguageCode.en
    if code == LanguageCode.auto:
        return LanguageCode.en
    return code


def _t(kind: str, name: str, lang: LanguageCode) -> str:
    table = _PERSONAL_TEMPLATES[kind]
    return table.get(lang, table[LanguageCode.en]).format(name=name)


@dataclass
class HealthSnapshot:
    available: bool = False
    markers: list = field(default_factory=list)
    marker_history: dict[str, int] = field(default_factory=dict)
    bio_risks: list = field(default_factory=list)
    has_nutrition: bool = False
    has_blood: bool = False
    has_bio: bool = False
    has_questionnaire: bool = False


def collect_snapshot(principal: AuthenticatedPrincipal, registry: ProviderRegistry) -> HealthSnapshot:
    snap = HealthSnapshot(available=True)
    blood_plan = QueryPlan(
        intent=IntentType.latest_result,
        needs_blood=True,
        history=True,
        knowledge_scope=KnowledgeScope.personal,
    )
    bio_plan = QueryPlan(
        intent=IntentType.bio_ai_score,
        needs_bio_ai=True,
        history=True,
        knowledge_scope=KnowledgeScope.personal,
    )
    life_plan = QueryPlan(
        intent=IntentType.broad_health_summary,
        needs_lifestyle=True,
        knowledge_scope=KnowledgeScope.personal,
    )
    try:
        reports = registry.blood.query(principal, blood_plan) or []
    except ProviderUnavailableError:
        reports = []
        snap.available = False
    except Exception:
        reports = []
    try:
        bio = registry.bio_ai.query(principal, bio_plan) or []
    except ProviderUnavailableError:
        bio = []
        if not reports:
            snap.available = False
    except Exception:
        bio = []
    try:
        life = registry.lifestyle.query(principal, life_plan)
    except Exception:
        life = None

    ordered = sorted(reports, key=lambda r: (r.report_date, r.report_id))
    if ordered:
        snap.has_blood = True
        latest = ordered[-1]
        snap.markers = [m for m in latest.markers if m.value is not None]
        counts: dict[str, int] = {}
        for report in ordered:
            seen = {m.key for m in report.markers if m.value is not None}
            for key in seen:
                counts[key] = counts.get(key, 0) + 1
        snap.marker_history = counts
    if bio:
        snap.has_bio = True
        latest_bio = sorted(bio, key=lambda r: (r.report_date, r.report_id))[-1]
        snap.bio_risks = list(latest_bio.risks or [])
    if life and any("diet preference" in (n or "").lower() for n in (life.notes or [])):
        snap.has_nutrition = True
    try:
        provider = getattr(registry, "questionnaires", None)
        if provider is not None:
            instances = provider.query(
                principal,
                QueryPlan(
                    intent=IntentType.questionnaire_lookup,
                    needs_questionnaire=True,
                    knowledge_scope=KnowledgeScope.personal,
                ),
            ) or []
            snap.has_questionnaire = any(item.answers for item in instances)
    except Exception:
        snap.has_questionnaire = False
    return snap


def _personal_from_snapshot(snap: HealthSnapshot, lang: LanguageCode) -> list[StarterQuestion]:
    out: list[StarterQuestion] = []
    used: set[str] = set()

    flagged = [m for m in snap.markers if m.flag in {MarkerFlag.low, MarkerFlag.high}]
    flagged.sort(key=lambda m: m.name)
    if flagged:
        m = flagged[0]
        used.add(m.key)
        out.append(
            StarterQuestion(
                text=_t("meaning", m.name, lang),
                knowledge_scope="personal",
                category="personal_health",
            )
        )

    others = [m for m in snap.markers if m.key not in used]
    preferred = ["hba1c", "ldl", "hdl", "vitamin_d", "tsh", "triglycerides", "vitamin_b12"]
    others.sort(key=lambda m: (preferred.index(m.key) if m.key in preferred else 99, m.name))
    if others and len(out) < 3:
        m = others[0]
        used.add(m.key)
        kind = "how" if m.key in {"ldl", "hdl", "triglycerides"} else "latest"
        out.append(
            StarterQuestion(
                text=_t(kind, m.name, lang),
                knowledge_scope="personal",
                category="personal_health",
            )
        )

    trend_keys = [k for k, n in snap.marker_history.items() if n >= 2 and k not in used]
    if trend_keys and len(out) < 3:
        key = trend_keys[0]
        name = next((m.name for m in snap.markers if m.key == key), NAMES.get(key, key.replace("_", " ")))
        used.add(key)
        out.append(
            StarterQuestion(
                text=_t("trend", name, lang),
                knowledge_scope="personal",
                category="personal_health",
            )
        )

    if snap.bio_risks and len(out) < 3:
        risk = next((r for r in snap.bio_risks if r.code == "cardiac_health"), snap.bio_risks[0])
        name = risk.name or NAMES.get(risk.code or "", "Bio-AI")
        out.append(
            StarterQuestion(
                text=_t("bio", name, lang),
                knowledge_scope="personal",
                category="personal_health",
            )
        )

    if snap.has_nutrition and len(out) < 3:
        out.append(
            StarterQuestion(
                text=_PERSONAL_TEMPLATES["nutrition"].get(lang, _PERSONAL_TEMPLATES["nutrition"][LanguageCode.en]),
                knowledge_scope="personal",
                category="personal_health",
            )
        )
    return out[:3]


def _general_questions(seed: str, lang: LanguageCode, avoid: set[str], count: int) -> list[StarterQuestion]:
    digest = hashlib.sha256(seed.encode()).hexdigest()
    start = int(digest[:8], 16) % len(GENERAL_POOL)
    ordered = GENERAL_POOL[start:] + GENERAL_POOL[:start]
    out: list[StarterQuestion] = []
    for key, _en in ordered:
        if key in avoid and len(out) + (count - len(out)) > 0 and any(k not in avoid for k, _ in ordered):
            if key in avoid:
                continue
        text = _GENERAL_I18N.get(key, {}).get(lang) or _en
        out.append(
            StarterQuestion(
                text=text,
                knowledge_scope="general",
                category="general_education",
            )
        )
        if len(out) >= count:
            break
    if len(out) < count:
        for key, _en in ordered:
            text = _GENERAL_I18N.get(key, {}).get(lang) or _en
            if any(q.text == text for q in out):
                continue
            out.append(
                StarterQuestion(text=text, knowledge_scope="general", category="general_education")
            )
            if len(out) >= count:
                break
    return out[:count]


def build_starters(
    principal: AuthenticatedPrincipal,
    registry: ProviderRegistry,
    language: str | LanguageCode | None = None,
    *,
    snapshot: HealthSnapshot | None = None,
    profile_available: bool = True,
) -> StarterQuestionSet:
    lang = _lang(language)
    if not profile_available:
        generals = _general_questions(str(principal.subject_id) + ":down", lang, set(), 2)
        return StarterQuestionSet(personal=[], general=generals, personal_unavailable=True)

    snap = snapshot if snapshot is not None else collect_snapshot(principal, registry)
    if not snap.available and not snap.has_blood and not snap.has_bio:
        generals = _general_questions(str(principal.subject_id) + ":empty", lang, set(), 2)
        return StarterQuestionSet(personal=[], general=generals, personal_unavailable=True)

    personal = _personal_from_snapshot(snap, lang)
    avoid = {m.key for m in snap.markers}
    extra = max(0, 3 - len(personal))
    generals = _general_questions(str(principal.subject_id), lang, avoid, 2 + extra)
    return StarterQuestionSet(
        personal=personal,
        general=generals,
        personal_unavailable=len(personal) == 0,
    )
