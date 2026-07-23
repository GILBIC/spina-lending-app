#!/usr/bin/env python3
"""Behavior regression test for the guarded area-text helper batch."""

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

DEFAULT_MANIFEST = ROOT / "tools/fixtures/area_text_helper_batch_05_manifest.json"
DEFAULT_FIXTURE = ROOT / "tools/fixtures/area_text_helper_batch_05_behavior.json"

CASES: dict[str, list[tuple[str, tuple[Any, ...]]]] = {
    "split_area_main_sub": [
        ("none", (None,)),
        ("empty", ("",)),
        ("spaces", ("   ",)),
        ("plain", ("Cardona",)),
        ("hyphen_spaced", ("Cardona - Looc",)),
        ("slash_spaced", ("Cardona / Looc",)),
        ("pipe_spaced", ("Cardona | Looc",)),
        ("greater_spaced", ("Cardona > Looc",)),
        ("colon_spaced", ("Cardona : Looc",)),
        ("em_dash", ("Cardona — Looc",)),
        ("en_dash", ("Cardona – Looc",)),
        ("single_slash", ("Cardona/Looc",)),
        ("single_pipe", ("Cardona|Looc",)),
        ("single_colon", ("Cardona:Looc",)),
        ("multiple_separators", ("Cardona - Looc / Zone 1",)),
        ("missing_left", ("/ Looc",)),
        ("missing_right", ("Cardona /",)),
        ("numeric", (123,)),
        ("boolean", (True,)),
        ("list", (["Cardona", "Looc"],)),
    ],
    "join_area_main_sub": [
        ("both_none", (None, None)),
        ("both_empty", ("", "")),
        ("main_only", ("Cardona", "")),
        ("sub_only", ("", "Looc")),
        ("both", ("Cardona", "Looc")),
        ("trim", ("  Cardona  ", "  Looc  ")),
        ("numeric", (123, 456)),
        ("boolean", (True, False)),
        ("list", (["Cardona"], ["Looc"])),
    ],
    "_spina_crc_split_area": [
        ("none", (None,)),
        ("plain", ("Cardona",)),
        ("hyphen_spaced", ("Cardona - Looc",)),
        ("slash_single", ("Cardona/Looc",)),
        ("em_dash", ("Cardona — Looc",)),
        ("multiple_separators", ("Cardona - Looc / Zone 1",)),
        ("missing_left", ("/ Looc",)),
        ("numeric", (123,)),
    ],
}


def _load_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _source_namespace(app_path: Path, helper_names: list[str]) -> dict[str, Any] | None:
    source = app_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(app_path))
    nodes = {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in helper_names
    }
    if not nodes:
        return None
    if set(nodes) != set(helper_names):
        raise RuntimeError(f"Mixed source state: found {sorted(nodes)}, expected {helper_names}")
    namespace: dict[str, Any] = {}
    for name in helper_names:
        exact = ast.get_source_segment(source, nodes[name])
        if exact is None:
            raise RuntimeError(f"Could not recover source for {name}")
        exec(compile(exact, f"<{name}>", "exec"), namespace)
    return namespace


def _resolve_functions(manifest_path: Path) -> dict[str, Callable[..., Any]]:
    manifest = _load_manifest(manifest_path)
    app_path = ROOT / str(manifest["app"])
    helper_names = [str(item["name"]) for item in manifest["helpers"]]
    namespace = _source_namespace(app_path, helper_names)
    if namespace is not None:
        return {name: namespace[name] for name in helper_names}

    functions: dict[str, Callable[..., Any]] = {}
    modules: dict[str, Any] = {}
    for helper in manifest["helpers"]:
        module_name = str(helper["module"])
        if module_name not in modules:
            module = importlib.import_module(module_name)
            modules[module_name] = importlib.reload(module)
        function = getattr(modules[module_name], str(helper["name"]), None)
        if not callable(function):
            raise RuntimeError(f"Could not resolve {helper['name']}")
        functions[str(helper["name"])] = function
    return functions


def _type_name(value: Any) -> str:
    cls = type(value)
    return f"{cls.__module__}.{cls.__qualname__}"


def _capture(function: Callable[..., Any], args: tuple[Any, ...]) -> dict[str, str]:
    try:
        value = function(*args)
    except Exception as exc:
        return {"kind": "raise", "type": _type_name(exc), "repr": repr(exc)}
    return {"kind": "return", "type": _type_name(value), "repr": repr(value)}


def _capture_crc_fallback(function: Callable[..., Any], area: Any, mode: str) -> dict[str, str]:
    namespace = function.__globals__
    sentinel = object()
    previous = namespace.get("split_area_main_sub", sentinel)

    def fail_split(_value: Any) -> Any:
        raise RuntimeError("forced split failure")

    try:
        if mode == "missing_helper":
            namespace.pop("split_area_main_sub", None)
        elif mode == "raising_helper":
            namespace["split_area_main_sub"] = fail_split
        else:
            raise RuntimeError(f"Unknown fallback mode: {mode}")
        return _capture(function, (area,))
    finally:
        if previous is sentinel:
            namespace.pop("split_area_main_sub", None)
        else:
            namespace["split_area_main_sub"] = previous


def capture_batch(manifest_path: Path) -> dict[str, Any]:
    manifest = _load_manifest(manifest_path)
    helper_names = [str(item["name"]) for item in manifest["helpers"]]
    if helper_names != list(CASES):
        raise RuntimeError(
            f"Test cases do not match manifest order: manifest={helper_names!r}, cases={list(CASES)!r}"
        )
    functions = _resolve_functions(manifest_path)

    behavior: dict[str, Any] = {}
    for name in helper_names:
        behavior[name] = {
            case_name: _capture(functions[name], args)
            for case_name, args in CASES[name]
        }

    crc = functions["_spina_crc_split_area"]
    behavior["_spina_crc_split_area"]["fallback_missing_helper"] = _capture_crc_fallback(
        crc, "Cardona - Looc", "missing_helper"
    )
    behavior["_spina_crc_split_area"]["fallback_raising_helper"] = _capture_crc_fallback(
        crc, "Cardona/Looc", "raising_helper"
    )

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
        raise SystemExit("Area text-helper behavior changed")

    print(
        f"Area text-helper behavior matches for {len(current['helper_names'])} helpers: "
        + ", ".join(current["helper_names"])
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
