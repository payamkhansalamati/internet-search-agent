from typing import Any

from search_agent.companies import CompanyRegistry
from search_agent.search.duckduckgo import DuckDuckGoSearch
from search_agent.settings import get_settings


def create_server() -> Any:
    from fastmcp import FastMCP

    settings = get_settings()
    registry = CompanyRegistry.load(settings.companies_path)
    server = FastMCP("Internet Search Agent")

    @server.tool
    def list_supported_companies() -> list[str]:
        return [company.name for company in registry.companies]

    @server.tool
    async def search_sustainability_reports(query: str) -> list[dict[str, str]]:
        rows = await DuckDuckGoSearch().search(f"{query} sustainability report", settings.search_max_results)
        return [{"title": row.title, "url": row.url, "snippet": row.text} for row in rows]

    @server.tool
    def get_report_metadata(company: str) -> dict[str, object]:
        matches = registry.resolve(company)
        return (
            {"company": matches[0].name, "approved_domains": matches[0].domains}
            if matches
            else {"error": "Unsupported company"}
        )

    return server


if __name__ == "__main__":
    create_server().run()
