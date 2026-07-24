#!/usr/bin/env python3
"""Headless behavior regression test for the legacy Dashboard summary-card constructor."""

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

DEFAULT_MANIFEST = ROOT / "tools/fixtures/legacy_dashboard_card_batch_16_manifest.json"
DEFAULT_FIXTURE = ROOT / "tools/fixtures/legacy_dashboard_card_batch_16_behavior.json"

PALETTE = {
    "card": "dash-card",
    "border": "dash-border",
    "muted": "dash-muted",
    "fg": "dash-fg",
}

CASES = [
    {"name": "defaults", "args": ["Active clients"]},
    {"name": "explicit", "args": ["Collections", "PHP 12,345.67", "Today"]},
    {"name": "blank_values", "args": ["Status", "", ""]},
    {"name": "palette_failure", "args": ["Active clients"], "palette_raises": True},
]


class FakeWidget:
    def __init__(self, kind: str, parent: Any = None, **kwargs: Any) -> None:
        self.kind = kind
        self.parent = parent
        self.kwargs = dict(kwargs)
        self.pack_calls: list[dict[str, Any]] = []
        self.grid_propagate_calls: list[Any] = []
        self.children: list[FakeWidget] = []
        if isinstance(parent, FakeWidget):
            parent.children.append(self)

    def pack(self, **kwargs: Any) -> None:
        self.pack_calls.append(dict(kwargs))

    def grid_propagate(self, value: Any) -> None:
        self.grid_propagate_calls.append(value)


class _WidgetFactory:
    def __init__(self, kind: str) -> None:
        self.kind = kind

    def __call__(self, parent: Any = None, **kwargs: Any) -> FakeWidget:
        return FakeWidget(self.kind, parent, **kwargs)


class FakeTk:
    Frame = _WidgetFactory("Frame")
    Label = _WidgetFactory("Label")


_palette_raises = False


def _dashboard_palette() -> dict[str, str]:
    if _palette_raises:
        raise RuntimeError("Dashboard palette unavailable")
    return dict(PALETTE)


def _load_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _source_function(app_path: Path, name: str) -> Callable[..., Any] | None:
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
    namespace: dict[str, Any] = {
        "tk": FakeTk,
        "_spina_v17_dash_colors": _dashboard_palette,
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
    module._spina_v17_dash_colors = _dashboard_palette
    function = getattr(module, name, None)
    if not callable(function):
        raise RuntimeError(f"Could not resolve extracted helper {name}")
    return function


def _widget_summary(widget: FakeWidget) -> dict[str, Any]:
    return {
        "kind": widget.kind,
        "kwargs": widget.kwargs,
        "pack_calls": widget.pack_calls,
        "grid_propagate_calls": widget.grid_propagate_calls,
        "children": [_widget_summary(child) for child in widget.children],
    }


def _capture(function: Callable[..., Any], case: dict[str, Any]) -> dict[str, Any]:
    global _palette_raises
    _palette_raises = bool(case.get("palette_raises"))
    parent = FakeWidget("Root")
    try:
        result = function(parent, *tuple(case["args"]))
    except Exception as exc:
        return {
            "kind": "raise",
            "type": f"{type(exc).__module__}.{type(exc).__qualname__}",
            "repr": repr(exc),
            "tree": _widget_summary(parent),
        }

    if not isinstance(result, tuple) or len(result) != 3:
        raise RuntimeError(f"Expected a three-widget tuple, got {result!r}")
    frame, value_label, subtitle_label = result
    if not all(isinstance(item, FakeWidget) for item in result):
        raise RuntimeError("Legacy Dashboard card returned a non-widget value")

    title_labels = [
        child
        for child in frame.children
        if child.kind == "Label" and child.kwargs.get("text") == case["args"][0]
    ]

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
            "title_label_count": len(title_labels),
            "value_is_frame_child": value_label in frame.children,
            "subtitle_is_frame_child": subtitle_label in frame.children,
            "child_order_is_title_value_subtitle": bool(
                len(frame.children) == 3
                and title_labels
                and frame.children[0] is title_labels[0]
                and frame.children[1] is value_label
                and frame.children[2] is subtitle_label
            ),
        },
    }


def capture_batch(manifest_path: Path) -> dict[str, Any]:
    manifest = _load_manifest(manifest_path)
    app_path = ROOT / str(manifest["app"])
    helpers = list(manifest["helpers"])
    if [str(item["name"]) for item in helpers] != ["_spina_v17_make_card"]:
        raise RuntimeError("Unexpected Wave 16 manifest helper list")
    function = _resolve_function(app_path, helpers[0])
    return {
        "batch": manifest.get("batch"),
        "helper_names": ["_spina_v17_make_card"],
        "behavior": {
            "_spina_v17_make_card": {
                str(case["name"]): _capture(function, case)
                for case in CASES
            }
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--write-fixture", action="store_true")
    args = parser.parse_args()

    manifest_path = args.manifest.resolve()
    current = json.loads(json.dumps(capture_batch(manifest_path), ensure_ascii=False))

    if args.write_fixture:
        args.fixture.parent.mkdir(parents=True, exist_ok=True)
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
        raise SystemExit("Legacy Dashboard card behavior changed")

    print("Legacy Dashboard card behavior matches for _spina_v17_make_card")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
