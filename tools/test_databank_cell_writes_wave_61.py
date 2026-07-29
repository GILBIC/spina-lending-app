"""Permanent exact-source regression for Wave 61 Data Bank writes."""
from __future__ import annotations

import ast
import hashlib
import importlib
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE_PATH = ROOT / "spina_app" / "databank_cell_writes.py"
DELETE_DAY_MODULE_PATH = ROOT / "spina_app" / "databank_delete_day.py"
TARGETS = ['_save_cell_edit', 'delete_selected_cell', '_mark_missed_for_selected']
EXPECTED = {'_save_cell_edit': {'lines': 84, 'source_sha256': '3f421b85935c6bdb2f9a5e53a689a81a362a3332889104b858d2b5e3689c7410', 'dedented_sha256': '817aa342b4a960d1b53d0056589c2ce20ab7b26780c5675c7d76a4921337aead', 'signature': 'self, client, day, dt_str, ent_widget', 'calls': ['_log_suppressed_once', 'dict', 'ent_widget.destroy', 'ent_widget.get', 'float', 'get', 'getattr', 'messagebox.showerror', 'replace', 'row.keys', 'self._pick_missed_reason', 'self.db.add_or_update_transaction', 'self.db.get_transaction', 'self.refresh_data_grid', 'simpledialog.askstring', 'str', 'strip'], 'db_calls': ['self.db.add_or_update_transaction', 'self.db.get_transaction']}, 'delete_selected_cell': {'lines': 88, 'source_sha256': '218ac3dadc0dfd0540b27b1cac968da8a6cf1b2197f0973b90577810e7097d6a', 'dedented_sha256': '4d27860a520a0474b54ab11c46d3cdc67a0ff15ab3297dcba45c2813bcbf0df0', 'signature': 'self, *_', 'calls': ['_date', '_log_suppressed_once', 'getattr', 'hasattr', 'int', 'messagebox.showerror', 'messagebox.showinfo', 'self._update_data_toolbar', 'self.days_tree.get_children', 'self.days_tree.set', 'self.db.delete_transaction', 'self.db.get_transaction', 'self.refresh_data_grid', 'strftime'], 'db_calls': ['self.db.delete_transaction', 'self.db.get_transaction']}, '_mark_missed_for_selected': {'lines': 71, 'source_sha256': 'df6545048882965daf68fca634445086426e358ca0b39fa4f319d865c648be67', 'dedented_sha256': '77c06f387f8902b78b683074d302cea98569535181549167fb42a88a9e391342', 'signature': 'self', 'calls': ['_date', '_log_suppressed_once', 'dict', 'get', 'getattr', 'int', 'messagebox.showerror', 'messagebox.showinfo', 'replace', 'row.keys', 'self._mode_filter', 'self._pick_missed_reason', 'self.db.add_or_update_transaction', 'self.db.get_transaction', 'self.refresh_data_grid', 'simpledialog.askstring', 'str', 'strftime', 'strip'], 'db_calls': ['self.db.add_or_update_transaction', 'self.db.get_transaction']}}


def sha(source: str) -> str:
    return hashlib.sha256(source.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def dotted(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = dotted(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return None


def main() -> None:
    module_text = MODULE_PATH.read_text(encoding="utf-8")
    module_lines = module_text.splitlines(keepends=True)
    module_tree = ast.parse(module_text)
    module_functions = {
        node.name: node for node in module_tree.body if isinstance(node, ast.FunctionDef)
    }
    imported = importlib.import_module("spina_app.databank_cell_writes")
    assert imported.DATABANK_CELL_WRITE_METHODS == EXPECTED

    for name in TARGETS:
        node = module_functions[name]
        source = "".join(module_lines[node.lineno - 1: node.end_lineno])
        data = EXPECTED[name]
        assert node.end_lineno - node.lineno + 1 == data["lines"]
        assert sha(textwrap.dedent(source)) == data["dedented_sha256"]
        assert ast.unparse(node.args) == data["signature"]
        calls = sorted({
            value for child in ast.walk(node)
            if isinstance(child, ast.Call)
            for value in [dotted(child.func)]
            if value
        })
        assert calls == data["calls"]
        assert sorted(call for call in calls if call.startswith("self.db.")) == data["db_calls"]

    app_text = APP_PATH.read_text(encoding="utf-8")
    app_tree = ast.parse(app_text)
    app_class = next(node for node in app_tree.body if isinstance(node, ast.ClassDef) and node.name == "App")
    app_methods = {
        node.name: node for node in app_class.body if isinstance(node, ast.FunctionDef)
    }
    assert all(name not in app_methods for name in TARGETS)
    assert "open_delete_day_dialog" not in app_methods

    # Waves 62-63 intentionally moved and hardened Delete Day after Wave 61.
    # Protect its current module-owned boundary rather than expecting the old App method.
    delete_day_text = DELETE_DAY_MODULE_PATH.read_text(encoding="utf-8")
    delete_day_lines = delete_day_text.splitlines(keepends=True)
    delete_day_tree = ast.parse(delete_day_text)
    delete_day_functions = {
        node.name: node for node in delete_day_tree.body if isinstance(node, ast.FunctionDef)
    }
    protected = delete_day_functions["open_delete_day_dialog"]
    protected_source = "".join(delete_day_lines[protected.lineno - 1: protected.end_lineno])
    delete_day_module = importlib.import_module("spina_app.databank_delete_day")
    delete_day_metadata = delete_day_module.DATABANK_DELETE_DAY_METHOD
    assert sha(protected_source) == delete_day_metadata["source_sha256"]
    assert sha(textwrap.dedent(protected_source)) == delete_day_metadata["dedented_sha256"]

    assert app_text.count("configure_databank_cell_write_dependencies as _configure_wave61_databank_writes") == 1
    for name in TARGETS:
        alias = {
            "_save_cell_edit": "_wave61_save_cell_edit",
            "delete_selected_cell": "_wave61_delete_selected_cell",
            "_mark_missed_for_selected": "_wave61_mark_missed_for_selected",
        }[name]
        assert app_text.count(f"App.{name} = {alias}") == 1

    print("Wave 61 exact write-boundary regression passed:", sum(data["lines"] for data in EXPECTED.values()), "lines")


if __name__ == "__main__":
    main()
