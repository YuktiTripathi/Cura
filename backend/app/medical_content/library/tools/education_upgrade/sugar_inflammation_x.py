"""Education upgrade for blood sugar, inflammation, muscle and IgE results. Pending clinical review."""

SUGAR_SUPPORT = [
    "Fill half your plate with vegetables and pair rice or roti with dal, curd, paneer, eggs or other protein. This slows how quickly sugar enters your blood.",
    "Swap sugary drinks, sweets and refined flour for water, whole fruit and whole grains like millets or brown rice. These cause smaller sugar spikes.",
    "Take a 10 to 15 minute walk after main meals. Physical activity helps your body manage blood sugar, and sugar after a walk is often lower than before.",
    "Aim for enough sleep. A healthy weight, regular activity and enough sleep are part of the lifestyle that may help prevent insulin resistance.",
]
_SUGAR_KEEP = [
    "Keep up what helps: regular activity, meals built around vegetables, dal and whole grains, and few sugary drinks.",
    "A good result now does not mean blood sugar stays the same. Risk rises with age, weight gain and family history, so check again at the interval your doctor suggests.",
]
_SUGAR_RISK = [
    "Indians tend to develop type 2 diabetes at a younger age and lower weight than many other groups, so waist size and activity matter even if you are not overweight.",
    "Lifestyle changes can delay or prevent type 2 diabetes in people with prediabetes.",
]
_NOT_RULED_OUT = "A result below the diabetes threshold on one test does not rule out diabetes on its own. Doctors confirm or exclude it with repeat or additional tests, especially if you have symptoms or risk factors."

X = {}

X["WB-067"] = dict(
    fx=[
        ("Food before the test", "Eating or drinking anything other than water within 8 hours raises the result, so it no longer shows a true fasting level."),
        ("Insulin resistance", "When cells respond poorly to insulin, the liver releases more glucose overnight and fasting sugar creeps up."),
        ("Body weight", "Extra weight, especially around the waist, makes insulin work less well."),
        ("Illness or stress", "Stress hormones during illness or strain push blood sugar up."),
        ("Steroids and some other medicines", "Steroids, some water tablets and some antipsychotic medicines raise blood sugar."),
        ("Sleep", "Enough sleep is part of the lifestyle that may help prevent insulin resistance."),
    ],
    fix=dict(support=SUGAR_SUPPORT, normal="Your fasting sugar is inside the healthy range, suggesting your body kept blood sugar steady overnight. " + _NOT_RULED_OUT),
    keep=_SUGAR_KEEP,
    risk=_SUGAR_RISK,
    myth=["Feeling well does not mean blood sugar is normal. Prediabetes and early diabetes usually cause no symptoms."],
    thr="The lab range for fasting sugar is not the same as the diagnostic thresholds. Doctors use 100 to 125 mg/dL for prediabetes and 126 mg/dL or above for diabetes, and usually confirm diabetes with a second test.",
)

X["WB-068"] = dict(
    fx=[
        ("Average blood sugar", "The higher your blood sugar over the past two to three months, the more sugar sticks to haemoglobin."),
        ("Diet and activity", "Meals low in sugary and refined foods and regular activity lower average sugar over months."),
        ("Body weight", "Extra weight makes insulin work less well, raising average sugar."),
        ("Very low iron", "Very low iron can make HbA1c read falsely high."),
        ("Recent blood loss or transfusion", "These replace old red cells with new ones, which can make HbA1c read too low."),
        ("Kidney failure", "Kidney failure can make HbA1c read too high or too low."),
        ("Inherited haemoglobin variants", "Some inherited types of haemoglobin, more common in some families, interfere with certain lab methods."),
    ],
    fix=dict(
        support=SUGAR_SUPPORT,
        low="A lower HbA1c is usually not a concern. If you take diabetes medicines, ask your doctor what a low result means for you. Recent blood loss or a transfusion can also make it read low.",
        normal="Your HbA1c is inside the healthy range, so your average blood sugar over the past few months has been healthy. Keep up the habits that support it, because risk can change over time. " + _NOT_RULED_OUT,
        limits=["Very low iron can make HbA1c read falsely high. Recent blood loss, kidney failure and some inherited types of haemoglobin can make it read too high or too low."],
    ),
    keep=_SUGAR_KEEP,
    risk=_SUGAR_RISK,
    myth=[
        "A normal HbA1c does not mean nothing else needs attention. It says nothing about cholesterol, blood pressure, weight or liver fat.",
        "HbA1c is an average. It cannot show sugar spikes after meals or drops in between.",
    ],
    thr="Labs often print 4.0 to 5.6% as the normal range. Doctors use separate diagnostic thresholds: 5.7 to 6.4% suggests prediabetes and 6.5% or above suggests diabetes, usually confirmed with a repeat test.",
)

X["WB-069"] = dict(
    fx=[
        ("Insulin resistance", "When cells respond poorly, the pancreas makes more insulin to keep sugar normal, so fasting insulin rises before sugar does."),
        ("Waist size and body weight", "Fat around the waist is closely linked with insulin resistance."),
        ("Physical activity", "Not being active is a risk factor for insulin resistance; regular activity helps."),
        ("Sleep", "Enough sleep is part of the lifestyle that may help prevent insulin resistance."),
        ("Food before the test", "Eating raises insulin, so a non-fasting sample reads high."),
        ("Some medicines", "Steroids and some others raise insulin; insulin injections make the result unreliable."),
    ],
    fix=dict(support=SUGAR_SUPPORT),
    keep=_SUGAR_KEEP,
    risk=_SUGAR_RISK,
    myth=["There is no agreed cut-off for fasting insulin. It is a clue to insulin resistance, not a diagnosis."],
)

X["WB-070"] = dict(
    fx=[
        ("HbA1c", "This value is usually calculated from HbA1c, so it follows it exactly."),
        ("Calculation method", "Labs use different formulas, and your lab's method is not confirmed."),
    ],
    keep=None,
    myth=["This number is not a measured sugar reading. It is HbA1c converted into sugar units."],
    na=dict(keeping_healthy="A calculated value; HbA1c carries the guidance."),
)

X["WB-092"] = dict(
    fx=[
        ("Vitamin B12 and folate levels", "The body needs B12 and folate to break down homocysteine, so shortages raise it."),
        ("Vegetarian diet", "Lower B12 intake in vegetarian diets often raises homocysteine."),
        ("Kidney function", "The kidneys clear homocysteine, so kidney disease raises it."),
        ("Smoking", "Smoking is linked with higher homocysteine."),
        ("Inherited patterns", "Some people inherit slower homocysteine breakdown."),
        ("Some medicines", "Metformin and some seizure medicines can raise it by lowering B12 or folate."),
    ],
    keep=["Enough B12 from dairy, eggs or fortified foods and folate from green leafy vegetables and dal help keep homocysteine down."],
    myth=["Lowering homocysteine has not been shown to reduce the risk of heart attack or stroke in most cases, though correcting a real B12 shortage still matters."],
)

X["WB-093"] = dict(
    fx=[
        ("Recent infection or injury", "Any infection, even a cold, or an injury raises CRP for a few weeks."),
        ("Body weight", "Body fat releases signals that keep CRP mildly raised."),
        ("Smoking", "Smoking keeps inflammation raised."),
        ("Physical activity", "Regular activity is linked with lower CRP."),
        ("Ongoing inflammatory conditions", "Arthritis, gum disease and other long-term inflammation raise CRP."),
    ],
    keep=["Regular activity, not smoking and a diet rich in vegetables, fruit, pulses and whole grains are linked with lower inflammation."],
    myth=["A high hs-CRP after a recent cold does not reflect heart risk. Doctors repeat it when you are well."],
)

X["WB-117"] = dict(
    fx=[
        ("Recent exercise", "Hard or unaccustomed exercise causes small muscle injuries that release CK for several days."),
        ("Muscle injury", "Injured muscle, for example after a fall or a crush injury, releases CK."),
        ("Muscle mass", "People with more muscle have higher normal levels."),
        ("Statins and some other medicines", "Statins can occasionally irritate muscles and raise CK, especially with muscle pain."),
        ("Thyroid function", "An underactive thyroid can raise CK."),
    ],
    keep=None,
    myth=["A high CK after a heavy workout is common and settles. It is the combination with muscle pain, weakness or dark urine that needs urgent care."],
    na=dict(keeping_healthy="CK follows muscle activity and injury."),
)

X["WB-118"] = dict(
    fx=[
        ("Tissue injury", "LDH sits in almost every cell, so damage to any tissue releases it."),
        ("Hard exercise", "Strenuous exercise can raise LDH for a while."),
        ("Red blood cell breakdown", "Red cells contain LDH, so faster breakdown raises it."),
        ("Sample handling", "If cells burst in the tube, LDH reads falsely high."),
        ("Liver conditions", "Liver damage can raise LDH."),
    ],
    keep=None,
    myth=["A raised LDH does not point to one organ. It shows that some tissue damage may be present and needs other tests to place it."],
    na=dict(keeping_healthy="LDH reflects tissue injury; no habit sets it."),
)

X["WB-330"] = dict(
    fx=[
        ("Allergic conditions", "Asthma, eczema, hay fever and food allergy make the immune system produce more IgE."),
        ("Parasite infections", "Worm infections, common in India, strongly raise total IgE."),
        ("Age", "IgE is higher in childhood and tends to fall with age."),
        ("Some immune conditions", "Rare immune conditions can raise IgE a great deal."),
    ],
    keep=None,
    myth=["A normal total IgE does not rule out allergy, and a high one does not tell you what you are allergic to."],
    na=dict(keeping_healthy="Total IgE reflects immune activity rather than a habit."),
)
