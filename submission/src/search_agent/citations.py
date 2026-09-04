import re
from dataclasses import replace
from urllib.parse import urlsplit, urlunsplit

from search_agent.domain import Evidence

CITATION = re.compile(r"\[(\d+)\]")
MAX_CITATION_TEXT = 6000
MAX_SNIPPET = 600


def deduplicate_citation_evidence(evidence: list[Evidence]) -> list[Evidence]:
    ordered: list[Evidence] = []
    positions: dict[tuple[str, int | None], int] = {}
    for item in evidence:
        if not item.url:
            continue
        physical_page = item.pdf_page or (item.pdf_pages[0] if item.pdf_pages else None)
        document = item.document_id or item.url
        key = (document, physical_page)
        if key not in positions:
            positions[key] = len(ordered)
            ordered.append(
                replace(
                    item,
                    pdf_page=physical_page,
                    pdf_pages=(physical_page,) if physical_page else (),
                )
            )
            continue
        position = positions[key]
        current = ordered[position]
        text = current.text
        if item.text not in text:
            text = f"{text}\n\n{item.text}"[:MAX_CITATION_TEXT]
        ordered[position] = replace(
            current,
            text=text,
            section=current.section or item.section,
            printed_page=current.printed_page or item.printed_page,
            units=tuple(dict.fromkeys((*current.units, *item.units))),
            table_metadata=current.table_metadata or item.table_metadata,
            extraction_confidence=current.extraction_confidence or item.extraction_confidence,
        )
    return ordered


def page_url(url: str, physical_page: int | None) -> str:
    if physical_page is None:
        return url
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, f"page={physical_page}"))


def citation_page_label(printed_page: str | None, pdf_page: int | None) -> str:
    if printed_page is not None and pdf_page is not None:
        if printed_page == str(pdf_page):
            return f"p. {printed_page}"
        return f"report p. {printed_page} · PDF p. {pdf_page}"
    if printed_page is not None:
        return f"report p. {printed_page}"
    if pdf_page is not None:
        return f"PDF p. {pdf_page}"
    return "page unavailable"


def evidence_snippet(item: Evidence, limit: int = MAX_SNIPPET) -> str:
    compact = " ".join(item.text.split())
    return compact if len(compact) <= limit else f"{compact[: limit - 1].rstrip()}…"


def remove_unmapped_citations(answer: str, source_count: int) -> tuple[str, list[int]]:
    invalid: list[int] = []

    def replace_marker(match: re.Match[str]) -> str:
        number = int(match.group(1))
        if 1 <= number <= source_count:
            return match.group(0)
        invalid.append(number)
        return ""

    return CITATION.sub(replace_marker, answer), invalid
