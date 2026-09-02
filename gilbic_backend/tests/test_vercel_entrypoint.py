from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from fastapi import FastAPI


ROOT = Path(__file__).resolve().parents[2]


def test_root_vercel_entrypoint_exports_existing_fastapi_app() -> None:
    path = ROOT / "app.py"
    spec = spec_from_file_location("spina_vercel_entrypoint", path)

    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)

    assert isinstance(module.app, FastAPI)
    paths = module.app.openapi()["paths"]
    assert "/health/live" in paths
    assert "/health/ready" in paths
    assert "/api/v1/meta" in paths


def test_root_requirements_installs_existing_backend_package() -> None:
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")

    assert requirements.splitlines() == ["./gilbic_backend"]
