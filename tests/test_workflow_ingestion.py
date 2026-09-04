from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from search_agent.companies import CompanyRegistry
from search_agent.domain import Evidence
from search_agent.graph.nodes import Nodes


@pytest.mark.asyncio
async def test_graph_ingests_report_after_web_search_for_stale_or_missing_evidence() -> None:
    registry = CompanyRegistry.load(Path("config/companies.yaml"))
    retrieval = MagicMock()
    retrieval.retrieve = AsyncMock(return_value=[
        Evidence(
            text="older evidence",
            title="Sustainability report 2023",
            url="https://assets.new.siemens.com/siemens/assets/api/uuid:old/report-2023.pdf",
            company="Siemens",
            year=2023,
        )
    ])
    search = MagicMock()
    search.search = AsyncMock(return_value=[
        Evidence(
            text="brand new official evidence",
            title="Sustainability report 2024",
            url="https://assets.new.siemens.com/siemens/assets/api/uuid:new/report-2024.pdf",
            company="Siemens",
            year=2024,
        )
    ])
    ingestion = AsyncMock()
    ingestion.ingest = AsyncMock(return_value=True)
    llm = MagicMock()
    llm.answer = AsyncMock(return_value="Final answer [1]")

    nodes = Nodes(
        registry,
        retrieval,
        search,
        llm,
        AsyncMock(),
        max_results=5,
        retrieval_top_k=6,
        ingestion=ingestion,
    )

    state = {"question": "What is Siemens' latest emissions target?", "companies": ["Siemens"], "attempts": 0}
    retrieve_result = await nodes.retrieve(state)
    assert retrieve_result["evidence"]

    evaluate_result = await nodes.evaluate({**state, "evidence": retrieve_result["evidence"]})
    assert evaluate_result["use_web"] is True

    web_result = await nodes.web({**state, "evidence": retrieve_result["evidence"]})
    assert web_result["attempts"] == 1

    ingest_result = await nodes.ingest_report({**state, "evidence": web_result["evidence"]})
    assert ingest_result["ingested"] is True
    ingestion.ingest.assert_awaited_once()

    final = await nodes.synthesize({**state, "route": "research", "evidence": web_result["evidence"]})
    assert "Final answer" in final["answer"]
