"""Modern account login dialog presentation extracted in Wave 45."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

_LOGIN_DIALOG_DEPENDENCIES = {}
_PROTECTED_GLOBALS = {'messagebox', 'LOGIN_DIALOG_TARGET', 'LOGIN_DIALOG_SIGNATURE', 'configure_login_dialog_dependencies', 'LOGIN_DIALOG_SOURCE_SHA256', '__builtins__', 'ttk', 'tk', '__name__', 'LOGIN_DIALOG_NESTED_CALLBACKS', '__doc__', '_PROTECTED_GLOBALS', 'LOGIN_DIALOG_CALLS', '__file__', '__spec__', '_LOGIN_DIALOG_DEPENDENCIES', '__package__', '__cached__', 'LOGIN_DIALOG_SOURCE_LINES', '__loader__'}

def configure_login_dialog_dependencies(namespace):
    _LOGIN_DIALOG_DEPENDENCIES.clear()
    _LOGIN_DIALOG_DEPENDENCIES.update(namespace)
    for name, value in namespace.items():
        if name not in _PROTECTED_GLOBALS:
            globals()[name] = value

LOGIN_DIALOG_TARGET = '_spina_v32_prompt_login'
LOGIN_DIALOG_SOURCE_LINES = 234
LOGIN_DIALOG_SOURCE_SHA256 = '0dc7c87e702bf93da77bbf6a9fc490a005114716e4ef487f10a203bfe75e48a3'
LOGIN_DIALOG_SIGNATURE = "self, default_user: str='admin'"
LOGIN_DIALOG_NESTED_CALLBACKS = ['_toggle_show', '_refresh_account_info', '_ok', '_cancel', '_enter']
LOGIN_DIALOG_CALLS = ['_log_exc', '_log_suppressed_once', '_ok', '_refresh_account_info', '_spina_v32_account_choices', '_spina_v32_account_permission_text', '_spina_v32_login_button', '_spina_v32_login_colors', '_spina_v32_selected_label_for_user', 'account_cb.bind', 'account_cb.pack', 'account_info_var.set', 'account_var.get', 'account_var.trace_add', 'btns.pack', 'card.pack', 'db.get', 'dlg.configure', 'dlg.destroy', 'dlg.geometry', 'dlg.grab_release', 'dlg.grab_set', 'dlg.resizable', 'dlg.title', 'dlg.transient', 'dlg.update_idletasks', 'dlg.winfo_screenheight', 'dlg.winfo_screenwidth', 'form.pack', 'get', 'label_to_user.get', 'left.pack', 'left.pack_propagate', 'max', 'min', 'msg_lbl.pack', 'msg_var.set', 'pack', 'pw_entry.bind', 'pw_entry.configure', 'pw_entry.focus_set', 'pw_entry.pack', 'pw_entry.selection_range', 'pw_var.get', 'rec.get', 'result.get', 'right.pack', 'right.pack_propagate', 'self._force_change_password_dialog', 'self._load_users_db', 'self._must_change_password', 'self._verify_login', 'self.root.wait_window', 'self.root.winfo_height', 'self.root.winfo_rootx', 'self.root.winfo_rooty', 'self.root.winfo_width', 'shell.pack', 'show_var.get', 'str', 'strip', 'tk.BooleanVar', 'tk.Frame', 'tk.Label', 'tk.StringVar', 'tk.Toplevel', 'ttk.Checkbutton', 'ttk.Combobox', 'ttk.Entry']

def _spina_v32_prompt_login(self, default_user: str = "admin"):
    """Modern account-based login dialog. Returns (username, internal_access_profile)."""
    import tkinter as tk
    from tkinter import ttk, messagebox

    c = _spina_v32_login_colors(self)
    family = "Segoe UI" if os.name == "nt" else "TkDefaultFont"

    try:
        db = self._load_users_db()
        users = db.get("users") or {}
    except Exception:
        users = {}

    choices, label_to_user = _spina_v32_account_choices(self, users=users)
    if not choices:
        choices, label_to_user = ["Owner Account"], {"Owner Account": "admin"}

    selected_label = _spina_v32_selected_label_for_user(self, default_user, choices, label_to_user)

    result = {"user": None, "role": None}

    dlg = tk.Toplevel(self.root)
    dlg.title("Account Sign In")
    dlg.configure(bg=c["bg"])
    dlg.resizable(False, False)

    try:
        dlg.transient(self.root)
    except Exception as __spina_exc:
        _log_suppressed_once('pure_login_dialog_ui.transient', 'suppressed pure login dialog UI exception: login_dialog_transient', __spina_exc)
        pass

    # Main shell
    shell = tk.Frame(dlg, bg=c["bg"], padx=18, pady=18)
    shell.pack(fill="both", expand=True)

    card = tk.Frame(shell, bg=c["panel"], highlightbackground=c["border"], highlightthickness=1, bd=0)
    card.pack(fill="both", expand=True)

    left = tk.Frame(card, bg=c["left"], width=260)
    left.pack(side="left", fill="both")
    left.pack_propagate(False)

    tk.Label(left, text="SPINA", bg=c["left"], fg=c["left_fg"], font=(family, 24, "bold"), anchor="w").pack(fill="x", padx=24, pady=(34, 0))
    tk.Label(left, text="Account-based sign in", bg=c["left"], fg=c["left_muted"], font=(family, 11, "bold"), anchor="w").pack(fill="x", padx=24, pady=(6, 0))
    tk.Label(
        left,
        text="Each account keeps its own access permissions. No need to choose Admin, Viewer, Collector, or System during login.",
        bg=c["left"],
        fg=c["left_muted"],
        font=(family, 9),
        justify="left",
        wraplength=210,
        anchor="nw",
    ).pack(fill="x", padx=24, pady=(28, 0))

    tk.Frame(left, bg="#1f2937", height=1).pack(fill="x", padx=24, pady=(28, 14))
    tk.Label(
        left,
        text="Tip: use Switch Account from the header when another person needs to use the app.",
        bg=c["left"],
        fg=c["left_muted"],
        font=(family, 8),
        justify="left",
        wraplength=210,
        anchor="nw",
    ).pack(fill="x", padx=24, pady=(0, 0))

    right = tk.Frame(card, bg=c["panel"], width=430)
    right.pack(side="left", fill="both", expand=True)
    right.pack_propagate(False)

    tk.Label(right, text="Welcome back", bg=c["panel"], fg=c["fg"], font=(family, 20, "bold"), anchor="w").pack(fill="x", padx=28, pady=(32, 0))
    tk.Label(right, text="Sign in with your account.", bg=c["panel"], fg=c["muted"], font=(family, 10), anchor="w").pack(fill="x", padx=28, pady=(4, 18))

    form = tk.Frame(right, bg=c["panel"])
    form.pack(fill="x", padx=28)

    tk.Label(form, text="Account", bg=c["panel"], fg=c["muted"], font=(family, 9, "bold"), anchor="w").pack(fill="x")
    account_var = tk.StringVar(value=selected_label)
    account_cb = ttk.Combobox(form, textvariable=account_var, values=choices, state="readonly", width=32)
    account_cb.pack(fill="x", pady=(4, 12), ipady=3)

    account_info_var = tk.StringVar(value="")
    tk.Label(form, textvariable=account_info_var, bg=c["panel"], fg=c["muted"], font=(family, 8), anchor="w").pack(fill="x", pady=(0, 8))

    tk.Label(form, text="Password", bg=c["panel"], fg=c["muted"], font=(family, 9, "bold"), anchor="w").pack(fill="x")
    pw_var = tk.StringVar(value="")
    pw_entry = ttk.Entry(form, textvariable=pw_var, show="*", width=34)
    pw_entry.pack(fill="x", pady=(4, 8), ipady=3)

    show_var = tk.BooleanVar(value=False)
    def _toggle_show():
        try:
            pw_entry.configure(show="" if show_var.get() else "*")
        except Exception:
            pass

    try:
        ttk.Checkbutton(form, text="Show password", variable=show_var, command=_toggle_show).pack(anchor="w", pady=(0, 8))
    except Exception:
        pass

    msg_var = tk.StringVar(value="")
    msg_lbl = tk.Label(form, textvariable=msg_var, bg=c["panel"], fg=c["red"], font=(family, 9, "bold"), anchor="w", justify="left", wraplength=360)
    msg_lbl.pack(fill="x", pady=(0, 8))

    btns = tk.Frame(right, bg=c["panel"])
    btns.pack(fill="x", padx=28, pady=(4, 0))

    def _refresh_account_info(*_):
        try:
            label = account_var.get()
            username = label_to_user.get(label, label)
            rec = (users or {}).get(username) or {}
            summary = str(rec.get("permission_summary") or _spina_v32_account_permission_text(rec.get("role")) or "").strip()
            if summary:
                account_info_var.set(summary)
            else:
                account_info_var.set("Account permissions will be loaded after sign in.")
        except Exception:
            account_info_var.set("Account permissions will be loaded after sign in.")

    def _ok():
        label = (account_var.get() or "").strip()
        username = str(label_to_user.get(label, label) or "").strip()
        password = pw_var.get() or ""

        if not username:
            msg_var.set("Please choose an account.")
            return

        role = self._verify_login(username, password)
        if not role:
            msg_var.set("Invalid account or password.")
            try:
                pw_entry.focus_set()
                pw_entry.selection_range(0, "end")
            except Exception:
                pass
            return

        try:
            if self._must_change_password(username, password):
                if not self._force_change_password_dialog(username, old_password=password):
                    msg_var.set("Password change required to continue.")
                    return
        except Exception:
            try:
                _log_exc("force_change_password")
            except Exception:
                pass
            msg_var.set("Password change required, but the change dialog failed. See log.")
            return

        result["user"] = username
        result["role"] = role
        try:
            dlg.grab_release()
        except Exception:
            pass
        dlg.destroy()

    def _cancel():
        try:
            dlg.grab_release()
        except Exception:
            pass
        dlg.destroy()

    _spina_v32_login_button(btns, "Sign In", command=_ok, kind="primary").pack(side="right")
    _spina_v32_login_button(btns, "Cancel", command=_cancel, kind="soft").pack(side="right", padx=(0, 8))

    tk.Label(
        right,
        text="Existing passwords are unchanged. Default accounts still require password change on first login.",
        bg=c["panel"],
        fg=c["muted"],
        font=(family, 8),
        anchor="w",
        justify="left",
        wraplength=360,
    ).pack(fill="x", padx=28, pady=(16, 0))

    try:
        account_var.trace_add("write", _refresh_account_info)
    except Exception as __spina_exc:
        _log_suppressed_once('pure_login_dialog_ui.account_trace', 'suppressed pure login dialog UI exception: login_dialog_account_trace', __spina_exc)
        pass
    _refresh_account_info()

    def _enter(_=None):
        _ok()

    try:
        pw_entry.bind("<Return>", _enter)
        account_cb.bind("<Return>", _enter)
    except Exception as __spina_exc:
        _log_suppressed_once('pure_login_dialog_ui.return_bind', 'suppressed pure login dialog UI exception: login_dialog_return_bind', __spina_exc)
        pass

    try:
        dlg.grab_set()
    except Exception as __spina_exc:
        _log_suppressed_once('pure_login_dialog_ui.grab_set', 'suppressed pure login dialog UI exception: login_dialog_grab_set', __spina_exc)
        pass

    try:
        dlg.update_idletasks()
        w, h = 735, 455
        sw, sh = dlg.winfo_screenwidth(), dlg.winfo_screenheight()
        try:
            rx, ry = self.root.winfo_rootx(), self.root.winfo_rooty()
            rw, rh = self.root.winfo_width(), self.root.winfo_height()
            x = rx + (rw - w) // 2
            y = ry + (rh - h) // 2
        except Exception:
            x = (sw - w) // 2
            y = (sh - h) // 2
        x = max(10, min(x, sw - w - 10))
        y = max(10, min(y, sh - h - 60))
        dlg.geometry(f"{w}x{h}+{x}+{y}")
    except Exception as __spina_exc:
        _log_suppressed_once('pure_login_dialog_ui.position', 'suppressed pure login dialog UI exception: login_dialog_position', __spina_exc)
        pass

    try:
        pw_entry.focus_set()
    except Exception:
        pass

    self.root.wait_window(dlg)
    return (result.get("user"), result.get("role"))
