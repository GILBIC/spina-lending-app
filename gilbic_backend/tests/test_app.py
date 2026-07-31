from fastapi.testclient import TestClient

from gilbic_backend import __version__
from gilbic_backend.main import create_app


def test_liveness_endpoint() -> None:
    client = TestClient(create_app())

    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "gilbic-backend",
    }


def test_readiness_endpoint_when_database_is_ready(monkeypatch) -> None:
    monkeypatch.setattr("gilbic_backend.main.database_ready", lambda settings: True)
    client = TestClient(create_app())

    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "service": "gilbic-backend",
        "database": "ok",
    }


def test_readiness_endpoint_when_database_is_unavailable(monkeypatch) -> None:
    monkeypatch.setattr("gilbic_backend.main.database_ready", lambda settings: False)
    client = TestClient(create_app())

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "unavailable",
        "service": "gilbic-backend",
        "database": "unavailable",
    }


def test_metadata_endpoint() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/meta")

    assert response.status_code == 200
    assert response.json() == {
        "service": "gilbic-backend",
        "version": __version__,
    }
