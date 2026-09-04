import asyncio

from ddgs import DDGS

from search_agent.domain import Evidence


class DuckDuckGoSearch:
    async def search(self, query: str, max_results: int) -> list[Evidence]:
        def run() -> list[dict[str, str]]:
            return list(DDGS().text(query, max_results=max_results))

        rows = await asyncio.to_thread(run)
        return [Evidence(text=r.get("body", ""), title=r.get("title", "Untitled"), url=r.get("href", "")) for r in rows]
