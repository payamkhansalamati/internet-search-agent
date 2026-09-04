import hashlib
import json
from pathlib import Path
from typing import Any

import httpx

from search_agent.companies import CompanyRegistry
from search_agent.glossary import GlossaryStore, discover_candidates
from search_agent.ingestion.documents import Report
from search_agent.ingestion.parsing import DocumentParser, chunk_pages
from search_agent.retrieval.service import RetrievalService
from search_agent.search.validation import validate_url
from search_agent.settings import Settings

INGESTION_VERSION = 5


class IngestionPipeline:
    def __init__(
        self,
        settings: Settings,
        registry: CompanyRegistry,
        retrieval: RetrievalService,
        parser: DocumentParser | None = None,
    ) -> None:
        self.settings, self.registry, self.retrieval = settings, registry, retrieval
        self.glossary_store = GlossaryStore(
            settings.glossary_path, settings.glossary_review_path, settings.glossary_history_path
        )
        self.glossary = self.glossary_store.load()
        self.parser = parser or DocumentParser(
            use_ocr=settings.docling_ocr,
            table_mode=settings.docling_table_mode,
            allow_fallback=settings.parsing_fallback_enabled,
            glossary=self.glossary,
        )

    async def ingest(self, report: Report) -> bool:
        validate_url(report.url, self.registry.approved_domains())
        manifest = self._manifest()
        async with httpx.AsyncClient(timeout=self.settings.http_timeout_seconds, follow_redirects=False) as client:
            response = await client.get(report.url, headers={"Accept": "application/pdf"})
            if 300 <= response.status_code < 400:
                # Re-validate destination before following; reject chains of more than one hop.
                location = response.headers.get("location", "")
                validate_url(location, self.registry.approved_domains())
                response = await client.get(location, headers={"Accept": "application/pdf"})
            response.raise_for_status()
            if 300 <= response.status_code < 400:
                raise ValueError("Redirect chain longer than one hop is not allowed")
        if "application/pdf" not in response.headers.get("content-type", "").casefold():
            raise ValueError("Expected a PDF response")
        if len(response.content) > self.settings.max_document_bytes:
            raise ValueError("Document exceeds maximum size")
        checksum = hashlib.sha256(response.content).hexdigest()
        if checksum in manifest and manifest[checksum].get("ingestion_version") == INGESTION_VERSION:
            return False
        identity = f"{report.company}:{report.year}:{report.url}"
        document_id = hashlib.sha256(identity.encode()).hexdigest()
        parsed = self.parser.parse(response.content, report, document_id)
        self.glossary_store.queue(discover_candidates(parsed, self.glossary))
        evidence = chunk_pages(parsed, glossary=self.glossary)
        index_checksum = hashlib.sha256(f"{checksum}:ingestion-v{INGESTION_VERSION}".encode()).hexdigest()
        changed = self.retrieval.add(evidence, document_id=document_id, checksum=index_checksum)
        if not changed:
            return False
        previous = [key for key, value in manifest.items() if value.get("document_id") == document_id]
        for key in previous:
            manifest.pop(key)
        manifest[checksum] = {
            "document_id": document_id,
            "url": report.url,
            "company": report.company,
            "year": report.year,
            "ingestion_version": INGESTION_VERSION,
        }
        self.settings.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.settings.manifest_path.write_text(json.dumps(manifest, indent=2))
        return True

    def _manifest(self) -> dict[str, dict[str, Any]]:
        path: Path = self.settings.manifest_path
        return json.loads(path.read_text()) if path.exists() else {}
