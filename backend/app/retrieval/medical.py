"""Authoritative general-medical evidence. Reused by ChatService; does not query SuperShyft."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, fields
from datetime import date, timedelta
from pathlib import Path
from typing import Protocol

from app.core.config import settings


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
    # Governance (readiness plan 4.3, 4.4). "cura_summary" is Cura's own wording that
    # points at a source; "quoted_passage" is the source's exact text.
    content_kind: str = "cura_summary"
    reviewer: str | None = None
    reviewed_on: str | None = None
    expires_on: str | None = None
    licence_status: str | None = None
    region: str | None = None

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


SERVABLE_STATUSES = frozenset({"reviewed", "published"})
REVIEW_STATUSES = ("draft", "reviewed", "published", "expired")
MAX_REVIEW_AGE_DAYS = 366


def is_servable(doc: MedicalEvidenceDoc, today: date | None = None) -> bool:
    """Only reviewed or published entries that are in date may be served to members."""
    if doc.review_status not in SERVABLE_STATUSES or not doc.reviewer or not doc.reviewed_on:
        return False
    current = today or date.today()
    try:
        reviewed = date.fromisoformat(doc.reviewed_on)
        expires = date.fromisoformat(doc.expires_on) if doc.expires_on else reviewed + timedelta(days=MAX_REVIEW_AGE_DAYS)
    except ValueError:
        return False
    # Expiry is capped at 12 months after review even if a later date was entered.
    expires = min(expires, reviewed + timedelta(days=MAX_REVIEW_AGE_DAYS))
    return reviewed <= current <= expires


def passage_label(doc: MedicalEvidenceDoc) -> str:
    """Evidence text for the model; source identity stays in response provenance."""
    text = re.sub(
        r"\b(?:WHO|CDC|NIDDK|MedlinePlus|NIH ODS)\s+"
        r"(?:describes|identifies|notes|discusses|lists)\s+",
        "",
        doc.excerpt,
        flags=re.I,
    )
    text = re.sub(r"\s*This is a source pointer, not a quotation\.?", "", text, flags=re.I)
    return f"Medical evidence: {text.strip()}"


def load_content_dir(path: Path) -> tuple[MedicalEvidenceDoc, ...]:
    """Load reviewed content files (one JSON list per file) written by the content team."""
    docs: list[MedicalEvidenceDoc] = []
    if not path.is_dir():
        return ()
    allowed = {f.name for f in fields(MedicalEvidenceDoc)}
    for file in sorted(path.glob("*.json")):
        for row in json.loads(file.read_text(encoding="utf-8")):
            data = {k: v for k, v in row.items() if k in allowed}
            data["topics"] = tuple(data.get("topics") or ())
            data["keywords"] = tuple(data.get("keywords") or ())
            docs.append(MedicalEvidenceDoc(**data))
    return tuple(docs)


CONTENT_DIR = Path(__file__).resolve().parent / "content"
BIO_AI_EXPLAINER = "cura_bio_ai_explainer"

# The Bio-AI guide is only relevant when the question is about Bio-AI itself, so it never
# competes with condition or biomarker passages for other questions.
_BIO_AI_ANCHOR = re.compile(
    r"bio[\s-]?ai|metsights|metflux|risk score|risk assessment|metabolic (?:score|age|risk)|"
    r"health rank|percentile|lifestyle contribution|\b\d{1,3}\s*/\s*100\b|\bscore (?:of|is|was|came) (?:in at )?\d",
    re.I,
)


def any_bio_ai_anchor(message: str) -> bool:
    return bool(_BIO_AI_ANCHOR.search(message or ""))


def _clean_markdown(text: str) -> str:
    """Plain text for the model: no markup, tables as sentences, ranges written with 'to'."""
    out: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or set(line) <= set("-| :"):
            continue
        line = re.sub(r"^>\s*", "", line)
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if cells and cells[0].lower() in {"score", "blood marker or group", "report area"}:
                continue
            line = (cells[0] + ": " + ". ".join(c for c in cells[1:] if c)) if len(cells) > 1 else cells[0]
        line = re.sub(r"(\d)\s*[\u2013\u2014-]\s*(\d)", r"\1 to \2", line)
        line = line.replace("\u2260", "is not").replace("\u2013", ",").replace("\u2014", ",")
        line = re.sub(r"\*\*|`", "", line)
        out.append(line)
    return "\n".join(out)


def _markdown_chunks(text: str, skip: set[str]) -> list[tuple[str, str, str]]:
    """Split by section. A section with numbered subsections (3.1, 3.2 ...) becomes one chunk per subsection."""
    sections = re.split(r"(?m)^## ", text)[1:]
    chunks: list[tuple[str, str, str]] = []
    for sec in sections:
        head, _, body = sec.partition("\n")
        number = (re.match(r"(\d+)\.", head) or [None, ""])[1]
        if not number or number in skip:
            continue
        title = re.sub(r"^\d+\.\s*", "", head).strip()
        parts = re.split(r"(?m)^### (?=\d+\.\d+)", body)
        if len(parts) == 1:
            chunks.append((number, title, body))
            continue
        intro = parts[0]
        for index, part in enumerate(parts[1:]):
            sub_head, _, sub_body = part.partition("\n")
            sub_id = re.match(r"(\d+\.\d+)", sub_head).group(1)
            sub_title = re.sub(r"^\d+\.\d+\s*", "", sub_head).strip()
            chunks.append((sub_id, sub_title, (intro + "\n" if index == 0 else "") + sub_body))
    return chunks


def load_markdown_dir(path: Path) -> tuple[MedicalEvidenceDoc, ...]:
    """Load Cura guides written as markdown, with a sidecar .meta.json for review and keywords."""
    docs: list[MedicalEvidenceDoc] = []
    if not path.is_dir():
        return ()
    for meta_file in sorted(path.glob("*.meta.json")):
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        source = path / meta["document"]
        if not source.is_file():
            continue
        skip = set(meta.get("skip_sections") or [])
        for chunk_id, title, body in _markdown_chunks(source.read_text(encoding="utf-8"), skip):
            conf = (meta.get("chunks") or {}).get(chunk_id)
            excerpt = _clean_markdown(body)
            if not conf or not excerpt:
                continue
            docs.append(
                MedicalEvidenceDoc(
                    name=meta["name"],
                    title=title,
                    url="",
                    source_type="cura_knowledge_base",
                    tier=2,
                    topics=tuple(conf.get("topics") or meta.get("topics") or ()),
                    keywords=tuple(k.lower() for k in conf.get("keywords") or ()),
                    excerpt=excerpt,
                    publication_date=meta.get("publication_date"),
                    provenance=BIO_AI_EXPLAINER,
                    review_status=meta.get("review_status", "draft"),
                    version=meta.get("version", "cura-kb-v1"),
                    content_kind="cura_summary",
                    reviewer=meta.get("reviewer"),
                    reviewed_on=meta.get("reviewed_on"),
                    expires_on=meta.get("expires_on"),
                    licence_status="own_content",
                    region="IN",
                )
            )
    return tuple(docs)


def active_corpus() -> tuple[MedicalEvidenceDoc, ...]:
    corpus = CORPUS + load_content_dir(CONTENT_DIR) + load_markdown_dir(CONTENT_DIR / "markdown")
    return tuple(doc for doc in corpus if is_servable(doc))


class MedicalKnowledgeProvider(Protocol):
    """General medical knowledge only. Never a source of personal lab values."""

    def query(self, message: str, topic: str | None = None, limit: int = 2) -> list[MedicalEvidenceDoc]:
        ...


class CuratedMedicalKnowledgeProvider:
    """Curated guideline index. Not a vector store and not a source of personal values."""

    def query(
        self, message: str, topic: str | None = None, limit: int = 2, *, only_provenance: str | None = None
    ) -> list[MedicalEvidenceDoc]:
        return retrieve_medical_evidence(message, topic, limit=limit, only_provenance=only_provenance)


def retrieve_medical_evidence(
    message: str, topic: str | None = None, limit: int = 2, *, only_provenance: str | None = None
) -> list[MedicalEvidenceDoc]:
    text = (message or "").lower()
    from app.biomarkers.medical_registry import biomarker_content, eligible

    selective: list[MedicalEvidenceDoc] = []
    for row in biomarker_content().values():
        label = (row.get("display_name") or "").lower()
        if label and len(label) > 3 and label in text and eligible(row):
            selective.append(
                MedicalEvidenceDoc(
                    name=row.get("display_name") or row.get("biomarker_id") or "biomarker",
                    title=row.get("display_name") or "Biomarker",
                    url="",
                    source_type="cura_knowledge_base",
                    tier=2,
                    topics=(row.get("biomarker_id") or "",),
                    keywords=(label,),
                    excerpt=row.get("short_description") or "",
                    provenance="medical_registry_v2_3",
                    review_status=row.get("review_status") or "draft",
                    version=row.get("content_version") or "2.3",
                    content_kind="cura_summary",
                    licence_status="own_content",
                    region="IN",
                )
            )
            break
    topic_key = (topic or "").lower().replace(" ", "_")
    bio_ai_question = bool(_BIO_AI_ANCHOR.search(text))
    scored: list[tuple[int, int, int, MedicalEvidenceDoc]] = []
    for index, doc in enumerate(active_corpus()):
        if only_provenance and doc.provenance != only_provenance:
            continue
        if doc.provenance == BIO_AI_EXPLAINER and not bio_ai_question:
            continue
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
    excerpts = [
        passage_label(doc).removeprefix("Medical evidence: ").strip()
        for doc in docs
        if (doc.excerpt or "").strip()
    ]
    if not excerpts:
        return None
    return " ".join(excerpts)