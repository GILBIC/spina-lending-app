"""Release boundaries after retirement of the independent desktop authority."""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_original_desktop_is_not_shipped_or_compiled():
    assert not (ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py").exists()
    # Ignored bytecode from a developer's previous checkout is not shipped source.
    assert not list((ROOT / "spina_app").rglob("*.py"))
    pipeline = (ROOT / ".github/workflows/spina-ci.yml").read_text(encoding="utf-8")
    assert "OFFICIAL_SPINA_APP" not in pipeline
    assert "compileall -q spina_app" not in pipeline
    assert (ROOT / "spina_pc/install_spina_pc.ps1").is_file()


def test_production_packages_do_not_import_the_retired_desktop():
    for folder in ("gilbic_backend/src", "spina_backend_mobile/src", "api"):
        for path in (ROOT / folder).rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8-sig"))):
                names = [item.name for item in node.names] if isinstance(node, ast.Import) else (
                    [node.module or ""] if isinstance(node, ast.ImportFrom) else []
                )
                assert not any(name.split(".")[0] == "spina_app" for name in names), path


def test_persistent_runners_accept_only_explicit_trusted_maintenance():
    for path in (ROOT / ".github/workflows").glob("*.yml"):
        source = path.read_text(encoding="utf-8")
        if "self-hosted" not in source:
            continue
        triggers = source.split("\njobs:", 1)[0]
        assert not re.search(r"^  (?:pull_request|pull_request_target|push|workflow_run):", triggers, re.M), path
        assert "workflow_dispatch:" in triggers, path
        assert "refs/heads/main" in source, path
