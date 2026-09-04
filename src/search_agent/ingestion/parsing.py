import logging
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, replace
from io import BytesIO
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from search_agent.domain import Evidence
from search_agent.glossary import SustainabilityGlossary
from search_agent.ingestion.documents import Report
from search_agent.page_labels import pdf_page_labels, resolve_printed_pages

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TableFragment:
    markdown: str
    pages: tuple[int, ...]
    headers: tuple[str, ...]
    columns: int
    caption: str | None = None
    units: tuple[str, ...] = ()
    confidence: float | None = None
    section: str | None = None


class DocumentParser:
    def __init__(
        self,
        *,
        use_ocr: bool = True,
        table_mode: str = "accurate",
        allow_fallback: bool = True,
        glossary: SustainabilityGlossary | None = None,
    ) -> None:
        self.use_ocr = use_ocr
        self.table_mode = table_mode
        self.allow_fallback = allow_fallback
        self.glossary = glossary or SustainabilityGlossary.load_default()

    def parse(self, content: bytes, report: Report, document_id: str) -> list[Evidence]:
        try:
            return self._parse_docling(content, report, document_id)
        except Exception as exc:
            if not self.allow_fallback:
                raise
            log.warning("Docling extraction failed; using page-text fallback: %s", type(exc).__name__)
            return self._parse_pypdf(content, report, document_id)

    def _parse_docling(self, content: bytes, report: Report, document_id: str) -> list[Evidence]:
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions, TableFormerMode
        from docling.document_converter import DocumentConverter, PdfFormatOption

        options = PdfPipelineOptions()
        options.do_ocr = self.use_ocr
        options.do_table_structure = True
        options.table_structure_options.mode = (
            TableFormerMode.ACCURATE if self.table_mode == "accurate" else TableFormerMode.FAST
        )
        converter = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)})
        with tempfile.NamedTemporaryFile(suffix=".pdf") as handle:
            handle.write(content)
            handle.flush()
            document = converter.convert(Path(handle.name)).document
        # Docling provides layout-aware tables and headings. PyPDF page text is
        # retained as a complementary representation because chart labels and
        # values are sometimes separate visual objects that Docling cannot join.
        page_text = self._parse_pypdf(content, report, document_id)
        printed_pages = {item.pdf_page: item.printed_page for item in page_text if item.pdf_page is not None}
        layout = [
            replace(item, printed_page=printed_pages.get(item.pdf_page) if item.pdf_page is not None else None)
            for item in _docling_evidence(document, report, document_id, self.glossary)
        ]
        return layout + page_text

    def _parse_pypdf(self, content: bytes, report: Report, document_id: str) -> list[Evidence]:
        reader = PdfReader(BytesIO(content))
        texts = [(page.extract_text() or "") for page in reader.pages]
        printed_pages = resolve_printed_pages(texts, pdf_page_labels(reader, len(texts)))
        pages: list[Evidence] = []
        for number, (text, printed_page) in enumerate(zip(texts, printed_pages, strict=True), 1):
            if text:
                pages.append(
                    Evidence(
                        text=text,
                        title=report.title,
                        url=report.url,
                        company=report.company,
                        year=report.year,
                        pdf_page=number,
                        document_id=document_id,
                        pdf_pages=(number,),
                        printed_page=printed_page,
                        units=extract_units(text, self.glossary),
                    )
                )
        return pages


def _docling_evidence(
    document: Any, report: Report, document_id: str, glossary: SustainabilityGlossary
) -> list[Evidence]:
    evidence: list[Evidence] = []
    tables: list[TableFragment] = []
    section: str | None = None
    for item, _level in document.iterate_items():
        label = str(getattr(item, "label", "")).casefold()
        text = str(getattr(item, "text", "") or "").strip()
        pages = _provenance_pages(item)
        confidence = _provenance_confidence(item)
        if "section_header" in label or label.endswith("title"):
            section = text or section
        if "table" in label:
            markdown = _table_markdown(item, document)
            headers, columns = _table_shape(markdown)
            tables.append(
                TableFragment(
                    markdown,
                    pages,
                    headers,
                    columns,
                    _caption(item),
                    extract_units(markdown, glossary),
                    confidence,
                    section,
                )
            )
        elif text:
            evidence.append(_evidence(text, report, document_id, section, pages, confidence, glossary=glossary))
    # Keep table fragments page-local. Merging a multi-page appendix table
    # destroys the mapping between individual KPI rows and their PDF pages.
    for table in tables:
        metadata: dict[str, object] = {
            "kind": "table",
            "caption": table.caption,
            "headers": list(table.headers),
            "columns": table.columns,
            "units": list(table.units),
        }
        evidence.append(
            _evidence(
                table.markdown,
                report,
                document_id,
                table.section,
                table.pages,
                table.confidence,
                metadata,
                glossary,
            )
        )
    if not evidence:
        raise RuntimeError("Docling produced no extractable content")
    return evidence


def _evidence(
    text: str,
    report: Report,
    document_id: str,
    section: str | None,
    pages: tuple[int, ...],
    confidence: float | None,
    table_metadata: dict[str, object] | None = None,
    glossary: SustainabilityGlossary | None = None,
) -> Evidence:
    return Evidence(
        text=text,
        title=report.title,
        url=report.url,
        company=report.company,
        year=report.year,
        pdf_page=pages[0] if pages else None,
        section=section,
        document_id=document_id,
        pdf_pages=pages,
        units=extract_units(text, glossary),
        table_metadata=table_metadata,
        extraction_confidence=confidence,
    )


def _provenance_pages(item: Any) -> tuple[int, ...]:
    return tuple(
        dict.fromkeys(int(prov.page_no) for prov in getattr(item, "prov", []) if getattr(prov, "page_no", None))
    )


def _provenance_confidence(item: Any) -> float | None:
    values = [float(value) for prov in getattr(item, "prov", []) if (value := getattr(prov, "confidence", None))]
    return min(values) if values else None


def _table_markdown(item: Any, document: Any) -> str:
    exporter: Callable[..., str] | None = getattr(item, "export_to_markdown", None)
    if exporter:
        try:
            return exporter(doc=document)
        except TypeError:
            return exporter()
    return str(getattr(item, "text", ""))


def _caption(item: Any) -> str | None:
    captions = getattr(item, "captions", [])
    return " ".join(str(getattr(caption, "text", caption)) for caption in captions) if captions else None


def _table_shape(markdown: str) -> tuple[tuple[str, ...], int]:
    rows = [line.strip().strip("|") for line in markdown.splitlines() if "|" in line]
    if not rows:
        return (), 0
    headers = tuple(cell.strip() for cell in rows[0].split("|"))
    return headers, len(headers)


def extract_units(text: str, glossary: SustainabilityGlossary | None = None) -> tuple[str, ...]:
    glossary = glossary or SustainabilityGlossary.load_default()
    return glossary.normalize_units(text)


def _chunk_table(page: Evidence, size: int, glossary: SustainabilityGlossary) -> list[Evidence]:
    lines = [line for line in page.text.splitlines() if line.strip()]
    if len(page.text) <= size or len(lines) < 3:
        return [page]
    header = lines[:2]
    rows = lines[2:]
    chunks: list[Evidence] = []
    current = header.copy()
    for row in rows:
        candidate = "\n".join((*current, row))
        if len(candidate) > size and len(current) > len(header):
            text = "\n".join(current)
            chunks.append(replace(page, text=text, units=extract_units(text, glossary)))
            current = [*header, row]
        else:
            current.append(row)
    if len(current) > len(header):
        text = "\n".join(current)
        chunks.append(replace(page, text=text, units=extract_units(text, glossary)))
    return chunks or [page]


def chunk_pages(
    pages: list[Evidence],
    size: int = 1800,
    overlap: int = 200,
    glossary: SustainabilityGlossary | None = None,
) -> list[Evidence]:
    glossary = glossary or SustainabilityGlossary.load_default()
    chunks: list[Evidence] = []
    for page in pages:
        if page.table_metadata and page.table_metadata.get("kind") == "table":
            chunks.extend(_chunk_table(page, size, glossary))
            continue
        if len(page.text) <= size:
            chunks.append(page)
            continue
        for start in range(0, len(page.text), size - overlap):
            text = page.text[start : start + size]
            chunks.append(replace(page, text=text, units=extract_units(text, glossary)))
    return chunks
