#!/usr/bin/env python3
"""Regression test for Cash Control input normalizer batch 07."""

from __future__ import annotations

import argparse
import ast
import importlib
import json
import sys
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tools")]
from extract_pure_helper_batch import inspect  # noqa: E402

MANIFEST = ROOT / "tools/fixtures/cash_control_input_normalizer_batch_07_manifest.json"
FIXTURE = ROOT / "tools/fixtures/cash_control_input_normalizer_batch_07_behavior.json"

PARSE_CASES = {
    "none": (None,),
    "empty": ("",),
    "spaces": ("   ",),
    "zero": (0,),
    "integer": (1234,),
    "decimal": (12.5,),
    "comma_text": ("1,234.50",),
    "negative": ("-25.75",),
    "invalid": ("abc",),
    "true": (True,),
    "false": (False,),
}

RANGE_CASES = {
    "none": (None, 10),
    "empty": ("", 10),
    "invalid": ("abc", 10),
    "valid": ("25", 10),
    "comma": ("1,234", 10),
    "round_5_6": ("5.6", 10),
    "round_4_5": ("4.5", 10),
    "round_5_5": ("5.5", 10),
    "below_min": ("0", 10),
    "negative": ("-50", 10),
    "above_max": ("999", 10),
    "zero_min": ("0", 5, 0, 10),
    "negative_min": ("-3", 5, -5, 10),
    "custom_max": ("20", 5, 0, 10),
    "equal_bounds": ("9", 5, 7, 7),
    "reversed_bounds": ("0", 5, 10, 3),
    "true": (True, 10),
}


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _functions(manifest: dict[str, Any]) -> dict[str, Callable[..., Any]]:
    names = [str(item["name"]) for item in manifest["helpers"]]
    app = ROOT / str(manifest["app"])
    source = app.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(app))
    nodes = {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    }
    if nodes:
        if set(nodes) != set(names):
            raise RuntimeError(f"Mixed source state: {sorted(nodes)}")
        namespace: dict[str, Any] = {}
        for name in names:
            text = ast.get_source_segment(source, nodes[name])
            if text is None:
                raise RuntimeError(f"Missing source for {name}")
            exec(compile(text, f"<{name}>", "exec"), namespace)
        return {name: namespace[name] for name in names}

    module = importlib.import_module(str(manifest["helpers"][0]["module"]))
    importlib.reload(module)
    return {name: getattr(module, name) for name in names}


def _capture(function: Callable[..., Any], args: tuple[Any, ...]) -> dict[str, str]:
    try:
        value = function(*args)
        return {
            "kind": "return",
            "type": f"{type(value).__module__}.{type(value).__qualname__}",
            "repr": repr(value),
        }
    except Exception as exc:
        return {
            "kind": "raise",
            "type": f"{type(exc).__module__}.{type(exc).__qualname__}",
            "repr": repr(exc),
        }


def capture(manifest_path: Path) -> dict[str, Any]:
    manifest = _load(manifest_path)
    names = [str(item["name"]) for item in manifest["helpers"]]
    expected = ["_spina_cashctl__parse_amount", "_spina_cashctl__int_range"]
    if names != expected:
        raise RuntimeError(f"Unexpected helper order: {names}")
    functions = _functions(manifest)
    return {
        "batch": manifest.get("batch"),
        "helper_names": names,
        "behavior": {
            names[0]: {key: _capture(functions[names[0]], args) for key, args in PARSE_CASES.items()},
            names[1]: {key: _capture(functions[names[1]], args) for key, args in RANGE_CASES.items()},
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--fixture", type=Path, default=FIXTURE)
    parser.add_argument("--write-fixture", action="store_true")
    args = parser.parse_args()
    current = capture(args.manifest.resolve())
    if args.write_fixture:
        args.fixture.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote behavior fixture: {args.fixture}")
        return 0
    if inspect(args.manifest.resolve())["state"] != "extracted":
        raise RuntimeError("Permanent test requires extracted state")
    expected = _load(args.fixture)
    if current != expected:
        raise SystemExit("Cash Control input normalizer behavior changed")
    print("Cash Control input normalizer behavior matches")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
