"""Organ and category education for the 15 health categories. Pending clinical review.

The one-line short descriptions are card copy shown on overview screens and stay as they are.
"""

C = {}

C["heart_circulation"] = dict(
    body=[
        "Your heart is a muscle about the size of a fist that pumps blood around your body all day and night.",
        "Arteries carry oxygen-rich blood out to every organ, and veins bring it back.",
        "Cholesterol and other fats travel in the blood inside tiny particles. Some kinds, such as LDL, can slowly build up in artery walls and narrow them.",
        "Narrowed arteries can reduce blood flow to the heart or brain, which is what causes most heart attacks and strokes.",
    ],
    why=["Heart disease is a leading cause of death in India and often starts years before any symptom.", "Blood fat tests, blood pressure and blood sugar together show how much strain your arteries are under."],
    keep=["Regular movement, not smoking, meals built around vegetables, dal, whole grains and nuts, and modest salt protect your heart and arteries."],
    risk=["Blood pressure, blood sugar, cholesterol and smoking add to each other, so improving any one of them lowers overall risk.", "Heart disease in a parent or sibling at a young age is worth telling your doctor about."],
    myth=["Feeling fit does not mean arteries are healthy. High cholesterol and blood pressure usually cause no symptoms."],
)
C["liver_health"] = dict(
    body=[
        "Your liver sits under your right ribs and is one of the busiest organs in the body.",
        "Blood from your stomach and intestines passes through it, so it is the first stop for nutrients, medicines and alcohol.",
        "It stores energy, makes proteins such as albumin, clears old red cells and breaks down medicines and alcohol.",
        "It also makes bile, a fluid that drains through small tubes called bile ducts into the gut to help digest fat.",
    ],
    why=["Liver problems are often silent until late, so blood tests are one of the few early signs.", "About one in three Indian adults has fat in the liver, often without being overweight."],
    keep=["Little or no alcohol, few sugary drinks and sweets, regular activity and a steady weight protect the liver.", "Ask before starting herbal, weight-loss or bodybuilding supplements, because some can injure the liver."],
    risk=["Losing 3 to 5% of body weight can reduce liver fat, and activity helps even when weight does not change."],
    myth=["Normal liver tests do not rule out fatty liver.", "Fatty liver is not only caused by alcohol."],
)
C["blood_sugar_metabolism"] = dict(
    body=[
        "When you eat, carbohydrates such as rice, roti and sugar are broken down into glucose, a sugar your cells use for energy.",
        "Insulin, a hormone from the pancreas, moves glucose from the blood into muscle, fat and liver cells.",
        "When these cells stop responding well to insulin, called insulin resistance, the pancreas has to make more, and blood sugar slowly rises.",
        "Over years this can lead to prediabetes and type 2 diabetes.",
    ],
    why=["Indians tend to develop type 2 diabetes at younger ages and lower weights than many other groups.", "Prediabetes is common and usually silent, and lifestyle change can delay or prevent diabetes."],
    keep=["Regular activity, meals built around vegetables, dal and whole grains, few sugary drinks and enough sleep help keep blood sugar healthy."],
    risk=["Waist size matters even if your weight looks normal.", "If a parent or sibling has diabetes, regular blood sugar checks are worth it."],
    myth=["You do not have to eat a lot of sweets to get diabetes. Genes, waist size, inactivity and refined grains all play a part."],
)
C["kidney_urinary"] = dict(
    body=[
        "You have two kidneys, each about the size of a fist, in your lower back.",
        "Together they filter all your blood many times a day through about a million tiny filters, removing waste and extra water as urine.",
        "They also balance salt, potassium and acid in the blood, help control blood pressure and help make red blood cells and keep bones strong.",
        "Urine tests show what the kidneys let through, and blood tests such as creatinine and eGFR show how well they filter.",
    ],
    why=["Kidney disease is often silent until a lot of function is lost.", "Diabetes and high blood pressure are the commonest causes, so people with either need regular kidney checks."],
    keep=["Keep blood pressure and blood sugar healthy, drink water through the day and use painkillers such as ibuprofen only as advised."],
    risk=["Keeping salt low helps blood pressure and protects the kidney filters."],
    myth=["Drinking huge amounts of water does not clean the kidneys. Enough to keep urine pale yellow is what helps."],
)
C["blood_iron"] = dict(
    body=[
        "Blood is made of red cells, white cells and platelets floating in a fluid called plasma.",
        "Red cells carry oxygen using haemoglobin, which needs iron, vitamin B12 and folate to be made.",
        "White cells fight infection, and platelets help blood clot.",
        "All three are made in the bone marrow, the soft tissue inside bones, and a blood count shows how many of each you have.",
    ],
    why=["Anaemia is very common in India, especially in women, and can cause tiredness and breathlessness.", "Blood counts also help spot infection, inflammation and, less often, bone marrow problems."],
    keep=["Iron-rich foods such as dal, chana, green leafy vegetables, eggs or meat, eaten with a vitamin C food, help keep iron up."],
    risk=["Heavy periods are the commonest reason women run low on iron and are worth mentioning to a doctor."],
    myth=["Not every anaemia is from low iron. Thalassaemia trait, B12 shortage and long-term illness are common causes too."],
)
C["vitamins_nutrition"] = dict(
    body=[
        "Vitamins and minerals are nutrients your body needs in small amounts to make blood, keep nerves and bones healthy and run chemical reactions.",
        "Most come from food; vitamin D is mainly made in your skin in sunlight.",
        "Some are stored in the body for months, such as B12 and vitamin D, so shortages build slowly.",
        "Blood tests show the level in your blood, which does not always match stores inside cells.",
    ],
    why=["Low vitamin D and low B12 are very common in India, including in people who eat well.", "Shortages can cause tiredness, weak bones, tingling or anaemia."],
    keep=["A varied diet with vegetables, fruit, dal, whole grains and dairy or eggs if you eat them, plus some daylight, covers most needs."],
    myth=["More is not always better. Very large doses of vitamin D, for example, can cause nausea, kidney stones and kidney damage."],
)
C["thyroid_health"] = dict(
    body=[
        "Your thyroid is a small butterfly-shaped gland at the front of your neck.",
        "It makes hormones, T4 and T3, that set how fast your body uses energy, affecting heart rate, temperature, weight, mood and periods.",
        "The pituitary gland in the brain controls it by releasing TSH: more TSH when thyroid hormone is low, less when it is high.",
        "The thyroid needs iodine, which iodised salt provides.",
    ],
    why=["Thyroid conditions are common, especially in women, and are easy to test for and treat.", "Untreated thyroid problems in pregnancy can affect the baby, so testing in pregnancy matters."],
    keep=["Thyroid conditions are not usually prevented by habits. Using iodised salt and having tests when you have symptoms, a family history or are pregnant is what helps."],
    myth=["Thyroid problems are not only about weight. Tiredness, feeling cold or hot, hair, mood and periods can all change."],
)
C["immunity_inflammation"] = dict(
    body=[
        "Your immune system defends you against germs using white blood cells, antibodies and chemical signals.",
        "Inflammation is part of that defence: blood flow, white cells and repair proteins rush to an injured or infected area.",
        "Short-term inflammation helps healing, but low-grade inflammation that lasts for months is linked with heart disease and other long-term conditions.",
        "Tests such as CRP and ESR show that inflammation may be present, but not where or why.",
    ],
    why=["Inflammation markers help doctors follow infections and inflammatory conditions such as arthritis.", "A raised marker during a recent cold is common and usually settles."],
    keep=["Regular activity, not smoking, a healthy weight and a diet rich in vegetables, fruit, pulses and whole grains are linked with lower long-term inflammation."],
    myth=["A normal ESR or CRP does not rule out every infection or inflammation."],
)
C["hormonal_health"] = dict(
    body=[
        "Hormones are chemical messengers released into the blood that control growth, periods, fertility, energy and stress responses.",
        "The pituitary gland in the brain directs many of them, including the ovaries, testes, thyroid and adrenal glands.",
        "In women, LH and FSH from the pituitary drive the monthly cycle; in men, they drive testosterone and sperm production.",
        "Hormone levels change with the time of day, the menstrual cycle, age and pregnancy, so timing matters for many tests.",
    ],
    why=["Hormone tests help explain irregular periods, fertility problems, acne or extra hair, and low energy.", "PCOS is one of the most common hormone conditions in Indian women."],
    keep=["Regular sleep, activity and a steady weight support hormone balance."],
    myth=["One hormone result rarely gives a diagnosis on its own; timing and symptoms matter."],
)
C["bone_mineral"] = dict(
    body=[
        "Bones are living tissue that is constantly broken down and rebuilt.",
        "They store most of the body's calcium and phosphate and release them when the blood needs more.",
        "Vitamin D helps your gut absorb calcium, and parathyroid hormone keeps blood calcium steady.",
        "Bone strength builds until about age 30, then slowly falls, faster in women after menopause.",
    ],
    why=["Blood calcium shows the body's balance, not bone strength; a bone density scan measures strength."],
    keep=["Calcium from milk, curd, ragi, sesame and green vegetables, enough vitamin D, and weight-bearing activity such as walking and strength exercise support bones."],
    myth=["A normal blood calcium does not mean bones are strong."],
)
C["cancer_related"] = dict(
    body=[
        "Some cells, including some cancer cells, release substances into the blood that labs can measure, called tumour markers.",
        "Many non-cancer conditions, such as inflammation, infection and liver disease, raise these markers too.",
        "They are mainly used to follow people already being treated for certain cancers, and sometimes to help investigate symptoms.",
    ],
    why=["A raised tumour marker needs a doctor's assessment, but it does not mean cancer on its own."],
    keep=None,
    risk=["Not smoking, limiting alcohol, staying active, a healthy weight and recommended cancer screening, such as cervical and breast checks, lower cancer risk more than marker tests do."],
    myth=["Tumour markers are not screening tests for most people. A normal result does not rule out cancer."],
)
C["sleep_recovery"] = dict(
    body=[
        "During sleep your body repairs tissue, balances hormones and stores memories.",
        "Short or poor sleep affects appetite hormones, blood sugar control, mood and blood pressure.",
        "Blood tests do not measure sleep directly; questionnaire answers about sleep give context.",
    ],
    why=["Enough sleep is part of the lifestyle that may help prevent insulin resistance and supports overall health."],
    keep=["A regular bedtime and wake time, a dark quiet room and less screen time before bed help sleep."],
    myth=["Catching up on sleep at weekends does not fully undo short sleep during the week."],
)
C["allergy"] = dict(
    body=[
        "Your immune system usually ignores harmless things such as food, dust and pollen.",
        "In allergy, it makes an antibody called IgE against one of these, which can trigger sneezing, itching, rashes, swelling or wheezing on contact.",
        "Having IgE to something, called sensitisation, does not always mean you react to it.",
    ],
    why=["Allergy tests help a doctor link symptoms to triggers, but they are read with what actually happens when you are exposed."],
    keep=None,
    myth=["A positive allergy test is not proof of allergy, and cutting foods based on tests alone can harm nutrition, especially in children."],
)
C["other_unmapped"] = dict(
    body=["These are results on your report that do not fit one of the main health areas, such as sample details or lab notes."],
    why=["They are shown so nothing on your report is hidden, but most need no action on their own."],
    keep=None,
    myth=[],
)
C["other_risks"] = dict(
    body=["These are Bio-AI predictions that do not fit one of the main health areas."],
    why=["Like every Bio-AI result, they are estimates from a prediction model, not diagnoses."],
    keep=None,
    myth=[],
)
