#!/usr/bin/env python3
"""Regression checks for the first guarded utility extraction."""

from __future__ import annotations

import ast
import importlib.util
import shutil
import tempfile
from pathlib import Path

from extract_fmt_currency_module import (
    FUNCTION_NAME,
    IMPORT_LINE,
    apply_extraction,
    build_plan,
)

APP_FILE = "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"


def _original_function(source: str):
    tree = ast.parse(source)
    node = next(
        item
        for item in tree.body
        if isinstance(item, ast.FunctionDef) and item.name == FUNCTION_NAME
    )
    module = ast.Module(body=[node], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace: dict[str, object] = {}
    exec(compile(module, "<original-fmt-currency>", "exec"), namespace)
    return namespace[FUNCTION_NAME]


def _load_generated_function(module_path: Path):
    spec = importlib.util.spec_from_file_location("temp_spina_formatting", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load generated formatting module.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, FUNCTION_NAME)


def _capture(function, value):
    try:
        return ("return", function(value))
    except Exception as exc:
        return ("raise", type(exc).__name__, str(exc))


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    source_path = repo_root / APP_FILE
    original_source = source_path.read_text(encoding="utf-8")
    original = _original_function(original_source)

    with tempfile.TemporaryDirectory() as tmp:
        temp_root = Path(tmp)
        temp_app = temp_root / APP_FILE
        shutil.copy2(source_path, temp_app)

        dry_run = build_plan(temp_app, temp_root)
        assert dry_run["safe_to_apply"] is True
        assert dry_run["already_applied"] is False
        assert temp_app.read_text(encoding="utf-8") == original_source

        result = apply_extraction(temp_app, temp_root)
        assert result["applied"] is True

        patched_source = temp_app.read_text(encoding="utf-8")
        assert IMPORT_LINE in patched_source
        patched_tree = ast.parse(patched_source)
        assert not any(
            isinstance(item, ast.FunctionDef) and item.name == FUNCTION_NAME
            for item in patched_tree.body
        )

        module_path = temp_root / "spina_app" / "utilities" / "formatting.py"
        assert module_path.exists()
        extracted = _load_generated_function(module_path)

        values = [None, "", "0", "1000", 0, 1, 1.25, -1234.56, "not-a-number"]
        for value in values:
            assert _capture(original, value) == _capture(extracted, value), value

        second = apply_extraction(temp_app, temp_root)
        assert second["already_applied"] is True
        compile(patched_source, str(temp_app), "exec")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
