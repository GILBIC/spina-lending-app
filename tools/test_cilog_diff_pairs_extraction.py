#!/usr/bin/env python3
"""Behavior regression test for the extracted CILOG diff-pairs helper."""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

APP_PATH = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
MODULE_PATH = Path("spina_app/utilities/diffs.py")
FIXTURE_PATH = Path("tools/fixtures/cilog_diff_pairs_behavior.json")
TARGET = "_spina_cilog_diff_pairs"


def _load_target():
    for path in (APP_PATH, MODULE_PATH):
        if not path.exists():
            continue
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        matches = [
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == TARGET
        ]
        if not matches:
            continue
        if len(matches) != 1:
            raise RuntimeError(f"Expected one {TARGET} in {path}, found {len(matches)}")
        isolated = ast.Module(body=[matches[0]], type_ignores=[])
        ast.fix_missing_locations(isolated)
        namespace: dict[str, object] = {}
        exec(compile(isolated, str(path), "exec"), namespace)
        return namespace[TARGET]
    raise RuntimeError(f"Could not find {TARGET} in app or utility module")


def _cases():
    return [
        ("both_none", None, None),
        ("new_dict_from_none", None, {"b": 2, "a": 1, "id": 99}),
        ("old_dict_to_none", {"b": 2, "a": 1, "id": 99}, None),
        ("scalar_change", "old", "new"),
        ("scalar_same", "same", "same"),
        ("mixed_dict_scalar", {"a": 1}, "value"),
        ("empty_dicts", {}, {}),
        ("id_only_change", {"id": 1}, {"id": 2}),
        ("changed_fields_sorted", {"b": 1, "a": 1}, {"b": 2, "a": 3}),
        ("added_removed", {"a": 1, "remove": 9}, {"a": 1, "add": 7}),
        ("nested_change", {"meta": {"x": 1}}, {"meta": {"x": 2}}),
        ("list_change", {"items": [1, 2]}, {"items": [1, 3]}),
        ("boolean_numeric_equal", {"flag": True}, {"flag": 1}),
        ("none_field_change", {"a": None}, {"a": 0}),
    ]


def _capture(function):
    behavior = {}
    for name, old_obj, new_obj in _cases():
        try:
            result = function(old_obj, new_obj)
            behavior[name] = {
                "kind": "return",
                "type": f"{type(result).__module__}.{type(result).__qualname__}",
                "repr": repr(result),
            }
        except Exception as exc:  # pragma: no cover - behavior capture only
            behavior[name] = {
                "kind": "raise",
                "type": f"{type(exc).__module__}.{type(exc).__qualname__}",
                "repr": repr(exc),
            }
    return {
        "target": TARGET,
        "case_names": [name for name, _old, _new in _cases()],
        "behavior": behavior,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-fixture", type=Path)
    args = parser.parse_args()

    current = _capture(_load_target())
    fixture_path = args.write_fixture or FIXTURE_PATH

    if args.write_fixture:
        fixture_path.parent.mkdir(parents=True, exist_ok=True)
        fixture_path.write_text(
            json.dumps(current, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return 0

    expected = json.loads(fixture_path.read_text(encoding="utf-8"))
    if current != expected:
        print("CILOG diff-pairs behavior changed")
        print(json.dumps({"expected": expected, "current": current}, indent=2, ensure_ascii=False))
        return 1

    print("CILOG diff-pairs behavior matches fixture")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
