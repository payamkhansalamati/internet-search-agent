from typing import Protocol

from search_agent.domain import Evidence


class LLM(Protocol):
    async def answer(self, question: str, evidence: list[Evidence]) -> str: ...
