from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class HealthResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"status": "ok"}]})

    status: Literal["ok"]


class ReadyResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"status": "ready"}]})

    status: Literal["ready"]


class QueryRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"examples": [{"question": "Compare the reported sustainability KPIs for 2024."}]}
    )
    question: str = Field(min_length=1, max_length=2000)


class QueryAccepted(BaseModel):
    request_id: str
    status: str = "received"


class Source(BaseModel):
    citation_number: int = Field(ge=1)
    title: str
    url: HttpUrl
    company: str | None = None
    reporting_year: int | None = None
    pdf_page: int | None = None
    printed_page: str | None = None
    snippet: str


class QueryResult(BaseModel):
    request_id: str
    answer: str
    sources: list[Source]
    warnings: list[str]
    used_live_web: bool
    confidence: Literal["low", "medium", "high"]


class StatusResponse(BaseModel):
    request_id: str
    stage: str
    created_at: datetime
    updated_at: datetime
    error: str | None = None
