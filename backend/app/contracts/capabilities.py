from pydantic import BaseModel

from app.contracts.me import MeCapabilities
from app.contracts.starters import StarterQuestionSet


class CapabilitiesResponse(BaseModel):
    capabilities: MeCapabilities
    starters: StarterQuestionSet
