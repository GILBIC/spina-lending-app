"""Exact-source regression for Wave 59 Data Bank grid presentation."""
from __future__ import annotations

import ast
import hashlib
import inspect
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
EXPECTED = {'goto_current_month': {'lines': 5, 'source_sha256': '42ecd7e7b76492b3e568621109b166249426f32199a9ed8d3c3966b7f9d44a96', 'dedented_sha256': '478fd8e11b972e47656ed78794331548073c07d8c4de26bd42c55fef371e4cf1', 'signature': 'self', 'calls': ['date.today', 'self.refresh_data_grid'], 'db_calls': []}, 'prev_month': {'lines': 4, 'source_sha256': 'e0b005e9000e608a411637ef7996cbd886c0d11babfad98f3679cb68ad217753', 'dedented_sha256': 'ffb617393a0c9f736fa0ff95512ad908464b754e0c83e17fc4cab7eef7dd15d3', 'signature': 'self', 'calls': ['self._month_label', 'self.month_lbl.config', 'self.refresh_data_grid'], 'db_calls': []}, 'next_month': {'lines': 4, 'source_sha256': '7e03166f967729a5f940e707332ce385e194f07c6f3a119bfd4ed9f48bfab41b', 'dedented_sha256': '2d3727c306f3be2a4229dde2808e6a5d219fc70bc22a2d2af9b849e80ee843f5', 'signature': 'self', 'calls': ['self._month_label', 'self.month_lbl.config', 'self.refresh_data_grid'], 'db_calls': []}, 'refresh_data_grid': {'lines': 271, 'source_sha256': 'e3ecfaae3f958c4d06ac7aa75b41ab5f0f0ab027b2dcc58dafa9e197779b31aa', 'dedented_sha256': 'a3e7d1d4fe903e20d1141aa0ecdf77497aabd88f3083b804b0902e41d9741b31', 'signature': 'self', 'calls': ['_log_ignored', '_log_suppressed_once', '_sync_selection', 'c.get', 'calendar.monthrange', 'date', 'enumerate', 'float', 'fmt_currency', 'from_tv.selection', 'grid.grid', 'grid.grid_columnconfigure', 'grid.grid_rowconfigure', 'h.grid', 'hasattr', 'info.get', 'int', 'isinstance', 'len', 'range', 'self._configure_tree_stripes', 'self._db_menu.add_command', 'self._db_menu.add_separator', 'self._db_menu.grab_release', 'self._db_menu.tk_popup', 'self._db_rows_var.set', 'self._ensure_databank_edit_bindings', 'self._mode_filter', 'self._month_label', 'self._remember_cell_click', 'self._resize_databank_columns', 'self._update_data_toolbar', 'self.days_tree.bind', 'self.days_tree.column', 'self.days_tree.configure', 'self.days_tree.focus', 'self.days_tree.grid', 'self.days_tree.heading', 'self.days_tree.identify_row', 'self.days_tree.insert', 'self.days_tree.selection_set', 'self.days_tree.yview', 'self.db.get_all_clients', 'self.db.get_client_info', 'self.db.get_transaction', 'self.inner.bind', 'self.inner.grid_columnconfigure', 'self.inner.grid_rowconfigure', 'self.inner.winfo_children', 'self.name_tree.bind', 'self.name_tree.column', 'self.name_tree.configure', 'self.name_tree.focus', 'self.name_tree.grid', 'self.name_tree.heading', 'self.name_tree.identify_row', 'self.name_tree.insert', 'self.name_tree.selection_set', 'self.name_tree.yview', 'self.root.bell', 'self.search_db_var.get', 'self.status_var.set', 'str', 'strftime', 'strip', 'tk.Menu', 'to_tv.focus', 'to_tv.selection', 'to_tv.selection_set', 'ttk.Frame', 'ttk.Scrollbar', 'ttk.Treeview', 'tuple', 'tv.bind', 'v.grid', 'vals.append', 'w.destroy'], 'db_calls': ['self.db.get_all_clients', 'self.db.get_client_info', 'self.db.get_transaction']}}
PROTECTED_MARKERS = ('.execute', '.executemany', '.commit', '.rollback', 'set_databank_day_close', 'replace_databank_day_collectors', 'delete_transactions_for_day', 'delete_transaction', 'add_or_update_transaction', 'close_day', 'reopen_day', 'backup', 'restore', 'password', 'print_databank_close_report', 'write_text', 'write_bytes', 'unlink', '_save_cell_edit', '_import_from_excel', 'open_delete_day_dialog')
PROTECTED_APP_METHODS = ('_begin_cell_edit', '_save_cell_edit', 'delete_selected_cell', '_mark_missed_for_selected', 'open_delete_day_dialog', '_import_from_excel_entry', 'open_databank_close_dialog')


def dotted(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def main() -> None:
    import spina_app.databank_grid_presentation as module

    assert module.DATABANK_GRID_PRESENTATION_METHODS == EXPECTED
    app_text = APP.read_text(encoding="utf-8-sig")
    app_tree = ast.parse(app_text, filename=str(APP))
    app_class = next(node for node in app_tree.body if isinstance(node, ast.ClassDef) and node.name == "App")
    remaining = {child.name for child in app_class.body if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))}

    for name, expected in EXPECTED.items():
        assert name not in remaining
        function = getattr(module, name)
        source = inspect.getsource(function)
        assert len(source.splitlines()) == expected["lines"]
        assert hashlib.sha256(source.encode("utf-8")).hexdigest() == expected["dedented_sha256"]
        node = ast.parse(source).body[0]
        assert ast.unparse(node.args) == expected["signature"]
        calls = sorted({dotted(call.func) for call in ast.walk(node) if isinstance(call, ast.Call) and dotted(call.func)})
        assert calls == expected["calls"]
        assert [call for call in calls if call.startswith("self.db.")] == expected["db_calls"]
        lowered = "\n".join(calls).lower()
        assert not [marker for marker in PROTECTED_MARKERS if marker in lowered]

    assert all(name in remaining for name in PROTECTED_APP_METHODS)
    assert app_text.count("_configure_wave59_databank_grid(globals())") == 1
    for name in EXPECTED:
        assert app_text.count(f"App.{name} = _wave59_{name}") == 1
    print("Wave 59 exact Data Bank grid extraction regression passed")


if __name__ == "__main__":
    main()
