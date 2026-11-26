"""Education upgrade for urine results. Pending clinical review.

Most urine items have an unconfirmed lab method, so they stay unlabelled; the factor explanations say how
each factor changes what the strip or microscope sees.
"""

_NA = dict(keeping_healthy="A urine finding that reflects a cause to be found, not a habit to maintain.")
_UTI = ("Urine infection", "Bacteria in the bladder or kidneys cause inflammation, which this finding can pick up.")
_CONTAM = ("Sample contamination", "If the first part of the stream or skin touches the sample, cells and bacteria from outside the bladder get in. A clean midstream sample avoids this.")

X = {}

X["WB-071"] = dict(
    fx=[
        ("Diet", "Meat-heavy diets make urine more acidic; fruit- and vegetable-rich diets make it less acidic."),
        ("Hydration", "Concentrated urine is often more acidic."),
        _UTI,
        ("Kidney function", "Kidneys balance acid by changing urine pH, so some kidney conditions alter it."),
        ("Some medicines", "Antacids and some other medicines change urine pH."),
    ],
    keep=["Enough water and plenty of vegetables and fruit help keep urine pH in a comfortable range."],
    myth=["Urine pH does not show the acidity of your blood or body. Blood pH stays tightly controlled whatever the urine shows."],
)
X["WB-089"] = dict(
    fx=[
        ("Fluid intake", "Drinking less water makes urine more concentrated; drinking a lot dilutes it."),
        ("Sweating", "Heat and exercise lose water through sweat, concentrating urine."),
        ("Vomiting or diarrhoea", "Fluid loss concentrates urine."),
        ("Sugar or protein in urine", "Dissolved sugar or protein raises the reading."),
        ("Kidney function", "Kidneys that cannot concentrate urine give a fixed, dilute reading."),
    ],
    keep=["Drinking water steadily through the day, more in hot weather, keeps urine pale yellow."],
    myth=["Very pale urine all the time is not always healthier. Drinking far more than you need can dilute body salts."],
)
X["WB-090"] = dict(
    fx=[("Amount collected", "This only records how much urine was in the container.")],
    keep=None, myth=[], na=dict(keeping_healthy="Describes the sample, not the body.", misconceptions="A sample description has no misconceptions to address."),
)
X["WB-072"] = dict(
    fx=[
        ("Liver function", "When the liver struggles to clear urobilinogen from the blood, more appears in urine."),
        ("Red blood cell breakdown", "Faster red cell breakdown makes more bilirubin, and more urobilinogen."),
        ("Bile flow", "If bile cannot reach the gut, gut bacteria make no urobilinogen, so it disappears from urine."),
        ("Antibiotics", "Antibiotics reduce the gut bacteria that make urobilinogen."),
    ],
    keep=None, myth=["Small amounts of urobilinogen in urine are normal."], na=_NA,
)
X["WB-073"] = dict(
    fx=[
        ("Hydration", "Less water makes urine darker yellow; more water makes it paler."),
        ("Foods such as beetroot", "Beetroot, berries and some food colours can tint urine pink or red."),
        ("Vitamins and medicines", "B vitamins make urine bright yellow; some medicines turn it orange, green or blue."),
        ("Blood or bile in urine", "Blood makes urine pink, red or cola-coloured; bile pigments make it dark brown."),
    ],
    keep=["Pale yellow urine is a simple sign you are drinking enough."],
    myth=["Dark urine is not always dehydration. Dark brown urine with yellow eyes can mean a liver or bile problem."],
)
X["WB-074"] = dict(
    fx=[
        ("Sample standing time", "Urine left standing becomes cloudy as crystals form and bacteria grow."),
        ("Crystals", "Phosphate and urate crystals, often harmless, cloud urine."),
        _UTI,
        ("Mucus or cells", "Mucus and lining cells make urine hazy."),
        ("Diet", "Some foods raise phosphate in urine and cloud it."),
    ],
    keep=None, myth=["Cloudy urine is not always infection. Crystals and standing time are common reasons."], na=_NA,
)
X["WB-075"] = dict(
    fx=[
        ("Blood sugar level", "Kidneys let sugar into urine once blood sugar rises above about 180 mg/dL."),
        ("Diabetes medicines called SGLT2 inhibitors", "These medicines deliberately pass sugar into urine."),
        ("Pregnancy", "Kidneys let more sugar through in pregnancy."),
        ("Kidney handling of sugar", "A few people have kidneys that let sugar through at normal blood sugar levels."),
    ],
    keep=None, myth=["No sugar in urine does not mean blood sugar is normal. It only appears once blood sugar is quite high."], na=_NA,
)
X["WB-076"] = dict(
    fx=[
        _UTI,
        ("Kidney stones", "Stones scratch the lining of the urinary tract and cause bleeding."),
        ("Menstrual blood", "A sample during or near a period often contains blood."),
        ("Hard exercise", "Strenuous exercise can cause a little blood in urine for a day or two."),
        ("Muscle injury", "Damaged muscle releases myoglobin, which the strip reads as blood."),
    ],
    keep=None, myth=["A positive strip without red cells under the microscope may be myoglobin, a protein released from damaged muscle, not blood."], na=_NA,
)
X["WB-077"] = dict(
    fx=[
        _UTI,
        ("Kidney stones", "Stones cause bleeding from the urinary lining."),
        ("Menstrual blood", "Period blood can enter the sample."),
        ("Hard exercise", "Strenuous exercise can add red cells to urine briefly."),
        ("Kidney or bladder conditions", "Kidney inflammation and, less often, growths in the bladder or kidney cause bleeding."),
    ],
    keep=None, myth=["Blood in urine that you cannot see still needs a repeat test, especially in people over 40 or smokers."], na=_NA,
)
X["WB-078"] = dict(
    fx=[
        _UTI,
        _CONTAM,
        ("Kidney inflammation", "Inflamed kidneys release white cells into urine."),
        ("Sexually transmitted infections", "Infections of the urethra release white cells."),
    ],
    keep=None, myth=["Pus cells without symptoms are often contamination, and do not always need antibiotics."], na=_NA,
)
X["WB-079"] = dict(
    fx=[
        ("Sample collection technique", "Lining cells from the skin around the urethra enter a sample that is not midstream."),
        ("Inflammation of the urinary tract", "Inflamed linings shed more cells."),
    ],
    keep=None, myth=["A few lining cells are normal and usually reflect how the sample was collected."], na=_NA,
)
X["WB-080"] = dict(
    fx=[
        ("Hydration", "Concentrated urine lets crystals form."),
        ("Diet", "Foods rich in oxalate, such as spinach and nuts, or purines can add crystals."),
        ("Urine pH", "Different crystals form in acidic and alkaline urine."),
        ("Sample cooling", "Crystals form as urine cools in the container, so many are not present in the body."),
    ],
    keep=["Drinking enough water keeps urine dilute, which makes crystals less likely to form."],
    myth=["Crystals in a sample are not kidney stones. Many form only after the urine has cooled."],
)
X["WB-081"] = dict(
    fx=[
        ("Exercise", "Hard exercise can produce a few harmless casts."),
        ("Dehydration", "Concentrated urine favours cast formation."),
        ("Kidney conditions", "Some casts, especially those containing cells, form inside damaged kidney tubules."),
    ],
    keep=None, myth=["A few clear casts are often harmless; casts containing cells need a doctor's view."], na=_NA,
)
X["WB-082"] = dict(
    fx=[
        _UTI,
        _CONTAM,
        ("Delay before testing", "Bacteria multiply in urine left at room temperature, so delays raise the count."),
    ],
    keep=None, myth=["Bacteria in urine without symptoms usually do not need antibiotics, except in pregnancy or before some procedures."], na=_NA,
)
X["WB-083"] = dict(
    fx=[
        _CONTAM,
        ("Diabetes or high blood sugar", "Sugar in urine feeds yeast."),
        ("Recent antibiotics", "Antibiotics clear normal bacteria and let yeast grow."),
        ("Pregnancy", "Hormone changes make yeast infections more common."),
    ],
    keep=None, myth=["Yeast in a sample is often from the skin or vagina rather than the bladder."], na=_NA,
)
X["WB-084"] = dict(
    fx=[
        ("Urine infection", "Many bacteria that cause urine infections turn nitrate into nitrite, which the strip detects."),
        ("Time the urine stayed in the bladder", "Bacteria need about four hours to make nitrite, so first-morning urine is best."),
        ("Diet", "Low vegetable intake means less nitrate in urine to convert."),
    ],
    keep=None, myth=["A negative nitrite does not rule out infection. Some bacteria do not make it."], na=_NA,
)
X["WB-085"] = dict(
    fx=[
        ("Fasting", "When you do not eat, the body burns fat and makes ketones."),
        ("Low-carbohydrate diets", "Very low carbohydrate eating makes the body switch to fat for fuel."),
        ("Vomiting or illness", "Not keeping food down raises ketones."),
        ("Diabetes", "Without enough insulin, cells cannot use sugar and burn fat, producing ketones; high levels in diabetes can be dangerous."),
        ("Intense exercise", "Long hard exercise raises ketones."),
    ],
    keep=None, myth=["Ketones after fasting are expected, but ketones with high blood sugar in diabetes need urgent care."], na=_NA,
)
X["WB-086"] = dict(
    fx=[
        ("Kidney filter damage", "Healthy filters keep protein in the blood; damaged ones let it leak."),
        ("Diabetes", "High blood sugar over years damages the filters."),
        ("High blood pressure", "Long-term high pressure damages the filters."),
        ("Fever or hard exercise", "Both can cause a brief, harmless rise."),
        ("Urine infection", "Infection can add protein to urine."),
    ],
    keep=None, myth=["One positive protein strip after exercise or fever is often temporary, so it is repeated before drawing conclusions."], na=_NA,
)
X["WB-087"] = dict(
    fx=[
        ("Urine infection", "White cells release this enzyme, so a positive strip suggests white cells are present."),
        _CONTAM,
        ("Kidney inflammation", "Inflamed kidneys release white cells."),
    ],
    keep=None, myth=["A positive strip alone does not confirm infection; symptoms and culture matter."], na=_NA,
)
X["WB-088"] = dict(
    fx=[
        ("Liver inflammation", "An inflamed liver lets processed bilirubin into the blood, and kidneys pass it into urine."),
        ("Bile duct blockage", "When bile cannot drain, processed bilirubin spills into urine and darkens it."),
        ("Sample exposed to light", "Bilirubin breaks down in light, so a delayed sample can read falsely negative."),
    ],
    keep=None, myth=["Bile in urine is never normal. Dark urine with yellow eyes needs prompt medical advice."], na=_NA,
)
X["WB-091"] = dict(
    fx=[
        ("Sample collection", "How the sample was collected changes what the lab sees."),
        ("Lab notes", "These are free-text remarks, so their meaning depends on what was written."),
    ],
    keep=None, myth=[], na=dict(keeping_healthy="Free-text lab notes.", misconceptions="Depends on the note; nothing general applies."),
)
