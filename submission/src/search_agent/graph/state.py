from typing import Literal, TypedDict

from search_agent.domain import Evidence, ResearchResult


class AgentState(TypedDict, total=False):
    question: str
    route: Literal["conversation", "research"]
    companies: list[str]
    evidence: list[Evidence]
    attempts: int
    use_web: bool
    answer: str
    result: ResearchResult
