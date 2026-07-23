#!/usr/bin/env python3
"""Behavior regression coverage for _merge_note_dict extraction."""

from __future__ import annotations

import argparse
import ast
import importlib.util
import json
from copy import deepcopy
from pathlib import Path

APP_PATH = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
MODULE_PATH = Path("spina_app/utilities/notes.py")
FIXTURE_PATH = Path("tools/fixtures/merge_note_dict_behavior.json")
TARGET = "_merge_note_dict"
IMPORT_LINE = f"from spina_app.utilities.notes import {TARGET}"

CASES = [
    ("both_none", None, None),
    ("empty_dicts", {}, {}),
    ("default_into_empty", {}, {"__default__": "hello"}),
    ("text_inputs", "old", "new"),
    ("distinct_default", {"__default__": "old"}, {"__default__": "new"}),
    ("duplicate_default", {"__default__": "old"}, {"__default__": "old"}),
    ("substring_default", {"__default__": "late payment reason"}, {"__default__": "late"}),
    ("reverse_substring", {"__default__": "late"}, {"__default__": "late payment"}),
    ("blank_incoming", {"__default__": "old"}, {"__default__": "   "}),
    ("none_incoming", {"__default__": "old"}, {"__default__": None}),
    ("empty_existing_value", {"2026-07-23": " "}, {"2026-07-23": "dated"}),
    ("dated_new_key", {"__default__": "general"}, {"2026-07-23": "dated"}),
    ("dated_conflict", {"2026-07-23": "first"}, {"2026-07-23": "second"}),
    ("numeric_value", {}, {"__default__": 123}),
    ("boolean_value", {}, {"__default__": False}),
    ("nested_value", {}, {"2026-07-23": {"reason": "late"}}),
    ("list_source", {}, ["x", "y"]),
    ("integer_source", {}, 5),
]


def load_notes_module():
    spec = importlib.util.spec_from_file_location("spina_notes_merge_test_module", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load notes utility module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_helper():
    app_source = APP_PATH.read_text(encoding="utf-8")
    tree = ast.parse(app_source)
    matches = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == TARGET]
    imported = IMPORT_LINE in app_source
    notes_module = load_notes_module()

    if len(matches) == 1 and not imported:
        namespace = {
            "_as_note_dict": getattr(notes_module, "_as_note_dict"),
            "_append_unique_text": getattr(notes_module, "_append_unique_text"),
        }
        module = ast.Module(body=[matches[0]], type_ignores=[])
        ast.fix_missing_locations(module)
        exec(compile(module, str(APP_PATH), "exec"), namespace)
        return namespace[TARGET]

    if not matches and imported:
        return getattr(notes_module, TARGET)

    raise RuntimeError(
        f"Unexpected extraction state: definitions={len(matches)}, import_present={imported}"
    )


def capture_behavior(fn) -> dict[str, object]:
    behavior: dict[str, object] = {}
    for name, dst, src in CASES:
        dst_before = deepcopy(dst)
        src_before = deepcopy(src)
        try:
            result = fn(dst, src)
            behavior[name] = {
                "kind": "return",
                "type": f"{type(result).__module__}.{type(result).__qualname__}",
                "repr": repr(result),
                "dst_after": repr(dst),
                "src_after": repr(src),
                "dst_unchanged": dst == dst_before,
                "src_unchanged": src == src_before,
            }
        except Exception as exc:
            behavior[name] = {
                "kind": "raise",
                "type": f"{type(exc).__module__}.{type(exc).__qualname__}",
                "repr": repr(exc),
                "dst_after": repr(dst),
                "src_after": repr(src),
                "dst_unchanged": dst == dst_before,
                "src_unchanged": src == src_before,
            }
    return {
        "target": TARGET,
        "case_names": [name for name, _, _ in CASES],
        "behavior": behavior,
    }


def validate_input_isolation(fn) -> None:
    dst = {"__default__": "old", "nested": {"value": 1}}
    src = {"__default__": "new", "2026-07-23": "dated"}
    dst_before = deepcopy(dst)
    src_before = deepcopy(src)
    result = fn(dst, src)
    if dst != dst_before:
        raise AssertionError("Destination input was mutated")
    if src != src_before:
        raise AssertionError("Source input was mutated")
    if result is dst:
        raise AssertionError("Expected a new destination dictionary")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-fixture", type=Path)
    args = parser.parse_args()

    fn = load_helper()
    validate_input_isolation(fn)
    current = capture_behavior(fn)

    if args.write_fixture:
        args.write_fixture.parent.mkdir(parents=True, exist_ok=True)
        args.write_fixture.write_text(json.dumps(current, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return

    expected = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    if current != expected:
        raise AssertionError(
            "_merge_note_dict behavior changed\n"
            + json.dumps({"expected": expected, "current": current}, indent=2, ensure_ascii=False)
        )


if __name__ == "__main__":
    main()
