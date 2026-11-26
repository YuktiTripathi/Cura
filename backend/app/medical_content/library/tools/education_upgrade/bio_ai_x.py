"""Education upgrade for the 12 Bio-AI assessments, including PCOS and metabolic age. Pending clinical review.

MetSights has published its general input set but not the formula, weights, prediction target, time
horizon or reference population for any score. Nothing here describes those, attributes a score to an
input, or turns a risk band into a probability.
"""

RISK_MEANING = [
    "Your Bio-AI result is a risk band from MetSights' prediction model, built from your blood results and other information such as lifestyle answers.",
    "It is not a diagnosis and does not measure the condition directly.",
    "MetSights has not published the exact outcome each score predicts, over what time, or how the band is calculated, so CURA does not turn it into a percentage chance.",
]
FACTORS_NOTE = "These are known general influences on this area of health. They are not confirmed inputs to, or reasons for, your own score."

_CARDIO_KEEP = ["Keep doing what protects your heart and blood vessels: regular movement, not smoking, meals built around vegetables, dal and whole grains, and checks of blood pressure, sugar and cholesterol at the interval your doctor suggests."]

X = {}

X["cardiac_health"] = dict(
    fx=[
        ("Blood pressure", "High pressure strains artery walls and the heart muscle over years."),
        ("Cholesterol", "LDL and other plaque-forming particles build up in artery walls and narrow them."),
        ("Blood sugar and diabetes", "High blood sugar damages blood vessels and speeds up artery narrowing."),
        ("Smoking", "Smoking damages artery linings, makes blood more likely to clot and lowers HDL."),
        ("Physical activity", "Regular activity lowers blood pressure, improves cholesterol and helps the heart pump efficiently."),
        ("Family history", "Heart disease in a parent or sibling at a young age raises your own risk."),
    ],
    keep=_CARDIO_KEEP,
)
X["dyslipidemia"] = dict(
    fx=[
        ("Foods high in saturated fat", "Ghee, butter, cream, fatty meat and fried snacks lead the liver to clear less LDL."),
        ("Sugar and refined carbohydrates", "Extra sugar and refined flour are turned into triglycerides by the liver."),
        ("Body weight", "Extra weight, especially around the waist, raises triglycerides and lowers HDL."),
        ("Physical activity", "Activity raises HDL and lowers triglycerides."),
        ("Inherited patterns", "Genes shape how your liver makes and clears cholesterol."),
        ("Thyroid function", "An underactive thyroid slows cholesterol clearance."),
    ],
    keep=_CARDIO_KEEP,
)
X["hypertension"] = dict(
    fx=[
        ("Salt intake", "Salt makes the body hold extra water, which raises pressure; pickles, papad, namkeen and processed foods add a lot."),
        ("Body weight", "Extra weight makes the heart pump harder."),
        ("Physical activity", "Regular activity lowers blood pressure over weeks."),
        ("Alcohol", "Regular drinking raises blood pressure."),
        ("Stress and sleep", "Ongoing stress and poor sleep keep pressure-raising hormones high."),
        ("Age and family history", "Arteries stiffen with age, and high blood pressure runs in families."),
    ],
    keep=["Keep salt modest, stay active and check your blood pressure from time to time, because high blood pressure usually causes no symptoms."],
)
X["nafld"] = dict(
    fx=[
        ("Body weight, especially around the waist", "Extra fat around the waist goes with fat building up in the liver."),
        ("Insulin resistance or diabetes", "When insulin works poorly, the liver stores more fat."),
        ("Sugar and refined carbohydrates", "NIDDK advises limiting simple sugars and sugary drinks, because extra sugar is turned into fat."),
        ("Alcohol", "Alcohol adds to liver fat and strain; drinking above low amounts changes how doctors classify fatty liver."),
        ("Physical activity", "Activity reduces liver fat even when weight does not change."),
        ("High triglycerides", "High blood triglycerides often go with fat in the liver."),
    ],
    fix=dict(
        short="Fatty liver means extra fat has built up inside your liver cells. The common form is now called MASLD, metabolic dysfunction-associated steatotic liver disease, which replaced the older name NAFLD.",
        body=[
            "Your liver stores some fat, but too much can build up when the body takes in more energy than it uses.",
            "Doctors call it MASLD when there is fat in the liver together with at least one metabolic risk factor, such as a large waist or extra weight, high blood sugar, high blood pressure, high triglycerides or low HDL, and little or no alcohol.",
            "When fat in the liver comes with inflammation and liver cell damage, it is called MASH, which replaced the older name NASH. Over years this can lead to scarring.",
        ],
        support=[
            "Cut down on sugary drinks, sweets and maida-based snacks. NIDDK advises limiting simple sugars for fatty liver.",
            "Aim for gradual weight loss if you carry extra weight. Losing 3 to 5% of body weight can reduce liver fat, and larger losses help more.",
            "Stay physically active. Activity helps the liver even when weight does not change.",
            "Keep alcohol low or avoid it. Alcohol adds extra strain on a fatty liver.",
        ],
        misconceptions=[
            "Fatty liver is not only caused by alcohol. The common form, MASLD, is linked with metabolism, not drinking.",
            "Normal liver enzymes do not rule out fatty liver.",
            "Slim people can have fatty liver too, and this is common in South Asians.",
            "A Healthy band on this prediction does not cancel abnormal liver results you have actually measured.",
        ],
    ),
    keep=["Keep sugary drinks and alcohol low, stay active and keep a steady waist size. These protect the liver even when results look good."],
)
X["type_2_diabetes"] = dict(
    fx=[
        ("Body weight, especially around the waist", "Fat around the waist makes insulin work less well; Indians develop diabetes at lower weights than many groups."),
        ("Physical activity", "Not being active is a risk factor for insulin resistance; activity helps manage blood sugar."),
        ("Diet", "Sugary drinks, sweets and large portions of refined grains raise blood sugar and, over time, the load on insulin."),
        ("Sleep", "Enough sleep is part of the lifestyle that may help prevent insulin resistance."),
        ("Family history", "Diabetes in a parent or sibling raises your risk."),
        ("Age", "Risk rises with age, though in India it often starts in the thirties and forties."),
    ],
    fix=dict(misconceptions_add=["A low predicted risk and normal blood sugar results do not rule out diabetes for good; risk changes with age and weight, so checks continue."]),
    keep=["Regular activity, meals built around vegetables, dal and whole grains, few sugary drinks and a steady waist size help keep blood sugar healthy."],
)
X["obesity"] = dict(
    fx=[
        ("Diet and portion size", "Eating more energy than you use, especially from sugary, fried and refined foods, is stored as fat."),
        ("Physical activity", "Activity uses energy and protects muscle, which helps weight and blood sugar."),
        ("Sleep", "Short sleep is linked with weight gain, partly through appetite hormones."),
        ("Stress", "Ongoing stress can change eating patterns and fat storage."),
        ("Some medicines", "Steroids, some antidepressants and some diabetes medicines can cause weight gain."),
        ("Hormone conditions such as an underactive thyroid", "An underactive thyroid slows metabolism a little and can add some weight."),
    ],
    keep=["Regular movement, regular meals with plenty of vegetables and protein, and enough sleep help keep weight steady."],
)
_THY_KEEP = ["Thyroid conditions are not usually prevented by habits. Knowing the symptoms and having thyroid tests when advised, especially in pregnancy or with a family history, is what helps."]
X["thyroid"] = dict(
    fx=[
        ("Autoimmune thyroid conditions", "The immune system can attack the thyroid, making it underactive (Hashimoto) or overactive (Graves)."),
        ("Family history", "Thyroid conditions often run in families."),
        ("Iodine intake", "The thyroid needs iodine; iodised salt prevents deficiency, while very large amounts can also upset the gland."),
        ("Pregnancy and after childbirth", "Pregnancy changes thyroid needs, and some women develop thyroid inflammation after childbirth."),
        ("Some medicines", "Medicines such as lithium and amiodarone can affect the thyroid."),
        ("Age and sex", "Thyroid conditions are much more common in women and become more common with age."),
    ],
    keep=_THY_KEEP,
)
X["hypothyroidism"] = dict(
    fx=[
        ("Autoimmune thyroiditis (Hashimoto)", "The commonest cause: the immune system slowly damages the thyroid so it makes less hormone."),
        ("Iodine deficiency", "Without enough iodine the gland cannot make hormone; iodised salt prevents this."),
        ("Thyroid surgery or radioactive iodine", "Treatments that remove or reduce the thyroid can leave it underactive."),
        ("Some medicines", "Lithium and amiodarone can make the thyroid underactive."),
        ("After childbirth", "Thyroid inflammation after childbirth can cause a temporary or lasting underactive phase."),
        ("Age and sex", "Women and older adults are affected far more often."),
    ],
    keep=_THY_KEEP,
)
X["hyperthyroidism"] = dict(
    fx=[
        ("Graves disease", "The commonest cause: antibodies stimulate the thyroid to make too much hormone."),
        ("Thyroid nodules", "Lumps in the thyroid can make hormone on their own."),
        ("Too much thyroid medicine", "Taking more levothyroxine than you need has the same effect as an overactive gland."),
        ("Thyroid inflammation", "Inflammation, including after childbirth or a viral illness, can release stored hormone for a while."),
        ("Large amounts of iodine", "Iodine-rich medicines or contrast dye can trigger an overactive thyroid in some people."),
        ("Sex and family history", "It is more common in women and runs in families."),
    ],
    keep=_THY_KEEP,
)
X["pcos"] = dict(
    fx=[
        ("Family history", "PCOS runs in families, and a mother or sister with PCOS or type 2 diabetes raises the chance."),
        ("Insulin resistance", "High insulin pushes the ovaries to make more androgens, which disturbs ovulation."),
        ("Body weight", "Extra weight worsens insulin resistance and symptoms, though PCOS also occurs at normal weight."),
        ("Physical activity", "Activity helps the body respond to insulin, which can ease symptoms."),
        ("Sleep and stress", "Poor sleep and ongoing stress can worsen insulin resistance and cycle regularity."),
    ],
    fix=dict(misconceptions_add=["A predicted PCOS band is not a diagnosis. Only a doctor can diagnose PCOS, using your periods, signs of high androgens, blood tests and sometimes an ultrasound."]),
    keep=["Regular activity, meals that keep blood sugar steady and regular sleep support hormone and insulin balance, whatever your weight."],
)
X["oxidative_stress"] = dict(
    fx=[
        ("Eating habits", "Vegetables, fruit, pulses and whole grains provide antioxidants that support the body's own protection."),
        ("Sleep", "Sleep supports the body's repair processes."),
        ("Physical activity", "Exercise makes some free radicals, but regular moderate activity strengthens the body's own protective systems."),
        ("Smoking", "Smoke is one of the strongest outside sources of free radicals."),
        ("Ongoing stress", "Long-term stress is linked with more oxidative strain."),
        ("Alcohol", "Breaking down alcohol produces reactive molecules in the liver."),
        ("Air pollution and strong sunlight", "Pollution and ultraviolet light create free radicals in the lungs and skin."),
    ],
    fix=dict(
        risk_meaning=RISK_MEANING + ["Routine blood tests do not measure oxidative stress directly, and MetSights has not said exactly what this score predicts."],
        misconceptions=[
            "A normal blood report does not contradict a higher oxidative stress band, because routine blood tests do not measure it.",
            "Antioxidant supplements have not been shown to prevent disease, and high-dose beta-carotene raised lung cancer risk in smokers.",
            "This band is not a measurement of damage to your cells.",
        ],
    ),
    keep=["Not smoking, a varied diet with plenty of vegetables, fruit and dal, regular moderate activity and enough sleep support the body's own protective systems."],
)
X["metabolic_age"] = dict(
    fx=[
        ("Physical activity", "Activity helps the body use sugar and fats well."),
        ("Eating habits", "Meals built around vegetables, pulses and whole grains support steadier blood sugar and blood fats."),
        ("Sleep", "Enough sleep is part of the lifestyle that may help prevent insulin resistance."),
        ("Body weight", "Extra weight, especially around the waist, makes insulin and fat handling less efficient."),
        ("Blood sugar and blood fats", "These are the measured parts of metabolic health that blood tests can show."),
    ],
    fix=dict(
        short="Metabolic age is a Bio-AI estimate that MetSights presents as an age, to sum up parts of your metabolic health such as how your body handles sugar and fats. MetSights has not published how the number is calculated or what it is compared against.",
        body=[
            "Metabolic health is how well your body turns food into energy, keeps blood sugar steady and handles fats.",
            "Your actual age is how many years you have lived. Metabolic age is an estimate based on health information, not a count of birthdays.",
            "MetSights has not shared the formula, the weight given to each input or the group it compares you with, so the gap between your metabolic age and your real age cannot be read as a precise measure of anything.",
        ],
        support=[
            "Move regularly and include some strength exercise. Activity helps your body use sugar and fats.",
            "Base meals on vegetables, pulses, whole grains and protein, with fewer sugary and fried foods. This supports steadier blood sugar and blood fats.",
            "Keep a regular sleep routine. Enough sleep is part of the lifestyle that may help prevent insulin resistance.",
        ],
        misconceptions_add=["Your measured results, such as HbA1c, fasting sugar and cholesterol, are a more reliable guide to where to focus than the metabolic age number."],
    ),
    keep=["Regular activity, balanced meals and enough sleep support metabolic health. Your measured results show where attention will help most."],
)
