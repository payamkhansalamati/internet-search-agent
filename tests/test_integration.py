from pathlib import Path

from fastapi.testclient import TestClient

from search_agent.domain import Evidence
from search_agent.main import create_app
from search_agent.settings import Settings


class FakeLLM:
    async def answer(self, question: str, evidence: list[Evidence]) -> str:
        return "Grounded answer [1]" if evidence else "No evidence available."


class FakeSearch:
    async def search(self, query: str, max_results: int) -> list[Evidence]:
        return [Evidence("A" * 350, "Official report", "https://siemens.com/report.pdf", "Siemens", 2024, 10)]


def test_api_and_status(tmp_path: Path) -> None:
    settings = Settings(
        index_path=tmp_path / "index",
        manifest_path=tmp_path / "manifest.json",
        companies_path=Path("config/companies.yaml"),
    )
    app = create_app(settings)
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json() == {"status": "ok"}
        ready = client.get("/ready")
        assert ready.status_code == 200
        assert ready.json() == {"status": "ready"}
        openapi = client.get("/openapi.json")
        assert openapi.status_code == 200
        schema = openapi.json()
        assert schema["paths"]["/health"]["get"]["responses"]["200"]["content"]["application/json"]["schema"] == {
            "$ref": "#/components/schemas/HealthResponse"
        }
        assert schema["paths"]["/ready"]["get"]["responses"]["200"]["content"]["application/json"]["schema"] == {
            "$ref": "#/components/schemas/ReadyResponse"
        }
        assert schema["components"]["schemas"]["HealthResponse"]["examples"] == [{"status": "ok"}]
        assert schema["components"]["schemas"]["ReadyResponse"]["examples"] == [{"status": "ready"}]
        assert "additionalProp1" not in str(schema["paths"]["/health"])
        assert "additionalProp1" not in str(schema["paths"]["/ready"])
        response = client.post("/api/v1/query", json={"question": "hello"})
        assert response.status_code == 202
        request_id = response.json()["request_id"]
        status = client.get(f"/api/v1/status/{request_id}").json()
        assert status["stage"] == "completed"
        assert client.get(f"/api/v1/requests/{request_id}").status_code == 200
