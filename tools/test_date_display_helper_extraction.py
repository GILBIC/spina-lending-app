#!/usr/bin/env python3
"""Regression checks for the extracted SPINA date display helpers."""

from __future__ import annotations

import argparse
import ast
import importlib.util
import inspect
import json
import shutil
import tempfile
from datetime import date, datetime
from pathlib import Path

from extract_date_display_helpers import (
    IMPORT_LINES,
    MODULE_RELATIVE_PATH,
    TARGETS,
    apply_extraction,
    build_plan,
)

APP_FILE = "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
DEFAULT_FIXTURE = Path("tools") / "fixtures" / "date_display_helpers_behavior.json"


def _cases() -> list[tuple[str, object]]:
    return [
        ("none", None),
        ("empty", ""),
        ("spaces", "   "),
        ("iso_date", "2024-02-29"),
        ("iso_datetime", "2024-02-29 12:30:45"),
        ("slash_date", "2024/02/29"),
        ("invalid_date", "2024-02-30"),
        ("bad_text", "not-a-date"),
        ("zero", 0),
        ("date_object", date(2024, 2, 29)),
        ("datetime_object", datetime(2024, 2, 29, 12, 30, 45)),
    ]


def _validate_signature(name: str, function) -> None:
    signature = inspect.signature(function)
    positional = [
        parameter
        for parameter in signature.parameters.values()
        if parameter.kind
        in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    ]
    if len(positional) != 1 or any(
        parameter.kind
        in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
        for parameter in signature.parameters.values()
    ):
        raise AssertionError(f"Unexpected signature for {name}{signature}")


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


def _behavior(functions: dict[str, object]) -> dict[str, dict[str, dict[str, str]]]:
    result: dict[str, dict[str, dict[str, str]]] = {}
    for name in TARGETS:
        function = functions[name]
        _validate_signature(name, function)
        result[name] = {
            case_name: _capture(function, value) for case_name, value in _cases()
        }
    return result


def _load_dates_module(module_path: Path, module_name: str) -> object:
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load dates module from {module_path}.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _legacy_functions(legacy_source: str, module_path: Path) -> dict[str, object]:
    dates_module = _load_dates_module(module_path, "legacy_spina_dates_base")
    namespace = {
        "datetime": datetime,
        "_spina_dash__parse_date": getattr(dates_module, "_spina_dash__parse_date"),
    }
    exec(compile(legacy_source, "<legacy-date-display-helpers>", "exec"), namespace)
    return {name: namespace[name] for name in TARGETS}


def _generated_functions(module_path: Path) -> dict[str, object]:
    module = _load_dates_module(module_path, "generated_spina_dates")
    return {name: getattr(module, name) for name in TARGETS}


def _source_state(source: str) -> tuple[set[str], set[str]]:
    tree = ast.parse(source)
    definitions = {
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in TARGETS
    }
    imports = {name for name, line in IMPORT_LINES.items() if line in source}
    return definitions, imports


def _write_fixture(path: Path, behavior: dict[str, object]) -> None:
    payload = {
        "targets": list(TARGETS),
        "case_names": [name for name, _value in _cases()],
        "behavior": behavior,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _copy_existing_package(repo_root: Path, temp_root: Path) -> None:
    source_package = repo_root / "spina_app"
    target_package = temp_root / "spina_app"
    target_package.mkdir(parents=True, exist_ok=True)
    for relative in (
        Path("__init__.py"),
        Path("utilities") / "__init__.py",
        Path("utilities") / "dates.py",
    ):
        source = source_package / relative
        target = target_package / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.exists():
            shutil.copy2(source, target)


def _test_original_state(repo_root: Path, fixture_path: Path | None) -> None:
    source_path = repo_root / APP_FILE
    original_source = source_path.read_text(encoding="utf-8")
    plan = build_plan(source_path, repo_root)
    assert plan["already_applied"] is False
    assert plan["safe_to_apply"] is True
    assert source_path.read_text(encoding="utf-8") == original_source

    before = _behavior(
        _legacy_functions(str(plan["_legacy_source"]), repo_root / MODULE_RELATIVE_PATH)
    )
    if fixture_path is not None:
        _write_fixture(fixture_path, before)

    with tempfile.TemporaryDirectory() as temporary:
        temp_root = Path(temporary)
        temp_app = temp_root / APP_FILE
        shutil.copy2(source_path, temp_app)
        _copy_existing_package(repo_root, temp_root)

        result = apply_extraction(temp_app, temp_root)
        assert result["applied"] is True
        module_path = temp_root / MODULE_RELATIVE_PATH
        compile(temp_app.read_text(encoding="utf-8"), str(temp_app), "exec")
        compile(module_path.read_text(encoding="utf-8"), str(module_path), "exec")
        after = _behavior(_generated_functions(module_path))
        assert after == before

        second = apply_extraction(temp_app, temp_root)
        assert second["already_applied"] is True


def _test_applied_state(repo_root: Path, fixture_path: Path, rewrite_fixture: bool) -> None:
    source_path = repo_root / APP_FILE
    source = source_path.read_text(encoding="utf-8")
    definitions, imports = _source_state(source)
    assert definitions == set()
    assert imports == set(TARGETS)

    module_path = repo_root / MODULE_RELATIVE_PATH
    current_behavior = _behavior(_generated_functions(module_path))
    if rewrite_fixture:
        _write_fixture(fixture_path, current_behavior)
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    assert fixture["targets"] == list(TARGETS)
    assert fixture["case_names"] == [name for name, _value in _cases()]
    assert current_behavior == fixture["behavior"]

    plan = build_plan(source_path, repo_root)
    assert plan["already_applied"] is True
    assert plan["safe_to_apply"] is True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write-fixture",
        nargs="?",
        const=str(DEFAULT_FIXTURE),
        help="Write or refresh the behavior fixture",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    source = (repo_root / APP_FILE).read_text(encoding="utf-8")
    definitions, imports = _source_state(source)
    fixture_path = Path(args.write_fixture) if args.write_fixture else repo_root / DEFAULT_FIXTURE
    if not fixture_path.is_absolute():
        fixture_path = repo_root / fixture_path

    if definitions == set(TARGETS) and not imports:
        _test_original_state(repo_root, fixture_path if args.write_fixture else None)
    elif not definitions and imports == set(TARGETS):
        if not fixture_path.exists() and not args.write_fixture:
            raise AssertionError(f"Missing behavior fixture: {fixture_path}")
        _test_applied_state(repo_root, fixture_path, bool(args.write_fixture))
    else:
        raise AssertionError(
            f"Unexpected mixed date-display state: definitions={definitions}, imports={imports}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
