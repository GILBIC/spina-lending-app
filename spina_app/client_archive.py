from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Mapping

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

_CLIENT_ARCHIVE_DEPENDENCIES: dict[str, Any] = {}


def configure_client_archive_dependencies(namespace: Mapping[str, Any]) -> None:
    _CLIENT_ARCHIVE_DEPENDENCIES.clear()
    _CLIENT_ARCHIVE_DEPENDENCIES.update(namespace)
    protected = {"__name__", "__file__", "__package__", "__builtins__", "_CLIENT_ARCHIVE_DEPENDENCIES", "configure_client_archive_dependencies"}
    for name, value in namespace.items():
        if name not in protected:
            globals()[name] = value


def _spina_archive_row_to_dict(_row):
    try:
        if _row is None:
            return {}
        if isinstance(_row, sqlite3.Row):
            return dict(_row)
        try:
            return {k: _row[k] for k in _row.keys()}
        except Exception:
            return {}
    except Exception:
        return {}

def _spina_fixed_archive_client(self, name, loan_type=None):
    """Soft-delete: hide the client while keeping transactions/history.

    Fix: after archiving, fetch the new row with include_archived=True so history
    can still see the archived row instead of getting an empty new_row.
    """
    cur = self.conn.cursor()
    lt = self._effective_lt(loan_type)
    self._ensure_archive_columns(cur)
    old_row = self.get_client_info(name, loan_type=lt, include_archived=True) or {}
    if not old_row:
        raise ValueError("Client not found.")
    uid = (old_row.get("client_uid") or "").strip()

    cur.execute(
        """UPDATE clients
              SET is_archived=1,
                  archived_at=datetime('now')
            WHERE name=? AND IFNULL(loan_type,'Regular')=?""",
        (name, lt),
    )
    self.conn.commit()

    try:
        new_row = self.get_client_info(name, loan_type=lt, include_archived=True) or {}
        self._log_client_history(uid, "ARCHIVE", old_row=old_row, new_row=new_row, source="clients:archive")
    except Exception as __spina_exc:
        _log_suppressed_once('archive_fix_log_archive', 'suppressed exception archive_fix_log_archive', __spina_exc)
        pass
    return True

def _spina_fixed_restore_client(self, name, loan_type=None):
    """Restore a previously archived client by name + loan type.

    Important fix: the old code called get_client_info() without include_archived=True.
    Because archived rows are hidden by default, restore failed with "Client not found".
    """
    cur = self.conn.cursor()
    lt = self._effective_lt(loan_type)
    self._ensure_archive_columns(cur)

    old_row = self.get_client_info(name, loan_type=lt, include_archived=True) or {}
    if not old_row:
        try:
            r = cur.execute(
                "SELECT * FROM clients WHERE name=? AND IFNULL(loan_type,'Regular')=? LIMIT 1",
                (name, lt),
            ).fetchone()
            old_row = _spina_archive_row_to_dict(r)
        except Exception:
            old_row = {}
    if not old_row:
        raise ValueError("Client not found in archived list.")

    uid = (old_row.get("client_uid") or "").strip()

    cur.execute(
        """UPDATE clients
              SET is_archived=0,
                  archived_at=NULL
            WHERE name=? AND IFNULL(loan_type,'Regular')=?""",
        (name, lt),
    )
    self.conn.commit()

    try:
        new_row = self.get_client_info(name, loan_type=lt, include_archived=True) or {}
        self._log_client_history(uid, "RESTORE", old_row=old_row, new_row=new_row, source="clients:restore")
    except Exception as __spina_exc:
        _log_suppressed_once('archive_fix_log_restore', 'suppressed exception archive_fix_log_restore', __spina_exc)
        pass
    return True

def _spina_fixed_restore_client_by_uid(self, client_uid):
    """Restore archived client by UID, with name/type fallback support."""
    if not client_uid:
        raise ValueError("Missing client UID.")
    cur = self.conn.cursor()
    self._ensure_archive_columns(cur)
    try:
        r = cur.execute(
            "SELECT name, IFNULL(loan_type,'Regular') AS loan_type FROM clients WHERE client_uid=? LIMIT 1",
            (client_uid,),
        ).fetchone()
    except Exception:
        r = None
    if not r:
        raise ValueError("Client not found by UID.")
    try:
        name = r["name"] if isinstance(r, sqlite3.Row) else r[0]
        lt = r["loan_type"] if isinstance(r, sqlite3.Row) else r[1]
    except Exception:
        name, lt = r[0], r[1]
    return _spina_fixed_restore_client(self, name, loan_type=lt)

def _spina_fixed_open_archived_clients_dialog(self):
    """Archived clients restore dialog with UID fallback and refresh after restore."""
    try:
        win = tk.Toplevel(self.root)
    except Exception:
        win = tk.Toplevel()
    win.title("Archived Clients (Restore)")
    win.geometry("760x520")
    try:
        win.transient(self.root)
    except Exception as __spina_exc:
        _log_suppressed_once('archive_fix_transient', 'suppressed exception archive_fix_transient', __spina_exc)
        pass

    outer = ttk.Frame(win, padding=10)
    outer.pack(fill='both', expand=True)

    top = ttk.Frame(outer)
    top.pack(fill='x')

    ttk.Label(top, text="Archived Clients", style='Section.TLabel').pack(side='left', padx=(0, 10))

    search_var = tk.StringVar()
    ttk.Label(top, text="Search:").pack(side='left')
    ttk.Entry(top, textvariable=search_var, width=26).pack(side='left', padx=6)

    lt_var = tk.StringVar(value="All")
    ttk.Label(top, text="Loan:").pack(side='left', padx=(10,2))
    cb = ttk.Combobox(top, textvariable=lt_var, values=("All","Regular","7x7"), state='readonly', width=10)
    cb.pack(side='left')

    tree = ttk.Treeview(outer, columns=("name","loan_type","area","archived_at"), show='headings', height=18)
    tree.pack(fill='both', expand=True, pady=8)

    tree.heading("name", text="Name")
    tree.heading("loan_type", text="Loan Type")
    tree.heading("area", text="Area")
    tree.heading("archived_at", text="Archived At")

    tree.column("name", width=280, anchor='w')
    tree.column("loan_type", width=90, anchor='center')
    tree.column("area", width=150, anchor='w')
    tree.column("archived_at", width=160, anchor='w')

    status = tk.StringVar(value="")
    ttk.Label(outer, textvariable=status).pack(anchor='w')

    btns = ttk.Frame(outer)
    btns.pack(fill='x', pady=(6,0))

    def load_list(*_):
        try:
            for iid in tree.get_children():
                tree.delete(iid)
        except Exception:
            pass
        lt = lt_var.get()
        loan_type = None if lt == "All" else lt
        term = (search_var.get() or "").strip() or None
        try:
            rows = self.db.get_archived_clients(search=term, loan_type=loan_type) or []
        except Exception:
            rows = []
        if not rows:
            status.set("No archived clients.")
            return
        status.set(f"{len(rows)} archived client(s). Select one and click Restore.")
        for idx, r in enumerate(rows):
            uid = (r.get("client_uid") or "").strip()
            # Use a unique UI iid even when old records have no client_uid.
            if not uid:
                uid = f"__NOUID__|{idx}|{r.get('name','')}|{r.get('loan_type','')}"
            try:
                tree.insert("", "end", iid=uid, values=(r.get("name",""), r.get("loan_type",""), r.get("area",""), (r.get("archived_at","") or "")))
            except Exception:
                # Last-resort insert if an unusual UID causes a Tk iid conflict.
                tree.insert("", "end", values=(r.get("name",""), r.get("loan_type",""), r.get("area",""), (r.get("archived_at","") or "")))

    def restore_selected():
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Restore", "Select an archived client first.")
            return
        uid = sel[0]
        vals = tree.item(uid, "values") or ()
        nm = vals[0] if vals else uid
        lt = vals[1] if len(vals) > 1 else ""
        if not messagebox.askyesno("Confirm", f"Restore '{nm}' ({lt})?"):
            return
        try:
            # Old records may have no client_uid, so restore by name + loan type.
            if str(uid).startswith("__NOUID__|"):
                self.db.restore_client(nm, loan_type=lt)
            else:
                try:
                    self.db.restore_client_by_uid(uid)
                except Exception:
                    self.db.restore_client(nm, loan_type=lt)
        except Exception as e:
            messagebox.showerror("Restore Error", str(e))
            return
        try:
            self.refresh_clients()
        except Exception:
            pass
        try:
            self.refresh_reports()
        except Exception:
            pass
        try:
            self.refresh_data_grid()
        except Exception:
            pass
        try:
            self.refresh_collectors()
        except Exception:
            pass
        load_list()
        messagebox.showinfo("Restored", f"Client '{nm}' restored.")

    ttk.Button(btns, text="Restore Selected", command=restore_selected).pack(side='right')
    ttk.Button(btns, text="Close", command=win.destroy).pack(side='right', padx=6)

    try:
        search_var.trace_add('write', lambda *_: load_list())
    except Exception:
        try:
            search_var.trace('w', lambda *_: load_list())
        except Exception as e2:
            _log_ignored('ui.trace_add failed', e2, key='ui.trace_add_failed')
    try:
        cb.bind("<<ComboboxSelected>>", lambda e: load_list())
    except Exception as e:
        _log_ignored("ui.bind failed", e, key="ui.bind_failed")

    load_list()

def _spina_fixed_get_archived_clients_with_id(self, search=None, loan_type=None):
    """List archived clients and include the internal row id for reliable restore."""
    cur = self.conn.cursor()
    try:
        self._ensure_archive_columns(cur)
    except Exception:
        pass
    try:
        cols = [r[1] for r in cur.execute("PRAGMA table_info(clients)").fetchall()]
    except Exception:
        cols = []
    if "is_archived" not in cols:
        return []

    q = """
        SELECT id,
               IFNULL(client_uid,'') AS client_uid,
               IFNULL(name,'') AS name,
               IFNULL(loan_type,'Regular') AS loan_type,
               IFNULL(area,'') AS area,
               IFNULL(archived_at,'') AS archived_at
          FROM clients
         WHERE COALESCE(is_archived,0)=1
    """
    params = []
    if loan_type:
        try:
            lt = self._effective_lt(loan_type)
        except Exception:
            lt = "7x7" if str(loan_type).strip().lower().replace(" ", "") in ("7x7", "7×7") else "Regular"
        q += " AND IFNULL(loan_type,'Regular')=?"
        params.append(lt)
    if search:
        term = f"%{str(search).strip()}%"
        q += " AND (IFNULL(name,'') LIKE ? OR IFNULL(area,'') LIKE ? OR IFNULL(client_uid,'') LIKE ?)"
        params.extend([term, term, term])
    q += " ORDER BY archived_at DESC, name COLLATE NOCASE, id DESC"

    out = []
    try:
        for r in cur.execute(q, params).fetchall() or []:
            try:
                out.append({
                    "id": r["id"] if isinstance(r, sqlite3.Row) else r[0],
                    "client_uid": r["client_uid"] if isinstance(r, sqlite3.Row) else r[1],
                    "name": r["name"] if isinstance(r, sqlite3.Row) else r[2],
                    "loan_type": r["loan_type"] if isinstance(r, sqlite3.Row) else r[3],
                    "area": r["area"] if isinstance(r, sqlite3.Row) else r[4],
                    "archived_at": r["archived_at"] if isinstance(r, sqlite3.Row) else r[5],
                })
            except Exception:
                continue
    except Exception as __spina_exc:
        try:
            _log_suppressed_once('archive_rowid_list_failed', 'archived client list failed', __spina_exc)
        except Exception:
            pass
    return out

def _spina_fixed_restore_client_by_id(self, client_id):
    """Restore archived client by exact clients.id row."""
    cur = self.conn.cursor()
    try:
        self._ensure_archive_columns(cur)
    except Exception:
        pass
    try:
        cid = int(client_id)
    except Exception:
        raise ValueError("Invalid archived row id.")
    try:
        old = cur.execute("SELECT * FROM clients WHERE id=? LIMIT 1", (cid,)).fetchone()
    except Exception:
        old = None
    old_row = _spina_restore_row_to_dict(old)
    if not old_row:
        raise ValueError("Archived client row not found.")
    try:
        is_arch = int(old_row.get("is_archived") or 0)
    except Exception:
        is_arch = 0
    if is_arch != 1:
        return True
    cur.execute("UPDATE clients SET is_archived=0, archived_at=NULL WHERE id=?", (cid,))
    self.conn.commit()
    try:
        new = cur.execute("SELECT * FROM clients WHERE id=? LIMIT 1", (cid,)).fetchone()
        new_row = _spina_restore_row_to_dict(new)
        uid = str(old_row.get("client_uid") or "").strip()
        if hasattr(self, "_log_client_history"):
            self._log_client_history(uid, "RESTORE", old_row=old_row, new_row=new_row, source="clients:restore_by_id")
    except Exception as __spina_exc:
        try:
            _log_suppressed_once('archive_rowid_log_restore', 'suppressed exception archive rowid log restore', __spina_exc)
        except Exception:
            pass
    return True

def _spina_fixed_open_archived_clients_dialog_rowid(self):
    """Archived clients restore dialog that restores by clients.id first."""
    try:
        win = tk.Toplevel(self.root)
    except Exception:
        win = tk.Toplevel()
    win.title("Archived Clients (Restore)")
    win.geometry("780x530")
    try:
        win.transient(self.root)
    except Exception:
        pass
    outer = ttk.Frame(win, padding=10)
    outer.pack(fill='both', expand=True)
    top = ttk.Frame(outer)
    top.pack(fill='x')
    try:
        ttk.Label(top, text="Archived Clients", style='Section.TLabel').pack(side='left', padx=(0, 10))
    except Exception:
        ttk.Label(top, text="Archived Clients").pack(side='left', padx=(0, 10))
    search_var = tk.StringVar()
    ttk.Label(top, text="Search:").pack(side='left')
    ttk.Entry(top, textvariable=search_var, width=26).pack(side='left', padx=6)
    lt_var = tk.StringVar(value="All")
    ttk.Label(top, text="Loan:").pack(side='left', padx=(10,2))
    cb = ttk.Combobox(top, textvariable=lt_var, values=("All","Regular","7x7"), state='readonly', width=10)
    cb.pack(side='left')
    tree = ttk.Treeview(outer, columns=("id","name","loan_type","area","archived_at"), show='headings', height=18)
    tree.pack(fill='both', expand=True, pady=8)
    for col, txt in (("id","ID"),("name","Name"),("loan_type","Loan Type"),("area","Area"),("archived_at","Archived At")):
        tree.heading(col, text=txt)
    tree.column("id", width=60, anchor='center')
    tree.column("name", width=280, anchor='w')
    tree.column("loan_type", width=90, anchor='center')
    tree.column("area", width=150, anchor='w')
    tree.column("archived_at", width=160, anchor='w')
    status = tk.StringVar(value="")
    ttk.Label(outer, textvariable=status).pack(anchor='w')
    btns = ttk.Frame(outer)
    btns.pack(fill='x', pady=(6,0))

    def _rowid_from_iid(iid):
        try:
            s = str(iid or "")
            if s.startswith("ARCHID::"):
                return int(s.split("::", 1)[1])
        except Exception:
            pass
        try:
            vals = tree.item(iid, "values") or ()
            if vals:
                return int(vals[0])
        except Exception:
            pass
        return None

    def load_list(*_):
        try:
            for iid in tree.get_children():
                tree.delete(iid)
        except Exception:
            pass
        lt = lt_var.get()
        loan_type = None if lt == "All" else lt
        term = (search_var.get() or "").strip() or None
        try:
            rows = self.db.get_archived_clients(search=term, loan_type=loan_type) or []
        except Exception:
            rows = []
        if not rows:
            status.set("No archived clients.")
            return
        status.set(f"{len(rows)} archived client(s). Select one and click Restore.")
        for idx, r in enumerate(rows):
            rid = r.get("id") or r.get("rowid") or ""
            uid = str(r.get("client_uid") or "").strip()
            iid = f"ARCHID::{rid}" if str(rid).strip() else (uid or f"ARCHIDX::{idx}")
            values = (rid, r.get("name",""), r.get("loan_type",""), r.get("area",""), (r.get("archived_at","") or ""))
            try:
                tree.insert("", "end", iid=iid, values=values)
            except Exception:
                try:
                    tree.insert("", "end", values=values)
                except Exception:
                    pass

    def restore_selected():
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Restore", "Select an archived client first.")
            return
        iid = sel[0]
        vals = tree.item(iid, "values") or ()
        rid = _rowid_from_iid(iid)
        nm = vals[1] if len(vals) > 1 else ""
        lt = vals[2] if len(vals) > 2 else ""
        if not messagebox.askyesno("Confirm", f"Restore '{nm}' ({lt})?"):
            return
        try:
            if rid is not None:
                self.db.restore_client_by_id(rid)
            else:
                try:
                    uid = str(iid or "")
                    if uid and not uid.startswith("ARCHIDX::"):
                        self.db.restore_client_by_uid(uid)
                    else:
                        self.db.restore_client(nm, loan_type=lt)
                except Exception:
                    self.db.restore_client(nm, loan_type=lt)
        except Exception as e:
            messagebox.showerror("Restore Error", str(e))
            return
        for _meth in ("refresh_clients", "refresh_reports", "refresh_data_grid", "refresh_collectors"):
            try:
                fn = getattr(self, _meth, None)
                if fn:
                    fn()
            except Exception:
                pass
        load_list()
        messagebox.showinfo("Restored", f"Client '{nm}' restored.")

    ttk.Button(btns, text="Restore Selected", command=restore_selected).pack(side='right')
    ttk.Button(btns, text="Close", command=win.destroy).pack(side='right', padx=6)
    try:
        search_var.trace_add('write', lambda *_: load_list())
    except Exception:
        try:
            search_var.trace('w', lambda *_: load_list())
        except Exception:
            pass
    try:
        cb.bind("<<ComboboxSelected>>", lambda e: load_list())
    except Exception:
        pass
    load_list()

