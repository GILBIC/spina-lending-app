from __future__ import annotations

import ast
import hashlib
import importlib.util
import inspect
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "long_task_presentation.py"
TARGET_CLASS = 'App'
TARGET = '_run_long_task'
EXPECTED_LINES = 273
EXPECTED_SHA256 = '037194095a785211335844178a4f90675c08d7cede51fa7675db4a9ccc17ac21'
EXPECTED_NESTED = ['_cleanup_dialog', '_finish', '_request_cancel', '_watchdog', '_call_work_fn', '_worker']
EXPECTED_CALLS = ['TimeoutError', '_call_work_fn', '_cleanup_dialog', '_finish', '_inspect.signature', '_log_exc', '_log_suppressed_once', 'any', 'box.get', 'btn_cancel.config', 'btn_cancel.pack', 'cancel_event.is_set', 'cancel_event.set', 'dlg.destroy', 'dlg.geometry', 'dlg.grab_release', 'dlg.grab_set', 'dlg.protocol', 'dlg.resizable', 'dlg.title', 'dlg.transient', 'dlg.update_idletasks', 'dlg.winfo_exists', 'dlg.winfo_height', 'dlg.winfo_width', 'done.get', 'float', 'frm.pack', 'int', 'len', 'list', 'max', 'messagebox.showerror', 'on_error', 'on_success', 'pack', 'pb.pack', 'pb.start', 'pb.stop', 'self.root.after', 'self.root.winfo_height', 'self.root.winfo_rootx', 'self.root.winfo_rooty', 'self.root.winfo_width', 'sig.parameters.values', 'start', 'str', 'threading.Event', 'threading.Thread', 'time.time', 'tk.Toplevel', 'ttk.Button', 'ttk.Frame', 'ttk.Label', 'ttk.Progressbar', 'work_fn']
EXPECTED_CALLER_COUNT = 5
FORBIDDEN_CALL_SUFFIXES = ['add_client', 'add_transaction', 'archive_client', 'close_databank_day', 'commit', 'copy', 'copy2', 'cursor', 'delete_client', 'delete_transaction', 'dump', 'dumps', 'execute', 'executemany', 'move', 'open', 'remove', 'rename', 'renew_client', 'reopen_databank_day', 'restore_client', 'rmdir', 'rollback', 'run_write', 'save_settings', 'set_client_note', 'set_transaction', 'touch', 'unlink', 'update_client', 'update_transaction', 'write', 'write_bytes', 'write_text']
FORBIDDEN_SQL_TOKENS = ('INSERT INTO', 'UPDATE ', 'DELETE FROM', 'CREATE TABLE', 'ALTER TABLE', 'DROP TABLE', 'TRUNCATE TABLE')


def normalized(source):
    return textwrap.dedent(source).strip() + "\n"


def call_chain(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return list(reversed(parts))


def main():
    spec = importlib.util.spec_from_file_location("wave42_long_task_import_smoke", MODULE)
    assert spec is not None and spec.loader is not None
    imported = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(imported)
    assert callable(imported._run_long_task)
    assert imported.tk.Toplevel is not None
    assert imported.threading.Event is not None
    assert imported._inspect.signature is not None
    signature = inspect.signature(imported._run_long_task)
    assert list(signature.parameters) == [
        "self", "title", "work_fn", "on_success", "on_error", "allow_cancel", "timeout_s"
    ]

    module_text = MODULE.read_text(encoding="utf-8")
    mtree = ast.parse(module_text)
    funcs = [n for n in mtree.body if isinstance(n, ast.FunctionDef) and n.name == TARGET]
    assert len(funcs) == 1, len(funcs)
    node = funcs[0]
    lines = module_text.splitlines(keepends=True)
    source = "".join(lines[node.lineno - 1 : node.end_lineno])
    assert node.end_lineno - node.lineno + 1 == EXPECTED_LINES
    assert hashlib.sha256(normalized(source).encode("utf-8")).hexdigest() == EXPECTED_SHA256

    nested = [
        item.name for item in node.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    assert nested == EXPECTED_NESTED, nested

    calls = set()
    for item in ast.walk(node):
        if isinstance(item, ast.Attribute):
            full = ".".join(call_chain(item))
            assert not full.startswith("self.db"), full
        elif isinstance(item, ast.Call):
            parts = call_chain(item.func)
            full = ".".join(parts)
            if full:
                calls.add(full)
            suffix = parts[-1].lower() if parts else ""
            assert suffix not in FORBIDDEN_CALL_SUFFIXES, full
        elif isinstance(item, ast.Constant) and isinstance(item.value, str):
            upper = " ".join(item.value.upper().split())
            assert not any(token in upper for token in FORBIDDEN_SQL_TOKENS), upper
    assert sorted(calls) == EXPECTED_CALLS, sorted(calls)

    desktop_text = DESKTOP.read_text(encoding="utf-8")
    dtree = ast.parse(desktop_text)
    app = next(n for n in dtree.body if isinstance(n, ast.ClassDef) and n.name == TARGET_CLASS)
    originals = [n for n in app.body if isinstance(n, ast.FunctionDef) and n.name == TARGET]
    assert not originals
    assert "_configure_wave42_long_task(globals())" in desktop_text
    assert "App._run_long_task = _wave42_run_long_task" in desktop_text

    # Count protected callers across the desktop and extracted application modules.
    # Later modularization waves may move callers out of the desktop class while
    # preserving the same delegated long-task behavior.
    caller_paths = [DESKTOP, *sorted((ROOT / "spina_app").rglob("*.py"))]
    caller_count = sum(
        path.read_text(encoding="utf-8").count("self._run_long_task(")
        for path in caller_paths
    )
    assert caller_count == EXPECTED_CALLER_COUNT, caller_count
    print("Wave 42 long-task regression passed:", EXPECTED_LINES, EXPECTED_SHA256)


if __name__ == "__main__":
    main()
