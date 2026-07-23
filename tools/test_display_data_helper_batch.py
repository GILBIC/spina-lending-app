#!/usr/bin/env python3
"""Behavior regression test for display/data helper batch 03."""

from __future__ import annotations

import argparse
import ast
import importlib
import json
import sys
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

from extract_pure_helper_batch import inspect  # noqa: E402

DEFAULT_MANIFEST = ROOT / "tools/fixtures/display_data_helper_batch_03_manifest.json"
DEFAULT_FIXTURE = ROOT / "tools/fixtures/display_data_helper_batch_03_behavior.json"


class PairRow:
    def __iter__(self):
        return iter((("x", 1), ("y", 2)))


class FlakyKeysRow:
    def __init__(self):
        self.calls = 0
        self.values = {"a": 10, "b": 20}

    def keys(self):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("first keys call fails")
        return list(self.values)

    def __getitem__(self, key):
        return self.values[key]


class BadRow:
    def __iter__(self):
        raise RuntimeError("not iterable")

    def keys(self):
        raise RuntimeError("no keys")

    def __getitem__(self, key):
        raise KeyError(key)


CASES: dict[str, list[tuple[str, tuple[Any, ...]]]] = {
    "_spina_dash__status_for": [
        ("complete_remaining_zero", (0, 0, 120)),
        ("complete_negative_remaining", (10, -1, 120)),
        ("complete_pct_100", (100, 500, 120)),
        ("complete_precedes_overdue", (100, 500, -10)),
        ("finishing_90", (90, 500, 30)),
        ("finishing_99", (99.9, 500, -1)),
        ("near_75", (75, 500, 30)),
        ("near_precedes_overdue", (80, 500, -1)),
        ("overdue", (50, 500, -1)),
        ("due_today", (50, 500, 0)),
        ("due_in_14", (50, 500, 14)),
        ("in_progress_15", (50, 500, 15)),
        ("empty_days", (50, 500, "")),
        ("none_days", (50, 500, None)),
        ("string_days", (50, 500, "14")),
        ("invalid_days", (50, 500, "soon")),
        ("invalid_pct", ("bad", 500, 30)),
        ("invalid_remaining_becomes_complete", (50, "bad", -1)),
        ("none_values", (None, None, None)),
        ("boolean_values", (True, True, True)),
    ],
    "_spina_perf_dict_rows": [
        ("none", (None,)),
        ("empty", ([],)),
        ("plain_dicts", ([{"a": 1}, {"b": 2}],)),
        ("pair_iterable", ([PairRow()],)),
        ("fallback_keys", ([FlakyKeysRow()],)),
        ("bad_row_skipped", ([{"ok": 1}, BadRow(), {"after": 2}],)),
        ("mixed_rows", ([PairRow(), FlakyKeysRow(), BadRow()],)),
        ("false_value", (False,)),
    ],
    "_spina_crc_fmt_money": [
        ("none", (None,)),
        ("empty", ("",)),
        ("zero", (0,)),
        ("zero_blank", (0, True)),
        ("small_blank", (0.004, True)),
        ("threshold_not_blank", (0.005, True)),
        ("integer", (1234,)),
        ("near_integer", (1234.004,)),
        ("decimal", (1234.25,)),
        ("negative_integer", (-2500,)),
        ("negative_decimal", (-2500.25,)),
        ("numeric_text", ("1250.50",)),
        ("comma_text_invalid", ("1,250.50",)),
        ("invalid_text", ("abc",)),
        ("boolean_true", (True,)),
        ("boolean_false_blank", (False, True)),
        ("list_invalid", ([1, 2],)),
        ("nan_text", ("nan",)),
        ("infinity_text", ("inf",)),
    ],
}


def _load_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_from_source(app_path: Path, name: str) -> Callable[..., Any] | None:
    source = app_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(app_path))
    matches = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]
    if not matches:
        return None
    if len(matches) != 1:
        raise RuntimeError(f"Expected one source definition for {name}, found {len(matches)}")
    exact = ast.get_source_segment(source, matches[0])
    if exact is None:
        raise RuntimeError(f"Could not recover source for {name}")
    namespace: dict[str, Any] = {}
    exec(compile(exact, f"<{name}>", "exec"), namespace)
    return namespace[name]


def _resolve_function(app_path: Path, helper: dict[str, Any]) -> Callable[..., Any]:
    name = str(helper["name"])
    source_function = _resolve_from_source(app_path, name)
    if source_function is not None:
        return source_function
    module = importlib.import_module(str(helper["module"]))
    importlib.reload(module)
    function = getattr(module, name, None)
    if not callable(function):
        raise RuntimeError(f"Could not resolve extracted helper {name}")
    return function


def _type_name(value: Any) -> str:
    cls = type(value)
    return f"{cls.__module__}.{cls.__qualname__}"


def _capture(function: Callable[..., Any], args: tuple[Any, ...]) -> dict[str, str]:
    try:
        value = function(*args)
    except Exception as exc:
        return {
            "kind": "raise",
            "type": _type_name(exc),
            "repr": repr(exc),
        }
    return {
        "kind": "return",
        "type": _type_name(value),
        "repr": repr(value),
    }


def capture_batch(manifest_path: Path) -> dict[str, Any]:
    manifest = _load_manifest(manifest_path)
    app_path = ROOT / str(manifest["app"])
    helper_names = [str(item["name"]) for item in manifest["helpers"]]
    if helper_names != list(CASES):
        raise RuntimeError(
            f"Cases do not match manifest order: manifest={helper_names!r}, cases={list(CASES)!r}"
        )

    behavior: dict[str, Any] = {}
    for helper in manifest["helpers"]:
        name = str(helper["name"])
        function = _resolve_function(app_path, helper)
        behavior[name] = {
            case_name: _capture(function, args)
            for case_name, args in CASES[name]
        }

    return {
        "batch": manifest.get("batch"),
        "helper_names": helper_names,
        "behavior": behavior,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--write-fixture", action="store_true")
    args = parser.parse_args()

    manifest_path = args.manifest.resolve()
    current = capture_batch(manifest_path)

    if args.write_fixture:
        args.fixture.write_text(
            json.dumps(current, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"Wrote behavior fixture: {args.fixture}")
        return 0

    report = inspect(manifest_path)
    if report["state"] != "extracted":
        raise RuntimeError(
            f"Permanent regression test requires extracted state, got {report['state']!r}"
        )

    expected = json.loads(args.fixture.read_text(encoding="utf-8"))
    if current != expected:
        print("Expected:")
        print(json.dumps(expected, indent=2, ensure_ascii=False))
        print("Current:")
        print(json.dumps(current, indent=2, ensure_ascii=False))
        raise SystemExit("Display/data helper batch behavior changed")

    print(
        f"Display/data helper batch matches for {len(current['helper_names'])} helpers: "
        + ", ".join(current["helper_names"])
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
