"""Education upgrade for hormone and tumour marker results. Pending clinical review."""

_TUMOUR_MYTH = "Tumour markers are not cancer screening tests for most people. Many non-cancer conditions raise them, and a normal result does not rule out cancer."
_NA_T = dict(keeping_healthy="A tumour marker follows illness or treatment, not a habit.")

X = {}

X["WB-095"] = dict(
    fx=[
        ("Time of day", "Testosterone is highest in the morning, so a later sample reads lower."),
        ("Age and sex", "Men have much higher levels than women, and men's levels fall slowly with age."),
        ("Body weight", "Extra body fat converts testosterone to oestrogen and lowers it in men."),
        ("Sleep", "Poor or short sleep lowers testosterone in men."),
        ("PCOS", "In women, polycystic ovary syndrome raises testosterone, causing acne, extra hair and irregular periods."),
        ("Testosterone or steroid use", "Taking testosterone or anabolic steroids raises the level and stops the body's own production."),
    ],
    keep=["Enough sleep, regular activity including strength exercise, and a healthy weight support normal testosterone in men."],
    myth=["Low energy in men is not always low testosterone. Sleep, mood, thyroid and anaemia are common causes too."],
)
X["WB-096"] = dict(
    fx=[
        ("Age", "DHEA-S peaks in young adulthood and falls steadily with age."),
        ("Sex", "Men have higher levels than women."),
        ("PCOS", "Some women with PCOS have higher DHEA-S from the adrenal glands."),
        ("Adrenal conditions", "Adrenal growths or inherited adrenal conditions raise it; adrenal failure lowers it."),
        ("Steroid medicines", "Steroid tablets switch off adrenal production and lower DHEA-S."),
    ],
    keep=None, myth=["DHEA supplements are not proven to slow ageing, and they can raise testosterone in women."], na=dict(keeping_healthy="Set by age, sex and the adrenal glands."),
)
X["WB-097"] = dict(
    fx=[
        ("Age", "IGF-1 is highest in teenage years and falls with age, so ranges are age-specific."),
        ("Nutrition", "Undernutrition lowers IGF-1."),
        ("Liver function", "The liver makes IGF-1, so liver disease lowers it."),
        ("Thyroid function", "An underactive thyroid lowers IGF-1."),
        ("Pituitary activity", "Too much growth hormone from the pituitary raises IGF-1; too little lowers it."),
    ],
    keep=None, myth=["IGF-1 is only meaningful against an age-matched range."], na=dict(keeping_healthy="Set by age, nutrition and the pituitary."),
)
X["WB-098"] = dict(
    fx=[
        ("Time of day", "Cortisol is highest early in the morning and lowest around midnight, so timing changes the result a great deal."),
        ("Stress and illness", "Physical illness and severe stress raise cortisol."),
        ("Sleep", "Night shifts and poor sleep shift the daily pattern."),
        ("Steroid medicines", "Steroid tablets, creams and inhalers lower the body's own cortisol, while some lab methods read prednisolone as cortisol."),
        ("Hormone pills or pregnancy", "Oestrogen raises the protein that carries cortisol, raising total cortisol."),
    ],
    keep=["Regular sleep at similar times supports a normal daily cortisol rhythm."],
    myth=["A single cortisol result cannot diagnose stress or adrenal fatigue. Adrenal fatigue is not a recognised medical condition."],
)
X["WB-099"] = dict(
    fx=[
        ("Calcium level", "When blood calcium falls, the parathyroid glands release more PTH to raise it."),
        ("Vitamin D level", "Low vitamin D lowers calcium absorption, so PTH rises to compensate."),
        ("Kidney function", "Kidney disease upsets calcium and phosphate and raises PTH."),
        ("Magnesium level", "Very low magnesium stops the glands releasing PTH."),
    ],
    keep=["Enough vitamin D and calcium from food support normal PTH."],
    myth=["A high PTH with low vitamin D often settles once vitamin D is corrected, rather than meaning a gland problem."],
)
X["WB-100"] = dict(
    fx=[
        ("Pregnancy and breastfeeding", "Prolactin rises naturally to make breast milk."),
        ("Stress", "Physical stress, including a difficult blood draw, can raise prolactin."),
        ("Some medicines", "Some antipsychotic, anti-sickness and acid medicines raise prolactin."),
        ("Thyroid function", "An underactive thyroid raises prolactin."),
        ("Kidney function", "Kidney disease reduces prolactin clearance."),
        ("Time of sample", "Prolactin is higher during sleep and early morning."),
    ],
    keep=None, myth=["A mildly high prolactin is often from stress or medicines and is usually rechecked before further tests."], na=dict(keeping_healthy="Set by the pituitary, medicines and pregnancy."),
)
X["WB-101"] = dict(
    fx=[
        ("Menstrual cycle day", "LH surges in mid-cycle to trigger ovulation, so results depend on the day."),
        ("Menopause", "After menopause the ovaries stop responding and LH rises."),
        ("Hormone pills", "Contraceptive pills lower LH."),
        ("PCOS", "Many women with PCOS have LH higher than FSH."),
        ("Body weight and exercise", "Very low weight or heavy training lowers LH and can stop periods."),
    ],
    keep=None, myth=["An LH result means little without knowing the cycle day."], na=dict(keeping_healthy="Follows the cycle and the pituitary."),
)
X["WB-102"] = dict(
    fx=[
        ("Menstrual cycle day", "FSH rises early in the cycle to grow egg follicles."),
        ("Menopause", "FSH rises as the ovaries run low on eggs."),
        ("Age", "FSH rises gradually as fertility falls with age."),
        ("Hormone pills", "Contraceptive pills lower FSH."),
        ("Body weight", "Very low body weight lowers FSH."),
    ],
    keep=None, myth=["A single FSH cannot confirm menopause in women who still have periods; levels swing from month to month."], na=dict(keeping_healthy="Follows the cycle, age and the pituitary."),
)
X["WB-103"] = dict(
    fx=[
        ("Which calcium was measured", "The lab has not confirmed whether this is total or ionised calcium, which have different ranges."),
        ("Vitamin D", "Vitamin D helps the gut absorb calcium."),
        ("Parathyroid hormone", "This hormone raises blood calcium."),
        ("Albumin", "Low albumin lowers total calcium without a true shortage."),
        ("Kidney function", "Kidneys help balance calcium."),
        ("Supplements", "Large doses of vitamin D or calcium can push it high."),
    ],
    keep=["Calcium from milk, curd, ragi and sesame, with enough vitamin D, supports bones."],
    myth=["Blood calcium does not show bone strength."],
)
X["WB-104"] = dict(
    fx=[
        ("Age", "PSA rises as the prostate grows with age, so normal levels are higher in older men."),
        ("Prostate enlargement", "A benign enlarged prostate, common after 50, raises PSA."),
        ("Prostate inflammation or infection", "Prostatitis can raise PSA sharply for weeks."),
        ("Recent ejaculation or cycling", "Both can raise PSA a little for a day or two."),
        ("Some medicines", "Medicines for an enlarged prostate, such as finasteride, roughly halve PSA."),
    ],
    keep=None, myth=["A high PSA does not mean cancer. Most raised PSA results come from enlargement or inflammation."], na=dict(keeping_healthy="PSA follows prostate size and inflammation."),
)
X["WB-105"] = dict(
    fx=[
        ("Smoking", "Smokers have higher CEA."),
        ("Inflammatory bowel conditions", "Gut inflammation raises CEA."),
        ("Liver disease", "The liver clears CEA, so liver disease raises it."),
        ("Lung conditions", "Some lung conditions raise CEA."),
        ("Some cancers", "Some bowel and other cancers make CEA, which is why it is used to follow treatment."),
    ],
    keep=None, myth=[_TUMOUR_MYTH], na=_NA_T,
)
X["WB-106"] = dict(
    fx=[
        ("Sample type", "The lab has not confirmed whether this was blood or another fluid, which changes its meaning."),
        ("Pregnancy", "The baby makes AFP, so levels rise in pregnancy."),
        ("Liver conditions", "Hepatitis and cirrhosis can raise AFP."),
    ],
    keep=None, myth=[_TUMOUR_MYTH], na=_NA_T,
)
X["WB-107"] = dict(
    fx=[
        ("Bile duct blockage", "Blocked bile flow raises CA 19-9, sometimes to very high levels."),
        ("Pancreatitis", "Pancreas inflammation raises it."),
        ("Liver conditions", "Liver disease raises it."),
        ("Diabetes", "Poorly controlled diabetes can raise it."),
        ("Some cancers", "Some pancreas and bile duct cancers make it."),
    ],
    keep=None, myth=[_TUMOUR_MYTH], na=_NA_T,
)
X["WB-108"] = dict(
    fx=[
        ("Menstrual cycle", "CA 125 can rise during periods."),
        ("Pregnancy", "It rises in early pregnancy."),
        ("Endometriosis or fibroids", "Both common, non-cancer conditions raise it."),
        ("Pelvic infection", "Infection of the pelvic organs raises it."),
        ("Liver disease", "Fluid in the belly from liver disease raises it."),
        ("Some cancers", "Some ovarian cancers make it, which is why it is used to follow treatment."),
    ],
    keep=None, myth=[_TUMOUR_MYTH], na=_NA_T,
)
X["WB-109"] = dict(
    fx=[
        ("Liver conditions", "Liver disease can raise CA 15-3."),
        ("Benign breast conditions", "Non-cancer breast conditions can raise it a little."),
        ("Some cancers", "Some breast cancers make it, so it is used to follow treatment."),
    ],
    keep=None, myth=[_TUMOUR_MYTH, "CA 15-3 is not a breast cancer screening test; mammography and breast examination are."], na=_NA_T,
)
