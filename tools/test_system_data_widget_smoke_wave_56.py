"""Real Tkinter smoke test for Wave 56 System Data presentation."""
from __future__ import annotations

import datetime as _dt
import tkinter as tk
from tkinter import ttk

import spina_app.system_data_presentation as module


def walk(widget):
    yield widget
    for child in widget.winfo_children():
        yield from walk(child)


class FakeApp:
    def __init__(self, root):
        self.root = root
        self.tab_system_data = ttk.Frame(root)
        self.tab_system_data.grid(row=0, column=0, sticky="nsew")
        self.calls = []

    def __getattr__(self, name):
        if name.startswith("_"):
            def stub(*args, **kwargs):
                self.calls.append(name)
                if name == "_get_databank_focus_date":
                    return "2026-07-27"
                return None
            return stub
        raise AttributeError(name)


def main() -> None:
    module.configure_system_data_presentation_dependencies({
        "tk": tk,
        "ttk": ttk,
        "_dt": _dt,
        "_log_suppressed_once": lambda *args, **kwargs: None,
    })
    root = tk.Tk()
    root.withdraw()
    try:
        app = FakeApp(root)
        module._build_system_data_tab(app)
        root.update_idletasks()
        widgets = list(walk(app.tab_system_data))
        texts = {str(w.cget("text")) for w in widgets if "text" in w.keys()}
        assert set(module.SYSTEM_DATA_PRESENTATION_BUTTON_TEXTS) <= texts
        assert set(module.SYSTEM_DATA_PRESENTATION_LABEL_TEXTS) <= texts
        for attr in module.SYSTEM_DATA_PRESENTATION_SELF_ATTRIBUTES:
            assert hasattr(app, attr), attr
        for text, callback in module.SYSTEM_DATA_PRESENTATION_BUTTON_CALLBACKS:
            button = next(w for w in widgets if isinstance(w, ttk.Button) and str(w.cget("text")) == text)
            app.calls.clear()
            button.invoke()
            assert callback in app.calls, (text, callback, app.calls)
        print("Wave 56 real Tkinter System Data construction test passed")
    finally:
        root.destroy()


if __name__ == "__main__":
    main()
