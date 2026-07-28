"""Settings dialog presentation extracted in Wave 65."""
from __future__ import annotations

_SETTINGS_DIALOG_DEPENDENCIES = {}
_PROTECTED_GLOBALS = {
    '__name__', '__doc__', '__package__', '__loader__', '__spec__',
    '__file__', '__cached__', '__builtins__',
    '_SETTINGS_DIALOG_DEPENDENCIES', '_PROTECTED_GLOBALS',
    'SETTINGS_DIALOG_PRESENTATION_METHODS',
    'configure_settings_dialog_dependencies', 'open_settings_dialog',
}

def configure_settings_dialog_dependencies(namespace):
    _SETTINGS_DIALOG_DEPENDENCIES.clear()
    _SETTINGS_DIALOG_DEPENDENCIES.update(namespace)
    for name, value in namespace.items():
        if name not in _PROTECTED_GLOBALS:
            globals()[name] = value

SETTINGS_DIALOG_PRESENTATION_METHODS = {"open_settings_dialog": {"calls": ["_can_use_dir", "_get_reports_root", "_log_exc", "_log_suppressed_once", "_open_path", "_open_target", "_save_auto_close_setting_only", "_t.startswith", "auto_close_days_var.get", "auto_row.pack", "auto_spin.pack", "btns.pack", "dark_var.get", "data_info.columnconfigure", "data_info.pack", "data_path", "dict", "dlg.destroy", "dlg.geometry", "dlg.grab_set", "dlg.title", "dlg.transient", "dlg.update_idletasks", "dlg.winfo_height", "dlg.winfo_width", "enumerate", "filedialog.askdirectory", "float", "globals", "hasattr", "int", "load_settings", "max", "messagebox.showerror", "messagebox.showinfo", "messagebox.showwarning", "nb.add", "nb.pack", "open_row1.pack", "open_row2.pack", "os.path.join", "outer.pack", "rep_ent.pack", "rep_row.pack", "reports_var.get", "reports_var.set", "s.get", "save_settings", "self._users_db_path", "self.root.winfo_height", "self.root.winfo_rootx", "self.root.winfo_rooty", "self.root.winfo_width", "self.run_auto_daily_close", "self.set_theme", "str", "str.strip", "str.strip.lower", "strip", "tk.BooleanVar", "tk.StringVar", "tk.Toplevel", "ttk.Button", "ttk.Button.pack", "ttk.Checkbutton", "ttk.Checkbutton.pack", "ttk.Entry", "ttk.Frame", "ttk.Label", "ttk.Label.grid", "ttk.Label.pack", "ttk.Notebook", "ttk.Separator", "ttk.Separator.pack", "ttk.Spinbox", "val.configure", "val.grid", "val.insert"], "db_calls": [], "dedented_sha256": "13de166ef2b91828fd001a3e7af16de9539c9153a7f9cd8ec3013e0520f396a8", "lines": 288, "signature": "self", "source_sha256": "bd74c40f81adcd19d97c31ad9a0bd3fd398879053a09e99e8f316f2a27ff6441"}}

def open_settings_dialog(self):
    """App settings (local-only)."""
    dlg = tk.Toplevel(self.root)
    dlg.title("Settings")
    dlg.transient(self.root)
    try:
        dlg.grab_set()
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_0349', 'suppressed exception excpass_0349', __spina_exc)
        pass

    outer = ttk.Frame(dlg, padding=14)
    outer.pack(fill="both", expand=True)

    # Load current settings (theme + reports folder)
    try:
        s = load_settings()
    except Exception:
        s = dict(_DEFAULT_SETTINGS)

    nb = ttk.Notebook(outer)
    nb.pack(fill='both', expand=True)

    tab_general = ttk.Frame(nb, padding=12)
    tab_data = ttk.Frame(nb, padding=12)
    nb.add(tab_general, text='General')
    nb.add(tab_data, text='Data')

    # ---------------- General tab ----------------
    ttk.Label(tab_general, text="Appearance", font=("TkDefaultFont", 11, "bold")).pack(anchor='w')
    try:
        _t = str(s.get('ui_theme') or 'dark').strip().lower()
    except Exception:
        _t = 'dark'
    dark_var = tk.BooleanVar(value=_t.startswith('d'))
    try:
        ttk.Checkbutton(
            tab_general,
            text="Dark mode (easier on the eyes)",
            variable=dark_var,
            command=lambda: self.set_theme('dark' if dark_var.get() else 'light', persist=True)
        ).pack(anchor='w', pady=(6, 0))
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_0350', 'suppressed exception excpass_0350', __spina_exc)
        pass

    try:
        ttk.Separator(tab_general).pack(fill='x', pady=(12, 12))
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_0351', 'suppressed exception excpass_0351', __spina_exc)
        pass
    ttk.Label(tab_general, text="Reports folder (optional)", font=("TkDefaultFont", 11, "bold")).pack(anchor="w")
    ttk.Label(
        tab_general,
        text=("If set, generated PDFs will be saved here.\n"
              "Leave blank to use the default Client_Statements folder."),
        justify="left"
    ).pack(anchor="w", pady=(4, 8))

    reports_var = tk.StringVar(value=str(s.get("reports_root") or "").strip())

    rep_row = ttk.Frame(tab_general)
    rep_row.pack(fill="x")
    rep_ent = ttk.Entry(rep_row, textvariable=reports_var)
    rep_ent.pack(side="left", fill="x", expand=True)

    def _browse_reports():
        try:
            p = filedialog.askdirectory(parent=dlg, title="Select Reports Folder")
        except Exception:
            p = ""
        if p:
            try:
                reports_var.set(p)
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_0352', 'suppressed exception excpass_0352', __spina_exc)
                pass

    try:
        ttk.Button(rep_row, text="Browse…", command=_browse_reports).pack(side="left", padx=(8, 0))
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_0353', 'suppressed exception excpass_0353', __spina_exc)
        pass

    try:
        ttk.Separator(tab_general).pack(fill='x', pady=(14, 12))
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_auto_close_sep', 'suppressed exception excpass_auto_close_sep', __spina_exc)
        pass

    ttk.Label(tab_general, text="Auto Daily Close", font=("TkDefaultFont", 11, "bold")).pack(anchor="w")
    ttk.Label(
        tab_general,
        text=("Control when Data Bank days are automatically closed.\n"
              "Example: 3 = auto-close days once they are 3 days old. 0 = disabled."),
        justify="left"
    ).pack(anchor="w", pady=(4, 8))

    auto_row = ttk.Frame(tab_general)
    auto_row.pack(fill="x", pady=(0, 4))
    ttk.Label(auto_row, text="Auto-close after").pack(side="left")
    try:
        auto_close_days_var = tk.StringVar(value=str(int(s.get("auto_close_after_days", 0) or 0)))
    except Exception:
        auto_close_days_var = tk.StringVar(value="0")
    try:
        auto_spin = ttk.Spinbox(auto_row, from_=0, to=365, width=6, textvariable=auto_close_days_var)
    except Exception:
        auto_spin = ttk.Entry(auto_row, width=6, textvariable=auto_close_days_var)
    auto_spin.pack(side="left", padx=(6, 6))
    ttk.Label(auto_row, text="day(s)").pack(side="left")

    def _save_auto_close_setting_only():
        try:
            d = int(float(str(auto_close_days_var.get() or 0).strip()))
        except Exception:
            messagebox.showerror("Auto Daily Close", "Enter a valid number of days from 0 to 365.", parent=dlg)
            return False
        if d < 0 or d > 365:
            messagebox.showerror("Auto Daily Close", "Auto-close days must be from 0 to 365. Use 0 to disable.", parent=dlg)
            return False
        try:
            s_tmp = load_settings()
        except Exception:
            s_tmp = dict(_DEFAULT_SETTINGS)
        s_tmp["auto_close_after_days"] = d
        if not save_settings(s_tmp):
            messagebox.showerror("Auto Daily Close", f"Failed to save settings file:\n{SETTINGS_FILE}", parent=dlg)
            return False
        return True

    def _run_auto_close_now():
        if not _save_auto_close_setting_only():
            return
        try:
            if hasattr(self, 'run_auto_daily_close'):
                self.run_auto_daily_close(show_message=True)
            else:
                messagebox.showinfo("Auto Daily Close", "Auto-close engine is not available in this build yet.", parent=dlg)
        except Exception as e:
            try:
                _log_exc('settings.run_auto_close_now', e)
            except Exception:
                pass
            messagebox.showerror("Auto Daily Close", str(e), parent=dlg)

    ttk.Button(tab_general, text="Run Auto Close Check Now", command=_run_auto_close_now).pack(anchor="w", pady=(4, 0))

    # ---------------- Data tab ----------------
    ttk.Label(tab_data, text="System Data", font=("TkDefaultFont", 11, "bold")).pack(anchor='w')
    ttk.Label(
        tab_data,
        text="These are the local files and folders used by this PC.",
        justify='left'
    ).pack(anchor='w', pady=(4, 10))

    data_info = ttk.Frame(tab_data)
    data_info.pack(fill='x', expand=False)
    data_info.columnconfigure(1, weight=1)

    users_path = self._users_db_path() if hasattr(self, '_users_db_path') else data_path('users.json')
    log_path = _LOG_FILE or os.path.join(DATA_DIR, 'spina_app.log')
    info_rows = [
        ('Database file', DB_FILE),
        ('Data folder', DATA_DIR),
        ('Settings file', SETTINGS_FILE),
        ('Users file', users_path),
        ('Notes file', CLIENT_NOTES_PATH),
        ('Reports folder', _get_reports_root() if '_get_reports_root' in globals() else PDF_DIR),
        ('Log file', log_path),
    ]
    for r_idx, (label_text, value_text) in enumerate(info_rows):
        ttk.Label(data_info, text=label_text + ':', font=("TkDefaultFont", 9, 'bold')).grid(row=r_idx, column=0, sticky='nw', padx=(0, 8), pady=3)
        try:
            val = ttk.Entry(data_info)
            val.grid(row=r_idx, column=1, sticky='ew', pady=3)
            val.insert(0, str(value_text or ''))
            val.configure(state='readonly')
        except Exception:
            ttk.Label(data_info, text=str(value_text or ''), justify='left').grid(row=r_idx, column=1, sticky='w', pady=3)

    try:
        ttk.Separator(tab_data).pack(fill='x', pady=(12, 10))
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_settings_data_sep', 'suppressed exception excpass_settings_data_sep', __spina_exc)
        pass

    ttk.Label(tab_data, text="Quick Open", font=("TkDefaultFont", 10, "bold")).pack(anchor='w')
    open_row1 = ttk.Frame(tab_data)
    open_row1.pack(fill='x', pady=(6, 0))
    open_row2 = ttk.Frame(tab_data)
    open_row2.pack(fill='x', pady=(6, 0))

    def _open_target(p, title):
        try:
            ok = _open_path(p)
        except Exception:
            ok = False
        if not ok:
            try:
                messagebox.showinfo(title, str(p or ''))
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_settings_open_target', 'suppressed exception excpass_settings_open_target', __spina_exc)
                pass

    ttk.Button(open_row1, text='Open Data Folder', command=lambda: _open_target(DATA_DIR, 'Data Folder')).pack(side='left', padx=(0, 6))
    ttk.Button(open_row1, text='Open Reports Folder', command=lambda: _open_target(_get_reports_root() if '_get_reports_root' in globals() else PDF_DIR, 'Reports Folder')).pack(side='left', padx=6)
    ttk.Button(open_row1, text='Open Database File', command=lambda: _open_target(DB_FILE, 'Database File')).pack(side='left', padx=6)

    ttk.Button(open_row2, text='Open Users File', command=lambda: _open_target(users_path, 'Users File')).pack(side='left', padx=(0, 6))
    ttk.Button(open_row2, text='Open Notes File', command=lambda: _open_target(CLIENT_NOTES_PATH, 'Notes File')).pack(side='left', padx=6)
    ttk.Button(open_row2, text='Open Log File', command=lambda: _open_target(log_path, 'Log File')).pack(side='left', padx=6)

    info_var = tk.StringVar(value=f"Database: {DB_FILE}\nData folder: {DATA_DIR}")
    ttk.Label(tab_general, textvariable=info_var, justify="left").pack(anchor="w", pady=(10, 6))

    btns = ttk.Frame(outer)
    btns.pack(fill="x", pady=(10, 0))

    def _test_reports():
        p = (reports_var.get() or "").strip()
        if not p:
            messagebox.showwarning("Test", "Reports folder is empty.")
            return
        ok = False
        try:
            ok = _can_use_dir(p)
        except Exception:
            ok = False
        if ok:
            messagebox.showinfo("Test", "OK: Can read/write to this folder.")
        else:
            messagebox.showerror("Test", "Not accessible / not writable.\n\nChoose another folder.")

    def _save():
        try:
            s2 = load_settings()
        except Exception:
            s2 = dict(_DEFAULT_SETTINGS)

        # Theme is already persisted by set_theme(); still store a copy for consistency.
        try:
            s2["ui_theme"] = "dark" if dark_var.get() else "light"
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0354', 'suppressed exception excpass_0354', __spina_exc)
            pass

        try:
            s2["reports_root"] = str(reports_var.get() or "").strip()
        except Exception:
            s2["reports_root"] = ""

        try:
            _acd = int(float(str(auto_close_days_var.get() or 0).strip()))
        except Exception:
            messagebox.showerror("Save", "Auto-close days must be a number from 0 to 365. Use 0 to disable.")
            return
        if _acd < 0 or _acd > 365:
            messagebox.showerror("Save", "Auto-close days must be from 0 to 365. Use 0 to disable.")
            return
        s2["auto_close_after_days"] = _acd

        if not save_settings(s2):
            messagebox.showerror("Save", f"Failed to save settings file:\n{SETTINGS_FILE}")
            return
        try:
            dlg.destroy()
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0355', 'suppressed exception excpass_0355', __spina_exc)
            pass

    try:
        ttk.Button(btns, text="Test", command=_test_reports).pack(side="left")
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_0356', 'suppressed exception excpass_0356', __spina_exc)
        pass
    ttk.Button(btns, text="Cancel", command=lambda: dlg.destroy()).pack(side="right")
    ttk.Button(btns, text="Save", command=_save).pack(side="right", padx=(0, 8))

    # Center dialog (best-effort)
    try:
        dlg.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() // 2) - (dlg.winfo_width() // 2)
        y = self.root.winfo_rooty() + (self.root.winfo_height() // 2) - (dlg.winfo_height() // 2)
        dlg.geometry(f"+{max(x, 0)}+{max(y, 0)}")
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_0357', 'suppressed exception excpass_0357', __spina_exc)
        pass
