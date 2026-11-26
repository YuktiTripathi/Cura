"""Education upgrade for liver and blood protein results. Pending clinical review."""

_LIVER_KEEP = [
    "Keep doing what protects your liver: little or no alcohol, few sugary drinks and sweets, regular activity and a steady weight.",
    "Ask before starting herbal, weight-loss or bodybuilding supplements. Some herbal and dietary supplements can injure the liver.",
]

_LIVER_RISK = [
    "About one in three Indian adults has fat in the liver, often without being overweight, so keeping sugar, refined flour and alcohol low is worth it even when you feel well.",
    "Losing 3 to 5% of body weight can reduce liver fat, and regular activity helps the liver even when weight does not change.",
]

_ENZ_MYTH = "Normal liver enzymes do not rule out fatty liver. A good share of people with fat in the liver have normal ALT and AST."

X = {}

X["WB-010"] = dict(
    fx=[
        ("Hydration", "When you are short of water the blood is more concentrated, so albumin reads higher; extra fluid dilutes it."),
        ("Recent illness or inflammation", "During illness the liver switches to making infection-fighting proteins and makes less albumin."),
        ("Liver function", "Albumin is made only in the liver, so long-term liver disease can lower it."),
        ("Protein loss through kidneys", "Damaged kidney filters can leak albumin into urine, lowering the blood level."),
        ("Nutrition", "Very low protein intake over a long time can lower albumin, though illness is a more common cause."),
    ],
    keep=["Eating some protein at each meal, such as dal, curd, paneer, eggs, fish or chicken, gives the liver what it needs to make albumin."],
    myth=["Low albumin is not usually fixed by protein powder. It more often reflects illness, liver or kidney problems that need a doctor to find."],
)

X["WB-011"] = dict(
    fx=[
        ("Bone growth or healing", "Bone-building cells release ALP, so growing children and teenagers, and people healing a fracture, have higher levels."),
        ("Bile duct problems", "When bile cannot flow freely, the cells lining the bile ducts release more ALP into the blood."),
        ("Pregnancy", "ALP is normally higher during pregnancy, separate from any bone or liver cause, so results in pregnancy are judged against pregnancy ranges."),
        ("Vitamin D levels", "A long shortage of vitamin D can soften bones (osteomalacia), which is one cause of a high ALP."),
        ("Thyroid and parathyroid glands", "An overactive thyroid or parathyroid gland speeds up bone turnover and can raise ALP."),
        ("Some medicines", "Some medicines can affect the liver or bile flow and raise ALP."),
    ],
    fix=dict(
        body=[
            "ALP is an enzyme, a protein that speeds up chemical reactions. It is found mainly in the liver, the bile ducts and bone.",
            "Small amounts leak into your blood all the time.",
            "More enters your blood when bile ducts are blocked, or when bone-building cells are busy, as in growing children or a healing fracture.",
            "ALP is also normally higher during pregnancy, which has nothing to do with bone-building.",
        ],
        high="Higher ALP may come from the liver or bile ducts, for example when bile cannot flow freely, or from bone, for example during growth, healing or bone softening from long-term low vitamin D. An overactive thyroid or parathyroid gland can also raise it, and it is normally higher in pregnancy. Your GGT result helps tell whether the liver or bone is the more likely source.",
        low="Low ALP is uncommon. It can go with poor nutrition or low protein, low zinc, thyroid disease, pernicious anaemia (a condition that stops B12 being absorbed), Wilson disease, or a rare inherited bone condition called hypophosphatasia. It is worth mentioning to a doctor rather than ignoring.",
    ),
    keep=None,
    myth=["A high ALP does not always mean a liver problem. In children, teenagers and pregnant women it is often expected, and in adults it may come from bone."],
    na=dict(keeping_healthy="ALP reflects bile flow, bone activity and pregnancy; everyday habits do not set it."),
)

X["WB-012"] = dict(
    fx=[
        ("Bile duct blockage such as gallstones", "A stone or narrowing stops processed bilirubin draining into the gut, so it backs up into the blood."),
        ("Liver inflammation", "Inflamed liver cells cannot pass processed bilirubin into bile as well, so more leaks into the blood."),
        ("Some medicines", "A few medicines slow bile flow inside the liver and raise direct bilirubin."),
    ],
    keep=None,
    myth=["Yellow eyes are not always from eating too much oily food. When direct bilirubin is high, a doctor needs to check the bile ducts and liver."],
    na=dict(keeping_healthy="Direct bilirubin reflects bile drainage; habits do not set it."),
)

X["WB-013"] = dict(
    fx=[
        ("Red blood cell breakdown", "Bilirubin comes from old red cells, so faster breakdown produces more of it."),
        ("Liver function", "The liver processes bilirubin; when it is struggling, bilirubin builds up."),
        ("Bile flow", "Blocked bile ducts stop processed bilirubin leaving the body, so it backs up into the blood."),
        ("Gilbert syndrome", "A common inherited pattern in which the liver processes bilirubin a little slowly. It is not dangerous."),
        ("Fasting or recent illness", "In people with Gilbert syndrome, fasting, poor sleep or illness can raise bilirubin for a while."),
    ],
    fix=dict(high="Higher bilirubin can come from red cells breaking down faster, from liver problems, or from blocked bile flow. A common cause that is not dangerous is Gilbert syndrome, an inherited pattern where bilirubin rises a little, especially with fasting, poor sleep or illness."),
    keep=None,
    myth=["Gilbert syndrome is not liver disease. It is a common inherited pattern that does not damage the liver."],
    na=dict(keeping_healthy="Total bilirubin reflects red cell turnover and liver processing; there is no habit to maintain it."),
)

X["WB-014"] = dict(
    fx=[
        ("Alcohol", "Regular drinking makes liver cells produce more GGT, so it often rises with alcohol use and falls after stopping."),
        ("Fatty liver", "Fat building up in the liver raises GGT, often along with ALT."),
        ("Bile duct problems", "GGT sits in the cells lining the bile ducts and rises when bile does not drain freely."),
        ("Some medicines", "Some medicines, such as certain seizure medicines, make the liver produce more GGT."),
        ("Body weight", "Extra weight goes with fat in the liver, which raises GGT."),
    ],
    keep=_LIVER_KEEP,
    risk=_LIVER_RISK,
    myth=["GGT is not only an alcohol test. Fatty liver, bile duct problems and medicines raise it too."],
)

X["WB-015"] = dict(
    fx=[
        ("Hydration", "Dehydration concentrates the blood and raises total protein; extra fluid dilutes it."),
        ("Inflammation or infection", "Long-term inflammation raises antibodies (globulins), which lifts total protein."),
        ("Liver function", "The liver makes albumin, the largest part of total protein, so liver disease can lower it."),
        ("Protein loss through kidneys", "Kidney filters that leak protein lower the blood level."),
        ("Nutrition", "Very poor nutrition over a long time can lower total protein."),
    ],
    keep=None,
    myth=["Total protein does not show how much protein you eat. It mostly reflects albumin and antibodies made by your body."],
    na=dict(keeping_healthy="Total protein reflects liver, kidney and immune activity rather than a habit."),
)

X["WB-016"] = dict(
    fx=[
        ("Fatty liver", "Fat in liver cells stresses them, so more AST leaks out."),
        ("Alcohol", "Alcohol damages liver cells and tends to raise AST more than ALT."),
        ("Hepatitis", "Viral infections of the liver inflame liver cells and release AST."),
        ("Intense exercise", "Hard workouts strain muscles, which also contain AST, so levels can rise for a day or two."),
        ("Muscle injury", "Injured muscle releases AST into the blood."),
        ("Some medicines", "Some medicines and supplements can strain the liver and raise AST."),
    ],
    keep=_LIVER_KEEP,
    risk=_LIVER_RISK,
    myth=[_ENZ_MYTH, "A high AST is not always the liver. Muscles contain AST too, so a recent hard workout can raise it."],
)

X["WB-017"] = dict(
    fx=[
        ("Fatty liver", "Fat in liver cells is the most common reason ALT rises in India."),
        ("Alcohol", "Alcohol damages liver cells and releases ALT."),
        ("Viral hepatitis", "Hepatitis B and C infect liver cells and can raise ALT for years."),
        ("Body weight", "Extra weight, especially around the waist, goes with fat in the liver."),
        ("Some medicines and supplements", "Some medicines and herbal or dietary supplements can injure liver cells."),
    ],
    keep=_LIVER_KEEP,
    risk=_LIVER_RISK,
    myth=[_ENZ_MYTH, "The size of the ALT rise does not show how serious liver disease is."],
)

X["WB-018"] = dict(
    fx=[
        ("Red blood cell breakdown", "When red cells break down faster, more unprocessed bilirubin is made than the liver can handle at once."),
        ("Gilbert syndrome", "In Gilbert syndrome the liver processes bilirubin slowly, so the unprocessed part rises a little."),
        ("Fasting or illness", "Long gaps without food, poor sleep or illness raise it in people with Gilbert syndrome."),
    ],
    keep=None,
    myth=["A mildly high indirect bilirubin with normal liver enzymes is often Gilbert syndrome, which is not dangerous."],
    na=dict(keeping_healthy="Indirect bilirubin reflects red cell turnover and inherited liver handling."),
)

X["WB-019"] = dict(
    fx=[
        ("Inflammation or infection", "Long-lasting infection or inflammation makes the immune system produce more antibodies, which are globulins."),
        ("Immune conditions", "Autoimmune conditions can raise antibody levels."),
        ("Liver function", "Long-term liver disease can raise globulins while albumin falls."),
        ("Protein loss", "Losing protein through the kidneys or gut can lower globulins."),
    ],
    keep=None,
    myth=["Globulin is not one protein. It is a group, including antibodies, so a high result needs more tests to see which part is raised."],
    na=dict(keeping_healthy="Globulin reflects immune and liver activity; habits do not set it."),
)

X["WB-020"] = dict(
    fx=[
        ("Albumin level", "A lower albumin, from illness, liver or kidney problems, pulls the ratio down."),
        ("Globulin level", "Higher antibody levels, from long-term inflammation or immune conditions, also pull the ratio down."),
    ],
    keep=None,
    myth=["The ratio adds little when albumin and globulin are both normal."],
    na=dict(keeping_healthy="A calculated ratio that follows albumin and globulin."),
)

X["WB-021"] = dict(
    fx=[
        ("AST level", "AST rises with alcohol-related liver damage, scarring and muscle strain, which pushes the ratio up."),
        ("ALT level", "ALT rises most with fatty liver and viral hepatitis, which pushes the ratio down."),
    ],
    keep=None,
    myth=["The ratio is not a diagnosis. It only hints at a pattern when AST or ALT is raised."],
    na=dict(keeping_healthy="A calculated ratio that follows AST and ALT."),
)
