"""Education upgrade for vitamin and thyroid results. Pending clinical review."""

_THY_KEEP = [
    "If you take thyroid tablets, take them the same way every day, usually on an empty stomach, and have levels checked as advised.",
]

X = {}

X["WB-036"] = dict(
    fx=[
        ("Vegetarian or vegan diet", "B12 occurs naturally only in animal foods, so diets with little or no dairy, eggs, fish or meat supply less."),
        ("Stomach or gut absorption", "B12 needs stomach acid and a protein called intrinsic factor to be absorbed; some stomach and gut conditions, including pernicious anaemia, block this."),
        ("Metformin", "This diabetes medicine can lower B12 absorption over years."),
        ("Long-term acid-reducing tablets", "Less stomach acid means less B12 is freed from food."),
        ("Age", "Absorption falls with age, even when the diet contains enough."),
        ("Supplements", "B12 tablets or injections raise the level, often above the printed range, which is generally not harmful."),
    ],
    fix=dict(
        body=[
            "B12 comes naturally from animal foods such as milk, curd, paneer, eggs, fish and meat. Fortified foods, such as some breakfast cereals and plant milks, also supply it.",
            "Your stomach needs acid and a protein called intrinsic factor to absorb B12.",
            "Your liver stores B12, so a shortage can take months or years to show.",
        ],
        high="Higher B12 is usually from supplements, injections or fortified foods and is not known to be harmful. A high level without supplements is uncommon and can sometimes go with liver, kidney or blood conditions, so it is worth mentioning to a doctor.",
        low="Lower B12 often comes from eating few animal foods, as in vegetarian and vegan diets. Poor absorption in the stomach or gut, and medicines such as metformin or long-term acid-reducing tablets, can also lower it, so people who eat meat can be low too. A low B12 is one possible reason for large red cells or anaemia, but other causes need checking too.",
    ),
    keep=["Dairy and eggs every day, if you eat them, or fortified foods if you are vegan, keep B12 supply steady."],
    risk=["If you take metformin or long-term acid-reducing tablets, ask whether your B12 should be checked regularly."],
    myth=[
        "Eating dairy every day does not guarantee enough B12. Absorption problems can cause a shortage whatever you eat.",
        "A B12 shortage is not the only reason red cells become large. Folate, alcohol, thyroid and liver problems can do it too, so a doctor checks the cause.",
    ],
)

X["WB-037"] = dict(
    fix=dict(high="Higher vitamin D is almost always caused by taking too much from supplements. NIH describes levels above 50 ng/mL as too high; very large doses can cause nausea, kidney stones and kidney damage."),
    fx=[
        ("Sunlight exposure", "Skin makes vitamin D in sunlight; working indoors, covering most skin and pollution reduce this."),
        ("Skin colour", "Darker skin makes vitamin D more slowly from the same sunlight."),
        ("Body weight", "Vitamin D is stored in body fat, so people with more body fat tend to have lower blood levels."),
        ("Diet", "Few Indian foods are rich in vitamin D; eggs, oily fish and fortified milk or cereals help a little."),
        ("Supplements", "Tablets or sachets raise the level; very large doses for a long time can push it too high."),
        ("Gut, liver or kidney conditions", "The gut absorbs vitamin D and the liver and kidneys activate it, so conditions of these organs lower it."),
    ],
    keep=["Some regular daylight on uncovered arms and face, when safe for your skin, plus vitamin D foods that suit your diet, help keep levels up."],
    myth=[
        "Living in a sunny country does not prevent low vitamin D. Low levels are very common in India.",
        "More is not better. NIH describes levels above 50 ng/mL as too high, and very large doses can cause nausea, kidney stones and kidney damage.",
    ],
    thr="NIH describes 20 ng/mL or above as adequate for most people and below 12 ng/mL as too low. Many labs print a higher lower limit, such as 30 ng/mL, so a result between 20 and 30 may be flagged low; a doctor decides whether treatment is needed.",
)

X["WB-038"] = dict(
    fx=[
        ("Fruit and vegetable intake", "Vitamin C comes from fruit and vegetables such as amla, guava, citrus and capsicum; the body cannot store much."),
        ("Smoking", "Smoking uses up vitamin C faster, so smokers need more."),
        ("Alcohol", "Heavy drinking lowers intake and absorption."),
        ("Illness or inflammation", "Illness lowers the blood level as the body uses more."),
        ("Supplements", "Tablets raise the level for some hours."),
        ("Recent meals", "A vitamin C-rich meal shortly before the test can raise the result."),
    ],
    keep=["Fresh fruit and vegetables every day, such as amla, guava, oranges and capsicum, keep vitamin C topped up. Cooking for a long time destroys some of it."],
    myth=["Vitamin C supplements have not been shown to prevent colds in most people."],
)

_THY_FX = ("Thyroid gland activity", "An overactive gland makes more thyroid hormone and an underactive one makes less, often from autoimmune thyroid disease.")

X["WB-039"] = dict(
    fx=[
        _THY_FX,
        ("Illness or fasting", "During serious illness or fasting the body makes less active T3 to save energy, without a thyroid problem."),
        ("Pregnancy", "Pregnancy hormones raise the proteins that carry thyroid hormone, which changes total T3."),
        ("Some medicines", "Steroids, beta blockers and some heart medicines can change T3."),
    ],
    keep=_THY_KEEP,
    myth=["T3 is not usually the first test for thyroid problems. TSH is, and T3 helps mainly when an overactive thyroid is suspected."],
)

X["WB-040"] = dict(
    fx=[
        _THY_FX,
        ("Pregnancy", "Pregnancy raises the proteins that carry T4, which changes total T4."),
        ("Thyroid tablets", "Levothyroxine is T4, so the dose and timing of the last tablet affect the result."),
        ("Some medicines and supplements such as biotin", "High-dose biotin, common in hair, skin and nail supplements, can interfere with many thyroid tests and give falsely high or low results, so tell the lab or doctor if you take it."),
    ],
    keep=_THY_KEEP,
    myth=["Thyroid problems are not only about weight. Tiredness, feeling cold or hot, periods, mood and heart rate can all change."],
)

X["WB-041"] = dict(
    fx=[
        ("Thyroid gland activity", "TSH comes from the pituitary gland in the brain. When the thyroid is underactive, TSH rises to push it; when overactive, TSH falls."),
        ("Thyroid tablets", "Too low a dose leaves TSH high and too high a dose pushes it low."),
        ("Recent illness", "TSH can be briefly high or low during and after an illness."),
        ("Pregnancy", "TSH is normally lower in early pregnancy, so pregnancy-specific ranges are used."),
        ("Some medicines", "Steroids, some heart medicines and others can change TSH."),
        ("Biotin supplements", "Biotin can interfere with the lab test and give misleading results."),
    ],
    keep=_THY_KEEP,
    myth=["A slightly high TSH does not always need tablets. Mild rises are often rechecked, especially after an illness."],
    thr="TSH ranges differ between labs, and doctors use different targets in pregnancy and in older adults, so a result just outside the printed range is judged with your symptoms and T4.",
)
