#!/usr/bin/env python3
"""Regression checks for the extracted Client Information Log money formatter."""

from __future__ import annotations

import argparse
import ast
import importlib.util
import inspect
import json
from pathlib import Path

APP_FILE = "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = Path("spina_app/utilities/formatting.py")
TARGET = "_spina_cilog_fmt_money"
IMPORT_LINE = f"from spina_app.utilities.formatting import {TARGET}"
FIXTURE = Path("tools/fixtures/cilog_money_formatter_behavior.json")


def _cases() -> list[tuple[str, object]]:
    return [
        ("none", None),
        ("empty", ""),
        ("zero", 0),
        ("integer", 1234),
        ("negative", -1234.5),
        ("float", 1234.567),
        ("numeric_text", "1234.5"),
        ("spaces", " 12.5 "),
        ("comma_text", "1,234.50"),
        ("bad_text", "not-a-number"),
        ("boolean", True),
        ("list_value", [1, 2]),
    ]


def _capture(function, value: object) -> dict[str, str]:
    try:
        result = function(value)
        return {
            "kind": "return",
            "type": f"{type(result).__module__}.{type(result).__qualname__}",
            "repr": repr(result),
        }
    except Exception as exc:
        return {
            "kind": "raise",
            "type": f"{type(exc).__module__}.{type(exc).__qualname__}",
            "message": str(exc),
        }


def _behavior(function) -> dict[str, dict[str, str]]:
    signature = inspect.signature(function)
    if len(signature.parameters) != 1:
        raise AssertionError(f"Unexpected signature for {TARGET}: {signature}")
    return {name: _capture(function, value) for name, value in _cases()}


def _state(source: str) -> tuple[ast.FunctionDef | None, bool]:
    tree = ast.parse(source)
    matches = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == TARGET
    ]
    if len(matches) > 1:
        raise AssertionError(f"Duplicate top-level definition for {TARGET}")
    return (matches[0] if matches else None), IMPORT_LINE in source


def _legacy_function(source: str, node: ast.FunctionDef):
    lines = source.splitlines()
    function_source = "\n".join(lines[node.lineno - 1 : node.end_lineno]) + "\n"
    namespace: dict[str, object] = {}
    exec(compile(function_source, "<legacy-cilog-money-formatter>", "exec"), namespace)
    return namespace[TARGET]


def _module_function(path: Path):
    spec = importlib.util.spec_from_file_location("spina_formatting_test", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load formatting utility module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, TARGET)


def _write_fixture(path: Path, behavior: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "target": TARGET,
                "case_names": [name for name, _value in _cases()],
                "behavior": behavior,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-fixture", nargs="?", const=str(FIXTURE))
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    app_path = root / APP_FILE
    source = app_path.read_text(encoding="utf-8")
    node, imported = _state(source)
    fixture_path = Path(args.write_fixture) if args.write_fixture else root / FIXTURE
    if not fixture_path.is_absolute():
        fixture_path = root / fixture_path

    if node is not None and not imported:
        behavior = _behavior(_legacy_function(source, node))
        if args.write_fixture:
            _write_fixture(fixture_path, behavior)
        return 0

    if node is None and imported:
        module_path = root / MODULE
        compile(source, str(app_path), "exec")
        compile(module_path.read_text(encoding="utf-8"), str(module_path), "exec")
        behavior = _behavior(_module_function(module_path))
        if args.write_fixture:
            _write_fixture(fixture_path, behavior)
        if not fixture_path.exists():
            raise AssertionError(f"Missing behavior fixture: {fixture_path}")
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        assert fixture["target"] == TARGET
        assert fixture["case_names"] == [name for name, _value in _cases()]
        assert fixture["behavior"] == behavior
        return 0

    raise AssertionError(
        f"Unexpected mixed formatter state: definition={node is not None}, import={imported}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
