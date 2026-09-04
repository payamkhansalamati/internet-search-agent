from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from search_agent.companies import CompanyRegistry
from search_agent.domain import Evidence
from search_agent.graph.nodes import GREETING, Nodes, comparability_warnings, evidence_sufficient
from search_agent.search.validation import UnsafeURL, validate_url


@pytest.fixture
def registry() -> CompanyRegistry:
    return CompanyRegistry.load(Path("config/companies.yaml"))


def test_company_resolution_and_warning(registry: CompanyRegistry) -> None:
    company = registry.resolve("Compare GE Vernova today")[0]
    assert company.name == "GE Vernova" and "General Electric" in (company.warning or "")


def test_conversation_routing() -> None:
    assert GREETING.match("Hello!")
    assert not GREETING.match("Hello, what did ABB report?")


def test_url_security(registry: CompanyRegistry) -> None:
    assert validate_url("https://reports.siemens.com/a.pdf", registry.approved_domains(), resolve_dns=False)
    for bad in ("http://siemens.com/a.pdf", "https://evil.test/a.pdf", "https://user:pass@siemens.com/a"):
        with pytest.raises(UnsafeURL):
            validate_url(bad, registry.approved_domains(), resolve_dns=False)


def test_evidence_and_comparability() -> None:
    evidence = [
        Evidence("x" * 200, "a", "https://a", "ABB", 2023),
        Evidence("y" * 200, "b", "https://b", "BMW Group", 2024),
    ]
    assert evidence_sufficient(evidence)
    assert len(comparability_warnings(evidence)) == 2


@pytest.mark.asyncio
async def test_finds_official_pdf_for_automatic_ingestion_only_when_missing_or_stale() -> None:
    registry = CompanyRegistry.load(Path("config/companies.yaml"))
    pipeline = AsyncMock()
    pipeline.ingest.return_value = True
    nodes = Nodes(
        registry,
        MagicMock(),
        MagicMock(),
        MagicMock(),
        AsyncMock(),
        max_results=5,
        ingestion=pipeline,
    )

    insufficient = await nodes.ingest_report(
        {
            "question": "What is Siemens' latest emissions target?",
            "companies": ["Siemens"],
            "evidence": [
                Evidence(
                    "Siemens sustainability report excerpt",
                    "Sustainability report 2024",
                    "https://assets.new.siemens.com/siemens/assets/api/uuid:cf240c4d-2e09-42ee-9ed8-752a47ab924f/sustainability-report-2024.pdf",
                    "Siemens",
                    2024,
                )
            ],
        }
    )
    assert insufficient["ingested"] is True
    pipeline.ingest.assert_awaited_once()

    pipeline.ingest.reset_mock()
    sufficient = await nodes.ingest_report(
        {
            "question": "What is Siemens' emissions target?",
            "companies": ["Siemens"],
            "evidence": [
                Evidence("x" * 200, "Official report", "https://siemens.com/report-2024.pdf", "Siemens", 2024),
                Evidence("y" * 200, "Official report", "https://siemens.com/report-2024.pdf", "Siemens", 2024),
            ],
        }
    )
    assert sufficient["ingested"] is False
    pipeline.ingest.assert_not_awaited()
