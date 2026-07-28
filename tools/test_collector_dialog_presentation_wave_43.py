from __future__ import annotations

import ast
import hashlib
import importlib.util
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "collector_dialog_presentation.py"
TARGET = '_spina_v27_collector_editor_dialog'
EXPECTED_LINES = 350
EXPECTED_SHA256 = 'acc8e500cd9e62435bd24d7e998c0dc3c6145e396437f22ca4ee8781c3bbe0f6'
EXPECTED_SIGNATURE = "self, title='Collector', initial_name='', initial_areas=None, initial_notes=''"
EXPECTED_CALLBACKS = ['_panel', '_assigned_keys', '_refresh_lists', '_clean_assigned_display', '_add_selected', '_remove_selected', '_move_selected', '_move_top', '_move_bottom', '_add_all_visible', '_clear_assigned', '_save', '_cancel']
EXPECTED_CALLS = ['_add_selected', '_assigned_keys', '_cancel', '_clean_assigned_display', '_move_selected', '_panel', '_refresh_lists', '_remove_selected', '_spina_v27_get_route_master_areas', '_spina_v27_route_button', '_spina_v27_route_colors', 'append', 'assigned_frame.pack', 'assigned_lb.bind', 'assigned_lb.configure', 'assigned_lb.curselection', 'assigned_lb.delete', 'assigned_lb.get', 'assigned_lb.insert', 'assigned_lb.pack', 'assigned_lb.see', 'assigned_lb.selection_clear', 'assigned_lb.selection_set', 'assigned_lb.size', 'assigned_panel.grid', 'assigned_vsb.pack', 'avail_frame.pack', 'avail_vsb.pack', 'available_lb.bind', 'available_lb.configure', 'available_lb.curselection', 'available_lb.delete', 'available_lb.get', 'available_lb.insert', 'available_lb.pack', 'available_lb.size', 'available_panel.grid', 'body.columnconfigure', 'body.pack', 'body.rowconfigure', 'clean.append', 'enumerate', 'footer.pack', 'header.pack', 'initial.append', 'insert', 'join', 'len', 'list', 'lower', 'master_areas.append', 'max', 'messagebox.askyesno', 'messagebox.showwarning', 'middle.grid', 'middle.grid_propagate', 'min', 'name_panel.pack', 'name_var.get', 'next', 'notes_panel.pack', 'notes_txt.get', 'notes_txt.insert', 'notes_txt.pack', 'pack', 'picks.append', 'pop', 'range', 're.sub', 'result.get', 'result.update', 's.lower', 's.split', 'search_a.pack', 'search_assigned_var.get', 'search_assigned_var.set', 'search_assigned_var.trace_add', 'search_available_var.get', 'search_available_var.set', 'search_available_var.trace_add', 'search_s.pack', 'seen.add', 'seen_init.add', 'self.root.winfo_height', 'self.root.winfo_rootx', 'self.root.winfo_rooty', 'self.root.winfo_width', 'set', 'split', 'status_var.set', 'str', 'strip', 'titlebox.pack', 'tk.Frame', 'tk.Label', 'tk.Listbox', 'tk.StringVar', 'tk.Text', 'tk.Toplevel', 'top.bind', 'top.configure', 'top.destroy', 'top.geometry', 'top.grab_release', 'top.grab_set', 'top.minsize', 'top.protocol', 'top.title', 'top.transient', 'top.wait_window', 'top.winfo_screenheight', 'top.winfo_screenwidth', 'ttk.Entry', 'ttk.Scrollbar', 'used.add']
EXPECTED_HELPER_CALLS = ['_spina_v27_get_route_master_areas', '_spina_v27_route_button', '_spina_v27_route_colors', 'messagebox.askyesno', 'messagebox.showwarning']
FORBIDDEN_CALL_SUFFIXES = ['_save_client_notes', 'add_client', 'add_transaction', 'archive_client', 'close_databank_day', 'commit', 'delete_client', 'delete_transaction', 'dump', 'dumps', 'execute', 'executemany', 'remove', 'rename', 'renew_client', 'reopen_databank_day', 'replace', 'restore_client', 'rmtree', 'rollback', 'run_write', 'save_settings', 'set_client_note', 'set_transaction', 'unlink', 'update_client', 'update_transaction', 'write', 'write_bytes', 'write_text']
SQL_WRITE = ('INSERT INTO', 'UPDATE ', 'DELETE FROM', 'CREATE TABLE', 'ALTER TABLE', 'DROP TABLE', 'TRUNCATE TABLE')


def normalized(source):
    return textwrap.dedent(source).strip() + "\n"


def chain(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return list(reversed(parts))


def call_name(node):
    return ".".join(chain(node))


def source_for(node, lines):
    return "".join(lines[node.lineno - 1 : node.end_lineno])


def main():
    spec = importlib.util.spec_from_file_location("wave43_collector_dialog_import", MODULE)
    assert spec is not None and spec.loader is not None
    imported = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(imported)
    assert callable(imported._spina_v27_collector_editor_dialog)
    assert imported.tk.Toplevel is not None
    assert imported.ttk.Entry is not None
    assert imported.messagebox.showwarning is not None

    module_text = MODULE.read_text(encoding="utf-8")
    mtree = ast.parse(module_text)
    funcs = [n for n in mtree.body if isinstance(n, ast.FunctionDef) and n.name == TARGET]
    assert len(funcs) == 1, len(funcs)
    node = funcs[0]
    lines = module_text.splitlines(keepends=True)
    source = source_for(node, lines)
    assert node.end_lineno - node.lineno + 1 == EXPECTED_LINES
    assert hashlib.sha256(normalized(source).encode("utf-8")).hexdigest() == EXPECTED_SHA256
    assert ast.unparse(node.args) == EXPECTED_SIGNATURE
    callbacks = [
        item.name for item in node.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    assert callbacks == EXPECTED_CALLBACKS, callbacks

    calls = set()
    for item in ast.walk(node):
        if isinstance(item, ast.Attribute):
            full = call_name(item)
            assert not full.startswith("self.db"), full
        if isinstance(item, ast.Call):
            full = call_name(item.func)
            calls.add(full)
            suffix = full.split(".")[-1].lower() if full else ""
            assert suffix not in FORBIDDEN_CALL_SUFFIXES, full
        if isinstance(item, ast.Constant) and isinstance(item.value, str):
            upper = " ".join(item.value.upper().split())
            assert not any(token in upper for token in SQL_WRITE), upper
    assert sorted(calls) == EXPECTED_CALLS
    for helper in EXPECTED_HELPER_CALLS:
        assert helper in calls

    desktop_text = DESKTOP.read_text(encoding="utf-8")
    dtree = ast.parse(desktop_text)
    originals = [
        n for n in dtree.body if isinstance(n, ast.FunctionDef) and n.name == TARGET
    ]
    assert not originals, originals
    assert "_configure_wave43_collector_dialog(globals())" in desktop_text
    assert f"{TARGET} = _wave43_collector_editor_dialog" in desktop_text
    binding = "App._collector_editor_dialog = _spina_v27_collector_editor_dialog"
    assert desktop_text.count(binding) == 1

    app = next(n for n in dtree.body if isinstance(n, ast.ClassDef) and n.name == "App")
    old_methods = [
        n for n in app.body
        if isinstance(n, ast.FunctionDef) and n.name == "_collector_editor_dialog"
    ]
    assert not old_methods, old_methods

    binding_line = desktop_text[:desktop_text.index(binding)].count("\n") + 1
    main_guards = [
        node for node in dtree.body
        if isinstance(node, ast.If) and "__name__" in ast.unparse(node.test) and "__main__" in ast.unparse(node.test)
    ]
    assert main_guards, "Top-level main guard missing"
    assert binding_line < main_guards[-1].lineno
    print("Wave 43 collector dialog regression passed:", EXPECTED_LINES, EXPECTED_SHA256)


if __name__ == "__main__":
    main()
