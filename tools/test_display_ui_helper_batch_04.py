#!/usr/bin/env python3
"""Behavior regression test for accelerated display/UI helper batch 04."""

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

DEFAULT_MANIFEST = ROOT / "tools/fixtures/display_ui_helper_batch_04_manifest.json"
DEFAULT_FIXTURE = ROOT / "tools/fixtures/display_ui_helper_batch_04_behavior.json"

FORMAT_CASES: dict[str, list[tuple[str, tuple[Any, ...]]]] = {
    "_spina_dash__fmt_money": [
        ("none", (None,)),
        ("empty", ("",)),
        ("zero", (0,)),
        ("integer", (1234,)),
        ("decimal", (1234.5,)),
        ("negative", (-2500.25,)),
        ("numeric_text", ("1250.75",)),
        ("invalid_text", ("abc",)),
        ("boolean_true", (True,)),
    ],
    "_spina_cashctl__fmt_pct": [
        ("none", (None,)),
        ("empty", ("",)),
        ("zero", (0,)),
        ("integer", (25,)),
        ("decimal", (12.3456,)),
        ("negative", (-5,)),
        ("numeric_text", ("7.5",)),
        ("invalid_text", ("abc",)),
        ("boolean_true", (True,)),
    ],
}


class FakeLabel:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[dict[str, Any]] = []

    def configure(self, **kwargs: Any) -> None:
        self.calls.append(_stable(kwargs))
        if self.fail:
            raise RuntimeError("configure failed")


class Holder:
    pass


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


def _source_namespace() -> dict[str, Any]:
    formatting = importlib.import_module("spina_app.utilities.formatting")
    importlib.reload(formatting)
    return {
        "fmt_currency": formatting.fmt_currency,
        "_spina_dash__fmt_pct": formatting._spina_dash__fmt_pct,
    }


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
    namespace = _source_namespace()
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


def _capture_call(function: Callable[..., Any], args: tuple[Any, ...]) -> dict[str, Any]:
    try:
        value = function(*args)
    except Exception as exc:
        return {"kind": "raise", "type": _type_name(exc), "repr": repr(exc)}
    return {"kind": "return", "type": _type_name(value), "repr": repr(value)}


def _capture_card(function: Callable[..., Any], case: str) -> dict[str, Any]:
    holder = Holder()
    value_label: FakeLabel | None = None
    subtitle_label: FakeLabel | None = None

    if case == "value_and_subtitle":
        value_label = FakeLabel()
        subtitle_label = FakeLabel()
        holder._cashctl_cards = {"total": (value_label, subtitle_label)}
        args = (holder, "total", 1234, "Active")
    elif case == "value_only":
        value_label = FakeLabel()
        subtitle_label = FakeLabel()
        holder._cashctl_cards = {"total": (value_label, subtitle_label)}
        args = (holder, "total", None, None)
    elif case == "missing_key":
        value_label = FakeLabel()
        subtitle_label = FakeLabel()
        holder._cashctl_cards = {"other": (value_label, subtitle_label)}
        args = (holder, "total", "X", "Y")
    elif case == "missing_attribute":
        args = (holder, "total", "X", "Y")
    elif case == "value_label_failure":
        value_label = FakeLabel(fail=True)
        subtitle_label = FakeLabel()
        holder._cashctl_cards = {"total": (value_label, subtitle_label)}
        args = (holder, "total", "X", "Y")
    else:
        raise RuntimeError(f"Unknown card case: {case}")

    try:
        value = function(*args)
        result: dict[str, Any] = {
            "kind": "return",
            "type": _type_name(value),
            "repr": repr(value),
        }
    except Exception as exc:
        result = {"kind": "raise", "type": _type_name(exc), "repr": repr(exc)}
    result["value_calls"] = None if value_label is None else value_label.calls
    result["subtitle_calls"] = None if subtitle_label is None else subtitle_label.calls
    return result


def capture_batch(manifest_path: Path) -> dict[str, Any]:
    manifest = _load_manifest(manifest_path)
    app_path = ROOT / str(manifest["app"])
    helper_names = [str(item["name"]) for item in manifest["helpers"]]
    expected_names = [
        "_spina_dash__fmt_money",
        "_spina_cashctl__fmt_pct",
        "_spina_v21_cash_set_card",
    ]
    if helper_names != expected_names:
        raise RuntimeError(f"Unexpected helper order: {helper_names!r}")

    behavior: dict[str, Any] = {}
    for helper in manifest["helpers"]:
        name = str(helper["name"])
        function = _resolve_function(app_path, helper)
        if name in FORMAT_CASES:
            behavior[name] = {
                case_name: _capture_call(function, args)
                for case_name, args in FORMAT_CASES[name]
            }
        elif name == "_spina_v21_cash_set_card":
            behavior[name] = {
                case: _capture_card(function, case)
                for case in (
                    "value_and_subtitle",
                    "value_only",
                    "missing_key",
                    "missing_attribute",
                    "value_label_failure",
                )
            }
        else:
            raise RuntimeError(f"No behavior cases for {name}")

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
        raise SystemExit("Display/UI helper batch 04 behavior changed")

    print(
        f"Display/UI helper behavior matches for {len(current['helper_names'])} helpers: "
        + ", ".join(current["helper_names"])
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
