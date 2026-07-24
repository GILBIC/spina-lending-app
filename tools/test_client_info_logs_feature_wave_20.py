from __future__ import annotations

import ast
from datetime import date
import hashlib
import importlib
import json
from pathlib import Path

MAIN = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
MODULE = Path("spina_app/tabs/client_info_logs.py")
MANIFEST = Path("tools/fixtures/client_info_logs_feature_wave_20_manifest.json")


def defs(path: Path):
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    tree = ast.parse(text)
    out = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            out[node.name] = (node, "\n".join(lines[node.lineno - 1 : node.end_lineno]))
    return text, out


class FakeVar:
    def __init__(self):
        self.value = None
    def set(self, value):
        self.value = value


class FakeApp:
    def __init__(self, built=True):
        self._spina_client_info_logs_built = built
        self.db = object()
        self.status_var = FakeVar()
        self.render_calls = 0
    def render_client_info_logs(self):
        self.render_calls += 1


def main():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    main_text, main_defs = defs(MAIN)
    _, module_defs = defs(MODULE)

    assert manifest["function_count"] == 7
    assert manifest["moved_source_lines"] == 516
    for item in manifest["functions"]:
        name = item["name"]
        assert name not in main_defs, name
        assert name in module_defs, name
        digest = hashlib.sha256(module_defs[name][1].encode("utf-8")).hexdigest()
        assert digest == item["sha256"], (name, digest)

    for name in manifest["protected_functions_kept_in_desktop"]:
        assert name in main_defs, name
    assert "from spina_app.tabs.client_info_logs import (" in main_text
    assert "configure_client_info_logs_dependencies(globals())" in main_text

    cilog = importlib.import_module("spina_app.tabs.client_info_logs")
    missing = cilog.configure_client_info_logs_dependencies({})
    assert set(missing) == {"_log_exc", "_spina_cilog_fetch_rows"}

    log_calls = []
    rows = [{"client": "Alice", "action": "ADD", "field": "Area", "when": "today"}]
    cilog.configure_client_info_logs_dependencies(
        {
            "_log_exc": lambda *args: log_calls.append(args),
            "_spina_cilog_fetch_rows": lambda db, limit=0: list(rows),
        }
    )

    colors = {
        "green": "g", "blue": "b", "orange": "o", "purple": "p",
        "red": "r", "yellow": "y", "muted": "m",
    }
    assert cilog._spina_v24_cilog_action_color("ADD", colors) == "g"
    assert cilog._spina_v24_cilog_action_color("DELETE", colors) == "r"
    assert cilog._spina_v24_cilog_action_color("unknown", colors) == "m"

    original_parse_day = cilog._spina_v24_cilog_parse_day
    cilog._spina_v24_cilog_parse_day = lambda value: date.today() if value == "today" else None
    stats = cilog._spina_v24_cilog_stats(rows)
    cilog._spina_v24_cilog_parse_day = original_parse_day
    assert stats["total"] == 1
    assert stats["clients"] == 1
    assert stats["today"] == 1
    assert stats["actions"] == {"ADD": 1}

    app = FakeApp(built=False)
    assert cilog._spina_v24_refresh_client_info_logs(app) is None
    assert app.render_calls == 0

    app = FakeApp(built=True)
    assert cilog._spina_v24_refresh_client_info_logs(app) is None
    assert app._spina_cilog_all_rows == rows
    assert app.render_calls == 1
    assert app.status_var.value == "Client Info Logs refreshed."

    print("Client Information Log feature Wave 20 regression passed")


if __name__ == "__main__":
    main()
