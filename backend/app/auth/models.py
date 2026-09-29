from pydantic import BaseModel, Field


class AuthenticatedPrincipal(BaseModel):
    subject_id: str
    roles: list[str] = Field(default_factory=list)
    consent_scopes: list[str] = Field(default_factory=list)
    display_name: str | None = None
