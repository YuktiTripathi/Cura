"""Authoritative general-medical evidence. Reused by ChatService; does not query SuperShyft."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class MedicalEvidenceDoc:
    name: str
    url: str
    source_type: str
    tier: int
    topics: tuple[str, ...]
    keywords: tuple[str, ...]
    excerpt: str
    title: str = ""
    publication_date: str | None = None
    provenance: str = "curated_source_index"
    review_status: str = "unreviewed_index"
    version: str = "cura-kb-v1"
    retrieved_at: str | None = None

    @property
    def evidence_text(self) -> str:
        return self.excerpt

    @property
    def evidence_retrieved(self) -> bool:
        return bool(self.url)


MedicalEvidenceSource = MedicalEvidenceDoc


CORPUS: tuple[MedicalEvidenceDoc, ...] = (
    MedicalEvidenceDoc(
        name="WHO",
        url="https://www.who.int/news-room/fact-sheets/detail/hypertension",
        source_type="guideline",
        tier=1,
        topics=("hypertension",),
        keywords=("hypertension", "high blood pressure", "blood pressure"),
        excerpt=(
            "Hypertension is high blood pressure. WHO describes it as a major risk for heart, brain, "
            "kidney, and other disease. Lifestyle measures and clinician-guided treatment can reduce risk. "
            "It does not say every person always needs the same treatment."
        ),
    ),
    MedicalEvidenceDoc(
        name="NICE",
        url="https://www.nice.org.uk/guidance/ng136",
        source_type="guideline",
        tier=1,
        topics=("hypertension",),
        keywords=("hypertension", "treatment", "blood pressure"),
        excerpt=(
            "NICE guidance on hypertension covers diagnosis and treatment options that depend on age, "
            "blood pressure readings, and other conditions. Treatment is individualized; it is not a single "
            "universal regimen."
        ),
    ),
    MedicalEvidenceDoc(
        name="CDC",
        url="https://www.cdc.gov/high-blood-pressure/about/index.html",
        source_type="guideline",
        tier=1,
        topics=("hypertension",),
        keywords=("hypertension", "symptoms", "high blood pressure"),
        excerpt=(
            "CDC notes that high blood pressure often has no warning symptoms. Measuring blood pressure "
            "is how it is found. Lifestyle changes may help; medication is used when a clinician recommends it."
        ),
    ),
    MedicalEvidenceDoc(
        name="NIDDK",
        url="https://www.niddk.nih.gov/health-information/endocrine-diseases/hyperthyroidism",
        source_type="guideline",
        tier=1,
        topics=("thyroid", "hyperthyroidism"),
        keywords=("hyperthyroidism", "thyroid", "overactive", "tsh", "iodine"),
        excerpt=(
            "Hyperthyroidism is when the thyroid makes more hormone than the body needs. Symptoms can "
            "include weight loss, fast heartbeat, heat intolerance, and anxiety. Causes and treatment vary. "
            "Diet advice, including iodine, depends on the cause and should be individualized."
        ),
    ),
    MedicalEvidenceDoc(
        name="MedlinePlus",
        url="https://medlineplus.gov/hyperthyroidism.html",
        source_type="guideline",
        tier=1,
        topics=("thyroid", "hyperthyroidism"),
        keywords=("hyperthyroidism", "thyroid", "symptoms"),
        excerpt=(
            "MedlinePlus lists possible hyperthyroidism symptoms such as nervousness, weight loss, "
            "tremor, and heat sensitivity. Not everyone has every symptom. A clinician uses history, exam, "
            "and tests such as TSH to evaluate thyroid function."
        ),
    ),
    MedicalEvidenceDoc(
        name="NICE",
        url="https://www.nice.org.uk/guidance/ng145",
        source_type="guideline",
        tier=1,
        topics=("thyroid", "hyperthyroidism"),
        keywords=("hyperthyroidism", "thyroid", "treatment"),
        excerpt=(
            "NICE guidance on thyroid disease covers assessment and management of thyrotoxicosis. "
            "Treatment options can include antithyroid medicines, radioiodine, or surgery depending on "
            "the diagnosis. People should not start or stop treatment without clinical advice."
        ),
    ),
    MedicalEvidenceDoc(
        name="CDC",
        url="https://www.cdc.gov/diabetes/about/index.html",
        source_type="guideline",
        tier=1,
        topics=("type_2_diabetes", "hba1c"),
        keywords=("diabetes", "hba1c", "a1c", "blood sugar"),
        excerpt=(
            "CDC describes diabetes as a condition with high blood glucose. HbA1c is one test clinicians "
            "use. Management can include lifestyle measures and medicines prescribed for that person."
        ),
    ),
    MedicalEvidenceDoc(
        name="MedlinePlus",
        url="https://medlineplus.gov/lab-tests/hemoglobin-a1c-hba1c-test/",
        source_type="guideline",
        tier=1,
        topics=("hba1c",),
        keywords=("hba1c", "a1c", "hemoglobin a1c", "blood sugar"),
        excerpt=(
            "MedlinePlus describes hemoglobin A1c as a blood test that reflects average glucose over "
            "about three months. Many factors can influence results, and interpretation belongs with a clinician. "
            "This is a source pointer, not a quotation."
        ),
        title="Hemoglobin A1c (HbA1c) test",
    ),
    MedicalEvidenceDoc(
        name="NIDDK",
        url="https://www.niddk.nih.gov/health-information/diabetes/overview/managing-diabetes/nutrition-physical-activity",
        source_type="guideline",
        tier=1,
        topics=("hba1c", "type_2_diabetes"),
        keywords=("foods", "diet", "nutrition", "eat", "carbohydrate", "lifestyle", "exercise", "hba1c", "a1c"),
        excerpt=(
            "NIDDK notes that eating patterns, carbohydrate intake, and physical activity are commonly "
            "discussed in diabetes and blood-glucose management, including tests such as HbA1c. "
            "Food choices are individualized and are not a substitute for clinical dietary advice. "
            "This is a source pointer, not a quotation."
        ),
        title="Diabetes diet, eating, and physical activity",
    ),
    MedicalEvidenceDoc(
        name="CDC",
        url="https://www.cdc.gov/diabetes/healthy-eating/index.html",
        source_type="guideline",
        tier=1,
        topics=("hba1c", "type_2_diabetes"),
        keywords=("foods", "diet", "healthy eating", "lifestyle", "hba1c", "a1c"),
        excerpt=(
            "CDC discusses healthy eating patterns, vegetables, whole grains, lean proteins, and limiting "
            "added sugars as general diabetes self-management themes. Lifestyle measures can support "
            "blood-glucose management alongside clinician-guided care. This is a source pointer, not a quotation."
        ),
        title="Healthy eating for diabetes",
    ),
    MedicalEvidenceDoc(
        name="WHO",
        url="https://www.who.int/news-room/fact-sheets/detail/the-top-10-causes-of-death",
        source_type="guideline",
        tier=1,
        topics=("cholesterol", "ldl", "hdl"),
        keywords=("cholesterol", "ldl", "hdl", "cardiovascular"),
        excerpt=(
            "WHO identifies cardiovascular disease as a leading cause of death worldwide. Abnormal blood "
            "lipids are one of several risk factors. Advice is population-level and does not replace a "
            "personal assessment."
        ),
    ),
    MedicalEvidenceDoc(
        name="MedlinePlus",
        url="https://medlineplus.gov/cholesterol.html",
        source_type="guideline",
        tier=1,
        topics=("cholesterol", "ldl", "hdl"),
        keywords=("cholesterol", "ldl", "hdl", "triglycerides"),
        excerpt=(
            "LDL, HDL, and triglycerides are blood lipids. Higher LDL is associated "
            "with higher atherosclerotic risk in many people. Diet and activity may help; treatment is "
            "individual. This is a source pointer, not a quotation."
        ),
    ),
    MedicalEvidenceDoc(
        name="MedlinePlus",
        url="https://medlineplus.gov/lab-tests/creatinine-test/",
        source_type="guideline",
        tier=1,
        topics=("creatinine", "kidney_function"),
        keywords=("creatinine", "kidney", "renal"),
        excerpt=(
            "Creatinine is a blood test used when assessing kidney function. High creatinine can have "
            "several causes and needs clinical interpretation. This is a source pointer, not a quotation."
        ),
        title="Creatinine test",
    ),
    MedicalEvidenceDoc(
        name="NIDDK",
        url="https://www.niddk.nih.gov/health-information/kidney-disease/chronic-kidney-disease-ckd/tests-diagnosis",
        source_type="guideline",
        tier=1,
        topics=("egfr", "creatinine", "kidney_function"),
        keywords=("egfr", "gfr", "kidney", "creatinine"),
        excerpt=(
            "eGFR is estimated from blood creatinine and other information to help assess kidney function. "
            "A low eGFR can indicate reduced kidney function and should be interpreted by a clinician. "
            "This is a source pointer, not a quotation."
        ),
        title="CKD tests and diagnosis",
    ),
    MedicalEvidenceDoc(
        name="MedlinePlus",
        url="https://medlineplus.gov/lab-tests/tsh-thyroid-stimulating-hormone-test/",
        source_type="guideline",
        tier=1,
        topics=("tsh", "thyroid", "hyperthyroidism"),
        keywords=("tsh", "thyroid", "hyperthyroidism"),
        excerpt=(
            "TSH is used to help evaluate thyroid function. High TSH and low TSH have different possible "
            "meanings and need clinical context. This is a source pointer, not a quotation."
        ),
        title="TSH test",
    ),
    MedicalEvidenceDoc(
        name="NIH ODS",
        url="https://ods.od.nih.gov/factsheets/VitaminD-Consumer/",
        source_type="guideline",
        tier=1,
        topics=("vitamin_d",),
        keywords=("vitamin d", "vit d", "25 oh", "bone", "calcium", "sunlight"),
        excerpt=(
            "NIH ODS describes vitamin D as a nutrient that helps the body absorb calcium and maintain "
            "bone health. The body can make vitamin D from sunlight, and it is also found in some foods "
            "and supplements. Low levels can have several causes, including limited sun exposure and diet. "
            "This is a source pointer, not a quotation."
        ),
        title="Vitamin D fact sheet for consumers",
    ),
    MedicalEvidenceDoc(
        name="MedlinePlus",
        url="https://medlineplus.gov/vitamind.html",
        source_type="guideline",
        tier=1,
        topics=("vitamin_d",),
        keywords=("vitamin d", "vit d", "deficiency", "low", "bone"),
        excerpt=(
            "MedlinePlus notes that vitamin D helps the body use calcium and phosphorus. Too little "
            "vitamin D can weaken bones. Causes of low vitamin D include limited sunlight, diet, and "
            "some medical conditions. Interpretation of a specific result belongs with a clinician. "
            "This is a source pointer, not a quotation."
        ),
        title="Vitamin D",
    ),
)


class MedicalKnowledgeProvider(Protocol):
    """General medical knowledge only. Never a source of personal lab values."""

    def query(self, message: str, topic: str | None = None, limit: int = 2) -> list[MedicalEvidenceDoc]:
        ...


class CuratedMedicalKnowledgeProvider:
    """Curated guideline index. Not a vector store and not a source of personal values."""

    def query(self, message: str, topic: str | None = None, limit: int = 2) -> list[MedicalEvidenceDoc]:
        return retrieve_medical_evidence(message, topic, limit=limit)


def retrieve_medical_evidence(message: str, topic: str | None = None, limit: int = 2) -> list[MedicalEvidenceDoc]:
    text = (message or "").lower()
    topic_key = (topic or "").lower().replace(" ", "_")
    scored: list[tuple[int, int, int, MedicalEvidenceDoc]] = []
    for index, doc in enumerate(CORPUS):
        score = 0
        if topic_key and topic_key in doc.topics:
            score += 4
        for keyword in doc.keywords:
            if keyword in text or keyword.replace(" ", "_") == topic_key:
                score += 2
        if score:
            scored.append((score, doc.tier, index, doc))
    scored.sort(key=lambda row: (-row[0], row[1], row[2]))
    picked: list[MedicalEvidenceDoc] = []
    seen: set[tuple[str, str]] = set()
    for _, _, _, doc in scored:
        key = (doc.name, doc.url)
        if key in seen:
            continue
        seen.add(key)
        picked.append(doc)
        if len(picked) >= limit:
            break
    return picked


def render_medical_evidence_answer(topic: str | None, docs: list[MedicalEvidenceDoc]) -> str | None:
    excerpts = [doc.excerpt.strip() for doc in docs if (doc.excerpt or "").strip()]
    if not excerpts:
        return None
    label = (topic or "this topic").replace("_", " ")
    return (
        " ".join(excerpts)
        + f" This is general educational information about {label}, "
        "not a personal result, diagnosis, or meal plan."
    )