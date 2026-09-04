from search_agent.domain import Evidence
from search_agent.ingestion.documents import Report
from search_agent.ingestion.parsing import (
    DocumentParser,
    chunk_pages,
    extract_units,
)


def test_parser_falls_back_when_docling_fails() -> None:
    report = Report("ABB", 2023, "Report", "https://abb.com/report.pdf")

    class StubParser(DocumentParser):
        def _parse_docling(self, content: bytes, report: Report, document_id: str) -> list[Evidence]:
            raise RuntimeError("Docling unavailable")

        def _parse_pypdf(self, content: bytes, report: Report, document_id: str) -> list[Evidence]:
            return [Evidence("fallback", report.title, report.url, report.company, report.year, 1)]

    result = StubParser().parse(b"pdf", report, "abb-2023")
    assert result[0].text == "fallback" and result[0].page_numbers == (1,)


def test_large_table_is_split_by_rows_with_header_page_and_units_preserved() -> None:
    header = "| Metric | Unit | FY 2024 |\n|---|---|---|"
    rows = [f"| KPI {number} | 1,000 metric tons of CO2e | {number:,} |" for number in range(60)]
    evidence = Evidence(
        f"{header}\n" + "\n".join(rows),
        "Sustainability report",
        "https://example.com/report.pdf",
        "Siemens",
        2024,
        120,
        "Sustainability KPIs",
        page_numbers=(120,),
        units=("kt CO2e",),
        table_metadata={"kind": "table", "headers": ["Metric", "Unit", "FY 2024"]},
    )

    chunks = chunk_pages([evidence], size=500, overlap=50)

    assert len(chunks) > 1
    assert all(chunk.text.startswith(header) for chunk in chunks)
    assert all(chunk.company == "Siemens" and chunk.year == 2024 for chunk in chunks)
    assert all(chunk.page_numbers == (120,) and chunk.units == ("kt CO2e",) for chunk in chunks)


def test_unit_extraction_normalizes_esg_units() -> None:
    text = "Scope 1: 347 in 1,000 metric tons of CO2e; energy 9,012 thousand gigajoules; water 0.67 million m3"
    assert extract_units(text) == ("kt CO2e", "thousand GJ", "million m3")
