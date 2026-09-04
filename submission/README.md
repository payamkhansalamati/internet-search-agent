# Evidence-Grounded Sustainability Research Agent

This submission is a self-contained delivery copy of an evidence-grounded research application for sustainability
reports. It combines deterministic PDF ingestion, a persistent LlamaIndex store, hybrid semantic/lexical retrieval,
a bounded LangGraph workflow, evidence-only synthesis, page-linked citations, a FastAPI API, and a Streamlit UI.

No source reports, secrets, local virtual environments, or machine-specific paths are included. The persistent
demonstration index is not included; see **Index status** below.

## 1. Purpose and architecture

The application supports questions and comparisons across configured companies while retaining company, report
year, unit, section, physical PDF page, printed page label, document identity, URL, and evidence snippets.

Runtime query flow:

1. Classify a greeting versus a research question.
2. Resolve configured company aliases.
3. Retrieve indexed evidence first.
4. Search DuckDuckGo for freshness requests or insufficient local evidence.
5. Validate any official PDF candidate returned by search, then ingest it automatically when it is missing or newer than the current indexed report.
6. Re-retrieve the updated corpus and answer from the refreshed evidence.
7. Validate inline citation numbering and return numbered, page-linked sources.

Offline ingestion validates an approved HTTPS host and public DNS result, performs a bounded PDF download,
deduplicates by SHA-256, extracts layout/tables/text with Docling and PyPDF, preserves page metadata, normalizes
approved glossary units, creates chunks, persists the LlamaIndex store, and updates the manifest only after
successful persistence.

## 2. Prerequisites

- Python **3.12** (the package requires `>=3.12,<3.13`)
- `uv` is recommended for the locked installation; `pip` is supported
- Internet access for the first dependency/model download and for report ingestion
- An OpenAI API key **or** a running Ollama service for real research synthesis
- Sufficient memory and disk for Docling, embedding models, and indexed reports

## 3. Clean installation

From this `submission/` directory:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev,ui,mcp]"
```

For an exact locked environment, install `uv` and use:

```bash
uv sync --frozen --all-extras
```

The committed `uv.lock` is the reproducible dependency lock. Generated `*.egg-info` files must not be edited.

## 4. Configuration

```bash
cp .env.example .env
```

Important settings:

| Variable | Purpose |
|---|---|
| `LLM_PROVIDER` | `openai` or `ollama` |
| `OPENAI_API_KEY` | OpenAI credential; leave empty when using Ollama |
| `OPENAI_MODEL` | OpenAI model name; default `gpt-4.1-mini` |
| `OLLAMA_BASE_URL` / `OLLAMA_MODEL` | Local Ollama endpoint and model |
| `INDEX_PATH` / `MANIFEST_PATH` | Portable relative persistence paths |
| `EMBEDDING_PROVIDER` / `EMBEDDING_MODEL` | FastEmbed or Hugging Face embedding configuration |
| `RETRIEVAL_TOP_K` / `SEMANTIC_WEIGHT` | Retrieval breadth and semantic/lexical weighting |
| `COMPANIES_PATH` | Company aliases and official-domain allowlist |
| `GLOSSARY_PATH` | Approved sustainability vocabulary and unit rules |
| `GLOSSARY_REVIEW_PATH` / `GLOSSARY_HISTORY_PATH` | Candidate review queue and version history |

The included `.env.example` contains placeholders only. Never commit `.env` or real credentials.

## 5. LLM provider options

### OpenAI

```bash
export LLM_PROVIDER=openai
export OPENAI_API_KEY="your-key-here"
export OPENAI_MODEL=gpt-4.1-mini
```

### Ollama / Llama 3.1

```bash
ollama serve
ollama pull llama3.1
export LLM_PROVIDER=ollama
export OLLAMA_BASE_URL=http://localhost:11434
export OLLAMA_MODEL=llama3.1
```

OpenAI is the default managed provider. Ollama keeps prompts local but requires adequate local hardware and may have
different citation quality.

## 6. Index status

**Status: regeneration required.** No index or copyrighted source PDF is included.

The original full index consisted of six interdependent LlamaIndex files totaling **59,413,611 bytes**, excluding
the separate 737-byte ingestion manifest. It exceeded the 50 MB submission limit and contained extracted report
content. There was no safe, independently valid file subset: removing any monolithic store component would corrupt
loading, and repackaging selected copyrighted report text was not assumed to be permitted.

The application creates `data/index/` and `data/manifest.json` during ingestion. Always run commands from the
submission root so the relative paths resolve correctly.

## 7. Optional admin fallback: ingest reports manually

The normal system flow is automatic: retrieve, detect missing or stale official report coverage, validate the PDF, ingest it if needed, then re-retrieve and answer. The commands below are an optional administrative fallback for one-off reindexing or repairs; they are not the standard user-facing workflow.

The company and report host must be present in `config/companies.yaml`. URLs containing `&` must be shell-quoted.

ABB 2024:

```bash
python scripts/ingest_reports.py \
  --company ABB \
  --year 2024 \
  --title "Sustainability Statement 2024" \
  --url 'https://search.abb.com/library/Download.aspx?Action=Launch&DocumentID=9AKK108470A7211&DocumentPartId=&LanguageCode=en'
```

Siemens 2024:

```bash
python scripts/ingest_reports.py \
  --company Siemens \
  --year 2024 \
  --title "Sustainability report 2024" \
  --url 'https://assets.new.siemens.com/siemens/assets/api/uuid:cf240c4d-2e09-42ee-9ed8-752a47ab924f/sustainability-report-2024.pdf'
```

Expected output is `ingested`; repeating an unchanged report prints `already indexed`. New glossary candidates are
written to `config/glossary-review-queue.json` and are never auto-approved. Validate or review the glossary with:

```bash
python scripts/manage_glossary.py validate
```

Only ingest documents you are authorized to download and process. This submission does not grant redistribution
rights for third-party reports.

## 8. Start the FastAPI service

```bash
uvicorn search_agent.main:app --host 127.0.0.1 --port 8000
```

Development reload:

```bash
uvicorn search_agent.main:app --reload
```

Interactive API documentation is available at <http://localhost:8000/docs> and the OpenAPI schema at
<http://localhost:8000/openapi.json>.

## 9. API endpoints

| Method and path | Behavior |
|---|---|
| `GET /health` | Process health: `{"status":"ok"}` |
| `GET /ready` | Confirms application dependencies were constructed |
| `POST /api/v1/query` | Validates a question and returns HTTP 202 with a request UUID |
| `GET /api/v1/status/{request_id}` | Returns current workflow stage and any error |
| `GET /api/v1/requests/{request_id}` | Returns completed answer, sources, warnings and confidence |

Unknown IDs return 404, unfinished results return 409, invalid requests return 422, and failed work returns 500.

## 10. API examples

Health:

```bash
curl -s http://localhost:8000/health
```

Submit a query:

```bash
curl -s -X POST http://localhost:8000/api/v1/query \
  -H 'content-type: application/json' \
  -d '{"question":"Compare ABB and Siemens Scope 2 emissions in 2024."}'
```

Use the returned UUID:

```bash
curl -s http://localhost:8000/api/v1/status/REQUEST_ID
curl -s http://localhost:8000/api/v1/requests/REQUEST_ID
```

Workflow stages may include `received`, `classifying`, `retrieving`, `searching`, `synthesizing`, `validating`,
`completed`, and `failed`; routes can skip stages.

## 11. Streamlit UI

In a second activated shell:

```bash
export API_BASE_URL=http://localhost:8000
streamlit run frontend/app.py
```

Open <http://localhost:8501>. The UI submits a question, polls status, displays the answer, and renders numbered
sources with company, year, evidence snippet, and physical/printed page labels.

## 12. Expected results and citations

With ABB and Siemens indexed, a comparison should return a table or structured answer based on retrieved evidence.
Every retained inline marker `[n]` maps to source entry `n`. Sources are deduplicated by document and physical PDF
page and include a link ending in `#page=<physical-page>`. The UI displays `report p. X · PDF p. Y` when printed and
physical pages differ, `p. X` when they match, and `PDF p. Y` when no printed label is available.

The system must not infer missing values or unsupported methodology differences. Exact wording varies by model, so
tests assert deterministic retrieval and citation contracts rather than a fixed generated narrative.

## 13. Tests and verification

```bash
pytest -q
ruff check .
ruff format --check src tests scripts frontend
mypy src
python scripts/evaluate_agent.py
python scripts/manage_glossary.py validate
python scripts/verify_submission.py
```

`verify_submission.py` creates a temporary, synthetic index outside the project data paths and exercises health,
readiness, asynchronous query submission, indexed retrieval, evidence-based synthesis, citation numbering,
`#page=` linking, snippets, and physical/printed page metadata through the actual API. It requires no API key and
does not represent a production answer benchmark.

## 14. Known limitations and troubleshooting

- **No index:** run the ingestion commands above before research queries. Greetings work without an index.
- **`OPENAI_API_KEY is required`:** configure OpenAI or switch to a running Ollama service.
- **First retrieval is slow:** the embedding model may be downloaded and initialized on first use.
- **Docling extraction:** scans, charts, irregular layouts and multi-page tables can still be misread; review cited pages.
- **DuckDuckGo:** availability, ranking and completeness are not guaranteed; runtime snippets are transient.
- **Comparability:** years, units, organizational boundaries and methodologies may differ; warnings do not replace expert review.
- **Local persistence:** the included implementation is appropriate for one process, not concurrent distributed writers.
- **Status storage:** request state is in memory and is not shared across API replicas.
- **Citation validation:** numbering is validated, but claim-level entailment is a production recommendation.
- **Intel macOS:** Docling is pinned because newer parser wheels are unavailable for the supported Intel toolchain.

The package explicitly pins the compatible Docling core range and includes the FastEmbed runtime selected by the
default embedding configuration; do not remove these direct dependencies when updating the lock file.

For production, the documented design direction is Azure Container Apps with Redis request state, Service Bus or
Container Apps Jobs, Blob Storage, Azure AI Search or PostgreSQL/pgvector, Key Vault, private networking, WAF/API
Management, Application Insights, backups, autoscaling and controlled revisions. Those cloud resources are proposed,
not provisioned by this submission.
