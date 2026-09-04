# API

`GET /health` reports process health. `GET /ready` confirms dependencies were constructed. `POST /api/v1/query` accepts `{"question":"..."}` and returns HTTP 202 with a UUID. Poll `GET /api/v1/status/{request_id}`, then read `GET /api/v1/requests/{request_id}`.

```bash
curl -s http://localhost:8000/health
curl -s -X POST http://localhost:8000/api/v1/query -H 'content-type: application/json' -d '{"question":"What is ABB latest emissions target?"}'
curl -s http://localhost:8000/api/v1/status/REQUEST_ID
curl -s http://localhost:8000/api/v1/requests/REQUEST_ID
```

Stages are `received`, `classifying`, `retrieving`, `searching`, `processing_documents`, `synthesizing`, `validating`, `completed`, and `failed`; a particular route may skip stages. Results include answer, source metadata, live-search flag, confidence, and comparison warnings. Missing IDs return 404, unfinished results 409, invalid requests 422, and failed work 500. FastAPI publishes exact schemas at `/openapi.json` and interactive documentation at `/docs`.

