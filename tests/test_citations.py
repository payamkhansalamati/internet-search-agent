from search_agent.api.routes import build_sources
from search_agent.citations import (
    citation_page_label,
    deduplicate_citation_evidence,
    evidence_snippet,
    page_url,
    remove_unmapped_citations,
)
from search_agent.domain import Evidence


def evidence(
    text: str,
    *,
    company: str = "ABB",
    document_id: str = "abb-2024",
    page: int = 36,
    printed_page: str | None = "34",
) -> Evidence:
    return Evidence(
        text=text,
        title=f"{company} Sustainability Report 2024",
        url=f"https://example.com/{company.casefold()}.pdf?download=1",
        company=company,
        year=2024,
        page=page,
        document_id=document_id,
        page_numbers=(page,),
        printed_page=printed_page,
        units=("kt CO2e",),
    )


def test_citation_sources_are_numbered_deduplicated_and_page_linked_with_snippets() -> None:
    rows = deduplicate_citation_evidence(
        [
            evidence("Scope 1 total was 119 kt CO2e."),
            evidence("Scope 2 market-based total was 19 kt CO2e."),
            evidence("Total waste was 177,465 tons.", page=43, printed_page="41"),
            evidence("Siemens Scope 2 was 94 market based.", company="Siemens", document_id="siemens-2024", page=120),
        ]
    )
    sources = build_sources(rows)

    assert len(rows) == 3
    assert "Scope 1 total" in rows[0].text and "Scope 2 market-based" in rows[0].text
    assert [source.citation_number for source in sources] == [1, 2, 3]
    assert str(sources[0].url).endswith("?download=1#page=36")
    assert sources[0].pdf_page == 36 and sources[0].printed_page == "34"
    assert sources[0].company == "ABB" and sources[0].reporting_year == 2024
    assert sources[0].snippet == evidence_snippet(rows[0])


def test_page_url_replaces_an_existing_fragment_without_custom_highlighting() -> None:
    assert page_url("https://example.com/report.pdf?download=1#old", 120) == (
        "https://example.com/report.pdf?download=1#page=120"
    )
    assert page_url("https://example.com/report.pdf", None) == "https://example.com/report.pdf"


def test_citation_page_display_distinguishes_report_and_pdf_pages() -> None:
    assert citation_page_label("34", 36) == "report p. 34 · PDF p. 36"
    assert citation_page_label("36", 36) == "p. 36"
    assert citation_page_label("1", 3) == "report p. 1 · PDF p. 3"
    assert citation_page_label("iv", 4) == "report p. iv · PDF p. 4"
    assert citation_page_label("A-1", 20) == "report p. A-1 · PDF p. 20"
    assert citation_page_label(None, 36) == "PDF p. 36"


def test_printed_labels_never_change_the_physical_pdf_link() -> None:
    for printed_page, pdf_page in (("1", 3), ("iv", 4), ("A-1", 20), (None, 7)):
        row = evidence("Evidence", page=pdf_page, printed_page=printed_page)
        source = build_sources(deduplicate_citation_evidence([row]))[0]
        assert source.pdf_page == pdf_page
        assert str(source.url).endswith(f"#page={pdf_page}")


def test_every_retained_citation_number_has_a_source_entry() -> None:
    answer, invalid = remove_unmapped_citations("ABB [1], Siemens [2], unsupported [7].", source_count=2)
    assert answer == "ABB [1], Siemens [2], unsupported ."
    assert invalid == [7]
