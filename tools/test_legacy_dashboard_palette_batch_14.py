#!/usr/bin/env python3
"""Behavior regression test for legacy Dashboard palette batch 14."""

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

DEFAULT_MANIFEST = ROOT / "tools/fixtures/legacy_dashboard_palette_batch_14_manifest.json"
DEFAULT_FIXTURE = ROOT / "tools/fixtures/legacy_dashboard_palette_batch_14_behavior.json"
EXPECTED_HELPERS = [
    "_spina_v17_dash_colors",
    "_spina_v18_dashboard_palette",
]


class Holder:
    def __init__(self, theme: Any, *, set_attribute: bool = True) -> None:
        if set_attribute:
            self.ui_theme = theme


class BadString:
    def __str__(self) -> str:
        raise RuntimeError("theme string failed")


def _stable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _stable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_stable(item) for item in value]
    return repr(value)


def _type_name(value: Any) -> str:
    cls = type(value)
    return f"{cls.__module__}.{cls.__qualname__}"


def _load_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_from_source(app_path: Path, name: str) -> Callable[..., Any] | None:
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
        raise RuntimeError(f"Could not recover exact source for {name}")
    namespace: dict[str, Any] = {}
    exec(compile(exact, f"<{name}>", "exec"), namespace)
    function = namespace.get(name)
    if not callable(function):
        raise RuntimeError(f"Source helper did not compile: {name}")
    return function


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


def _cases() -> dict[str, tuple[Any, ...]]:
    return {
        "none": (None,),
        "missing_attribute": (Holder(None, set_attribute=False),),
        "dark": (Holder("dark"),),
        "dark_upper": (Holder("DARK"),),
        "light": (Holder("light"),),
        "light_upper": (Holder("LIGHT"),),
        "light_prefix": (Holder("l"),),
        "blank": (Holder(""),),
        "unknown_theme": (Holder("solarized"),),
        "non_string": (Holder(123),),
        "string_failure": (Holder(BadString()),),
    }


def _capture_call(function: Callable[..., Any], args: tuple[Any, ...]) -> dict[str, Any]:
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
        "value": _stable(value),
    }


def capture_batch(manifest_path: Path) -> dict[str, Any]:
    manifest = _load_manifest(manifest_path)
    app_path = ROOT / str(manifest["app"])
    helper_names = [str(item["name"]) for item in manifest["helpers"]]
    if helper_names != EXPECTED_HELPERS:
        raise RuntimeError(f"Unexpected helper order: {helper_names!r}")

    behavior: dict[str, Any] = {}
    for helper in manifest["helpers"]:
        name = str(helper["name"])
        function = _resolve_function(app_path, helper)
        behavior[name] = {
            case_name: _capture_call(function, args)
            for case_name, args in _cases().items()
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
    fixture_path = args.fixture.resolve()
    current = capture_batch(manifest_path)

    if args.write_fixture:
        fixture_path.parent.mkdir(parents=True, exist_ok=True)
        fixture_path.write_text(
            json.dumps(current, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"Wrote behavior fixture: {fixture_path}")
        return 0

    extraction_report = inspect(manifest_path)
    if extraction_report["state"] != "extracted":
        raise RuntimeError(
            f"Permanent regression test requires extracted state, got {extraction_report['state']!r}"
        )

    expected = json.loads(fixture_path.read_text(encoding="utf-8"))
    if current != expected:
        print("Expected:")
        print(json.dumps(expected, indent=2, ensure_ascii=False))
        print("Current:")
        print(json.dumps(current, indent=2, ensure_ascii=False))
        raise SystemExit("Legacy Dashboard palette behavior changed")

    helper_names = current["helper_names"]
    print(
        f"Legacy Dashboard palette behavior matches for {len(helper_names)} helpers: "
        + ", ".join(helper_names)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
