#!/usr/bin/env python3
"""Headless behavior regression test for Clients and Collector Route Treeview styles."""

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

DEFAULT_MANIFEST = ROOT / "tools/fixtures/client_route_tree_style_batch_12_manifest.json"
DEFAULT_FIXTURE = ROOT / "tools/fixtures/client_route_tree_style_batch_12_behavior.json"

CLIENTS_PALETTE = {
    "panel": "clients-panel",
    "card2": "clients-card2",
    "fg": "clients-fg",
    "blue": "clients-blue",
}
ROUTE_PALETTE = {
    "panel": "route-panel",
    "card2": "route-card2",
    "fg": "route-fg",
    "blue": "route-blue",
}


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


_clients_palette_raises = False
_route_palette_raises = False


def _clients_palette(_self: Any = None) -> dict[str, str]:
    if _clients_palette_raises:
        raise RuntimeError("clients palette unavailable")
    return dict(CLIENTS_PALETTE)


def _route_palette(_self: Any = None) -> dict[str, str]:
    if _route_palette_raises:
        raise RuntimeError("route palette unavailable")
    return dict(ROUTE_PALETTE)


def _reset_runtime(
    *,
    clients_palette_raises: bool = False,
    route_palette_raises: bool = False,
    style_raises: bool = False,
) -> None:
    global _clients_palette_raises, _route_palette_raises
    _clients_palette_raises = clients_palette_raises
    _route_palette_raises = route_palette_raises
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
        "ttk": FakeTtk,
        "_spina_v23_clients_colors": _clients_palette,
        "_spina_v27_route_colors": _route_palette,
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
    module.ttk = FakeTtk
    module._spina_v23_clients_colors = _clients_palette
    module._spina_v27_route_colors = _route_palette
    function = getattr(module, name, None)
    if not callable(function):
        raise RuntimeError(f"Could not resolve extracted helper {name}")
    return function


def _capture_style(function: Callable[..., Any], case: dict[str, Any]) -> dict[str, Any]:
    _reset_runtime(
        clients_palette_raises=bool(case.get("clients_palette_raises")),
        route_palette_raises=bool(case.get("route_palette_raises")),
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
        "_spina_v23_style_clients_tree": [
            {"name": "normal"},
            {"name": "palette_failure", "clients_palette_raises": True},
            {"name": "style_failure", "style_raises": True},
        ],
        "_spina_v27_style_route_trees": [
            {"name": "normal"},
            {"name": "palette_failure", "route_palette_raises": True},
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
        behavior[name] = {
            str(case["name"]): _capture_style(function, case)
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
        raise SystemExit("Clients/Collector Route Treeview style behavior changed")

    print(
        f"Clients/Collector Route Treeview style behavior matches for {len(current['helper_names'])} helpers: "
        + ", ".join(current["helper_names"])
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
