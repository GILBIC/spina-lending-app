from __future__ import annotations

import tkinter as tk
from pathlib import Path

from spina_app import collector_dialog_presentation as presentation

ROOT = Path(__file__).resolve().parents[1]


class FakeApp:
    def __init__(self, root):
        self.root = root


def colors(_self):
    return {
        "bg": "#f5f5f5",
        "panel": "#ffffff",
        "border": "#cccccc",
        "entry": "#ffffff",
        "fg": "#111111",
        "muted": "#555555",
        "blue": "#4477aa",
        "green": "#338855",
    }


def master_areas(_self):
    return ["North", "South", "East"]


def route_button(parent, text, command, kind="soft"):
    return tk.Button(parent, text=text, command=command)


def all_widgets(widget):
    yield widget
    for child in widget.winfo_children():
        yield from all_widgets(child)


def invoke_button(root, label):
    for widget in all_widgets(root):
        try:
            if str(widget.cget("text")) == label:
                widget.invoke()
                return
        except Exception:
            pass
    raise AssertionError(f"Button not found: {label}")


def main() -> None:
    root = tk.Tk()
    root.withdraw()
    presentation.configure_collector_dialog_dependencies({
        "_spina_v27_route_colors": colors,
        "_spina_v27_get_route_master_areas": master_areas,
        "_spina_v27_route_button": route_button,
    })
    app = FakeApp(root)

    root.after(100, lambda: invoke_button(root, "Save Route"))
    saved = presentation._spina_v27_collector_editor_dialog(
        app,
        title="Collector",
        initial_name="Alice",
        initial_areas=["North", "South"],
        initial_notes="Priority route",
    )
    assert saved == {
        "name": "Alice",
        "areas": ["North", "South"],
        "notes": "Priority route",
    }, saved

    root.after(100, lambda: invoke_button(root, "Cancel"))
    cancelled = presentation._spina_v27_collector_editor_dialog(
        app,
        title="Collector",
        initial_name="Bob",
        initial_areas=["East"],
        initial_notes="",
    )
    assert cancelled is None

    root.destroy()
    print("Wave 69 collector editor real Tkinter smoke regression passed.")


if __name__ == "__main__":
    main()
