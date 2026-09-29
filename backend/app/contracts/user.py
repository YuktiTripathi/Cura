from pydantic import BaseModel, Field


class UserProfile(BaseModel):
    subject_id: str
    display_name: str
    first_name: str | None = None
    last_name: str | None = None
    age_band: str | None = None
    sex: str | None = None
