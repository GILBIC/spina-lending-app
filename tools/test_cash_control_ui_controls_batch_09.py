#!/usr/bin/env python3
"""Headless behavior regression test for Cash Control UI controls."""

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

DEFAULT_MANIFEST = ROOT / "tools/fixtures/cash_control_ui_controls_batch_09_manifest.json"
DEFAULT_FIXTURE = ROOT / "tools/fixtures/cash_control_ui_controls_batch_09_behavior.json"

PALETTE = {
    "panel": "cash-panel",
    "muted": "cash-muted",
    "fg": "cash-fg",
    "card2": "cash-card2",
    "button": "cash-button",
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


class FakeStyle:
    def __init__(self) -> None:
        self.configure_calls: list[dict[str, Any]] = []
        self.map_calls: list[dict[str, Any]] = []

    def configure(self, style_name: str, **kwargs: Any) -> None:
        self.configure_calls.append({"style": style_name, "kwargs": dict(kwargs)})

    def map(self, style_name: str, **kwargs: Any) -> None:
        self.map_calls.append({"style": style_name, "kwargs": dict(kwargs)})


class FakeTtk:
    Entry = _WidgetFactory("Entry")
    style_instances: list[FakeStyle] = []
    raise_on_style = False

    @classmethod
    def Style(cls) -> FakeStyle:
        if cls.raise_on_style:
            raise RuntimeError("style unavailable")
        style = FakeStyle()
        cls.style_instances.append(style)
        return style


_palette_raises = False


def _cash_palette(_self: Any = None) -> dict[str, str]:
    if _palette_raises:
        raise RuntimeError("palette unavailable")
    return dict(PALETTE)


def _reset_runtime(*, palette_raises: bool = False, style_raises: bool = False) -> None:
    global _palette_raises
    _palette_raises = palette_raises
    FakeTtk.style_instances = []
    FakeTtk.raise_on_style = style_raises


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
        "ttk": FakeTtk,
        "_spina_v21_cash_colors": _cash_palette,
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
    module.ttk = FakeTtk
    module._spina_v21_cash_colors = _cash_palette
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


def _capture_builder(function: Callable[..., Any], case: dict[str, Any]) -> dict[str, Any]:
    _reset_runtime(palette_raises=bool(case.get("palette_raises")))
    parent = FakeWidget("Root")
    args = tuple(case["args"])
    try:
        result = function(parent, *args)
    except Exception as exc:
        return {
            "kind": "raise",
            "type": f"{type(exc).__module__}.{type(exc).__qualname__}",
            "repr": repr(exc),
            "tree": _widget_summary(parent),
        }

    if not isinstance(result, tuple) or len(result) != 2:
        raise RuntimeError(f"Expected a two-widget tuple, got {result!r}")
    box, entry = result
    if not isinstance(box, FakeWidget) or not isinstance(entry, FakeWidget):
        raise RuntimeError("Labeled-entry helper returned a non-widget value")

    return {
        "kind": "return",
        "tree": _widget_summary(parent),
        "returned": [_widget_summary(box), _widget_summary(entry)],
        "identity": {
            "box_is_root_first_child": bool(parent.children and box is parent.children[0]),
            "entry_is_box_child": entry in box.children,
            "entry_is_last_box_child": bool(box.children and entry is box.children[-1]),
        },
    }


def _capture_style(function: Callable[..., Any], case: dict[str, Any]) -> dict[str, Any]:
    _reset_runtime(
        palette_raises=bool(case.get("palette_raises")),
        style_raises=bool(case.get("style_raises")),
    )
    owner = object()
    try:
        result = function(owner)
    except Exception as exc:
        return {
            "kind": "raise",
            "type": f"{type(exc).__module__}.{type(exc).__qualname__}",
            "repr": repr(exc),
        }

    return {
        "kind": "return",
        "result": result,
        "styles": [
            {
                "configure_calls": style.configure_calls,
                "map_calls": style.map_calls,
            }
            for style in FakeTtk.style_instances
        ],
    }


def capture_batch(manifest_path: Path) -> dict[str, Any]:
    manifest = _load_manifest(manifest_path)
    app_path = ROOT / str(manifest["app"])
    cases = {
        "_spina_v21_build_labeled_entry": [
            {"name": "default_width", "args": ["Daily Amount", "daily-var"]},
            {"name": "custom_width", "args": ["Average Days", "days-var", 24]},
            {
                "name": "palette_failure",
                "args": ["Expected", "expected-var"],
                "palette_raises": True,
            },
        ],
        "_spina_v21_style_cash_table": [
            {"name": "normal"},
            {"name": "palette_failure", "palette_raises": True},
            {"name": "style_failure", "style_raises": True},
        ],
    }

    helper_names = [str(item["name"]) for item in manifest["helpers"]]
    if helper_names != list(cases):
        raise RuntimeError(
            f"Test cases do not match manifest order: manifest={helper_names!r}, cases={list(cases)!r}"
        )

    behavior: dict[str, Any] = {}
    for helper in manifest["helpers"]:
        name = str(helper["name"])
        function = _resolve_function(app_path, helper)
        capture = _capture_builder if name.endswith("build_labeled_entry") else _capture_style
        behavior[name] = {
            str(case["name"]): capture(function, case)
            for case in cases[name]
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
    current = json.loads(json.dumps(capture_batch(manifest_path), ensure_ascii=False))

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
        raise SystemExit("Cash Control UI-control behavior changed")

    print(
        f"Cash Control UI-control behavior matches for {len(current['helper_names'])} helpers: "
        + ", ".join(current["helper_names"])
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
