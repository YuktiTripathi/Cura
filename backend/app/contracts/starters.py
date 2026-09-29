from pydantic import BaseModel, Field


class StarterQuestion(BaseModel):
    text: str
    knowledge_scope: str
    category: str


class StarterQuestionSet(BaseModel):
    personal: list[StarterQuestion] = Field(default_factory=list)
    general: list[StarterQuestion] = Field(default_factory=list)
    personal_unavailable: bool = False
