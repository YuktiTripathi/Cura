"""Recognise biomarker names written in the Indic scripts Cura supports, for routing.

People asking in Hindi, Marathi, Punjabi, Gujarati or Bengali write lab abbreviations three ways:
in Latin ("मेरा LDL क्या है?"), spelled out letter by letter in their own script ("मेरा एलडीएल
क्या है?"), or with a localized name the ontology already knows ("विटामिन डी"). The routing
pipeline matches Latin aliases, so this module rewrites the last two forms to their Latin/English
name before planning. It never invents a biomarker: a rewrite happens only when the result is a
known alias.

It also reads possessive-free status questions ("Vitamin D कम है क्या?") as questions about the
user's own result. These languages routinely drop the possessive there; English keeps "my", so
English routing is untouched.
"""

from __future__ import annotations

import re
from functools import lru_cache

from app.pipeline.lab_parameters import display_name_for, parameter_alias_map
from app.pipeline.medical_terms import MARKER_ALIASES_I18N

# English letter names as commonly written in each script (variants included).
_LETTER_NAMES: dict[str, dict[str, str]] = {
    "devanagari": {
        "ए": "A", "बी": "B", "सी": "C", "डी": "D", "ई": "E", "एफ": "F", "जी": "G", "एच": "H", "ऐच": "H",
        "आई": "I", "जे": "J", "के": "K", "एल": "L", "एम": "M", "एन": "N", "ओ": "O", "पी": "P",
        "क्यू": "Q", "आर": "R", "एस": "S", "टी": "T", "यू": "U", "वी": "V", "व्ही": "V", "डब्ल्यू": "W",
        "डबल्यू": "W", "एक्स": "X", "वाई": "Y", "वाय": "Y", "जेड": "Z", "ज़ेड": "Z", "झेड": "Z",
    },
    "gurmukhi": {
        "ਏ": "A", "ਬੀ": "B", "ਸੀ": "C", "ਡੀ": "D", "ਈ": "E", "ਐਫ": "F", "ਜੀ": "G", "ਐਚ": "H",
        "ਆਈ": "I", "ਜੇ": "J", "ਕੇ": "K", "ਐਲ": "L", "ਐਮ": "M", "ਐਨ": "N", "ਓ": "O", "ਪੀ": "P",
        "ਕਿਊ": "Q", "ਆਰ": "R", "ਐਸ": "S", "ਟੀ": "T", "ਯੂ": "U", "ਵੀ": "V", "ਡਬਲਯੂ": "W",
        "ਐਕਸ": "X", "ਵਾਈ": "Y", "ਜ਼ੈਡ": "Z", "ਜੈਡ": "Z",
    },
    "gujarati": {
        "એ": "A", "બી": "B", "સી": "C", "ડી": "D", "ઈ": "E", "એફ": "F", "જી": "G", "એચ": "H",
        "આઈ": "I", "જે": "J", "કે": "K", "એલ": "L", "એમ": "M", "એન": "N", "ઓ": "O", "પી": "P",
        "ક્યૂ": "Q", "આર": "R", "એસ": "S", "ટી": "T", "યુ": "U", "યૂ": "U", "વી": "V", "ડબલ્યુ": "W",
        "એક્સ": "X", "વાય": "Y", "વાઈ": "Y", "ઝેડ": "Z",
    },
    "bengali": {
        "এ": "A", "বি": "B", "সি": "C", "ডি": "D", "ই": "E", "এফ": "F", "জি": "G", "এইচ": "H",
        "এইচ্": "H", "আই": "I", "জে": "J", "কে": "K", "এল": "L", "এম": "M", "এন": "N", "ও": "O",
        "পি": "P", "কিউ": "Q", "আর": "R", "এস": "S", "টি": "T", "ইউ": "U", "ভি": "V", "ডাবলিউ": "W",
        "এক্স": "X", "ওয়াই": "Y", "জেড": "Z",
    },
}

_DIGITS = str.maketrans("०१२३४५६७८९੦੧੨੩੪੫੬੭੮੯૦૧૨૩૪૫૬૭૮૯০১২৩৪৫৬৭৮৯", "0123456789" * 4)
# Gurmukhi addak / Devanagari nukta-free spellings: marks that do not change the letter name.
_IGNORABLE = re.compile("[ੱ़਼઼়‌‍]")
_INDIC = "ऀ-ॿঀ-৿਀-੿઀-૿"
# A run of Indic letters, digits (any script) and hyphens: a candidate spelled abbreviation.
_TOKEN = re.compile(rf"[{_INDIC}0-9०-९੦-੯૦-૯০-৯]+(?:-[{_INDIC}0-9०-९੦-੯૦-૯০-৯]+)*")
_HAS_INDIC = re.compile(rf"[{_INDIC}]")


@lru_cache(maxsize=1)
def _known_aliases() -> frozenset[str]:
    names = set(parameter_alias_map())
    names.update(display_name_for(key).lower() for key in set(parameter_alias_map().values()))
    return frozenset(name.lower() for name in names)


def _spell(part: str) -> str | None:
    """Letter names → Latin letters, or None if `part` is not made only of letter names and digits."""
    for table in _LETTER_NAMES.values():
        names = sorted(table, key=len, reverse=True)
        out: list[str] = []
        i = 0
        while i < len(part):
            if part[i].isdigit():
                out.append(part[i])
                i += 1
                continue
            match = next((name for name in names if part.startswith(name, i)), None)
            if match is None:
                break
            out.append(table[match])
            i += len(match)
        else:
            if sum(ch.isalpha() for ch in out) >= 2:
                return "".join(out)
    return None


def latinize_spelled_abbreviations(text: str) -> str:
    """"एलडीएल" → "LDL", "एचबीए1सी" → "HBA1C", "एचएस-सीआरपी" → "HS-CRP" when that is a known biomarker alias."""
    if not text or not _HAS_INDIC.search(text):
        return text
    known = _known_aliases()

    def replace(match: re.Match[str]) -> str:
        raw = match.group(0)
        token = _IGNORABLE.sub("", raw).translate(_DIGITS)
        if not _HAS_INDIC.search(token):
            return raw
        parts = token.split("-")
        latin = [_spell(part) for part in parts]
        if any(item is None for item in latin):
            return raw
        candidate = "-".join(latin)  # type: ignore[arg-type]
        variants = {candidate.lower(), candidate.lower().replace("-", " "), candidate.lower().replace("-", "")}
        # "HS-CRP": accept when the whole or any hyphenated part is a known alias.
        variants.update(item.lower() for item in latin if item)  # type: ignore[union-attr]
        return candidate if variants & known else raw

    return _TOKEN.sub(replace, text)


@lru_cache(maxsize=1)
def _localized_pattern() -> tuple[re.Pattern[str], dict[str, str]]:
    names = {alias: display_name_for(key) or key.replace("_", " ") for alias, key in MARKER_ALIASES_I18N.items() if _HAS_INDIC.search(alias)}
    ordered = sorted(names, key=len, reverse=True)
    return re.compile("|".join(re.escape(alias) for alias in ordered), re.I), names


def english_names_for_localized_terms(text: str) -> str:
    """Localized ontology names ("विटामिन डी", "कोलेस्ट्रॉल") → their English display name."""
    if not text or not _HAS_INDIC.search(text):
        return text
    pattern, names = _localized_pattern()
    return pattern.sub(lambda m: names.get(m.group(0), names.get(m.group(0).lower(), m.group(0))), text)


def canonicalize_biomarker_terms(text: str) -> str:
    """Biomarker names in Indic scripts → the Latin/English names the routing ontology matches."""
    return latinize_spelled_abbreviations(english_names_for_localized_terms(text))


# "<biomarker> low/high/normal is (question)?" in each supported language, without a possessive.
_STATUS_WORDS = {
    "low": r"कम|कमी|लो|ਘੱਟ|ਘਟ|ઓછું|ઓછુ|ઓછી|কম",
    "high": r"ज़्यादा|ज्यादा|जास्त|अधिक|हाई|ਵੱਧ|ਜ਼ਿਆਦਾ|ਜਿਆਦਾ|વધારે|વધુ|বেশি|বেশী",
    "normal": r"नॉर्मल|सामान्य|ठीक|ਠੀਕ|ਨਾਰਮਲ|ਸਧਾਰਨ|સામાન્ય|બરાબર|નોર્મલ|স্বাভাবিক|ঠিক|নরমাল",
}
_COPULA = r"(?:है|हैं|आहे|ਹੈ|ਹਨ|છે|আছে)?"
_QUESTION = r"(?:क्या|का|ਕੀ|શું|કે|কি|কী)?"
_STATUS_QUESTION = re.compile(
    rf"^\s*(?:my\s+)?(?P<term>.+?)\s+(?:{_QUESTION}\s*)?(?P<status>{'|'.join(_STATUS_WORDS.values())})\s*{_COPULA}\s*{_QUESTION}\s*[?？।]?\s*$",
    re.I,
)
_STATUS_OF = {word: label for label, words in _STATUS_WORDS.items() for word in words.split("|")}


def status_question_as_english(text: str) -> str:
    """'Vitamin D कम है क्या?' → 'is my Vitamin D low?' when the subject is a known biomarker."""
    match = _STATUS_QUESTION.match(text or "")
    if not match:
        return text
    term = match.group("term").strip()
    if term.lower() not in _known_aliases():
        return text
    return f"is my {term} {_STATUS_OF.get(match.group('status'), 'low')}?"


# "(and) <biomarker> का क्या?" ≈ "what about <biomarker>?" — the follow-up form English routing supports.
_AND = r"और|आणि|ਅਤੇ|ਤੇ|અને|আর|এবং|and"
_OF = r"का|के|की|चं|चे|ची|चा|ਦਾ|ਦੇ|ਦੀ|નું|ના|ની|નો|এর|ের|র"
_WHAT = r"क्या|काय|ਕੀ|શું|কী|কি|के बारे में|बद्दल|ਬਾਰੇ|વિશે|সম্পর্কে"
_WHAT_ABOUT = re.compile(
    rf"^\s*(?:(?:{_AND})\s+)?(?P<term>.+?)\s*(?:{_OF})?\s*(?:{_WHAT})\s*(?:है|आहे|ਹੈ|છે)?\s*[?？।]?\s*$",
    re.I,
)


def follow_up_as_english(text: str) -> str:
    """'और HDL का क्या?' → 'what about HDL?' when the subject is a known biomarker."""
    match = _WHAT_ABOUT.match(text or "")
    if not match or not _HAS_INDIC.search(text):
        return text
    term = match.group("term").strip()
    if term.lower() not in _known_aliases():
        return text
    return f"what about {term}?"

