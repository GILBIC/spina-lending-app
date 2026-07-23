#!/usr/bin/env python3
"""Regression checks for the extracted log JSON helper."""

from __future__ import annotations

import argparse
import ast
import importlib.util
import inspect
import json
import shutil
import tempfile
from pathlib import Path

from extract_log_serialization_helper import APP_FILE, IMPORT_LINE, MODULE, TARGET, apply, build_plan

FIXTURE = Path("tools/fixtures/log_serialization_helper_behavior.json")


def _cases() -> list[tuple[str, object]]:
    return [
        ("none", None),
        ("empty", ""),
        ("dict", {"a": 1}),
        ("json_object", '{"a": 1, "b": "x"}'),
        ("json_list", '[1, 2, "x"]'),
        ("json_number", "12.5"),
        ("json_true", "true"),
        ("json_null", "null"),
        ("bytes_object", b'{"a": 2}'),
        ("invalid", "not-json"),
        ("integer", 7),
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
        raise AssertionError(f"Unexpected signature: {signature}")
    return {name: _capture(function, value) for name, value in _cases()}


def _load_module(path: Path):
    spec = importlib.util.spec_from_file_location("spina_serialization_test", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load serialization module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, TARGET)


def _source_state(source: str) -> tuple[bool, bool]:
    tree = ast.parse(source)
    defined = any(isinstance(node, ast.FunctionDef) and node.name == TARGET for node in tree.body)
    imported = IMPORT_LINE in source
    return defined, imported


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


def _original(root: Path, fixture_path: Path | None) -> None:
    app = root / APP_FILE
    original = app.read_text(encoding="utf-8")
    plan = build_plan(app, root)
    assert plan["safe_to_apply"] is True
    namespace: dict[str, object] = {}
    exec(compile(str(plan["_module_text"]), "<legacy-helper>", "exec"), namespace)
    before = _behavior(namespace[TARGET])
    if fixture_path is not None:
        _write_fixture(fixture_path, before)
    assert app.read_text(encoding="utf-8") == original

    with tempfile.TemporaryDirectory() as temporary:
        temp_root = Path(temporary)
        temp_app = temp_root / APP_FILE
        shutil.copy2(app, temp_app)
        result = apply(temp_app, temp_root)
        assert result["applied"] is True
        module_path = temp_root / MODULE
        compile(temp_app.read_text(encoding="utf-8"), str(temp_app), "exec")
        compile(module_path.read_text(encoding="utf-8"), str(module_path), "exec")
        after = _behavior(_load_module(module_path))
        assert after == before
        assert apply(temp_app, temp_root)["already_applied"] is True


def _applied(root: Path, fixture_path: Path, rewrite: bool) -> None:
    app = root / APP_FILE
    defined, imported = _source_state(app.read_text(encoding="utf-8"))
    assert defined is False and imported is True
    current = _behavior(_load_module(root / MODULE))
    if rewrite:
        _write_fixture(fixture_path, current)
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    assert fixture["target"] == TARGET
    assert fixture["case_names"] == [name for name, _value in _cases()]
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
        _original(root, fixture_path if args.write_fixture else None)
    elif not defined and imported:
        if not fixture_path.exists() and not args.write_fixture:
            raise AssertionError(f"Missing fixture: {fixture_path}")
        _applied(root, fixture_path, bool(args.write_fixture))
    else:
        raise AssertionError(f"Unexpected state: defined={defined}, imported={imported}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
