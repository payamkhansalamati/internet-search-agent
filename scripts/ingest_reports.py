import argparse
import asyncio

from search_agent.companies import CompanyRegistry
from search_agent.ingestion.documents import Report
from search_agent.ingestion.pipeline import IngestionPipeline
from search_agent.retrieval.service import RetrievalService
from search_agent.settings import get_settings


async def main() -> None:
    parser = argparse.ArgumentParser()
    for name in ("company", "year", "title", "url"):
        parser.add_argument(f"--{name}", required=True)
    args = parser.parse_args()
    settings = get_settings()
    pipeline = IngestionPipeline(
        settings,
        CompanyRegistry.load(settings.companies_path),
        RetrievalService(
            settings.index_path,
            embedding_model=settings.embedding_model,
            embedding_provider=settings.embedding_provider,
            semantic_weight=settings.semantic_weight,
            allow_lexical_fallback=settings.parsing_fallback_enabled,
        ),
    )
    changed = await pipeline.ingest(Report(args.company, int(args.year), args.title, args.url))
    print("ingested" if changed else "already indexed")


if __name__ == "__main__":
    asyncio.run(main())
