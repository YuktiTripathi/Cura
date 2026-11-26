"""Education upgrade for kidney, salt and mineral results. Pending clinical review."""

_KIDNEY_KEEP = [
    "Keep blood pressure and blood sugar in a healthy range. They are the two most common causes of kidney damage.",
    "Drink water through the day, more in heat or after sweating, and use painkillers such as ibuprofen or diclofenac only as advised.",
]
_KIDNEY_RISK = [
    "If you have diabetes or high blood pressure, ask how often your kidneys should be checked. Kidney damage is often silent until late.",
    "Keeping salt low helps blood pressure, which protects the kidney filters.",
]
_HYD = ("Hydration", "Being short of water concentrates the blood and slows kidney filtering for a while, so this result can read higher; it settles once you drink normally.")
_KIDNEY_FX = ("Kidney function", "Healthy kidneys keep this level steady; when filtering falls, the level drifts out of range.")

X = {}

X["WB-022"] = dict(
    fx=[
        _HYD,
        ("Protein intake", "Urea nitrogen is made when the body breaks down protein, so a high-protein diet raises it a little and a very low one lowers it."),
        _KIDNEY_FX,
        ("Bleeding in the gut", "Blood digested in the gut is a large protein load, which raises BUN."),
        ("Liver function", "The liver makes urea, so severe liver disease can lower BUN."),
        ("Some medicines", "Steroids and some antibiotics can raise BUN."),
    ],
    keep=_KIDNEY_KEEP,
    myth=["A high BUN on its own does not mean kidney failure. Dehydration is a very common reason, which is why it is read with creatinine."],
)
X["WB-027"] = dict(fx=X["WB-022"]["fx"][:5], keep=_KIDNEY_KEEP,
                   myth=["Urea and BUN measure the same waste in different units, so they move together."])

X["WB-023"] = dict(
    fx=[
        ("Albumin level", "About half of blood calcium travels on albumin, so a low albumin makes total calcium read low even when the active calcium is normal."),
        ("Vitamin D", "Vitamin D helps your gut absorb calcium; a long shortage can lower it."),
        ("Parathyroid hormone", "This hormone raises calcium by drawing it from bone and keeping it in the kidneys; an overactive parathyroid gland raises calcium."),
        ("Kidney function", "Kidneys activate vitamin D and balance calcium, so kidney disease can upset the level."),
        ("Calcium or vitamin D supplements", "Large doses, especially of vitamin D, can push calcium too high."),
        ("Hydration", "Dehydration concentrates the blood and can raise calcium a little."),
    ],
    keep=["Calcium in food, such as milk, curd, paneer, ragi, sesame and green leafy vegetables, along with enough vitamin D, supports bones."],
    myth=["Blood calcium does not show how strong your bones are. The body keeps blood calcium steady by taking it from bone if needed."],
)

X["WB-024"] = dict(
    fx=[
        ("Hydration", "Chloride follows water and sodium, so dehydration raises it and too much water lowers it."),
        ("Vomiting or diarrhoea", "Vomiting loses stomach acid, which contains chloride, so the level falls; severe diarrhoea can raise it."),
        _KIDNEY_FX,
        ("Water tablets (diuretics)", "Diuretics make the kidneys pass more salt and water and can lower chloride."),
        ("Salt intake", "Table salt is sodium chloride, though in healthy kidneys the effect on blood chloride is small."),
    ],
    keep=None,
    myth=["Chloride is rarely a problem on its own. It is read with sodium and bicarbonate to understand fluid and acid balance."],
    na=dict(keeping_healthy="Chloride is held steady by the kidneys; there is no specific habit to maintain it."),
)

X["WB-025"] = dict(
    fx=[
        ("Muscle mass", "Creatinine comes from normal muscle wear, so people with more muscle make more of it."),
        _HYD,
        _KIDNEY_FX,
        ("Meat eaten before the test", "Cooked meat contains creatine, which turns into creatinine, so a large meat meal can raise the level for some hours."),
        ("Creatine supplements", "Creatine taken for training is turned into creatinine and can make the result read high."),
        ("Some medicines", "Some medicines stop the kidneys releasing creatinine, raising the level without kidney damage."),
    ],
    keep=_KIDNEY_KEEP,
    risk=_KIDNEY_RISK,
    myth=["A high creatinine in a muscular person or someone taking creatine may not mean kidney damage. Doctors may use other tests to check."],
)

X["WB-026"] = dict(
    fx=[
        ("Fluid intake", "Drinking far more water than the kidneys can clear dilutes sodium; drinking too little raises it."),
        ("Vomiting or diarrhoea", "Losing fluid and salt can push sodium either way, depending on what is lost and replaced."),
        ("Water tablets and some other medicines", "Diuretics and some antidepressants and seizure medicines can lower sodium."),
        _KIDNEY_FX,
        ("Hormone conditions", "Problems with the thyroid, adrenal glands or the hormone that controls water can change sodium."),
    ],
    keep=None,
    myth=["Blood sodium is not a measure of how much salt you eat. Healthy kidneys keep it steady whatever your intake, though salt still affects blood pressure."],
    na=dict(keeping_healthy="Blood sodium is held steady by the kidneys and hormones."),
)

X["WB-028"] = dict(
    fx=[
        ("Purine-rich foods", "Purines in red meat, organ meat and some seafood are broken down into uric acid."),
        ("Alcohol, especially beer", "Alcohol makes the body produce more uric acid and the kidneys clear less; beer is also rich in purines."),
        ("Sugary drinks", "Fructose in sugary drinks and fruit juice raises uric acid production."),
        ("Body weight", "Extra weight goes with higher uric acid, and losing weight lowers it."),
        _KIDNEY_FX,
        ("Water tablets (diuretics)", "Some diuretics reduce how much uric acid the kidneys release."),
    ],
    keep=["Plenty of water, few sugary drinks and little alcohol help keep uric acid healthy."],
    risk=["If you have had gout or kidney stones, keeping uric acid down lowers the chance of another attack."],
    myth=["High uric acid does not always cause gout or kidney stones; many people with high levels have no health problems.", "Dal and vegetables are not the main problem for most people with high uric acid. Alcohol, sugary drinks, red and organ meat matter more."],
)

for _k, _top in [("WB-029", "BUN level"), ("WB-030", "Urea level")]:
    X[_k] = dict(
        fx=[
            ("Hydration", "Dehydration raises urea more than creatinine, so the ratio goes up."),
            ("Protein intake", "A high-protein diet or bleeding in the gut raises urea and the ratio."),
            (_top, "The top of the ratio; anything that raises urea nitrogen raises the ratio."),
            ("Creatinine level", "The bottom of the ratio; more muscle or reduced kidney filtering raises creatinine."),
        ],
        keep=None,
        myth=["The ratio does not measure kidney function by itself. It helps a doctor think about dehydration or bleeding when urea is raised."],
        na=dict(keeping_healthy="A calculated ratio that follows urea and creatinine."),
    )

X["WB-031"] = dict(
    fx=[
        ("Creatinine level", "eGFR is calculated from creatinine, so anything that raises creatinine lowers eGFR."),
        ("Age", "Kidney filtering slowly falls with age, and the formula allows for this."),
        ("Muscle mass", "Very muscular people can have a falsely low eGFR, and very slim people a falsely high one."),
        ("Hydration", "Dehydration can lower eGFR for a while."),
        ("Diabetes", "High blood sugar over years damages the tiny kidney filters."),
        ("High blood pressure", "Long-term high pressure damages kidney blood vessels and filters."),
    ],
    keep=_KIDNEY_KEEP,
    risk=_KIDNEY_RISK,
    fix=dict(low="A lower eGFR means the kidneys are filtering less blood. A single low result can be caused by dehydration or a large meat meal before the test, so doctors repeat it and check urine before deciding whether it means kidney disease."),
    myth=["One low eGFR is not a diagnosis. Doctors repeat the test and look at urine results before deciding."],
    thr="Lab ranges for eGFR vary. NIDDK notes that an eGFR below 60 may mean kidney disease, whatever the printed range, so a result under 60 is worth discussing with a doctor.",
)

X["WB-032"] = dict(
    fx=[
        _KIDNEY_FX,
        ("Vitamin D", "Vitamin D helps the gut absorb phosphate."),
        ("Parathyroid hormone", "This hormone makes the kidneys pass more phosphate, lowering the blood level."),
        ("Nutrition", "Poor nutrition or refeeding after starvation can lower phosphate."),
        ("Alcohol", "Heavy drinking can lower phosphate."),
        ("Some antacids", "Antacids containing aluminium or calcium bind phosphate in the gut and lower it."),
    ],
    keep=None,
    myth=["Phosphate is rarely about diet alone in healthy people. It mainly reflects kidney and hormone balance."],
    na=dict(keeping_healthy="Phosphate is held steady by kidneys and hormones."),
)

X["WB-033"] = dict(
    fx=[
        _KIDNEY_FX,
        ("Water tablets and some blood pressure medicines", "Some medicines and supplements raise potassium, and water tablets (diuretics) can push it up or down."),
        ("Vomiting or diarrhoea", "Fluid loss from the gut can lower potassium."),
        ("Sample handling", "Clenching your fist hard during the blood draw can raise potassium for a while and give an incorrect result."),
        ("Potassium supplements", "Supplements or salt substitutes can raise it, especially with kidney problems."),
    ],
    keep=None,
    myth=["A single high potassium is often a sample problem, but it is still repeated quickly because a truly high level can affect the heart."],
    na=dict(keeping_healthy="Potassium is held steady by the kidneys."),
)

X["WB-034"] = dict(
    fx=[
        ("Diet", "Whole grains, dal, nuts, seeds and green vegetables supply magnesium; diets low in these can be low in it."),
        ("Alcohol", "Heavy drinking makes the kidneys pass more magnesium."),
        ("Diarrhoea", "Long-lasting diarrhoea loses magnesium from the gut."),
        ("Diabetes", "Poorly controlled diabetes makes the kidneys pass more magnesium."),
        ("Water tablets or acid-reducing medicines", "Some diuretics and long-term acid-reducing tablets lower magnesium."),
        ("Kidney function", "Kidney disease can raise magnesium, especially with magnesium-containing antacids."),
    ],
    keep=["Whole grains, dal, nuts and seeds, and green leafy vegetables are everyday sources of magnesium."],
    myth=["Blood magnesium can look normal even when body stores are a little low, because most magnesium sits inside cells and bone."],
)

X["WB-035"] = dict(
    fx=[
        ("Diet", "Zinc comes from dal, nuts, seeds, whole grains, dairy, eggs and meat; phytates, natural compounds in some grains and pulses, reduce how much is absorbed."),
        ("Gut absorption", "Gut conditions can reduce absorption."),
        ("Inflammation or illness", "During illness zinc moves out of the blood into tissues, so the blood level falls without a true shortage."),
        ("Alcohol", "Alcohol reduces absorption and increases loss."),
        ("Zinc supplements", "Supplements raise the level; very high doses can lower copper."),
        ("Time of day the sample was taken", "Zinc is highest in the morning and falls after meals."),
    ],
    keep=["A varied diet with dal, nuts, seeds and whole grains supplies zinc for most people."],
    myth=["A low zinc during an illness may not mean you need supplements. The level often recovers once the illness settles."],
)
