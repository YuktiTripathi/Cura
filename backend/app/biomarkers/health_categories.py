"""Shared health categories for blood biomarkers and Bio-AI risks.

The blood registry (`systems.py`, 121 tests with one primary system each) and the risk registry
(`risk_registry_v1.json`) already use the same ids, so a category is the join of the two on that id.
A biomarker has exactly one primary category, so no count is ever repeated. Related markers listed
as secondary systems support the interpretation and are never counted again.

Wearable signals can join later by naming a category id here; nothing else has to change.
"""

from __future__ import annotations

from dataclasses import dataclass

REGISTRY_VERSION = "unified-1"

MY_HEALTH_INTRO = "There's a story behind every health result. Let's explore yours."


@dataclass(frozen=True)
class HealthCategory:
    id: str
    name: str
    icon: str  # a line icon name the frontend knows
    topic: str  # the area in everyday words, for questions and button labels
    about: str  # one plain sentence, used only if the model has not written one
    action_label: str  # the one primary action on the card
    order: int
    description: str = ""  # the short everyday line shown on the overview card


CATEGORIES: tuple[HealthCategory, ...] = (
    HealthCategory("heart_circulation", "Heart & Circulation", "heart", "heart health", "Your heart pumps blood around your body, and your blood vessels carry it.", "Explore my heart health", 10, "Every heartbeat tells a story. Discover what yours can reveal."),
    HealthCategory("liver_health", "Liver Health", "liver", "liver health", "Your liver helps clean your blood, process food and medicines, and remove waste.", "Explore my liver health", 20, "From the food you eat to the energy you use, your liver does more than you think."),
    HealthCategory("blood_sugar_metabolism", "Blood Sugar & Metabolism", "drops", "metabolic health", "Your body turns food into sugar for energy, and keeps the amount in your blood balanced.", "Explore my metabolic health", 30, "From your morning meals to your daily energy, there's more going on inside than you think."),
    HealthCategory("kidney_urinary", "Kidney & Urinary Health", "kidney", "kidney health", "Your kidneys filter waste from your blood and keep your salts and fluids in balance.", "Explore my kidney health", 40, "Your body's natural cleaning system works around the clock to keep things in balance."),
    HealthCategory("blood_iron", "Blood & Iron", "blood", "blood health", "Your blood cells and iron carry oxygen around your body.", "Explore my blood health", 50, "Feeling energetic or running low? Your blood may hold some clues."),
    HealthCategory("vitamins_nutrition", "Vitamins & Nutrition", "sun", "nutrition", "Vitamins and minerals help your body run well every day.", "Explore my nutrition", 60, "Small nutrients make a big difference to the way you feel every day."),
    HealthCategory("thyroid_health", "Thyroid Health", "thyroid", "thyroid health", "Your thyroid makes hormones that set your energy level and metabolism.", "Explore my thyroid health", 70, "A tiny gland with a big influence on your energy, weight and everyday well-being."),
    HealthCategory("immunity_inflammation", "Immunity & Inflammation", "shield", "immune health", "Your immune system defends your body, and inflammation is one way it responds.", "Explore my immune health", 80, "Your body's natural defence system is always at work. Get to know it better."),
    HealthCategory("hormonal_health", "Hormonal & Reproductive Health", "hormone", "hormone health", "Hormones are chemical messengers that shape energy, mood, growth and reproduction.", "Explore my hormone health", 90, "Your hormones play a bigger role in your periods, skin and overall health than you might realise."),
    HealthCategory("bone_mineral", "Bone & Joint Health", "bone", "bone health", "Minerals keep your bones and muscles strong.", "Explore my bone health", 100, "The health of your bones and joints that help you stay strong and move comfortably."),
    HealthCategory("cancer_related", "Cancer-Related Markers", "marker", "these markers", "Doctors may use these markers alongside other tests. On their own they are not a screening.", "Explore these markers", 110, "Markers doctors may use alongside other tests. On their own they are not a screening."),
    HealthCategory("sleep_recovery", "Sleep & Recovery", "moon", "recovery", "Some results are linked to stress and recovery.", "Explore my recovery results", 120, "How well your body recovers from stress and rest."),
    HealthCategory("allergy", "Allergy & Sensitivity", "shield", "sensitivities", "", "Explore my sensitivities", 130, "How your body reacts to certain foods, substances and things around you."),
    HealthCategory("other_unmapped", "Other Health Results", "marker", "these results", "Results that are not grouped into a health category yet.", "Explore these results", 900, "There's more to your health story. Explore the other pieces of the puzzle."),
    HealthCategory("other_risks", "Other predicted risks", "marker", "these risks", "Predicted risks that are not grouped into a health category yet.", "Explore these risks", 910, "Additional predicted risks that provide more information about your health."),
)

_BY_ID = {c.id: c for c in CATEGORIES}


def category(category_id: str) -> HealthCategory | None:
    return _BY_ID.get(category_id)


def category_for(category_id: str) -> HealthCategory:
    return _BY_ID.get(category_id) or HealthCategory(category_id, category_id.replace("_", " ").title(), "marker", "these results", "", "Explore these results", 999)
