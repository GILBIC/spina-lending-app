#!/usr/bin/env python3
"""Behavior regression coverage for _append_unique_text extraction."""

from __future__ import annotations

import argparse
import ast
import importlib.util
import json
from pathlib import Path

APP_PATH = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
MODULE_PATH = Path("spina_app/utilities/notes.py")
FIXTURE_PATH = Path("tools/fixtures/append_unique_text_behavior.json")
TARGET = "_append_unique_text"
IMPORT_LINE = f"from spina_app.utilities.notes import {TARGET}"

CASES = [
    ("both_none", None, None),
    ("both_empty", "", ""),
    ("existing_only", "  old note  ", ""),
    ("addition_only", "", "  new note  "),
    ("append_distinct", "old note", "new note"),
    ("duplicate_exact", "old note", "old note"),
    ("duplicate_substring", "first line\nlate payment reason", "late payment"),
    ("existing_is_substring", "late", "late payment"),
    ("trim_both", "  old  ", "  new  "),
    ("multiline_append", "first\nsecond", "third\nfourth"),
    ("zero_existing", 0, "new"),
    ("zero_addition", "old", 0),
    ("integer_existing", 5, "new"),
    ("integer_addition", "old", 5),
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
        spec = importlib.util.spec_from_file_location("spina_notes_append_test", MODULE_PATH)
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
    for name, existing, addition in CASES:
        try:
            result = fn(existing, addition)
            behavior[name] = {
                "kind": "return",
                "type": f"{type(result).__module__}.{type(result).__qualname__}",
                "repr": repr(result),
            }
        except Exception as exc:
            behavior[name] = {
                "kind": "raise",
                "type": f"{type(exc).__module__}.{type(exc).__qualname__}",
                "repr": repr(exc),
            }
    return {
        "target": TARGET,
        "case_names": [name for name, _, _ in CASES],
        "behavior": behavior,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-fixture", type=Path)
    args = parser.parse_args()

    current = capture_behavior(load_helper())
    if args.write_fixture:
        args.write_fixture.parent.mkdir(parents=True, exist_ok=True)
        args.write_fixture.write_text(json.dumps(current, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return

    expected = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    if current != expected:
        raise AssertionError(
            "_append_unique_text behavior changed\n"
            + json.dumps({"expected": expected, "current": current}, indent=2, ensure_ascii=False)
        )


if __name__ == "__main__":
    main()
