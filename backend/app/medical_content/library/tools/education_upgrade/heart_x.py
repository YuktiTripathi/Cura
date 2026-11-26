"""Education upgrade for heart and cholesterol results. Pending clinical review.

Each entry adds what the 2.3.1 text lacked: how every influencing factor acts, what keeps a good result
good, what lowers modifiable risk, real misconceptions, and the difference between a laboratory range and
a clinical target. `fix` replaces 2.3.1 text that the sample review found inaccurate.
"""

_LIPID_TARGET = (
    "Many labs print a desirable cut-off rather than a range drawn from healthy people. The level a doctor "
    "aims for depends on your overall heart risk, including blood pressure, blood sugar, smoking and family history, "
    "so the same number can be fine for one person and too high for another."
)

_HEART_KEEP = [
    "Keep doing what supports your blood vessels: regular movement, not smoking, and meals built around vegetables, dal, whole grains and nuts.",
    "Cholesterol can change over years with weight, age and menopause, so repeat checks at the interval your doctor suggests matter even when this result is good.",
]

_HEART_RISK = [
    "Blood pressure, blood sugar and smoking add to the same artery risk as cholesterol, so working on any of them protects your heart.",
    "If close family members had heart disease young, tell your doctor. It changes how your results are judged.",
]

X = {}

X["WB-001"] = dict(
    fx=[
        ("Inherited cholesterol patterns", "Genes set how much cholesterol your liver makes and how fast it clears LDL, so some people run high even with careful eating."),
        ("Foods high in saturated fat", "Ghee, butter, cream, fatty meat and many fried snacks lead the liver to clear less LDL from the blood, which raises the total."),
        ("Body weight", "Extra body fat, especially around the waist, tends to raise LDL and triglycerides and lower HDL."),
        ("Physical activity", "Regular activity mainly lifts HDL and lowers triglycerides, which changes the mix inside the total."),
        ("Thyroid function", "An underactive thyroid slows LDL clearance, so cholesterol can rise until the thyroid is treated."),
        ("Cholesterol-lowering medicines", "Statins and similar medicines lower LDL, which brings the total down."),
    ],
    keep=_HEART_KEEP,
    risk=_HEART_RISK,
    myth=[
        "A normal total does not always mean a healthy pattern. A high HDL can hide a raised LDL inside a normal-looking total, so the separate results matter more.",
        "Thin people can have high cholesterol too, because genes play a large part.",
    ],
    thr=_LIPID_TARGET,
)

X["WB-002"] = dict(
    fx=[
        ("Physical activity", "Regular aerobic activity such as brisk walking is one of the few habits shown to raise HDL."),
        ("Smoking", "Smoking lowers HDL; stopping lets it recover."),
        ("Waist size and body weight", "Extra fat around the waist goes with lower HDL; losing some of it can raise HDL a little."),
        ("Triglyceride levels", "When triglycerides are high, HDL particles are reshaped and cleared faster, so HDL usually falls."),
        ("Inherited patterns", "Genes strongly shape HDL, which is why some people have low or very high HDL despite their habits."),
        ("Some medicines", "Some medicines, such as anabolic steroids and some blood pressure tablets, can lower HDL."),
    ],
    fix=dict(
        body=[
            "HDL particles pick up spare cholesterol from tissues and artery walls.",
            "HDL carries it back to your liver, which clears it from your body.",
            "This test measures how much cholesterol is inside HDL particles. It does not measure how well those particles are doing their clean-up work.",
        ],
        high="Higher HDL is generally linked with lower heart risk. Very high levels, above about 100 mg/dL, do not add extra protection and in some people come from inherited patterns or heavy alcohol use.",
        normal="Your HDL is inside the healthy range, which is encouraging. It is still read together with your LDL, triglycerides and other heart risk factors, because a good HDL does not cancel out a high LDL.",
    ),
    keep=[
        "Regular activity and not smoking are the habits most linked with keeping HDL healthy.",
        "If you do not drink alcohol, there is no reason to start to raise HDL.",
    ],
    risk=_HEART_RISK,
    myth=[
        "More HDL is not always better. Raising HDL with medicines has not lowered heart attacks, so doctors do not treat HDL as a target on its own.",
        "HDL concentration is not the same as HDL working well. Two people with the same HDL number can have particles that clear cholesterol differently.",
    ],
    thr="Healthy HDL is usually above 40 mg/dL for men and above 50 mg/dL for women. Some reports print one cut-off for everyone, so check which applies to you.",
)

X["WB-003"] = dict(
    fx=[
        ("Recent meal or not fasting", "Fat from a meal enters the blood as triglycerides for several hours, so a non-fasting sample can read higher."),
        ("Sugar and refined carbohydrates", "When you eat more sugar or refined flour than you burn, your liver turns the extra into triglycerides."),
        ("Alcohol", "Alcohol is turned into fat by the liver and can push triglycerides up sharply, even in moderate amounts for some people."),
        ("Body weight", "Extra weight, especially around the waist, goes with higher triglycerides."),
        ("Insulin resistance or diabetes", "When insulin works poorly, the liver makes more triglyceride-rich particles and the body clears them more slowly."),
        ("Thyroid function", "An underactive thyroid can slow how quickly triglycerides are cleared."),
    ],
    keep=_HEART_KEEP,
    risk=[
        "Triglycerides respond quickly to cutting sugary drinks, sweets, refined flour and alcohol, often within weeks.",
        "Very high triglycerides, roughly above 500 mg/dL, can inflame the pancreas, so they need prompt medical advice.",
    ],
    myth=["Triglycerides are not only about fatty food. Sugar, refined carbohydrates and alcohol often raise them more."],
    thr=_LIPID_TARGET,
)

X["WB-004"] = dict(
    fx=[
        ("LDL cholesterol", "Non-HDL includes LDL, so anything that raises LDL raises non-HDL."),
        ("Triglyceride levels", "Non-HDL also includes VLDL and remnant particles, which carry triglycerides, so high triglycerides lift it."),
        ("Foods high in saturated fat", "These lead the liver to clear less LDL, which raises non-HDL."),
        ("Inherited patterns", "Genes shape how many plaque-forming particles your liver makes and clears."),
        ("Cholesterol-lowering medicines", "Statins and similar medicines lower LDL and so lower non-HDL."),
    ],
    keep=_HEART_KEEP,
    risk=_HEART_RISK,
    myth=["Non-HDL does not need a fasting sample to be useful, which is one reason doctors like it."],
    thr=_LIPID_TARGET,
)

for _k, _a, _b in [("WB-005", "Total cholesterol", "HDL cholesterol"), ("WB-008", "LDL cholesterol", "HDL cholesterol"), ("WB-009", "HDL cholesterol", "LDL cholesterol")]:
    X[_k] = dict(
        fx=[
            (_a, f"A ratio moves when either part moves, so a change in {_a} shifts the ratio even if {_b} stays the same."),
            (_b, f"Likewise a change in {_b} shifts the ratio; looking at the two results separately shows which one moved."),
        ],
        keep=_HEART_KEEP,
        risk=_HEART_RISK,
        myth=["A ratio cannot replace the separate results. Two very different cholesterol patterns can give the same ratio."],
    )

X["WB-006"] = dict(
    fx=[
        ("Foods high in saturated and trans fat", "Saturated fat (ghee, butter, cream, fatty meat) and trans fat (some fried and bakery foods, vanaspati) lead the liver to clear less LDL."),
        ("Inherited patterns", "Some families carry genes that slow LDL clearance, giving very high LDL from a young age."),
        ("Body weight", "Extra weight tends to raise LDL a little; the effect is larger on triglycerides and HDL."),
        ("Thyroid function", "An underactive thyroid slows LDL clearance."),
        ("Kidney or liver conditions", "Some kidney conditions that leak protein, and blocked bile flow, can raise LDL."),
        ("Cholesterol-lowering medicines", "Statins and similar medicines lower LDL substantially."),
    ],
    keep=_HEART_KEEP,
    risk=[
        "Soluble fibre from oats, dal, rajma, chana and fruit helps the body remove some cholesterol.",
        "Swapping ghee, butter and fried snacks for small amounts of mustard, groundnut or olive oil and nuts lowers LDL.",
    ] + _HEART_RISK[:1],
    myth=[
        "Feeling well does not mean LDL is fine. High LDL causes no symptoms while it builds up in arteries.",
        "This LDL is usually calculated from other results, not measured directly, so it can be less accurate when triglycerides are very high.",
    ],
    thr=_LIPID_TARGET,
)

X["WB-007"] = dict(
    fx=[
        ("Triglyceride levels", "VLDL is usually estimated from triglycerides, so it rises and falls with them."),
        ("Sugar and refined carbohydrates", "Extra sugar is turned into triglycerides, which the liver packs into VLDL."),
        ("Alcohol", "Alcohol makes the liver produce more VLDL."),
        ("Body weight", "Extra weight goes with more VLDL production."),
        ("Insulin resistance or diabetes", "When insulin works poorly, the liver releases more VLDL."),
    ],
    keep=_HEART_KEEP,
    risk=_HEART_RISK,
    myth=["VLDL on most reports is calculated from triglycerides, so it adds little new information on its own."],
)

X["WB-110"] = dict(
    fx=[
        ("Inherited genes", "Lp(a) is set mostly by genes, so it stays roughly the same through life."),
        ("Kidney disease", "Some kidney conditions can raise Lp(a)."),
        ("Menopause", "Lp(a) can rise somewhat after menopause."),
        ("Some medicines", "A few medicines change Lp(a) a little; ordinary statins usually do not lower it."),
    ],
    keep=None,
    risk=[
        "Diet and exercise do not change Lp(a) much, so a high result is a reason to control the risks you can change: LDL, blood pressure, blood sugar and smoking.",
        "Because it is inherited, close family members may want their Lp(a) checked.",
    ],
    myth=["A high Lp(a) is not something you caused by eating badly. It is mainly inherited."],
    thr="Labs often use fixed risk cut-offs for Lp(a), such as above 50 mg/dL or 125 nmol/L, and the units differ between labs, so compare with the cut-off printed on your report.",
    na=dict(keeping_healthy="Lp(a) is set by genes and everyday habits barely change it."),
)

X["WB-111"] = dict(
    fx=[
        ("Inherited patterns", "Genes set how many cholesterol-carrying particles your liver releases and clears."),
        ("Triglyceride levels", "High triglycerides often come with many small particles, each carrying one ApoB, so ApoB can be high even when LDL looks moderate."),
        ("Diet and body weight", "Saturated fat, sugar and extra weight increase the number of these particles."),
        ("Insulin resistance or diabetes", "Poor insulin action raises the number of small, dense particles."),
        ("Cholesterol-lowering medicines", "Statins lower ApoB along with LDL."),
    ],
    keep=_HEART_KEEP,
    risk=_HEART_RISK,
    myth=["ApoB is not another kind of cholesterol. It counts the particles that can enter artery walls, so it can add information when LDL and triglycerides disagree."],
    thr=_LIPID_TARGET,
)
