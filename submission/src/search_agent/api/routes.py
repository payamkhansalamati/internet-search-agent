import logging
from typing import cast
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status
from pydantic import HttpUrl

from search_agent.api.schemas import (
    HealthResponse,
    QueryAccepted,
    QueryRequest,
    QueryResult,
    ReadyResponse,
    Source,
    StatusResponse,
)
from search_agent.api.status import RequestRecord
from search_agent.citations import evidence_snippet, page_url
from search_agent.domain import Evidence

router = APIRouter()
log = logging.getLogger(__name__)


def build_sources(evidence: list[Evidence]) -> list[Source]:
    return [
        Source(
            citation_number=number,
            title=item.title,
            url=cast(HttpUrl, page_url(item.url, item.pdf_page)),
            company=item.company,
            reporting_year=item.year,
            pdf_page=item.pdf_page,
            printed_page=item.printed_page,
            snippet=evidence_snippet(item),
        )
        for number, item in enumerate(evidence, 1)
    ]


@router.get("/health", response_model=HealthResponse)
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready", response_model=ReadyResponse)
async def ready(request: Request) -> dict[str, str]:
    if not hasattr(request.app.state, "graph"):
        raise HTTPException(status_code=503, detail="Service is not ready")
    return {"status": "ready"}


async def run_query(app: object, request_id: str, question: str) -> None:
    store, graph = app.state.store, app.state.graph  # type: ignore[attr-defined]

    async def update(stage: str) -> None:
        store.update(request_id, stage)

    try:
        graph = app.state.graph_factory(update)  # type: ignore[attr-defined]
        output = await graph.ainvoke({"question": question})
        result = output["result"]
        payload = QueryResult(
            request_id=request_id,
            answer=result.answer,
            sources=build_sources(result.sources),
            warnings=result.warnings,
            used_live_web=result.used_live_web,
            confidence=result.confidence,
        )
        store.update(request_id, "completed", result=payload)
    except Exception as exc:
        log.exception("Query %s failed", request_id)
        store.update(request_id, "failed", error=str(exc))


@router.post("/api/v1/query", response_model=QueryAccepted, status_code=status.HTTP_202_ACCEPTED)
async def submit(payload: QueryRequest, request: Request, tasks: BackgroundTasks) -> QueryAccepted:
    request_id = str(uuid4())
    request.app.state.store.create(request_id)
    tasks.add_task(run_query, request.app, request_id, payload.question)
    return QueryAccepted(request_id=request_id)


def record_or_404(request: Request, request_id: str) -> RequestRecord:
    record = request.app.state.store.get(request_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Request not found")
    return cast(RequestRecord, record)


@router.get("/api/v1/status/{request_id}", response_model=StatusResponse)
async def request_status(request_id: str, request: Request) -> StatusResponse:
    item = record_or_404(request, request_id)
    return StatusResponse(
        request_id=request_id,
        stage=item.stage,
        created_at=item.created_at,
        updated_at=item.updated_at,
        error=item.error,
    )


@router.get("/api/v1/requests/{request_id}", response_model=QueryResult)
async def request_result(request_id: str, request: Request) -> QueryResult:
    item = record_or_404(request, request_id)
    if item.stage == "failed":
        raise HTTPException(status_code=500, detail=item.error or "Request failed")
    if item.stage != "completed":
        raise HTTPException(status_code=409, detail=f"Request is {item.stage}")
    return cast(QueryResult, item.result)
