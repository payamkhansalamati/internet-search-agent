from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True, slots=True)
class Evidence:
    text: str
    title: str
    url: str
    company: str | None = None
    year: int | None = None
    page: int | None = None
    section: str | None = None
    score: float | None = None
    document_id: str | None = None
    page_numbers: tuple[int, ...] = ()
    pdf_page: int | None = None
    pdf_pages: tuple[int, ...] = ()
    printed_page: str | None = None
    units: tuple[str, ...] = ()
    table_metadata: dict[str, object] | None = None
    extraction_confidence: float | None = None

    def __post_init__(self) -> None:
        physical_page = self.pdf_page if self.pdf_page is not None else self.page
        physical_pages = self.pdf_pages or self.page_numbers or ((physical_page,) if physical_page is not None else ())
        if self.page is not None and self.pdf_page is not None and self.page != self.pdf_page:
            raise ValueError("page and pdf_page cannot identify different physical pages")
        object.__setattr__(self, "page", physical_page)
        object.__setattr__(self, "pdf_page", physical_page)
        object.__setattr__(self, "page_numbers", physical_pages)
        object.__setattr__(self, "pdf_pages", physical_pages)


@dataclass(frozen=True, slots=True)
class ResearchResult:
    answer: str
    sources: list[Evidence] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    used_live_web: bool = False
    confidence: Literal["low", "medium", "high"] = "low"
