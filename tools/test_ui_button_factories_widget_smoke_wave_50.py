from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from spina_app import ui_controls

COLORS = {
    "card2": "#222222",
    "fg": "#eeeeee",
    "blue": "#2255cc",
    "green": "#228855",
    "red": "#bb3333",
    "orange": "#cc7722",
    "soft": "#444444",
}


def expected(kind: str) -> tuple[str, str]:
    if kind == "primary":
        return COLORS["blue"], "#ffffff"
    if kind == "success":
        return COLORS["green"], "#ffffff"
    if kind == "danger":
        return COLORS["red"], "#ffffff"
    if kind == "warning":
        return COLORS["orange"], "#ffffff"
    if kind == "soft":
        return COLORS["soft"], COLORS["fg"]
    return COLORS["card2"], COLORS["fg"]


def verify_button(parent, factory, kind: str, pady: int, font_size: int) -> None:
    calls = []
    button = factory(
        parent,
        f"{factory.__name__}:{kind}",
        command=lambda: calls.append(kind),
        kind=kind,
        width=18,
    )
    button.pack()
    parent.update_idletasks()
    bg, fg = expected(kind)
    assert button.cget("background") == bg
    assert button.cget("foreground") == fg
    assert button.cget("activebackground") == bg
    assert button.cget("activeforeground") == fg
    assert int(button.cget("pady")) == pady
    assert int(button.cget("width")) == 18
    font = str(button.cget("font"))
    assert str(font_size) in font, (font, font_size)
    button.invoke()
    assert calls == [kind]
    button.destroy()


def main() -> None:
    root = tk.Tk()
    root.withdraw()
    assert not hasattr(ui_controls, "_spina_v25_collector_button")
    original_route = ui_controls._spina_v27_route_colors
    original_login = ui_controls._spina_v32_login_colors
    try:
        ui_controls._spina_v27_route_colors = lambda self=None: dict(COLORS)
        ui_controls._spina_v32_login_colors = lambda self=None: dict(COLORS)

        frame = tk.Frame(root)
        frame.pack()
        for kind in ("normal", "primary", "success", "danger", "soft"):
            verify_button(frame, ui_controls._spina_v32_login_button, kind, 9, 10)
        for kind in ("normal", "primary", "success", "danger", "warning", "soft"):
            verify_button(frame, ui_controls._spina_v27_route_button, kind, 8, 9)

        print("Wave 50 active UI button-factory Tkinter smoke test passed.")
    finally:
        ui_controls._spina_v27_route_colors = original_route
        ui_controls._spina_v32_login_colors = original_login
        root.destroy()


if __name__ == "__main__":
    main()
