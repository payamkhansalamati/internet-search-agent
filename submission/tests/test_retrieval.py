from pathlib import Path

import pytest
from llama_index.core.embeddings import MockEmbedding

from search_agent.domain import Evidence
from search_agent.retrieval.service import RetrievalService


def item(
    text: str,
    company: str,
    year: int,
    document_id: str,
    page_numbers: tuple[int, ...] = (1,),
) -> Evidence:
    return Evidence(
        text=text,
        title=f"{company} report",
        url=f"https://example.com/{document_id}.pdf",
        company=company,
        year=year,
        page=page_numbers[0],
        section="Emissions",
        document_id=document_id,
        page_numbers=page_numbers,
        extraction_confidence=0.92,
    )


def service(path: Path) -> RetrievalService:
    return RetrievalService(path, embed_model=MockEmbedding(embed_dim=8), semantic_weight=0.5)


@pytest.mark.asyncio
async def test_persistence_duplicate_and_page_metadata(tmp_path: Path) -> None:
    first = service(tmp_path)
    evidence = [item("Scope 1 emissions were 100 tCO2e", "ABB", 2023, "abb-2023", (10, 11))]
    assert first.add(evidence, document_id="abb-2023", checksum="one")
    assert not first.add(evidence, document_id="abb-2023", checksum="one")

    loaded = service(tmp_path)
    result = await loaded.retrieve("Scope 1 emissions", companies=["ABB"], year=2023)
    assert result[0].page_numbers == (10, 11)
    assert result[0].extraction_confidence == 0.92
    assert result[0].score is not None


@pytest.mark.asyncio
async def test_metadata_filters_and_balanced_company_retrieval(tmp_path: Path) -> None:
    index = service(tmp_path)
    index.add(
        [item(f"emissions target ABB detail {number}", "ABB", 2023, "abb") for number in range(5)],
        document_id="abb",
        checksum="abb-v1",
    )
    index.add(
        [item("emissions target BMW detail", "BMW Group", 2024, "bmw")],
        document_id="bmw",
        checksum="bmw-v1",
    )
    filtered = await index.retrieve("emissions target", companies=["BMW Group"], year=2024)
    assert filtered and {row.company for row in filtered} == {"BMW Group"}

    comparison = await index.retrieve("compare emissions target", limit=4, companies=["ABB", "BMW Group"])
    assert {row.company for row in comparison} == {"ABB", "BMW Group"}
    assert comparison[0].company != comparison[1].company


@pytest.mark.asyncio
async def test_index_update_replaces_previous_nodes(tmp_path: Path) -> None:
    index = service(tmp_path)
    index.add([item("obsolete water metric", "ABB", 2023, "abb")], document_id="abb", checksum="old")
    assert index.add([item("updated energy metric", "ABB", 2023, "abb")], document_id="abb", checksum="new")
    old_query = await index.retrieve("obsolete water", companies=["ABB"])
    assert all("obsolete" not in row.text for row in old_query)
    assert await index.retrieve("updated energy", companies=["ABB"])


@pytest.mark.asyncio
async def test_lexical_fallback_when_semantic_retrieval_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    index = service(tmp_path)
    index.add([item("exact ESG taxonomy term", "ABB", 2023, "abb")], document_id="abb", checksum="v1")

    class BrokenRetriever:
        def retrieve(self, query: str) -> list[object]:
            raise RuntimeError("embedding unavailable")

    assert index._index is not None
    monkeypatch.setattr(index._index, "as_retriever", lambda **_: BrokenRetriever())
    result = await index.retrieve("exact ESG taxonomy", companies=["ABB"])
    assert result and result[0].company == "ABB"
