# Submission manifest

Every included item is listed below. Paths are relative to the submission root.

## Root installation and runtime files

| Item | Why it is required |
|---|---|
| `.dockerignore` | Keeps local environments, caches, secrets and data out of container build contexts. |
| `.env.example` | Placeholder-only portable runtime configuration template. |
| `Dockerfile` | Reproducible container build for the FastAPI service and optional UI image. |
| `docker-compose.yml` | Local API, Streamlit and optional Ollama orchestration. |
| `pyproject.toml` | Package metadata, supported Python version, dependencies and tool configuration. |
| `uv.lock` | Exact reproducible dependency resolution. |
| `README.md` | Complete clean-environment installation, configuration, ingestion, API, UI, testing and troubleshooting guide. |
| `MANIFEST.md` | Exhaustive delivery inventory and rationale. |
| `SUBMISSION_REPORT.md` | Packaging decisions, exclusions, index measurements and verification evidence. |

## Runtime configuration and glossary

| Item | Why it is required |
|---|---|
| `config/companies.yaml` | Company aliases, official host allowlists and reporting-entity warnings. |
| `config/sustainability_glossary.yaml` | Approved canonical KPI concepts, aliases, units, qualifiers, relationships and provenance. |
| `config/glossary-review-queue.json` | Valid empty/pending candidate queue required by ingestion governance. |
| `config/glossary-history/.gitkeep` | Preserves the portable history destination used by approved glossary updates and rollback. |

## Production package

| Item | Why it is required |
|---|---|
| `src/search_agent/__init__.py` | Declares the Python package. |
| `src/search_agent/main.py` | FastAPI application factory and ASGI entry point. |
| `src/search_agent/settings.py` | Typed environment and path configuration. |
| `src/search_agent/domain.py` | Evidence and research-result domain models. |
| `src/search_agent/companies.py` | Company registry and alias/domain resolution. |
| `src/search_agent/glossary.py` | Glossary schema, loading, normalization, discovery, approval, versioning and rollback. |
| `src/search_agent/citations.py` | Citation deduplication, numbering, snippets, page links and display labels. |
| `src/search_agent/page_labels.py` | PDF metadata/header/footer printed-page resolution. |
| `src/search_agent/api/routes.py` | Health, readiness, submission, status and result routes. |
| `src/search_agent/api/schemas.py` | Explicit Pydantic request and response schemas. |
| `src/search_agent/api/status.py` | In-memory request lifecycle store. |
| `src/search_agent/graph/state.py` | Typed LangGraph state. |
| `src/search_agent/graph/nodes.py` | Classification, retrieval, conditional search, synthesis and validation nodes. |
| `src/search_agent/graph/workflow.py` | Bounded LangGraph topology and routing. |
| `src/search_agent/ingestion/documents.py` | Report ingestion descriptor. |
| `src/search_agent/ingestion/parsing.py` | Docling/PyPDF extraction, table handling, metadata and chunking. |
| `src/search_agent/ingestion/pipeline.py` | Secure download, checksum deduplication, indexing and manifest lifecycle. |
| `src/search_agent/retrieval/service.py` | Persistent LlamaIndex, hybrid retrieval, filtering, balancing and reranking. |
| `src/search_agent/search/base.py` | Search-provider protocol used for dependency boundaries and tests. |
| `src/search_agent/search/duckduckgo.py` | Runtime DuckDuckGo provider. |
| `src/search_agent/search/validation.py` | HTTPS, domain, credential and public-DNS validation. |
| `src/search_agent/llm/base.py` | LLM-provider protocol. |
| `src/search_agent/llm/providers.py` | OpenAI/Ollama providers, grounded prompt and evidence context. |
| `src/search_agent/mcp/server.py` | Optional documented MCP server entry point and tools. |

## User interface

| Item | Why it is required |
|---|---|
| `frontend/app.py` | Streamlit chat client, status polling and citation/source rendering. |

## Operational scripts

| Item | Why it is required |
|---|---|
| `scripts/ingest_reports.py` | Supported CLI for report download, extraction and indexing. |
| `scripts/manage_glossary.py` | Glossary validation, candidate approval/rejection and rollback CLI. |
| `scripts/evaluate_agent.py` | Loads the included deterministic evaluation scenario inventory. |
| `scripts/verify_submission.py` | Self-contained API/retrieval/synthesis/citation/page-metadata smoke verification. |

## Evaluation data

| Item | Why it is required |
|---|---|
| `evaluation/cases.json` | Five documented evaluation categories without fabricated scores. |

## Essential tests

| Item | Why it is required |
|---|---|
| `tests/test_core.py` | Company resolution, conversation routing, URL security and comparability tests. |
| `tests/test_integration.py` | API, health/readiness, status and OpenAPI integration test. |
| `tests/test_retrieval.py` | Persistence, replacement, filtering, balanced retrieval and lexical fallback tests. |
| `tests/test_parsing.py` | Parser fallback, row-safe table chunking and glossary unit normalization tests. |
| `tests/test_page_labels.py` | Equal, offset, Roman, missing and non-numeric printed-page tests. |
| `tests/test_citations.py` | Numbering, deduplication, snippets, page links and label rendering tests. |
| `tests/test_glossary.py` | Schema, conflicts, evidence-supported discovery, approval, rollback and isolation tests. |
| `tests/test_kpi_regression.py` | ABB–Siemens KPI retrieval regression contract. |
| `tests/fixtures/abb_siemens_2024_kpis.json` | Test-only expected values and page metadata; production code is prohibited from importing it. |

No other files are required by this delivery copy.
