"""Education upgrade for blood count, ESR and iron results. Pending clinical review.

The 2.3.1 text gave all ten white cell results the same factor list and the same biology. Each type now
has its own job, its own factors and its own reason for testing.
"""

_MARROW = "White blood cells are made in the bone marrow, the soft tissue inside bones."
_PCT = "This result is the share of all your white cells that are this type, so it moves when other types change. The absolute count is usually more useful."

_IRON_KEEP = [
    "Iron-rich foods such as dal, chana, rajma, green leafy vegetables, eggs, fish or meat, eaten with a vitamin C food such as lemon, amla or guava, help keep iron stores up.",
    "Tea and coffee with meals reduce iron absorption, so having them an hour away from meals helps.",
]
_IRON_RISK = ["Heavy periods are the most common reason Indian women run low on iron. If periods are heavy, tell your doctor."]

_WBC = {
    "neutrophil": dict(
        job="Neutrophils are the most common white cell. They are the first to arrive at a bacterial infection or injury and swallow germs.",
        why="Neutrophils help show whether the body is fighting a bacterial infection or physical stress, and a low count shows how well protected you are against infection.",
        fx=[
            ("Bacterial infection", "The marrow releases extra neutrophils to fight bacteria, so the count rises."),
            ("Physical stress, injury or surgery", "Stress hormones push neutrophils from the vessel walls into the bloodstream."),
            ("Smoking", "Smoking keeps the body in a low-grade inflamed state, raising neutrophils."),
            ("Steroid medicines", "Steroids raise the neutrophil count."),
            ("Viral infections", "Some viral infections, including dengue, temporarily lower neutrophils."),
            ("Some medicines", "Some antibiotics, thyroid medicines and cancer treatments can lower neutrophils."),
            ("Low B12 or folate", "The marrow needs these vitamins to make all blood cells."),
            ("Inherited lower counts", "Many healthy people of South Asian, African or Middle Eastern descent naturally have lower neutrophils without extra infections."),
        ],
        myth="A slightly low neutrophil count in a well person is often a normal variation, especially in people of South Asian descent, but it is still worth a doctor's view if it persists.",
    ),
    "eosinophil": dict(
        job="Eosinophils fight parasites, such as worms, and take part in allergic reactions such as asthma, hay fever and eczema.",
        why="Eosinophils help point to allergy or a parasite infection when they are raised.",
        fx=[
            ("Allergy, asthma or eczema", "Allergic reactions call eosinophils into the blood and tissues."),
            ("Parasite infections", "Worm infections, common in India, strongly raise eosinophils."),
            ("Some medicines", "Some medicines cause an allergic-type reaction that raises eosinophils."),
            ("Steroid medicines and acute stress", "Steroids and stress hormones lower eosinophils."),
        ],
        myth="High eosinophils are not always allergy. Worm infections are a common cause in India, so a doctor may check stool or treat for worms.",
    ),
    "lymphocyte": dict(
        job="Lymphocytes include the cells that make antibodies and the cells that kill virus-infected cells. They also remember past infections.",
        why="Lymphocytes help show a recent viral infection and, when low, how well the immune system can respond.",
        fx=[
            ("Viral infections", "Lymphocytes multiply to fight viruses, so the count rises during and after a viral illness."),
            ("Long-lasting infections", "Infections such as tuberculosis can raise lymphocytes."),
            ("Acute illness and stress", "Severe illness and stress hormones lower lymphocytes for a while."),
            ("Steroid medicines", "Steroids lower the lymphocyte count."),
            ("Conditions that weaken immunity", "Some infections, such as HIV, and some treatments reduce lymphocytes."),
            ("Blood conditions", "Less often, a raised count comes from a blood condition, especially in older adults."),
        ],
        myth="A raised lymphocyte count after a cold or fever is usually the immune system doing its job.",
    ),
    "monocyte": dict(
        job="Monocytes travel to tissues, where they become clean-up cells that swallow germs and dead cells and help healing.",
        why="Monocytes help show recovery from infection or a long-lasting infection or inflammation.",
        fx=[
            ("Recovery from infection", "Monocytes often rise as the body clears an infection."),
            ("Long-lasting infections", "Infections such as tuberculosis raise monocytes."),
            ("Inflammatory conditions", "Ongoing inflammation, such as inflammatory bowel disease, raises them."),
            ("Steroid medicines", "Steroids lower monocytes."),
            ("Bone marrow conditions", "Less often, a persistent change comes from the bone marrow."),
        ],
        myth="A mildly high monocyte count after an infection is common and often settles on its own.",
    ),
    "basophil": dict(
        job="Basophils are the rarest white cell. They release histamine and other chemicals during allergic reactions and inflammation.",
        why="Basophils are rarely important alone; a persistently raised count can sometimes point to allergy or a bone marrow condition.",
        fx=[
            ("Allergy", "Allergic reactions can raise basophils slightly."),
            ("Ongoing inflammation", "Long-term inflammation can raise them."),
            ("Underactive thyroid", "An underactive thyroid is sometimes linked with higher basophils."),
            ("Bone marrow conditions", "A persistently high count can rarely come from the bone marrow."),
        ],
        myth="A low basophil count is not a problem. They are normally so few that zero is a common result.",
    ),
}

_KEYS = {"WB-046": ("neutrophil", False), "WB-057": ("neutrophil", True), "WB-043": ("eosinophil", False), "WB-058": ("eosinophil", True),
         "WB-044": ("lymphocyte", False), "WB-059": ("lymphocyte", True), "WB-045": ("monocyte", False), "WB-060": ("monocyte", True),
         "WB-042": ("basophil", False), "WB-061": ("basophil", True)}

X = {}
for _k, (_t, _pct) in _KEYS.items():
    w = _WBC[_t]
    X[_k] = dict(
        fx=w["fx"],
        fix=dict(body=[_MARROW, w["job"], _PCT if _pct else "This count shows how many of these cells are in a set amount of blood."], why=[w["why"]]),
        keep=None,
        myth=[w["myth"]],
        na=dict(keeping_healthy="White cell counts follow infection, allergy, medicines and the marrow; no habit sets them."),
    )

_ESR_FX = [
    ("Infection", "Infection makes the liver release proteins that cause red cells to clump, so they settle faster."),
    ("Inflammation", "Any inflammation raises these proteins and the ESR."),
    ("Age and sex", "The normal upper limit is higher in older adults and in women."),
    ("Anaemia", "With fewer red cells in the tube, the cells settle faster, raising ESR without inflammation."),
    ("Pregnancy", "Pregnancy raises ESR."),
    ("Autoimmune conditions", "Conditions such as rheumatoid arthritis and lupus raise ESR."),
    ("Kidney disease", "Kidney disease can raise ESR."),
    ("Thyroid disease", "Thyroid disease can raise ESR."),
    ("Red cell and heart conditions", "Too many red cells (polycythaemia), sickle cell anaemia and heart failure lower ESR."),
]
for _k in ("WB-047", "WB-094"):
    X[_k] = dict(
        fx=_ESR_FX,
        fix=dict(
            high="A higher ESR can come from infection, inflammation, autoimmune conditions such as rheumatoid arthritis, anaemia, pregnancy, kidney disease or thyroid disease. The normal upper limit is higher in older adults and in women.",
            low="A lower ESR is usually not a concern. Some conditions lower it, such as having too many red cells (polycythaemia), sickle cell anaemia or heart failure.",
            seek=["Talk to a doctor if ESR is high, especially with unexplained fever, joint pain, muscle symptoms or a new headache."],
        ),
        keep=None,
        myth=["A normal ESR does not rule out inflammation, and a raised ESR does not show where it is. CRP is often checked alongside it."],
        na=dict(keeping_healthy="ESR follows inflammation, anaemia, pregnancy and age; no habit sets it."),
    )

X["WB-048"] = dict(
    fx=[
        ("Iron, B12 and folate levels", "The marrow needs iron to build haemoglobin and B12 and folate to make red cells; a shortage of any lowers it."),
        ("Blood loss including heavy periods", "Losing blood, often slowly through heavy periods or the gut, uses up iron and lowers haemoglobin."),
        ("Inherited haemoglobin traits", "Thalassaemia trait, common in India, can give a mildly low haemoglobin with small red cells, unrelated to iron."),
        ("Long-term illness", "Kidney disease and ongoing inflammation slow red cell production."),
        ("Hydration", "Dehydration concentrates the blood and makes haemoglobin read higher."),
        ("Smoking", "Carbon monoxide from smoke reduces oxygen delivery, so the body makes more haemoglobin."),
        ("Altitude", "Living high up, where air has less oxygen, raises haemoglobin."),
    ],
    keep=_IRON_KEEP,
    risk=_IRON_RISK,
    myth=["Not every low haemoglobin is from low iron. Thalassaemia trait, B12 or folate shortage and long-term illness can cause it, so iron tablets should not be started without finding the cause."],
)

X["WB-049"] = dict(
    fx=[
        ("Iron level", "Low iron means less haemoglobin is packed into each cell, lowering MCH."),
        ("Vitamin B12 and folate", "Shortages make cells larger, each carrying more haemoglobin, raising MCH."),
        ("Thalassaemia trait", "This inherited trait gives small cells with less haemoglobin each."),
        ("Alcohol", "Heavy drinking can enlarge red cells and raise MCH."),
    ],
    keep=None,
    myth=["MCH rarely needs separate action. It follows MCV and is read with it."],
    na=dict(keeping_healthy="A red cell index that follows iron and vitamin status."),
)
X["WB-050"] = dict(
    fx=[
        ("Iron level", "Long-term low iron makes cells paler, lowering MCHC."),
        ("Inherited red cell conditions", "Conditions such as hereditary spherocytosis raise MCHC."),
        ("Sample handling", "A sample with fatty blood or clumped cells can give a falsely high result."),
    ],
    keep=None,
    myth=["A slightly unusual MCHC with otherwise normal results is often a lab variation."],
    na=dict(keeping_healthy="A red cell index read with the others."),
)
X["WB-051"] = dict(
    fx=[
        ("Iron level", "Without enough iron, cells are made smaller."),
        ("Vitamin B12 and folate", "Without these, cells cannot divide properly and stay large."),
        ("Alcohol", "Heavy drinking enlarges red cells."),
        ("Thalassaemia trait", "This common inherited trait makes cells small, without low iron."),
        ("Thyroid function", "An underactive thyroid can enlarge red cells."),
        ("Liver disease and some medicines", "Liver disease and some medicines, such as some used for seizures or HIV, enlarge red cells."),
    ],
    keep=None,
    myth=["Small red cells do not always mean low iron. Thalassaemia trait is common in India and needs different advice."],
    na=dict(keeping_healthy="A red cell size index that points to causes rather than a habit."),
)
X["WB-052"] = dict(
    fx=[
        ("Platelet production", "When the marrow makes platelets quickly, as after bleeding, new platelets are larger."),
        ("Platelet destruction", "When platelets are used up quickly, the young large ones dominate."),
        ("Sample timing and handling", "Platelets swell in the tube over time, so delays raise MPV."),
    ],
    keep=None,
    myth=["MPV on its own is rarely meaningful. It helps a doctor read an abnormal platelet count."],
    na=dict(keeping_healthy="A platelet index read with the platelet count."),
)
X["WB-053"] = dict(
    fx=[
        ("Hydration", "Dehydration reduces the fluid part of blood, raising haematocrit."),
        ("Haemoglobin and iron levels", "Haematocrit falls with anaemia from low iron or other causes."),
        ("Smoking", "Smoking raises red cell mass."),
        ("Altitude", "Living high up raises red cells."),
    ],
    keep=None,
    myth=["Haematocrit tells the same story as haemoglobin in most people, so they are read together."],
    na=dict(keeping_healthy="Follows haemoglobin and hydration."),
)
X["WB-054"] = dict(
    fx=[
        ("Infection", "Many infections raise platelets as part of the body's reaction, while viral infections such as dengue lower them."),
        ("Inflammation", "Ongoing inflammation raises platelets."),
        ("Low iron", "Iron shortage often raises platelets."),
        ("Some medicines", "Some antibiotics, heparin and others can lower platelets."),
        ("Alcohol", "Heavy drinking lowers platelets."),
        ("Sample clumping", "Platelets can clump in the tube and give a falsely low count."),
    ],
    keep=None,
    myth=["Papaya leaf juice is not a proven treatment for low platelets in dengue. Dengue needs medical monitoring."],
    na=dict(keeping_healthy="The platelet count follows infection, marrow and medicines."),
)
X["WB-055"] = dict(
    fx=[
        ("Infection", "Bacterial infections usually raise the count; some viral infections lower it."),
        ("Inflammation", "Ongoing inflammation raises white cells."),
        ("Stress", "Physical stress and hard exercise push white cells into the blood for a while."),
        ("Smoking", "Smoking keeps white cells slightly raised."),
        ("Some medicines", "Steroids raise the count; some antibiotics, thyroid medicines and cancer treatments lower it."),
        ("Bone marrow conditions", "Less often, a persistently abnormal count comes from the marrow."),
    ],
    keep=None,
    myth=["A slightly high white count during a cold is normal and usually settles."],
    na=dict(keeping_healthy="Follows infection, stress and medicines."),
)
for _k in ("WB-056", "WB-062"):
    X[_k] = dict(
        fx=[
            ("Iron level", "As iron runs low, new cells are smaller than old ones, so sizes vary more."),
            ("Vitamin B12 and folate", "Shortages produce larger cells alongside normal ones."),
            ("Recent blood loss or treatment", "After bleeding or starting iron or B12, new cells differ in size from old ones."),
        ],
        keep=None,
        myth=["A high RDW is a clue, not a diagnosis. It helps tell early iron shortage from thalassaemia trait."],
        na=dict(keeping_healthy="A red cell index that follows iron and vitamin status."),
    )
for _k, _parts in (("WB-063", "MCV divided by the red cell count"), ("WB-065", "a formula using MCV, haemoglobin and the red cell count"), ("WB-066", "MCV and RDW multiplied and divided by the red cell count")):
    X[_k] = dict(
        fx=[(_p.strip(), "This index is calculated from the red cell results above, so it changes when they change.") for _p in ["Red cell measurements"]] + [
            ("Iron level", "Iron shortage and thalassaemia trait push the result in different directions, which is why the index exists."),
            ("Calculation method", f"The index is {_parts}; the method and cut-offs your lab used are not confirmed."),
        ],
        keep=None,
        myth=["These indices only suggest whether iron shortage or thalassaemia trait is more likely. Neither can be confirmed without other tests."],
        na=dict(keeping_healthy="A calculated screening index."),
    )
X["WB-064"] = dict(
    fx=[
        ("Hydration", "Dehydration concentrates the blood and raises the count."),
        ("Iron, B12 and folate", "Shortages reduce red cell production."),
        ("Smoking", "Smoking raises red cell production."),
        ("Altitude", "Living high up raises red cells."),
        ("Thalassaemia trait", "This trait often gives a high count of small cells with a normal or slightly low haemoglobin."),
    ],
    keep=None,
    myth=["A high red cell count with small cells is a classic clue to thalassaemia trait, not to having too much blood."],
    na=dict(keeping_healthy="Follows iron, vitamins, hydration and inherited traits."),
)
X["WB-112"] = dict(
    fx=[
        ("Iron intake and tablets", "Iron tablets or an iron-rich meal raise blood iron for several hours."),
        ("Time of day", "Iron is highest in the morning and lower later in the day."),
        ("Recent meals", "Eating before the test can raise the result."),
        ("Blood loss", "Losing blood uses up iron."),
        ("Inflammation", "During inflammation the body locks iron away, so blood iron falls even if stores are fine."),
    ],
    keep=_IRON_KEEP,
    risk=_IRON_RISK,
    myth=["Serum iron changes hour to hour, so ferritin is a better guide to stores."],
)
X["WB-113"] = dict(
    fx=[
        ("Iron stores", "When stores are low, the liver makes more transferrin to catch iron, so TIBC rises."),
        ("Inflammation", "Inflammation lowers TIBC."),
        ("Pregnancy or hormone pills", "Oestrogen raises transferrin and TIBC."),
        ("Liver function", "The liver makes transferrin, so liver disease lowers TIBC."),
        ("Nutrition", "Poor nutrition lowers TIBC."),
    ],
    keep=None,
    myth=["A high TIBC is not too much iron. It usually means the body is hungry for iron."],
    na=dict(keeping_healthy="Follows iron stores, hormones and the liver."),
)
X["WB-114"] = dict(
    fx=[
        ("Iron level", "Less iron in the blood leaves more carrier spaces empty, raising UIBC."),
        ("Transferrin level", "More carrier protein, as in iron shortage or pregnancy, raises UIBC."),
        ("Inflammation", "Inflammation lowers transferrin and UIBC."),
    ],
    keep=None,
    myth=["UIBC adds little on its own; it is read with iron and TIBC."],
    na=dict(keeping_healthy="A carrier measure read with iron and TIBC."),
)
X["WB-115"] = dict(
    fx=[
        ("Iron level", "Saturation falls as blood iron falls."),
        ("Iron tablets", "Recent iron tablets raise saturation for some hours."),
        ("Inherited iron overload", "Haemochromatosis makes the gut absorb too much iron, raising saturation."),
        ("Inflammation", "Inflammation lowers blood iron and saturation."),
    ],
    keep=None,
    myth=["A high saturation is worth checking even if you feel well, because iron overload can quietly damage the liver and heart."],
    na=dict(keeping_healthy="Follows blood iron and carrier protein."),
)
X["WB-116"] = dict(
    fx=[
        ("Iron intake", "Too little iron from food slowly empties stores."),
        ("Heavy periods or blood loss", "Regular blood loss is the most common reason stores run low."),
        ("Pregnancy", "The baby draws on the mother's stores."),
        ("Inflammation", "Ferritin rises during inflammation, so it can look normal or high even when stores are low."),
        ("Liver health", "Fatty liver and other liver strain raise ferritin."),
        ("Alcohol", "Regular drinking raises ferritin."),
    ],
    keep=_IRON_KEEP,
    risk=_IRON_RISK,
    myth=["A high ferritin does not always mean too much iron. Inflammation, liver disease, obesity and alcohol can also raise it."],
    thr="Many labs print a lower limit for ferritin that is lower than the level doctors use to diagnose iron deficiency, so a result at the bottom of the range can still mean low stores.",
)
