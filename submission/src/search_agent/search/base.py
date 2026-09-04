from typing import Protocol

from search_agent.domain import Evidence


class SearchProvider(Protocol):
    async def search(self, query: str, max_results: int) -> list[Evidence]: ...
