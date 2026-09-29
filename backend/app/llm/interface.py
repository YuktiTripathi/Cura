from typing import Protocol

from app.llm.models import LLMStructuredOutput


class LLMClient(Protocol):
    def complete(self, messages: list[dict[str, str]]) -> str:
        ...

    def complete_structured(self, messages: list[dict[str, str]]) -> LLMStructuredOutput:
        ...

    def stream(self, messages: list[dict[str, str]]):
        ...
