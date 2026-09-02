from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from fastapi import FastAPI


ROOT = Path(__file__).resolve().parents[2]


def _load_app(path: Path, module_name: str) -> FastAPI:
    spec = spec_from_file_location(module_name, path)

    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)

    assert isinstance(module.app, FastAPI)
    return module.app


def _assert_required_routes(app: FastAPI) -> None:
    paths = app.openapi()["paths"]
    assert "/health/live" in paths
    assert "/health/ready" in paths
    assert "/api/v1/meta" in paths


def test_root_adapter_exports_existing_fastapi_app() -> None:
    _assert_required_routes(
        _load_app(ROOT / "app.py", "spina_root_entrypoint"),
    )


def test_api_directory_adapter_exports_existing_fastapi_app() -> None:
    _assert_required_routes(
        _load_app(ROOT / "api" / "index.py", "spina_api_entrypoint"),
    )


def test_root_requirements_installs_both_existing_backend_packages() -> None:
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")

    assert requirements.splitlines() == [
        "./spina_backend_mobile",
        "./gilbic_backend",
    ]
