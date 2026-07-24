#!/usr/bin/env python3
"""Headless behavior regression test for legacy Dashboard filter and table-style helpers."""

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

DEFAULT_MANIFEST = ROOT / "tools/fixtures/legacy_dashboard_controls_batch_15_manifest.json"
DEFAULT_FIXTURE = ROOT / "tools/fixtures/legacy_dashboard_controls_batch_15_behavior.json"

PALETTE = {
    "accent": "dash-accent",
    "card2": "dash-card2",
    "fg": "dash-fg",
    "soft": "dash-soft",
    "panel": "dash-panel",
}


class FakeStringVar:
    def __init__(self, value: Any = "") -> None:
        self.value = value

    def get(self) -> Any:
        return self.value


class FakeTk:
    stringvar_calls: list[dict[str, Any]] = []
    raise_on_stringvar = False

    @classmethod
    def StringVar(cls, value: Any = None) -> FakeStringVar:
        cls.stringvar_calls.append({"value": value})
        if cls.raise_on_stringvar:
            raise RuntimeError("StringVar unavailable")
        return FakeStringVar(value)


class FakeButton:
    def __init__(self, name: str, *, raise_on_configure: bool = False) -> None:
        self.name = name
        self.raise_on_configure = raise_on_configure
        self.configure_calls: list[dict[str, Any]] = []

    def configure(self, **kwargs: Any) -> None:
        if self.raise_on_configure:
            raise RuntimeError(f"configure failed: {self.name}")
        self.configure_calls.append(dict(kwargs))


class FakeStyle:
    def __init__(self) -> None:
        self.configure_calls: list[dict[str, Any]] = []
        self.map_calls: list[dict[str, Any]] = []

    def configure(self, style_name: str, **kwargs: Any) -> None:
        self.configure_calls.append({"style": style_name, "kwargs": dict(kwargs)})

    def map(self, style_name: str, **kwargs: Any) -> None:
        self.map_calls.append({"style": style_name, "kwargs": dict(kwargs)})


class FakeTtk:
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


def _palette(_self: Any = None) -> dict[str, str]:
    if _palette_raises:
        raise RuntimeError("Dashboard palette unavailable")
    return dict(PALETTE)


def _reset_runtime(
    *,
    palette_raises: bool = False,
    stringvar_raises: bool = False,
    style_raises: bool = False,
) -> None:
    global _palette_raises
    _palette_raises = palette_raises
    FakeTk.stringvar_calls = []
    FakeTk.raise_on_stringvar = stringvar_raises
    FakeTtk.style_instances = []
    FakeTtk.raise_on_style = style_raises


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
        "ttk": FakeTtk,
        "_spina_v17_dash_colors": _palette,
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
    module._spina_v17_dash_colors = _palette
    function = getattr(module, name, None)
    if not callable(function):
        raise RuntimeError(f"Could not resolve extracted helper {name}")
    return function


def _capture_filter(function: Callable[..., Any], case: dict[str, Any]) -> dict[str, Any]:
    _reset_runtime(
        palette_raises=bool(case.get("palette_raises")),
        stringvar_raises=bool(case.get("stringvar_raises")),
    )

    holder = type("Holder", (), {})()
    if not case.get("missing_var"):
        holder.dashboard_loan_filter_var = FakeStringVar(case.get("value", "All"))

    buttons: dict[str, FakeButton] = {}
    if not case.get("missing_buttons"):
        failure_key = case.get("button_failure_key")
        for key in ("All", "REG", "7x7"):
            buttons[key] = FakeButton(key, raise_on_configure=(key == failure_key))
        holder._dash_filter_buttons = buttons

    try:
        result = function(holder)
    except Exception as exc:
        return {
            "kind": "raise",
            "type": f"{type(exc).__module__}.{type(exc).__qualname__}",
            "repr": repr(exc),
        }

    return {
        "kind": "return",
        "result": result,
        "stringvar_calls": list(FakeTk.stringvar_calls),
        "buttons": {
            key: list(button.configure_calls)
            for key, button in buttons.items()
        },
    }


def _capture_style(function: Callable[..., Any], case: dict[str, Any]) -> dict[str, Any]:
    _reset_runtime(
        palette_raises=bool(case.get("palette_raises")),
        style_raises=bool(case.get("style_raises")),
    )
    try:
        result = function(object())
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
        "_spina_v17_update_filter_buttons": [
            {"name": "regular_selected", "value": "REG"},
            {"name": "all_selected", "value": "All"},
            {"name": "blank_defaults_all", "value": ""},
            {"name": "missing_var_defaults_all", "missing_var": True},
            {"name": "missing_buttons", "value": "REG", "missing_buttons": True},
            {"name": "palette_failure", "value": "REG", "palette_raises": True},
            {"name": "stringvar_failure", "value": "REG", "stringvar_raises": True},
            {"name": "button_failure", "value": "REG", "button_failure_key": "REG"},
        ],
        "_spina_v17_style_dashboard_table": [
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
        capture = _capture_filter if name == "_spina_v17_update_filter_buttons" else _capture_style
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
        raise SystemExit("Legacy Dashboard control behavior changed")

    print(
        f"Legacy Dashboard control behavior matches for {len(current['helper_names'])} helpers: "
        + ", ".join(current["helper_names"])
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
