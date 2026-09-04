import tempfile
from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi.testclient import TestClient
from llama_index.core.embeddings import MockEmbedding

from search_agent.companies import CompanyRegistry
from search_agent.domain import Evidence
from search_agent.graph.nodes import Nodes
from search_agent.graph.workflow import build_graph
from search_agent.main import create_app
from search_agent.retrieval.service import RetrievalService
from search_agent.settings import Settings


class VerificationLLM:
    async def answer(self, question: str, evidence: list[Evidence]) -> str:
        citation = next(index for index, item in enumerate(evidence, 1) if "42 GWh" in item.text)
        return f"The verification report records renewable electricity of 42 GWh [{citation}]."


class NoWebSearch:
    async def search(self, query: str, max_results: int) -> list[Evidence]:
        raise AssertionError("Indexed evidence should make web search unnecessary")


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        settings = Settings(index_path=root / "app-index", manifest_path=root / "manifest.json")
        app = create_app(settings)
        with TestClient(app) as client:
            retrieval = RetrievalService(
                root / "verification-index",
                embed_model=MockEmbedding(embed_dim=8),
                semantic_weight=0.5,
            )
            common = {
                "title": "Verification Sustainability Report 2024",
                "url": "https://example.com/verification-report.pdf",
                "company": "Verification Corp",
                "year": 2024,
                "document_id": "verification-2024",
                "table_metadata": {"kind": "table"},
            }
            evidence = [
                Evidence(
                    text=(
                        "Renewable electricity consumption was 42 GWh in fiscal year 2024. The value covers the "
                        "verification entity's reported operations and is reproduced as a synthetic test fixture "
                        "for retrieval, citation numbering, snippets, and page-link behavior."
                    ),
                    pdf_page=7,
                    printed_page="5",
                    units=("GWh",),
                    **common,
                ),
                Evidence(
                    text=(
                        "The verification report describes its organizational boundary and reporting methodology "
                        "on a separate page. This second synthetic evidence item ensures the implemented local "
                        "evidence-sufficiency threshold is met without invoking any live web provider."
                    ),
                    pdf_page=8,
                    printed_page="6",
                    **common,
                ),
            ]
            assert retrieval.add(evidence, document_id="verification-2024", checksum="verification-v1")
            registry = CompanyRegistry.load(settings.companies_path)

            def graph_factory(status: Callable[[str], Awaitable[None]]) -> object:
                return build_graph(Nodes(registry, retrieval, NoWebSearch(), VerificationLLM(), status, 5, 6))

            app.state.graph_factory = graph_factory
            app.state.graph = graph_factory(_noop)

            assert client.get("/health").json() == {"status": "ok"}
            assert client.get("/ready").json() == {"status": "ready"}
            accepted = client.post(
                "/api/v1/query",
                json={"question": "What renewable electricity did the verification report record in 2024?"},
            )
            accepted.raise_for_status()
            request_id = accepted.json()["request_id"]
            status = client.get(f"/api/v1/status/{request_id}")
            status.raise_for_status()
            assert status.json()["stage"] == "completed"
            response = client.get(f"/api/v1/requests/{request_id}")
            response.raise_for_status()
            result = response.json()
            assert "42 GWh [" in result["answer"]
            assert result["used_live_web"] is False
            assert len(result["sources"]) >= 1
            source = next(item for item in result["sources"] if "42 GWh" in item["snippet"])
            assert source["pdf_page"] == 7 and source["printed_page"] == "5"
            assert str(source["url"]).endswith("#page=7")
            assert "42 GWh" in source["snippet"]
            print("submission verification passed: API, retrieval, synthesis, citation and page metadata")


async def _noop(_: str) -> None:
    return None


if __name__ == "__main__":
    main()
