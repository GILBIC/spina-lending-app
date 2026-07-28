from __future__ import annotations

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
