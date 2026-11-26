"""Revision 2.3.1 content: blood sugar, inflammation and muscle enzymes. Pending clinical review."""

C = {}

_SUGAR_SUPPORT = [
    "Fill half your plate with vegetables and pair rice or roti with dal, curd, paneer, eggs or other protein. This slows how quickly sugar enters your blood.",
    "Swap sugary drinks, sweets and refined flour for water, whole fruit and whole grains like millets or brown rice. These cause smaller sugar spikes.",
    "Take a 10 to 15 minute walk after main meals. Working muscles pull sugar out of the blood.",
    "Aim for 7 to 8 hours of sleep. Poor sleep makes it harder for insulin to work.",
]
_SUGAR_SEEK = [
    "Talk to a doctor if your blood sugar results are above range, so they can check for prediabetes or diabetes. Both are common and often have no symptoms.",
    "Seek care promptly if you have extreme thirst, passing a lot of urine, unexplained weight loss, blurred vision, or feel shaky, sweaty or confused from low sugar.",
]

C["WB-067"] = dict(
    d="Fasting blood sugar measures the amount of glucose, a type of sugar, in your blood after at least 8 hours without food.",
    body=[
        "Food is broken down into glucose, which your cells use for energy.",
        "Insulin, a hormone from the pancreas, moves glucose from the blood into your cells.",
        "Overnight, your liver releases stored glucose to keep levels steady, so a fasting sample shows your baseline.",
    ],
    why=["It is one of the main tests used to check for prediabetes and diabetes."],
    high="A higher fasting sugar can mean your body is not responding well to insulin or is not making enough. It can also rise if you ate before the test, were unwell or stressed, or take some medicines such as steroids.",
    low="A lower fasting sugar can follow a long fast, heavy exercise, alcohol or diabetes medicines. It can cause shakiness, sweating and confusion.",
    normal="Your fasting sugar is inside the lab's range, suggesting your body is keeping blood sugar steady overnight.",
    factors=["Food before the test", "Insulin resistance", "Body weight", "Illness or stress", "Steroids and some other medicines", "Sleep"],
    life=["Diet, activity, sleep and body weight all affect how well insulin works and so your fasting sugar."],
    support=_SUGAR_SUPPORT,
    seek=_SUGAR_SEEK,
    limits=["One fasting sugar result is a snapshot. Diabetes is usually confirmed with a repeat test or HbA1c."],
    q=dict(
        high=["Should I be concerned about my fasting sugar?", "Do I have diabetes or prediabetes?", "What can I eat to help my blood sugar?"],
        low=["Why is my fasting sugar low?", "What are the signs of low blood sugar?"],
        normal=["Can I have diabetes with a normal fasting sugar?", "How can I keep my blood sugar healthy?"],
    ),
)

C["WB-068"] = dict(
    d="HbA1c shows your average blood sugar over roughly the past two to three months. It measures how much sugar has stuck to the haemoglobin in your red blood cells.",
    body=[
        "Glucose in your blood naturally sticks to haemoglobin, the oxygen-carrying protein in red cells.",
        "The more sugar in your blood over time, the more sticks.",
        "Red cells live about three months, so HbA1c gives a longer view than a single sugar test.",
    ],
    why=["HbA1c is used to diagnose prediabetes and diabetes and to see how well diabetes is controlled."],
    high="A higher HbA1c means your blood sugar has been running higher over recent months, which can mean prediabetes or diabetes. It is linked with a higher risk of heart, kidney, eye and nerve problems over time.",
    low="A lower HbA1c is usually good. A very low value can come from frequent low sugar, or from conditions that shorten red cell life, such as recent blood loss.",
    normal="Your HbA1c is inside the lab's range, suggesting your average blood sugar has been healthy over the past few months.",
    factors=["Average blood sugar", "Diet and activity", "Body weight", "Anaemia or low iron", "Recent blood loss or transfusion", "Inherited haemoglobin variants"],
    life=["Regular activity, fewer sugary and refined foods, good sleep and a healthy weight can all bring HbA1c down over time."],
    support=_SUGAR_SUPPORT,
    seek=_SUGAR_SEEK,
    limits=["HbA1c can be misleading in people with anaemia, low iron, kidney disease, recent blood loss or some inherited haemoglobin types."],
    q=dict(
        high=["What does my HbA1c say about my diabetes risk?", "How can I lower my HbA1c?", "How long does it take for HbA1c to improve?"],
        low=["Is a low HbA1c a problem?"],
        normal=["Why can HbA1c differ from my fasting sugar?", "How often should I check my HbA1c?"],
    ),
)

C["WB-069"] = dict(
    d="Fasting insulin measures how much insulin is in your blood after not eating. Insulin is the hormone that moves sugar from your blood into your cells.",
    body=[
        "Your pancreas releases insulin even between meals to keep sugar steady.",
        "If your cells respond poorly to insulin, the pancreas makes more to keep sugar normal. This is called insulin resistance.",
        "So insulin can rise years before blood sugar does.",
    ],
    why=["A high fasting insulin can be an early sign of insulin resistance, which raises the chance of type 2 diabetes, fatty liver and PCOS."],
    high="A higher fasting insulin often means your body needs more insulin to keep sugar normal, a sign of insulin resistance. Extra weight around the waist, low activity and poor sleep are common contributors.",
    low="A lower fasting insulin with normal sugar is usually fine. Low insulin with high sugar can mean the pancreas is not making enough.",
    normal="Your fasting insulin is inside the lab's range.",
    factors=["Insulin resistance", "Waist size and body weight", "Physical activity", "Sleep", "Food before the test", "Some medicines"],
    life=["Regular activity, especially strength exercise, losing extra weight around the waist and better sleep help your cells respond to insulin."],
    support=_SUGAR_SUPPORT,
    seek=["Talk to a doctor if fasting insulin is high, especially with high sugar, a large waist, irregular periods or signs of fatty liver."],
    limits=["Insulin tests are not standardised between labs, and one result cannot diagnose insulin resistance."],
    q=dict(
        high=["Does high insulin mean I have insulin resistance?", "Can I improve insulin resistance with lifestyle?", "Is high insulin linked with PCOS?"],
        low=["Is a low fasting insulin a problem?"],
        normal=["What does insulin do in my body?", "Can my insulin be high even if my sugar is normal?"],
    ),
)

C["WB-070"] = dict(
    d="Average blood sugar is a blood sugar value that represents an average over time, rather than one moment. Many labs calculate it from your HbA1c.",
    body=[
        "Blood sugar rises and falls through the day.",
        "When worked out from HbA1c, this value turns your HbA1c into everyday glucose units, covering roughly the past two to three months.",
    ],
    why=["It makes HbA1c easier to compare with day-to-day sugar readings."],
    factors=["HbA1c", "Calculation method"],
    life=None, support=[],
    seek=["Use your HbA1c result and discuss it with a doctor if it is above range."],
    limits=["The lab's calculation method is not confirmed, so this value is shown for information only. Your HbA1c is the result to rely on."],
    not_applicable={"lifestyle_relationships": "Derived from HbA1c; covered by the HbA1c entry.", "practical_guidance": "Derived value; guidance sits on HbA1c and fasting sugar.", "interpretation": "Method unconfirmed, so high or low wording is not given."},
    assay="The way this lab calculates average blood sugar is not confirmed, so CURA does not label it high or low. Look at your HbA1c, which this value is usually based on.",
    q=dict(assay_unconfirmed=["Is this average calculated from my HbA1c?", "Which result should I rely on, HbA1c or average sugar?"]),
)

C["WB-092"] = dict(
    d="Homocysteine is a substance your body makes when it breaks down protein. Vitamins B12, B6 and folate help clear it.",
    body=[
        "Homocysteine forms naturally when your body processes an amino acid called methionine.",
        "B vitamins turn it into other useful substances.",
        "When these vitamins are low, homocysteine can build up.",
    ],
    why=["High homocysteine often points to low B12 or folate, and is linked with a higher risk of heart disease and blood clots."],
    high="A higher homocysteine most often reflects low vitamin B12 or folate, which is common in vegetarian diets. Kidney problems, an underactive thyroid, smoking and some inherited patterns can also raise it.",
    low="A low homocysteine is not a concern.",
    normal="Your homocysteine is inside the lab's range.",
    factors=["Vitamin B12 and folate levels", "Vegetarian diet", "Kidney function", "Smoking", "Inherited patterns", "Some medicines"],
    life=["Folate from leafy greens, pulses and citrus, and B12 from dairy, eggs, fish or meat help keep homocysteine low."],
    support=[
        "Eat leafy greens, dal and beans regularly. They are rich in folate, which helps clear homocysteine.",
        "Include B12 sources such as milk, curd, eggs or fish, or B12-fortified foods if you are vegan.",
        "If you smoke, ask for help to stop. Smoking raises homocysteine and harms blood vessels.",
    ],
    seek=["Talk to a doctor if homocysteine is high, so they can check B12, folate and kidney function before any treatment."],
    limits=["Lowering homocysteine with vitamins has not been shown to reduce heart disease in most studies. It is mainly a pointer to check B vitamins."],
    q=dict(
        high=["Why is my homocysteine high?", "Is high homocysteine linked with low B12?", "Does high homocysteine affect my heart?"],
        low=["Is low homocysteine a problem?"],
        normal=["What does homocysteine tell me?"],
    ),
)

C["WB-093"] = dict(
    d="High-sensitivity C-reactive protein, or hs-CRP, measures small amounts of CRP, a protein your liver makes when there is inflammation in the body.",
    body=[
        "When your body is fighting infection or injury, the liver releases more CRP.",
        "The high-sensitivity test picks up low levels linked with long-term, low-grade inflammation.",
        "Low-grade inflammation in blood vessels plays a part in heart disease.",
    ],
    why=["hs-CRP is used as one extra guide to heart risk, alongside cholesterol and blood pressure."],
    high="A higher hs-CRP can mean low-grade inflammation linked with higher heart risk. It also rises with any recent infection, injury, gum disease, extra weight or smoking, so a high value is usually repeated after a few weeks when you are well.",
    low="A low hs-CRP suggests little inflammation, which is favourable for heart health.",
    normal="Your hs-CRP is inside the lab's range, suggesting no marked inflammation at the moment.",
    factors=["Recent infection or injury", "Body weight", "Smoking", "Physical activity", "Ongoing inflammatory conditions"],
    life=["Extra body fat, smoking, inactivity and poor sleep are linked with higher CRP. Regular activity and a diet with plenty of plant foods are linked with lower levels."],
    support=[
        "Stay active on most days, such as brisk walking. Regular activity is linked with lower inflammation.",
        "Eat plenty of vegetables, fruit, pulses, nuts and whole grains. These eating patterns are linked with lower CRP.",
        "If you smoke, ask for help to stop. Smoking keeps inflammation raised.",
    ],
    seek=["Talk to a doctor if hs-CRP stays high on a repeat test, or if it is very high, as that usually means an infection or inflammatory condition needs checking."],
    limits=["hs-CRP shows inflammation but not where it is or why. A recent cold can raise it."],
    q=dict(
        high=["Why is my hs-CRP high?", "Does a high CRP mean I have heart disease?", "Can a recent cold raise my CRP?"],
        low=["Is a low hs-CRP good for my heart?"],
        normal=["What does hs-CRP tell me about inflammation?", "How is CRP different from ESR?"],
    ),
)

C["WB-117"] = dict(
    d="Creatine kinase, or CK, is an enzyme found mainly in your muscles, including the heart. It leaks into the blood when muscles are strained or damaged.",
    body=["Muscles use CK to make energy quickly.", "After hard exercise or an injury, some CK passes into the blood.", "People with more muscle naturally have higher CK."],
    why=["CK helps check for muscle damage, including side effects of some medicines such as statins."],
    high="A higher CK most often follows hard or unfamiliar exercise, a fall or injury, or an injection into muscle. It can also be raised by some medicines, an underactive thyroid or muscle conditions.",
    low="A low CK is usually not a concern and often reflects less muscle.",
    normal="Your CK is inside the lab's range, suggesting no sign of muscle strain from this test.",
    factors=["Recent exercise", "Muscle injury", "Muscle mass", "Statins and some other medicines", "Thyroid function"],
    life=["Heavy or new exercise in the days before the test can raise CK for up to a week."],
    support=["Avoid very hard workouts for two to three days before a repeat test. Exercise raises CK and can hide the real picture."],
    seek=["See a doctor promptly if CK is high with muscle pain or weakness, dark or cola-coloured urine, or if you take a statin and develop muscle aches."],
    limits=["CK does not show which muscle is affected. Heart muscle damage is checked with different tests."],
    q=dict(high=["Can exercise raise my CK?", "Should I be concerned about my high CK?", "Can my cholesterol medicine raise CK?"], low=["Is a low CK a problem?"], normal=["What does CK tell me about my muscles?"]),
)

C["WB-118"] = dict(
    d="Lactate dehydrogenase, or LDH, is an enzyme found in almost every tissue in your body. It rises in the blood when cells are damaged.",
    body=["LDH helps cells turn sugar into energy.", "It is found in the heart, liver, muscles, kidneys, lungs and blood cells.", "When cells are injured, LDH leaks out."],
    why=["LDH is a general sign of tissue damage and is sometimes used to follow certain conditions."],
    high="A higher LDH means some tissue damage somewhere, for example from muscle injury, hard exercise, liver problems, red blood cell breakdown, infection or, less often, some cancers. A falsely high value is common if red cells burst during sampling.",
    low="A low LDH is not a concern.",
    normal="Your LDH is inside the lab's range.",
    factors=["Tissue injury", "Hard exercise", "Red blood cell breakdown", "Sample handling", "Liver conditions"],
    life=None, support=[],
    seek=["Talk to a doctor if LDH is high, especially with other abnormal results, tiredness, yellow eyes or unexplained weight loss."],
    limits=["LDH is non-specific and cannot show which tissue is affected."],
    not_applicable={"lifestyle_relationships": "General tissue damage marker; no established lifestyle effect apart from exercise before testing.", "practical_guidance": "A raised LDH needs a doctor to find the source."},
    q=dict(high=["Why is my LDH high?", "Can exercise or the blood sample raise LDH?"], low=["Is a low LDH a problem?"], normal=["What does LDH tell me?"]),
)

C["WB-330"] = dict(
    d="Total IgE measures the overall amount of immunoglobulin E (IgE), a type of antibody involved in allergies, in your blood. It does not show what you are allergic to.",
    body=["Antibodies are proteins your immune system makes to recognise threats.", "IgE is the antibody type that triggers allergy symptoms like sneezing, itching and wheezing.", "It also helps fight some parasites."],
    why=["Total IgE can support a picture of allergic conditions, but specific allergy tests are needed to find triggers."],
    high="A higher total IgE is common with allergies, asthma, eczema and hay fever. Parasite infections and, less often, some immune conditions can also raise it.",
    low="A low or normal total IgE does not rule out allergy to a particular substance.",
    normal="Your total IgE is inside the lab's range. You can still be allergic to specific things.",
    factors=["Allergic conditions", "Parasite infections", "Age", "Some immune conditions"],
    life=None,
    support=["Keep a simple diary of symptoms and possible triggers, such as dust, pollen, pets or foods. It helps a doctor decide which specific tests are worth doing."],
    seek=["See a doctor about persistent sneezing, wheezing, rashes or reactions to food. Seek emergency care for swelling of the lips or throat, trouble breathing or fainting."],
    limits=["Total IgE cannot identify a specific allergen, and normal levels do not rule out allergy."],
    not_applicable={"lifestyle_relationships": "Total IgE reflects immune activity; no diet or habit is known to change it reliably."},
    q=dict(
        high=["Does a high IgE mean I have allergies?", "Can worms raise my IgE?", "Which allergy tests should I do next?"],
        low=["Can I still have an allergy with low IgE?"],
        normal=["How is total IgE different from individual allergy tests?"],
    ),
)
