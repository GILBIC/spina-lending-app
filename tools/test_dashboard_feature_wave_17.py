#!/usr/bin/env python3
"""Regression checks for the Wave 17 Dashboard feature-level extraction."""

from __future__ import annotations

import ast
import hashlib
import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

APP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MANIFEST = ROOT / "tools/fixtures/dashboard_feature_wave_17_manifest.json"


class Var:
    def __init__(self, value=None):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


def _functions(path: Path):
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(path))
    return text, {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }


def verify_static_extraction():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    app_text, app_functions = _functions(APP)
    module_path = ROOT / manifest["module_path"]
    module_text, module_functions = _functions(module_path)

    names = [item["name"] for item in manifest["helpers"]]
    for item in manifest["helpers"]:
        name = item["name"]
        if name in app_functions:
            raise RuntimeError(f"{name} still has a top-level definition in the main source")
        node = module_functions.get(name)
        if node is None:
            raise RuntimeError(f"{name} is missing from the Dashboard feature module")
        segment = ast.get_source_segment(module_text, node)
        if segment is None:
            raise RuntimeError(f"Could not recover module source for {name}")
        digest = hashlib.sha256(segment.encode("utf-8")).hexdigest()
        if digest != item["sha256"]:
            raise RuntimeError(f"Source body changed for {name}: {digest}")
        if ast.unparse(node.args) != item["signature"]:
            raise RuntimeError(f"Signature changed for {name}")

    if "from spina_app.tabs.dashboard import (" not in app_text:
        raise RuntimeError("Main source does not import the Dashboard feature group")
    if manifest["helper_count"] != 5 or manifest["moved_source_lines"] != 462:
        raise RuntimeError("Unexpected Wave 17 extraction size")
    return names


def verify_visible_rows(module):
    module.tk.StringVar = Var
    rows = [
        {"name": "Ana", "area": "North", "loan_type": "Regular", "status": "Due Soon"},
        {"name": "Ben", "area": "South", "loan_type": "7x7", "status": "Complete"},
        {"name": "Cara", "area": "North", "loan_type": "7x7", "status": "Overdue"},
    ]
    app = SimpleNamespace(
        _dashboard_rows=rows,
        dashboard_loan_filter_var=Var("All"),
        dashboard_status_filter_var=Var("All Active"),
        dashboard_search_var=Var(""),
    )
    assert module._spina_v17_visible_dashboard_rows(app) == rows

    app.dashboard_loan_filter_var.set("7x7")
    assert [r["name"] for r in module._spina_v17_visible_dashboard_rows(app)] == ["Ben", "Cara"]

    app.dashboard_status_filter_var.set("Priority")
    assert [r["name"] for r in module._spina_v17_visible_dashboard_rows(app)] == ["Cara"]

    app.dashboard_loan_filter_var.set("All")
    app.dashboard_status_filter_var.set("All Active")
    app.dashboard_search_var.set("north")
    assert [r["name"] for r in module._spina_v17_visible_dashboard_rows(app)] == ["Ana", "Cara"]


def verify_refresh_bridge(module):
    calls = []
    logs = []
    original_populate = module._spina_v17_populate_dashboard_tree
    try:
        module._spina_v17_populate_dashboard_tree = lambda app: calls.append(("populate", list(app._dashboard_rows)))
        module.configure_legacy_dashboard_feature(
            fetch_rows=lambda app: [{"name": "Loaded"}],
            log_exc=lambda context, exc=None: logs.append((context, type(exc).__name__ if exc else None)),
        )
        app = SimpleNamespace(tab_dashboard=object(), status_var=Var(""))
        module._spina_v17_refresh_dashboard(app)
        assert app._dashboard_rows == [{"name": "Loaded"}]
        assert calls == [("populate", [{"name": "Loaded"}])]
        assert app.status_var.get() == "Dashboard refreshed."

        def broken_fetch(_app):
            raise RuntimeError("fetch failed")

        module.configure_legacy_dashboard_feature(fetch_rows=broken_fetch)
        app2 = SimpleNamespace(tab_dashboard=object(), status_var=Var(""))
        module._spina_v17_refresh_dashboard(app2)
        assert app2.status_var.get() == "Dashboard refresh failed. See data/spina_app.log."
        assert logs and logs[-1][0] == "v17.refresh_dashboard"
    finally:
        module._spina_v17_populate_dashboard_tree = original_populate


def main():
    names = verify_static_extraction()
    module = importlib.import_module("spina_app.tabs.dashboard")
    verify_visible_rows(module)
    verify_refresh_bridge(module)
    print(f"Dashboard Wave 17 extraction verified: {len(names)} helpers, 462 source lines moved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
