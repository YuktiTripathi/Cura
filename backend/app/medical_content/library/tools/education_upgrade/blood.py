"""Revision 2.3.1 content: complete blood count, ESR and iron studies. Pending clinical review."""

C = {}

_IRON_SUPPORT = [
    "Include iron-rich foods such as dal, chana, rajma, green leafy vegetables, jaggery in moderation, eggs, fish or meat. Your body needs iron to make haemoglobin.",
    "Have a vitamin C food with iron-rich meals, such as lemon, amla, guava or tomato. Vitamin C helps you absorb iron from plant foods.",
    "Keep tea and coffee away from meals by about an hour. They reduce how much iron you absorb.",
]
_DIFF_NA = {
    "lifestyle_relationships": "White cell counts mainly reflect infection, allergy, immune activity or bone marrow; no reliable diet or lifestyle effect on the count itself.",
    "practical_guidance": "An abnormal white cell count needs its cause found by a doctor; everyday habits do not correct it.",
}
_INDEX_ASSAY = "This index is worked out from your red cell results. The lab's formula and cut-off are not confirmed, so CURA does not label it high or low. It only matters if your red cells are small."
_PCT_NOTE = "Percentages depend on the other white cell types, so the absolute count is usually more useful."


def _diff(name, role, high, low, count=True):
    return dict(
        d=f"{name} are a type of white blood cell. {role}",
        body=[
            "White blood cells are made in the bone marrow, the soft tissue inside bones.",
            "There are five main types, and each has a different job in protecting your body.",
            "A blood count shows how many of each type are present." if count else "This result shows what share of your white cells are this type.",
        ],
        why=["Changes in this cell type can point to infection, allergy, inflammation or, less often, a bone marrow condition."],
        high=high, low=low,
        normal=f"Your {name.lower()} result is inside the lab's range, suggesting this part of your immune system looks balanced.",
        factors=["Infection", "Allergy", "Inflammation", "Some medicines", "Bone marrow conditions"],
        life=None, support=[],
        seek=[f"Talk to a doctor if your {name.lower()} result is clearly abnormal, keeps being abnormal, or comes with fever, weight loss, night sweats, easy bruising or frequent infections."],
        limits=["One result can change with a recent infection or stress, so a single mild change is often rechecked." if count else _PCT_NOTE],
        not_applicable=dict(_DIFF_NA),
    )


C["WB-042"] = _diff("Basophils", "They are the least common type and are involved in allergic reactions and inflammation.",
    "A higher basophil count can be seen with allergies, ongoing inflammation, an underactive thyroid or, rarely, some bone marrow conditions.",
    "A lower basophil count is common and usually not a concern, as basophils are normally very few.")
C["WB-042"]["q"] = dict(high=["What does a high basophil count mean?", "Can allergies raise basophils?"], low=["Is a low basophil count a problem?"], normal=["What do basophils do?"])

C["WB-043"] = _diff("Eosinophils", "They help fight parasites and take part in allergic reactions such as asthma and hay fever.",
    "A higher eosinophil count is most often caused by allergies, asthma, eczema or parasite infections. Some medicines can also raise it.",
    "A lower eosinophil count is usually not a concern. It can fall with stress, steroid medicines or the body's response to infection.")
C["WB-043"]["q"] = dict(high=["Why are my eosinophils high?", "Can allergies or worms raise eosinophils?", "Should I be concerned about high eosinophils?"], low=["Is a low eosinophil count a problem?"], normal=["What do eosinophils do?"])

C["WB-044"] = _diff("Lymphocytes", "They include cells that make antibodies and cells that fight viruses.",
    "A higher lymphocyte count is often seen during or after a viral infection. Less often, it can be due to a long-lasting infection or a blood condition.",
    "A lower lymphocyte count can happen during acute illness, stress, with steroid medicines, or with conditions that weaken immunity.")
C["WB-044"]["q"] = dict(high=["Why are my lymphocytes high?", "Can a viral infection raise lymphocytes?"], low=["Why are my lymphocytes low?", "Does a low lymphocyte count affect my immunity?"], normal=["What do lymphocytes do?"])

C["WB-045"] = _diff("Monocytes", "They clean up germs and damaged cells and help with healing.",
    "A higher monocyte count can be seen while recovering from infection, with ongoing infections or inflammation, or, less often, with some blood conditions.",
    "A lower monocyte count is usually not a concern on its own. It can be seen with steroid medicines or some bone marrow problems.")
C["WB-045"]["q"] = dict(high=["Why are my monocytes high?", "Can recovering from an infection raise monocytes?"], low=["Is a low monocyte count a problem?"], normal=["What do monocytes do?"])

C["WB-046"] = _diff("Neutrophils", "They are the most common type and the first responders to bacterial infections.",
    "A higher neutrophil count is most often caused by a bacterial infection, inflammation, injury, physical stress, smoking or steroid medicines.",
    "A lower neutrophil count can come from viral infections, some medicines, low B12 or folate, or bone marrow problems. It can also be naturally lower in some healthy people, including many people of African, Middle Eastern or South Asian descent.")
C["WB-046"]["q"] = dict(high=["Why are my neutrophils high?", "Does a high neutrophil count mean I have an infection?"], low=["Why are my neutrophils low?", "Does a low neutrophil count raise my risk of infection?"], normal=["What do neutrophils do?"])

for key, src in (("WB-057", "WB-046"), ("WB-058", "WB-043"), ("WB-059", "WB-044"), ("WB-060", "WB-045"), ("WB-061", "WB-042")):
    base = C[src]
    name = base["d"].split(" are a type")[0]
    C[key] = dict(base)
    C[key]["d"] = f"This result shows what share of your white blood cells are {name.lower()}. {base['d'].split('. ', 1)[1]}"
    C[key]["body"] = base["body"][:2] + ["This result shows what share of your white cells are this type, as a percentage."]
    C[key]["limits"] = [_PCT_NOTE]
    C[key]["high"] = base["high"].replace(" count", " percentage")
    C[key]["low"] = base["low"].replace(" count", " percentage")
    C[key]["q"] = {state: [q.replace("count", "percentage") for q in qs] for state, qs in base["q"].items()}
    C[key]["q"]["normal"] = C[key]["q"]["normal"] + ["Why does my report show both a percentage and a count?"]

C["WB-047"] = dict(
    d="The erythrocyte (red blood cell) sedimentation rate, or ESR, measures how quickly red blood cells settle to the bottom of a tube. Faster settling is a general sign of inflammation.",
    body=[
        "During inflammation, the liver releases proteins that make red cells clump together.",
        "Clumped cells are heavier and settle faster.",
        "So ESR shows that inflammation may be present, but not where or why.",
    ],
    why=["ESR is a simple check for inflammation and is used to follow some long-term inflammatory conditions."],
    high="A higher ESR can come from infection, inflammation, autoimmune conditions such as rheumatoid arthritis, anaemia, pregnancy or kidney disease. It naturally rises with age and is often higher in women.",
    low="A lower ESR is usually not a concern.",
    normal="Your ESR is inside the lab's range, suggesting no marked inflammation from this test.",
    factors=["Infection", "Inflammation", "Age and sex", "Anaemia", "Pregnancy", "Autoimmune conditions"],
    life=None, support=[],
    seek=["Talk to a doctor if ESR is high with joint pain, fever, weight loss, night sweats or headaches with scalp tenderness."],
    limits=["ESR is non-specific. A normal ESR does not rule out inflammation, and a raised ESR does not show the cause."],
    not_applicable={"lifestyle_relationships": "ESR reflects inflammation from many causes; no reliable direct lifestyle effect.", "practical_guidance": "A raised ESR needs its cause found by a doctor."},
    q=dict(high=["Why is my ESR high?", "Should I be concerned about a high ESR?", "How is ESR different from CRP?"], low=["Is a low ESR a problem?"], normal=["What does ESR tell me?"]),
)
C["WB-094"] = {**C["WB-047"], "d": "ESR, or erythrocyte (red blood cell) sedimentation rate, measures how quickly red blood cells settle in a tube of blood. It is a general sign of inflammation and is shown here as part of an inflammation panel."}

C["WB-048"] = dict(
    d="Haemoglobin is the protein inside red blood cells that carries oxygen from your lungs to the rest of your body. It also gives blood its red colour.",
    body=[
        "Each red blood cell is packed with haemoglobin.",
        "Haemoglobin picks up oxygen in the lungs and releases it in your tissues.",
        "Your body needs iron, vitamin B12 and folate to make haemoglobin.",
    ],
    why=["Low haemoglobin, called anaemia, is very common and can cause tiredness, breathlessness and pale skin."],
    high="Higher haemoglobin can come from dehydration, smoking, living at high altitude or lung conditions. Less often, the bone marrow makes too many red cells.",
    low="Lower haemoglobin means anaemia. Common causes include low iron, often from heavy periods or a diet low in iron, low vitamin B12 or folate, blood loss and long-term illness.",
    normal="Your haemoglobin is inside the lab's range, suggesting your blood is carrying oxygen well.",
    factors=["Iron, B12 and folate levels", "Blood loss including heavy periods", "Hydration", "Smoking", "Altitude", "Long-term illness"],
    life=["Iron-rich foods, with vitamin C to help absorption, support healthy haemoglobin. Vegetarians may need to plan iron sources more carefully."],
    support=_IRON_SUPPORT,
    seek=[
        "Talk to a doctor if haemoglobin is low, so they can find the cause before treatment. Do not start iron tablets without checking first.",
        "Seek care promptly if low haemoglobin comes with chest pain, fainting, black stools or heavy bleeding.",
    ],
    limits=["Haemoglobin shows whether anaemia is present, but not its cause. Red cell indices and iron or vitamin tests help with that."],
    q=dict(
        high=["Why is my haemoglobin high?", "Can dehydration raise my haemoglobin?"],
        low=["Why is my haemoglobin low?", "What foods help raise haemoglobin?", "Does low haemoglobin mean I need iron tablets?"],
        normal=["What does haemoglobin do in my body?", "How can I keep my haemoglobin healthy?"],
    ),
)

_INDEX_NA = {"practical_guidance": "Red cell index; guidance depends on the cause, which is covered by haemoglobin, iron and B12 entries."}

C["WB-049"] = dict(
    d="MCH, or mean corpuscular haemoglobin, shows the average amount of haemoglobin inside each red blood cell.",
    body=["Haemoglobin is the oxygen-carrying protein in red cells.", "MCH tells you how much of it, on average, each cell contains."],
    why=["MCH helps work out the type and likely cause of anaemia."],
    high="A higher MCH usually means red cells are larger than usual, which can happen with low vitamin B12 or folate, liver disease or heavy alcohol use.",
    low="A lower MCH means red cells contain less haemoglobin than usual. The most common cause is low iron. Inherited conditions such as thalassaemia trait can also cause it.",
    normal="Your MCH is inside the lab's range, suggesting your red cells carry a normal amount of haemoglobin.",
    factors=["Iron level", "Vitamin B12 and folate", "Thalassaemia trait", "Alcohol"],
    life=["Low iron intake is the most common everyday reason MCH falls."],
    support=[],
    seek=["Talk to a doctor if MCH is abnormal together with low haemoglobin, to find the cause."],
    limits=["MCH is read together with MCV and haemoglobin; on its own it cannot diagnose a cause."],
    not_applicable=dict(_INDEX_NA),
    q=dict(high=["What does a high MCH mean?", "Can low B12 change my MCH?"], low=["What does a low MCH mean?", "Is a low MCH a sign of low iron?", "Could I have thalassaemia trait?"], normal=["What does MCH tell me about my red blood cells?"]),
)

C["WB-050"] = dict(
    d="MCHC, or mean corpuscular haemoglobin concentration, shows how concentrated the haemoglobin is inside your red blood cells.",
    body=["It compares the amount of haemoglobin with the size of the red cells.", "It helps describe how well each cell is filled with haemoglobin."],
    why=["MCHC helps describe the type of anaemia and can point to some inherited red cell conditions."],
    high="A higher MCHC is uncommon. It can be seen with some inherited red cell shape conditions or when red cells are breaking down. Sample problems can also cause it.",
    low="A lower MCHC means red cells are paler than usual, most often because of low iron.",
    normal="Your MCHC is inside the lab's range.",
    factors=["Iron level", "Inherited red cell conditions", "Sample handling"],
    life=None, support=[],
    seek=["Talk to a doctor if MCHC is abnormal together with other red cell changes."],
    limits=["MCHC changes less than other red cell measures, so it is mainly useful alongside MCV and MCH."],
    not_applicable={**_INDEX_NA, "lifestyle_relationships": "Red cell index; diet links are covered by haemoglobin and iron entries."},
    q=dict(high=["What does a high MCHC mean?"], low=["What does a low MCHC mean?", "Is a low MCHC linked with low iron?"], normal=["What does MCHC tell me?"]),
)

C["WB-051"] = dict(
    d="MCV, or mean corpuscular volume, shows the average size of your red blood cells.",
    body=["Red cells are normally a fairly even size.", "Low iron tends to make them smaller, while low B12 or folate tends to make them larger."],
    why=["MCV is one of the most useful clues to the cause of anaemia."],
    high="A higher MCV means red cells are larger than usual. Common causes are low vitamin B12 or folate, heavy alcohol use, liver disease, an underactive thyroid and some medicines.",
    low="A lower MCV means red cells are smaller than usual. The most common cause is low iron. Thalassaemia trait, an inherited condition, is another common cause.",
    normal="Your MCV is inside the lab's range, suggesting your red cells are a normal size.",
    factors=["Iron level", "Vitamin B12 and folate", "Alcohol", "Thalassaemia trait", "Thyroid function"],
    life=["Low iron intake makes cells smaller, while low B12 intake, common in vegetarian diets, can make them larger."],
    support=[],
    seek=["Talk to a doctor if MCV is abnormal, especially with low haemoglobin or tiredness, so the cause can be found."],
    limits=["Low iron and low B12 together can cancel out, giving a normal MCV even when both are low."],
    not_applicable=dict(_INDEX_NA),
    q=dict(high=["What does a high MCV mean?", "Can low B12 make my red cells larger?"], low=["What does a low MCV mean?", "Is my low MCV caused by low iron or thalassaemia?"], normal=["What does MCV tell me about my red blood cells?"]),
)

C["WB-052"] = dict(
    d="MPV, or mean platelet volume, shows the average size of your platelets. Platelets are tiny blood cells that help your blood clot.",
    body=["Platelets are made in the bone marrow.", "Young platelets are usually larger, so MPV can hint at how quickly new platelets are being made."],
    why=["MPV helps explain why a platelet count is high or low."],
    high="A higher MPV can mean the bone marrow is making many new platelets, for example after platelets have been used up or destroyed.",
    low="A lower MPV can be seen when the bone marrow is making fewer platelets.",
    normal="Your MPV is inside the lab's range.",
    factors=["Platelet production", "Platelet destruction", "Sample timing and handling"],
    life=None, support=[],
    seek=["Talk to a doctor if MPV is abnormal together with an abnormal platelet count, or with easy bruising or bleeding."],
    limits=["MPV is affected by how long the sample sits before testing, and it is not useful on its own."],
    not_applicable={"lifestyle_relationships": "Platelet index; no established lifestyle effect.", "practical_guidance": "Platelet index; needs reading with the platelet count by a doctor."},
    q=dict(high=["What does a high MPV mean?"], low=["What does a low MPV mean?"], normal=["What does MPV tell me about my platelets?"]),
)

C["WB-053"] = dict(
    d="Haematocrit, also called PCV, shows what share of your blood is made up of red blood cells.",
    body=["Blood is made of red cells, white cells, platelets and a liquid called plasma.", "Haematocrit is the percentage taken up by red cells."],
    why=["It helps confirm anaemia and shows whether you may be dehydrated or have too many red cells."],
    high="A higher haematocrit can come from dehydration, smoking, high altitude or lung conditions. Less often, the bone marrow makes too many red cells.",
    low="A lower haematocrit usually goes with anaemia, from causes such as low iron, low B12 or folate, or blood loss.",
    normal="Your haematocrit is inside the lab's range.",
    factors=["Hydration", "Haemoglobin and iron levels", "Smoking", "Altitude"],
    life=["Dehydration raises haematocrit; low iron intake can lower it through anaemia."],
    support=[],
    seek=["Talk to a doctor if haematocrit is abnormal along with abnormal haemoglobin."],
    limits=["Haematocrit usually moves with haemoglobin and adds little on its own."],
    not_applicable={"practical_guidance": "Moves with haemoglobin; guidance is covered by the haemoglobin and iron entries."},
    q=dict(high=["Why is my haematocrit high?", "Can dehydration raise haematocrit?"], low=["Why is my haematocrit low?"], normal=["What does haematocrit measure?"]),
)

C["WB-054"] = dict(
    d="Platelets are tiny blood cells that help stop bleeding by forming clots. The platelet count shows how many you have.",
    body=["Platelets are made in the bone marrow and live for about a week to ten days.", "When a blood vessel is damaged, they stick together to plug the gap."],
    why=["Too few platelets can lead to easy bleeding, and too many can raise the chance of clots."],
    high="A higher platelet count is most often a reaction to infection, inflammation, low iron or recent bleeding or surgery. Less often, the bone marrow makes too many.",
    low="A lower platelet count can follow viral infections such as dengue, or come from some medicines, heavy alcohol use, an enlarged spleen, low B12 or folate, or immune conditions. Clumping in the sample tube can also give a falsely low result.",
    normal="Your platelet count is inside the lab's range, suggesting normal clotting cells.",
    factors=["Infection", "Inflammation", "Low iron", "Some medicines", "Alcohol", "Sample clumping"],
    life=["Heavy alcohol use can lower platelets."],
    support=[],
    seek=[
        "Seek care promptly if platelets are low with bleeding gums, nosebleeds, blood in urine or stools, or many small red or purple spots on the skin.",
        "Talk to a doctor if platelets stay high or low on repeat tests.",
    ],
    limits=["A low count can be falsely low if platelets clumped in the tube, so an unexpected low result is often repeated."],
    not_applicable={"practical_guidance": "Abnormal platelet counts need the cause found by a doctor; everyday habits do not correct them."},
    q=dict(high=["Why is my platelet count high?", "Can low iron raise platelets?"], low=["Should I be worried about a low platelet count?", "Can a viral fever lower platelets?"], normal=["What do platelets do?"]),
)

C["WB-055"] = dict(
    d="The white blood cell count, or WBC, shows how many infection-fighting cells are in your blood.",
    body=["White blood cells are part of your immune system.", "Your body sends more of them into the blood when fighting infection or inflammation.", "There are five main types, shown separately in your report."],
    why=["WBC helps spot infection, inflammation and, less often, bone marrow or immune problems."],
    high="A higher WBC is most often caused by an infection or inflammation. Stress, smoking, pregnancy and steroid medicines can also raise it. Less often, it is due to a blood condition.",
    low="A lower WBC can follow viral infections, or come from some medicines, low B12 or folate, autoimmune conditions or bone marrow problems. Some healthy people naturally run lower.",
    normal="Your white cell count is inside the lab's range.",
    factors=["Infection", "Inflammation", "Stress", "Smoking", "Some medicines", "Bone marrow conditions"],
    life=["Smoking can raise the white cell count."],
    support=[],
    seek=["Talk to a doctor if WBC is clearly high or low, or comes with fever, frequent infections, weight loss or night sweats."],
    limits=["The total count does not show which white cell type has changed. The separate counts help with that."],
    not_applicable={"practical_guidance": "An abnormal WBC needs its cause found by a doctor."},
    q=dict(high=["Why is my white blood cell count high?", "Does a high WBC mean I have an infection?"], low=["Why is my white blood cell count low?", "Does a low WBC mean weak immunity?"], normal=["What do white blood cells do?"]),
)

C["WB-056"] = dict(
    d="RDW, or red cell distribution width, shows how much your red blood cells vary in size.",
    body=["Healthy red cells are mostly a similar size.", "When new cells are made under strain, for example with low iron or B12, sizes become more mixed."],
    why=["A high RDW can be an early clue to low iron or low B12, sometimes before haemoglobin falls."],
    high="A higher RDW means red cells are more mixed in size. It is commonly seen with low iron, low B12 or folate, or recovery from blood loss.",
    low="A low RDW is not a concern.",
    normal="Your RDW is inside the lab's range, suggesting your red cells are a fairly even size.",
    factors=["Iron level", "Vitamin B12 and folate", "Recent blood loss or treatment"],
    life=None, support=[],
    seek=["Talk to a doctor if RDW is high together with low haemoglobin or abnormal MCV."],
    limits=["RDW is non-specific and is mainly useful alongside MCV and iron or B12 tests."],
    not_applicable={**_INDEX_NA, "lifestyle_relationships": "Red cell index; diet links are covered by iron and B12 entries."},
    q=dict(high=["What does a high RDW mean?", "Can low iron raise my RDW?"], low=["Is a low RDW a problem?"], normal=["What does RDW tell me?"]),
)
C["WB-062"] = {**C["WB-056"], "d": "RDW-CV shows how much your red blood cells vary in size, expressed as a percentage of their average size."}

C["WB-063"] = dict(
    d="The Mentzer index is a calculation that divides your red cell size (MCV) by your red cell count. Doctors use it as a rough first clue when red cells are small.",
    body=["Both low iron and thalassaemia trait make red cells small.", "Thalassaemia trait tends to give many small cells, while low iron tends to give fewer."],
    why=["When red cells are small, the index helps decide which tests to do next."],
    high="A higher index leans towards low iron as the cause of small red cells.",
    low="A lower index leans towards thalassaemia trait, an inherited condition, as the cause of small red cells.",
    normal="Your index falls in the lab's range. It is only meaningful when your red cells are small.",
    factors=["MCV", "Red blood cell count"],
    life=None, support=[],
    seek=["Talk to a doctor if your red cells are small. Iron tests or haemoglobin studies may be needed to confirm the cause."],
    limits=["The index is a screening clue, not a diagnosis. It can be wrong, especially if low iron and thalassaemia trait occur together."],
    not_applicable={"lifestyle_relationships": "Calculated index; not affected by habits directly.", "practical_guidance": "Calculated index used only to guide further testing."},
    assay=_INDEX_ASSAY,
    q=dict(assay_unconfirmed=["What is the Mentzer index used for?", "Could my red cell results point to thalassaemia trait?", "Should I get tested for thalassaemia?"]),
)

C["WB-064"] = dict(
    d="The red blood cell count shows how many red blood cells are in a small amount of your blood. Red cells carry oxygen around your body.",
    body=["Red cells are made in the bone marrow and live about four months.", "Your body needs iron, B12 and folate to make them."],
    why=["The count helps check for anaemia, dehydration and conditions where too many red cells are made."],
    high="A higher red cell count can come from dehydration, smoking, high altitude, lung conditions or thalassaemia trait, where there are many small cells.",
    low="A lower red cell count usually goes with anaemia, caused for example by low iron, low B12 or folate, or blood loss.",
    normal="Your red cell count is inside the lab's range.",
    factors=["Hydration", "Iron, B12 and folate", "Smoking", "Altitude", "Thalassaemia trait"],
    life=["Diets low in iron or B12 can lower red cell production over time."],
    support=[],
    seek=["Talk to a doctor if the count is abnormal along with abnormal haemoglobin or tiredness."],
    limits=["The count is read together with haemoglobin and red cell size; on its own it cannot show the cause."],
    not_applicable={"practical_guidance": "Guidance depends on the cause, covered by haemoglobin, iron and B12 entries."},
    q=dict(high=["Why is my red blood cell count high?", "Can thalassaemia trait raise my red cell count?"], low=["Why is my red blood cell count low?"], normal=["What do red blood cells do?"]),
)

C["WB-065"] = dict(
    d="The GK index is a calculation from your red cell results. Like the Mentzer index, doctors sometimes use it to tell low iron apart from thalassaemia trait when red cells are small.",
    body=["It combines red cell size, haemoglobin and red cell count into one number.", "It is only meaningful when red cells are small."],
    why=["It can help decide whether iron tests or thalassaemia tests should come next."],
    high="A higher index leans towards low iron as the cause of small red cells.",
    low="A lower index leans towards thalassaemia trait.",
    normal="Your index falls in the lab's range. It matters only if your red cells are small.",
    factors=["MCV", "Haemoglobin", "Red blood cell count"],
    life=None, support=[],
    seek=["Talk to a doctor if your red cells are small, so the cause can be confirmed with the right tests."],
    limits=["The GK index is a screening clue only and can be wrong; confirmation needs iron or haemoglobin studies."],
    not_applicable={"lifestyle_relationships": "Calculated index.", "practical_guidance": "Calculated index used only to guide further testing."},
    assay=_INDEX_ASSAY,
    q=dict(assay_unconfirmed=["What is the GK index used for?", "Could my red cell results point to thalassaemia trait?"]),
)

C["WB-066"] = dict(
    d="RDWI is a calculation that combines red cell size, size variation and red cell count. It is another screening clue used when red cells are small.",
    body=["It uses MCV, RDW and the red cell count.", "Like the Mentzer and GK indices, it helps compare low iron with thalassaemia trait."],
    why=["It can help decide which tests to do next when red cells are small."],
    high="A higher RDWI leans towards low iron as the cause of small red cells.",
    low="A lower RDWI leans towards thalassaemia trait.",
    normal="Your RDWI falls in the lab's range. It matters only if your red cells are small.",
    factors=["MCV", "RDW", "Red blood cell count"],
    life=None, support=[],
    seek=["Talk to a doctor if your red cells are small, so the cause can be confirmed."],
    limits=["RDWI is a screening clue only; confirmation needs iron or haemoglobin studies."],
    not_applicable={"lifestyle_relationships": "Calculated index.", "practical_guidance": "Calculated index used only to guide further testing."},
    assay=_INDEX_ASSAY,
    q=dict(assay_unconfirmed=["What is RDWI used for?", "Could my red cell results point to thalassaemia trait?"]),
)

_IRON_SEEK = [
    "Talk to a doctor if iron results are low, so they can find the cause, such as heavy periods or blood loss from the gut, before starting tablets.",
    "Talk to a doctor if iron results are high, as iron overload can harm the liver and heart.",
]

C["WB-112"] = dict(
    d="Serum iron measures the iron travelling in your blood right now. Iron is needed to make haemoglobin, which carries oxygen.",
    body=["Iron from food is absorbed in the gut.", "It travels in the blood attached to a carrier protein called transferrin.", "Spare iron is stored as ferritin, mainly in the liver."],
    why=["Serum iron is read with ferritin, TIBC and transferrin saturation to check for low iron or too much iron."],
    high="Higher serum iron can follow iron tablets or a recent iron-rich meal. It can also be seen with iron overload conditions or liver damage.",
    low="Lower serum iron can come from low iron stores, blood loss, low iron intake, or inflammation, which hides iron away from the blood.",
    normal="Your serum iron is inside the lab's range. It is read together with ferritin to judge your stores.",
    factors=["Iron intake and tablets", "Time of day", "Recent meals", "Blood loss", "Inflammation"],
    life=["Iron-rich foods, with vitamin C, help keep iron levels up. Tea and coffee with meals reduce absorption."],
    support=_IRON_SUPPORT,
    seek=_IRON_SEEK,
    limits=["Serum iron changes through the day and after meals, so it is not reliable on its own."],
    q=dict(high=["Why is my serum iron high?", "Can iron tablets raise my iron result?"], low=["Why is my iron low?", "Which foods can help raise my iron?"], normal=["What does serum iron tell me?", "How is iron different from ferritin?"]),
)

C["WB-113"] = dict(
    d="TIBC, or total iron-binding capacity, measures how much iron your blood could carry if all its carrier protein were full.",
    body=["Iron travels in the blood on a protein called transferrin.", "When iron stores are low, the liver makes more transferrin, so TIBC rises."],
    why=["TIBC helps tell low iron apart from other causes of anaemia."],
    high="A higher TIBC usually means your body is short of iron and is making more carrier protein to capture it. It can also rise in pregnancy or with hormone pills.",
    low="A lower TIBC can be seen with inflammation, long-term illness, liver disease, poor nutrition or iron overload.",
    normal="Your TIBC is inside the lab's range.",
    factors=["Iron stores", "Inflammation", "Pregnancy or hormone pills", "Liver function", "Nutrition"],
    life=None, support=[],
    seek=_IRON_SEEK[:1],
    limits=["TIBC is read together with serum iron and ferritin; on its own it cannot confirm low iron."],
    not_applicable={"lifestyle_relationships": "Carrier capacity follows iron stores; diet links are covered by the iron and ferritin entries.", "practical_guidance": "Guidance is covered by the iron and ferritin entries."},
    q=dict(high=["What does a high TIBC mean?", "Is a high TIBC a sign of low iron?"], low=["What does a low TIBC mean?"], normal=["What does TIBC measure?"]),
)

C["WB-114"] = dict(
    d="UIBC, or unsaturated iron-binding capacity, measures how much spare room is left on the iron carrier protein in your blood.",
    body=["Iron travels on a protein called transferrin.", "UIBC is the part of that carrier that is still empty."],
    why=["UIBC is used to work out TIBC and transferrin saturation."],
    high="A higher UIBC means more empty carrier space, which usually points to low iron.",
    low="A lower UIBC means less empty carrier space, which can be seen with high iron or with inflammation.",
    normal="Your UIBC is inside the lab's range.",
    factors=["Iron level", "Transferrin level", "Inflammation"],
    life=None, support=[],
    seek=_IRON_SEEK[:1],
    limits=["UIBC is mostly a step in calculating other iron results and is rarely read on its own."],
    not_applicable={"lifestyle_relationships": "Calculated from iron carrier capacity; covered by iron and ferritin entries.", "practical_guidance": "Covered by the iron and ferritin entries."},
    q=dict(high=["What does a high UIBC mean?"], low=["What does a low UIBC mean?"], normal=["What is UIBC?"]),
)

C["WB-115"] = dict(
    d="Transferrin saturation shows what percentage of the iron carrier protein in your blood is filled with iron.",
    body=["Transferrin carries iron around your body.", "This result is worked out by dividing serum iron by TIBC."],
    why=["A low saturation suggests low iron, while a high saturation can be an early sign of iron overload."],
    high="A higher saturation means a lot of the carrier is full. It can follow iron tablets, but a persistently high result can point to iron overload, such as haemochromatosis, an inherited condition.",
    low="A lower saturation means the carrier holds little iron, which usually points to low iron.",
    normal="Your transferrin saturation is inside the lab's range.",
    factors=["Iron level", "Iron tablets", "Inherited iron overload", "Inflammation"],
    life=None, support=[],
    seek=_IRON_SEEK,
    limits=["Transferrin saturation varies through the day, so a high result is usually repeated on a fasting sample."],
    not_applicable={"lifestyle_relationships": "Calculated percentage; diet links are covered by iron and ferritin entries.", "practical_guidance": "Covered by the iron and ferritin entries."},
    q=dict(high=["What does high transferrin saturation mean?", "Could I have iron overload?"], low=["Does low transferrin saturation mean I'm low in iron?"], normal=["What does transferrin saturation tell me?"]),
)

C["WB-116"] = dict(
    d="Ferritin is a protein that stores iron inside your body. The amount in your blood reflects how much iron you have in reserve.",
    body=["Your body keeps spare iron in ferritin, mostly in the liver.", "When you need more iron to make red blood cells, it is released from these stores.", "Low ferritin is usually the earliest sign that iron is running low."],
    why=["Ferritin is the best single blood test for low iron stores."],
    high="Higher ferritin can come from inflammation, infection, liver strain such as fatty liver, heavy alcohol use or iron overload. Because inflammation raises ferritin, a high level does not always mean too much iron.",
    low="Lower ferritin means your iron stores are low. Common causes are heavy periods, pregnancy, low iron intake, blood loss from the gut or poor absorption.",
    normal="Your ferritin is inside the lab's range, suggesting adequate iron stores at the moment.",
    factors=["Iron intake", "Heavy periods or blood loss", "Pregnancy", "Inflammation", "Liver health", "Alcohol"],
    life=["Iron-rich foods with vitamin C help build stores. Vegetarian diets can provide enough iron with planning."],
    support=_IRON_SUPPORT,
    seek=_IRON_SEEK,
    limits=["Inflammation can raise ferritin and hide low iron stores, so a normal ferritin during illness does not always rule out low iron."],
    q=dict(high=["Why is my ferritin high?", "Does high ferritin mean too much iron?"], low=["Why are my iron stores low?", "How can I raise my ferritin naturally?", "Can low ferritin make me tired?"], normal=["What does ferritin tell me about my iron?"]),
)
