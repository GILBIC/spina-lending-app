#!/usr/bin/env python3
"""Behavior regression test for payment schedule normalizer batch 06."""

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

DEFAULT_MANIFEST = ROOT / "tools/fixtures/payment_schedule_normalizer_batch_06_manifest.json"
DEFAULT_FIXTURE = ROOT / "tools/fixtures/payment_schedule_normalizer_batch_06_behavior.json"


class BrokenText:
    def __str__(self) -> str:
        raise RuntimeError("string conversion failed")


class MondayText:
    def __str__(self) -> str:
        return "Monday"


def _type_name(value: Any) -> str:
    cls = type(value)
    return f"{cls.__module__}.{cls.__qualname__}"


def _resolve_source_function(app_path: Path, name: str) -> Callable[..., Any] | None:
    source = app_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(app_path))
    matches = [
        node
        for node in tree.body
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
    source_function = _resolve_source_function(app_path, name)
    if source_function is not None:
        return source_function
    module = importlib.import_module(str(helper["module"]))
    importlib.reload(module)
    function = getattr(module, name, None)
    if not callable(function):
        raise RuntimeError(f"Could not resolve extracted helper {name}")
    return function


def _capture(function: Callable[[Any], Any], value: Any) -> dict[str, Any]:
    try:
        result = function(value)
    except Exception as exc:
        return {
            "kind": "raise",
            "type": _type_name(exc),
            "repr": repr(exc),
        }
    return {
        "kind": "return",
        "type": _type_name(result),
        "repr": repr(result),
    }


def _weekday_cases() -> list[tuple[str, Any]]:
    return [
        ("none", None),
        ("empty", ""),
        ("spaces", "   "),
        ("monday", "Monday"),
        ("short_monday", "mon"),
        ("uppercase_monday", "MONDAY"),
        ("tuesday", "Tuesday"),
        ("wednesday", "Wednesday"),
        ("thursday", "Thursday"),
        ("friday", "Friday"),
        ("saturday", "Saturday"),
        ("sunday", "Sunday"),
        ("trimmed", "  Friday  "),
        ("prefix_only", "Thu extra"),
        ("unknown", "Holiday"),
        ("number", 123),
        ("boolean", True),
        ("object_text", MondayText()),
        ("broken_text", BrokenText()),
    ]


def _day_of_month_cases() -> list[tuple[str, Any]]:
    return [
        ("none", None),
        ("empty", ""),
        ("spaces", "   "),
        ("one_int", 1),
        ("thirty_one_int", 31),
        ("zero", 0),
        ("thirty_two", 32),
        ("negative", -1),
        ("one_text", "1"),
        ("fifteen_text", " 15 "),
        ("thirty_one_text", "31"),
        ("decimal_text", "15.0"),
        ("letters", "abc"),
        ("boolean", True),
        ("broken_text", BrokenText()),
    ]


def capture_batch(manifest_path: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    app_path = ROOT / str(manifest["app"])
    names = [str(item["name"]) for item in manifest["helpers"]]
    expected_names = ["_spina__norm_weekday", "_spina__norm_dom"]
    if names != expected_names:
        raise RuntimeError(f"Unexpected helper order: {names!r}")

    behavior: dict[str, Any] = {}
    for helper in manifest["helpers"]:
        name = str(helper["name"])
        function = _resolve_function(app_path, helper)
        cases = _weekday_cases() if name == "_spina__norm_weekday" else _day_of_month_cases()
        behavior[name] = {
            case_name: _capture(function, value)
            for case_name, value in cases
        }

    return {
        "batch": manifest.get("batch"),
        "helper_names": names,
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
        raise SystemExit("Payment schedule normalizer behavior changed")

    print(
        f"Payment schedule normalizer behavior matches for {len(current['helper_names'])} helpers: "
        + ", ".join(current["helper_names"])
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
