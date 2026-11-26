"""Revision 2.3.1 Bio-AI assessment content. Pending clinical review.

Shared rule for every entry: a Bio-AI result is a provider prediction, not a measurement and not a
diagnosis. Nothing here says which inputs produced a member's score, and a score out of 100 is never
described as a percentage chance.
"""

R = {}

_RISK_MEANING = [
    "Your Bio-AI result here is a predicted risk: an estimate of how likely this pattern may be, based on the information the assessment used.",
    "A predicted risk is not a diagnosis and does not measure the condition directly.",
]
_NOT_CAUSE = "The factors listed are known general influences. They are not confirmed reasons for your own score."

R["cardiac_health"] = dict(
    short="Heart health describes how well your heart and blood vessels are likely to keep working over time. This assessment estimates your risk of heart and blood vessel disease.",
    body=[
        "Your heart pumps blood through a network of blood vessels to every part of your body.",
        "Over years, cholesterol can build up as plaque inside artery walls, and high blood pressure can stiffen them.",
        "Narrowed or blocked arteries can reduce blood flow to the heart or brain, which can lead to a heart attack or stroke.",
    ],
    why=["Heart disease is one of the leading causes of illness and death, and it often develops silently for years.", "Many of its main drivers, such as blood pressure, cholesterol, blood sugar and smoking, can be checked and managed."],
    symptoms=["Early heart disease often has no symptoms.", "Warning signs can include chest pain or pressure, breathlessness, or unusual tiredness on exertion."],
    factors=["Blood pressure", "Cholesterol", "Blood sugar and diabetes", "Smoking", "Physical activity", "Family history"],
    life=["Diets high in salt, saturated fat and processed foods, smoking, inactivity, heavy alcohol use and long-term stress are linked with higher heart risk.", "Diets rich in vegetables, fruit, pulses, whole grains and nuts are linked with lower risk."],
    long_term=["Untreated risk factors can lead to heart attack, stroke, heart failure and kidney disease over time."],
    support=[
        "Aim for about 150 minutes of brisk walking or similar activity each week. Regular movement helps blood pressure, cholesterol and blood sugar.",
        "Cut back on salt, fried foods and packaged snacks, and add vegetables, dal and whole grains. This eating pattern is linked with healthier arteries.",
        "If you smoke, ask for help to stop. Stopping smoking is one of the biggest single steps for heart health.",
        "Know your blood pressure and get it checked regularly. High blood pressure often has no symptoms.",
    ],
    seek=["Call emergency services for chest pain, pressure or tightness, especially with breathlessness, sweating or pain spreading to the arm, jaw or back.", "Talk to a doctor about an increased or very high predicted risk, especially with high blood pressure, diabetes, high cholesterol or early heart disease in your family."],
    misconceptions=["A predicted heart risk does not mean you have heart disease.", "Normal cholesterol does not rule out heart risk, because blood pressure, blood sugar, smoking and family history also matter."],
    limits=["The assessment does not show which of your inputs most affected the score."],
    q=["What does my heart health score mean?", "What does my cholesterol say about my heart health?", "What can I do to protect my heart?", "Should I see a doctor about my heart risk?"],
    reasons={"WB-001": "Shows the full amount of cholesterol in your blood.", "WB-002": "Shows your good cholesterol, which helps clear cholesterol away.", "WB-006": "Shows your bad cholesterol, the main type that builds up in arteries.", "WB-111": "Counts the particles that can carry cholesterol into artery walls."},
    src=["lipids", "life_activity", "life_salt", "life_fat", "life_diet", "who_cvd"],
)

R["dyslipidemia"] = dict(
    short="Cholesterol imbalance, also called dyslipidaemia, means the fats in your blood, such as cholesterol and triglycerides, are at unhealthy levels.",
    body=[
        "Your blood carries fats inside particles such as LDL, HDL and VLDL.",
        "Too much LDL or triglycerides, or too little HDL, makes it easier for fatty plaque to build up in arteries.",
        "The build-up happens slowly and usually without symptoms.",
    ],
    why=["Unhealthy blood fats are one of the main causes of heart attacks and strokes.", "Unhealthy blood fats can be found with a simple blood test and are often improved with lifestyle and, when needed, treatment."],
    symptoms=["Unhealthy blood fats usually cause no symptoms. Very high triglycerides can occasionally cause tummy pain from an inflamed pancreas."],
    factors=["Foods high in saturated fat", "Sugar and refined carbohydrates", "Body weight", "Physical activity", "Inherited patterns", "Thyroid function"],
    life=["Saturated fat and trans fat raise LDL. Sugar, refined flour and alcohol raise triglycerides.", "Regular activity, soluble fibre and unsaturated plant oils support healthier blood fats."],
    long_term=["Over years, it raises the chance of heart attack, stroke and narrowed leg arteries."],
    support=[
        "Use small amounts of plant oils instead of ghee, butter or vanaspati. This lowers the fats that raise LDL.",
        "Eat oats, dal, beans, vegetables and fruit daily. Their fibre helps remove cholesterol.",
        "Cut back on sweets, sugary drinks and alcohol. These raise triglycerides.",
        "Move for about 30 minutes on most days. Activity lowers triglycerides and can raise HDL.",
    ],
    seek=["Talk to a doctor about an increased or very high predicted risk, or if your measured LDL or triglycerides are high. Some people need medicine as well as lifestyle changes."],
    misconceptions=["Slim people can have unhealthy cholesterol too, often because of genes.", "A normal total cholesterol does not mean every blood fat is healthy."],
    limits=["A predicted risk does not replace your measured cholesterol results, which show your actual levels."],
    q=["What does my cholesterol imbalance score mean?", "My cholesterol is normal, so why is my predicted risk high?", "Which foods help balance cholesterol?", "Do I need medicine for my cholesterol?"],
    reasons={"WB-001": "Shows the full amount of cholesterol in your blood.", "WB-002": "Shows your good cholesterol.", "WB-003": "Shows triglycerides, the main fat your body stores for energy.", "WB-004": "Adds up all the cholesterol in particles that can build up in arteries.", "WB-006": "Shows your bad cholesterol."},
    src=["lipids", "life_fat", "life_diet", "life_activity"],
)

R["hypertension"] = dict(
    short="High blood pressure, or hypertension, means blood is pushing too hard against the walls of your arteries for a long time.",
    body=[
        "Blood pressure is the force of blood on artery walls as your heart pumps.",
        "When it stays high, the heart works harder and artery walls become strained and stiff.",
        "Over time this damages blood vessels in the heart, brain, kidneys and eyes.",
    ],
    why=["High blood pressure is very common and is a leading cause of stroke, heart attack and kidney disease.", "High blood pressure usually has no symptoms, so measuring it is the only way to know."],
    symptoms=["Most people have no symptoms.", "Very high blood pressure can cause severe headache, chest pain, breathlessness, vision changes or confusion."],
    factors=["Salt intake", "Body weight", "Physical activity", "Alcohol", "Stress and sleep", "Age and family history"],
    life=["Eating a lot of salt, carrying extra weight, low activity, heavy alcohol use and poor sleep are linked with higher blood pressure.", "Diets rich in vegetables, fruit, pulses and low-fat dairy, with less salt, can lower it."],
    long_term=["Untreated high blood pressure raises the chance of stroke, heart attack, heart failure, kidney disease and vision problems."],
    support=[
        "Use less salt in cooking and at the table, and cut down on pickles, papads, chips and packaged foods. Less salt is one of the most reliable ways to lower blood pressure.",
        "Eat more vegetables, fruit and dal. Their potassium helps balance the effect of salt.",
        "Walk briskly for 30 minutes on most days. Regular activity lowers blood pressure.",
        "Check your blood pressure at a pharmacy, clinic or at home every few months. It is the only way to know your numbers.",
    ],
    seek=["Talk to a doctor if your predicted risk is increased or very high, or if home or clinic readings are often 140/90 or higher.", "Seek emergency care for a very high reading with severe headache, chest pain, weakness on one side, or difficulty speaking."],
    misconceptions=["You cannot tell your blood pressure by how you feel.", "Normal kidney blood tests do not rule out high blood pressure."],
    limits=["This assessment is a prediction. Only a blood pressure measurement can confirm high blood pressure."],
    q=["What does my blood pressure risk mean?", "Do I need to check my blood pressure?", "How much salt is too much?", "Can I lower my blood pressure without medicine?"],
    reasons={"WB-025": "Shows how well your kidneys clear waste. Kidneys and blood pressure affect each other.", "WB-031": "Estimates how much blood your kidneys filter, which high blood pressure can reduce.", "WB-033": "Shows potassium, a mineral that helps balance the effect of salt."},
    src=["life_salt", "life_activity", "life_diet", "who_hypertension"],
)

R["nafld"] = dict(
    short="Fatty liver means extra fat has built up inside your liver cells. The common form linked with metabolic health is now called metabolic dysfunction-associated steatotic liver disease, or MASLD.",
    body=[
        "Your liver stores some fat, but too much can build up when the body takes in more sugar and fat than it can use.",
        "Insulin resistance makes this build-up more likely.",
        "In some people, the extra fat leads to inflammation and, over years, scarring of the liver.",
    ],
    why=["Fatty liver is very common and often silent.", "Fatty liver is closely linked with type 2 diabetes, high triglycerides and heart disease, and early stages can improve with lifestyle change."],
    symptoms=["Most people have no symptoms. Some notice tiredness or discomfort in the upper right tummy."],
    factors=["Body weight, especially around the waist", "Insulin resistance or diabetes", "Sugar and refined carbohydrates", "Alcohol", "Physical activity", "High triglycerides"],
    life=["Sugary drinks, sweets, refined flour and large portions increase liver fat. Alcohol adds further strain.", "Regular activity and gradual weight loss reduce liver fat."],
    long_term=["In some people, it can progress to liver scarring (fibrosis or cirrhosis) and raises the risk of diabetes and heart disease."],
    support=[
        "Cut down on sugary drinks, sweets and maida-based snacks. Extra sugar is turned into fat inside the liver.",
        "Aim for gradual weight loss if you carry extra weight. Losing even a small amount can reduce liver fat.",
        "Be active for at least 150 minutes a week. Exercise reduces liver fat even before weight changes.",
        "Keep alcohol low or avoid it. Alcohol adds extra strain on a fatty liver.",
    ],
    seek=["Talk to a doctor if your predicted risk is increased or very high, or if liver enzymes are raised. They may suggest an ultrasound or other checks.", "Seek care for yellow eyes or skin, swelling of the tummy or legs, or vomiting blood."],
    misconceptions=["You can have fatty liver without drinking alcohol.", "Normal liver enzymes do not rule out fatty liver.", "Slim people can have fatty liver too."],
    limits=["A predicted risk cannot show how much fat is in your liver or whether there is scarring. Imaging or other tests are needed."],
    q=["What does my fatty liver score mean?", "Can I have fatty liver with normal liver tests?", "What can I do to support my liver health?", "Can fatty liver be reversed?"],
    reasons={"WB-017": "Shows an enzyme that rises when liver cells are under strain.", "WB-016": "Shows an enzyme from liver and muscle that rises with liver strain.", "WB-003": "Shows triglycerides, the blood fat that often goes with fatty liver.", "WB-068": "Shows your average blood sugar, which is closely linked with liver fat."},
    src=["life_liver", "niddk_nafld", "liver"],
)

R["type_2_diabetes"] = dict(
    short="Type 2 diabetes is a long-term condition where blood sugar stays too high, because the body does not respond well to insulin or does not make enough of it.",
    body=[
        "Insulin is a hormone that moves sugar from your blood into your cells for energy.",
        "In type 2 diabetes, cells respond less to insulin. This is called insulin resistance.",
        "The pancreas works harder to make more insulin, and over time it may not keep up, so blood sugar rises.",
    ],
    why=["Type 2 diabetes is very common, especially in South Asia, and can develop silently for years.", "Finding risk early allows changes that can delay or prevent it."],
    symptoms=["Early stages often have no symptoms.", "Later signs include thirst, passing a lot of urine, tiredness, blurred vision, slow-healing wounds and frequent infections."],
    factors=["Body weight, especially around the waist", "Physical activity", "Diet", "Sleep", "Family history", "Age"],
    life=["Low activity, extra weight around the waist, diets high in refined carbohydrates and sugary drinks, and poor sleep are linked with higher risk.", "Regular activity and modest weight loss lower the risk."],
    long_term=["Over time, high blood sugar can damage the heart, kidneys, eyes, nerves and feet."],
    support=[
        "Fill half your plate with vegetables and add a protein such as dal, curd, eggs or paneer. This slows the rise in blood sugar after meals.",
        "Choose whole grains such as millets, brown rice or whole wheat in sensible portions. They release sugar more slowly than white rice or maida.",
        "Walk for 10 to 15 minutes after main meals and aim for 150 minutes of activity a week. Muscles use sugar when they work.",
        "Aim for 7 to 8 hours of sleep. Poor sleep makes insulin work less well.",
    ],
    seek=["Talk to a doctor if your predicted risk is increased or very high, so they can check your blood sugar or HbA1c.", "See a doctor soon if you have extreme thirst, frequent urination, unexplained weight loss or blurred vision."],
    misconceptions=["Diabetes is not caused by eating sugar alone.", "A normal fasting sugar does not rule out raised risk, as HbA1c and insulin can change earlier."],
    limits=["A predicted risk cannot diagnose diabetes. Blood tests such as fasting sugar or HbA1c are needed."],
    q=["What does my diabetes risk score mean?", "Can I lower my diabetes risk?", "My sugar is normal, so why is my risk raised?", "What should I eat to prevent diabetes?"],
    reasons={"WB-067": "Shows your blood sugar after fasting.", "WB-068": "Shows your average blood sugar over about three months.", "WB-069": "Shows how much insulin your body needs to keep sugar steady."},
    src=["glucose", "a1c", "life_glucose", "life_activity", "who_diabetes"],
)

R["obesity"] = dict(
    short="This assessment looks at weight and metabolic health: whether your body may be carrying extra fat in a way that strains your health, especially around the waist.",
    body=[
        "Your body stores spare energy as fat.",
        "Fat stored deep in the tummy around organs is more active and affects blood sugar, blood fats and blood pressure more than fat elsewhere.",
        "Deep tummy fat can lead to insulin resistance and inflammation.",
    ],
    why=["Extra weight around the waist raises the chance of type 2 diabetes, high blood pressure, fatty liver, heart disease and joint problems."],
    symptoms=["There are usually no symptoms apart from weight or waist change. Some people notice snoring, tiredness or joint pain."],
    factors=["Diet and portion size", "Physical activity", "Sleep", "Stress", "Some medicines", "Hormone conditions such as an underactive thyroid"],
    life=["Large portions, sugary drinks, fried and processed foods, low activity, short sleep and ongoing stress are linked with weight gain.", "Many South Asians develop metabolic problems at lower body weights."],
    long_term=["Over time, it raises the risk of diabetes, heart disease, fatty liver, sleep apnoea and some cancers."],
    support=[
        "Use a smaller plate and fill half with vegetables. This lowers calories without leaving you hungry.",
        "Replace sugary drinks and juices with water, buttermilk or unsweetened tea. Liquid sugar adds calories without filling you up.",
        "Add movement through the day and some strength exercise twice a week. Muscle helps your body use sugar.",
        "Keep a regular sleep routine. Short sleep is linked with weight gain and cravings.",
    ],
    seek=["Talk to a doctor if your predicted risk is increased or very high, if your waist is growing, or if you have snoring with daytime sleepiness."],
    misconceptions=["Weight is not only about willpower. Genes, sleep, stress, medicines and hormones all play a part.", "A normal BMI does not always mean healthy metabolism, especially for South Asians."],
    limits=["A predicted risk does not measure body fat directly. Waist size and other checks help."],
    q=["What does my weight and metabolic health score mean?", "Why does belly fat matter more?", "How can I lose weight in a healthy way?", "Can I be at risk even if my weight is normal?"],
    reasons={"WB-067": "Shows your blood sugar after fasting.", "WB-068": "Shows your average blood sugar over about three months.", "WB-003": "Shows triglycerides, a blood fat that often rises with extra weight."},
    src=["life_activity", "life_diet", "who_obesity"],
)

_THY_FACTORS = ["Autoimmune thyroid conditions", "Family history", "Iodine intake", "Pregnancy and after childbirth", "Some medicines", "Age and sex"]
_THY_NA_SUPPORT = None

R["thyroid"] = dict(
    short="Thyroid health describes how well your thyroid gland, a small butterfly-shaped gland in your neck, is making the hormones that set your body's pace.",
    body=[
        "Your thyroid makes hormones called T4 and T3 that control how fast your body uses energy.",
        "A signal from your brain, called TSH, tells the thyroid how much to make.",
        "If the thyroid makes too little or too much, many body systems slow down or speed up.",
    ],
    why=["Thyroid problems are common, especially in women, and can affect energy, weight, mood, periods, fertility and the heart.", "Thyroid problems are easy to check with a blood test and usually treatable."],
    symptoms=["An underactive thyroid can cause tiredness, weight gain, feeling cold and constipation.", "An overactive thyroid can cause weight loss, a racing heart, feeling hot, shakiness and anxiety."],
    factors=_THY_FACTORS,
    life=["Most thyroid problems are caused by the immune system, not by lifestyle. Using iodised salt helps prevent iodine shortage."],
    long_term=["Untreated thyroid problems can affect the heart, bones, fertility and pregnancy."],
    support=["Use iodised salt in normal amounts. Iodine is needed to make thyroid hormones."],
    seek=["Talk to a doctor if your predicted risk is increased or very high, or you have symptoms such as unusual tiredness, weight change, a racing heart or changes in periods. A TSH blood test can check."],
    misconceptions=["Thyroid problems are not usually caused by diet.", "A predicted thyroid risk does not mean your thyroid is not working."],
    limits=["A predicted risk does not measure your thyroid hormones. Only blood tests can show how your thyroid is working."],
    q=["What does my thyroid health score mean?", "Do I need a thyroid blood test?", "What are the signs of a thyroid problem?", "Can thyroid problems cause weight gain?"],
    reasons={"WB-039": "Shows T3, the active thyroid hormone.", "WB-040": "Shows T4, the main hormone made by your thyroid.", "WB-041": "Shows TSH, the brain's signal that tells your thyroid how hard to work."},
    src=["niddk_hypothyroid", "niddk_hyperthyroid"],
)

R["hypothyroidism"] = dict(
    short="An underactive thyroid, or hypothyroidism, means your thyroid gland is not making enough hormone, so many body processes slow down.",
    body=[
        "Thyroid hormones set how fast your cells use energy.",
        "When there is too little hormone, the brain sends more TSH to push the thyroid harder.",
        "The most common cause is Hashimoto's thyroiditis, where the immune system slowly damages the thyroid.",
    ],
    why=["An underactive thyroid is common, especially in women, and can affect energy, weight, mood, cholesterol, periods and pregnancy."],
    symptoms=["Tiredness, weight gain, feeling cold, constipation, dry skin, hair thinning, low mood and heavy or irregular periods."],
    factors=_THY_FACTORS,
    life=["An underactive thyroid is mainly caused by the immune system rather than habits. Iodine shortage is a cause in some areas, so iodised salt helps."],
    long_term=["Untreated, it can raise cholesterol, affect the heart, and cause problems with fertility and pregnancy."],
    support=["Use iodised salt in normal amounts. Iodine is needed to make thyroid hormones."],
    seek=["Talk to a doctor if your predicted risk is increased or very high, or if you have symptoms. A TSH test is the main check. Treatment, if needed, is a daily tablet decided by a doctor."],
    misconceptions=["Weight gain from an underactive thyroid is usually modest.", "Eating cabbage or soya in normal amounts does not cause thyroid disease."],
    limits=["A predicted risk does not measure your thyroid hormones. Blood tests are needed."],
    q=["What does my underactive thyroid risk mean?", "What are the signs of an underactive thyroid?", "Can my thyroid make me tired or gain weight?", "Should I get my TSH checked?"],
    reasons={"WB-039": "Shows T3, the active thyroid hormone.", "WB-040": "Shows T4, which is often low when the thyroid is underactive.", "WB-041": "Shows TSH, which usually rises when the thyroid is underactive."},
    src=["niddk_hypothyroid"],
)

R["hyperthyroidism"] = dict(
    short="An overactive thyroid, or hyperthyroidism, means your thyroid gland is making too much hormone, so many body processes speed up.",
    body=[
        "Too much thyroid hormone makes cells use energy faster.",
        "The brain's TSH signal falls in response.",
        "The most common cause is Graves' disease, where the immune system pushes the thyroid to overwork.",
    ],
    why=["An overactive thyroid can strain the heart, thin the bones and cause pregnancy problems if not treated."],
    symptoms=["Weight loss, a fast or irregular heartbeat, feeling hot, sweating, shaky hands, anxiety, poor sleep and frequent bowel movements."],
    factors=_THY_FACTORS,
    life=["An overactive thyroid is mainly caused by the immune system rather than habits. Very high iodine intake, for example from some supplements, can trigger it in some people."],
    long_term=["Untreated, it can cause an irregular heart rhythm, heart strain and thinning bones."],
    support=[],
    seek=["Talk to a doctor if your predicted risk is increased or very high, or you have symptoms. Seek care promptly for a racing or irregular heartbeat, chest pain or severe shakiness."],
    misconceptions=["Weight loss from an overactive thyroid is not healthy weight loss."],
    limits=["A predicted risk does not measure your thyroid hormones. Blood tests are needed."],
    q=["What does my overactive thyroid risk mean?", "What are the signs of an overactive thyroid?", "Can my thyroid cause a racing heart?", "Should I get my thyroid checked?"],
    reasons={"WB-039": "Shows T3, which is often high when the thyroid is overactive.", "WB-040": "Shows T4, which is often high when the thyroid is overactive.", "WB-041": "Shows TSH, which usually falls when the thyroid is overactive."},
    src=["niddk_hyperthyroid"],
    na={"practical_guidance": "An overactive thyroid needs medical treatment; no everyday habit reliably helps it."},
)

R["pcos"] = dict(
    short="Polycystic ovary syndrome, or PCOS, is a common hormone condition that can make periods irregular, raise male-type hormones and affect how the body handles sugar.",
    body=[
        "Normally the ovaries release an egg each month.",
        "In PCOS, hormone signals shift, so eggs may not be released regularly and periods become irregular.",
        "The ovaries may make more androgens, male-type hormones that can cause acne or extra hair growth.",
        "Many people with PCOS also have insulin resistance, which can raise blood sugar and weight.",
    ],
    why=["PCOS is one of the most common hormone conditions in women of reproductive age.", "PCOS can affect periods, fertility, skin, mood and long-term metabolic health."],
    symptoms=["Irregular, infrequent or missed periods.", "Acne, oily skin, extra facial or body hair, or hair thinning on the scalp.", "Weight gain or difficulty losing weight, and difficulty getting pregnant."],
    factors=["Family history", "Insulin resistance", "Body weight", "Physical activity", "Sleep and stress"],
    life=["Regular activity, balanced meals and healthy sleep help insulin work better, which can improve PCOS symptoms.", "PCOS also occurs in people of normal weight."],
    long_term=["PCOS is linked with a higher risk of type 2 diabetes, high cholesterol, fatty liver, sleep apnoea, low mood and, with very infrequent periods, thickening of the womb lining."],
    support=[
        "Build regular movement into your week, including some strength exercise. Activity helps your body respond to insulin.",
        "Base meals on vegetables, protein and whole grains, and limit sugary drinks and sweets. Steadier blood sugar can help hormone balance.",
        "Keep a regular sleep routine and find ways to manage stress. Both affect hormones and insulin.",
        "Track your periods in a calendar or app. It helps your doctor understand your pattern.",
    ],
    seek=["Talk to a doctor if your predicted risk is increased or very high, or if you have irregular periods, acne or extra hair growth, or difficulty getting pregnant.", "See a doctor if you go three months or more without a period and are not pregnant."],
    misconceptions=["You can have PCOS even if your weight is normal.", "Not everyone with PCOS has cysts on the ovaries, and ovarian cysts alone do not mean PCOS.", "PCOS and PCOD are commonly used names for the same condition.", "No single blood test confirms PCOS."],
    limits=["A doctor diagnoses PCOS from your periods, signs of high androgens, blood tests and sometimes an ultrasound."],
    q=["What does my PCOS score mean?", "Can I have PCOS even if my weight is normal?", "How are PCOS and blood sugar connected?", "When should I see a doctor about PCOS?"],
    reasons={"WB-095": "Shows testosterone, a male-type hormone that is often higher in PCOS.", "WB-101": "Shows LH, a hormone that controls egg release and can be raised in PCOS.", "WB-102": "Shows FSH, which helps eggs develop and is read with LH.", "WB-067": "Shows your fasting blood sugar, which PCOS can affect.", "WB-069": "Shows fasting insulin, which is often high with insulin resistance in PCOS."},
    src=["who_pcos", "pcos_guideline_2023"],
)

R["oxidative_stress"] = dict(
    short="Oxidative stress is what happens when substances your cells make as they work build up faster than your body's protective systems can handle them.",
    body=[
        "Your cells naturally make some reactive molecules, often called free radicals, as they use energy.",
        "Your body has protective systems, including antioxidants from food, that keep these molecules in balance.",
        "When that protection cannot keep up, the extra molecules may damage parts of cells. That imbalance is called oxidative stress.",
    ],
    why=["Over time, this imbalance can affect the health of cells.", "Research discusses oxidative stress alongside inflammation and some longer-term health conditions."],
    symptoms=["Oxidative stress does not cause symptoms you can feel."],
    factors=["Eating habits", "Sleep", "Physical activity", "Smoking", "Ongoing stress", "Alcohol"],
    life=["Smoking, heavy alcohol use, diets low in fruit and vegetables, and poor sleep are studied as general influences on oxidative stress."],
    long_term=["Research links long-term oxidative stress with inflammation and some conditions such as heart disease, but a score does not show that this has happened."],
    support=[
        "Include a variety of vegetables, fruit, pulses and other minimally processed foods. They provide natural antioxidants.",
        "Keep a sleep routine that gives you enough rest. Sleep supports your body's repair processes.",
        "Stay physically active in a way that fits your usual day. Regular moderate activity strengthens the body's own protective systems.",
        "If you smoke, ask for help to stop. Smoking is a strong source of oxidative stress.",
    ],
    seek=["There is no specific medical test or treatment for oxidative stress. Talk to a doctor if you have other raised risks or symptoms that worry you."],
    misconceptions=["A normal blood test in this area does not cancel a higher predicted oxidative stress risk, because routine blood tests do not directly measure it.", "Antioxidant supplements have not been shown to replace a healthy diet."],
    limits=["This score is a risk estimate, not a direct measurement of cell damage."],
    q=["Why is my oxidative stress risk high when a blood test in this area is normal?", "Which everyday habits are linked with oxidative stress?", "Which foods support the body's protective systems?", "Do I need antioxidant supplements?"],
    reasons={"WB-093": "Shows hs-CRP, a sign of inflammation, which often goes alongside oxidative stress.", "WB-038": "Shows vitamin C, one of the body's antioxidants from food."},
    src=["life_c", "life_diet", "life_activity"],
)

R["metabolic_age"] = dict(
    short="Metabolic age is a Bio-AI estimate that compares parts of your metabolic health, such as how your body handles sugar and fats, with patterns usually seen at different ages.",
    body=[
        "Metabolic health is how well your body turns food into energy, keeps blood sugar steady and handles fats.",
        "Your actual age is how many years you have lived. Metabolic age is an estimate based on health information, not a count of birthdays.",
        "A metabolic age above your actual age suggests your metabolic health looks more like that of an older group. Below suggests it looks more like a younger group.",
    ],
    why=["Metabolic age is a simple way to start a conversation about blood sugar, blood fats, weight, activity and sleep.", "The estimate does not measure how long you will live or how fast your whole body is ageing."],
    factors=["Physical activity", "Eating habits", "Sleep", "Body weight", "Blood sugar and blood fats"],
    life=["Activity, eating habits, sleep and weight are general influences on metabolic health. The provider has not said which inputs or weights it uses."],
    long_term=["Metabolic age is not linked to a specific disease. Metabolic health in general is linked with the risk of diabetes, fatty liver and heart disease."],
    support=[
        "Move regularly and include some strength exercise. Muscle helps your body use sugar and fats.",
        "Base meals on vegetables, pulses, whole grains and protein, with fewer sugary and fried foods. This supports steadier blood sugar and blood fats.",
        "Keep a regular sleep routine of 7 to 8 hours. Sleep affects how well insulin works.",
    ],
    seek=["There is no medical treatment for metabolic age itself. Talk to a doctor about any raised blood sugar, cholesterol or other risks shown alongside it."],
    misconceptions=["A higher metabolic age does not mean you have lost years of life.", "A lower metabolic age does not guarantee good health.", "Normal blood results can sit alongside a higher estimate, because a prediction is not a measurement.", "No habit is promised to change the number by a set number of years."],
    limits=["The calculation method, inputs and reference group are not available, so CURA cannot say what produced your estimate."],
    q=["What does my metabolic age mean?", "Can my metabolic age change over time?", "How is metabolic age different from biological age?", "What habits support my metabolic health?"],
    risk_meaning=["Metabolic age is an estimate from your Bio-AI assessment, not a measurement or diagnosis.", "A different estimate on a later assessment can reflect changes in your health or in the information used."],
    reasons={},
    src=["metsights_inputs", "nia_aging"],
)
