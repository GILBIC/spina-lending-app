#!/usr/bin/env python3
"""Regression checks for extracted SPINA display-formatting helpers."""

from __future__ import annotations

import argparse
import ast
import importlib.util
import inspect
import json
import shutil
import tempfile
from pathlib import Path

from extract_display_formatters import (
    DEFAULT_APP,
    IMPORT_LINES,
    MODULE_RELATIVE_PATH,
    TARGETS,
    apply_extraction,
    build_plan,
)

DEFAULT_FIXTURE = Path("tools") / "fixtures" / "display_formatters_behavior.json"


def _cases() -> list[tuple[str, object]]:
    return [
        ("none", None),
        ("empty", ""),
        ("zero_int", 0),
        ("one_int", 1),
        ("negative_int", -7),
        ("decimal", 12.3456),
        ("negative_decimal", -42.75),
        ("numeric_text", "1234.5"),
        ("comma_text", "1,234.50"),
        ("bad_text", "not-a-number"),
        ("true", True),
    ]


def _validate_signature(name: str, function) -> None:
    signature = inspect.signature(function)
    positional = [
        parameter
        for parameter in signature.parameters.values()
        if parameter.kind
        in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    ]
    required = [
        parameter for parameter in positional if parameter.default is inspect.Parameter.empty
    ]
    required_keyword_only = [
        parameter
        for parameter in signature.parameters.values()
        if parameter.kind is inspect.Parameter.KEYWORD_ONLY
        and parameter.default is inspect.Parameter.empty
    ]
    if len(positional) != 1 or len(required) > 1 or required_keyword_only:
        raise AssertionError(f"Unsupported formatter signature: {name}{signature}")


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


def _functions_from_sources(sources: dict[str, str]) -> dict[str, object]:
    namespace: dict[str, object] = {}
    text = "\n".join(sources[name] for name in TARGETS)
    exec(compile(text, "<legacy-display-formatters>", "exec"), namespace)
    return {name: namespace[name] for name in TARGETS}


def _load_module_functions(module_path: Path) -> dict[str, object]:
    spec = importlib.util.spec_from_file_location("temp_spina_formatting", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load formatting module.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
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


def _test_original(repo_root: Path, fixture_path: Path | None) -> None:
    app_path = repo_root / DEFAULT_APP
    original_source = app_path.read_text(encoding="utf-8")
    plan = build_plan(app_path, repo_root)
    assert plan["already_applied"] is False
    assert plan["safe_to_apply"] is True
    assert app_path.read_text(encoding="utf-8") == original_source

    before = _behavior(_functions_from_sources(plan["_function_sources"]))
    if fixture_path is not None:
        _write_fixture(fixture_path, before)

    with tempfile.TemporaryDirectory() as temporary:
        temp_root = Path(temporary)
        temp_app = temp_root / DEFAULT_APP
        temp_module = temp_root / MODULE_RELATIVE_PATH
        temp_module.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(app_path, temp_app)
        shutil.copy2(repo_root / MODULE_RELATIVE_PATH, temp_module)

        result = apply_extraction(temp_app, temp_root)
        assert result["applied"] is True
        compile(temp_app.read_text(encoding="utf-8"), str(temp_app), "exec")
        compile(temp_module.read_text(encoding="utf-8"), str(temp_module), "exec")
        after = _behavior(_load_module_functions(temp_module))
        assert after == before
        assert apply_extraction(temp_app, temp_root)["already_applied"] is True


def _test_applied(repo_root: Path, fixture_path: Path) -> None:
    app_path = repo_root / DEFAULT_APP
    source = app_path.read_text(encoding="utf-8")
    definitions, imports = _source_state(source)
    assert definitions == set()
    assert imports == set(TARGETS)

    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    assert fixture["targets"] == list(TARGETS)
    assert fixture["case_names"] == [name for name, _value in _cases()]
    actual = _behavior(_load_module_functions(repo_root / MODULE_RELATIVE_PATH))
    assert actual == fixture["behavior"]
    plan = build_plan(app_path, repo_root)
    assert plan["already_applied"] is True
    assert plan["safe_to_apply"] is True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write-fixture",
        nargs="?",
        const=str(DEFAULT_FIXTURE),
        help="Write the pre-extraction behavior fixture.",
    )
    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    source = (repo_root / DEFAULT_APP).read_text(encoding="utf-8")
    definitions, imports = _source_state(source)
    fixture_path = Path(args.write_fixture) if args.write_fixture else repo_root / DEFAULT_FIXTURE
    if not fixture_path.is_absolute():
        fixture_path = repo_root / fixture_path

    if definitions == set(TARGETS) and not imports:
        _test_original(repo_root, fixture_path if args.write_fixture else None)
    elif not definitions and imports == set(TARGETS):
        if not fixture_path.exists():
            raise AssertionError(f"Missing display formatter fixture: {fixture_path}")
        _test_applied(repo_root, fixture_path)
    else:
        raise AssertionError(
            f"Unexpected mixed formatter state: definitions={definitions}, imports={imports}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
