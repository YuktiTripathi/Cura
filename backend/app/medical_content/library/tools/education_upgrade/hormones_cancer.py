"""Revision 2.3.1 content: hormones, calcium (assay unconfirmed) and tumour markers. Pending clinical review."""

C = {}

_HORMONE_NA = {"practical_guidance": "Abnormal levels of this hormone need medical assessment of the cause; everyday habits do not reliably correct it."}

C["WB-095"] = dict(
    d="Testosterone is a sex hormone made mainly in the testes in men and in smaller amounts by the ovaries and adrenal glands in women. Total testosterone measures all of it in your blood.",
    body=[
        "In men, testosterone supports sex drive, sperm production, muscle, bone strength and energy.",
        "In women, smaller amounts support sex drive, bone and muscle.",
        "Levels are highest in the morning and fall gradually with age in men.",
    ],
    why=["It helps check for low testosterone in men and for high androgen levels in women, which can be part of PCOS."],
    high="In women, a higher testosterone often goes with PCOS and can cause irregular periods, acne or extra hair growth. In men, high levels are uncommon and can come from testosterone or anabolic steroid use.",
    low="In men, a lower testosterone can come from ageing, extra weight, poor sleep, long illness, some medicines or problems with the testes or pituitary gland. It can cause low sex drive, tiredness and loss of muscle.",
    normal="Your testosterone is inside the lab's range for the reference group used.",
    factors=["Time of day", "Age and sex", "Body weight", "Sleep", "PCOS", "Testosterone or steroid use"],
    life=["Extra body weight, poor sleep and heavy alcohol use are linked with lower testosterone in men."],
    support=[
        "Aim for 7 to 8 hours of sleep. Testosterone is made mostly during sleep.",
        "Stay active and include some strength exercise. It supports muscle and a healthy weight, which helps hormone balance.",
    ],
    seek=["Men: talk to a doctor if testosterone is low and you have low sex drive, erection problems or tiredness.", "Women: talk to a doctor if testosterone is high and you have irregular periods, acne or extra hair growth."],
    limits=["Testosterone varies by time of day and is best checked in the morning. A low result is usually repeated before any diagnosis."],
    q=dict(
        high=["Could high testosterone be a sign of PCOS?", "What symptoms can high testosterone cause in women?"],
        low=["Why is my testosterone low?", "Can sleep or weight affect testosterone?", "Should I repeat my testosterone test?"],
        normal=["What does testosterone do in my body?"],
    ),
)

C["WB-096"] = dict(
    d="DHEA-S is a hormone made mainly by the adrenal glands, which sit on top of your kidneys. Your body can turn it into other sex hormones.",
    body=["The adrenal glands make DHEA-S in large amounts in young adults.", "It is a building block for testosterone and oestrogen.", "Levels fall naturally as you age."],
    why=["It helps check whether extra male-type hormones are coming from the adrenal glands, for example in women with acne or extra hair growth."],
    high="A higher DHEA-S can be seen with PCOS or, less often, with adrenal gland conditions. In women it can cause acne, extra hair growth or irregular periods.",
    low="A lower DHEA-S is common with ageing. It can also be seen with adrenal or pituitary problems or long-term steroid medicines.",
    normal="Your DHEA-S is inside the lab's range for your age and sex.",
    factors=["Age", "Sex", "PCOS", "Adrenal conditions", "Steroid medicines"],
    life=None, support=[],
    seek=["Talk to a doctor if DHEA-S is high with acne, extra hair growth or irregular periods, or if it is very high."],
    limits=["Normal ranges change a lot with age, so the result must be read against the right age group."],
    not_applicable={**_HORMONE_NA, "lifestyle_relationships": "DHEA-S is set mainly by age and adrenal activity."},
    q=dict(high=["What does a high DHEA-S mean?", "Is high DHEA-S linked with PCOS?"], low=["Is low DHEA-S normal with age?"], normal=["What does DHEA-S do?"]),
)

C["WB-097"] = dict(
    d="IGF-1 is a hormone made mainly by the liver in response to growth hormone. It reflects how much growth hormone your body has been making.",
    body=["Growth hormone from the pituitary gland tells the liver to make IGF-1.", "IGF-1 helps build bone and muscle and repair tissue.", "Levels peak in the teenage years and fall with age."],
    why=["IGF-1 is used to check for too much or too little growth hormone."],
    high="A higher IGF-1 can be seen in puberty and pregnancy. Persistently high levels in adults can, rarely, mean the pituitary is making too much growth hormone.",
    low="A lower IGF-1 can come from ageing, poor nutrition, liver disease, an underactive thyroid, poorly controlled diabetes or low growth hormone.",
    normal="Your IGF-1 is inside the lab's range for your age.",
    factors=["Age", "Nutrition", "Liver function", "Thyroid function", "Pituitary activity"],
    life=["Very low calorie or protein intake can lower IGF-1."],
    support=[],
    seek=["Talk to a doctor if IGF-1 is outside the range for your age, especially with changes in hand or foot size, facial features, or unexplained tiredness."],
    limits=["IGF-1 ranges depend strongly on age, and results differ between labs."],
    not_applicable=dict(_HORMONE_NA),
    q=dict(high=["What does a high IGF-1 mean?"], low=["Why is my IGF-1 low?"], normal=["What does IGF-1 tell me?"]),
)

C["WB-098"] = dict(
    d="Cortisol is a hormone made by your adrenal glands. It helps your body respond to stress, control blood sugar and blood pressure, and regulate your sleep and wake cycle.",
    body=["Cortisol is highest in the early morning and lowest around midnight.", "It rises during physical or emotional stress.", "The brain controls how much cortisol the adrenal glands release."],
    why=["Cortisol is used to check whether the adrenal glands are making too much or too little."],
    high="A higher cortisol can come from stress, illness, poor sleep, pregnancy, hormone pills or steroid medicines. Rarely, it is due to Cushing syndrome, where the body makes too much cortisol for a long time.",
    low="A lower cortisol can be normal if the sample was taken later in the day. A low morning cortisol can point to adrenal insufficiency, where the glands do not make enough, or follow stopping steroid medicines.",
    normal="Your cortisol is inside the lab's range for the time the sample was taken.",
    factors=["Time of day", "Stress and illness", "Sleep", "Steroid medicines", "Hormone pills or pregnancy"],
    life=["Ongoing stress and poor sleep can change cortisol patterns."],
    support=[
        "Keep a regular sleep and wake time. Cortisol follows a daily rhythm that steady sleep helps support.",
        "Make time for things that help you unwind, such as walking, prayer, breathing exercises or time with friends. These can ease the stress response.",
    ],
    seek=["Talk to a doctor if cortisol is clearly abnormal, especially with weight gain around the tummy, purple stretch marks, or with weakness, dizziness, weight loss and salt cravings. Never stop steroid medicines suddenly."],
    limits=["A single cortisol result depends heavily on the time of day. Special timed tests are needed to diagnose adrenal conditions."],
    q=dict(high=["Can stress raise my cortisol?", "Should I worry about high cortisol?"], low=["Why is my cortisol low?", "Does the time of my test affect cortisol?"], normal=["What does cortisol do in my body?"]),
)

C["WB-099"] = dict(
    d="Parathyroid hormone, or PTH, is made by four tiny glands in your neck. It controls the calcium level in your blood.",
    body=["When blood calcium falls, PTH rises.", "PTH releases calcium from bones, helps kidneys keep calcium and activates vitamin D to absorb more from food.", "When calcium is high, PTH should fall."],
    why=["PTH is read with calcium and vitamin D to find the cause of calcium problems."],
    high="A higher PTH with high calcium usually points to an overactive parathyroid gland. A higher PTH with normal or low calcium often means low vitamin D or kidney disease.",
    low="A lower PTH with high calcium suggests the calcium rise is coming from somewhere else. Low PTH with low calcium can mean the parathyroid glands are underactive, for example after neck surgery.",
    normal="Your PTH is inside the lab's range. It is interpreted together with calcium.",
    factors=["Calcium level", "Vitamin D level", "Kidney function", "Magnesium level"],
    life=["Low vitamin D, from little sunlight or diet, is a common reason PTH rises."],
    support=["Spend some time in daylight and include calcium and vitamin D foods. Low vitamin D is a common reason PTH rises."],
    seek=["Talk to a doctor if PTH is abnormal together with abnormal calcium, kidney stones, bone pain or thinning bones."],
    limits=["PTH cannot be interpreted without a calcium result taken at the same time."],
    q=dict(high=["Why is my parathyroid hormone high?", "Can low vitamin D raise PTH?"], low=["What does a low PTH mean?"], normal=["How do PTH and calcium work together?"]),
)

C["WB-100"] = dict(
    d="Prolactin is a hormone made by the pituitary gland in your brain. Its main job is to help make breast milk after childbirth.",
    body=["Prolactin rises in pregnancy and breastfeeding.", "It also affects periods and fertility in women and sex drive in men.", "Stress, sleep and some medicines can raise it."],
    why=["High prolactin can cause irregular or missed periods, milk leakage, low sex drive and fertility problems."],
    high="A higher prolactin can come from pregnancy, breastfeeding, stress, a recent meal or exercise, an underactive thyroid, kidney disease or some medicines such as certain anti-sickness and mental health medicines. A small harmless growth on the pituitary called a prolactinoma is another cause.",
    low="A low prolactin is rarely a concern.",
    normal="Your prolactin is inside the lab's range.",
    factors=["Pregnancy and breastfeeding", "Stress", "Some medicines", "Thyroid function", "Kidney function", "Time of sample"],
    life=None, support=[],
    seek=["Talk to a doctor if prolactin is high, especially with missed periods, milk from the breasts when not breastfeeding, headaches or vision changes."],
    limits=["Mildly high prolactin is often repeated, as stress or the blood draw itself can raise it."],
    not_applicable={**_HORMONE_NA, "lifestyle_relationships": "Prolactin is set mainly by the pituitary, pregnancy and medicines."},
    q=dict(high=["Why is my prolactin high?", "Can stress or medicines raise prolactin?", "Can high prolactin affect my periods?"], low=["Is a low prolactin a problem?"], normal=["What does prolactin do?"]),
)

C["WB-101"] = dict(
    d="Luteinising hormone, or LH, is made by the pituitary gland. It signals the ovaries to release an egg and the testes to make testosterone.",
    body=["In women, LH rises sharply in the middle of the cycle to trigger ovulation.", "In men, LH tells the testes to make testosterone.", "After menopause, LH rises because the ovaries stop responding."],
    why=["LH helps check fertility, periods, menopause and testosterone problems. In some women with PCOS, LH is higher compared with FSH."],
    high="A higher LH can be normal mid-cycle or after menopause. Outside these times, it can be seen with PCOS or when the ovaries or testes are not working well.",
    low="A lower LH can mean the pituitary is not sending enough signal. It can also be seen with hormone pills, stress, very low body weight or heavy exercise.",
    normal="Your LH is inside the lab's range for the reference group used.",
    factors=["Menstrual cycle day", "Menopause", "Hormone pills", "PCOS", "Body weight and exercise"],
    life=["Very low body weight, intense exercise and severe stress can lower LH."],
    support=[],
    seek=["Talk to a doctor if LH is abnormal along with irregular or missed periods, difficulty getting pregnant, or low testosterone symptoms."],
    limits=["LH in women must be read against the day of the menstrual cycle the sample was taken."],
    not_applicable=dict(_HORMONE_NA),
    q=dict(high=["What does a high LH mean?", "Is high LH linked with PCOS?"], low=["What does a low LH mean?"], normal=["What does LH do in my body?", "Does the day of my cycle affect LH?"]),
)

C["WB-102"] = dict(
    d="Follicle-stimulating hormone, or FSH, is made by the pituitary gland. It helps eggs develop in the ovaries and sperm develop in the testes.",
    body=["In women, FSH helps egg follicles grow early in each cycle.", "In men, it supports sperm production.", "FSH rises around menopause as the ovaries respond less."],
    why=["FSH helps check fertility, menopause and the function of the ovaries and testes."],
    high="A higher FSH in women often goes with menopause or reduced ovarian reserve. In men, it can mean the testes are not making sperm well.",
    low="A lower FSH can mean the pituitary is not sending enough signal, or can be seen with hormone pills, pregnancy, very low body weight or stress.",
    normal="Your FSH is inside the lab's range for the reference group used.",
    factors=["Menstrual cycle day", "Menopause", "Age", "Hormone pills", "Body weight"],
    life=None, support=[],
    seek=["Talk to a doctor if FSH is abnormal along with irregular or missed periods, difficulty getting pregnant, or hot flushes before 40."],
    limits=["FSH in women varies through the cycle and is usually checked in the first few days of a period."],
    not_applicable={**_HORMONE_NA, "lifestyle_relationships": "FSH is set mainly by the pituitary, age and ovarian or testicular function."},
    q=dict(high=["Does a high FSH mean menopause?", "Can high FSH affect fertility?"], low=["What does a low FSH mean?"], normal=["What does FSH do?"]),
)

C["WB-103"] = dict(
    d="This result measures calcium, the mineral that keeps bones strong and helps muscles, nerves and the heart work. The lab has not confirmed whether it is total or free (ionised) calcium.",
    body=["Most calcium is stored in bones.", "A small amount in blood is carefully controlled by parathyroid hormone and vitamin D.", "Free calcium is the active part; total calcium includes calcium carried on albumin."],
    why=["Calcium helps check bone health, parathyroid function, vitamin D status and kidney function."],
    high="A higher calcium most often comes from an overactive parathyroid gland, too much vitamin D or calcium from supplements, or dehydration.",
    low="A lower calcium can come from low vitamin D, low albumin, low magnesium, kidney disease or low parathyroid hormone.",
    normal="Your calcium is inside the lab's range.",
    factors=["Which calcium was measured", "Vitamin D", "Parathyroid hormone", "Albumin", "Kidney function", "Supplements"],
    life=["Dietary calcium and vitamin D support bones, though blood calcium rarely changes with diet alone."],
    support=["Include calcium foods such as milk, curd, ragi, sesame or calcium-set tofu. These support bone health."],
    seek=["Talk to a doctor if calcium is abnormal, especially with cramps, tingling, extreme thirst, confusion or kidney stones."],
    limits=["The lab has not confirmed whether this is total or free calcium, so this result should not be compared directly with the total calcium result on your report."],
    q=dict(high=["Why is my calcium high?", "Which calcium was measured on my report?"], low=["Why is my calcium low?", "Is low calcium linked to vitamin D?"], normal=["Does normal blood calcium mean my bones are healthy?"]),
)

_TUMOUR_LIMIT = "This marker is not a cancer screening test on its own. Many non-cancer conditions raise it, and a normal result does not rule out cancer."
_TUMOUR_NA = {"lifestyle_relationships": "Tumour marker; levels are not meaningfully changed by everyday habits.", "practical_guidance": "A raised tumour marker needs medical assessment, not lifestyle change."}
_TUMOUR_SEEK = "Talk to a doctor about any raised result, so it can be put in context and, if needed, repeated or followed up with other tests. Most raised results are not caused by cancer."


def _tumour(d, body, high, normal, factors, q, extra_limit=None, low="A low result is expected and is not a concern."):
    return dict(d=d, body=body, why=["This marker is mainly used to follow people already being treated for certain cancers, and sometimes to help investigate symptoms."],
                high=high, low=low, normal=normal, factors=factors, life=None, support=[], seek=[_TUMOUR_SEEK],
                limits=[_TUMOUR_LIMIT] + ([extra_limit] if extra_limit else []), not_applicable=dict(_TUMOUR_NA), q=q)


C["WB-104"] = _tumour(
    "PSA, or prostate-specific antigen, is a protein made by the prostate gland, a small gland below the bladder in men.",
    ["The prostate makes PSA to help semen stay liquid.", "A small amount enters the blood.", "PSA tends to rise with age as the prostate grows."],
    "A higher PSA is most often due to a larger prostate with age, prostate inflammation or infection, recent ejaculation, cycling or a recent urinary procedure. Prostate cancer is one possible cause and needs further checks.",
    "Your PSA is inside the lab's range. A normal PSA lowers the likelihood of significant prostate cancer but does not rule it out.",
    ["Age", "Prostate enlargement", "Prostate inflammation or infection", "Recent ejaculation or cycling", "Some medicines"],
    dict(high=["Does a high PSA mean I have prostate cancer?", "What can raise PSA apart from cancer?", "Should I repeat my PSA test?"], low=["Is a low PSA good?"], normal=["How often should I check my PSA?", "What is PSA?"]),
    extra_limit="PSA screening has benefits and harms. Decisions about testing are best made with a doctor.",
)
C["WB-104"]["not_applicable"]["practical_guidance"] = "PSA needs medical interpretation; avoiding ejaculation and cycling for 48 hours before a repeat test is a testing tip, not health guidance."

C["WB-105"] = _tumour(
    "CEA, or carcinoembryonic antigen, is a protein that is normally present only in very small amounts in adult blood.",
    ["Some cells, especially in the bowel, make CEA.", "Levels can rise with some cancers, but also with smoking and inflammation."],
    "A higher CEA can come from smoking, inflammation of the bowel, liver or lungs, or pancreatitis. Some cancers, especially bowel cancer, can also raise it.",
    "Your CEA is inside the lab's range.",
    ["Smoking", "Inflammatory bowel conditions", "Liver disease", "Lung conditions", "Some cancers"],
    dict(high=["Does a high CEA mean cancer?", "Can smoking raise CEA?"], low=["Is a low CEA good?"], normal=["What is CEA used for?"]),
    extra_limit="Smokers often have higher CEA than non-smokers.",
)

C["WB-106"] = dict(
    d="AFP, or alpha-fetoprotein, is a protein made by a developing baby and, in adults, in small amounts by the liver. The report labels this as an amniotic fluid test, so the lab needs to confirm which sample was used.",
    body=["In pregnancy, AFP passes from the baby into the mother's blood and the fluid around the baby.", "In adults, high blood AFP can be linked with some liver conditions and some cancers."],
    why=["AFP in pregnancy screens for some birth conditions. In adults, it is used to follow some liver and testicular cancers."],
    factors=["Sample type", "Pregnancy", "Liver conditions"],
    life=None, support=[],
    seek=["Ask your doctor or the lab what sample this AFP result came from before reading anything into it."],
    limits=["Amniotic fluid AFP and adult blood AFP have completely different purposes and ranges, so this result cannot be interpreted until the sample is confirmed."],
    not_applicable={**_TUMOUR_NA, "interpretation": "Specimen not confirmed, so high or low wording is withheld."},
    assay="The sample type for this AFP result is not confirmed, so CURA does not interpret it. Ask the lab or your doctor which sample was tested.",
    q=dict(assay_unconfirmed=["Which sample was my AFP test done on?", "What is AFP used for in adults?"]),
)

C["WB-107"] = _tumour(
    "CA 19-9 is a protein found on some cells of the pancreas, bile ducts and gut. It is mainly used to follow pancreatic and bile duct conditions.",
    ["Small amounts are normal in the blood.", "CA 19-9 rises when bile flow is blocked or the pancreas is inflamed, as well as with some cancers."],
    "A higher CA 19-9 is often caused by blocked bile flow, gallstones, pancreatitis, liver conditions or diabetes. Some cancers of the pancreas and bile ducts can also raise it.",
    "Your CA 19-9 is inside the lab's range.",
    ["Bile duct blockage", "Pancreatitis", "Liver conditions", "Diabetes", "Some cancers"],
    dict(high=["Does a high CA 19-9 mean cancer?", "Can gallstones raise CA 19-9?"], low=["Is a low CA 19-9 good?"], normal=["What is CA 19-9 used for?"]),
    extra_limit="Some people cannot make CA 19-9 because of their blood group genes, so their level stays low even with disease.",
)

C["WB-108"] = _tumour(
    "CA 125 is a protein found on some cells, including those lining the ovaries, womb, tummy and chest. It is mainly used to follow ovarian conditions.",
    ["Small amounts are normal in the blood.", "CA 125 can rise with many conditions that irritate these linings."],
    "A higher CA 125 is often caused by periods, pregnancy, endometriosis, fibroids, pelvic infection, liver disease or fluid in the tummy. Ovarian cancer is one possible cause.",
    "Your CA 125 is inside the lab's range.",
    ["Menstrual cycle", "Pregnancy", "Endometriosis or fibroids", "Pelvic infection", "Liver disease", "Some cancers"],
    dict(high=["Does a high CA 125 mean ovarian cancer?", "Can my period raise CA 125?"], low=["Is a low CA 125 good?"], normal=["What is CA 125 used for?"]),
    extra_limit="CA 125 is often higher in women who have not reached menopause, for reasons that are not cancer.",
)

C["WB-109"] = _tumour(
    "CA 15-3 is a protein made by breast cells. It is mainly used to follow people being treated for breast cancer.",
    ["Small amounts are normal in the blood.", "Levels can rise with some breast cancers and with some non-cancer conditions."],
    "A higher CA 15-3 can come from liver conditions, some benign breast conditions or, in people with breast cancer, from disease activity.",
    "Your CA 15-3 is inside the lab's range.",
    ["Liver conditions", "Benign breast conditions", "Some cancers"],
    dict(high=["Does a high CA 15-3 mean breast cancer?"], low=["Is a low CA 15-3 good?"], normal=["What is CA 15-3 used for?"]),
    extra_limit="CA 15-3 is not used to screen for or diagnose breast cancer.",
)
