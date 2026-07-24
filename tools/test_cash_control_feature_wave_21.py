from __future__ import annotations

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
