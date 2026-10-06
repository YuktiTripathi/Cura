"""Red flag taxonomy for the deterministic safety gate.

DRAFT pending clinician sign-off: see docs/clinical/red_flag_taxonomy.md. Every entry
has an urgency level: "now" (call emergency services) or "soon" (see a doctor within a
day). Patterns run on normalized text (see ``normalize_text``), cover English,
romanized Hinglish, Hindi, Marathi, Punjabi, Gujarati and Bengali, and are checked
for negation ("no chest pain") before they fire.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

URGENCY_NOW = "now"
URGENCY_SOON = "soon"

_ZERO_WIDTH = re.compile(r"[​-‍⁠﻿]")
_SPACES = re.compile(r"\s+")

# Common misspellings and voice transcription slips mapped to a canonical form.
_SPELLING_FIXES: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(pattern, re.I), repl)
    for pattern, repl in (
        (r"\bchset\b|\bchets\b|\bcheast\b", "chest"),
        (r"\bpian\b|\bpayn\b", "pain"),
        (r"\bbreathin\b|\bbrething\b|\bbreatheing\b", "breathing"),
        (r"\bsucide|\bsuicde|\bsuiside|\bsucidal|\bsuicidle", "suicide"),
        (r"\bparacetamo?l+\b|\bparacitamol\b|\bparasetamol\b", "paracetamol"),
        (r"\bunconcious\b|\bunconsious\b|\bunconscius\b", "unconscious"),
        (r"\bseziure\b|\bsiezure\b|\bseizur\b", "seizure"),
        (r"\bpregnent\b|\bpragnant\b|\bpreganant\b", "pregnant"),
        (r"\bvomitting\b|\bvommiting\b|\bvomting\b", "vomiting"),
        (r"\bbleding\b|\bbleeeding\b", "bleeding"),
        (r"\bsugar level\b", "sugar"),
        (r"\bcan ?not\b|\bcant\b|\bcan't\b|\bcan’t\b", "cannot"),
        (r"\bdon'?t\b|\bdon’t\b", "do not"),
        (r"\bi'?m\b|\bi’m\b", "i am"),
    )
)


def normalize_text(text: str) -> str:
    """NFKC, lowercase, strip zero-width marks, fix common misspellings, collapse spaces."""
    value = unicodedata.normalize("NFKC", text or "")
    value = _ZERO_WIDTH.sub("", value).replace("’", "'").lower()
    for pattern, repl in _SPELLING_FIXES:
        value = pattern.sub(repl, value)
    return _SPACES.sub(" ", value).strip()


# Negation cue in the few words before a match: "no chest pain", "without fever",
# "denies breathlessness", "chest pain nahi hai" is handled by the trailing check.
_NEG_BEFORE = re.compile(
    r"(?:\b(?:no|not|never|without|denies|deny|free of|absence of|ruled out|"
    r"no sign of|no signs of|nor)\b|नहीं|नही|नाही|ਨਹੀਂ|નથી|না)"
    r"(?:\s+\S+){0,3}\s*$",
    re.I,
)
_NEG_AFTER = re.compile(r"^\s*(?:nahi|nahin|नहीं|नही|नाही|ਨਹੀਂ|નથી|নেই|না)\b(?!\s*(?:aa|आ|ho raha|hoti))", re.I)


@dataclass(frozen=True)
class RedFlag:
    id: str
    category: str  # emergency | self_harm
    urgency: str  # now | soon
    patterns: tuple[re.Pattern[str], ...]
    negatable: bool = True


def _p(*patterns: str) -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(p, re.I) for p in patterns)


# Third person subjects are covered because patterns key on the symptom, not "I".
RED_FLAGS: tuple[RedFlag, ...] = (
    RedFlag(
        "chest_pain",
        "emergency",
        URGENCY_NOW,
        _p(
            r"\bchest (?:pain|pressure|tightness|heaviness|discomfort|squeez\w*|crushing)\b",
            r"\b(?:pain|pressure|tightness|heaviness|discomfort) (?:in|on|across) (?:my |his |her |the )?chest\b",
            r"\bcrushing (?:pain|feeling)\b",
            r"\bchest\b.{0,40}\b(?:left )?arm\b.{0,20}\b(?:numb|pain|tingl\w*|heavy)",
            r"\bheart attack\b",
            r"\bchest\b.{0,30}\bsweat\w*|\bsweat\w*.{0,30}\bchest\b",
            r"\bchest\s*(?:me|mein|main|mai)\s*(?:bahut\s*|tez\s*|bhaari\s*)?(?:dard|pain|jalan|dabav|dabaav)",
            r"\b(?:seene|sine|seena|chhati|chati|chaati)\s*(?:me|mein|main|mai)?\s*(?:bahut\s*|tez\s*|bhaari\s*)?(?:dard|pain|jalan|dabav|dabaav|bhaaripan)",
            r"(?:छाती|सीने|सीना)\s*(?:में|मे)?\s*(?:बहुत\s*|तेज\s*|तेज़\s*)?(?:दर्द|दबाव|भारीपन)",
            r"छाती(?:त|मध्ये)?\s*(?:खूप\s*|फार\s*)?(?:दुख|वेदना|कळ)",
            r"ਛਾਤੀ\s*(?:ਵਿੱਚ|ਵਿਚ)?\s*(?:ਬਹੁਤ\s*|ਤੇਜ਼\s*)?ਦਰਦ",
            r"છાતી(?:માં)?\s*(?:ખૂબ\s*|બહુ\s*)?(?:દુખાવો|દુખે|દર્દ)",
            r"বুকে\s*(?:প্রচণ্ড\s*|খুব\s*|তীব্র\s*)?(?:ব্যথা|ব্যাথা|চাপ)",
        ),
    ),
    RedFlag(
        "stroke_signs",
        "emergency",
        URGENCY_NOW,
        _p(
            r"\b(?:face|mouth|smile)\b.{0,30}\b(?:droop\w*|drooping|tilted|crooked|lopsided|uneven)",
            r"\b(?:droop\w*|crooked) (?:face|mouth|smile)\b",
            r"\bone side(?:d)?\b.{0,40}\b(?:face|weak\w*|numb\w*|paraly\w*|droop\w*)",
            r"\bslurr?ed speech\b|\bspeech (?:is |was )?slurr?ed\b|\bslurring\b|\bcannot speak properly\b",
            r"\bsudden(?:ly)?\b.{0,30}\b(?:weakness|numbness|confusion|vision loss|cannot see|worst headache)",
            r"\bstroke\b|\bparalys\w*|\bparaly[sz]ed\b",
            r"\b(?:muh|munh|mooh)\s*(?:tedha|terha|tirchha)|\blakwa\b|\blaqwa\b|\bbolne me (?:dikkat|takleef)",
            r"लकवा|मुंह\s*टेढ़ा|मुँह\s*टेढ़ा|अर्धांगवायू|ਅਧਰੰਗ|ਲਕਵਾ|લકવો|পক্ষাঘাত|স্ট্রোক",
        ),
    ),
    RedFlag(
        "breathing",
        "emergency",
        URGENCY_NOW,
        _p(
            r"\b(?:difficulty|trouble|struggling) breathing\b|\bshortness of breath\b|\bcannot breathe\b|"
            r"\bunable to breathe\b|\bgasping\b|\bchoking\b|\bbreathless\w* (?:at rest|suddenly)\b|\blips? (?:are |is )?(?:turning |going )?blue\b",
            r"\b(?:saans|saas|sans)\s*(?:nahi|nahin|na)\s*(?:aa|le pa)|\bsaans (?:phool|fool)\w* (?:rahi|raha)",
            r"(?:सांस|साँस)\s*(?:नही|नहीं).{0,12}(?:आ|ले)|सांस\s*फूल",
            r"श्वास\s*(?:घेता\s*येत\s*नाही|घ्यायला\s*त्रास|घेण्यास\s*त्रास)|दम\s*लागत",
            r"ਸਾਹ\s*(?:ਨਹੀਂ|ਨਹੀ)\s*(?:ਆ|ਲੈ)|ਸਾਹ\s*ਲੈਣ\s*(?:ਵਿੱਚ|ਚ)\s*(?:ਤਕਲੀਫ|ਤਕਲੀਫ਼|ਮੁਸ਼ਕਲ)",
            r"શ્વાસ\s*(?:લેવામાં|લેવા)\s*(?:તકલીફ|મુશ્કેલી)|શ્વાસ\s*(?:નથી\s*આવતો|લઈ\s*શકતો\s*નથી|લઈ\s*શકતી\s*નથી)",
            r"শ্বাস\s*নিতে\s*(?:পারছি\s*না|কষ্ট)|শ্বাসকষ্ট|দম\s*বন্ধ",
        ),
        negatable=False,
    ),
    RedFlag(
        "consciousness",
        "emergency",
        URGENCY_NOW,
        _p(
            r"\bunconscious\b|\bloss of consciousness\b|\bpassed out\b|\bfainted\b|\bcollapsed\b|"
            r"\bnot (?:waking|responding|responsive)\b|\bunresponsive\b|\bwill not wake\b|\bvery (?:drowsy|confused)\b",
            r"\bbehosh\w*|\bbehos\b|\bhosh nahi\b",
            r"बेहोश|बेशुद्ध|ਬੇਹੋਸ਼|બેભાન|બેહોશ|অজ্ঞান|জ্ঞান\s*হারা",
        ),
    ),
    RedFlag(
        "seizure",
        "emergency",
        URGENCY_NOW,
        _p(r"\bseizures?\b|\bconvulsion\w*|\bfits?\b(?= (?:now|again|right now|happening))|\bmirgi\b|\bdaura pad", r"मिर्गी|दौरा\s*पड़|ਦੌਰਾ|આંચકી|খিঁচুনি"),
    ),
    RedFlag(
        "heavy_bleeding",
        "emergency",
        URGENCY_NOW,
        _p(
            r"\b(?:severe|heavy|major|uncontrolled|a lot of|lots of|non stop|nonstop) bleeding\b|\bbleeding (?:heavily|a lot|will not stop|won't stop|that will not stop)\b",
            r"\bbleeding\b.{0,40}\bpregnan\w*|\bpregnan\w*.{0,60}\bbleed\w*|\b\d+ weeks?\b.{0,30}\bbleed\w*|\bbleed\w*.{0,30}\b\d+ weeks?\b",
            r"\bvomit\w* (?:blood|bl[o]+d)\b|\bblood in (?:my |his |her )?vomit\b|\bthrowing up blood\b|\bcoughing up blood\b|\bkhoon ki ulti\b",
            r"\b(?:black|tarry) (?:stool|stools|poop|motion)\b",
            r"खून\s*की\s*उल्टी|बहुत\s*खून|खूप\s*रक्तस्त्राव|ਖੂਨ\s*ਦੀ\s*ਉਲਟੀ|લોહીની\s*ઉલટી|রক্ত\s*বমি",
        ),
    ),
    RedFlag(
        "anaphylaxis",
        "emergency",
        URGENCY_NOW,
        _p(
            r"\banaphyla(?:xis|ctic)\b|\bsevere allergic reaction\b|\b(?:throat|tongue|lips?) (?:is |are )?(?:swelling|swollen|closing)\b|\bswelling\b.{0,20}\b(?:throat|tongue)\b",
        ),
    ),
    RedFlag(
        "poisoning_overdose",
        "emergency",
        URGENCY_NOW,
        _p(
            r"\boverdose\w*|\bod'?d\b|\bpoison\w*|\bswallowed\b.{0,30}\b(?:bleach|pesticide|kerosene|acid|cleaner|tablets|pills)\b",
            r"\b(?:too many|too much|lots of|a lot of|whole (?:strip|bottle)|entire (?:strip|bottle)|\d{2,} )\s*(?:of )?(?:my |his |her )?"
            r"(?:\w+ )?(?:tablets|pills|medicine|paracetamol|dolo|crocin|sleeping pills)\b",
            r"\b(?:took|taken|ate|swallowed|kha li|kha liya|kha li hai)\b.{0,30}\b(?:whole|entire|poori|puri) (?:strip|bottle|patta)\b",
            r"\bzeher\b|\bzehar\b|ज़हर|जहर|विष\s*प्या|ਜ਼ਹਿਰ|ઝેર|বিষ",
        ),
    ),
    RedFlag(
        "glucose_extreme",
        "emergency",
        URGENCY_NOW,
        _p(
            r"\b(?:blood )?sugar\b[^.\d]{0,20}\b(?:[4-9]\d\d|[1-9]\d{3})\b",
            r"\b(?:blood )?sugar\b[^.\d]{0,20}\b(?:[1-5]\d|[0-9])\b(?! ?(?:years|yrs|days|weeks|%))",
            r"\b(?:very )?(?:high|low) (?:blood )?sugar\b.{0,40}\b(?:dizz\w*|faint\w*|confus\w*|shak\w*|sweat\w*|vomit\w*|drowsy|unconscious)",
            r"\b(?:hypo|hypoglycemi\w*|hypoglycaemi\w*|dka|ketoacidosis)\b",
        ),
    ),
    RedFlag(
        "infant_red_flags",
        "emergency",
        URGENCY_NOW,
        _p(
            r"\b(?:baby|infant|newborn|toddler|\d+ (?:month|months|week|weeks) old)\b.{0,60}\b(?:fever|not responding|unresponsive|limp|floppy|lethargic|not feeding|will not feed|blue|fit|seizure|not waking)",
            r"\b(?:fever|not responding|limp|floppy|lethargic)\b.{0,40}\b(?:baby|infant|newborn)\b",
            r"\b(?:bachch?a|bachch?e|shishu)\b.{0,40}\b(?:tez bukhar|bukhar|behosh|hil nahi|jawab nahi)",
        ),
    ),
    RedFlag(
        "other_now",
        "emergency",
        URGENCY_NOW,
        _p(
            r"\bsevere dehydration\b|\brapidly worsening\b|\bworst headache of my life\b|\bsevere head injury\b|\bburn\w*\b.{0,20}\b(?:large|severe|face)\b",
        ),
    ),
    RedFlag(
        "self_harm",
        "self_harm",
        URGENCY_NOW,
        _p(
            r"\bsuicid\w*|\bkill (?:myself|me)\b|\bend (?:my|it all|my own) life\b|\bend it all\b|\bending (?:everything|it all|my life)\b|\bend everything\b",
            r"\b(?:do not|no longer|never) want to (?:live|be alive|wake up|exist)\b|\bwant to die\b|\bwish i (?:was|were) dead\b|\bbetter off dead\b",
            r"\b(?:no|not any|any) (?:point|reason|purpose) (?:in |of )?(?:living|life|going on|to live)\b|\bno point living\b|\bdo not see (?:any |a )?(?:point|reason)\b.{0,20}\b(?:liv\w*|life|anymore)\b",
            r"\bhurt(?:ing)? myself\b|\bharm(?:ing)? myself\b|\bself[ -]?harm\w*|\bcut(?:ting)? myself\b",
            r"\bcannot (?:go on|take it anymore|cope anymore)\b|\bgive up on (?:life|living)\b|\beveryone would be better without me\b",
            r"\b(?:mujhe )?jeena nahi|\bjeene ka (?:mann|man|koi matlab) nahi\b|\bmarna chaht\w*|\bmar jana chaht\w*|\bmar jaun\b|\bkhudkushi\b|\bsuicide kar\w*|\baatmahatya\b",
            r"जीना\s*नहीं|जीना\s*नहि|जीने\s*का\s*मन\s*नहीं|मरना\s*चाहत|मर\s*जाना\s*चाहत|आत्महत्या|खुदकुशी",
            r"जगायचं\s*नाही|जगायचे\s*नाही|जीव\s*द्यायचा|मरायचं\s*आहे",
            r"ਖੁਦਕੁਸ਼ੀ|ਖ਼ੁਦਕੁਸ਼ੀ|ਆਤਮਹੱਤਿਆ|ਜੀਣਾ\s*ਨਹੀਂ|ਮਰਨਾ\s*ਚਾਹੁੰਦ",
            r"આત્મહત્યા|આપઘાત|જીવવું\s*નથી|મરી\s*જવું\s*છે",
            r"আত্মহত্যা|বাঁচতে\s*চাই\s*না|মরে\s*যেতে\s*চাই",
        ),
        negatable=False,
    ),
    # "soon" — see a doctor within a day. These do not block; they add a caution.
    RedFlag(
        "see_doctor_soon",
        "urgent_soon",
        URGENCY_SOON,
        _p(
            r"\bfever\b.{0,30}\b(?:[3-9]|\d{2}) days\b|\b(?:[3-9]|\d{2}) days\b.{0,30}\bfever\b",
            r"\bblood in (?:my |his |her )?(?:urine|stool|stools|pee)\b",
            r"\b(?:persistent|continuous|non stop) vomiting\b|\bcannot keep (?:anything|water|food) down\b",
            r"\b(?:bp|blood pressure)\b[^.\d]{0,20}\b(?:1[89]\d|2\d\d)\s*/\s*\d{2,3}\b",
            r"\byellow(?:ing)? (?:eyes|skin)\b|\bjaundice\b",
        ),
    ),
)


def _negated(text: str, start: int, end: int) -> bool:
    before = text[max(0, start - 40):start]
    if _NEG_BEFORE.search(before):
        return True
    return bool(_NEG_AFTER.match(text[end:end + 16]))


def match_red_flags(text: str) -> list[RedFlag]:
    """Return every red flag that fires on ``text`` (normalized inside), skipping negated hits."""
    normalized = normalize_text(text)
    hits: list[RedFlag] = []
    for flag in RED_FLAGS:
        for pattern in flag.patterns:
            fired = False
            for match in pattern.finditer(normalized):
                if flag.negatable and _negated(normalized, match.start(), match.end()):
                    continue
                fired = True
                break
            if fired:
                hits.append(flag)
                break
    return hits
