#!/usr/bin/env python3
"""Regression checks for the extracted CILOG action-label helper."""

from __future__ import annotations

import argparse
import ast
import importlib.util
import inspect
import json
import shutil
import tempfile
from pathlib import Path

from extract_cilog_action_label import APP_FILE, IMPORT_LINE, MODULE, TARGET, apply, build_plan

FIXTURE = Path("tools/fixtures/cilog_action_label_behavior.json")


def _cases() -> list[tuple[str, object, object]]:
    return [
        ("update_picture", "UPDATE", "client picture"),
        ("update_link", "update", "account link"),
        ("update_area", " UPDATE ", "Area assignment"),
        ("update_generic", "UPDATE", "client record"),
        ("create", "create", ""),
        ("delete", "DELETE", "anything"),
        ("empty", "", ""),
        ("none", None, None),
        ("spaces", "  approve  ", ""),
        ("numeric", 12, ""),
        ("picture_priority", "UPDATE", "picture link area"),
        ("link_priority", "UPDATE", "link area"),
    ]


def _capture(function, action: object, source: object) -> dict[str, str]:
    try:
        result = function(action, source)
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
    if list(signature.parameters) != ["action", "source"]:
        raise AssertionError(f"Unexpected signature: {signature}")
    return {name: _capture(function, action, source) for name, action, source in _cases()}


def _load(path: Path):
    spec = importlib.util.spec_from_file_location("spina_text_action_label_test", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load text utility module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, TARGET)


def _source_state(source: str) -> tuple[bool, bool]:
    tree = ast.parse(source)
    defined = any(isinstance(node, ast.FunctionDef) and node.name == TARGET for node in tree.body)
    return defined, IMPORT_LINE in source


def _write_fixture(path: Path, behavior: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "target": TARGET,
                "case_names": [name for name, _action, _source in _cases()],
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
    original_source = app.read_text(encoding="utf-8")
    plan = build_plan(app, root)
    assert plan["safe_to_apply"] is True

    tree = ast.parse(original_source)
    node = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == TARGET)
    lines = original_source.splitlines(keepends=True)
    function_text = "".join(lines[node.lineno - 1 : node.end_lineno])
    namespace: dict[str, object] = {}
    exec(compile(function_text, "<legacy-action-label>", "exec"), namespace)
    before = _behavior(namespace[TARGET])
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
        result = apply(temp_app, temp_root)
        assert result["applied"] is True
        compile(temp_app.read_text(encoding="utf-8"), str(temp_app), "exec")
        compile(temp_module.read_text(encoding="utf-8"), str(temp_module), "exec")
        after = _behavior(_load(temp_module))
        assert after == before
        assert apply(temp_app, temp_root)["already_applied"] is True


def _applied(root: Path, fixture_path: Path, rewrite: bool) -> None:
    app = root / APP_FILE
    defined, imported = _source_state(app.read_text(encoding="utf-8"))
    assert defined is False and imported is True
    current = _behavior(_load(root / MODULE))
    if rewrite:
        _write_fixture(fixture_path, current)
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    assert fixture["target"] == TARGET
    assert fixture["case_names"] == [name for name, _action, _source in _cases()]
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
