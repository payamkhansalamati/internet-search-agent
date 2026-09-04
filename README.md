# Internet Search Agent

An evidence-grounded research service for sustainability reports from ten industrial organizations. It combines a deterministic report-ingestion path with a bounded LangGraph query workflow, a FastAPI API, and a small Streamlit client.

## Architecture and behavior

The graph classifies greetings away from research, resolves configured company aliases, retrieves indexed evidence, searches with `ddgs` when evidence is insufficient or freshness is requested, then synthesizes and checks citations. Search is behind an interface; OpenAI is the default model and Ollama/Llama 3.1 is the local option. PDF pages and report metadata survive chunking. Report hosts must match configured official domains.

Docling is the primary PDF parser, with OCR, layout, headings, captions, and table structure enabled. It emits page-aware blocks and Markdown tables; table fragments remain page-local so KPI rows retain their physical PDF page. PyPDF remains a configurable fallback for documents Docling cannot process.

LlamaIndex owns the persistent local vector index. It loads existing storage instead of rebuilding per request, replaces changed documents by stable document ID and checksum, and supports company/year metadata filters. Retrieval combines embedding similarity with exact-term lexical matches. Comparisons query each company independently and interleave the ranked groups so a long report cannot crowd out another company.

## Install and configure

Requires Python 3.12.

```bash
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev,ui,mcp]"
cp .env.example .env
```

Set `OPENAI_API_KEY`, or set `LLM_PROVIDER=ollama`, run `ollama serve`, and pull `llama3.1`. Never put secrets in source control.

The committed `uv.lock` is the reproducible dependency source for local and
container builds. Install exactly the locked development environment with:

```bash
uv sync --frozen --all-extras
```

Upgrade dependencies deliberately with `uv lock --upgrade`, then run the
quality checks below before committing both `pyproject.toml` and `uv.lock`.
Generated `*.egg-info` metadata is ignored and must not be edited manually.

## Run

```bash
uvicorn search_agent.main:app --reload
streamlit run frontend/app.py
python scripts/ingest_reports.py --company Siemens --year 2024 --title "Sustainability report" --url https://siemens.com/path/report.pdf
python -m search_agent.mcp.server
```

API documentation is at `http://localhost:8000/docs`. Docker users can run `docker compose up api`; UI and Ollama use the `ui` and `ollama` profiles. Example questions include “What is Siemens’ latest emissions target?” and “Compare ABB and BMW Group Scope 1 emissions.”

## Quality checks

```bash
pytest
ruff check .
mypy src
python scripts/evaluate_agent.py
```

## Limitations

DuckDuckGo result availability and ranking are not guaranteed. Docling can still misread scans, irregular layouts, and multi-page tables; extraction confidence and every contributing page are retained for review. The PyPDF fallback extracts text only. The local vector store is suitable for one process and does not provide distributed writes. Search snippets are not a substitute for ingested primary reports, and cross-company metrics may differ in boundaries, methods, units, and years.

See [architecture](docs/architecture.md), [API](docs/api.md), [approach](docs/approach-and-findings.md), [evaluation](docs/evaluation.md), and [Azure deployment](docs/deployment.md).

The approved KPI vocabulary and unit mappings are centralized in
`config/sustainability_glossary.yaml`. New evidence-supported terms are staged for human review and never merged
automatically. See the [glossary workflow](docs/glossary.md).
