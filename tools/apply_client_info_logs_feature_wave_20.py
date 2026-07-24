from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

MAIN = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
DEST = Path("spina_app/tabs/client_info_logs.py")
MANIFEST = Path("tools/fixtures/client_info_logs_feature_wave_20_manifest.json")
TEST = Path("tools/test_client_info_logs_feature_wave_20.py")

SELECTED = [
    "_spina_v24_cilog_action_color",
    "_spina_v24_cilog_stats",
    "_spina_v24_cilog_draw_charts",
    "_spina_v24_cilog_update_cards",
    "_spina_v24_build_client_info_logs_tab",
    "_spina_v24_render_client_info_logs",
    "_spina_v24_refresh_client_info_logs",
]

EXPECTED_HASHES = {
    "_spina_v24_cilog_action_color": "fa180fe725a7d21bc2483a2bd6103ebd8f3a8985572a17fe3a4fad4cdf4aebc2",
    "_spina_v24_cilog_stats": "b79e70845eb5faa7981d329f4197652392898f1c368b3ec5a543e85d91b9e16e",
    "_spina_v24_cilog_draw_charts": "fe3b6488edbf484013b13a1af858ee6308d8d9fbc1b6c56b85eb3d5aac21e033",
    "_spina_v24_cilog_update_cards": "e0f5702652a4c8a00973231bc9378c7600c4715d93163d9e2a313669fc3d5a6f",
    "_spina_v24_build_client_info_logs_tab": "2fb6156b4e72e6a5c17b9a788405d4b007e72ccaae64419bb4a18f6c25f5ac91",
    "_spina_v24_render_client_info_logs": "c4837132333d1bc760f8b3f3c39b898248e86d7dcd85af1e9067340f6a533f77",
    "_spina_v24_refresh_client_info_logs": "7458df955bed836d9ddb2c2d114b8da4bbf787f25f594da8fbbb1169a9578cdc",
}

PROTECTED = ["_spina_cilog_fetch_rows"]
DEPENDENCIES = ("_log_exc", "_spina_cilog_fetch_rows")


def source_for(lines: list[str], node: ast.AST) -> str:
    return "\n".join(lines[node.lineno - 1 : node.end_lineno])


def top_level_functions(tree: ast.Module) -> dict[str, list[ast.AST]]:
    out: dict[str, list[ast.AST]] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.setdefault(node.name, []).append(node)
    return out


def main() -> None:
    text = MAIN.read_text(encoding="utf-8")
    lines = text.splitlines()
    tree = ast.parse(text)
    functions = top_level_functions(tree)

    selected_nodes: dict[str, ast.AST] = {}
    records: list[dict[str, object]] = []
    for name in SELECTED:
        matches = functions.get(name, [])
        if len(matches) != 1:
            raise RuntimeError(f"Expected one top-level {name}, found {len(matches)}")
        node = matches[0]
        src = source_for(lines, node)
        digest = hashlib.sha256(src.encode("utf-8")).hexdigest()
        if digest != EXPECTED_HASHES[name]:
            raise RuntimeError(f"Source guard failed for {name}: {digest}")
        selected_nodes[name] = node
        records.append(
            {
                "name": name,
                "start_line": node.lineno,
                "end_line": node.end_lineno,
                "source_lines": node.end_lineno - node.lineno + 1,
                "sha256": digest,
            }
        )

    for name in PROTECTED:
        if len(functions.get(name, [])) != 1:
            raise RuntimeError(f"Protected function missing or duplicated: {name}")

    moved_lines = sum(int(item["source_lines"]) for item in records)
    if moved_lines != 516:
        raise RuntimeError(f"Expected 516 moved lines, found {moved_lines}")

    module_header = '''"""Client Information Log presentation extracted from the SPINA desktop entry module.

Database row fetching and application logging remain owned by the desktop application.
This module owns only CILog tab construction, charts, cards, rendering, and refresh orchestration.
"""

from __future__ import annotations

from datetime import date, timedelta
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Mapping

from spina_app.theme_palettes import _spina_v24_cilog_colors
from spina_app.ui_cards import _spina_v24_cilog_card
from spina_app.ui_controls import _spina_v24_cilog_button, _spina_v24_cilog_style_tree
from spina_app.ui_helpers import _spina_v24_cilog_round_rect, _spina_v24_cilog_set_card
from spina_app.utilities.dates import _spina_v24_cilog_parse_day

_REQUIRED_DEPENDENCIES = (
    "_log_exc",
    "_spina_cilog_fetch_rows",
)


def configure_client_info_logs_dependencies(namespace: Mapping[str, Any]) -> tuple[str, ...]:
    """Bind application-owned callbacks used by the CILog presentation module."""
    missing = []
    for name in _REQUIRED_DEPENDENCIES:
        value = namespace.get(name)
        if value is None:
            missing.append(name)
            continue
        globals()[name] = value
    return tuple(missing)


'''

    selected_sources = [source_for(lines, selected_nodes[name]) for name in SELECTED]
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(module_header + "\n\n".join(selected_sources) + "\n", encoding="utf-8")

    import_block = "\n".join(
        [
            "from spina_app.tabs.client_info_logs import (",
            "    configure_client_info_logs_dependencies,",
            *[f"    {name}," for name in SELECTED],
            ")",
            "",
            "_spina_v24_cilog_missing_dependencies = configure_client_info_logs_dependencies(globals())",
        ]
    )

    ranges = sorted((node.lineno, node.end_lineno) for node in selected_nodes.values())
    first_start = min(start for start, _ in ranges)
    skipped: set[int] = set()
    for start, end in ranges:
        skipped.update(range(start, end + 1))

    output: list[str] = []
    for line_number, line in enumerate(lines, start=1):
        if line_number == first_start:
            output.extend(import_block.splitlines())
        if line_number not in skipped:
            output.append(line)

    new_text = "\n".join(output) + "\n"
    new_tree = ast.parse(new_text)
    new_functions = top_level_functions(new_tree)
    for name in SELECTED:
        if name in new_functions:
            raise RuntimeError(f"Selected definition still remains in desktop source: {name}")
    for name in PROTECTED:
        if len(new_functions.get(name, [])) != 1:
            raise RuntimeError(f"Protected function changed during extraction: {name}")
    if "configure_client_info_logs_dependencies(globals())" not in new_text:
        raise RuntimeError("CILog dependency bridge was not inserted")
    MAIN.write_text(new_text, encoding="utf-8")

    manifest = {
        "wave": 20,
        "feature": "client_information_log_presentation",
        "destination": str(DEST).replace("\\", "/"),
        "function_count": len(SELECTED),
        "moved_source_lines": moved_lines,
        "dependencies_kept_in_desktop": list(DEPENDENCIES),
        "protected_functions_kept_in_desktop": PROTECTED,
        "functions": records,
        "status": "extracted",
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    test_source = r'''from __future__ import annotations

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
'''
    TEST.write_text(test_source, encoding="utf-8")
    print(f"Extracted {len(SELECTED)} CILog presentation functions and {moved_lines} lines")


if __name__ == "__main__":
    main()
