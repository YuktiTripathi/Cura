from datetime import date, datetime

from pydantic import BaseModel, Field

from app.contracts.common import MarkerFlag


class BloodMarker(BaseModel):
    id: str
    key: str
    name: str
    value: float | None = None
    unit: str | None = None
    reference_low: float | None = None
    reference_high: float | None = None
    flag: MarkerFlag = MarkerFlag.unknown
    category: str | None = None
    status: MarkerFlag | None = None
    source: str = "supershyft"
    report_id: str | None = None
    measured_at: date | datetime | None = None

    def model_post_init(self, __context) -> None:
        if self.status is None:
            self.status = self.flag


class BloodReport(BaseModel):
    report_id: str
    report_date: date
    source: str = "blood_report"
    markers: list[BloodMarker] = Field(default_factory=list)
    assessment_instance_id: str | None = None
    engagement_id: str | None = None
    report_url: str | None = None
