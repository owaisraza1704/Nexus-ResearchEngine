from fastapi.testclient import TestClient

from app.main import app


def test_liveness_endpoint() -> None:
    response = TestClient(app).get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_checks_database_and_provider_configuration(client, settings):
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["checks"] == {"database": "ok", "embeddings": "ok", "llm": "ok"}
    settings.azure_openai_model = None
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["detail"]["checks"]["llm"] == "not_configured"
