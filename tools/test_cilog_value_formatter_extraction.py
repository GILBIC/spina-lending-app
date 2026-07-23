#!/usr/bin/env python3
"""Regression checks for the extracted CILOG value formatter."""

from __future__ import annotations

import argparse
import ast
import importlib.util
import inspect
import json
import shutil
import tempfile
from pathlib import Path

from extract_cilog_value_formatter import (
    APP_FILE,
    DEPENDENCY,
    IMPORT_LINE,
    MODULE,
    TARGET,
    apply_extraction,
    build_plan,
)

FIXTURE = Path("tools/fixtures/cilog_value_formatter_behavior.json")


def _cases() -> list[tuple[str, str | None, object]]:
    return [
        ("none_value", "principal", None),
        ("principal_integer", "principal", 1234),
        ("principal_negative", "principal", -1234.5),
        ("principal_text", "principal", "1234.5"),
        ("principal_comma_text", "principal", "1,234.50"),
        ("payment_amount", "payment_amount", 250.25),
        ("new_principal", "new_principal", 5000),
        ("interest_fraction", "interest_rate", 0.35),
        ("interest_one", "interest_rate", 1),
        ("interest_percent", "interest_rate", 35),
        ("interest_bad", "interest_rate", "not-a-rate"),
        ("unknown_newline", "remarks", "first\nsecond"),
        ("unknown_spaces", "status", "  Approved  "),
        ("unknown_list", "details", [1, 2]),
        ("empty_field", "", "value"),
        ("none_field", None, "value"),
        ("boolean_money", "principal", True),
    ]


def _capture(function, field: str | None, value: object) -> dict[str, str]:
    try:
        result = function(field, value)
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
    if len(signature.parameters) != 2:
        raise AssertionError(f"Unexpected signature: {signature}")
    return {
        name: _capture(function, field, value)
        for name, field, value in _cases()
    }


def _load_module(path: Path):
    spec = importlib.util.spec_from_file_location("spina_formatting_value_test", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load formatting module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _source_state(source: str) -> tuple[bool, bool]:
    tree = ast.parse(source)
    defined = any(
        isinstance(node, ast.FunctionDef) and node.name == TARGET
        for node in tree.body
    )
    imported = IMPORT_LINE in source
    return defined, imported


def _write_fixture(path: Path, behavior: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "target": TARGET,
                "dependency": DEPENDENCY,
                "case_names": [name for name, _field, _value in _cases()],
                "behavior": behavior,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


def _legacy_function(root: Path, function_text: str):
    module = _load_module(root / MODULE)
    namespace = {DEPENDENCY: getattr(module, DEPENDENCY)}
    exec(compile(function_text, "<legacy-cilog-value-formatter>", "exec"), namespace)
    return namespace[TARGET]


def _test_original(root: Path, fixture_path: Path | None) -> None:
    app = root / APP_FILE
    original_source = app.read_text(encoding="utf-8")
    plan = build_plan(app, root)
    assert plan["already_applied"] is False
    assert plan["safe_to_apply"] is True

    before = _behavior(_legacy_function(root, str(plan["_function_text"])))
    if fixture_path is not None:
        _write_fixture(fixture_path, before)
    assert app.read_text(encoding="utf-8") == original_source

    with tempfile.TemporaryDirectory() as temporary:
        temp_root = Path(temporary)
        temp_app = temp_root / APP_FILE
        temp_module = temp_root / MODULE
        temp_module.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(app, temp_app)
        shutil.copy2(root / MODULE, temp_module)

        result = apply_extraction(temp_app, temp_root)
        assert result["applied"] is True
        compile(temp_app.read_text(encoding="utf-8"), str(temp_app), "exec")
        compile(temp_module.read_text(encoding="utf-8"), str(temp_module), "exec")

        after_module = _load_module(temp_module)
        after = _behavior(getattr(after_module, TARGET))
        assert after == before
        assert apply_extraction(temp_app, temp_root)["already_applied"] is True


def _test_applied(root: Path, fixture_path: Path, rewrite: bool) -> None:
    app = root / APP_FILE
    defined, imported = _source_state(app.read_text(encoding="utf-8"))
    assert defined is False and imported is True

    module = _load_module(root / MODULE)
    current = _behavior(getattr(module, TARGET))
    if rewrite:
        _write_fixture(fixture_path, current)

    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    assert fixture["target"] == TARGET
    assert fixture["dependency"] == DEPENDENCY
    assert fixture["case_names"] == [name for name, _field, _value in _cases()]
    assert fixture["behavior"] == current
    assert build_plan(app, root)["already_applied"] is True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-fixture", nargs="?", const=str(FIXTURE))
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    fixture_path = Path(args.write_fixture) if args.write_fixture else root / FIXTURE
    if not fixture_path.is_absolute():
        fixture_path = root / fixture_path

    defined, imported = _source_state((root / APP_FILE).read_text(encoding="utf-8"))
    if defined and not imported:
        _test_original(root, fixture_path if args.write_fixture else None)
    elif not defined and imported:
        if not fixture_path.exists() and not args.write_fixture:
            raise AssertionError(f"Missing behavior fixture: {fixture_path}")
        _test_applied(root, fixture_path, bool(args.write_fixture))
    else:
        raise AssertionError(
            f"Unexpected formatter state: defined={defined}, imported={imported}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
