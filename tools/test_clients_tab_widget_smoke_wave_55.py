from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import spina_app.clients_tab_presentation as presentation


class _Flexible:
    def __init__(self, owner, name):
        self.owner = owner
        self.name = name
    def __call__(self, *args, **kwargs):
        self.owner.calls.append((self.name, args, kwargs))
        parent = args[0] if args and isinstance(args[0], tk.Misc) else self.owner.tab_clients
        lower = self.name.lower()
        if "button" in lower:
            text = kwargs.get("text", "")
            command = kwargs.get("command")
            return ttk.Button(parent, text=text, command=command)
        if "tree" in lower:
            return ttk.Treeview(parent)
        return None
    def get(self, *args, **kwargs):
        return ""
    def set(self, *args, **kwargs):
        return None
    def __iter__(self):
        return iter(())
    def __bool__(self):
        return False


class DummyApp:
    def __init__(self, root):
        self.root = root
        self.tab_clients = ttk.Frame(root)
        self.tab_clients.pack(fill="both", expand=True)
        self.calls = []
    def __getattr__(self, name):
        value = _Flexible(self, name)
        setattr(self, name, value)
        return value


def _walk(widget):
    yield widget
    for child in widget.winfo_children():
        yield from _walk(child)


def main() -> None:
    root = tk.Tk()
    root.withdraw()
    try:
        app = DummyApp(root)
        presentation.configure_clients_tab_presentation_dependencies({"tk": tk, "ttk": ttk})
        presentation._build_clients_tab(app)
        root.update_idletasks()

        widgets = list(_walk(app.tab_clients))
        assert len(widgets) >= 12, f"too few Clients widgets: {len(widgets)}"
        entries = [w for w in widgets if isinstance(w, (tk.Entry, ttk.Entry))]
        trees = [w for w in widgets if isinstance(w, ttk.Treeview)]
        buttons = [w for w in widgets if isinstance(w, (tk.Button, ttk.Button))]
        assert entries, "Clients tab has no search/filter entry"
        assert trees, "Clients tab has no client table"
        assert buttons, "Clients tab has no buttons"

        visible_texts = set()
        for widget in widgets:
            try:
                text = str(widget.cget("text") or "").strip()
            except Exception:
                text = ""
            if text:
                visible_texts.add(text)
        for text in presentation.CLIENTS_TAB_PRESENTATION_BUTTON_TEXTS:
            assert text in visible_texts, f"missing Clients button: {text}"
        for text in presentation.CLIENTS_TAB_PRESENTATION_LABEL_TEXTS:
            assert text in visible_texts, f"missing Clients label: {text}"

        command_buttons = []
        for button in buttons:
            try:
                if str(button.cget("command") or ""):
                    command_buttons.append(button)
            except Exception:
                pass
        assert command_buttons, "Clients buttons have no callbacks"
        assert hasattr(app, "clients_tree") or any(isinstance(w, ttk.Treeview) for w in widgets)
        print("Wave 55 real Tkinter Clients-tab construction test passed")
    finally:
        root.destroy()


if __name__ == "__main__":
    main()
