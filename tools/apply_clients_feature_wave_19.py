from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

MAIN = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
DEST = Path("spina_app/tabs/clients.py")
MANIFEST = Path("tools/fixtures/clients_feature_wave_19_manifest.json")
TEST = Path("tools/test_clients_feature_wave_19.py")

SELECTED = [
    "_spina_v23_button",
    "_spina_v23_card",
    "_spina_v23_selected_name_lt",
    "_spina_v23_refresh_client_profile",
    "_spina_v23_build_clients_tab",
    "_spina_v23_entry",
    "_spina_v23_update_client_cards",
]

EXPECTED_HASHES = {
    "_spina_v23_button": "6494efce07479ceb08d40d3e4915e6d935a34bd142d484ab02fa2779256ba8f5",
    "_spina_v23_card": "8f652d54bfffe6bba7a6173661f52ffb586428f65c31ee0dca18755a78945119",
    "_spina_v23_selected_name_lt": "d8b06aec702eff2fba8a64e2f5cde9b5abad2547285ef5b2012a961d019aad9c",
    "_spina_v23_refresh_client_profile": "18a4893cb4cc8c08996e9e4c85d0d0ccc39a213a8246591af9fefa76c44d51a3",
    "_spina_v23_build_clients_tab": "9fd162cf2011af50b77a590e6494d1dd3fe118b3045b252f0b73e2d859a6aa47",
    "_spina_v23_entry": "7616aaf2e0dbea43205b394953ebe1098107abccc6074f99275eedff09b96949",
    "_spina_v23_update_client_cards": "d5557fe858d777ca046c6089432257596abd9d66615dba06bb737192bc2e98d5",
}

PROTECTED = [
    "_spina_v23_client_loan_summary",
    "_spina_v23_client_form",
    "_spina_v23_add_client_dialog",
    "_spina_v23_on_client_edit",
]

DEPENDENCIES = (
    "_app__norm_lt_value",
    "_spina_v23_client_loan_summary",
    "_log_exc",
)


def source_for(lines: list[str], node: ast.FunctionDef) -> str:
    return "\n".join(lines[node.lineno - 1 : node.end_lineno])


def top_level_functions(tree: ast.Module) -> dict[str, list[ast.FunctionDef]]:
    out: dict[str, list[ast.FunctionDef]] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.setdefault(node.name, []).append(node)
    return out


def main() -> None:
    text = MAIN.read_text(encoding="utf-8")
    lines = text.splitlines()
    tree = ast.parse(text)
    functions = top_level_functions(tree)

    selected_nodes: dict[str, ast.FunctionDef] = {}
    records = []
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

    summary_node = functions["_spina_v23_client_loan_summary"][0]
    selected_sources = [source_for(lines, selected_nodes[name]) for name in SELECTED]
    moved_lines = sum(r["source_lines"] for r in records)
    if moved_lines != 387:
        raise RuntimeError(f"Expected 387 moved lines, found {moved_lines}")

    module_header = '''"""Modern Clients tab presentation extracted from the SPINA desktop entry module.

Client application-form validation, add/update database writes, picture/file handling,
loan balance and interest calculations, and the original refresh chain remain owned by
the desktop application. This module owns only Clients presentation and display helpers.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Mapping

from spina_app.theme_palettes import _spina_v23_clients_colors
from spina_app.ui_controls import _spina_v23_style_clients_tree
from spina_app.utilities.formatting import _spina_v23_money, _spina_v23_percent

_REQUIRED_DEPENDENCIES = (
    "_app__norm_lt_value",
    "_spina_v23_client_loan_summary",
    "_log_exc",
)


def configure_clients_dependencies(namespace: Mapping[str, Any]) -> tuple[str, ...]:
    """Bind application-owned callbacks used by the Clients presentation module."""
    missing = []
    for name in _REQUIRED_DEPENDENCIES:
        value = namespace.get(name)
        if value is None:
            missing.append(name)
            continue
        globals()[name] = value
    return tuple(missing)


'''
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(module_header + "\n\n".join(selected_sources) + "\n", encoding="utf-8")

    import_block = "\n".join(
        [
            "from spina_app.tabs.clients import (",
            "    configure_clients_dependencies,",
            *[f"    {name}," for name in SELECTED],
            ")",
        ]
    )
    configure_block = "\n".join(
        [
            "",
            "_spina_v23_clients_missing_dependencies = configure_clients_dependencies(globals())",
            "",
        ]
    )

    ranges = sorted((node.lineno, node.end_lineno) for node in selected_nodes.values())
    first_start = min(start for start, _ in ranges)
    skipped = set()
    for start, end in ranges:
        skipped.update(range(start, end + 1))

    output: list[str] = []
    for line_number, line in enumerate(lines, start=1):
        if line_number == first_start:
            output.extend(import_block.splitlines())
        if line_number not in skipped:
            output.append(line)
        if line_number == summary_node.end_lineno:
            output.extend(configure_block.splitlines())

    new_text = "\n".join(output) + "\n"
    new_tree = ast.parse(new_text)
    new_functions = top_level_functions(new_tree)
    for name in SELECTED:
        if name in new_functions:
            raise RuntimeError(f"Selected definition still remains in desktop source: {name}")
    for name in PROTECTED:
        if len(new_functions.get(name, [])) != 1:
            raise RuntimeError(f"Protected function changed during extraction: {name}")
    if "configure_clients_dependencies(globals())" not in new_text:
        raise RuntimeError("Clients dependency bridge was not inserted")
    MAIN.write_text(new_text, encoding="utf-8")

    manifest = {
        "wave": 19,
        "feature": "clients_presentation",
        "destination": str(DEST).replace("\\", "/"),
        "function_count": len(SELECTED),
        "moved_source_lines": moved_lines,
        "dependencies_kept_in_desktop": list(DEPENDENCIES),
        "protected_functions_kept_in_desktop": PROTECTED,
        "functions": records,
        "status": "extracted",
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    test_source = r'''from __future__ import annotations

import ast
import hashlib
import importlib
import json
from pathlib import Path

MAIN = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
MODULE = Path("spina_app/tabs/clients.py")
MANIFEST = Path("tools/fixtures/clients_feature_wave_19_manifest.json")


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
    def __init__(self, value=None):
        self.value = value
    def get(self):
        return self.value
    def set(self, value):
        self.value = value


class FakeLabel:
    def __init__(self):
        self.text = None
    def configure(self, **kwargs):
        if "text" in kwargs:
            self.text = kwargs["text"]


class FakeTree:
    def __init__(self, selected=True):
        self.selected = selected
    def selection(self):
        return ("row1",) if self.selected else ()
    def item(self, iid, option):
        if option == "values":
            return ("Alice", "Area 1")
        if option == "tags":
            return ("lt:7x7",)
        return ()
    def get_children(self):
        return ("row1", "row2")


class FakeDB:
    def get_client_info(self, name, loan_type=None, include_archived=False):
        return {"name": name, "loan_type": loan_type, "principal": 1000}


class FakeApp:
    def __init__(self, selected=True):
        self.clients_tree = FakeTree(selected=selected)
        self.db = FakeDB()
        self._clients_stat_labels = {
            key: (FakeLabel(), FakeLabel())
            for key in ("rows", "view", "selected", "balance")
        }
    def _mode_filter(self):
        return "Regular"


def main():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    main_text, main_defs = defs(MAIN)
    module_text, module_defs = defs(MODULE)

    selected = [item["name"] for item in manifest["functions"]]
    assert manifest["function_count"] == 7
    assert manifest["moved_source_lines"] == 387
    for item in manifest["functions"]:
        name = item["name"]
        assert name not in main_defs, name
        assert name in module_defs, name
        digest = hashlib.sha256(module_defs[name][1].encode("utf-8")).hexdigest()
        assert digest == item["sha256"], (name, digest)

    for name in manifest["protected_functions_kept_in_desktop"]:
        assert name in main_defs, name
    assert "from spina_app.tabs.clients import (" in main_text
    assert "configure_clients_dependencies(globals())" in main_text

    clients = importlib.import_module("spina_app.tabs.clients")
    missing = clients.configure_clients_dependencies({})
    assert set(missing) == {
        "_app__norm_lt_value",
        "_spina_v23_client_loan_summary",
        "_log_exc",
    }

    clients.configure_clients_dependencies(
        {
            "_app__norm_lt_value": lambda app, value: str(value or "Regular"),
            "_spina_v23_client_loan_summary": lambda app, info: {"balance": 321.0},
            "_log_exc": lambda *args, **kwargs: None,
        }
    )

    app = FakeApp(selected=False)
    assert clients._spina_v23_selected_name_lt(app) == ("", "Regular")

    app = FakeApp(selected=True)
    assert clients._spina_v23_selected_name_lt(app) == ("Alice", "7x7")
    assert clients._spina_v23_update_client_cards(app) is None
    cards = app._clients_stat_labels
    assert cards["rows"][0].text == "2"
    assert cards["view"][0].text == "Regular"
    assert cards["selected"][0].text == "Alice"
    assert cards["selected"][1].text == "7x7"
    assert cards["balance"][0].text not in (None, "", "—")

    print("Clients feature Wave 19 regression passed")


if __name__ == "__main__":
    main()
'''
    TEST.write_text(test_source, encoding="utf-8")
    print(f"Extracted {len(SELECTED)} Clients presentation functions and {moved_lines} lines")


if __name__ == "__main__":
    main()
