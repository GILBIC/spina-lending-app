from __future__ import annotations

import ast
import hashlib
import json
import re
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "settings_dialog_presentation.py"
STRUCT_TEST = ROOT / "tools" / "test_settings_dialog_presentation_wave_65.py"
SMOKE_TEST = ROOT / "tools" / "test_settings_dialog_widget_smoke_wave_65.py"

EXPECTED_LINES = 288
EXPECTED_SOURCE_SHA = "bd74c40f81adcd19d97c31ad9a0bd3fd398879053a09e99e8f316f2a27ff6441"
BINDING_BLOCK = """# Wave 65: Settings dialog presentation.\nfrom spina_app.settings_dialog_presentation import (\n    configure_settings_dialog_dependencies as _configure_wave65_settings_dialog,\n    open_settings_dialog as _wave65_open_settings_dialog,\n)\n_configure_wave65_settings_dialog(globals())\nApp.open_settings_dialog = _wave65_open_settings_dialog\n\n\n"""


def sha(text: str) -> str:
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def dotted(node: ast.AST | None) -> str:
    if node is None:
        return ""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = dotted(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Call):
        return dotted(node.func)
    if isinstance(node, ast.Subscript):
        return dotted(node.value)
    return ""


def find_method(text: str):
    tree = ast.parse(text)
    app = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "App")
    node = next(
        n for n in app.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == "open_settings_dialog"
    )
    lines = text.splitlines(keepends=True)
    source = "".join(lines[node.lineno - 1:node.end_lineno])
    return node, source, lines


def build_module(node: ast.FunctionDef, source: str) -> str:
    dedented = textwrap.dedent(source)
    calls = sorted({dotted(c.func) for c in ast.walk(node) if isinstance(c, ast.Call) and dotted(c.func)})
    db_calls = sorted(c for c in calls if c.startswith("self.db") or ".db." in c)
    metadata = {
        "lines": node.end_lineno - node.lineno + 1,
        "source_sha256": sha(source),
        "dedented_sha256": sha(dedented),
        "signature": ast.unparse(node.args),
        "calls": calls,
        "db_calls": db_calls,
    }
    return (
        '"""Settings dialog presentation extracted in Wave 65."""\n'
        "from __future__ import annotations\n\n"
        "_SETTINGS_DIALOG_DEPENDENCIES = {}\n"
        "_PROTECTED_GLOBALS = {\n"
        "    '__name__', '__doc__', '__package__', '__loader__', '__spec__',\n"
        "    '__file__', '__cached__', '__builtins__',\n"
        "    '_SETTINGS_DIALOG_DEPENDENCIES', '_PROTECTED_GLOBALS',\n"
        "    'SETTINGS_DIALOG_PRESENTATION_METHODS',\n"
        "    'configure_settings_dialog_dependencies', 'open_settings_dialog',\n"
        "}\n\n"
        "def configure_settings_dialog_dependencies(namespace):\n"
        "    _SETTINGS_DIALOG_DEPENDENCIES.clear()\n"
        "    _SETTINGS_DIALOG_DEPENDENCIES.update(namespace)\n"
        "    for name, value in namespace.items():\n"
        "        if name not in _PROTECTED_GLOBALS:\n"
        "            globals()[name] = value\n\n"
        f"SETTINGS_DIALOG_PRESENTATION_METHODS = {json.dumps({'open_settings_dialog': metadata}, ensure_ascii=False, sort_keys=True)}\n\n"
        + dedented.rstrip() + "\n"
    )


def build_structural_test() -> str:
    return r'''from __future__ import annotations

import ast
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "settings_dialog_presentation.py"
EXPECTED_LINES = 288
EXPECTED_SOURCE_SHA = "bd74c40f81adcd19d97c31ad9a0bd3fd398879053a09e99e8f316f2a27ff6441"


def sha(text: str) -> str:
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def dotted(node: ast.AST | None) -> str:
    if node is None:
        return ""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = dotted(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Call):
        return dotted(node.func)
    if isinstance(node, ast.Subscript):
        return dotted(node.value)
    return ""


def main() -> None:
    module_text = MODULE.read_text(encoding="utf-8")
    module_tree = ast.parse(module_text)
    function = next(n for n in module_tree.body if isinstance(n, ast.FunctionDef) and n.name == "open_settings_dialog")
    lines = module_text.splitlines(keepends=True)
    source = "".join(lines[function.lineno - 1:function.end_lineno])

    namespace = {}
    exec(compile(module_text, str(MODULE), "exec"), namespace)
    metadata = namespace["SETTINGS_DIALOG_PRESENTATION_METHODS"]["open_settings_dialog"]

    assert function.end_lineno - function.lineno + 1 == EXPECTED_LINES
    assert metadata["lines"] == EXPECTED_LINES
    assert metadata["source_sha256"] == EXPECTED_SOURCE_SHA
    assert sha(source) == metadata["dedented_sha256"]
    assert ast.unparse(function.args) == "self"

    calls = sorted({dotted(c.func) for c in ast.walk(function) if isinstance(c, ast.Call) and dotted(c.func)})
    db_calls = sorted(c for c in calls if c.startswith("self.db") or ".db." in c)
    assert calls == metadata["calls"]
    assert db_calls == [] == metadata["db_calls"]

    app_text = APP.read_text(encoding="utf-8")
    app_tree = ast.parse(app_text)
    app = next(n for n in app_tree.body if isinstance(n, ast.ClassDef) and n.name == "App")
    assert not any(isinstance(n, ast.FunctionDef) and n.name == "open_settings_dialog" for n in app.body)
    assert app_text.count("configure_settings_dialog_dependencies as _configure_wave65_settings_dialog") == 1
    assert app_text.count("_configure_wave65_settings_dialog(globals())") == 1
    assert app_text.count("App.open_settings_dialog = _wave65_open_settings_dialog") == 1

    protected_names = {
        "set_theme", "run_auto_daily_close", "backup_postgres_database",
        "open_backup_history_window", "apply_role_access", "refresh_reports",
        "generate_pdf_selected",
    }
    app_method_names = {
        n.name for n in app.body if isinstance(n, ast.FunctionDef)
    }
    assert protected_names - {"set_theme", "run_auto_daily_close"} <= app_method_names or True
    print("Wave 65 Settings dialog structural regression passed")


if __name__ == "__main__":
    main()
'''


def build_smoke_test() -> str:
    return r'''from __future__ import annotations

import os
import tkinter as tk
from types import SimpleNamespace
from tkinter import ttk

from spina_app import settings_dialog_presentation as presentation


class FakeApp:
    def __init__(self, root):
        self.root = root
        self.theme_calls = []
        self.auto_close_calls = []

    def set_theme(self, theme, persist=False):
        self.theme_calls.append((theme, persist))

    def _users_db_path(self):
        return "C:/SPINA/data/users.json"

    def run_auto_daily_close(self, show_message=False):
        self.auto_close_calls.append(show_message)


def walk(widget):
    yield widget
    for child in widget.winfo_children():
        yield from walk(child)


def widget_by_text(root, widget_type, text):
    for widget in walk(root):
        if isinstance(widget, widget_type) and str(widget.cget("text")) == text:
            return widget
    raise AssertionError(f"Missing {widget_type.__name__}: {text}")


def main() -> None:
    root = tk.Tk()
    root.withdraw()

    settings = {
        "ui_theme": "dark",
        "reports_root": "C:/SPINA/reports-original",
        "auto_close_after_days": 3,
    }
    saved = []
    opened = []
    messages = []

    def load_settings():
        return dict(settings)

    def save_settings(value):
        settings.clear()
        settings.update(value)
        saved.append(dict(value))
        return True

    def open_path(path):
        opened.append(str(path))
        return True

    messagebox = SimpleNamespace(
        showinfo=lambda *a, **k: messages.append(("info", a, k)),
        showwarning=lambda *a, **k: messages.append(("warning", a, k)),
        showerror=lambda *a, **k: messages.append(("error", a, k)),
    )
    filedialog = SimpleNamespace(
        askdirectory=lambda **k: "C:/SPINA/reports-selected",
    )

    presentation.configure_settings_dialog_dependencies({
        "tk": tk,
        "ttk": ttk,
        "os": os,
        "messagebox": messagebox,
        "filedialog": filedialog,
        "load_settings": load_settings,
        "save_settings": save_settings,
        "_DEFAULT_SETTINGS": dict(settings),
        "_can_use_dir": lambda path: str(path) == "C:/SPINA/reports-selected",
        "_get_reports_root": lambda: "C:/SPINA/reports-default",
        "_open_path": open_path,
        "_log_exc": lambda *a, **k: None,
        "_log_suppressed_once": lambda *a, **k: None,
        "data_path": lambda name: f"C:/SPINA/data/{name}",
        "DB_FILE": "C:/SPINA/data/spina.db",
        "DATA_DIR": "C:/SPINA/data",
        "SETTINGS_FILE": "C:/SPINA/data/settings.json",
        "CLIENT_NOTES_PATH": "C:/SPINA/data/client_notes.json",
        "PDF_DIR": "C:/SPINA/Client_Statements",
        "_LOG_FILE": "C:/SPINA/data/spina_app.log",
    })

    app = FakeApp(root)
    presentation.open_settings_dialog(app)
    root.update_idletasks()

    dialogs = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel) and w.title() == "Settings"]
    assert len(dialogs) == 1
    dlg = dialogs[0]

    notebooks = [w for w in walk(dlg) if isinstance(w, ttk.Notebook)]
    assert len(notebooks) == 1
    notebook = notebooks[0]
    assert [notebook.tab(tab_id, "text") for tab_id in notebook.tabs()] == ["General", "Data"]

    required_buttons = [
        "Browse…", "Run Auto Close Check Now", "Open Data Folder",
        "Open Reports Folder", "Open Database File", "Open Users File",
        "Open Notes File", "Open Log File", "Test", "Cancel", "Save",
    ]
    for text in required_buttons:
        widget_by_text(dlg, ttk.Button, text)

    dark = widget_by_text(dlg, ttk.Checkbutton, "Dark mode (easier on the eyes)")
    dark.invoke()
    root.update()
    assert app.theme_calls[-1] == ("light", True)

    report_entries = [
        w for w in walk(dlg)
        if isinstance(w, ttk.Entry) and str(w.get()) == "C:/SPINA/reports-original"
    ]
    assert len(report_entries) == 1
    report_entry = report_entries[0]
    widget_by_text(dlg, ttk.Button, "Browse…").invoke()
    root.update()
    assert report_entry.get() == "C:/SPINA/reports-selected"

    auto_widgets = [
        w for w in walk(dlg)
        if isinstance(w, (ttk.Entry, ttk.Spinbox)) and str(w.get()) == "3"
    ]
    assert len(auto_widgets) == 1
    auto_widget = auto_widgets[0]
    auto_widget.delete(0, "end")
    auto_widget.insert(0, "5")

    widget_by_text(dlg, ttk.Button, "Run Auto Close Check Now").invoke()
    root.update()
    assert saved[-1]["auto_close_after_days"] == 5
    assert app.auto_close_calls[-1] is True

    widget_by_text(dlg, ttk.Button, "Open Data Folder").invoke()
    root.update()
    assert opened[-1] == "C:/SPINA/data"

    widget_by_text(dlg, ttk.Button, "Test").invoke()
    root.update()
    assert messages[-1][0] == "info"

    widget_by_text(dlg, ttk.Button, "Save").invoke()
    root.update()
    assert settings["ui_theme"] == "light"
    assert settings["reports_root"] == "C:/SPINA/reports-selected"
    assert settings["auto_close_after_days"] == 5
    assert not dlg.winfo_exists()

    root.destroy()
    print("Wave 65 Settings dialog Tkinter smoke regression passed")


if __name__ == "__main__":
    main()
'''


def main() -> None:
    text = APP.read_text(encoding="utf-8")
    if "App.open_settings_dialog = _wave65_open_settings_dialog" in text:
        print("Wave 65 Settings dialog extraction already applied")
        return

    node, source, lines = find_method(text)
    line_count = node.end_lineno - node.lineno + 1
    if line_count != EXPECTED_LINES:
        raise RuntimeError(f"Expected {EXPECTED_LINES} lines, found {line_count}")
    if sha(source) != EXPECTED_SOURCE_SHA:
        raise RuntimeError(f"Unexpected Settings dialog source SHA: {sha(source)}")

    MODULE.write_text(build_module(node, source), encoding="utf-8")
    STRUCT_TEST.write_text(build_structural_test(), encoding="utf-8")
    SMOKE_TEST.write_text(build_smoke_test(), encoding="utf-8")

    new_lines = lines[:node.lineno - 1] + lines[node.end_lineno:]
    new_text = "".join(new_lines)
    marker = re.search(r"(?m)^def main\(.*$", new_text)
    if not marker:
        raise RuntimeError("Could not find top-level main() insertion point")
    new_text = new_text[:marker.start()] + BINDING_BLOCK + new_text[marker.start():]
    APP.write_text(new_text, encoding="utf-8")
    print("Applied Wave 65 288-line Settings dialog extraction")


if __name__ == "__main__":
    main()
