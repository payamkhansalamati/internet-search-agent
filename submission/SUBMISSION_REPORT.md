# Submission packaging and verification report

## Packaging decision

The delivery is a clean source-only project. Original repository files were copied; none were moved, deleted or
modified. The submission contains no source PDFs, secrets, local environment, generated package metadata, cached
models, persistent runtime data, or presentation assets.

## Index decision

**Index status: excluded; regeneration required.**

The original LlamaIndex store is monolithic and exceeded the 50 MB maximum before packaging:

| Original index item | Bytes |
|---|---:|
| `data/index/default__vector_store.json` | 48,423,149 |
| `data/index/docstore.json` | 9,600,671 |
| `data/index/graph_store.json` | 18 |
| `data/index/image__vector_store.json` | 72 |
| `data/index/index-manifest.json` | 477,286 |
| `data/index/index_store.json` | 912,415 |
| **Index total** | **59,413,611** |
| Separate `data/manifest.json` | 737 |

A partial selection of these files is not a valid LlamaIndex store. Creating a derivative subset from extracted ABB
or Siemens report text was also rejected because redistribution permission was not established. The submission
therefore includes exact ingestion commands for the official report URLs but no copyrighted report file or extracted
production index.

## Excluded components

- Original `data/` vector store and manifests — over the size limit and contains extracted third-party report text.
- `.env` and all credentials — secret-bearing local configuration.
- `.venv/` — machine-specific environment and dependencies.
- `.pytest_cache/`, `.ruff_cache/`, `.mypy_cache/`, `__pycache__/`, `*.pyc` — generated caches.
- `src/*.egg-info/` — generated build metadata recreated during installation.
- `deliverables/` — presentation, PDF and presentation verification notes are unrelated to application execution.
- Attached screenshots and external presentation reference — not part of the application.
- `.git/`, editor settings, local IDE state and temporary files — development-machine metadata.
- `.github/` CI definition — useful in the source repository but not required to install, run, test or evaluate this delivery.
- Redundant repository documentation — consolidated into the submission-specific `README.md`.
- Logs, recordings and coverage output — none required or included.

## Verification environment and results

| Check | Result |
|---|---|
| Fresh isolated virtual environment | Passed with Python 3.12 in a temporary directory outside the submission |
| Install using included package/lock files | `uv sync --frozen --all-extras` passed; 219 packages installed solely from included metadata |
| Test suite | 30 passed; one upstream Starlette `TestClient` deprecation warning |
| Ruff lint and format check | Passed; 37 Python files correctly formatted |
| Mypy strict type check | Passed; 24 source files checked |
| API startup, `/health`, `/ready` | Uvicorn started; both endpoints returned HTTP 200 with documented bodies |
| Representative API query and status | POST returned HTTP 202; status and result endpoints returned HTTP 200 and completed output |
| Retrieval, synthesis and citations | Deterministic end-to-end verification passed; regenerated ABB index returned 12 matching evidence chunks |
| Physical/printed page metadata | Passed; smoke citation retained report p. 5, PDF p. 7 and a `#page=7` link |
| Glossary schema validation | Passed; approved glossary version 1.0.0 |
| Evaluation case loader | Passed; loaded five deterministic cases |
| Document/index rebuild | ABB official report ingestion completed; fallback extraction produced a valid, queryable 3.5 MB temporary index |
| Secret and absolute-path scan | Passed; no private-key marker, token pattern, machine-specific home path or user name found |
| Symlink/external dependency scan | Passed; no symlinks and no file dependency outside `submission/` |
| Final folder size | 1,473,440 logical bytes (1,564 KiB allocated), below 50 MiB |

## Functional impact

No application feature, schema, prompt, ranking rule, ingestion behavior or test expectation was weakened for
packaging. Research queries require rebuilding an authorized index as documented in `README.md`; greeting routing and
the deterministic submission smoke verification work without an external report or model credential.

Clean-install testing exposed two dependencies that had previously been supplied transitively by the developer
environment. The submission package now declares `fastembed` directly and constrains `docling-core[chunking]` to the
version family compatible with Docling 2.10.0. This changes packaging only and makes the copied application reproducible;
no production implementation was changed.
