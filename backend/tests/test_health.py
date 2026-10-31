"""Scaffold smoke test: the API boots and answers its liveness probe."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok() -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_unknown_route_is_404() -> None:
    response = client.get("/api/does-not-exist")

    assert response.status_code == 404
