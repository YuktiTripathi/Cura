"""Revision 2.3.1 content: vitamins and thyroid. Pending clinical review."""

C = {}

C["WB-036"] = dict(
    d="Vitamin B12 is a vitamin your body needs to make healthy red blood cells, keep nerves working and make DNA, the genetic material in your cells.",
    body=[
        "B12 comes mostly from animal foods such as milk, curd, eggs, fish and meat.",
        "Your stomach needs acid and a protein called intrinsic factor to absorb B12.",
        "Your liver stores B12, so a shortage can take months or years to show.",
    ],
    why=["Low B12 can cause tiredness, anaemia, tingling, numbness and memory problems. Nerve damage can become permanent if a shortage lasts a long time."],
    high="Higher B12 is usually from supplements or injections and is generally not harmful. Very high levels without supplements are uncommon and may be checked further.",
    low="Lower B12 often comes from eating few animal foods, as in vegetarian and vegan diets. Poor absorption in the stomach or gut, and medicines such as metformin or long-term acid-reducing tablets, can also lower it. So people who eat meat can be low too.",
    normal="Your vitamin B12 is inside the lab's range. Some people with results near the lower end can still have a mild shortage, so symptoms matter.",
    factors=["Vegetarian or vegan diet", "Stomach or gut absorption", "Metformin", "Long-term acid-reducing tablets", "Age", "Supplements"],
    life=[
        "B12 is found naturally only in animal foods, so vegetarians and vegans are at higher risk of low levels.",
        "Absorption falls with age and with some stomach conditions, even when the diet contains enough.",
    ],
    support=[
        "Include milk, curd, paneer or eggs daily if you eat them. They are the main vegetarian sources of B12.",
        "If you are vegan, look for foods fortified with B12, such as some plant milks and cereals. Plant foods do not naturally contain it.",
    ],
    seek=[
        "Talk to a doctor if B12 is low, especially with tingling, numbness, balance problems, memory changes or anaemia. They can find the cause and advise on treatment.",
    ],
    limits=["Blood B12 does not always reflect how much B12 your cells can use, so borderline results are sometimes checked with other tests."],
    q=dict(
        high=["Is a high vitamin B12 harmful?", "Why is my B12 high if I don't take supplements?"],
        low=["Can my vitamin B12 be low even if I eat non-vegetarian food?", "What are the signs of low B12?", "Which vegetarian foods have vitamin B12?"],
        normal=["How can I keep my vitamin B12 healthy on a vegetarian diet?", "Do any of my medicines affect B12?"],
    ),
)

C["WB-037"] = dict(
    d="This test measures 25-hydroxy vitamin D, the main form of vitamin D stored in your blood. It is the best guide to your vitamin D levels.",
    body=[
        "Your skin makes vitamin D when exposed to sunlight. Some also comes from food.",
        "Your liver turns it into 25-hydroxy vitamin D, the form this test measures.",
        "Vitamin D helps your gut absorb calcium for strong bones and also supports muscles and immunity.",
    ],
    why=["Low vitamin D is very common and can lead to weak bones, bone pain and muscle weakness."],
    high="Higher vitamin D is almost always caused by taking too much from supplements. Very high levels can raise blood calcium, causing nausea, thirst and kidney problems.",
    low="Lower vitamin D is often due to little time in sunlight, covering most skin, darker skin, staying indoors, extra body weight, or few vitamin D foods. Some gut, liver and kidney conditions also lower it.",
    normal="Your vitamin D is inside the lab's range, which supports healthy bones and muscles.",
    factors=["Sunlight exposure", "Skin colour", "Body weight", "Diet", "Supplements", "Gut, liver or kidney conditions"],
    life=[
        "Sunlight on the skin is the main natural source of vitamin D.",
        "Few foods contain much vitamin D. Oily fish, egg yolks and fortified milk or cereals are the main ones.",
    ],
    support=[
        "Spend some time outdoors in daylight with arms and face uncovered, when safe for your skin. Sunlight helps your skin make vitamin D.",
        "Include vitamin D foods such as eggs, oily fish or fortified milk and cereals if they suit your diet.",
        "Stay physically active with walking or strength exercise. This supports bones and muscles alongside vitamin D.",
    ],
    seek=["Talk to a doctor if vitamin D is low, especially with bone pain or muscle weakness, or if you take high-dose supplements and your level is high. They will advise on any treatment and dose."],
    limits=["Labs use different methods and cut-offs for vitamin D, so the same number may be labelled differently by different labs."],
    q=dict(
        high=["Is high vitamin D harmful?", "Could my supplements be raising my vitamin D too much?"],
        low=["Why is my vitamin D low even though I live in a sunny country?", "How can I raise my vitamin D naturally?", "Can low vitamin D make me tired?"],
        normal=["How can I keep my vitamin D healthy?", "How does vitamin D help my bones?"],
    ),
)

C["WB-038"] = dict(
    d="Vitamin C is a vitamin your body uses to heal wounds, build healthy skin and blood vessels, and absorb iron from plant foods.",
    body=[
        "Your body cannot make or store much vitamin C, so it needs a regular supply from food.",
        "It helps make collagen, a protein that holds skin, gums and blood vessels together.",
        "It also protects cells from damage and helps you absorb iron.",
    ],
    why=["Low vitamin C can cause tiredness, bleeding gums, slow wound healing and poor iron absorption."],
    high="Higher vitamin C usually comes from supplements. Very large doses can upset the stomach and may raise the chance of kidney stones in some people.",
    low="Lower vitamin C usually means you are not eating enough fruit and vegetables. Smoking, heavy alcohol use and some illnesses also lower it.",
    normal="Your vitamin C is inside the lab's range, suggesting you are getting enough from your diet.",
    factors=["Fruit and vegetable intake", "Smoking", "Alcohol", "Illness or inflammation", "Supplements", "Recent meals"],
    life=["Citrus fruits, amla, guava, kiwi, tomatoes, capsicum and leafy greens are rich in vitamin C. Long cooking destroys some of it."],
    support=[
        "Eat at least one fresh fruit or raw vegetable each day, such as amla, guava, orange or tomato. Your body needs a daily supply.",
        "Pair vitamin C foods with iron-rich meals, such as lemon on dal or spinach. This helps you absorb more iron.",
        "If you smoke, ask for help to stop. Smoking uses up vitamin C faster.",
    ],
    seek=["Talk to a doctor if vitamin C is low with bleeding gums, easy bruising or slow healing."],
    limits=["Blood vitamin C reflects recent intake more than long-term stores."],
    q=dict(
        high=["Can too much vitamin C be harmful?"],
        low=["Why is my vitamin C low?", "Which foods are best for vitamin C?", "Does vitamin C help me absorb iron?"],
        normal=["What does vitamin C do in my body?"],
    ),
)

_THY_SEEK = "Talk to a doctor if your thyroid results are abnormal, especially with tiredness, weight change, feeling unusually hot or cold, a racing heart, or changes in periods or mood."

C["WB-039"] = dict(
    d="T3 is one of the two main thyroid hormones. It is the active form that tells your cells how fast to use energy.",
    body=[
        "Your thyroid gland in the neck makes mostly T4 and a smaller amount of T3.",
        "Much of the T3 in your body is made by converting T4 in other tissues.",
        "T3 affects heart rate, body temperature, digestion and energy levels.",
    ],
    why=["T3 helps confirm and judge the severity of an overactive thyroid, and is read with TSH and T4."],
    high="Higher T3 usually points to an overactive thyroid. It can also rise in pregnancy or with some hormone medicines.",
    low="Lower T3 can be seen with an underactive thyroid, but it also often falls during illness, fasting or stress even when the thyroid is healthy.",
    normal="Your T3 is inside the lab's range. It is read together with TSH and T4.",
    factors=["Thyroid gland activity", "Illness or fasting", "Pregnancy", "Some medicines"],
    life=None, support=[],
    seek=[_THY_SEEK],
    limits=["T3 is not a good test on its own for an underactive thyroid, because it often stays normal or falls for other reasons."],
    not_applicable={"lifestyle_relationships": "Thyroid hormone levels are set by thyroid gland activity; no reliable diet or lifestyle effect for most people with adequate iodine.", "practical_guidance": "Abnormal thyroid hormones need medical assessment and, if needed, treatment."},
    q=dict(
        high=["Does a high T3 mean my thyroid is overactive?", "What symptoms can a high T3 cause?"],
        low=["Can illness lower my T3?", "Does a low T3 mean an underactive thyroid?"],
        normal=["What is the difference between T3 and T4?", "Why are TSH, T3 and T4 checked together?"],
    ),
)

C["WB-040"] = dict(
    d="T4 is the main hormone made by your thyroid gland. Your body turns it into T3, the active form that controls how fast your cells use energy.",
    body=[
        "Your thyroid makes T4 when it receives a signal called TSH from the brain.",
        "T4 travels in the blood and is converted into T3 in tissues like the liver.",
        "Together, these hormones set your body's pace, affecting energy, weight, temperature and heart rate.",
    ],
    why=["T4 is used with TSH to check whether the thyroid is underactive or overactive."],
    high="Higher T4 usually points to an overactive thyroid. It can also rise in pregnancy, with some medicines, or if thyroid tablets are at too high a dose.",
    low="Lower T4 usually points to an underactive thyroid. Less often, it comes from a problem with the brain signal that controls the thyroid.",
    normal="Your T4 is inside the lab's range, suggesting your thyroid is making enough of its main hormone.",
    factors=["Thyroid gland activity", "Pregnancy", "Thyroid tablets", "Some medicines and supplements such as biotin"],
    life=None, support=[],
    seek=[_THY_SEEK],
    limits=["Biotin supplements can interfere with some thyroid tests. Tell your doctor if you take biotin."],
    not_applicable={"lifestyle_relationships": "T4 is set by thyroid gland activity; no reliable diet or lifestyle effect for most people with adequate iodine.", "practical_guidance": "Abnormal T4 needs medical assessment and, if needed, treatment."},
    q=dict(
        high=["Does a high T4 mean my thyroid is overactive?"],
        low=["Does a low T4 mean an underactive thyroid?", "Can an underactive thyroid cause weight gain?"],
        normal=["What does T4 do in my body?", "Why are TSH and T4 checked together?"],
    ),
)

C["WB-041"] = dict(
    d="Thyroid-stimulating hormone, or TSH, is a signal from your brain that tells your thyroid gland how much hormone to make. It is the main first test of thyroid health.",
    body=[
        "The pituitary gland in your brain watches your thyroid hormone levels.",
        "If thyroid hormones are low, it sends out more TSH to push the thyroid to work harder.",
        "If thyroid hormones are high, TSH drops. So TSH moves in the opposite direction to thyroid hormones.",
    ],
    why=["TSH is usually the first test to check for an underactive or overactive thyroid, and to adjust thyroid treatment."],
    high="A higher TSH usually means the thyroid is underactive, so the brain is pushing harder. Common causes include autoimmune thyroid disease and thyroid tablets at too low a dose. Mild rises can be temporary, for example after an illness.",
    low="A lower TSH usually means the thyroid is overactive, or thyroid tablets are at too high a dose. Less often, it comes from a problem with the pituitary gland.",
    normal="Your TSH is inside the lab's range, which usually means your thyroid is working normally.",
    factors=["Thyroid gland activity", "Thyroid tablets", "Recent illness", "Pregnancy", "Some medicines", "Biotin supplements"],
    life=["Iodine in food, such as iodised salt, is needed to make thyroid hormones. Most people using iodised salt get enough."],
    support=[
        "If you take thyroid tablets, take them the same way every day, usually on an empty stomach. Consistency keeps your levels steady.",
    ],
    seek=[_THY_SEEK, "Ask about thyroid testing before or early in pregnancy, as thyroid levels matter for the baby."],
    limits=["A single mildly abnormal TSH is often repeated, as illness, timing and some medicines can shift it."],
    q=dict(
        high=["Does a high TSH mean I have an underactive thyroid?", "Can a high TSH make me tired or gain weight?", "Should I get my thyroid tested again?"],
        low=["Does a low TSH mean my thyroid is overactive?", "Can my thyroid tablets lower my TSH?"],
        normal=["What does TSH tell me about my thyroid?", "How often should I check my thyroid?"],
    ),
)
