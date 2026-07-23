#!/usr/bin/env python3
"""Headless behavior regression test for SPINA UI card constructors."""

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

DEFAULT_MANIFEST = ROOT / "tools/fixtures/ui_card_constructor_batch_08_manifest.json"
DEFAULT_FIXTURE = ROOT / "tools/fixtures/ui_card_constructor_batch_08_behavior.json"

CASES: dict[str, list[tuple[str, tuple[Any, ...]]]] = {
    "_spina_v21_cash_card": [
        ("defaults", ("Collections",)),
        ("explicit_without_accent", ("Expected", "PHP 1,000.00", "Today", None)),
        ("explicit_with_accent", ("Collected", "PHP 750.00", "75%", "#22c55e")),
    ],
    "_spina_v24_cilog_card": [
        ("defaults", ("Changes",)),
        ("explicit_without_accent", ("Edits", "12", "This month", None)),
        ("explicit_with_accent", ("Updates", "5", "Today", "#60a5fa")),
    ],
}

PALETTES = {
    "cash": {
        "card": "cash-card",
        "border": "cash-border",
        "muted": "cash-muted",
        "fg": "cash-fg",
    },
    "cilog": {
        "card": "cilog-card",
        "border": "cilog-border",
        "muted": "cilog-muted",
        "fg": "cilog-fg",
    },
}


class FakeWidget:
    def __init__(self, kind: str, parent: Any = None, **kwargs: Any) -> None:
        self.kind = kind
        self.parent = parent
        self.kwargs = dict(kwargs)
        self.pack_calls: list[dict[str, Any]] = []
        self.children: list[FakeWidget] = []
        if isinstance(parent, FakeWidget):
            parent.children.append(self)

    def pack(self, **kwargs: Any) -> None:
        self.pack_calls.append(dict(kwargs))


class _WidgetFactory:
    def __init__(self, kind: str) -> None:
        self.kind = kind

    def __call__(self, parent: Any = None, **kwargs: Any) -> FakeWidget:
        return FakeWidget(self.kind, parent, **kwargs)


class FakeTk:
    Frame = _WidgetFactory("Frame")
    Label = _WidgetFactory("Label")


def _cash_palette() -> dict[str, str]:
    return dict(PALETTES["cash"])


def _cilog_palette() -> dict[str, str]:
    return dict(PALETTES["cilog"])


def _load_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _source_function(app_path: Path, name: str) -> Callable[..., Any] | None:
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
    namespace: dict[str, Any] = {
        "tk": FakeTk,
        "_spina_v21_cash_colors": _cash_palette,
        "_spina_v24_cilog_colors": _cilog_palette,
    }
    exec(compile(exact, f"<{name}>", "exec"), namespace)
    return namespace[name]


def _resolve_function(app_path: Path, helper: dict[str, Any]) -> Callable[..., Any]:
    name = str(helper["name"])
    function = _source_function(app_path, name)
    if function is not None:
        return function

    module = importlib.import_module(str(helper["module"]))
    importlib.reload(module)
    module.tk = FakeTk
    module._spina_v21_cash_colors = _cash_palette
    module._spina_v24_cilog_colors = _cilog_palette
    function = getattr(module, name, None)
    if not callable(function):
        raise RuntimeError(f"Could not resolve extracted helper {name}")
    return function


def _widget_summary(widget: FakeWidget) -> dict[str, Any]:
    return {
        "kind": widget.kind,
        "kwargs": widget.kwargs,
        "pack_calls": widget.pack_calls,
        "children": [_widget_summary(child) for child in widget.children],
    }


def _capture(function: Callable[..., Any], args: tuple[Any, ...]) -> dict[str, Any]:
    parent = FakeWidget("Root")
    try:
        result = function(parent, *args)
    except Exception as exc:
        return {
            "kind": "raise",
            "type": f"{type(exc).__module__}.{type(exc).__qualname__}",
            "repr": repr(exc),
        }

    if not isinstance(result, tuple) or len(result) != 3:
        raise RuntimeError(f"Expected a three-widget tuple, got {result!r}")
    frame, value_label, subtitle_label = result
    if not all(isinstance(item, FakeWidget) for item in result):
        raise RuntimeError("Card constructor returned a non-widget value")

    return {
        "kind": "return",
        "tree": _widget_summary(parent),
        "returned": [
            _widget_summary(frame),
            _widget_summary(value_label),
            _widget_summary(subtitle_label),
        ],
        "identity": {
            "frame_is_root_first_child": bool(parent.children and frame is parent.children[0]),
            "value_is_frame_child": value_label in frame.children,
            "subtitle_is_frame_child": subtitle_label in frame.children,
            "value_before_subtitle": (
                frame.children.index(value_label) < frame.children.index(subtitle_label)
            ),
        },
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
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--write-fixture", action="store_true")
    args = parser.parse_args()

    manifest_path = args.manifest.resolve()
    current = json.loads(
        json.dumps(capture_batch(manifest_path), ensure_ascii=False)
    )

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
        raise SystemExit("UI card constructor behavior changed")

    print(
        f"UI card constructor behavior matches for {len(current['helper_names'])} helpers: "
        + ", ".join(current["helper_names"])
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
