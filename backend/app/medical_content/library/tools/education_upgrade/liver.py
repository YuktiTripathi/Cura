"""Revision 2.3.1 content: liver and blood proteins. Pending clinical review."""

C = {}

_LIVER_SUPPORT = [
    "Keep alcohol low or avoid it. Your liver has to break down every drink, and alcohol is a common cause of liver strain.",
    "Cut back on sugary drinks, sweets and fried foods. Extra sugar and fat can build up in the liver.",
    "Stay active and work towards a healthy waist size. Losing even a little extra weight can reduce fat in the liver.",
    "Do not start herbal or bodybuilding supplements without advice. Some can harm the liver.",
]

C["WB-010"] = dict(
    d="Albumin is the main protein in your blood. It is made by your liver and helps keep fluid in your blood vessels.",
    body=[
        "Albumin acts like a sponge that holds water inside your blood vessels, so it does not leak into tissues.",
        "It also carries hormones, vitamins, calcium and some medicines around your body.",
        "Your liver makes albumin every day, so its level reflects liver work, nutrition and losses from the body.",
    ],
    why=["It helps doctors check liver function, nutrition and whether protein is being lost through the kidneys or gut."],
    high="High albumin is uncommon and most often means you were a little dehydrated when the sample was taken, which concentrates the blood.",
    low="Low albumin can happen during illness or inflammation, with liver disease, with protein loss through the kidneys or gut, or with poor nutrition. Low levels can cause swelling in the legs or tummy.",
    normal="Your albumin is inside the lab's range, which suggests your liver is making enough of this protein and you are not losing large amounts.",
    factors=["Hydration", "Recent illness or inflammation", "Liver function", "Protein loss through kidneys", "Nutrition"],
    life=["Long-term low protein intake can lower albumin, but in most people low albumin is caused by illness rather than diet."],
    support=[
        "Drink enough water through the day, especially in hot weather. Dehydration can make albumin read high.",
        "Include a protein food at each meal, such as dal, eggs, curd, paneer, fish or chicken. Your liver needs protein to build albumin.",
    ],
    seek=["See a doctor if albumin is low, especially with swelling of the legs, ankles or tummy, frothy urine, or weight loss."],
    limits=["Albumin changes slowly, over about three weeks, so it does not reflect very recent changes in nutrition."],
    q=dict(
        high=["Can dehydration make my albumin high?", "Should I worry about high albumin?"],
        low=["Why is my albumin low?", "Can low albumin cause swelling?", "Does low albumin mean I need more protein?"],
        normal=["What does albumin do in my body?", "What does my albumin say about my liver?"],
    ),
)

C["WB-011"] = dict(
    d="Alkaline phosphatase, or ALP, is an enzyme found mainly in your liver, bile ducts and bones. An enzyme is a protein that helps chemical reactions happen.",
    body=[
        "Small amounts of ALP leak into your blood all the time.",
        "More ALP enters your blood when bile ducts are blocked or when bones are growing or repairing.",
        "Children, teenagers and pregnant women naturally have higher ALP.",
    ],
    why=["ALP helps spot problems with bile flow from the liver, and some bone conditions."],
    high="Higher ALP may come from the liver, for example when bile cannot flow freely, or from bones, for example during growth, healing fractures or vitamin D shortage. Your GGT result helps tell which source is more likely.",
    low="Low ALP is uncommon and usually not important. It can occasionally go with low zinc or magnesium, poor nutrition or rare inherited bone conditions.",
    normal="Your ALP is inside the lab's range, suggesting no sign of bile flow problems or unusual bone activity from this test.",
    factors=["Bone growth or healing", "Bile duct problems", "Pregnancy", "Vitamin D levels", "Some medicines"],
    life=None,
    support=[],
    seek=["See a doctor if ALP is high along with yellowing of the eyes or skin, itching, dark urine, pale stools or bone pain."],
    limits=["ALP alone cannot tell whether the extra enzyme comes from the liver or from bone. GGT or other tests are needed for that."],
    not_applicable={
        "lifestyle_relationships": "ALP mostly reflects bile flow or bone activity; no reliable diet or lifestyle effect on ALP itself.",
        "practical_guidance": "A raised ALP needs a cause found by a doctor; everyday habits do not correct it.",
    },
    q=dict(
        high=["Is my high ALP from my liver or my bones?", "Should I be concerned about my ALP result?", "Can low vitamin D raise ALP?"],
        low=["Is low ALP a problem?", "What does ALP do in my body?"],
        normal=["What does ALP tell me about my liver?", "Why are ALP and GGT checked together?"],
    ),
)

C["WB-012"] = dict(
    d="Direct bilirubin is the part of bilirubin that your liver has already processed and is ready to send out of your body in bile.",
    body=[
        "When old red blood cells break down, they release a yellow pigment called bilirubin.",
        "Your liver changes it into a water-friendly form called direct bilirubin.",
        "Direct bilirubin flows out with bile into the gut and leaves your body in stool.",
    ],
    why=["A high direct bilirubin suggests a problem with how bile drains out of the liver, rather than with red blood cells breaking down."],
    high="Higher direct bilirubin can mean bile is not draining well, for example from a gallstone blocking a bile duct, swelling of the liver, or a liver condition. It can cause yellow skin or eyes and dark urine.",
    low="A low direct bilirubin is not a concern.",
    normal="Your direct bilirubin is inside the lab's range, which suggests your liver is processing and draining bilirubin normally.",
    factors=["Bile duct blockage such as gallstones", "Liver inflammation", "Some medicines"],
    life=None, support=[],
    seek=["See a doctor promptly if direct bilirubin is high, or if you notice yellow eyes or skin, dark urine, pale stools, itching or pain in the upper right tummy."],
    limits=["Direct bilirubin is measured with a lab method that does not perfectly match the processed form, so small differences between labs are normal."],
    not_applicable={
        "lifestyle_relationships": "Raised direct bilirubin points to bile drainage or liver problems, not a habit that can be changed.",
        "practical_guidance": "Needs medical assessment of the liver and bile ducts rather than lifestyle change.",
    },
    q=dict(
        high=["Should I be concerned about my bilirubin result?", "Could a gallstone raise my direct bilirubin?", "What is the difference between direct and total bilirubin?"],
        low=["Is low direct bilirubin a problem?"],
        normal=["What does bilirubin tell me about my liver?", "What is the difference between direct and indirect bilirubin?"],
    ),
)

C["WB-013"] = dict(
    d="Total bilirubin measures all the bilirubin in your blood. Bilirubin is a yellow pigment made when old red blood cells are broken down.",
    body=[
        "Your body replaces red blood cells every few months, and the old ones are broken down.",
        "Breaking them down releases bilirubin, which your liver processes and sends out in bile.",
        "If too much is made, or the liver cannot clear it, bilirubin builds up and can turn the skin and eyes yellow.",
    ],
    why=["Bilirubin helps check how well your liver is clearing waste and whether red blood cells are breaking down faster than usual."],
    high="Higher bilirubin can come from red cells breaking down faster, from liver problems, or from blocked bile flow. A common harmless cause is Gilbert syndrome, an inherited pattern where bilirubin rises a little, especially with fasting or illness.",
    low="Low bilirubin is not a health concern.",
    normal="Your total bilirubin is inside the lab's range, suggesting your liver is clearing this pigment as expected.",
    factors=["Red blood cell breakdown", "Liver function", "Bile flow", "Gilbert syndrome", "Fasting or recent illness"],
    life=["Long fasting and illness can raise bilirubin a little in people with Gilbert syndrome."],
    support=[
        "Eat regular meals rather than skipping them, if your bilirubin is mildly high. In people with Gilbert syndrome, long gaps without food can raise it.",
    ],
    seek=["See a doctor if bilirubin is high together with yellow skin or eyes, dark urine, pale stools, tummy pain or tiredness."],
    limits=["Total bilirubin does not show the cause. The direct and indirect parts help tell whether the liver, bile ducts or red cells are involved."],
    q=dict(
        high=["Should I be concerned about my bilirubin result?", "What is Gilbert syndrome?", "Why might my bilirubin be high if I feel fine?"],
        low=["Is low bilirubin a problem?"],
        normal=["What does bilirubin tell me about my liver?", "What turns skin yellow in jaundice?"],
    ),
)

C["WB-014"] = dict(
    d="Gamma-glutamyl transferase, or GGT, is an enzyme found mostly in the liver and bile ducts. It rises when the liver or bile ducts are under strain.",
    body=[
        "GGT helps your cells move substances in and out and handle protective molecules.",
        "When liver cells or bile ducts are irritated, more GGT spills into your blood.",
        "Alcohol and some medicines can make the liver produce more GGT.",
    ],
    why=["GGT is a sensitive sign of liver or bile duct strain, and it helps tell whether a high ALP comes from the liver or from bone."],
    high="Higher GGT can reflect alcohol use, fatty liver, bile duct problems or some medicines. It is sensitive but not specific, so it shows strain without saying exactly why.",
    low="A low GGT is not a concern.",
    normal="Your GGT is inside the lab's range, suggesting no sign of liver or bile duct strain from this test.",
    factors=["Alcohol", "Fatty liver", "Bile duct problems", "Some medicines", "Body weight"],
    life=["GGT often rises with regular alcohol use and with fat building up in the liver."],
    support=_LIVER_SUPPORT[:3],
    seek=["Talk to a doctor if GGT is high, especially with other abnormal liver tests, yellow eyes or skin, or tummy pain."],
    limits=["A high GGT shows liver or bile duct strain but cannot identify the cause on its own."],
    q=dict(
        high=["Can alcohol raise my GGT?", "Is my high GGT a sign of fatty liver?", "What can I do to support my liver health?"],
        low=["Is low GGT a problem?"],
        normal=["What does GGT tell me about my liver?", "Why are ALP and GGT checked together?"],
    ),
)

C["WB-015"] = dict(
    d="Total protein measures all the protein in the liquid part of your blood. It is mainly made up of albumin and globulins.",
    body=[
        "Albumin keeps fluid in your blood vessels and carries substances around your body.",
        "Globulins include antibodies that fight infection, as well as carrier and clotting proteins.",
        "Your liver makes albumin and many globulins. Immune cells make antibodies.",
    ],
    why=["Total protein gives a broad picture of nutrition, liver function, kidney losses and immune activity."],
    high="Higher total protein can come from dehydration, ongoing inflammation or infection, or, less often, from a condition where the immune system makes too much of one antibody.",
    low="Lower total protein can come from liver disease, protein loss through the kidneys or gut, poor nutrition or problems absorbing food.",
    normal="Your total protein is inside the lab's range, suggesting a normal overall balance of blood proteins.",
    factors=["Hydration", "Inflammation or infection", "Liver function", "Protein loss through kidneys", "Nutrition"],
    life=["Very low protein intake over a long time can lower blood protein, but illness is a more common cause."],
    support=[
        "Include a protein food at each meal, such as dal, curd, eggs, paneer, soya, fish or chicken. Your body needs protein to build blood proteins.",
        "Drink enough fluids through the day. Dehydration can make protein read high.",
    ],
    seek=["Talk to a doctor if total protein is high or low, especially with swelling, weight loss, frequent infections or bone pain."],
    limits=["Total protein does not show which protein has changed. The albumin and globulin results show that."],
    q=dict(
        high=["Why is my total protein high?", "Can dehydration raise my protein result?"],
        low=["Why is my total protein low?", "Do I need more protein in my diet?"],
        normal=["What does total protein tell me?", "How are albumin and globulin related?"],
    ),
)

C["WB-016"] = dict(
    d="Aspartate aminotransferase, or AST, is an enzyme found in the liver and also in muscles, including the heart. It leaks into the blood when these cells are damaged.",
    body=[
        "AST helps your cells turn food into energy.",
        "Healthy cells keep most of it inside. When liver or muscle cells are hurt, more AST spills into your blood.",
        "Because muscles also contain AST, hard exercise or a muscle injury can raise it.",
    ],
    why=["AST is used with ALT to check for liver cell damage. Comparing the two can give clues about the cause."],
    high="Higher AST can come from liver strain, such as fatty liver, alcohol, hepatitis or some medicines. It can also rise after intense exercise or a muscle injury.",
    low="A low AST is not a concern.",
    normal="Your AST is inside the lab's range, suggesting no sign of liver or muscle cell damage from this test.",
    factors=["Fatty liver", "Alcohol", "Hepatitis", "Intense exercise", "Muscle injury", "Some medicines"],
    life=["Alcohol and extra body fat that builds up in the liver are common reasons AST rises."],
    support=_LIVER_SUPPORT[:2] + ["Avoid very hard workouts for a day or two before a blood test. Intense exercise can raise AST from your muscles."],
    seek=["See a doctor if AST is clearly high, keeps rising, or comes with yellow eyes or skin, dark urine, tummy pain or unusual tiredness."],
    limits=["AST is not specific to the liver, so a raised level may come from muscle rather than liver."],
    q=dict(
        high=["Should I be worried about my high AST?", "Can exercise raise AST?", "What can I do to support my liver health?"],
        low=["Is low AST a problem?"],
        normal=["What does AST tell me about my liver?", "What is the difference between AST and ALT?"],
    ),
)

C["WB-017"] = dict(
    d="Alanine aminotransferase, or ALT, is an enzyme found mainly in the liver. A high level in the blood is one of the clearest signs that liver cells are under strain.",
    body=[
        "ALT helps liver cells turn food into energy.",
        "When liver cells are irritated or damaged, ALT leaks into the blood.",
        "Because most ALT is in the liver, it is more liver-specific than AST.",
    ],
    why=["ALT is the main blood test for spotting liver cell strain, which often has no symptoms early on."],
    high="Higher ALT usually means liver cells are under strain. Common causes include fat building up in the liver, alcohol, viral hepatitis and some medicines or supplements.",
    low="A low ALT is not a concern.",
    normal="Your ALT is inside the lab's range, suggesting no sign of liver cell strain from this test. Fatty liver can sometimes be present with a normal ALT.",
    factors=["Fatty liver", "Alcohol", "Viral hepatitis", "Body weight", "Some medicines and supplements"],
    life=["Extra weight, a diet high in sugar and refined carbohydrates, and alcohol can all lead to fat in the liver, which raises ALT."],
    support=_LIVER_SUPPORT,
    seek=["See a doctor if ALT is high, especially if it stays high on a repeat test or you notice yellow eyes, dark urine, tummy pain or tiredness."],
    limits=["A normal ALT does not fully rule out liver disease, and the level does not always match how serious the problem is."],
    q=dict(
        high=["Should I be worried about my high ALT?", "Is high ALT a sign of fatty liver?", "What can I do to support my liver health?"],
        low=["Is a low ALT a problem?"],
        normal=["Can I have fatty liver with a normal ALT?", "What does ALT tell me about my liver?"],
    ),
)

C["WB-018"] = dict(
    d="Indirect bilirubin is the part of bilirubin that has not yet been processed by your liver. It is worked out by subtracting direct bilirubin from total bilirubin.",
    body=[
        "When red blood cells break down, they release bilirubin into the blood first in this unprocessed form.",
        "The liver then picks it up and changes it so it can leave the body.",
    ],
    why=["A high indirect bilirubin points towards red cells breaking down faster, or a slower liver uptake such as in Gilbert syndrome."],
    high="Higher indirect bilirubin can happen when red blood cells break down faster than usual, or with Gilbert syndrome, a common and harmless inherited pattern. Fasting or illness can make it rise.",
    low="Low indirect bilirubin is not a concern.",
    normal="Your indirect bilirubin is inside the lab's range, suggesting normal red cell breakdown and liver uptake.",
    factors=["Red blood cell breakdown", "Gilbert syndrome", "Fasting or illness"],
    life=["In Gilbert syndrome, long fasting or illness can raise indirect bilirubin a little."],
    support=["Eat regular meals rather than going long hours without food, if indirect bilirubin is mildly high. Long gaps can raise it in Gilbert syndrome."],
    seek=["Talk to a doctor if indirect bilirubin is high together with tiredness, breathlessness, pale skin or yellow eyes, which can point to faster red cell breakdown."],
    limits=["Indirect bilirubin is calculated from two other results, so small errors in either one affect it."],
    q=dict(
        high=["What could cause high indirect bilirubin?", "What is Gilbert syndrome?", "Should I be concerned about my bilirubin result?"],
        low=["Is low indirect bilirubin a problem?"],
        normal=["What is the difference between direct and indirect bilirubin?"],
    ),
)

C["WB-019"] = dict(
    d="Globulins are a group of blood proteins that include antibodies, which fight infection, as well as proteins that carry substances and help blood clot.",
    body=[
        "Immune cells make antibodies, a major type of globulin.",
        "The liver makes many other globulins.",
        "Globulin is usually calculated as total protein minus albumin.",
    ],
    why=["Globulin helps show immune activity and liver function. It is also used to work out the albumin to globulin ratio."],
    high="Higher globulin often reflects ongoing inflammation or infection. Less often, it can be due to liver disease or a condition where the immune system makes too much of one antibody.",
    low="Lower globulin can happen when the body makes fewer antibodies, with liver disease, or when protein is lost through the kidneys or gut.",
    normal="Your globulin is inside the lab's range, suggesting a normal level of these immune and carrier proteins.",
    factors=["Inflammation or infection", "Immune conditions", "Liver function", "Protein loss"],
    life=None, support=[],
    seek=["Talk to a doctor if globulin is high or low, especially with frequent infections, weight loss, bone pain or swelling."],
    limits=["Globulin is a combined group, so it cannot show which protein has changed. Further tests are needed for that."],
    not_applicable={
        "lifestyle_relationships": "Globulin mainly reflects immune and liver processes; no direct diet or lifestyle effect is established.",
        "practical_guidance": "Abnormal globulin needs medical assessment of the cause.",
    },
    q=dict(
        high=["Why is my globulin high?", "Can an infection raise globulin?"],
        low=["Why is my globulin low?", "Does low globulin affect my immunity?"],
        normal=["What are globulins?", "How are albumin and globulin related?"],
    ),
)

C["WB-020"] = dict(
    d="The albumin to globulin ratio compares the two main groups of blood proteins. It is worked out from your albumin and globulin results.",
    body=["Usually there is a little more albumin than globulin in the blood.", "The ratio changes if one group rises or falls more than the other."],
    why=["A change in the ratio can be a clue to inflammation, liver disease, kidney protein loss or an immune problem."],
    high="A higher ratio usually means globulin is lower than usual. It is less common and is often not significant on its own.",
    low="A lower ratio usually means globulin is high, for example with inflammation, or albumin is low, for example with liver disease or protein loss.",
    normal="Your ratio is inside the lab's range, suggesting a normal balance between albumin and globulin.",
    factors=["Albumin level", "Globulin level"],
    life=None, support=[],
    seek=["Talk to a doctor if the ratio is abnormal along with other abnormal liver or kidney results."],
    limits=["The ratio is calculated from two other results and does not show which protein has changed."],
    not_applicable={"lifestyle_relationships": "Calculated ratio; links are covered by albumin and globulin.", "practical_guidance": "Calculated ratio; acts through its component results."},
    q=dict(
        high=["What does a high albumin to globulin ratio mean?"],
        low=["Why is my albumin to globulin ratio low?", "Can inflammation change this ratio?"],
        normal=["What does the albumin to globulin ratio tell me?"],
    ),
)

C["WB-021"] = dict(
    d="The AST to ALT ratio compares two liver enzymes. The pattern can give clues about what is affecting the liver.",
    body=["AST is found in the liver and in muscle, while ALT is found mainly in the liver.", "The ratio is worked out from your two results."],
    why=["When liver enzymes are raised, the ratio can help a doctor think about possible causes, such as fatty liver or alcohol."],
    high="A higher ratio means AST is high compared with ALT. This pattern can be seen with alcohol-related liver strain, advanced liver scarring or muscle sources of AST.",
    low="A lower ratio means ALT is higher than AST, a pattern often seen with fatty liver or viral hepatitis.",
    normal="Your ratio is inside the lab's range. The ratio matters most when AST or ALT is raised.",
    factors=["AST level", "ALT level"],
    life=None, support=[],
    seek=["Talk to a doctor if AST or ALT is raised, as the ratio helps guide what to check next."],
    limits=["The ratio means little when both enzymes are normal, and it can be misleading when one value is very low."],
    not_applicable={"lifestyle_relationships": "Calculated ratio; links are covered by AST and ALT.", "practical_guidance": "Calculated ratio; acts through AST and ALT."},
    q=dict(
        high=["What does a high AST to ALT ratio mean?", "Can alcohol change my AST to ALT ratio?"],
        low=["What does a low AST to ALT ratio mean?", "Is a low ratio linked with fatty liver?"],
        normal=["Why does my report show an AST to ALT ratio?"],
    ),
)
