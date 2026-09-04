import hashlib
import json
import re
import threading
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

from llama_index.core import StorageContext, VectorStoreIndex, load_index_from_storage
from llama_index.core.embeddings import BaseEmbedding
from llama_index.core.schema import BaseNode, MetadataMode, TextNode
from llama_index.core.vector_stores import ExactMatchFilter, MetadataFilter, MetadataFilters

from search_agent.domain import Evidence
from search_agent.glossary import SustainabilityGlossary

EmbedFactory = Callable[[], BaseEmbedding]
TOKEN = re.compile(r"[a-z0-9%]+", re.I)


class RetrievalService:
    """Persistent LlamaIndex vector retrieval combined with exact-term ranking."""

    def __init__(
        self,
        path: Path,
        *,
        embedding_model: str = "BAAI/bge-small-en-v1.5",
        embedding_provider: str = "fastembed",
        embed_model: BaseEmbedding | None = None,
        embed_factory: EmbedFactory | None = None,
        semantic_weight: float = 0.7,
        allow_lexical_fallback: bool = True,
        glossary: SustainabilityGlossary | None = None,
    ) -> None:
        self.path = path
        self.manifest_file = path / "index-manifest.json"
        self.embedding_model = embedding_model
        self.embedding_provider = embedding_provider
        self._embed_model = embed_model
        self._embed_factory = embed_factory
        self.semantic_weight = semantic_weight
        self.allow_lexical_fallback = allow_lexical_fallback
        self.glossary = glossary or SustainabilityGlossary.load_default()
        self._index: VectorStoreIndex | None = None
        self._lock = threading.RLock()

    def add(
        self,
        evidence: list[Evidence],
        *,
        document_id: str | None = None,
        checksum: str | None = None,
    ) -> bool:
        if not evidence:
            return False
        document_id = document_id or evidence[0].document_id or evidence[0].url
        checksum = checksum or hashlib.sha256("\n".join(item.text for item in evidence).encode()).hexdigest()
        with self._lock:
            manifest = self._manifest()
            existing = manifest.get(document_id)
            if existing and existing["checksum"] == checksum:
                return False
            index = self._ensure_index()
            if existing:
                index.delete_nodes(existing["node_ids"], delete_from_docstore=True)
            nodes = [self._node(item, document_id, checksum, offset) for offset, item in enumerate(evidence)]
            index.insert_nodes(nodes)
            manifest[document_id] = {"checksum": checksum, "node_ids": [node.node_id for node in nodes]}
            self._persist(index, manifest)
            return True

    async def retrieve(
        self,
        query: str,
        limit: int = 6,
        *,
        companies: list[str] | None = None,
        year: int | None = None,
    ) -> list[Evidence]:
        with self._lock:
            if not self._has_index():
                return []
            index = self._ensure_index()
            scopes: list[str | None] = list(companies) if companies else [None]
            per_scope = max(1, limit // len(scopes)) if len(scopes) > 1 else limit
            groups = [self._retrieve_scope(index, query, per_scope, company, year) for company in scopes]
            return _balanced_merge(groups, limit)

    def _retrieve_scope(
        self,
        index: VectorStoreIndex,
        query: str,
        limit: int,
        company: str | None,
        year: int | None,
    ) -> list[Evidence]:
        queries = [query, *self.glossary.expand_query(query)]
        groups = [self._retrieve_query(index, item, limit, company, year) for item in queries]
        return _balanced_merge(groups, limit)

    def _retrieve_query(
        self,
        index: VectorStoreIndex,
        query: str,
        limit: int,
        company: str | None,
        year: int | None,
    ) -> list[Evidence]:
        filters = _metadata_filters(company, year)
        semantic: list[tuple[BaseNode, float]] = []
        try:
            retriever = index.as_retriever(similarity_top_k=max(limit * 3, 8), filters=filters)
            semantic = [(item.node, float(item.score or 0)) for item in retriever.retrieve(query)]
        except Exception:
            if not self.allow_lexical_fallback:
                raise
        lexical = self._lexical(index, query, company, year)
        return self._hybrid(query, semantic, lexical, limit)

    def _lexical(
        self,
        index: VectorStoreIndex,
        query: str,
        company: str | None,
        year: int | None,
    ) -> list[tuple[BaseNode, float]]:
        query_terms = set(TOKEN.findall(query.casefold()))
        ranked: list[tuple[BaseNode, float]] = []
        for node in index.docstore.docs.values():
            metadata = node.metadata
            if company and metadata.get("company") != company:
                continue
            if year is not None and metadata.get("reporting_year") != year:
                continue
            terms = set(TOKEN.findall(node.get_content().casefold()))
            exact = len(query_terms & terms) / max(1, len(query_terms))
            phrase = 1.0 if query.casefold() in node.get_content().casefold() else 0.0
            if exact:
                ranked.append((node, min(1.0, exact + phrase * 0.25)))
        return sorted(ranked, key=lambda item: item[1], reverse=True)

    def _hybrid(
        self,
        query: str,
        semantic: list[tuple[BaseNode, float]],
        lexical: list[tuple[BaseNode, float]],
        limit: int,
    ) -> list[Evidence]:
        scores: dict[str, float] = {}
        nodes: dict[str, BaseNode] = {}
        for node, score in semantic:
            nodes[node.node_id] = node
            scores[node.node_id] = scores.get(node.node_id, 0) + self.semantic_weight * max(0.0, score)
        for node, score in lexical:
            nodes[node.node_id] = node
            scores[node.node_id] = scores.get(node.node_id, 0) + (1 - self.semantic_weight) * score
        for node_id, node in nodes.items():
            metadata = node.metadata
            kind = str(metadata.get("table_metadata", ""))
            units = metadata.get("units", [])
            text = node.get_content(metadata_mode=MetadataMode.NONE)
            quality = 0.0
            if '"kind": "table"' in kind:
                quality += 0.3
            if units:
                quality += 0.2
            if re.search(r"\d[\d,.]*\s*%?|[<>]\s*\d", text):
                quality += 0.1
            quality += self.glossary.row_bonus(query, text)
            scores[node_id] = scores.get(node_id, 0.0) + quality
        ranked = sorted(scores, key=scores.get, reverse=True)[:limit]  # type: ignore[arg-type]
        return [self._evidence(nodes[node_id], scores[node_id]) for node_id in ranked]

    def _ensure_index(self) -> VectorStoreIndex:
        if self._index is not None:
            return self._index
        embed_model = self._embedding()
        if (self.path / "docstore.json").exists():
            context = StorageContext.from_defaults(persist_dir=str(self.path))
            self._index = cast(VectorStoreIndex, load_index_from_storage(context, embed_model=embed_model))
        else:
            self._index = VectorStoreIndex([], embed_model=embed_model)
        return self._index

    def _embedding(self) -> BaseEmbedding:
        if self._embed_model is None:
            if self._embed_factory:
                self._embed_model = self._embed_factory()
            elif self.embedding_provider == "fastembed":
                from llama_index.embeddings.fastembed import FastEmbedEmbedding

                self._embed_model = FastEmbedEmbedding(model_name=self.embedding_model)
            else:
                from llama_index.embeddings.huggingface import HuggingFaceEmbedding

                self._embed_model = HuggingFaceEmbedding(model_name=self.embedding_model)
        return self._embed_model

    def _node(self, item: Evidence, document_id: str, checksum: str, offset: int) -> TextNode:
        metadata: dict[str, Any] = {
            "title": item.title,
            "source_url": item.url,
            "company": item.company or "",
            "reporting_year": item.year or 0,
            "section": item.section or "",
            "pdf_page": item.pdf_page if item.pdf_page is not None else 0,
            "pdf_pages": list(item.pdf_pages),
            "printed_page": item.printed_page or "",
            "units": list(item.units),
            "table_metadata": json.dumps(item.table_metadata) if item.table_metadata else "",
            "extraction_confidence": item.extraction_confidence if item.extraction_confidence is not None else -1.0,
            "document_id": document_id,
            "checksum": checksum,
        }
        return TextNode(text=item.text, metadata=metadata, id_=f"{document_id}:{checksum[:12]}:{offset}")

    def _evidence(self, node: BaseNode, score: float) -> Evidence:
        metadata = node.metadata
        pages = tuple(int(page) for page in metadata.get("pdf_pages", metadata.get("page_numbers", [])))
        pdf_page = int(metadata.get("pdf_page", 0)) or (pages[0] if pages else None)
        raw_table = metadata.get("table_metadata")
        return Evidence(
            text=node.get_content(metadata_mode=MetadataMode.NONE),
            title=str(metadata.get("title", "Untitled")),
            url=str(metadata.get("source_url", "")),
            company=str(metadata["company"]) or None,
            year=int(metadata["reporting_year"]) or None,
            pdf_page=pdf_page,
            section=str(metadata["section"]) or None,
            score=score,
            document_id=str(metadata["document_id"]),
            pdf_pages=pages,
            printed_page=str(metadata.get("printed_page", "")) or None,
            units=tuple(str(unit) for unit in metadata.get("units", [])),
            table_metadata=json.loads(raw_table) if raw_table else None,
            extraction_confidence=(
                float(metadata["extraction_confidence"]) if float(metadata["extraction_confidence"]) >= 0 else None
            ),
        )

    def _persist(self, index: VectorStoreIndex, manifest: dict[str, dict[str, Any]]) -> None:
        self.path.mkdir(parents=True, exist_ok=True)
        index.storage_context.persist(persist_dir=str(self.path))
        self.manifest_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    def _manifest(self) -> dict[str, dict[str, Any]]:
        return json.loads(self.manifest_file.read_text()) if self.manifest_file.exists() else {}

    def _has_index(self) -> bool:
        return self._index is not None or (self.path / "docstore.json").exists()


def _metadata_filters(company: str | None, year: int | None) -> MetadataFilters | None:
    filters: list[MetadataFilter | MetadataFilters] = []
    if company:
        filters.append(ExactMatchFilter(key="company", value=company))
    if year is not None:
        filters.append(ExactMatchFilter(key="reporting_year", value=year))
    return MetadataFilters(filters=filters) if filters else None


def _balanced_merge(groups: list[list[Evidence]], limit: int) -> list[Evidence]:
    result: list[Evidence] = []
    seen: set[str] = set()
    for position in range(max((len(group) for group in groups), default=0)):
        for group in groups:
            if position >= len(group):
                continue
            item = group[position]
            key = f"{item.document_id}:{hashlib.sha1(item.text.encode()).hexdigest()}"
            if key not in seen:
                result.append(replace(item, score=item.score or 0.0))
                seen.add(key)
            if len(result) == limit:
                return result
    return result
