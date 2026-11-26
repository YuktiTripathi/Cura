"""Revision 2.3.1 content: urine routine and microscopy. Pending clinical review."""

C = {}

_UTI_SEEK = "See a doctor if you have burning when passing urine, needing to go often, cloudy or smelly urine, lower tummy pain, fever or pain in your back or side."
_URINE_LIMIT = "Urine results can change with how the sample was collected, how concentrated it was and how long it waited before testing."
_ASSAY = "The lab's method and reporting format for this item are not confirmed, so CURA does not label the result. Use the wording on your report and ask the lab or your doctor if it is unclear."
_NA_HABIT = {"lifestyle_relationships": "Urine finding that reflects kidney, bladder or body chemistry; no direct habit link beyond hydration.", "practical_guidance": "An abnormal finding needs medical assessment rather than lifestyle change."}


def _u(d, body, why, factors, seek, limits, q, life=None, support=None, na=None, cond=None, assay=_ASSAY):
    return dict(d=d, body=body, why=why, factors=factors, seek=seek, limits=limits, q=dict(assay_unconfirmed=q),
                life=life, support=support or [], not_applicable=na if na is not None else dict(_NA_HABIT), cond=cond, assay=assay)


C["WB-071"] = dict(
    d="Urine pH shows how acidic or alkaline your urine is. Your kidneys adjust it to keep your blood's acid balance steady.",
    body=["A lower number means more acidic urine, and a higher number means more alkaline urine.", "Diet changes urine pH: meat tends to make it more acidic, while vegetables and fruit make it more alkaline."],
    why=["Urine pH can help explain kidney stones and infections and is part of routine urine testing."],
    high="More alkaline urine can follow a vegetable-rich diet, some urine infections or some medicines. It can favour certain types of kidney stones.",
    low="More acidic urine can follow a high-protein diet, dehydration, fasting or uncontrolled diabetes. It can favour uric acid stones.",
    normal="Your urine pH is inside the lab's range.",
    factors=["Diet", "Hydration", "Urine infection", "Kidney function", "Some medicines"],
    life=["Diets high in meat make urine more acidic; fruit and vegetables make it more alkaline."],
    support=["Drink water regularly through the day. Well-diluted urine lowers the chance of stones whatever the pH."],
    seek=["Talk to a doctor if you have had kidney stones or urine infections and your pH is outside the range."],
    limits=[_URINE_LIMIT],
    q=dict(high=["What does alkaline urine mean?", "Can diet change my urine pH?"], low=["What does acidic urine mean?", "Is acidic urine linked with kidney stones?"], normal=["What does urine pH tell me?"]),
)

C["WB-089"] = dict(
    d="Urine specific gravity shows how concentrated your urine is. It is a quick guide to how well hydrated you are and how well your kidneys concentrate urine.",
    body=["When you drink less, your kidneys hold on to water and urine becomes more concentrated.", "When you drink more, urine becomes more dilute."],
    why=["It helps judge hydration and can hint at kidney or hormone problems."],
    high="A higher specific gravity usually means concentrated urine from not drinking enough, sweating, vomiting or diarrhoea. Sugar or protein in the urine can also raise it.",
    low="A lower specific gravity means dilute urine, usually from drinking a lot. If it stays low, it can mean the kidneys are not concentrating urine well.",
    normal="Your urine concentration is inside the lab's range.",
    factors=["Fluid intake", "Sweating", "Vomiting or diarrhoea", "Sugar or protein in urine", "Kidney function"],
    life=["How much you drink is the main everyday influence."],
    support=["Drink water regularly, more in hot weather or when active. Pale yellow urine is a simple sign you are drinking enough."],
    seek=["Talk to a doctor if your urine is always very dilute even when you drink little, or always very concentrated despite drinking well."],
    limits=[_URINE_LIMIT],
    q=dict(high=["Does concentrated urine mean I'm dehydrated?"], low=["Why is my urine very dilute?"], normal=["What does urine specific gravity tell me?"]),
)

C["WB-090"] = dict(
    d="This records the volume of the urine sample that was tested. It describes the sample, not how much urine you pass in a day.",
    body=["Labs note the sample volume to check there was enough to test."],
    why=["It helps the lab judge whether the sample was adequate."],
    high="A larger sample simply means more urine was collected.",
    low="A small sample can limit how much testing the lab can do.",
    normal="The sample volume was adequate for testing.",
    factors=["Amount collected"],
    life=None, support=[],
    seek=["No action is needed for this item on its own."],
    limits=["The sample volume does not show how much urine you make each day."],
    not_applicable={"lifestyle_relationships": "Describes the sample, not the body.", "practical_guidance": "Describes the sample, not the body.", "when_to_seek_care": "Not a health measurement.", "interpretation": "Sample description only."},
    q=dict(high=["What does sample volume mean on my urine report?"], low=["Was my urine sample too small?"], normal=["What does sample volume mean on my urine report?"]),
)

C["WB-072"] = _u(
    "Urobilinogen is a substance made in the gut from bilirubin, the yellow pigment from old red blood cells. A small amount normally appears in urine.",
    ["Bilirubin from the liver passes into the gut, where bacteria turn it into urobilinogen.", "Some is reabsorbed into the blood and passes out in urine."],
    ["Changes can point to liver problems, red cell breakdown or blocked bile flow."],
    ["Liver function", "Red blood cell breakdown", "Bile flow", "Antibiotics"],
    ["Talk to a doctor if urobilinogen is abnormal together with yellow eyes or skin, dark urine or pale stools."],
    ["Urobilinogen is a screening clue only; blood liver tests give a clearer picture."],
    ["What does urobilinogen in urine mean?", "Is urobilinogen linked to my liver?"],
)

C["WB-073"] = _u(
    "Urine colour describes how your urine sample looked. Pale yellow is typical.",
    ["Urine gets its colour from a pigment called urochrome.", "Drinking less makes urine darker, and drinking more makes it paler."],
    ["Colour gives quick clues about hydration and, sometimes, blood, bile or medicines in the urine."],
    ["Hydration", "Foods such as beetroot", "Vitamins and medicines", "Blood or bile in urine"],
    ["See a doctor if urine is red, brown or cola-coloured without an obvious food or medicine cause, or dark with yellow eyes."],
    ["Colour alone cannot identify the cause of a change."],
    ["Why is my urine dark yellow?", "Can foods or vitamins change my urine colour?"],
    life=["Hydration, some foods and B vitamins change urine colour."],
    support=["Drink water regularly. Pale yellow urine is a simple sign of good hydration."],
    na={},
)

C["WB-074"] = _u(
    "Urine clarity describes whether your urine sample was clear or cloudy.",
    ["Fresh urine is usually clear.", "Cloudiness can come from crystals, cells, bacteria, mucus or simply from the sample cooling."],
    ["Cloudy urine can be a clue to infection or crystals, but often has a harmless cause."],
    ["Sample standing time", "Crystals", "Infection", "Mucus or cells", "Diet"],
    [_UTI_SEEK],
    ["Clarity alone cannot show the cause; microscopy results help."],
    ["Why was my urine cloudy?", "Does cloudy urine mean an infection?"],
)

C["WB-075"] = _u(
    "This checks whether sugar (glucose) is present in your urine. Normally there is little or none.",
    ["Your kidneys filter sugar but usually reabsorb all of it.", "When blood sugar is very high, the kidneys cannot keep up and sugar spills into urine."],
    ["Sugar in the urine can be a sign of high blood sugar or diabetes."],
    ["Blood sugar level", "Diabetes medicines called SGLT2 inhibitors", "Pregnancy", "Kidney handling of sugar"],
    ["Talk to a doctor if sugar is found in your urine, so your blood sugar can be checked. Note that some diabetes medicines cause sugar in urine on purpose."],
    ["Urine sugar does not measure current blood sugar and is not used to diagnose diabetes."],
    ["Does sugar in my urine mean I have diabetes?", "Can my medicine cause sugar in my urine?"],
    cond={"if_qualitative_assay_confirmed": {"positive": ["Sugar in urine can mean blood sugar has been high, or that the kidneys pass sugar more easily. Some diabetes medicines do this on purpose."], "negative": ["No sugar was found. This does not rule out diabetes, which is checked with blood tests."]}},
)

C["WB-076"] = _u(
    "This dipstick test looks for traces of blood in your urine, which may not be visible to the eye.",
    ["The test reacts with haemoglobin from red blood cells.", "The test can also react with myoglobin, a muscle protein released after muscle injury."],
    ["Blood in urine can come from infection, stones, hard exercise, periods or, less often, kidney or bladder disease."],
    ["Urine infection", "Kidney stones", "Menstrual blood", "Hard exercise", "Muscle injury"],
    ["Talk to a doctor if blood is found in your urine and you were not on your period, especially if you are over 40, smoke or see visible blood."],
    ["The dipstick does not show where the blood comes from, and a positive test needs microscopy and often a repeat sample."],
    ["What does blood in my urine mean?", "Can my period affect a urine test?"],
    cond={"if_qualitative_assay_confirmed": {"positive": ["Traces of blood were detected. Periods, infection, stones and hard exercise are common causes, and a repeat test is usually advised."], "negative": ["No blood was detected by the dipstick."]}},
)

C["WB-077"] = _u(
    "This counts red blood cells seen under a microscope in your urine sample. A few can be normal.",
    ["Red cells can enter urine anywhere from the kidneys to the bladder.", "Microscopy confirms what a dipstick blood test suggests."],
    ["More than a few red cells can point to infection, stones, injury or kidney or bladder conditions."],
    ["Urine infection", "Kidney stones", "Menstrual blood", "Hard exercise", "Kidney or bladder conditions"],
    ["Talk to a doctor if red cells are reported in your urine and you were not on your period, especially if you are over 40 or smoke."],
    ["Microscopy does not show the source of the bleeding."],
    ["What do red blood cells in my urine mean?", "Should I repeat my urine test?"],
)

C["WB-078"] = _u(
    "This counts white blood cells, sometimes called pus cells, seen in your urine sample. A few can be normal.",
    ["White cells fight infection.", "Many white cells in urine usually mean there is inflammation or infection in the urinary tract."],
    ["Raised white cells in urine are a common sign of a urine infection."],
    ["Urine infection", "Sample contamination", "Kidney inflammation", "Sexually transmitted infections"],
    [_UTI_SEEK],
    ["White cells can come from skin or vaginal contamination if the sample was not a clean midstream catch."],
    ["Do pus cells in my urine mean an infection?", "How should I collect a clean urine sample?"],
)

C["WB-079"] = _u(
    "Epithelial cells are cells from the lining of the urinary tract or skin, seen in your urine sample.",
    ["Small numbers are normal as linings shed old cells.", "Many cells usually mean the sample picked up skin cells during collection."],
    ["Epithelial cells mainly help the lab judge sample quality."],
    ["Sample collection technique", "Inflammation of the urinary tract"],
    ["Usually no action is needed. Repeat with a clean midstream sample if many cells are reported."],
    ["A high count usually reflects contamination rather than disease."],
    ["What are epithelial cells in my urine?", "Was my urine sample contaminated?"],
)

C["WB-080"] = _u(
    "Crystals are tiny solid particles that can form in urine from minerals and salts.",
    ["Crystals form when urine is concentrated or its acid balance favours them.", "Many types are harmless and appear when the sample cools."],
    ["Some crystal types can be linked with kidney stones."],
    ["Hydration", "Diet", "Urine pH", "Sample cooling"],
    ["Talk to a doctor if you have had kidney stones, or have side or back pain, and crystals are reported."],
    ["Crystals in a sample do not mean you have or will get kidney stones."],
    ["Do crystals in my urine mean kidney stones?", "Can drinking more water help?"],
    life=["Concentrated urine from low fluid intake makes crystals more likely."],
    support=["Drink water regularly through the day. Dilute urine makes crystals less likely to form."],
    na={},
)

C["WB-081"] = _u(
    "Casts are tiny tube-shaped particles formed in the kidney's small tubes and washed out in urine.",
    ["Casts take the shape of the tubes they form in.", "Clear (hyaline) casts can appear after exercise or dehydration. Other types can point to kidney problems."],
    ["Some cast types are a clue to kidney inflammation or damage."],
    ["Exercise", "Dehydration", "Kidney conditions"],
    ["Talk to a doctor if casts other than a few clear casts are reported, especially with protein or blood in the urine."],
    ["The type of cast matters, and the report may not always specify it."],
    ["What do casts in my urine mean?", "Are casts a sign of kidney disease?"],
)

C["WB-082"] = _u(
    "This reports whether bacteria were seen in your urine sample.",
    ["Urine in the bladder is normally free of bacteria.", "Bacteria can come from a urine infection or from skin during collection."],
    ["Bacteria with symptoms or white cells can point to a urine infection."],
    ["Urine infection", "Sample contamination", "Delay before testing"],
    [_UTI_SEEK],
    ["Bacteria without symptoms often do not need treatment, except in pregnancy and some other situations. A urine culture confirms infection."],
    ["Do bacteria in my urine mean I need antibiotics?", "How is a urine infection confirmed?"],
)

C["WB-083"] = _u(
    "This reports whether yeast, a type of fungus, was seen in your urine sample.",
    ["Yeast can live harmlessly on skin and in the vagina.", "Yeast can enter a sample during collection or, less often, cause infection."],
    ["Yeast can be more common with diabetes, after antibiotics or in pregnancy."],
    ["Sample contamination", "Diabetes or high blood sugar", "Recent antibiotics", "Pregnancy"],
    ["Talk to a doctor if yeast is reported with urinary symptoms, or if you have diabetes."],
    ["Yeast in a sample is often contamination and does not always mean infection."],
    ["What does yeast in my urine mean?", "Is yeast in urine linked with high blood sugar?"],
)

C["WB-084"] = _u(
    "This item is labelled nitrate on your report. The standard urine dipstick test checks for nitrite, which some bacteria make. The lab needs to confirm which test was done.",
    ["Some bacteria that cause urine infections turn nitrate from food into nitrite.", "A positive nitrite test can support a urine infection."],
    ["Nitrite testing is one of the quick screening checks for urine infection."],
    ["Urine infection", "Time the urine stayed in the bladder", "Diet"],
    [_UTI_SEEK],
    ["The test identity is not confirmed, and a negative nitrite does not rule out infection."],
    ["What does nitrite in urine mean?", "Can I have a urine infection with a negative nitrite test?"],
)

C["WB-085"] = _u(
    "This checks for ketones in your urine. Ketones are made when your body burns fat for energy instead of sugar.",
    ["When you fast, eat very few carbohydrates or are unwell, your body burns more fat and makes ketones.", "In diabetes, a lack of insulin can make ketones build up dangerously."],
    ["Ketones can show fasting or low-carbohydrate eating, but in diabetes they can be a warning sign."],
    ["Fasting", "Low-carbohydrate diets", "Vomiting or illness", "Diabetes", "Intense exercise"],
    ["Seek urgent care if you have diabetes and ketones with vomiting, tummy pain, fast breathing or confusion."],
    ["Urine ketones show recent fat burning, not how serious it is."],
    ["Why are there ketones in my urine?", "Can fasting cause ketones in urine?"],
    cond={"if_qualitative_assay_confirmed": {"positive": ["Ketones were found. Fasting, low-carbohydrate eating, vomiting or illness are common causes. In diabetes, ketones need prompt medical attention."], "negative": ["No ketones were found."]}},
)

C["WB-086"] = _u(
    "This checks for protein in your urine. Healthy kidneys keep almost all protein in the blood.",
    ["Kidney filters hold back protein while letting waste pass.", "When filters are damaged, protein leaks into urine."],
    ["Protein in urine can be an early sign of kidney damage, especially with diabetes or high blood pressure."],
    ["Kidney filter damage", "Diabetes", "High blood pressure", "Fever or hard exercise", "Urine infection"],
    ["Talk to a doctor if protein is found in your urine, especially with diabetes, high blood pressure, swelling or foamy urine."],
    ["A dipstick can miss small amounts. A urine albumin to creatinine ratio test is more sensitive."],
    ["Does protein in my urine mean kidney damage?", "Can exercise or fever cause protein in urine?"],
    cond={"if_qualitative_assay_confirmed": {"positive": ["Protein was found. It can be temporary after fever or exercise, but if it persists it can mean kidney damage."], "negative": ["No protein was found by the dipstick. Small amounts may need a more sensitive test."]}},
)

C["WB-087"] = _u(
    "Leukocyte esterase is a substance released by white blood cells. A positive test suggests white cells, and possibly infection, in the urine.",
    ["White cells fight infection and release this enzyme.", "The dipstick changes colour when it detects the enzyme."],
    ["Leukocyte esterase is a quick screening check for urine infection."],
    ["Urine infection", "Sample contamination", "Kidney inflammation"],
    [_UTI_SEEK],
    ["A positive result can come from contamination, and a negative result does not rule out infection."],
    ["What does a positive leukocyte esterase mean?", "Do I have a urine infection?"],
    cond={"if_qualitative_assay_confirmed": {"positive": ["White cell activity was detected, which can point to a urine infection or inflammation."], "negative": ["No white cell activity was detected."]}},
)

C["WB-088"] = _u(
    "This checks for bile pigments, mainly bilirubin, in your urine. Normally none is found.",
    ["Bilirubin is a yellow pigment processed by the liver.", "When the liver or bile ducts are not working well, processed bilirubin can spill into urine and make it dark."],
    ["Bile pigments in urine can be an early sign of liver or bile duct problems."],
    ["Liver inflammation", "Bile duct blockage", "Sample exposed to light"],
    ["See a doctor if bile pigments are found, especially with dark urine, yellow eyes or skin, or pale stools."],
    ["The result can be falsely negative if the sample was left in light."],
    ["What do bile pigments in my urine mean?", "Is this linked to my liver?"],
    cond={"only_if_lab_confirms_qualitative_assay": {"positive": ["Bile pigments were found, which can point to a liver or bile duct problem."], "negative": ["No bile pigments were found."]}},
)

C["WB-091"] = _u(
    "This section lists any other findings the lab noted in your urine sample, such as mucus or sperm cells.",
    ["Labs record anything else they see under the microscope."],
    ["Most of these notes are minor, but the lab may flag something that needs a look."],
    ["Sample collection", "Lab notes"],
    ["Ask your doctor about anything listed here that is not explained elsewhere on your report."],
    ["What is noted here varies between labs and is not standardised."],
    ["What do the other findings on my urine report mean?"],
)
