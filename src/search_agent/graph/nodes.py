import re
from collections.abc import Awaitable, Callable
from urllib.parse import urlparse

from search_agent.citations import deduplicate_citation_evidence, remove_unmapped_citations
from search_agent.companies import CompanyRegistry
from search_agent.domain import Evidence, ResearchResult
from search_agent.graph.state import AgentState
from search_agent.ingestion.documents import Report
from search_agent.ingestion.pipeline import IngestionPipeline
from search_agent.llm.base import LLM
from search_agent.retrieval.service import RetrievalService
from search_agent.search.base import SearchProvider

StatusCallback = Callable[[str], Awaitable[None]]
GREETING = re.compile(r"^\s*(hi|hello|hey|good (morning|afternoon|evening))[!.\s]*$", re.I)


def evidence_sufficient(evidence: list[Evidence]) -> bool:
    return len(evidence) >= 2 and sum(len(item.text) for item in evidence) >= 300


def comparability_warnings(evidence: list[Evidence]) -> list[str]:
    warnings: list[str] = []
    years = {e.year for e in evidence if e.year}
    companies = {e.company for e in evidence if e.company}
    if len(years) > 1:
        warnings.append("Sources cover different reporting years; compare values cautiously.")
    if len(companies) > 1:
        warnings.append("Reporting boundaries, units, and methodologies may differ between companies.")
    return warnings


class Nodes:
    def __init__(
        self,
        registry: CompanyRegistry,
        retrieval: RetrievalService,
        search: SearchProvider,
        llm: LLM,
        status: StatusCallback,
        max_results: int,
        retrieval_top_k: int = 6,
        ingestion: IngestionPipeline | None = None,
    ) -> None:
        self.registry, self.retrieval, self.search, self.llm, self.status, self.max_results = (
            registry,
            retrieval,
            search,
            llm,
            status,
            max_results,
        )
        self.retrieval_top_k = retrieval_top_k
        self.ingestion = ingestion

    async def classify(self, state: AgentState) -> AgentState:
        await self.status("classifying")
        return {"route": "conversation" if GREETING.match(state["question"]) else "research", "attempts": 0}

    async def resolve(self, state: AgentState) -> AgentState:
        return {"companies": [c.name for c in self.registry.resolve(state["question"])]}

    async def retrieve(self, state: AgentState) -> AgentState:
        await self.status("retrieving")
        return {
            "evidence": await self.retrieval.retrieve(
                state["question"],
                limit=self.retrieval_top_k,
                companies=state.get("companies") or None,
            )
        }

    async def evaluate(self, state: AgentState) -> AgentState:
        current = any(word in state["question"].casefold() for word in ("latest", "current", "today", "recent"))
        return {"use_web": current or not evidence_sufficient(state.get("evidence", []))}

    async def web(self, state: AgentState) -> AgentState:
        await self.status("searching")
        found = await self.search.search(state["question"], self.max_results)
        return {"evidence": state.get("evidence", []) + found, "attempts": state.get("attempts", 0) + 1}

    def _official_pdf_candidates(self, evidence: list[Evidence]) -> list[Evidence]:
        candidates: list[Evidence] = []
        for item in evidence:
            url = (item.url or "").strip()
            if not url.lower().endswith(".pdf"):
                continue
            host = urlparse(url).netloc.casefold()
            if not host:
                continue
            approved = {domain.casefold() for company in self.registry.companies for domain in company.domains}
            if not any(host == domain or host.endswith(f".{domain}") for domain in approved):
                continue
            candidates.append(item)
        return candidates

    def _should_ingest(self, state: AgentState) -> bool:
        evidence = state.get("evidence", [])
        candidates = self._official_pdf_candidates(evidence)
        if not candidates:
            return False

        current = any(word in state["question"].casefold() for word in ("latest", "current", "today", "recent"))
        if evidence_sufficient(evidence):
            newest_index_year = max((item.year for item in evidence if item.year is not None), default=0)
            newest_candidate_year = max((item.year for item in candidates if item.year is not None), default=0)
            return current and newest_candidate_year > newest_index_year

        return True

    async def ingest_report(self, state: AgentState) -> AgentState:
        if self.ingestion is None or not self._should_ingest(state):
            return {"ingested": False, "evidence": state.get("evidence", [])}

        candidates = self._official_pdf_candidates(state.get("evidence", []))
        source = max(candidates, key=lambda item: (item.year or 0, item.score or 0.0))
        companies = state.get("companies") or [company.name for company in self.registry.resolve(state["question"])]
        company = source.company or next((name for name in companies if name), "")
        report = Report(
            company=company,
            year=int(source.year or 2024),
            title=source.title or "Sustainability report",
            url=source.url,
        )
        try:
            ingested = await self.ingestion.ingest(report)
            return {"ingested": ingested, "evidence": state.get("evidence", [])}
        except ValueError:
            return {"ingested": False, "evidence": state.get("evidence", [])}

    async def synthesize(self, state: AgentState) -> AgentState:
        await self.status("synthesizing")
        if state["route"] == "conversation":
            return {"answer": "Hello! Ask me about sustainability reports from a supported company."}
        evidence = deduplicate_citation_evidence(state.get("evidence", []))
        return {"answer": await self.llm.answer(state["question"], evidence), "evidence": evidence}

    async def validate(self, state: AgentState) -> AgentState:
        await self.status("validating")
        evidence = state.get("evidence", [])
        warnings = comparability_warnings(evidence)
        for company in self.registry.resolve(state["question"]):
            if company.warning:
                warnings.append(company.warning)
        answer, invalid_citations = remove_unmapped_citations(state["answer"], len(evidence))
        if invalid_citations:
            warnings.append(
                "Removed citation markers without matching sources: "
                + ", ".join(f"[{number}]" for number in dict.fromkeys(invalid_citations))
                + "."
            )
        cited = bool(re.search(r"\[\d+\]", answer)) or not evidence
        if evidence and not cited:
            warnings.append("The generated answer did not include inline citation markers.")
        return {
            "result": ResearchResult(
                answer,
                evidence,
                warnings,
                bool(state.get("attempts")),
                "high" if cited and evidence_sufficient(evidence) else "medium" if evidence else "low",
            )
        }
