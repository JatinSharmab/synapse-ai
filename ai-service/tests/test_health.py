from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_health_returns_typed_service_contract() -> None:
    settings = Settings(app_env="test", app_version="0.1.0-test")

    with TestClient(create_app(settings)) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {
        "service": "synapse-ai-service",
        "status": "ok",
        "version": "0.1.0-test",
        "environment": "test",
    }


def test_health_schema_is_exposed_in_openapi() -> None:
    app = create_app(Settings(app_env="test"))

    with TestClient(app) as client:
        schema = client.get("/openapi.json").json()

    health_operation = schema["paths"]["/health"]["get"]
    response_schema = health_operation["responses"]["200"]["content"]["application/json"]["schema"]
    assert response_schema["$ref"].endswith("/HealthResponse")
