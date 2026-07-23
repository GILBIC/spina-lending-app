#!/usr/bin/env python3
"""Behavior regression coverage for _as_note_dict extraction."""

from __future__ import annotations

import argparse
import ast
import importlib.util
import json
from pathlib import Path

APP_PATH = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
MODULE_PATH = Path("spina_app/utilities/notes.py")
FIXTURE_PATH = Path("tools/fixtures/note_dict_helper_behavior.json")
TARGET = "_as_note_dict"
IMPORT_LINE = f"from spina_app.utilities.notes import {TARGET}"

CASES = [
    ("none", None),
    ("empty", ""),
    ("spaces", "   "),
    ("text", "payment delayed"),
    ("trimmed_text", "  payment delayed  "),
    ("zero", 0),
    ("integer", 123),
    ("negative", -5),
    ("false", False),
    ("true", True),
    ("list_value", [1, 2]),
    ("tuple_value", (1, 2)),
    ("empty_dict", {}),
    ("simple_dict", {"2026-07-23": "note"}),
    ("default_dict", {"__default__": "general"}),
    ("nested_dict", {"2026-07-23": {"reason": "late"}}),
]


def load_helper():
    app_source = APP_PATH.read_text(encoding="utf-8")
    tree = ast.parse(app_source)
    matches = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == TARGET]
    imported = IMPORT_LINE in app_source

    if len(matches) == 1 and not imported:
        namespace: dict[str, object] = {}
        module = ast.Module(body=[matches[0]], type_ignores=[])
        ast.fix_missing_locations(module)
        exec(compile(module, str(APP_PATH), "exec"), namespace)
        return namespace[TARGET]

    if not matches and imported and MODULE_PATH.exists():
        spec = importlib.util.spec_from_file_location("spina_notes_test_module", MODULE_PATH)
        if spec is None or spec.loader is None:
            raise RuntimeError("Unable to load notes utility module")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return getattr(module, TARGET)

    raise RuntimeError(
        f"Unexpected extraction state: definitions={len(matches)}, import_present={imported}, module_exists={MODULE_PATH.exists()}"
    )


def capture_behavior(fn) -> dict[str, object]:
    behavior: dict[str, object] = {}
    for name, value in CASES:
        try:
            result = fn(value)
            behavior[name] = {
                "kind": "return",
                "type": f"{type(result).__module__}.{type(result).__qualname__}",
                "repr": repr(result),
            }
        except Exception as exc:  # pragma: no cover - fixture records any unexpected behavior
            behavior[name] = {
                "kind": "raise",
                "type": f"{type(exc).__module__}.{type(exc).__qualname__}",
                "repr": repr(exc),
            }
    return {
        "target": TARGET,
        "case_names": [name for name, _ in CASES],
        "behavior": behavior,
    }


def validate_copy_semantics(fn) -> None:
    nested: list[int] = [1]
    original = {"__default__": "general", "nested": nested}
    result = fn(original)
    if result != original:
        raise AssertionError("Dictionary content changed")
    if result is original:
        raise AssertionError("Dictionary input must be copied")
    if result["nested"] is not nested:
        raise AssertionError("Expected the original shallow-copy behavior")
    result["extra"] = "value"
    if "extra" in original:
        raise AssertionError("Returned dictionary must be independently mutable")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-fixture", type=Path)
    args = parser.parse_args()

    fn = load_helper()
    validate_copy_semantics(fn)
    current = capture_behavior(fn)

    if args.write_fixture:
        args.write_fixture.parent.mkdir(parents=True, exist_ok=True)
        args.write_fixture.write_text(json.dumps(current, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return

    expected = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    if current != expected:
        raise AssertionError(
            "_as_note_dict behavior changed\n"
            + json.dumps({"expected": expected, "current": current}, indent=2, ensure_ascii=False)
        )


if __name__ == "__main__":
    main()
