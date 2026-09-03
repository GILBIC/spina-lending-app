from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
for package_root in (
    ROOT / "gilbic_backend" / "src",
    ROOT / "spina_backend_mobile" / "src",
    ROOT,
):
    value = str(package_root)
    if value not in sys.path:
        sys.path.insert(0, value)


def _fresh_app(cors_origins: str):
    os.environ["GILBIC_CORS_ORIGINS"] = cors_origins

    from gilbic_backend.config import get_settings

    get_settings.cache_clear()
    module = importlib.import_module("gilbic_backend.main")
    return module.create_app()


def test_vercel_entrypoint_exports_existing_fastapi_app() -> None:
    module = importlib.import_module("api.index")
    response = TestClient(module.app).get("/health/live")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "gilbic-backend",
    }


def test_preflight_allows_configured_portal_origin() -> None:
    app = _fresh_app("https://portal.example")
    response = TestClient(app).options(
        "/api/v1/meta",
        headers={
            "Origin": "https://portal.example",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,x-device-id",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://portal.example"
    assert "authorization" in response.headers["access-control-allow-headers"].lower()
    assert "x-device-id" in response.headers["access-control-allow-headers"].lower()


def test_preflight_rejects_unlisted_origin() -> None:
    app = _fresh_app("https://portal.example")
    response = TestClient(app).options(
        "/api/v1/meta",
        headers={
            "Origin": "https://attacker.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_vercel_requirements_use_registry_dependencies_not_ambiguous_local_paths() -> None:
    lines = [
        line.strip()
        for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]

    assert "./gilbic_backend" not in lines
    assert "./spina_backend_mobile" not in lines
    assert any(line.startswith("fastapi") for line in lines)
    assert any(line.startswith("psycopg") for line in lines)
