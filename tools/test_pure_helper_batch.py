#!/usr/bin/env python3
"""Behavior regression test for a guarded pure-helper batch."""

from __future__ import annotations

import argparse
import ast
import importlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

from extract_pure_helper_batch import DEFAULT_MANIFEST, inspect  # noqa: E402

DEFAULT_FIXTURE = ROOT / "tools/fixtures/pure_helper_batch_01_behavior.json"

CASES: dict[str, list[tuple[str, tuple[Any, ...]]]] = {
    "_spina__fmt_client_money": [
        ("none", (None,)),
        ("empty", ("",)),
        ("zero", (0,)),
        ("integer", (1234,)),
        ("decimal", (1234.5,)),
        ("negative_integer", (-2500,)),
        ("negative_decimal", (-2500.25,)),
        ("numeric_text", ("1250.75",)),
        ("comma_text", ("1,250.75",)),
        ("invalid_text", ("abc",)),
        ("boolean_true", (True,)),
        ("list_value", (["x"],)),
    ],
    "_spina_v17_fmt_short_money": [
        ("none", (None,)),
        ("zero", (0,)),
        ("under_thousand", (999,)),
        ("one_thousand", (1000,)),
        ("thousand_decimal", (1549,)),
        ("under_million", (999999,)),
        ("one_million", (1000000,)),
        ("multi_million", (2450000,)),
        ("negative_thousand", (-1250,)),
        ("negative_million", (-1500000,)),
        ("numeric_text", ("2500",)),
        ("invalid_text", ("abc",)),
        ("boolean_true", (True,)),
    ],
    "_spina_v18_fmt_money_compact": [
        ("none", (None,)),
        ("zero", (0,)),
        ("under_thousand", (999,)),
        ("one_thousand", (1000,)),
        ("under_hundred_thousand", (99999,)),
        ("one_hundred_thousand", (100000,)),
        ("under_million", (999999,)),
        ("one_million", (1000000,)),
        ("multi_million", (2750000,)),
        ("negative_hundred_thousand", (-125000,)),
        ("numeric_text", ("1500",)),
        ("invalid_text", ("abc",)),
        ("boolean_true", (True,)),
    ],
    "_spina_v25_parse_count_from_var": [
        ("none", (None,)),
        ("empty", ("",)),
        ("spaces", ("   ",)),
        ("plain_number", ("12",)),
        ("leading_zeroes", ("0012",)),
        ("labelled_count", ("Active clients: 27",)),
        ("multiple_numbers", ("27 active, 3 late",)),
        ("negative_text", ("-15",)),
        ("decimal_text", ("12.5",)),
        ("no_number", ("none",)),
        ("integer", (42,)),
        ("boolean_true", (True,)),
        ("list_value", ([7, 8],)),
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
    namespace: dict[str, Any] = {"re": re}
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
    except Exception as exc:  # regression test intentionally records exceptions
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
            f"Test cases do not match manifest order: manifest={helper_names!r}, cases={list(CASES)!r}"
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
    parser.add_argument("--manifest", type=Path, default=ROOT / DEFAULT_MANIFEST)
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

    extraction_report = inspect(manifest_path)
    if extraction_report["state"] != "extracted":
        raise RuntimeError(
            f"Permanent regression test requires extracted state, got {extraction_report['state']!r}"
        )

    expected = json.loads(args.fixture.read_text(encoding="utf-8"))
    if current != expected:
        print("Expected:")
        print(json.dumps(expected, indent=2, ensure_ascii=False))
        print("Current:")
        print(json.dumps(current, indent=2, ensure_ascii=False))
        raise SystemExit("Pure helper batch behavior changed")

    print(
        f"Pure helper batch behavior matches for {len(current['helper_names'])} helpers: "
        + ", ".join(current["helper_names"])
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
