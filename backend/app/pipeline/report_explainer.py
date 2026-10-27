"""Plain-language explanations of a whole blood report or Bio-AI report.

Used when no model writes the answer (for example while personal-health prompts
stay local). Results are grouped by body system, each group says what its tests
measure and what the member's pattern means, the most important group comes
first, and Bio-AI scores are linked to the blood results behind them. Wording
stays educational: it describes ranges and patterns and points to a doctor,
never diagnoses.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.contracts.blood import BloodMarker
from app.pipeline.clinical_thresholds import clinical_notes


def _norm(text: str | None) -> str:
    return "".join(ch for ch in (text or "").lower() if ch.isalnum())


@dataclass(frozen=True)
class _Theme:
    code: str
    title: str
    about: str
    words: tuple[str, ...]


# Order is the reading order when no result is urgent.
_THEMES = (
    _Theme("sugar", "Blood sugar",
           "These tests show how your body is handling sugar.",
           ("hba1c", "glycated", "glucose", "bloodsugar", "insulin")),
    _Theme("lipids", "Cholesterol and blood fats",
           "These tests measure the fats carried in your blood. Over years, high LDL, VLDL and triglycerides are linked to a higher risk of heart and blood-vessel disease, and they usually respond well to changes in diet, activity and weight.",
           ("cholesterol", "cholestrol", "ldl", "hdl", "vldl", "triglyceride", "lipoprotein", "apob")),
    _Theme("iron", "Iron and red blood cells",
           "These tests show how much iron your body has stored and how well your red blood cells are formed. Red blood cells carry oxygen, so low iron can show up as tiredness or low energy.",
           ("ferritin", "iron", "tibc", "transferrin", "haemoglobin", "hemoglobin", "mcv", "mchc", "mch",
            "rdw", "redbloodcell", "rbc", "haematocrit", "hematocrit", "pcv")),
    _Theme("liver", "Liver",
           "These enzymes and proteins show how your liver is working.",
           ("sgot", "sgpt", "alt", "ast", "ggt", "alkalinephosphatase", "bilirubin", "albumin", "globulin")),
    _Theme("kidney", "Kidneys and body salts",
           "These tests show how well your kidneys are filtering and how your body is balancing salts and water. Small differences just outside the range are common and often not significant on their own.",
           ("creatinine", "urea", "bun", "uricacid", "egfr", "sodium", "potassium", "chloride", "calcium", "phosph")),
    _Theme("thyroid", "Thyroid",
           "Thyroid hormones help set your body's energy use and metabolism.",
           ("tsh", "t3", "t4", "thyro")),
    _Theme("vitamins", "Vitamins",
           "Vitamins such as D and B12 support bones, muscles, nerves and energy.",
           ("vitamin", "b12", "cobalamin", "folate", "folic")),
    _Theme("cells", "Platelets and white blood cells",
           "Platelets help your blood clot and white blood cells fight infection. Small changes in platelet size (MPV) are common and usually not significant on their own.",
           ("platelet", "mpv", "pdw", "plcr", "wbc", "whitebloodcell", "neutrophil", "lymphocyte",
            "monocyte", "eosinophil", "basophil", "leucocyte", "leukocyte")),
)
_SHORT = {"sugar": "blood sugar", "lipids": "cholesterol", "iron": "iron", "liver": "liver health",
          "kidney": "kidney and salt balance", "vitamins": "vitamins", "cells": "platelets"}
_OTHER = _Theme("other", "Other results", "", ())


def _theme(marker: BloodMarker) -> _Theme:
    text = _norm(marker.key) + " " + _norm(marker.name)
    for theme in _THEMES:
        if any(word in text for word in theme.words):
            return theme
    return _OTHER


def _flag(marker: BloodMarker) -> str:
    return getattr(marker.flag, "value", str(marker.flag or "")).lower()


def _out_of_range(marker: BloodMarker) -> bool:
    return marker.value is not None and _flag(marker) in {"low", "high", "critical", "critical_low", "critical_high"}


def _dedupe(markers: list[BloodMarker]) -> list[BloodMarker]:
    """Labs often repeat a test under two names (MPV / "MPV Mean Platelet Volume")."""
    seen: set[tuple[str, float | None, str]] = set()
    out = []
    for marker in markers:
        identity = (_norm(marker.name)[:3], marker.value, _norm(marker.unit))
        if identity in seen:
            continue
        seen.add(identity)
        out.append(marker)
    return out


def _bullets(items) -> str:
    """Members read bullets more easily than paragraphs: one idea per line."""
    return "\n".join(f"- {item.strip()}" for item in items if item and item.strip())


def _value(marker: BloodMarker) -> str:
    from app.pipeline.narrative import format_marker_name, format_unit

    unit = format_unit(marker.unit) or ""
    sep = "" if unit in {"%", ""} else " "
    direction = "high" if "high" in _flag(marker) else "low"
    return f"{_display_name(format_marker_name(marker.name))} {marker.value:g}{sep}{unit} ({direction})"


_SPELLING = {"Cholestrol": "Cholesterol", "cholestrol": "cholesterol", "Platelate": "Platelet",
             "platelate": "platelet", "HBA1C": "HbA1c", "Hba1c": "HbA1c", "HBA1c": "HbA1c"}


def _display_name(name: str) -> str:
    """Fix lab-feed spellings members would otherwise see verbatim."""
    for wrong, right in _SPELLING.items():
        name = name.replace(wrong, right)
    return name


def _test_notes(markers: list[BloodMarker]) -> list[str]:
    """Per-test background, only for tests the member actually has."""
    names = " ".join(_norm(m.name) + " " + _norm(m.key) for m in markers)
    notes = []
    if "hba1c" in names or "glycated" in names:
        notes.append("HbA1c shows your average blood sugar over the last two to three months.")
    if "glucose" in names or "bloodsugar" in names:
        notes.append("A glucose test shows the sugar level at the moment the sample was taken.")
    return notes


def _has(markers: list[BloodMarker], *words: str, direction: str) -> bool:
    return any(
        any(word in _norm(m.name) or word == _norm(m.key) for word in words) and direction in _flag(m)
        for m in markers
    )


def _pattern(theme: str, markers: list[BloodMarker]) -> str | None:
    """A sentence on what the results mean together, only for well-known patterns."""
    if theme == "iron":
        low_stores = _has(markers, "ferritin", direction="low")
        small_cells = _has(markers, "mcv", "mch", direction="low")
        high_tibc = _has(markers, "tibc", "transferrin", direction="high")
        if low_stores and (small_cells or high_tibc):
            return (
                "Taken together, low ferritin with smaller red blood cells"
                + (" and a high TIBC" if high_tibc else "")
                + " is a pattern often seen when the body's iron stores are running low."
                " A doctor can confirm this and check the cause."
            )
        if low_stores:
            return "Low ferritin usually means your iron stores are on the low side."
        low_hb = _has(markers, "haemoglobin", "hemoglobin", "hb", direction="low")
        low_iron = _has(markers, "iron", direction="low")
        if low_hb and small_cells and low_iron:
            return (
                "Taken together, low haemoglobin with smaller red blood cells and low iron is a pattern "
                "often seen with iron-deficiency anaemia. A doctor can confirm this and check the cause."
            )
    if theme == "lipids":
        high = [m for m in markers if "high" in _flag(m)]
        if len(high) >= 2:
            return (
                "Several of your blood-fat results are high at the same time, so this is worth "
                "looking at as one area rather than test by test."
            )
    if theme == "sugar" and _has(markers, "hba1c", direction="high"):
        return None  # the clinical note says it more precisely
    return None


def explain_blood_report(markers: list[BloodMarker], *, in_range: int | None = None,
                         out_of_range: int | None = None) -> str:
    flagged = _dedupe([m for m in markers if _out_of_range(m)])
    total = (in_range or 0) + (out_of_range or 0)
    if not flagged:
        return (
            "Good news: all the results in your latest report are within the lab's reference ranges. "
            "Keep up your current habits, and ask about any specific test you'd like explained."
        )

    groups: dict[str, list[BloodMarker]] = {}
    for marker in flagged:
        groups.setdefault(_theme(marker).code, []).append(marker)
    notes = clinical_notes(flagged)
    urgent = {(_theme(n.marker).code) for n in notes if n.urgent}
    noted = {(_theme(n.marker).code) for n in notes}
    order = [t for t in (*_THEMES, _OTHER) if t.code in groups]
    order.sort(key=lambda t: (t.code not in urgent, t.code not in noted))

    titles = [_SHORT.get(t.code, t.title.lower()) for t in order[:2]]
    focus = " and ".join(titles)
    stands = f"The area that stands out is {focus}." if len(titles) == 1 else f"The areas that stand out are {focus}."
    if total:
        opening = f"Most of your results look fine: {in_range} of {total} are within range. {stands}"
    else:
        opening = stands

    parts = [opening]
    for theme in order:
        items = groups[theme.code][:4]
        section = [f"**{theme.title}**"]
        if theme.about:
            section.append(theme.about)
        section.extend(_test_notes(items))
        section.append("Your results: " + ", ".join(_value(m) for m in items) + ".")
        pattern = _pattern(theme.code, items)
        if pattern:
            section.append(pattern)
        for note in notes:
            if _theme(note.marker).code == theme.code:
                section.append(note.text)
        parts.append(section[0] + "\n" + _bullets(section[1:]))

    # The urgent clinical note already says to see a doctor. Do not add a second visit paragraph.
    return "\n\n".join(parts)


# Bio-AI ---------------------------------------------------------------------

# The Bio-AI report's assessments (PCOS for women only). Metabolic syndrome comes first so
# "metabolic syndrome" is not read as the blood-sugar entry.
_RISK_INFO = (
    (("metabolicsyndrome",), "your risk of metabolic syndrome, a cluster of raised blood sugar, blood fats, blood pressure and waist size that together raise heart and diabetes risk", "sugar"),
    (("pcos", "polycystic"), "your risk related to PCOS (polycystic ovary syndrome), a hormonal condition linked to periods, weight and blood sugar", None),
    (("dyslipid", "cholesterol", "lipid"), "how likely you are to have unhealthy levels of blood fats such as cholesterol and triglycerides", "lipids"),
    (("diabet", "glyc", "sugar", "insulin"), "your risk of developing type 2 diabetes", "sugar"),
    (("hypertension", "bloodpressure"), "your risk of high blood pressure", None),
    (("oxidative",), "how much oxidative stress (wear on your cells) your body may be under, which is influenced by sleep, diet, activity and stress", None),
    (("nafld", "fattyliver", "liver"), "your risk of fat building up in the liver", "liver"),
    (("cardiac", "heart", "cardio"), "your risk related to heart health", "lipids"),
    (("obesity", "weight"), "your risk related to body weight", None),
    (("thyroid",), "your risk related to thyroid function", "thyroid"),
    (("anaemia", "anemia"), "your risk of anaemia (low red blood cells or iron)", "iron"),
)
_CONCERN = ("veryhigh", "high", "increased", "elevated", "moderate")


def _risk_info(code: str, name: str) -> tuple[str, str | None]:
    text = _norm(code) + _norm(name)
    for words, meaning, theme in _RISK_INFO:
        if any(word in text for word in words):
            return meaning, theme
    return f"your risk related to {name.lower()}", None


def _concern(status: str | None) -> int:
    s = _norm(status)
    for rank, word in enumerate(_CONCERN):
        if word in s:
            return rank
    return len(_CONCERN)


def explain_bio_ai(risks: list, markers: list[BloodMarker] | None = None) -> str:
    scored = [r for r in risks if getattr(r, "score", None) is not None]
    if not scored:
        return "Your Bio-AI report doesn't have scores I can explain yet."
    scored.sort(key=lambda r: (_concern(r.status), -(r.score or 0)))
    attention = [r for r in scored if _concern(r.status) < len(_CONCERN)]
    fine = [r for r in scored if r not in attention]
    flagged = [m for m in (markers or []) if _out_of_range(m)]

    parts = []
    if attention:
        names = ", ".join(r.name for r in attention[:3])
        parts.append(f"The scores that deserve the most attention are **{names}**.")
    for risk in attention:
        meaning, theme = _risk_info(risk.code, risk.name)
        line = f"- **{risk.name}: {risk.score:g} ({risk.status or 'no level given'}).** This score reflects {meaning}."
        linked = [m for m in flagged if theme and _theme(m).code == theme]
        if linked:
            line += (
                " It lines up with your blood report, where "
                + ", ".join(_value(m) for m in _dedupe(linked)[:4])
                + (" are" if len(linked) > 1 else " is")
                + " outside the range."
            )
        if (risk.lifestyle_contribution or 0) >= 40:
            line += " A large part of this score is linked to lifestyle, so it can come down with changes to diet, activity and sleep."
        parts.append(line)
    if not attention:
        parts.append("Good news: none of your Bio-AI scores is in a raised range right now.")
    if fine:
        names = ", ".join(f"{r.name} ({r.score:g}, {r.status or 'no level given'})" for r in fine)
        parts.append(f"**Looking good:** {names}.")
    parts.append(
        "These are risk estimates, not diagnoses. A higher score means a higher estimated risk."
    )
    return "\n\n".join(parts)


# Single tests and topics ------------------------------------------------------

_ABOUT = (
    (("hba1c", "glycated"), "HbA1c shows your average blood sugar over the last two to three months."),
    (("fastingbloodglucose", "fastingglucose", "fastingbloodsugar", "glucose"), "Glucose is the sugar level in your blood at the moment the sample was taken."),
    (("ldl",), "LDL is often called \"bad\" cholesterol because, when it stays high for years, it can build up in the walls of blood vessels."),
    (("hdl",), "HDL is often called \"good\" cholesterol because it helps carry extra cholesterol away from blood vessels."),
    (("vldl",), "VLDL carries mainly triglycerides (a type of fat) in the blood."),
    (("triglyceride",), "Triglycerides are a type of fat in the blood that the body uses for energy. They rise with sugary and refined foods, alcohol and low activity."),
    (("cholesterol", "cholestrol"), "Total cholesterol adds up the different kinds of cholesterol in your blood."),
    (("vitamind",), "Vitamin D helps your body absorb calcium and supports bones, muscles and immunity. Most of it is made in the skin from sunlight."),
    (("b12", "cobalamin"), "Vitamin B12 is needed for healthy nerves and for making red blood cells."),
    (("ferritin",), "Ferritin shows how much iron your body has in storage."),
    (("tibc", "transferrin"), "TIBC shows how much capacity your blood has to carry iron. It usually goes up when iron stores are low."),
    (("serumiron", "iron"), "Serum iron is the amount of iron circulating in your blood at the time of the test."),
    (("haemoglobin", "hemoglobin", "hb"), "Haemoglobin is the protein in red blood cells that carries oxygen around your body."),
    (("mchc",), "MCHC shows how concentrated the haemoglobin is inside your red blood cells."),
    (("mch",), "MCH is the average amount of haemoglobin in each red blood cell."),
    (("mcv",), "MCV is the average size of your red blood cells. Smaller cells are often linked with low iron."),
    (("rdw",), "RDW shows how much your red blood cells vary in size."),
    (("mpv",), "MPV is the average size of your platelets, the cells that help blood clot."),
    (("platelet",), "Platelets are the cells that help your blood clot."),
    (("redbloodcell", "rbc"), "This is the number of red blood cells, which carry oxygen."),
    (("creatinine",), "Creatinine is a waste product from your muscles that your kidneys filter out, so it helps show how well they are working. It also depends on muscle mass."),
    (("egfr",), "eGFR estimates how well your kidneys are filtering your blood."),
    (("urea", "bun"), "Urea is a waste product that your kidneys remove. It is affected by protein intake and how much water you drink."),
    (("uricacid",), "Uric acid is a waste product. High levels can lead to gout or kidney stones in some people."),
    (("chloride",), "Chloride is a salt that helps keep your body's fluid and acid balance steady."),
    (("sodium",), "Sodium is a salt that controls fluid balance and nerve and muscle function."),
    (("potassium",), "Potassium is a salt that is important for your heart rhythm and muscles."),
    (("tsh",), "TSH is the signal your brain sends to the thyroid. A high TSH can mean the thyroid is underactive, and a low TSH can mean it is overactive."),
    (("t4", "thyroxine"), "T4 is the main hormone made by your thyroid."),
    (("t3",), "T3 is the active form of thyroid hormone."),
    (("alt", "sgpt"), "ALT is a liver enzyme. Higher levels can mean the liver is under strain."),
    (("ast", "sgot"), "AST is an enzyme found in the liver and muscles."),
    (("bilirubin",), "Bilirubin is made when old red blood cells are broken down, and the liver clears it."),
)


def _about(marker: BloodMarker) -> str | None:
    key = _norm(marker.key)
    name = _norm(marker.name)
    for words, text in _ABOUT:
        if any(word == key or word in name for word in words):
            return text
    return None


def _range_text(marker: BloodMarker) -> str:
    from app.pipeline.narrative import format_unit

    unit = format_unit(marker.unit) or ""
    sep = "" if unit in {"%", ""} else " "
    low, high = marker.reference_low, marker.reference_high
    if low not in (None, 0) and high is not None:
        return f"{low:g} to {high:g}{sep}{unit}"
    if high is not None:
        return f"below {high:g}{sep}{unit}"
    if low is not None:
        return f"above {low:g}{sep}{unit}"
    return ""


def _status_sentence(marker: BloodMarker) -> str:
    from app.pipeline.narrative import format_unit

    unit = format_unit(marker.unit) or ""
    sep = "" if unit in {"%", ""} else " "
    name = _display_name(marker.name)
    flag = _flag(marker)
    ref = _range_text(marker)
    lab = f" (your lab's range is {ref})" if ref else ""
    if "high" in flag:
        state = "higher than the normal range"
    elif "low" in flag:
        state = "lower than the normal range"
    elif flag == "normal":
        state = "within the normal range"
    else:
        state = "reported without a clear range"
    verb = "are" if name.lower().endswith(("ides", "cells", "lipids")) else "is"
    return f"Your {name} {verb} {marker.value:g}{sep}{unit}, which is {state}{lab}."


def explain_markers(markers: list[BloodMarker]) -> str:
    """Explain one test or a small topic (cholesterol, iron) in plain words."""
    usable = _dedupe([m for m in markers if m.value is not None])
    if not usable:
        return ""
    parts = []
    for marker in usable:
        lines = [_status_sentence(marker)]
        about = _about(marker)
        if about:
            lines.append(about)
        from app.pipeline.clinical_thresholds import clinical_note

        note = clinical_note(marker)
        if note:
            lines.append(note.text)
        parts.append(" ".join(lines))
    flagged = [m for m in usable if _out_of_range(m)]
    one_test = len(parts) == 1
    themes = {_theme(m).code for m in flagged}
    patterns = [p for p in (_pattern(code, [m for m in flagged if _theme(m).code == code]) for code in themes) if p]
    parts.extend(patterns)
    if not flagged:
        parts.append("Everything here is within your lab's normal range, so there is nothing that needs action.")
    elif not clinical_notes(flagged) and not patterns:
        parts.append("Results a little outside the range are common and often settle on their own. "
                     "It is worth mentioning them to your doctor at your next visit.")
    if one_test and len(parts) <= 2:
        return "\n\n".join(parts)  # a simple question stays a short paragraph
    return _bullets(parts)


def explain_overall(markers: list[BloodMarker], risks: list | None, *,
                    in_range: int | None = None, out_of_range: int | None = None) -> str:
    """Whole-health questions: the blood report explained, then raised Bio-AI scores tied in."""
    text = explain_blood_report(markers, in_range=in_range, out_of_range=out_of_range)
    body, sep, closing = text.rpartition("\n\n**What to do next:**")
    raised = [r for r in (risks or []) if getattr(r, "score", None) is not None
              and _concern(r.status) < len(_CONCERN)]
    if raised:
        raised.sort(key=lambda r: (_concern(r.status), -(r.score or 0)))
        names = ", ".join(f"{r.name} ({r.score:g}, {r.status})" for r in raised[:3])
        bio = (
            f"\n\n**Your Bio-AI report**\nYour Bio-AI report also shows raised risk estimates for {names}. "
            "These are risk estimates, not diagnoses."
        )
        # Keep the next step last.
        text = f"{body}{bio}{sep}{closing}" if sep else text + bio
    return text


def explain_bio_risk(risk, *, comparison=None, markers: list[BloodMarker] | None = None) -> str:
    """One Bio-AI score: its level, what it estimates, how it moved and what sits behind it."""
    if getattr(risk, "score", None) is None:
        return f"Your Bio-AI report doesn't include a {risk.name.lower()} score."
    meaning, theme = _risk_info(risk.code, risk.name)
    status = (risk.status or "").strip()
    raised = _concern(status) < len(_CONCERN)
    level = f", which is in the {status.lower()} range" if status else ""
    parts = [f"Your {risk.name} score is {risk.score:g}{level}. This score reflects {meaning}."]
    if not raised and status:
        parts.append("That means it is not raised at the moment.")
    if (comparison is not None and getattr(comparison, "previous_value", None) is not None
            and getattr(comparison, "current_value", None) is not None):
        prev, curr = comparison.previous_value, comparison.current_value
        direction = str(getattr(comparison, "direction", "") or "").lower()
        if direction in {"increased", "up", "higher", "worsened"}:
            parts.append(f"It has gone up from {prev:g} to {curr:g} since your previous Bio-AI assessment.")
        elif direction in {"decreased", "down", "lower", "improved"}:
            parts.append(f"It has come down from {prev:g} to {curr:g} since your previous Bio-AI assessment.")
        else:
            parts.append(f"It is about the same as in your previous Bio-AI assessment ({prev:g}).")
    factors = [f for f in (getattr(risk, "contributing_factors", None) or []) if f]
    if factors:
        parts.append("The main things feeding into it are " + ", ".join(factors[:4]) + ".")
    linked = [m for m in (markers or []) if _out_of_range(m) and theme and _theme(m).code == theme]
    if linked:
        parts.append(
            "In your blood report, " + ", ".join(_value(m) for m in _dedupe(linked)[:4])
            + (" are" if len(linked) > 1 else " is") + " outside the range, which fits with this score."
        )
    if raised and (getattr(risk, "lifestyle_contribution", None) or 0) >= 40:
        parts.append("A large part of this score is linked to lifestyle, so changes to diet, activity and sleep can bring it down.")
    closing = "Bio-AI scores are risk estimates, not a medical diagnosis."
    details = parts[1:]
    if len(details) < 2:
        return " ".join([*parts, closing])
    return f"{parts[0]}\n\n{_bullets(details)}\n\n{closing}"


def explain_metabolic_age(metabolic_age: float) -> str:
    return (
        f"Your metabolic age is {metabolic_age:g}, from your latest Bio-AI report. "
        "Metabolic age compares how your body is working (things like blood sugar, blood fats and "
        "body composition) with what is typical at different ages. A metabolic age below your actual "
        "age is a good sign, and one above it suggests there is room to improve, usually through "
        "diet, activity and sleep. It is an estimate, not a diagnosis."
    )


def explain_bio_comparison(comparisons: list, names: dict[str, str]) -> str:
    """Two Bio-AI assessments side by side: what got worse, what improved, what held."""
    rows = [c for c in comparisons if c.previous_value is not None and c.current_value is not None]
    if not rows:
        return (
            "I only have one Bio-AI assessment for you, so there is nothing to compare yet. "
            "Once you have another assessment, I can show how your scores have changed."
        )
    up = [c for c in rows if c.current_value > c.previous_value]
    down = [c for c in rows if c.current_value < c.previous_value]
    same = [c for c in rows if c.current_value == c.previous_value]

    def line(c) -> str:
        name = names.get(str(c.topic)) or str(c.topic).replace("_", " ").capitalize()
        return f"{name} {c.previous_value:g} → {c.current_value:g}"

    prev_date = next((c.previous_date for c in rows if c.previous_date), None)
    curr_date = next((c.current_date for c in rows if c.current_date), None)
    when = ""
    if prev_date and curr_date and prev_date != curr_date:
        when = f" between {prev_date:%d %b %Y} and {curr_date:%d %b %Y}"
    parts = [f"Here is how your Bio-AI scores changed{when}. A higher score means a higher estimated risk."]
    if up:
        up.sort(key=lambda c: c.previous_value - c.current_value)
        parts.append("**Went up (higher risk):** " + "; ".join(line(c) for c in up) + ".")
    if down:
        down.sort(key=lambda c: c.current_value - c.previous_value)
        parts.append("**Came down (lower risk):** " + "; ".join(line(c) for c in down) + ".")
    if same:
        parts.append("**No change:** " + "; ".join(line(c) for c in same) + ".")
    if up:
        top = names.get(str(up[0].topic)) or str(up[0].topic)
        parts.append(
            f"**What to do next:** the biggest rise is in {top.lower()}, so that is the one to talk "
            "through with your doctor first. These are risk estimates, not diagnoses."
        )
    else:
        parts.append("None of your scores went up, which is a good sign. These are risk estimates, not diagnoses.")
    return "\n\n".join(parts)


_SECTION = re.compile(
    r"\*\*(?:What to do next|Looking good|Went up|Came down|No change|Your Bio-AI report)\b"
    r"|only have one Bio-AI assessment for you"
    r"|which is (?:higher|lower) than the normal range|which is within the normal range"
    r"|most important result to look at|ratio is \d"
)


def is_explained(text: str | None) -> bool:
    """True for text written by this module, which already states the values that matter."""
    return bool(_SECTION.search(text or ""))


def explain_missing_topic(codes: list[str]) -> str:
    """The question is about tests the latest report does not have."""
    from app.pipeline.lab_parameters import display_name_for, is_lab_key

    names = [display_name_for(code) for code in codes if is_lab_key(code)]
    listed = f" ({', '.join(dict.fromkeys(names[:4]))})" if names else ""
    return (
        f"Your latest blood report doesn't include the tests for this{listed}, so I can't tell from "
        "your results. If you'd like to check, ask your doctor whether these tests are worth adding "
        "to your next blood test."
    )


# Question-aware answers -------------------------------------------------------
# The same results answer different questions: "what does it mean", "what can I eat",
# "why is it low", "should I take a supplement". These keep to the tests asked about
# and answer the actual question. Advice stays general lifestyle guidance; doses and
# medicines are always left to the doctor.

_THEME_WORDS = {
    "sugar": ("sugar", "diabet", "glucose", "hba1c", "a1c"),
    "lipids": ("cholesterol", "cholestrol", "lipid", "triglycer", "ldl", "hdl"),
    "iron": ("anaem", "anem", "irondeficien", "ironlevel", "haemoglobin", "hemoglobin"),
    "kidney": ("kidney", "renal"),
    "liver": ("liver",),
    "thyroid": ("thyroid",),
}
_PATTERN_ASK = re.compile(
    r"deficien|anaem|anem|ratio|pattern|connect|together|in common|relat|overall|picture|review", re.I
)

_KIND = (
    ("supplement", re.compile(r"\b(supplements?|tablets?|pills?|capsules?|injections?|should i take)\b", re.I)),
    ("foods", re.compile(r"\b(foods?|eat|eating|diet|meals?|drink)\b", re.I)),
    ("actions", re.compile(
        r"\b(what (?:can|should) i do|how (?:can|do|should) i|improve|lower|reduce|raise|increase|"
        r"bring (?:it|them) (?:down|up)|fix|get (?:it|them) (?:down|up)|tips)\b", re.I)),
    ("causes", re.compile(r"\b(why|causes?|reasons?|what makes)\b", re.I)),
    ("top", re.compile(r"\b(most important|biggest|main (?:issue|concern|problem)|top priority|worst|first)\b", re.I)),
)


def question_kind(message: str | None) -> str | None:
    for kind, pattern in _KIND:
        if pattern.search(message or ""):
            return kind
    return None


# Advice is keyed by marker family: (foods, steps, common causes, supplement note).
_ADVICE = {
    "vitamin_d": (
        "oily fish such as salmon, sardines and mackerel, egg yolks, and milk, curd or cereals fortified with vitamin D. "
        "Food alone rarely fixes a low level, because most vitamin D is made in the skin from sunlight",
        "get some midday sun on your arms and face on most days (about 15 to 30 minutes, without burning), "
        "and add vitamin D foods where you can",
        "too little sun on the skin (spending most of the day indoors, covering most of the skin, sunscreen), darker skin, higher body weight, "
        "and, less often, gut, liver or kidney conditions that affect absorption",
        "Vitamin D supplements are often prescribed for a level this low, but the dose depends on your level "
        "and health, so please ask your doctor before starting one",
    ),
    "b12": (
        "eggs, milk, curd, paneer and cheese, fish, chicken and meat, and cereals fortified with B12. "
        "B12 comes almost only from animal foods, so vegetarians and especially vegans often need fortified foods",
        "include a B12 food every day, and if you are vegetarian or vegan, look for fortified foods",
        "a vegetarian or vegan diet, long-term use of metformin or acid-reducing medicines, "
        "and stomach or gut conditions that affect absorption",
        "B12 is often given as tablets or injections when it is low, but your doctor should check the cause "
        "and choose the right form and dose",
    ),
    "iron": (
        "lean red meat, chicken, fish and eggs, plus lentils, beans, chana, rajma, green leafy vegetables, "
        "and iron-fortified cereals. Having vitamin C (lemon, amla, oranges, tomatoes) with these meals helps "
        "absorption, while tea or coffee with meals reduces it",
        "eat iron-rich foods daily with a vitamin C source, keep tea and coffee away from meals, "
        "and see your doctor so the cause can be found",
        "too little iron in the diet, blood loss (for example heavy periods or bleeding in the gut), "
        "pregnancy, and conditions that reduce absorption",
        "Please don't start iron supplements on your own. Your doctor should first confirm low iron and find "
        "the cause, then choose the dose, because iron tablets can upset the stomach and too much iron is harmful",
    ),
    "lipids": (
        "more fibre from oats, beans, lentils, fruit and vegetables, nuts and seeds, and fish. "
        "Cut back on ghee, butter, fried and processed foods, sweets and sugary drinks",
        "aim for about 150 minutes a week of activity such as brisk walking, swap saturated fats for "
        "unsaturated ones (nuts, seeds, mustard or olive oil), cut sugary drinks, refined carbs and alcohol "
        "(these raise triglycerides most), and lose some weight if you are carrying extra",
        "diet, low activity, extra body weight, alcohol, family history, and sometimes thyroid or blood-sugar problems",
        "Whether you need cholesterol medicine depends on your overall heart risk, which your doctor can work out",
    ),
    "sugar": (
        "whole grains instead of white rice, maida and white bread, plenty of vegetables, dal and other "
        "protein at each meal, and fewer sweets, juices and sugary drinks",
        "cut sugary drinks and sweets, swap refined carbs for whole grains, keep portions moderate, aim for "
        "about 150 minutes a week of activity (a 10 to 15 minute walk after meals helps), sleep well, and lose "
        "some weight if you are carrying extra",
        "diet high in sugar and refined carbs, low activity, extra weight around the waist, family history, "
        "poor sleep and stress",
        "Any blood-sugar medicine is your doctor's decision",
    ),
    "liver": (
        "plenty of vegetables, whole grains and lean protein, with fewer fried foods, sweets and sugary drinks",
        "limit or avoid alcohol, keep to a healthy weight, cut sugar and fried food, and stay active",
        "alcohol, extra body weight, high blood sugar or triglycerides, some medicines, and infections",
        "Please check with your doctor before taking any supplement, because some can strain the liver",
    ),
    "kidney": (
        "a balanced diet with less salt and processed food",
        "drink enough water, keep salt down, avoid regular use of painkillers like ibuprofen without advice, "
        "and keep blood pressure and blood sugar in check",
        "dehydration, high protein intake or intense exercise before the test, muscle mass, and some medicines",
        "Please check with your doctor before taking supplements, as kidneys clear many of them",
    ),
}


def _advice_key(marker: BloodMarker) -> str | None:
    text = _norm(marker.key) + _norm(marker.name)
    if "vitamind" in text:
        return "vitamin_d"
    if "b12" in text or "cobalamin" in text:
        return "b12"
    code = _theme(marker).code
    return code if code in _ADVICE else None


def _focus(markers: list[BloodMarker], message: str | None) -> list[BloodMarker]:
    """Keep to the tests the question is about."""
    text = _norm(message)
    if not text or _PATTERN_ASK.search(message or ""):
        return markers
    words = f" {re.sub(r'[^a-z0-9]+', ' ', (message or '').lower())} "

    def said(term: str) -> bool:
        term = re.sub(r"[^a-z0-9]+", " ", term.lower()).strip()
        return len(term) >= 2 and f" {term} " in words

    named = [
        m for m in markers
        if said(m.key.replace("_", " ")) or said(m.name)
        or ("vitamind" in text and "vitamind" in _norm(m.name))
        or ("triglycer" in text and "triglycer" in _norm(m.name))
    ]
    if named:
        # An iron test is read with the member's other out-of-range iron results.
        if any(_theme(m).code == "iron" for m in named):
            pool = [
                m for m in markers
                if m not in named and _theme(m).code == "iron" and _out_of_range(m)
            ]
            ferritin = [m for m in pool if "ferritin" in _norm(m.name + m.key)]
            named += (ferritin or pool)[:1]
        return named
    for code, words in _THEME_WORDS.items():
        if any(word in text for word in words):
            themed = [m for m in markers if _theme(m).code == code]
            if themed:
                return themed
    return markers


def _ratio_answer(markers: list[BloodMarker]) -> str | None:
    def find(*words):
        return next((m for m in markers if m.value and any(w == _norm(m.key) or w in _norm(m.name) for w in words)), None)

    hdl = find("hdl")
    ldl = find("ldl")
    total = next((m for m in markers if m.value and _norm(m.key) in {"cholesterol", "totalcholesterol"}
                  or "cholesteroltotal" in _norm(m.name) or "totalcholesterol" in _norm(m.name)), None)
    if not hdl:
        return None
    parts = []
    if total:
        parts.append(f"Your total cholesterol to HDL ratio is {total.value / hdl.value:.1f} "
                     f"(total {total.value:g} ÷ HDL {hdl.value:g}).")
    if ldl:
        parts.append(f"Your LDL to HDL ratio is {ldl.value / hdl.value:.1f} (LDL {ldl.value:g} ÷ HDL {hdl.value:g}).")
    if not parts:
        return None
    parts.append(
        "A lower ratio is better: it means more \"good\" HDL compared with the cholesterol that can build up "
        "in blood vessels. Your doctor can tell you what target suits you, based on your overall heart risk."
    )
    return " ".join(parts)


def _top_answer(markers: list[BloodMarker]) -> str | None:
    flagged = _dedupe([m for m in markers if _out_of_range(m)])
    if not flagged:
        return None
    notes = clinical_notes(flagged)
    if notes:
        order = [t.code for t in _THEMES]
        notes.sort(key=lambda n: (not n.urgent, order.index(_theme(n.marker).code) if _theme(n.marker).code in order else len(order)))
        lead = notes[0].marker
        reason = notes[0].text
    else:
        order = [t.code for t in _THEMES]
        flagged.sort(key=lambda m: order.index(_theme(m).code) if _theme(m).code in order else len(order))
        lead = flagged[0]
        reason = _about(lead) or ""
    others = [m for m in flagged if m is not lead][:3]
    text = f"The most important result to look at is your {_value(lead)}. {reason}".strip()
    if others:
        text += " After that: " + ", ".join(_value(m) for m in others) + "."
    return text + " It is worth going through these with your doctor."


def answer_markers(markers: list[BloodMarker], message: str | None = None) -> str:
    """Answer a question about specific results: meaning, foods, steps, causes or supplements."""
    usable = _dedupe([m for m in markers if m.value is not None])
    if not usable:
        return ""
    kind = question_kind(message)
    if re.search(r"\bratio\b", message or "", re.I):
        ratio = _ratio_answer(usable)
        if ratio:
            return ratio
    if kind == "top":
        top = _top_answer(usable)
        if top:
            return top
    focus = _focus(usable, message)
    if kind in {"foods", "actions", "causes", "supplement"}:
        flagged = [m for m in focus if _out_of_range(m)] or focus
        parts = [" ".join(_status_sentence(m) for m in flagged)]
        seen: set[str] = set()
        for marker in flagged:
            key = _advice_key(marker)
            if not key or key in seen:
                continue
            seen.add(key)
            foods, steps, causes, supplement = _ADVICE[key]
            if kind == "foods":
                parts.append(f"Foods that help: {foods}.")
                parts.append(f"Beyond food: {steps}.")
            elif kind == "actions":
                parts.append(f"What helps most: {steps}.")
                parts.append(f"Foods to lean on: {foods}.")
            elif kind == "causes":
                parts.append(f"Common causes include {causes}. Your doctor can work out which applies to you.")
            if kind == "supplement" or (kind in {"foods", "actions"} and supplement and "doctor" in supplement
                                        and key in {"vitamin_d", "b12", "iron"}):
                parts.append(supplement + ".")
        if len(parts) == 1:
            parts.append(explain_markers(flagged))
            return "\n\n".join(p for p in parts if p)
        opening, advice = parts[0], [p for p in parts[1:] if p]
        closing = "Recheck the test after about three months of changes to see how it is moving." if kind != "supplement" else ""
        return "\n\n".join(p for p in (opening, _bullets(advice), closing) if p)
    return explain_markers(focus)


def related_blood_results(risk, markers: list[BloodMarker]) -> list[str]:
    """Out-of-range blood results behind a Bio-AI score ("HbA1c 9.1% (high)")."""
    _meaning, theme = _risk_info(getattr(risk, "code", "") or "", getattr(risk, "name", "") or "")
    if not theme:
        return []
    linked = [m for m in markers if _out_of_range(m) and _theme(m).code == theme]
    return [_value(m) for m in _dedupe(linked)[:4]]
