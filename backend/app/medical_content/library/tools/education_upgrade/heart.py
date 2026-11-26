"""Revision 2.3.1 content: heart and blood fats. Pending clinical review."""

C = {}

C["WB-001"] = dict(
    d="Total cholesterol is the full amount of cholesterol travelling in your blood, counting both the helpful and the less helpful kinds together.",
    body=[
        "Cholesterol is a waxy fat your body needs to build cells and make some hormones and vitamin D.",
        "Your liver makes most of it, and the rest comes from food.",
        "Cholesterol cannot dissolve in blood, so it travels inside tiny carrier particles. LDL and HDL are the best known.",
    ],
    why=[
        "Too much cholesterol in the wrong carriers can slowly build up in artery walls and narrow them.",
        "It is usually checked as part of a lipid profile to judge heart and blood vessel health.",
    ],
    high="A higher total usually means more cholesterol is circulating. It may come from LDL, which can build up in arteries, or partly from HDL, which is helpful. Your LDL and HDL results show which one is driving it.",
    low="A lower total is often a good sign for the heart. Very low values are uncommon and can occasionally go with an overactive thyroid, poor nutrition or some liver conditions.",
    normal="Your total cholesterol is inside the lab's range. Heart risk still depends on how it is split between LDL and HDL, and on things like blood pressure, smoking and diabetes.",
    factors=["Inherited cholesterol patterns", "Foods high in saturated fat", "Body weight", "Physical activity", "Thyroid function", "Cholesterol-lowering medicines"],
    life=[
        "Foods rich in saturated fat, such as fatty meat, butter, ghee and many fried or packaged snacks, tend to raise blood cholesterol.",
        "Soluble fibre from oats, dal, beans and fruit helps your body clear cholesterol.",
    ],
    support=[
        "Choose oils like mustard, groundnut or olive oil more often than ghee, butter or vanaspati. Unsaturated fats are kinder to blood cholesterol.",
        "Add a bowl of dal, beans, oats or vegetables to most meals. Their fibre helps carry cholesterol out of your body.",
        "Try to move for about 30 minutes on most days, such as a brisk walk. Regular activity helps raise HDL and lower other blood fats.",
    ],
    seek=[
        "Talk to a doctor if your cholesterol is high and you also have diabetes or high blood pressure.", "Also talk to a doctor if a parent or sibling had a heart attack or stroke at a young age.",
    ],
    limits=["Total cholesterol adds HDL and LDL together, so on its own it cannot show whether the cholesterol is mostly the helpful or the harmful kind."],
    q=dict(
        high=["Should I be worried about my high cholesterol?", "Is my cholesterol high because of HDL or LDL?", "What foods can help bring my cholesterol down?", "What does my cholesterol say about my heart health?"],
        low=["Is low cholesterol a good thing?", "Can cholesterol be too low?", "What does my cholesterol say about my heart health?"],
        normal=["My cholesterol is normal. Does that mean my heart is healthy?", "Why do LDL and HDL matter more than total cholesterol?", "How often should I check my cholesterol?"],
    ),
)

C["WB-002"] = dict(
    d="HDL is often called good cholesterol. This test measures how much cholesterol is carried by HDL particles, which help remove extra cholesterol from your body.",
    body=[
        "HDL particles pick up spare cholesterol from tissues and artery walls.",
        "HDL carries it back to your liver, which clears it from your body.",
        "So HDL works a bit like a clean-up crew for your blood vessels.",
    ],
    why=[
        "Low HDL is linked with a higher chance of heart disease.",
        "Doctors look at HDL together with LDL and triglycerides to judge heart risk.",
    ],
    high="Higher HDL is generally linked with lower heart risk. Very high levels do not always add extra protection, and in rare cases they come from inherited patterns or heavy alcohol use.",
    low="Low HDL means less cholesterol is being cleared away. It often goes with low activity, smoking, extra weight around the waist, high triglycerides or insulin resistance.",
    normal="Your HDL is inside the lab's range, which is a helpful sign. It is still read together with your LDL, triglycerides and other heart risk factors.",
    factors=["Physical activity", "Smoking", "Waist size and body weight", "Triglyceride levels", "Inherited patterns", "Some medicines"],
    life=[
        "Regular physical activity and stopping smoking are among the most reliable ways HDL rises.",
        "Diets high in refined carbohydrates and sugar tend to go with lower HDL and higher triglycerides.",
    ],
    support=[
        "Build movement into your day, such as walking after meals or taking stairs. Regular activity is one of the few habits known to lift HDL.",
        "If you smoke, ask about support to stop. Stopping smoking helps HDL recover and protects your blood vessels.",
        "Cut back on sugary drinks, sweets and refined flour. They push triglycerides up, which usually pulls HDL down.",
    ],
    seek=["Talk to a doctor if HDL is low alongside high LDL, high triglycerides, high blood sugar or high blood pressure, as these together raise heart risk."],
    limits=["HDL measures the cholesterol inside HDL particles, not how well those particles work. A good HDL result does not cancel out a high LDL."],
    q=dict(
        high=["Is a very high HDL always good?", "Does a good HDL protect me if my LDL is high?", "What does my cholesterol say about my heart health?"],
        low=["Why is my good cholesterol low?", "How can I raise my HDL naturally?", "Does low HDL mean I will get heart disease?"],
        normal=["What does a healthy HDL do for my heart?", "How do HDL and LDL work together?", "What habits help keep my HDL healthy?"],
    ),
)

C["WB-003"] = dict(
    d="Triglycerides are the most common type of fat in your blood. Your body stores spare energy from food as triglycerides and uses them as fuel between meals.",
    body=[
        "When you eat more energy than you need right away, your body turns the extra into triglycerides.",
        "Triglycerides are stored in fat cells and released later when you need energy.",
        "Sugar, refined carbohydrates and alcohol are easily turned into triglycerides by the liver.",
    ],
    why=[
        "High triglycerides are linked with heart disease, fatty liver and insulin resistance.",
        "Very high levels can inflame the pancreas, an organ behind the stomach that helps digestion.",
    ],
    high="Higher triglycerides often reflect a recent meal, extra sugar or refined carbohydrates, alcohol, extra weight or insulin resistance. If you did not fast before the test, the result can read higher.",
    low="Low triglycerides are usually not a concern. They can go with a low-fat diet, regular exercise, and occasionally an overactive thyroid or poor absorption of food.",
    normal="Your triglycerides are inside the lab's range, which suggests your body is handling fats from food well at the moment.",
    factors=["Recent meal or not fasting", "Sugar and refined carbohydrates", "Alcohol", "Body weight", "Insulin resistance or diabetes", "Thyroid function"],
    life=[
        "Sweets, sugary drinks, white rice and maida-based foods in large amounts can raise triglycerides.",
        "Alcohol raises triglycerides strongly in some people, even in modest amounts.",
        "Regular activity helps your muscles burn triglycerides for fuel.",
    ],
    support=[
        "Swap sugary drinks and packaged juices for water, buttermilk or unsweetened tea. Liquid sugar is turned into triglycerides quickly.",
        "Fill half your plate with vegetables and choose smaller portions of rice, roti or bread. This lowers the sugar load your liver has to process.",
        "Keep alcohol low or avoid it. Even small amounts can raise triglycerides in some people.",
        "Walk for 10 to 15 minutes after main meals. Moving muscles use blood fats and sugar as fuel.",
    ],
    seek=[
        "See a doctor soon if your triglycerides are very high, especially with tummy pain, as very high levels can inflame the pancreas.",
        "Talk to a doctor if triglycerides are high along with high blood sugar or signs of fatty liver.",
    ],
    limits=["Triglycerides change a lot after eating and drinking alcohol, so one result may not reflect your usual level."],
    q=dict(
        high=["Why are my triglycerides high?", "Do I need to fast before a triglyceride test?", "Can cutting sugar lower my triglycerides?", "Are high triglycerides linked to fatty liver?"],
        low=["Is it a problem if my triglycerides are low?", "What do triglycerides do in my body?"],
        normal=["What keeps triglycerides healthy?", "How are triglycerides different from cholesterol?", "Does alcohol affect triglycerides?"],
    ),
)

C["WB-004"] = dict(
    d="Non-HDL cholesterol is your total cholesterol minus your HDL. It shows all the cholesterol carried in particles that can build up in artery walls.",
    body=[
        "Several kinds of carrier particles, including LDL and VLDL, can leave cholesterol in artery walls.",
        "Non-HDL adds all of these together into one number.",
        "It is calculated from your results, so no extra blood is needed.",
    ],
    why=[
        "Non-HDL can be a better guide to heart risk than LDL alone, especially when triglycerides are high.",
        "It is still reliable if you had eaten before the test.",
    ],
    high="A higher non-HDL means more cholesterol is in particles that can narrow arteries. It usually rises with high LDL or high triglycerides.",
    low="A lower non-HDL is generally favourable for heart health.",
    normal="Your non-HDL cholesterol is inside the lab's range, which suggests the amount of plaque-forming cholesterol is not raised.",
    factors=["LDL cholesterol", "Triglyceride levels", "Foods high in saturated fat", "Inherited patterns", "Cholesterol-lowering medicines"],
    life=["The same habits that lower LDL and triglycerides, such as less saturated fat, less sugar and more activity, also lower non-HDL cholesterol."],
    support=[
        "Cut down on fried snacks, sweets and fatty meat. They feed both LDL and triglycerides, the two parts of non-HDL.",
        "Eat more fibre from dal, oats, beans, fruit and vegetables. Fibre helps remove cholesterol from your body.",
        "Aim for regular activity most days. It lowers triglycerides and supports healthy cholesterol.",
    ],
    seek=["Talk to a doctor if non-HDL is high, especially with diabetes, high blood pressure, smoking or early heart disease in your family."],
    limits=["Non-HDL is calculated from other results, so any error in total cholesterol or HDL carries through to it."],
    not_applicable={},
    q=dict(
        high=["What does a high non-HDL cholesterol mean for my heart?", "Is non-HDL more important than LDL?", "How can I lower my non-HDL cholesterol?"],
        low=["Is a low non-HDL good for my heart?", "What is included in non-HDL cholesterol?"],
        normal=["What is non-HDL cholesterol and why is it on my report?", "Is non-HDL more important than LDL?"],
    ),
)

_RATIO_NA = {"practical_guidance": "Calculated ratio. Habits act on the cholesterol results it is built from; guidance sits on those entries."}

C["WB-005"] = dict(
    d="This ratio divides your total cholesterol by your HDL (good cholesterol). It gives a quick sense of how much of your cholesterol is the helpful kind.",
    body=[
        "A smaller number means a larger share of your cholesterol is HDL.",
        "A bigger number means less HDL compared with the total.",
        "It is worked out from your two results and is not a separate blood measurement.",
    ],
    why=["Doctors sometimes use this ratio as one simple pointer to heart risk alongside other results."],
    high="A higher ratio means HDL makes up a smaller share of your cholesterol. This is linked with higher heart risk, usually because LDL is high, HDL is low, or both.",
    low="A lower ratio means HDL makes up a good share of your cholesterol, which is generally favourable.",
    normal="Your ratio is inside the lab's range, suggesting a reasonable balance between total cholesterol and HDL.",
    factors=["Total cholesterol", "HDL cholesterol"],
    life=None,
    support=[],
    seek=["Talk to a doctor if the ratio is high together with other heart risk factors such as diabetes or high blood pressure."],
    limits=["A ratio can look fine even when both numbers are high, so the separate cholesterol results still matter."],
    not_applicable={**_RATIO_NA, "lifestyle_relationships": "Calculated ratio; lifestyle links are covered by total cholesterol and HDL."},
    q=dict(
        high=["What does a high cholesterol ratio mean?", "Should I focus on raising HDL or lowering LDL?", "What does my cholesterol say about my heart health?"],
        low=["Is a low cholesterol ratio good?", "How is this ratio worked out?"],
        normal=["Why does my report show a cholesterol ratio?", "Can my ratio be fine even if my cholesterol is high?"],
    ),
)

C["WB-006"] = dict(
    d="LDL is often called bad cholesterol. This result estimates how much cholesterol is carried by LDL particles, the main type that builds up in artery walls.",
    body=[
        "LDL particles deliver cholesterol to cells around your body.",
        "When there are too many, some get trapped in artery walls and form fatty deposits called plaque.",
        "Plaque can slowly narrow arteries and reduce blood flow to the heart and brain.",
    ],
    why=[
        "LDL is the main cholesterol target doctors use to judge and treat heart risk.",
        "This lab calculates LDL from your other cholesterol results instead of measuring it directly.",
    ],
    high="A higher LDL means more cholesterol is available to build up in arteries. Diet, weight, inherited patterns and other conditions can all raise it. Very high values can point to an inherited cholesterol condition.",
    low="A lower LDL is generally good for heart health. Very low values are uncommon and may be checked if there is a medical reason.",
    normal="Your LDL is inside the lab's range. The healthy target for you can be lower if you have diabetes, kidney disease or existing heart disease, so a doctor may set a personal goal.",
    factors=["Foods high in saturated and trans fat", "Inherited patterns", "Body weight", "Thyroid function", "Kidney or liver conditions", "Cholesterol-lowering medicines"],
    life=[
        "Saturated fat from ghee, butter, cream, fatty meat and many bakery and fried foods raises LDL.",
        "Trans fats in vanaspati and some packaged snacks raise LDL and lower HDL.",
        "Soluble fibre and nuts can help lower LDL modestly.",
    ],
    support=[
        "Cook with less ghee, butter and vanaspati, and use plant oils in small amounts instead. This lowers the saturated and trans fat that raise LDL.",
        "Eat oats, dal, rajma, chana or barley several times a week. Their soluble fibre binds cholesterol in the gut.",
        "Have a small handful of unsalted nuts most days in place of fried snacks. Nuts contain fats that can help LDL.",
        "Keep active and work towards a healthy waist size. Both help LDL and overall heart health.",
    ],
    seek=[
        "Talk to a doctor if LDL is high, especially if you have diabetes, high blood pressure, kidney disease or family members who had heart problems young.",
        "Very high LDL can be inherited and may need medical treatment, as diet alone is often not enough.",
    ],
    limits=["Calculated LDL is less accurate when triglycerides are very high or LDL is very low, and it does not show the number of LDL particles."],
    q=dict(
        high=["Should I be concerned about my high LDL?", "Can I lower my LDL with diet alone?", "Could my high LDL be inherited?", "What does my cholesterol say about my heart health?"],
        low=["Is a low LDL good for me?", "Can LDL be too low?"],
        normal=["What LDL level is right for me?", "Why is LDL called bad cholesterol?", "What habits help keep my LDL low?"],
    ),
)

C["WB-007"] = dict(
    d="VLDL cholesterol is the cholesterol carried in very low-density lipoprotein, a particle your liver makes to carry triglycerides (blood fats) around your body.",
    body=[
        "Your liver packs triglycerides into VLDL particles and sends them into your blood.",
        "As they release fat to your tissues, VLDL particles shrink and can turn into LDL.",
        "Most labs estimate VLDL from your triglyceride result rather than measuring it directly.",
    ],
    why=["VLDL gives an extra view of how many fat-carrying particles your liver is making, which is linked with heart risk."],
    high="Higher VLDL usually goes with high triglycerides. It often reflects extra sugar or refined carbohydrates, alcohol, extra weight or insulin resistance.",
    low="Low VLDL is usually not a concern and generally matches low triglycerides.",
    normal="Your VLDL is inside the lab's range, which usually matches healthy triglyceride levels.",
    factors=["Triglyceride levels", "Sugar and refined carbohydrates", "Alcohol", "Body weight", "Insulin resistance or diabetes"],
    life=["VLDL follows triglycerides closely, so cutting back on sugar, refined flour and alcohol and staying active usually lowers both."],
    support=[
        "Limit sweets, sugary drinks and refined flour. Your liver turns extra sugar into the fat that VLDL carries.",
        "Keep alcohol low or avoid it. Alcohol increases the fat your liver sends out in VLDL.",
        "Stay active on most days. Active muscles take up and burn blood fats.",
    ],
    seek=["Talk to a doctor if VLDL and triglycerides are both high, particularly with high blood sugar or a large waist."],
    limits=["VLDL is usually estimated from triglycerides, so it adds little information beyond the triglyceride result and is less reliable when triglycerides are very high."],
    q=dict(
        high=["Why is my VLDL high?", "How are VLDL and triglycerides connected?", "Can diet lower my VLDL?"],
        low=["Is a low VLDL good?", "What does VLDL do in my body?"],
        normal=["What is VLDL and why is it on my report?", "How are VLDL and triglycerides connected?"],
    ),
)

C["WB-008"] = dict(
    d="This ratio compares your LDL (bad cholesterol) with your HDL (good cholesterol). It shows how much plaque-forming cholesterol you have for each unit of the helpful kind.",
    body=["A higher number means more LDL compared with HDL.", "It is calculated from your two cholesterol results, not measured separately."],
    why=["It is a simple way to see the balance between cholesterol that builds up in arteries and cholesterol that is cleared away."],
    high="A higher ratio means LDL is high compared with HDL. This balance is linked with higher heart risk.",
    low="A lower ratio means HDL is strong compared with LDL, which is generally favourable.",
    normal="Your ratio is inside the lab's range, suggesting a reasonable balance between LDL and HDL.",
    factors=["LDL cholesterol", "HDL cholesterol"],
    life=None, support=[],
    seek=["Talk to a doctor if the ratio is high along with diabetes, high blood pressure or a family history of early heart disease."],
    limits=["The ratio can hide a high LDL if HDL is also high, so the separate results still need to be read."],
    not_applicable={**_RATIO_NA, "lifestyle_relationships": "Calculated ratio; lifestyle links are covered by LDL and HDL."},
    q=dict(
        high=["What does a high LDL to HDL ratio mean?", "Which matters more, my ratio or my LDL?"],
        low=["Is a low LDL to HDL ratio good?", "How is this ratio worked out?"],
        normal=["Why does my report show an LDL to HDL ratio?", "Can my ratio be fine even if LDL is high?"],
    ),
)

C["WB-009"] = dict(
    d="This ratio compares your HDL (good cholesterol) with your LDL (bad cholesterol). It is the LDL to HDL ratio turned the other way up, so here a higher number is better.",
    body=["A higher number means you have more HDL for each unit of LDL.", "It is calculated from your two cholesterol results."],
    why=["It shows the same balance as the LDL to HDL ratio, just expressed the other way round."],
    high="A higher ratio means HDL is strong compared with LDL, which is generally favourable for the heart.",
    low="A lower ratio means LDL is high compared with HDL. This balance is linked with higher heart risk.",
    normal="Your ratio is inside the lab's range, suggesting a reasonable balance between HDL and LDL.",
    factors=["HDL cholesterol", "LDL cholesterol"],
    life=None, support=[],
    seek=["Talk to a doctor if the ratio is low along with other heart risk factors."],
    limits=["Because this ratio is the reverse of the LDL to HDL ratio, it does not add new information. The separate results matter most."],
    not_applicable={**_RATIO_NA, "lifestyle_relationships": "Calculated ratio; lifestyle links are covered by LDL and HDL."},
    q=dict(
        high=["Is a high HDL to LDL ratio good?", "Which result should I focus on, LDL or HDL?"],
        low=["What does a low HDL to LDL ratio mean for my heart?", "How can I improve my cholesterol balance?"],
        normal=["Why does my report show an HDL to LDL ratio?", "Is this the same as the LDL to HDL ratio?"],
    ),
)

C["WB-110"] = dict(
    d="Lipoprotein(a), or Lp(a), is a type of cholesterol-carrying particle whose level is set mostly by the genes you inherit.",
    body=[
        "Lp(a) looks like an LDL particle with an extra protein attached.",
        "It can add to plaque build-up in arteries and may make blood clots more likely.",
        "Your level stays fairly steady through life because it is mainly inherited.",
    ],
    why=[
        "A high Lp(a) can raise heart and stroke risk even when other cholesterol results look fine.",
        "Many experts suggest checking it at least once in adulthood, especially with early heart disease in the family.",
    ],
    high="A higher Lp(a) means an inherited increase in heart and blood vessel risk. It does not mean you have heart disease, but it makes managing your other risk factors more important.",
    low="A low Lp(a) means this inherited risk factor is not raised.",
    normal="Your Lp(a) is inside the lab's range, so this inherited risk factor does not appear to be raised.",
    factors=["Inherited genes", "Kidney disease", "Menopause", "Some medicines"],
    life=["Lp(a) is mostly decided by genes and changes very little with diet or exercise."],
    support=[],
    seek=[
        "Talk to a doctor if Lp(a) is high. They may focus more closely on your LDL, blood pressure and other risks.",
        "Close family members may want to ask about being tested, as high Lp(a) runs in families.",
    ],
    limits=["Different labs report Lp(a) in different units, so results from different labs cannot always be compared directly."],
    not_applicable={"practical_guidance": "Lp(a) is largely inherited and is not meaningfully lowered by everyday habits. Guidance is to manage other heart risk factors with a doctor."},
    q=dict(
        high=["What does a high Lp(a) mean for my heart?", "Can I lower my Lp(a) with diet or exercise?", "Should my family get their Lp(a) checked?"],
        low=["Do I need to test my Lp(a) again?", "Why is Lp(a) different from LDL?"],
        normal=["Why was Lp(a) tested?", "Do I need to test my Lp(a) again?", "How is Lp(a) different from LDL?"],
    ),
)

C["WB-111"] = dict(
    d="Apolipoprotein B, or ApoB, is a protein found on each particle that can carry cholesterol into artery walls. Measuring it gives a count of those particles.",
    body=[
        "Each LDL, VLDL and Lp(a) particle carries one ApoB protein.",
        "So ApoB shows how many plaque-forming particles are in your blood, not just how much cholesterol they hold.",
        "More particles means more chances for them to get trapped in artery walls.",
    ],
    why=["ApoB can show raised heart risk that LDL misses, especially in people with high triglycerides, diabetes or extra weight."],
    high="A higher ApoB means more cholesterol-carrying particles that can build up in arteries. It is linked with higher heart risk, even if LDL looks acceptable.",
    low="A lower ApoB means fewer plaque-forming particles, which is generally favourable.",
    normal="Your ApoB is inside the lab's range, suggesting the number of plaque-forming particles is not raised.",
    factors=["Inherited patterns", "Triglyceride levels", "Diet and body weight", "Insulin resistance or diabetes", "Cholesterol-lowering medicines"],
    life=["The habits that lower LDL and triglycerides, such as less saturated fat and sugar, more fibre and regular activity, also tend to lower ApoB."],
    support=[
        "Choose plant oils, dal, beans and vegetables more often than fried foods and fatty meat. This lowers the cholesterol particles that ApoB counts.",
        "Cut back on sugary foods and drinks. Extra sugar makes the liver release more fat-carrying particles.",
        "Stay active on most days. Activity helps your body clear blood fats.",
    ],
    seek=["Talk to a doctor if ApoB is high, especially alongside diabetes, high blood pressure or early heart disease in your family."],
    limits=["ApoB is not part of every routine cholesterol test, and target levels depend on your overall heart risk."],
    q=dict(
        high=["What does a high ApoB mean for my heart?", "Is ApoB more important than LDL?", "How can I lower my ApoB?"],
        low=["Is a low ApoB good?", "What does ApoB measure?"],
        normal=["Why was ApoB tested if I already have LDL?", "What does ApoB tell me about my heart?"],
    ),
)
