from __future__ import annotations

import os
import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from spina_app import login_dialog_presentation as presentation


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


def top_level(root: tk.Tk) -> tk.Toplevel:
    tops = [child for child in root.winfo_children() if isinstance(child, tk.Toplevel)]
    assert len(tops) == 1, tops
    return tops[0]


def find_button(dialog: tk.Toplevel, text: str) -> ttk.Button:
    matches = [
        widget for widget in descendants(dialog)
        if isinstance(widget, ttk.Button) and str(widget.cget("text")) == text
    ]
    assert len(matches) == 1, (text, matches)
    return matches[0]


class DummyApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.verify_calls: list[tuple[str, str]] = []
        self.password_change_calls: list[tuple[str, str]] = []

    def _load_users_db(self):
        return {
            "users": {
                "admin": {
                    "role": "Admin",
                    "permission_summary": "Full owner access",
                }
            }
        }

    def _verify_login(self, username: str, password: str):
        self.verify_calls.append((username, password))
        if username == "admin" and password == "secret":
            return "Admin"
        return None

    def _must_change_password(self, username: str, password: str):
        return False

    def _force_change_password_dialog(self, username: str, old_password: str):
        self.password_change_calls.append((username, old_password))
        return True


def configure_dependencies() -> None:
    colors = {
        "bg": "#f4f5f7",
        "panel": "#ffffff",
        "border": "#d1d5db",
        "left": "#111827",
        "left_fg": "#ffffff",
        "left_muted": "#d1d5db",
        "fg": "#111827",
        "muted": "#6b7280",
        "red": "#b91c1c",
    }

    def account_choices(_self, users=None):
        assert users and "admin" in users
        return ["Owner Account"], {"Owner Account": "admin"}

    def login_button(parent, text, command, kind="soft"):
        assert kind in {"soft", "primary"}
        return ttk.Button(parent, text=text, command=command)

    presentation.configure_login_dialog_dependencies(
        {
            "os": os,
            "_log_exc": lambda *_args, **_kwargs: None,
            "_log_suppressed_once": lambda *_args, **_kwargs: None,
            "_spina_v32_login_colors": lambda _self: colors,
            "_spina_v32_account_choices": account_choices,
            "_spina_v32_selected_label_for_user": lambda _self, _user, choices, _mapping: choices[0],
            "_spina_v32_account_permission_text": lambda role: f"{role or 'Account'} permissions",
            "_spina_v32_login_button": login_button,
        }
    )


def run_sign_in(root: tk.Tk, app: DummyApp) -> None:
    errors: list[BaseException] = []

    def action():
        try:
            dialog = top_level(root)
            assert dialog.title() == "Account Sign In"
            widgets = list(descendants(dialog))
            combos = [widget for widget in widgets if isinstance(widget, ttk.Combobox)]
            entries = [
                widget for widget in widgets
                if isinstance(widget, ttk.Entry) and not isinstance(widget, ttk.Combobox)
            ]
            assert len(combos) == 1, combos
            assert combos[0].get() == "Owner Account"
            assert len(entries) == 1, entries
            entries[0].delete(0, "end")
            entries[0].insert(0, "secret")
            find_button(dialog, "Sign In").invoke()
        except BaseException as exc:
            errors.append(exc)
            for child in root.winfo_children():
                if isinstance(child, tk.Toplevel):
                    child.destroy()

    root.after(100, action)
    result = presentation._spina_v32_prompt_login(app, default_user="admin")
    assert not errors, errors
    assert result == ("admin", "Admin"), result
    assert app.verify_calls == [("admin", "secret")], app.verify_calls
    assert not app.password_change_calls


def run_cancel(root: tk.Tk, app: DummyApp) -> None:
    errors: list[BaseException] = []

    def action():
        try:
            dialog = top_level(root)
            find_button(dialog, "Cancel").invoke()
        except BaseException as exc:
            errors.append(exc)
            for child in root.winfo_children():
                if isinstance(child, tk.Toplevel):
                    child.destroy()

    before = list(app.verify_calls)
    root.after(100, action)
    result = presentation._spina_v32_prompt_login(app, default_user="admin")
    assert not errors, errors
    assert result == (None, None), result
    assert app.verify_calls == before


def main() -> None:
    configure_dependencies()
    root = tk.Tk()
    root.withdraw()
    try:
        app = DummyApp(root)
        run_sign_in(root, app)
        run_cancel(root, app)
    finally:
        root.destroy()
    print("Wave 45 login-dialog Tkinter smoke test passed.")


if __name__ == "__main__":
    main()
