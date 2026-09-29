from datetime import date

from pydantic import BaseModel


class EvidenceRecord(BaseModel):
    evidence_id: str
    report_id: str
    report_type: str
    report_date: date
    marker: str | None = None
    risk_code: str | None = None
    source: str = "supershyft"
    document_id: str | None = None
    chunk_id: str | None = None
    filename: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    excerpt: str | None = None
    value: float | None = None
    unit: str | None = None
    reference_range: str | None = None
