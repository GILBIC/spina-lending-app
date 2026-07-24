from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

MAIN = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
MODULE = Path("spina_app/tabs/cash_control.py")
MANIFEST = Path("tools/fixtures/cash_control_feature_wave_21_manifest.json")
TEST = Path("tools/test_cash_control_feature_wave_21.py")

TARGETS = (
    "_spina_v21_cash_build_tab",
    "_spina_v21_cash_draw_charts",
)
EXPECTED_HASHES = {
    "_spina_v21_cash_build_tab": "193bcec0ceea15620e063b61b5e9e5685b04e511663396f621ace808592e965e",
    "_spina_v21_cash_draw_charts": "a6081d06e9aa1ae2865817743a6d55011d928cb38c5a54b5e162860b78bc54f0",
}
PROTECTED = (
    "_spina_v21_cash_refresh",
    "_spina_cashctl_get_average_collection",
    "_spina_cashctl_get_collection_totals",
    "_spina_cashctl_reserve_rows",
)
BRIDGED = (
    "_log_exc",
    "_spina_v21_cash_money_short",
    "_spina_v21_cash_round_rect",
)


def source_for(lines: list[str], node: ast.AST) -> str:
    return "\n".join(lines[node.lineno - 1 : node.end_lineno])


def functions_for(text: str) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    tree = ast.parse(text)
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def main() -> None:
    text = MAIN.read_text(encoding="utf-8")
    lines = text.splitlines()
    functions = functions_for(text)

    missing = [name for name in TARGETS + PROTECTED + BRIDGED if name not in functions]
    if missing:
        raise RuntimeError(f"Missing expected current-main functions: {missing}")

    first_line = min(functions[name].lineno for name in TARGETS)
    for name in BRIDGED:
        if functions[name].lineno >= first_line:
            raise RuntimeError(f"Dependency {name} is not defined before extraction point")

    sources: dict[str, str] = {}
    manifest_functions = []
    for name in TARGETS:
        node = functions[name]
        src = source_for(lines, node)
        digest = hashlib.sha256(src.encode("utf-8")).hexdigest()
        if digest != EXPECTED_HASHES[name]:
            raise RuntimeError(f"Source hash mismatch for {name}: {digest}")
        sources[name] = src
        manifest_functions.append({
            "name": name,
            "start_line": node.lineno,
            "end_line": node.end_lineno,
            "source_lines": node.end_lineno - node.lineno + 1,
            "sha256": digest,
        })

    module_header = '''"""Cash Control presentation shell extracted from the SPINA desktop entry module.

Collection totals, reserve calculations, refresh orchestration, and database access remain
owned by the desktop application. This module owns tab construction and chart rendering only.
"""

from __future__ import annotations

from datetime import date
import tkinter as tk
from tkinter import ttk
from typing import Any, Mapping

from spina_app.theme_palettes import _spina_v21_cash_colors
from spina_app.ui_cards import _spina_v21_cash_card
from spina_app.ui_controls import _spina_v21_build_labeled_entry, _spina_v21_style_cash_table

_REQUIRED_DEPENDENCIES = (
    "_log_exc",
    "_spina_v21_cash_money_short",
    "_spina_v21_cash_round_rect",
)


def configure_cash_control_dependencies(namespace: Mapping[str, Any]) -> tuple[str, ...]:
    """Bind application-owned display and logging helpers used by Cash Control."""
    missing = []
    for name in _REQUIRED_DEPENDENCIES:
        value = namespace.get(name)
        if value is None:
            missing.append(name)
            continue
        globals()[name] = value
    return tuple(missing)
'''
    module_text = module_header.rstrip() + "\n\n\n" + "\n\n\n".join(sources[name] for name in TARGETS) + "\n"
    ast.parse(module_text)

    bridge = '''from spina_app.tabs.cash_control import (
    configure_cash_control_dependencies,
    _spina_v21_cash_build_tab,
    _spina_v21_cash_draw_charts,
)
_cash_control_missing_dependencies = configure_cash_control_dependencies(globals())
if _cash_control_missing_dependencies:
    raise RuntimeError(
        "Cash Control module dependencies unavailable: "
        + ", ".join(_cash_control_missing_dependencies)
    )
'''

    mutable = lines[:]
    ordered = sorted((functions[name] for name in TARGETS), key=lambda node: node.lineno, reverse=True)
    first_target_line = min(node.lineno for node in ordered)
    for node in ordered:
        replacement = bridge.rstrip().splitlines() if node.lineno == first_target_line else []
        mutable[node.lineno - 1 : node.end_lineno] = replacement
    new_main = "\n".join(mutable) + ("\n" if text.endswith("\n") else "")
    ast.parse(new_main)

    new_functions = functions_for(new_main)
    still_present = [name for name in TARGETS if name in new_functions]
    if still_present:
        raise RuntimeError(f"Target definitions remain in desktop source: {still_present}")
    missing_protected = [name for name in PROTECTED if name not in new_functions]
    if missing_protected:
        raise RuntimeError(f"Protected functions were removed: {missing_protected}")
    if "from spina_app.tabs.cash_control import (" not in new_main:
        raise RuntimeError("Cash Control import bridge missing from desktop source")

    manifest = {
        "wave": 21,
        "feature": "cash_control_presentation_shell",
        "destination": str(MODULE).replace("\\", "/"),
        "function_count": len(TARGETS),
        "moved_source_lines": sum(item["source_lines"] for item in manifest_functions),
        "dependencies_kept_in_desktop": list(BRIDGED),
        "protected_functions_kept_in_desktop": list(PROTECTED),
        "functions": manifest_functions,
        "status": "extracted",
    }

    test_text = '''from __future__ import annotations

import ast
import importlib
from pathlib import Path

MAIN = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
MODULE = Path("spina_app/tabs/cash_control.py")
TARGETS = {
    "_spina_v21_cash_build_tab",
    "_spina_v21_cash_draw_charts",
}
PROTECTED = {
    "_spina_v21_cash_refresh",
    "_spina_cashctl_get_average_collection",
    "_spina_cashctl_get_collection_totals",
    "_spina_cashctl_reserve_rows",
}


def top_level_functions(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


class FakeCanvas:
    def __init__(self, width=420, height=190):
        self.width = width
        self.height = height
        self.operations = []

    def delete(self, *args):
        self.operations.append(("delete", args))

    def configure(self, **kwargs):
        self.operations.append(("configure", kwargs))

    def winfo_width(self):
        return self.width

    def winfo_height(self):
        return self.height

    def create_text(self, *args, **kwargs):
        self.operations.append(("text", args, kwargs))
        return len(self.operations)


class Dummy:
    ui_theme = "light"

    def __init__(self):
        self.cashctl_flow_canvas = FakeCanvas()
        self.cashctl_collection_canvas = FakeCanvas()
        self.cashctl_risk_canvas = FakeCanvas()


def main() -> None:
    main_functions = top_level_functions(MAIN)
    module_functions = top_level_functions(MODULE)
    assert TARGETS.isdisjoint(main_functions), TARGETS & main_functions
    assert TARGETS.issubset(module_functions), TARGETS - module_functions
    assert PROTECTED.issubset(main_functions), PROTECTED - main_functions

    desktop_text = MAIN.read_text(encoding="utf-8")
    assert "from spina_app.tabs.cash_control import (" in desktop_text
    assert "configure_cash_control_dependencies(globals())" in desktop_text

    module = importlib.import_module("spina_app.tabs.cash_control")
    errors = []
    rounded = []

    def log_exc(where, exc):
        errors.append((where, exc))

    def money_short(value):
        return f"PHP {float(value or 0):,.0f}"

    def round_rect(canvas, *args, **kwargs):
        rounded.append((canvas, args, kwargs))
        return len(rounded)

    missing = module.configure_cash_control_dependencies({
        "_log_exc": log_exc,
        "_spina_v21_cash_money_short": money_short,
        "_spina_v21_cash_round_rect": round_rect,
    })
    assert missing == (), missing

    dummy = Dummy()
    module._spina_v21_cash_draw_charts(dummy, {
        "current_available": 10000,
        "net_need": 2500,
        "buffer_now": 1000,
        "safe_now": 6500,
        "regular": 4200,
        "7x7": 1800,
        "other": 200,
        "reserve_rows": [
            {"status": "Near Completion", "reserve_amount": 1500},
            {"status": "Overdue", "reserve_amount": 900},
        ],
    })
    assert not errors, errors
    assert rounded, "chart bars were not drawn"
    assert any(op[0] == "text" for op in dummy.cashctl_flow_canvas.operations)
    assert any(op[0] == "text" for op in dummy.cashctl_collection_canvas.operations)
    assert any(op[0] == "text" for op in dummy.cashctl_risk_canvas.operations)

    build_source = MODULE.read_text(encoding="utf-8")
    assert "command=self.refresh_cash_control" in build_source
    assert "_spina_v21_style_cash_table(self)" in build_source
    print("Cash Control feature Wave 21 regression passed")


if __name__ == "__main__":
    main()
'''
    ast.parse(test_text)

    MODULE.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    TEST.parent.mkdir(parents=True, exist_ok=True)
    MODULE.write_text(module_text, encoding="utf-8")
    MAIN.write_text(new_main, encoding="utf-8")
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    TEST.write_text(test_text, encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
