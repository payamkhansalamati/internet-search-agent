import json
from pathlib import Path

import pytest
from llama_index.core.embeddings import MockEmbedding

from search_agent.domain import Evidence
from search_agent.llm.providers import evidence_context
from search_agent.retrieval.service import RetrievalService

QUERY = (
    "Compare ABB and Siemens based on their 2024 sustainability reports across Scope 1, Scope 2, Scope 3 "
    "emissions, energy consumption, renewable electricity, water consumption, and waste. Present the reported "
    "values and units in a table, cite the source page for every value, and clearly identify differences in "
    "reporting boundaries or methodology. Do not infer missing values."
)


@pytest.mark.asyncio
async def test_exact_abb_siemens_kpi_comparison_retrieves_every_expected_value_and_page(tmp_path: Path) -> None:
    rows = json.loads(Path("tests/fixtures/abb_siemens_2024_kpis.json").read_text())
    service = RetrievalService(tmp_path / "index", embed_model=MockEmbedding(embed_dim=8), semantic_weight=0.5)
    for company in ("ABB", "Siemens"):
        company_rows = [row for row in rows if row["company"] == company]
        evidence = [
            Evidence(
                text=row["text"],
                title=f"{company} Sustainability Report 2024",
                url=f"https://example.com/{company.casefold()}-2024.pdf",
                company=company,
                year=2024,
                page=row["page"],
                section=row["metric"],
                document_id=f"{company.casefold()}-2024",
                page_numbers=(row["page"],),
                units=(row["unit"],) if row["unit"] else (),
                table_metadata={"kind": "table"},
            )
            for row in company_rows
        ]
        assert service.add(evidence, document_id=f"{company.casefold()}-2024", checksum=f"{company}-v2")

    result = await service.retrieve(QUERY, limit=18, companies=["ABB", "Siemens"], year=2024)

    for expected in rows:
        expected_values = expected.get("expected_values", expected["value"].split(" / "))
        matching = [
            item
            for item in result
            if item.company == expected["company"]
            and all(value in item.text for value in expected_values)
            and expected["page"] in item.page_numbers
        ]
        assert matching, f"missing {expected['company']} {expected['metric']} from page {expected['page']}"
    assert {item.company for item in result[:2]} == {"ABB", "Siemens"}
    context = evidence_context(result)
    assert "company=ABB; report_year=2024" in context
    assert "company=Siemens; report_year=2024" in context
    assert all(f"pdf_pages={item.page}" in context for item in result)

    siemens_scope_2 = next(item for item in result if item.company == "Siemens" and item.section == "scope_2")
    assert siemens_scope_2.page_numbers == (120,)
    assert "market based 94" in siemens_scope_2.text
    assert "location based 667" in siemens_scope_2.text
    assert siemens_scope_2.units == ("kt CO2e",)
    siemens_energy = next(item for item in result if item.company == "Siemens" and item.section == "energy")
    assert "9,012" in siemens_energy.text and siemens_energy.units == ("thousand GJ",)
    siemens_waste = next(item for item in result if item.company == "Siemens" and item.section == "waste")
    assert "345.5" in siemens_waste.text and siemens_waste.units == ("thousand tons",)
