"""Revision 2.3.1 content for the 211 individual allergen tests.

The medical meaning of a specific IgE test is the same for every substance in a group, so this file
writes group-level text once and inserts the substance name and its own exposure description. That is
deliberate shared content, not mechanical filling: the group decides the practical guidance.
"""

GROUPS = {
    "Allergy Veg": "food", "Allergy Non-Veg": "food", "Allergy Dairy": "food", "Allergy Seeds/Nuts/Legumes": "food", "Allergy Spices": "food",
    "Allergy Dust Mites": "indoor", "Allergy Moulds & Yeast": "mould", "Allergy Pets": "animal",
    "Allergy Grass": "pollen", "Allergy Weed & Tree": "pollen",
    "Allergy Insects": "insect", "Allergy Drugs": "drug", "Allergy Occupational": "occupational", "Allergy Parasites": "parasite",
}

BODY = [
    "Your immune system protects you by making antibodies, proteins that recognise things it sees as a threat.",
    "In allergies, it makes an antibody called IgE against something that is usually harmless.",
    "When IgE meets that substance again, it can trigger symptoms such as sneezing, itching, rashes, swelling or wheezing.",
]
LIMITS = ["An allergy antibody test cannot confirm an allergy on its own or predict how severe a reaction might be. A doctor reads it alongside what happens when you are exposed."]
EMERGENCY = "Seek emergency care straight away for swelling of the lips, tongue or throat, trouble breathing, wheezing, feeling faint or collapse after contact with any trigger."

GROUP = {
    "food": dict(
        why="This test can help a doctor decide whether {n} might be linked to symptoms such as hives, itching, swelling, tummy upset or wheezing after eating.",
        life=["Avoiding a food matters only if it causes symptoms. Many people with antibodies to a food eat it without any problem."],
        support=[
            "Do not cut {n} or other foods from your diet based on this result alone. Unnecessary avoidance can limit nutrition, especially for children.",
            "If you notice symptoms after eating {n}, note what you ate, how much and how soon symptoms began. This helps a doctor judge whether the result matters.",
        ],
        seek=["Talk to a doctor or allergy specialist if you get symptoms after eating {n}.", EMERGENCY],
        q=["Does a positive {n} test mean I am allergic to it?", "Do I need to stop eating {n}?", "What symptoms would an allergy to {n} cause?"],
    ),
    "indoor": dict(
        why="This test can help a doctor decide whether {n} might be behind indoor symptoms such as a blocked or runny nose, sneezing, itchy eyes, cough or wheezing.",
        life=["Contact with house dust and mites is highest in bedding, mattresses, carpets and soft furnishings."],
        support=[
            "If you have symptoms at home, wash pillow covers and bedsheets weekly in hot water and dry them in the sun. This reduces dust mites.",
            "Dust with a damp cloth and air rooms daily. Damp dusting traps particles instead of spreading them.",
        ],
        seek=["Talk to a doctor if you have ongoing sneezing, a blocked nose, itchy eyes, cough or wheezing.", EMERGENCY],
        q=["Could {n} be causing my sneezing or blocked nose?", "How can I reduce dust mites at home?", "Does a positive result mean I am allergic?"],
    ),
    "mould": dict(
        why="This test can help a doctor decide whether {n}, a type of mould or yeast, might be linked to nose, eye, chest or skin symptoms.",
        life=["Moulds grow in damp places such as bathrooms, kitchens, leaking walls and stored grain."],
        support=[
            "Keep bathrooms and kitchens well ventilated and fix leaks or damp patches. Moulds grow where moisture stays.",
            "Do not keep damp clothes or wet items indoors for long. They encourage mould growth.",
        ],
        seek=["Talk to a doctor if you have symptoms that are worse in damp places or during the monsoon.", EMERGENCY],
        q=["Could mould like {n} be causing my symptoms?", "How can I reduce mould at home?", "Does a positive result mean I am allergic?"],
    ),
    "animal": dict(
        why="This test can help a doctor decide whether {n} might be linked to symptoms such as sneezing, itchy eyes, wheezing or skin rashes around animals or birds.",
        life=["Animal and bird allergens collect in dust, bedding, furniture and clothes, even after the animal has left."],
        support=[
            "If symptoms happen around animals or birds, keep them out of the bedroom and wash your hands after handling them.",
            "Clean areas where birds roost or animals sleep regularly, and avoid stirring up dry droppings.",
        ],
        seek=["Talk to a doctor if you get symptoms around animals or birds, or ongoing breathlessness or cough.", EMERGENCY],
        q=["Could {n} be causing my symptoms?", "Do I need to avoid {n} completely?", "Does a positive result mean I am allergic?"],
    ),
    "pollen": dict(
        why="This test can help a doctor decide whether pollen from {n} might be behind seasonal symptoms such as sneezing, a runny nose, itchy eyes or wheezing.",
        life=["Pollen counts are often highest on dry, windy days and in particular seasons."],
        support=[
            "On high pollen days, keep windows closed and shower and change clothes after being outdoors. This removes pollen from skin and hair.",
            "Note when your symptoms are worse in the year. Seasonal patterns help a doctor link symptoms to pollen.",
        ],
        seek=["Talk to a doctor if seasonal symptoms affect your sleep, work or breathing.", EMERGENCY],
        q=["Could pollen from {n} cause my seasonal symptoms?", "How can I reduce pollen exposure?", "Does a positive result mean I am allergic?"],
    ),
    "insect": dict(
        why="This test can help a doctor decide whether {n} might be linked to allergy symptoms, either from stings or bites, or from tiny insect particles in household dust.",
        life=["Household insects such as cockroaches and flies leave particles in dust, while bees and wasps cause reactions through stings."],
        support=[
            "Keep food covered, clear kitchen waste daily and seal cracks. This reduces cockroaches and flies indoors.",
            "If you have had a strong reaction to a sting, ask a doctor about an emergency plan before it happens again.",
        ],
        seek=["Talk to a doctor if you have had a large swelling or a reaction beyond the sting site.", EMERGENCY],
        q=["Could {n} be causing my symptoms?", "What should I do if I react to a sting?", "Does a positive result mean I am allergic?"],
    ),
    "drug": dict(
        why="This test may help a doctor or allergy specialist look into a past reaction to {n}. For most medicines, blood tests are less reliable than a careful history and specialist testing.",
        life=None,
        support=["Keep a written list of any medicine that caused a reaction, what happened and when, and show it to every doctor and pharmacist."],
        seek=["Do not take a medicine you reacted to before, or stop a prescribed medicine, based on this result alone. Ask a doctor first.", EMERGENCY],
        q=["Can this test tell me if it is safe to take {n}?", "What should I tell my doctor about a past reaction?", "Does a negative result mean I can take this medicine?"],
        na={"lifestyle_relationships": "Medicine allergy; no diet or lifestyle relationship applies."},
    ),
    "occupational": dict(
        why="This test can help a doctor decide whether {n}, a material met at work or at home, might be linked to skin, nose, eye or chest symptoms.",
        life=["Symptoms linked with a material often improve on days off or holidays and return on contact."],
        support=["Note when symptoms start and stop. Symptoms that ease on days away from the material are a useful clue for a doctor."],
        seek=["Talk to a doctor if symptoms seem linked to your work or to contact with a material.", EMERGENCY],
        q=["Could contact with {n} be causing my symptoms?", "Do my symptoms improve away from work?", "Does a positive result mean I am allergic?"],
    ),
    "parasite": dict(
        why="This test may help a doctor understand raised allergy antibodies or eosinophils, which some parasite infections can cause. A positive result does not confirm a current infection.",
        life=["Parasites can spread through unclean water, unwashed produce, undercooked fish or contact with soil and animal waste."],
        support=[
            "Wash hands with soap before eating and after using the toilet or handling soil or pets. This lowers the chance of parasite infections.",
            "Eat fish well cooked or properly frozen before eating raw. This kills parasites such as Anisakis.",
        ],
        seek=["Talk to a doctor if you have tummy pain, diarrhoea, weight loss, itching or raised eosinophils. Treatment decisions are a doctor's choice."],
        q=["Does a positive {n} result mean I have a parasite infection?", "How could I have been exposed to {n}?", "Do I need treatment?"],
    ),
}

ASSAY = "The lab has not confirmed the test method or how this result is reported, so CURA does not label it positive or negative. A positive allergy antibody result means your immune system recognises {n}. It does not prove you will react to it."
COND = {
    "positive_or_elevated": ["Antibodies to {n} were found. This is called sensitisation. Many sensitised people have no symptoms, so it matters only if you react when exposed."],
    "negative_or_low": ["Little or no antibody to {n} was found. This makes an IgE allergy less likely, but does not rule out every kind of reaction."],
}
