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

_CLIENT_PICTURE_DEPENDENCIES: dict[str, Any] = {}


def configure_client_picture_dependencies(namespace: Mapping[str, Any]) -> None:
    _CLIENT_PICTURE_DEPENDENCIES.clear()
    _CLIENT_PICTURE_DEPENDENCIES.update(namespace)
    protected = {"__name__", "__file__", "__package__", "__builtins__", "_CLIENT_PICTURE_DEPENDENCIES", "configure_client_picture_dependencies"}
    for name, value in namespace.items():
        if name not in protected:
            globals()[name] = value


def _spina__ensure_client_picture_column(db_obj):
    """Best-effort lazy migration for client_picture support."""
    try:
        cur = db_obj.conn.cursor()
        cols = [r[1] for r in cur.execute("PRAGMA table_info(clients)").fetchall()]
        if "client_picture" not in cols:
            cur.execute("ALTER TABLE clients ADD COLUMN client_picture TEXT DEFAULT ''")
            db_obj.conn.commit()
    except Exception as e:
        try:
            _log_exc('schema:ensure client_picture', e)
        except Exception:
            pass

def _spina__client_pictures_dir():
    try:
        p = data_path('client_pictures')
    except Exception:
        p = os.path.join(APP_DIR, 'data', 'client_pictures')
    try:
        os.makedirs(p, exist_ok=True)
    except Exception:
        pass
    return p

def _spina__resolve_app_path(p):
    try:
        s = str(p or '').strip()
    except Exception:
        s = ''
    if not s:
        return ''
    # V9: client pictures may now be stored in PostgreSQL as dbpic:<id>.
    try:
        if s.lower().startswith('dbpic:'):
            restored = _spina_pg_restore_client_picture_to_cache(s)
            if restored:
                return restored
    except Exception:
        pass
    if os.path.isabs(s):
        return s
    return os.path.abspath(os.path.join(APP_DIR, s))

def _spina__store_client_picture_file(src_path, client_uid):
    src = str(src_path or '').strip()
    uid = str(client_uid or '').strip()
    if not src or not uid:
        return ''
    # V9: save picture bytes into PostgreSQL first. If that fails, use the old
    # local-file storage as emergency fallback.
    try:
        tok = _spina_pg_store_client_picture_to_db(src, client_uid=uid)
        if tok:
            return tok
    except Exception:
        pass
    pics_dir = _spina__client_pictures_dir()
    try:
        ext = os.path.splitext(src)[1].lower().strip()
    except Exception:
        ext = ''
    if ext not in ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'):
        ext = '.png'
    # Remove older saved picture(s) for the same client uid.
    try:
        for old in os.listdir(pics_dir):
            try:
                if old.startswith(uid + '.'):
                    os.remove(os.path.join(pics_dir, old))
            except Exception:
                pass
    except Exception:
        pass
    dst_name = f'{uid}{ext}'
    dst_abs = os.path.join(pics_dir, dst_name)
    shutil.copy2(src, dst_abs)
    try:
        _spina_pg_store_file_to_db(dst_abs, file_type='client_picture', client_uid=uid)
    except Exception:
        pass
    return os.path.join('data', 'client_pictures', dst_name)

def _spina__delete_client_picture_file(stored_path):
    try:
        s = str(stored_path or '').strip()
        if s.lower().startswith('dbpic:'):
            _spina_pg_delete_client_picture_token(s)
            return
        abs_path = _spina__resolve_app_path(stored_path)
        if not abs_path:
            return
        if os.path.exists(abs_path):
            os.remove(abs_path)
    except Exception:
        pass

def _db_set_client_picture(self, name, picture_source_path, loan_type=None, source='clients:picture'):
    _spina__ensure_client_picture_column(self)
    cur = self.conn.cursor()
    lt = self._effective_lt(loan_type)
    info = self.get_client_info(name, loan_type=lt, include_archived=True) or {}
    if not info:
        return ''
    uid = str(info.get('client_uid') or '').strip()
    if not uid:
        return ''
    old_path = str(info.get('client_picture') or '').strip()
    rel_path = _spina__store_client_picture_file(picture_source_path, uid)
    if not rel_path:
        return ''
    try:
        cur.execute('UPDATE clients SET client_picture=? WHERE client_uid=?', (rel_path, uid))
        self.conn.commit()
    except Exception:
        cur.execute('UPDATE clients SET client_picture=? WHERE name=? AND loan_type=?', (rel_path, name, lt))
        self.conn.commit()
    try:
        if old_path and old_path != rel_path:
            _spina__delete_client_picture_file(old_path)
    except Exception:
        pass
    try:
        new_row = self.get_client_by_uid(uid) or self.get_client_info(name, loan_type=lt, include_archived=True) or {}
        old_row = dict(info)
        self._log_client_history(uid, 'UPDATE', old_row=old_row, new_row=new_row, source=source, note='Updated client picture')
    except Exception:
        pass
    return rel_path

def _db_clear_client_picture(self, name, loan_type=None, source='clients:picture_clear'):
    _spina__ensure_client_picture_column(self)
    cur = self.conn.cursor()
    lt = self._effective_lt(loan_type)
    info = self.get_client_info(name, loan_type=lt, include_archived=True) or {}
    if not info:
        return False
    uid = str(info.get('client_uid') or '').strip()
    old_path = str(info.get('client_picture') or '').strip()
    try:
        if uid:
            cur.execute('UPDATE clients SET client_picture=? WHERE client_uid=?', ('', uid))
        else:
            cur.execute('UPDATE clients SET client_picture=? WHERE name=? AND loan_type=?', ('', name, lt))
        self.conn.commit()
    except Exception:
        return False
    try:
        if old_path:
            _spina__delete_client_picture_file(old_path)
    except Exception:
        pass
    try:
        if uid:
            new_row = self.get_client_by_uid(uid) or self.get_client_info(name, loan_type=lt, include_archived=True) or {}
            old_row = dict(info)
            self._log_client_history(uid, 'UPDATE', old_row=old_row, new_row=new_row, source=source, note='Cleared client picture')
    except Exception:
        pass
    return True

def _app_refresh_client_picture_panel(self):
    box = getattr(self, 'clients_picture_box', None)
    if box is None:
        return
    preview = getattr(self, 'clients_picture_preview', None)
    info_var = getattr(self, 'clients_picture_info_var', None)
    path_var = getattr(self, 'clients_picture_path_var', None)
    if preview is None or info_var is None or path_var is None:
        return

    name, lt = _app__selected_client_name_and_lt(self)
    if not name:
        try:
            preview.configure(image='', text='No picture selected')
            self._clients_picture_img = None
        except Exception:
            pass
        try:
            info_var.set('Select a client to view picture.')
            path_var.set('')
        except Exception:
            pass
        return

    try:
        pic_rel = self.db.get_client_picture(name, loan_type=lt, include_archived=True)
    except Exception:
        pic_rel = ''

    if not pic_rel:
        try:
            preview.configure(image='', text='No picture')
            self._clients_picture_img = None
        except Exception:
            pass
        try:
            info_var.set(f'{name} ({lt})')
            path_var.set('No saved picture.')
        except Exception:
            pass
        return

    abs_path = _spina__resolve_app_path(pic_rel)
    if not abs_path or not os.path.exists(abs_path):
        try:
            preview.configure(image='', text='Picture file\nnot found')
            self._clients_picture_img = None
        except Exception:
            pass
        try:
            info_var.set(f'{name} ({lt})')
            path_var.set(pic_rel)
        except Exception:
            pass
        return

    loaded = False
    try:
        from PIL import Image, ImageTk
        with Image.open(abs_path) as _img:
            img = _img.copy()
        img.thumbnail((150, 150), Image.LANCZOS)
        self._clients_picture_img = ImageTk.PhotoImage(img)
        preview.configure(image=self._clients_picture_img, text='')
        loaded = True
    except Exception:
        try:
            self._clients_picture_img = tk.PhotoImage(file=abs_path)
            preview.configure(image=self._clients_picture_img, text='')
            loaded = True
        except Exception:
            loaded = False

    if not loaded:
        try:
            preview.configure(image='', text='Picture saved\nbut preview failed')
            self._clients_picture_img = None
        except Exception:
            pass

    try:
        info_var.set(f'{name} ({lt})')
        path_var.set(pic_rel)
    except Exception:
        pass

def _app_set_selected_client_picture(self):
    name, lt = _app__selected_client_name_and_lt(self)
    if not name:
        messagebox.showinfo('Picture', 'Select a client first.')
        return
    file_path = filedialog.askopenfilename(
        parent=getattr(self, 'root', None),
        title='Select Client Picture',
        filetypes=[('Image files', '*.png *.jpg *.jpeg *.gif *.bmp *.webp'), ('All files', '*.*')],
    )
    if not file_path:
        return
    try:
        rel = self.db.set_client_picture(name, file_path, loan_type=lt)
        if not rel:
            messagebox.showerror('Picture', 'Failed to save client picture.')
            return
    except Exception as e:
        messagebox.showerror('Picture', f'Failed to save client picture.\n\n{e}')
        return
    try:
        self.refresh_client_picture_panel()
    except Exception:
        pass

def _app_clear_selected_client_picture(self):
    name, lt = _app__selected_client_name_and_lt(self)
    if not name:
        messagebox.showinfo('Picture', 'Select a client first.')
        return
    try:
        cur = self.db.get_client_picture(name, loan_type=lt, include_archived=True)
    except Exception:
        cur = ''
    if not cur:
        messagebox.showinfo('Picture', 'This client has no saved picture.')
        return
    if not messagebox.askyesno('Clear Picture', f"Remove the saved picture for '{name}' ({lt})?"):
        return
    try:
        ok = self.db.clear_client_picture(name, loan_type=lt)
        if not ok:
            messagebox.showerror('Picture', 'Failed to clear client picture.')
            return
    except Exception as e:
        messagebox.showerror('Picture', f'Failed to clear client picture.\n\n{e}')
        return
    try:
        self.refresh_client_picture_panel()
    except Exception:
        pass

