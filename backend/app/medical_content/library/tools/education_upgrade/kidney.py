"""Revision 2.3.1 content: kidney function, salts and minerals. Pending clinical review."""

C = {}

_KIDNEY_SEEK = "Talk to a doctor if kidney results are abnormal, especially with diabetes, high blood pressure, swelling, foamy urine or passing much less urine."
_HYDRATE = "Drink water regularly through the day, more in hot weather or after sweating. Good hydration helps your kidneys and keeps results reliable."

C["WB-022"] = dict(
    d="Blood urea nitrogen, or BUN, measures urea in your blood. Urea is a waste product made when your body breaks down protein, and your kidneys remove it.",
    body=[
        "When your body uses protein, it makes ammonia, which the liver turns into urea.",
        "Urea travels in the blood to the kidneys, which filter it out into urine.",
        "If the kidneys filter less well, or you are dehydrated, urea builds up in the blood.",
    ],
    why=["BUN is one of the basic checks of kidney function and hydration, usually read with creatinine."],
    high="Higher BUN often means you were dehydrated, ate a lot of protein, or have bleeding in the stomach or gut. It can also mean the kidneys are filtering less well.",
    low="Lower BUN can come from a low-protein diet, drinking a lot of fluid, pregnancy or, less often, liver disease.",
    normal="Your BUN is inside the lab's range, suggesting your kidneys are clearing protein waste as expected.",
    factors=["Hydration", "Protein intake", "Kidney function", "Bleeding in the gut", "Liver function", "Some medicines"],
    life=["Dehydration and a very high-protein diet can both raise BUN."],
    support=[_HYDRATE],
    seek=[_KIDNEY_SEEK],
    limits=["BUN is affected by diet and hydration, so it is less reliable than creatinine or eGFR for judging kidney function."],
    q=dict(
        high=["Why is my BUN high?", "Can dehydration raise my BUN?", "Is my high BUN a kidney problem?"],
        low=["What does a low BUN mean?"],
        normal=["What does BUN tell me about my kidneys?", "How are BUN and creatinine related?"],
    ),
)

C["WB-023"] = dict(
    d="Total calcium measures all the calcium in your blood. Calcium keeps bones strong and helps nerves, muscles and the heart work properly.",
    body=[
        "Most of your calcium is stored in your bones and teeth.",
        "A small amount in the blood helps muscles contract, nerves send signals and blood clot.",
        "Parathyroid hormone and vitamin D keep blood calcium within a narrow range.",
    ],
    why=["Abnormal calcium can point to problems with the parathyroid glands, vitamin D, kidneys or bones."],
    high="Higher calcium is most often caused by an overactive parathyroid gland. Other causes include too much vitamin D or calcium from supplements, dehydration and, less commonly, some cancers.",
    low="Lower calcium is often linked with low albumin, the protein that carries calcium. It can also come from low vitamin D, low magnesium, kidney disease or low parathyroid hormone.",
    normal="Your calcium is inside the lab's range, suggesting your body is keeping blood calcium well balanced.",
    factors=["Albumin level", "Vitamin D", "Parathyroid hormone", "Kidney function", "Calcium or vitamin D supplements", "Hydration"],
    life=["Getting enough calcium from food and enough vitamin D supports bones, though blood calcium is tightly controlled and rarely changes with diet alone."],
    support=["Include calcium foods such as milk, curd, paneer, ragi, sesame, or calcium-set tofu. These support bone health."],
    seek=["See a doctor if calcium is high or low, especially with muscle cramps, tingling, confusion, constipation, extreme thirst or kidney stones."],
    limits=["Total calcium is affected by albumin. A doctor may correct it for albumin or measure ionised calcium for a truer picture."],
    q=dict(
        high=["Why is my calcium high?", "Can supplements raise my blood calcium?", "What does the parathyroid gland have to do with calcium?"],
        low=["Why is my calcium low?", "Is low calcium linked to low vitamin D?", "Does low albumin affect calcium?"],
        normal=["Does a normal blood calcium mean my bones are healthy?", "How does my body control calcium?"],
    ),
)

C["WB-024"] = dict(
    d="Chloride is a salt mineral in your blood. It works with sodium to keep the right amount of fluid in your body and the right acid balance in your blood.",
    body=[
        "Chloride mostly comes from salt in food.",
        "It moves with sodium and water, helping balance fluid inside and outside your cells.",
        "Your kidneys adjust how much chloride leaves in urine.",
    ],
    why=["Chloride is read with sodium, potassium and bicarbonate to check fluid and acid balance."],
    high="Higher chloride often goes with dehydration, or with conditions that make the blood more acidic, such as diarrhoea or some kidney problems.",
    low="Lower chloride can happen with long-lasting vomiting, some water tablets (diuretics), heart failure or lung conditions.",
    normal="Your chloride is inside the lab's range, suggesting normal fluid and salt balance.",
    factors=["Hydration", "Vomiting or diarrhoea", "Kidney function", "Water tablets (diuretics)", "Salt intake"],
    life=["Chloride follows salt and fluid balance; dehydration is the most common everyday reason it rises."],
    support=[_HYDRATE],
    seek=["See a doctor if chloride is abnormal along with ongoing vomiting, diarrhoea, weakness, confusion or breathing difficulty."],
    limits=["Chloride is rarely meaningful on its own and is interpreted together with sodium and bicarbonate."],
    q=dict(
        high=["Why is my chloride high?", "Can dehydration raise chloride?"],
        low=["Why is my chloride low?", "Can vomiting lower chloride?"],
        normal=["What does chloride do in my body?"],
    ),
)

C["WB-025"] = dict(
    d="Creatinine is a waste product made by your muscles as they work. Your kidneys filter it out, so its level in blood is a good guide to how well your kidneys are working.",
    body=[
        "Your muscles make creatinine at a fairly steady rate every day.",
        "Healthy kidneys filter it out of your blood and into your urine.",
        "When kidney filtering slows, creatinine builds up in the blood.",
    ],
    why=["Creatinine is the main blood test for kidney function and is used to calculate eGFR."],
    high="Higher creatinine can mean the kidneys are filtering less well. It can also rise with dehydration, a lot of muscle, eating plenty of meat before the test, creatine supplements or some medicines.",
    low="Lower creatinine usually reflects less muscle, for example in older or very slim people, or during pregnancy. It is rarely a concern.",
    normal="Your creatinine is inside the lab's range, suggesting your kidneys are filtering waste normally for your muscle size.",
    factors=["Muscle mass", "Hydration", "Kidney function", "Meat eaten before the test", "Creatine supplements", "Some medicines"],
    life=["Dehydration, a large meat meal shortly before the test and creatine supplements can raise creatinine without kidney damage."],
    support=[
        _HYDRATE,
        "Avoid painkillers like ibuprofen and diclofenac for long periods without medical advice. They can strain the kidneys.",
        "Keep blood pressure and blood sugar in check with your doctor. These are the two biggest causes of kidney damage.",
    ],
    seek=[_KIDNEY_SEEK],
    limits=["Creatinine depends on muscle size, so the same value can mean different kidney function in different people. eGFR adjusts for some of this."],
    q=dict(
        high=["Should I be worried about my high creatinine?", "Can dehydration or exercise raise my creatinine?", "What does my creatinine say about my kidneys?"],
        low=["Why is my creatinine low?", "Is low creatinine a problem?"],
        normal=["What does creatinine tell me about my kidneys?", "How are creatinine and eGFR connected?"],
    ),
)

C["WB-026"] = dict(
    d="Sodium is the main salt mineral in your blood. It controls how much water your body holds and helps nerves and muscles work.",
    body=[
        "Sodium mostly comes from salt in food.",
        "It pulls water with it, so it helps decide how much fluid is in your blood and around your cells.",
        "Your kidneys and hormones keep blood sodium within a narrow range.",
    ],
    why=["Abnormal sodium can cause confusion, weakness or seizures, and points to fluid, kidney, hormone or medicine problems."],
    high="Higher sodium usually means your body is short of water, for example from not drinking enough, sweating, vomiting or diarrhoea.",
    low="Lower sodium usually means there is too much water compared with salt. It can come from some medicines such as water tablets, drinking very large amounts of water, heart, liver or kidney conditions, or hormone problems.",
    normal="Your sodium is inside the lab's range, suggesting your body's water and salt balance is steady.",
    factors=["Fluid intake", "Vomiting or diarrhoea", "Water tablets and some other medicines", "Kidney function", "Hormone conditions"],
    life=["Blood sodium mostly reflects water balance. Eating more salt usually raises blood pressure rather than blood sodium."],
    support=[
        "Drink to thirst and a little more in hot weather. Avoid forcing very large amounts of water, which can dilute sodium.",
        "Keep added salt and salty packaged foods low for your blood pressure, even though blood sodium stays steady.",
    ],
    seek=["See a doctor promptly if sodium is abnormal with confusion, headache, vomiting, muscle cramps, unusual sleepiness or seizures."],
    limits=["Blood sodium does not show how much salt you eat."],
    q=dict(
        high=["Why is my sodium high?", "Does high blood sodium mean I eat too much salt?"],
        low=["Why is my sodium low?", "Can drinking too much water lower sodium?", "Can my medicines lower my sodium?"],
        normal=["What does sodium do in my body?", "Does blood sodium show how much salt I eat?"],
    ),
)

C["WB-027"] = dict(
    d="Urea is a waste product made when your body breaks down protein. Your kidneys filter it out into urine.",
    body=[
        "Your liver turns waste from protein into urea.",
        "Urea travels in the blood to the kidneys, which filter it into urine.",
        "Urea and BUN measure the same thing in different ways.",
    ],
    why=["Urea helps check kidney function and hydration, usually alongside creatinine."],
    high="Higher urea often means you were dehydrated, ate a lot of protein or have bleeding in the gut. It can also mean the kidneys are filtering less well.",
    low="Lower urea can come from a low-protein diet, drinking a lot of fluid, pregnancy or, less often, liver disease.",
    normal="Your urea is inside the lab's range, suggesting your kidneys are clearing protein waste as expected.",
    factors=["Hydration", "Protein intake", "Kidney function", "Bleeding in the gut", "Liver function"],
    life=["Dehydration and high-protein meals can raise urea."],
    support=[_HYDRATE],
    seek=[_KIDNEY_SEEK],
    limits=["Urea changes with diet and hydration, so it is less reliable than creatinine for judging kidney function."],
    q=dict(
        high=["Why is my urea high?", "Can eating a lot of protein raise urea?"],
        low=["What does a low urea mean?"],
        normal=["What is the difference between urea and BUN?", "What does urea tell me about my kidneys?"],
    ),
)

C["WB-028"] = dict(
    d="Uric acid is a waste product made when your body breaks down purines, natural substances found in your cells and in some foods.",
    body=[
        "Purines are found in all body cells and in foods like red meat, organ meat, some seafood and beer.",
        "When purines break down, uric acid forms and is mostly removed by the kidneys.",
        "If too much builds up, it can form sharp crystals in joints or kidneys.",
    ],
    why=["High uric acid can lead to gout, a painful joint condition, and kidney stones. It is also linked with high blood pressure and metabolic health."],
    high="Higher uric acid can come from foods rich in purines, alcohol (especially beer), sugary drinks, extra weight, kidneys removing less, or some medicines such as water tablets. Many people with high uric acid never get gout.",
    low="Low uric acid is uncommon and usually not a concern.",
    normal="Your uric acid is inside the lab's range, which lowers the chance of crystals forming in joints or kidneys.",
    factors=["Purine-rich foods", "Alcohol, especially beer", "Sugary drinks", "Body weight", "Kidney function", "Water tablets (diuretics)"],
    life=[
        "Red meat, organ meat, some seafood, beer and drinks sweetened with fructose can raise uric acid.",
        "Losing extra weight gradually and staying well hydrated help lower it.",
    ],
    support=[
        "Cut back on sugary drinks and fruit juices. Fructose raises uric acid.",
        "Limit beer and spirits, and eat red and organ meats less often. These are rich in purines.",
        "Drink plenty of water. It helps your kidneys remove uric acid and may lower the chance of stones.",
    ],
    seek=["See a doctor if you have a sudden hot, swollen, very painful joint, often the big toe, or pain in your side or back that could be a kidney stone."],
    limits=["A high uric acid does not mean you have gout, and uric acid can be normal during a gout attack."],
    q=dict(
        high=["Should I worry about my high uric acid?", "Which foods raise uric acid?", "Does high uric acid mean I have gout?"],
        low=["Is low uric acid a problem?"],
        normal=["What does uric acid do in my body?", "Can my uric acid go up over time?"],
    ),
)

C["WB-029"] = dict(
    d="The BUN to creatinine ratio compares two kidney waste products. The pattern can help show whether a kidney result is linked to hydration or to the kidneys themselves.",
    body=["BUN changes with hydration and protein, while creatinine is steadier.", "The ratio is calculated from your two results."],
    why=["When kidney results are abnormal, the ratio gives a clue about possible causes."],
    high="A higher ratio often points to dehydration, a high-protein diet or bleeding in the stomach or gut, rather than the kidneys themselves.",
    low="A lower ratio can go with a low-protein diet, liver disease or, less often, some kidney conditions.",
    normal="Your ratio is inside the lab's range. It matters most when BUN or creatinine is abnormal.",
    factors=["Hydration", "Protein intake", "BUN level", "Creatinine level"],
    life=None, support=[],
    seek=["Talk to a doctor if BUN or creatinine is abnormal, as the ratio helps guide what to check next."],
    limits=["The ratio has limited meaning when BUN and creatinine are both normal."],
    not_applicable={"lifestyle_relationships": "Calculated ratio; covered by BUN and creatinine.", "practical_guidance": "Calculated ratio; acts through BUN and creatinine."},
    q=dict(
        high=["What does a high BUN to creatinine ratio mean?", "Can dehydration raise this ratio?"],
        low=["What does a low BUN to creatinine ratio mean?"],
        normal=["Why does my report show a BUN to creatinine ratio?"],
    ),
)

C["WB-030"] = dict(
    d="The urea to creatinine ratio compares two kidney waste products. It works like the BUN to creatinine ratio, using urea instead of BUN.",
    body=["Urea changes with hydration and diet, while creatinine is steadier.", "The ratio is calculated from your two results."],
    why=["It helps a doctor think about whether an abnormal kidney result is linked to hydration, diet or the kidneys."],
    high="A higher ratio often points to dehydration, a high-protein diet or bleeding in the gut.",
    low="A lower ratio can go with a low-protein diet or liver disease.",
    normal="Your ratio is inside the lab's range. It matters most when urea or creatinine is abnormal.",
    factors=["Hydration", "Protein intake", "Urea level", "Creatinine level"],
    life=None, support=[],
    seek=["Talk to a doctor if urea or creatinine is abnormal."],
    limits=["The ratio adds little when urea and creatinine are both normal."],
    not_applicable={"lifestyle_relationships": "Calculated ratio; covered by urea and creatinine.", "practical_guidance": "Calculated ratio; acts through urea and creatinine."},
    q=dict(
        high=["What does a high urea to creatinine ratio mean?"],
        low=["What does a low urea to creatinine ratio mean?"],
        normal=["Why does my report show a urea to creatinine ratio?"],
    ),
)

C["WB-031"] = dict(
    d="eGFR estimates how much blood your kidneys clean each minute. The name stands for estimated glomerular (kidney filter) filtration rate.",
    body=[
        "Each kidney has around a million tiny filters that clean waste and extra water from your blood.",
        "eGFR is calculated from your creatinine, age and sex.",
        "A higher eGFR means your kidneys are filtering more blood. Kidney filtering naturally slows a little with age.",
    ],
    why=["eGFR is the main number used to check for and stage chronic kidney disease, which often has no symptoms early."],
    high="A higher eGFR usually means the kidneys are filtering well. Very high values are mostly seen in young people or pregnancy and are rarely a concern.",
    low="A lower eGFR means the kidneys are filtering less blood. A single low result can be caused by dehydration or a recent large meat meal. If it stays low for three months or more, it can mean chronic kidney disease.",
    normal="Your eGFR is inside the lab's range, suggesting your kidneys are filtering normally for your age.",
    factors=["Creatinine level", "Age", "Muscle mass", "Hydration", "Diabetes", "High blood pressure"],
    life=["Diabetes and high blood pressure are the most common causes of falling kidney function, so managing them protects eGFR."],
    support=[
        _HYDRATE,
        "Keep salt low and work with your doctor on blood pressure and blood sugar. These protect the kidney filters.",
        "Avoid long-term use of painkillers like ibuprofen or diclofenac without advice. They can reduce kidney filtering.",
    ],
    seek=["Talk to a doctor if eGFR is below the lab's range, has dropped compared with earlier tests, or comes with swelling, foamy urine, or high blood pressure."],
    limits=["eGFR is an estimate based on creatinine, so it can be less accurate in people with very high or very low muscle mass."],
    not_applicable={},
    q=dict(
        high=["Is a high eGFR good?", "What does eGFR measure?"],
        low=["Should I be worried about my low eGFR?", "Can dehydration lower my eGFR?", "How can I protect my kidneys?"],
        normal=["What does my eGFR say about my kidneys?", "Does eGFR change with age?"],
    ),
)

C["WB-032"] = dict(
    d="Phosphate is a mineral that works with calcium to build bones and teeth. It also helps your cells store and use energy.",
    body=[
        "Most phosphate is stored in your bones.",
        "The rest helps every cell make energy and build its outer wall.",
        "Your kidneys, vitamin D and parathyroid hormone keep blood phosphate balanced.",
    ],
    why=["Abnormal phosphate can point to kidney disease, vitamin D problems or parathyroid gland problems."],
    high="Higher phosphate is most often caused by the kidneys not removing enough. It can also come from low parathyroid hormone or too much vitamin D.",
    low="Lower phosphate can come from poor nutrition, heavy alcohol use, an overactive parathyroid gland, low vitamin D or some antacids.",
    normal="Your phosphate is inside the lab's range, suggesting this mineral is well balanced.",
    factors=["Kidney function", "Vitamin D", "Parathyroid hormone", "Nutrition", "Alcohol", "Some antacids"],
    life=None, support=[],
    seek=["Talk to a doctor if phosphate is abnormal, especially with kidney disease, bone pain or muscle weakness."],
    limits=["Phosphate can rise in a sample that was handled slowly, and it varies with recent meals."],
    not_applicable={
        "lifestyle_relationships": "Blood phosphate is controlled by the kidneys and hormones; diet matters mainly in people with kidney disease.",
        "practical_guidance": "Phosphate changes need a doctor to find the cause; diet advice is only given for kidney disease under medical care.",
    },
    q=dict(
        high=["Why is my phosphate high?", "Is high phosphate linked to my kidneys?"],
        low=["Why is my phosphate low?"],
        normal=["What does phosphate do in my body?", "How are calcium and phosphate linked?"],
    ),
)

C["WB-033"] = dict(
    d="Potassium is a mineral in your blood that helps your nerves, muscles and especially your heart beat steadily.",
    body=[
        "Potassium mostly lives inside your cells, with a small amount in the blood.",
        "It helps nerves send signals and muscles, including the heart, contract.",
        "Your kidneys keep blood potassium in a narrow range.",
    ],
    why=["Both high and low potassium can upset the heart's rhythm, so this result is watched closely."],
    high="Higher potassium can come from kidney problems, some blood pressure medicines or supplements. A falsely high result is common when blood cells burst during sample collection, so a repeat test is often done.",
    low="Lower potassium can come from vomiting, diarrhoea, water tablets (diuretics) or not eating enough. It can cause weakness, cramps or an uneven heartbeat.",
    normal="Your potassium is inside the lab's range, which supports a steady heart rhythm.",
    factors=["Kidney function", "Water tablets and some blood pressure medicines", "Vomiting or diarrhoea", "Sample handling", "Potassium supplements"],
    life=["Fruits and vegetables like banana, coconut water, potato, tomato and leafy greens are good sources of potassium."],
    support=[
        "Eat a variety of fruits and vegetables each day. They provide potassium, which also helps balance the effect of salt on blood pressure.",
    ],
    seek=[
        "Seek medical care promptly if potassium is clearly high or low, or you have palpitations, chest discomfort, muscle weakness or cramps.",
        "If you have kidney disease, check with your doctor before eating more potassium-rich foods or salt substitutes.",
    ],
    limits=["A falsely high potassium is common if the blood sample was difficult to take or delayed, so an unexpected high value is usually repeated."],
    q=dict(
        high=["Should I be worried about my high potassium?", "Can a blood sample give a falsely high potassium?", "Can my medicines raise potassium?"],
        low=["Why is my potassium low?", "Which foods are good sources of potassium?"],
        normal=["What does potassium do for my heart?"],
    ),
)

C["WB-034"] = dict(
    d="Magnesium is a mineral your body uses for hundreds of processes, including muscle and nerve work, energy production and keeping a steady heartbeat.",
    body=[
        "Most magnesium is stored in your bones and inside cells. Only a small amount is in the blood.",
        "It helps muscles relax after they contract and helps nerves send signals.",
        "Your kidneys control how much magnesium your body keeps.",
    ],
    why=["Low magnesium can cause cramps, tiredness and heart rhythm problems, and it can make low calcium and low potassium harder to correct."],
    high="Higher magnesium is uncommon. It is usually linked with kidney problems or taking magnesium in antacids, laxatives or supplements.",
    low="Lower magnesium can come from a diet low in whole foods, heavy alcohol use, diarrhoea, diabetes, or medicines such as water tablets and long-term acid-reducing tablets.",
    normal="Your blood magnesium is inside the lab's range, although blood levels do not always show how much is stored in the body.",
    factors=["Diet", "Alcohol", "Diarrhoea", "Diabetes", "Water tablets or acid-reducing medicines", "Kidney function"],
    life=["Whole grains, nuts, seeds, pulses and leafy green vegetables are good sources of magnesium."],
    support=[
        "Include magnesium-rich foods such as nuts, seeds, whole grains, dal and leafy greens. Food is the safest way to keep magnesium topped up.",
        "Keep alcohol low. Alcohol makes the kidneys lose magnesium.",
    ],
    seek=["Talk to a doctor if magnesium is abnormal, especially with muscle cramps, twitching, an irregular heartbeat or kidney disease. Do not take magnesium supplements with kidney disease unless advised."],
    limits=["Blood magnesium can be normal even when the body's stores are low."],
    q=dict(
        high=["Why is my magnesium high?", "Can supplements or antacids raise magnesium?"],
        low=["Why is my magnesium low?", "Which foods are rich in magnesium?", "Can low magnesium cause cramps?"],
        normal=["What does magnesium do in my body?", "Is magnesium linked to sleep?"],
    ),
)

C["WB-035"] = dict(
    d="Zinc is a trace mineral your body needs in small amounts for immunity, wound healing, taste and smell, and growth.",
    body=[
        "Zinc helps your immune cells fight infection.",
        "It is needed to heal wounds and to make new cells and proteins.",
        "Your body cannot store much zinc, so you need some from food regularly.",
    ],
    why=["Low zinc can weaken immunity, slow healing and affect taste, skin and hair."],
    high="Higher zinc is uncommon and usually comes from taking zinc supplements. Too much zinc over time can lower copper levels.",
    low="Lower zinc can come from a diet low in zinc foods, poor absorption from the gut, diarrhoea, heavy alcohol use or ongoing illness. Inflammation can also lower blood zinc temporarily.",
    normal="Your zinc is inside the lab's range, suggesting you are getting enough for now.",
    factors=["Diet", "Gut absorption", "Inflammation or illness", "Alcohol", "Zinc supplements", "Time of day the sample was taken"],
    life=[
        "Meat, eggs, seafood, dairy, pulses, nuts, seeds and whole grains provide zinc.",
        "Zinc from plant foods is absorbed less well, so vegetarians may need a little more.",
    ],
    support=[
        "Include zinc foods such as pumpkin seeds, chana, rajma, nuts, curd, eggs or meat. Regular intake matters because the body stores little zinc.",
        "If you are vegetarian, soak, sprout or ferment pulses and grains. This helps your body absorb more zinc from them.",
    ],
    seek=["Talk to a doctor if zinc is low with slow wound healing, frequent infections, hair loss or changes in taste, or if you take zinc supplements regularly."],
    limits=["Blood zinc falls during infection and inflammation and changes with time of day, so it does not always reflect body stores."],
    q=dict(
        high=["Can zinc supplements raise my zinc too much?"],
        low=["Why is my zinc low?", "Can I get enough zinc on a vegetarian diet?", "Which foods are rich in zinc?"],
        normal=["What does zinc do for my immunity?"],
    ),
)
