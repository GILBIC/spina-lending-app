from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from types import MethodType
from tkinter import ttk

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from spina_app import side_navigation_presentation as nav


def main() -> None:
    root = tk.Tk()
    try:
        root.geometry("900x600+30+30")
        shell = tk.Frame(root)
        shell.pack(fill="both", expand=True)
        sidebar = tk.Frame(shell)
        sidebar.pack(side="left", fill="y")
        notebook = ttk.Notebook(shell)
        notebook.pack(side="left", fill="both", expand=True)

        dashboard = tk.Frame(notebook)
        reports = tk.Frame(notebook)
        clients = tk.Frame(notebook)
        notebook.add(dashboard, text="Dashboard")
        notebook.add(reports, text="Reports")
        notebook.add(clients, text="Clients")
        notebook.hide(reports)

        class Dummy:
            pass

        app = Dummy()
        app.root = root
        app.nb = notebook
        app.sidebar_frame = sidebar
        app.user_name = "desktop-test"
        app.user_role = "Viewer"
        app.ui_theme = "light"
        app._ui_colors = {
            "panel": "#ffffff", "fg": "#111111", "muted": "#666666",
            "accent": "#ffd1e6", "border": "#dddddd",
            "button_active": "#f3e6eb",
        }
        app._theme_palette = lambda: dict(app._ui_colors)
        app._refresh_side_nav_selection = MethodType(nav._spina_v13_refresh_side_nav_selection, app)
        app._select_side_tab = lambda tab: notebook.select(tab)

        nav._spina_v13_hide_main_notebook_tabs(app)
        assert notebook.cget("style") in {"SideOnly.TNotebook", "Sidebar.TNotebook"}

        nav._spina_v13_rebuild_side_nav(app)
        root.update_idletasks()
        assert len(app._side_nav_buttons) == 2
        texts = [button.cget("text") for button in app._side_nav_buttons.values()]
        assert any("Dashboard" in text for text in texts)
        assert any("Clients" in text for text in texts)
        assert all("Reports" not in text for text in texts)

        notebook.select(clients)
        app._refresh_side_nav_selection()
        root.update_idletasks()
        active = app._side_nav_buttons[str(clients)]
        inactive = app._side_nav_buttons[str(dashboard)]
        assert active.cget("background") != inactive.cget("background")

        app.ui_theme = "dark"
        app._ui_colors = {
            "panel": "#181a20", "fg": "#ffffff", "muted": "#a9a9b3",
            "accent": "#ffd1e6", "border": "#30323a",
            "button_active": "#2a2d36",
        }
        nav._spina_v13_rebuild_side_nav(app)
        root.update_idletasks()
        assert len(app._side_nav_buttons) == 2
        assert any("desktop-test" in label.cget("text") for label in app._side_nav_labels)

        print("Wave 48 side-navigation Tkinter smoke test passed.")
    finally:
        try:
            root.update_idletasks()
        except Exception:
            pass
        root.destroy()


if __name__ == "__main__":
    main()
