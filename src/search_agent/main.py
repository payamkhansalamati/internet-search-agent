import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from search_agent.api.routes import router
from search_agent.api.status import StatusStore
from search_agent.companies import CompanyRegistry
from search_agent.glossary import SustainabilityGlossary
from search_agent.graph.nodes import Nodes, StatusCallback
from search_agent.graph.workflow import build_graph
from search_agent.ingestion.pipeline import IngestionPipeline
from search_agent.llm.providers import build_llm
from search_agent.retrieval.service import RetrievalService
from search_agent.search.duckduckgo import DuckDuckGoSearch
from search_agent.settings import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logging.basicConfig(level=settings.log_level)
        registry = CompanyRegistry.load(settings.companies_path)
        glossary = SustainabilityGlossary.load(settings.glossary_path)
        retrieval = RetrievalService(
            settings.index_path,
            embedding_model=settings.embedding_model,
            embedding_provider=settings.embedding_provider,
            semantic_weight=settings.semantic_weight,
            allow_lexical_fallback=settings.parsing_fallback_enabled,
            glossary=glossary,
        )
        search, llm = DuckDuckGoSearch(), build_llm(settings, glossary)
        ingestion = IngestionPipeline(
            settings,
            registry,
            retrieval,
        )
        app.state.store = StatusStore()

        def factory(callback: StatusCallback) -> Any:
            return build_graph(
                Nodes(
                    registry,
                    retrieval,
                    search,
                    llm,
                    callback,
                    settings.search_max_results,
                    settings.retrieval_top_k,
                    ingestion=ingestion,
                )
            )

        async def noop(_: str) -> None:
            pass

        app.state.graph_factory = factory
        app.state.graph = factory(noop)
        yield

    app = FastAPI(title="Internet Search Agent", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    app.include_router(router)
    return app


app = create_app()
