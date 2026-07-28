"""Backup-history presentation extracted in Wave 68."""
from __future__ import annotations

_BACKUP_HISTORY_DEPENDENCIES = {}
_PROTECTED_GLOBALS = {
    '__name__', '__doc__', '__package__', '__loader__', '__spec__',
    '__file__', '__cached__', '__builtins__',
    '_BACKUP_HISTORY_DEPENDENCIES', '_PROTECTED_GLOBALS',
    'BACKUP_HISTORY_PRESENTATION_METHODS',
    'configure_backup_history_dependencies',
    'open_backup_history_window',
}

def configure_backup_history_dependencies(namespace):
    _BACKUP_HISTORY_DEPENDENCIES.clear()
    _BACKUP_HISTORY_DEPENDENCIES.update(namespace)
    for name, value in namespace.items():
        if name not in _PROTECTED_GLOBALS:
            globals()[name] = value

BACKUP_HISTORY_PRESENTATION_METHODS = {'open_backup_history_window': {'calls': ['_dtm.datetime.fromtimestamp', '_dtm.datetime.fromtimestamp.strftime', '_error', '_log_exc', '_open_path', 'btns.pack', 'enumerate', 'get', 'getattr', 'info.pack', 'messagebox.askyesno', 'messagebox.showerror', 'messagebox.showinfo', 'messagebox.showwarning', 'os.path.exists', 'outer.pack', 'r.get', 'refresh', 'selected_path', 'self._format_bytes', 'self._list_postgres_backup_files', 'self._postgres_backup_dir', 'self._restore_backup_to_test_database', 'self._run_long_task', 'self._verify_postgres_backup_file', 'str', 'strip', 'tk.Toplevel', 'tree.column', 'tree.delete', 'tree.get_children', 'tree.heading', 'tree.insert', 'tree.pack', 'tree.selection', 'ttk.Button', 'ttk.Button.pack', 'ttk.Frame', 'ttk.Label', 'ttk.Treeview', 'win.geometry', 'win.title', 'win.transient'], 'db_calls': [], 'dedented_sha256': '9b0b5a126d64034daef89cc4af646854e0001ec6ce73e4a09ad95642704bd15e', 'lines': 182, 'signature': 'self', 'source_sha256': 'c05501298b2aa308c66f0f668bb482a96de8dc221b098f88705fa6d452c6d59f'}}

def open_backup_history_window(self):
    """Show backup files and provide verify/restore-test actions."""
    try:
        role = (getattr(self, "user_role", "") or "").strip()
    except Exception:
        role = ""
    if role not in ("Admin", "System"):
        try:
            messagebox.showwarning("Backup History", "Only Admin or System users can view backup tools.")
        except Exception:
            pass
        return

    try:
        win = tk.Toplevel(self.root)
        win.title("PostgreSQL Backup History")
        win.geometry("820x420")
        win.transient(self.root)
    except Exception as e:
        try:
            messagebox.showerror("Backup History", f"Could not open backup history window.\n\n{e}")
        except Exception:
            pass
        return

    try:
        outer = ttk.Frame(win, padding=10)
        outer.pack(fill="both", expand=True)

        info = ttk.Label(
            outer,
            text="Backups are stored in the app backups/ folder. Restore Test only uses spina_restore_test and never overwrites spina_db.",
            anchor="w",
            wraplength=780,
        )
        info.pack(fill="x", pady=(0, 8))

        cols = ("created", "filename", "size", "path")
        tree = ttk.Treeview(outer, columns=cols, show="headings", height=12)
        tree.heading("created", text="Created")
        tree.heading("filename", text="File")
        tree.heading("size", text="Size")
        tree.heading("path", text="Path")
        tree.column("created", width=150, anchor="w")
        tree.column("filename", width=240, anchor="w")
        tree.column("size", width=90, anchor="e")
        tree.column("path", width=300, anchor="w")
        tree.pack(fill="both", expand=True)

        self._backup_history_tree = tree
        self._backup_history_paths = {}

        btns = ttk.Frame(outer)
        btns.pack(fill="x", pady=(10, 0))

        def refresh():
            try:
                for iid in tree.get_children():
                    tree.delete(iid)
                self._backup_history_paths = {}
                for idx, r in enumerate(self._list_postgres_backup_files()):
                    try:
                        import datetime as _dtm
                        created = _dtm.datetime.fromtimestamp(r.get("mtime", 0)).strftime("%Y-%m-%d %H:%M:%S")
                    except Exception:
                        created = ""
                    iid = str(idx)
                    path = r.get("path") or ""
                    self._backup_history_paths[iid] = path
                    tree.insert("", "end", iid=iid, values=(created, r.get("name") or "", self._format_bytes(r.get("size")), path))
                if not tree.get_children():
                    tree.insert("", "end", iid="empty", values=("", "No .backup files found", "", self._postgres_backup_dir()))
            except Exception as e:
                try:
                    messagebox.showerror("Backup History", f"Could not refresh backup list.\n\n{e}")
                except Exception:
                    pass

        def selected_path():
            try:
                sel = tree.selection()
                if not sel:
                    messagebox.showinfo("Backup History", "Select a backup file first.")
                    return None
                iid = sel[0]
                path = (getattr(self, "_backup_history_paths", {}) or {}).get(iid)
                if not path or not os.path.exists(path):
                    messagebox.showwarning("Backup History", "Selected backup file was not found.")
                    return None
                return path
            except Exception:
                return None

        def open_folder():
            try:
                _open_path(self._postgres_backup_dir())
            except Exception:
                pass

        def verify():
            path = selected_path()
            if not path:
                return
            def _success(msg):
                try:
                    messagebox.showinfo("Backup Verified", str(msg))
                except Exception:
                    pass
            def _error(exc):
                try:
                    _log_exc("backup_verify", exc)
                except Exception:
                    pass
                try:
                    messagebox.showerror("Verify Failed", f"Could not verify backup.\n\n{exc}")
                except Exception:
                    pass
            try:
                self._run_long_task(
                    "Verifying backup...",
                    lambda cancel_event=None, p=path: self._verify_postgres_backup_file(p, cancel_event=cancel_event),
                    on_success=_success,
                    on_error=_error,
                    allow_cancel=False,
                    timeout_s=None,
                )
            except Exception as e:
                _error(e)

        def restore_test():
            path = selected_path()
            if not path:
                return
            try:
                ok = messagebox.askyesno(
                    "Restore Test Database",
                    "This will DROP and recreate only this test database:\n\n"
                    "spina_restore_test\n\n"
                    "It will NOT overwrite your live spina_db. Continue?"
                )
            except Exception:
                ok = False
            if not ok:
                return
            def _success(msg):
                try:
                    messagebox.showinfo("Restore Test Complete", str(msg))
                except Exception:
                    pass
            def _error(exc):
                try:
                    _log_exc("backup_restore_test", exc)
                except Exception:
                    pass
                try:
                    messagebox.showerror("Restore Test Failed", f"Could not restore backup into spina_restore_test.\n\n{exc}")
                except Exception:
                    pass
            try:
                self._run_long_task(
                    "Restoring backup into spina_restore_test...",
                    lambda cancel_event=None, p=path: self._restore_backup_to_test_database(p, cancel_event=cancel_event),
                    on_success=_success,
                    on_error=_error,
                    allow_cancel=False,
                    timeout_s=None,
                )
            except Exception as e:
                _error(e)

        ttk.Button(btns, text="Refresh", command=refresh).pack(side="left")
        ttk.Button(btns, text="Open Backup Folder", command=open_folder).pack(side="left", padx=(6, 0))
        ttk.Button(btns, text="Verify Selected", command=verify).pack(side="left", padx=(6, 0))
        ttk.Button(btns, text="Restore Test DB", command=restore_test).pack(side="left", padx=(6, 0))
        ttk.Button(btns, text="Close", command=win.destroy).pack(side="right")

        refresh()
    except Exception as e:
        try:
            messagebox.showerror("Backup History", f"Backup history window failed.\n\n{e}")
        except Exception:
            pass
