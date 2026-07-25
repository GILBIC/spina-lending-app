"""Client-note editor presentation extracted in Wave 40."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

_NOTE_EDITOR_DEPENDENCIES = {}
_PROTECTED_GLOBALS = {
    "__builtins__", "__cached__", "__doc__", "__file__", "__loader__",
    "__name__", "__package__", "__spec__", "_NOTE_EDITOR_DEPENDENCIES",
    "_PROTECTED_GLOBALS", "configure_note_editor_dependencies",
    "NOTE_EDITOR_SOURCE_SHA256", "NOTE_EDITOR_SOURCE_LINES",
    "NOTE_EDITOR_TARGET", "NOTE_EDITOR_METHODS", "NOTE_EDITOR_CALLS",
}


def configure_note_editor_dependencies(namespace):
    _NOTE_EDITOR_DEPENDENCIES.clear()
    _NOTE_EDITOR_DEPENDENCIES.update(namespace)
    for name, value in namespace.items():
        if name not in _PROTECTED_GLOBALS:
            globals()[name] = value


NOTE_EDITOR_TARGET = 'NoteEditorDialog'
NOTE_EDITOR_SOURCE_SHA256 = 'dac0182a8bd3d55f588d4075758b48a1d8ec1f9072c7af7c1488fd68ae966f3d'
NOTE_EDITOR_SOURCE_LINES = 638
NOTE_EDITOR_METHODS = ['__init__', '_migrate_legacy_notes_if_needed', '_title_text', '_set_dirty', '_note_date_value', '_sig_for_text', '_validate_date_or_warn', '_auto_choose_scope', '_scope_label', '_format_list_item', '_focus_search', '_build_ui', '_collect_items', '_refresh_list', '_on_list_select', '_pick_date', '_jump_today', '_jump_default', '_clear_text', '_open_notes_file', '_load_note', '_save_note', '_delete_note', '_on_text_modified', '_schedule_autosave', '_confirm_before_switch', '_save_and_close', '_close']
NOTE_EDITOR_CALLS = ['__init__', '_candidate_note_keys', '_load_client_notes', '_log_exc', '_log_suppressed_once', '_normalize_loan_type_value', '_note_id_key', '_note_scoped_prefix', '_note_type_key', '_open_path', '_resolve_note_key_scoped', '_save_client_notes', 'add_scope', 'bool', 'ctrl.pack', 'dated.append', 'dated.sort', 'datetime.now', 'datetime.strptime', 'encode', 'entry.get', 'entry.items', 'enumerate', 'footer.pack', 'get_client_note', 'getattr', 'hashlib.sha1', 'hdr.pack', 'hexdigest', 'int', 'isinstance', 'it.get', 'items.append', 'lbtn.pack', 'legacy_shared.append', 'legacy_type.append', 'len', 'lower', 'lsb.pack', 'main.add', 'main.pack', 'master.winfo_height', 'master.winfo_rootx', 'master.winfo_rooty', 'master.winfo_width', 'merged.setdefault', 'merged.update', 'messagebox.askyesno', 'messagebox.askyesnocancel', 'messagebox.showerror', 'messagebox.showinfo', 'notes.get', 'notes.pop', 'outer.pack', 'pack', 'pick_date', 'replace', 'rstrip', 'scope.pack', 'self._auto_choose_scope', 'self._build_ui', 'self._close', 'self._collect_items', 'self._confirm_before_switch', 'self._focus_search', 'self._format_list_item', 'self._load_note', 'self._migrate_legacy_notes_if_needed', 'self._note_date_value', 'self._on_list_select', 'self._refresh_list', 'self._save_and_close', 'self._save_note', 'self._schedule_autosave', 'self._scope_label', 'self._set_dirty', 'self._sig_for_text', 'self._title_text', 'self._validate_date_or_warn', 'self.after', 'self.after_cancel', 'self.autosave_var.get', 'self.bind', 'self.date_entry.pack', 'self.date_var.get', 'self.date_var.set', 'self.destroy', 'self.geometry', 'self.grab_release', 'self.grab_set', 'self.listbox.bind', 'self.listbox.configure', 'self.listbox.curselection', 'self.listbox.delete', 'self.listbox.insert', 'self.listbox.pack', 'self.listbox.see', 'self.listbox.selection_clear', 'self.listbox.selection_set', 'self.minsize', 'self.protocol', 'self.scope_var.get', 'self.scope_var.set', 'self.search_entry.bind', 'self.search_entry.focus_set', 'self.search_entry.pack', 'self.search_entry.select_range', 'self.search_var.get', 'self.status_var.set', 'self.title', 'self.transient', 'self.txt.bind', 'self.txt.configure', 'self.txt.delete', 'self.txt.edit_modified', 'self.txt.get', 'self.txt.insert', 'self.txt.pack', 'self.update_idletasks', 'self.winfo_height', 'self.winfo_width', 'set_client_note', 'srow.pack', 'status_row.pack', 'str', 'strftime', 'strip', 'super', 'tk.BooleanVar', 'tk.Listbox', 'tk.PanedWindow', 'tk.StringVar', 'tk.Text', 'ttk.Button', 'ttk.Checkbutton', 'ttk.Entry', 'ttk.Frame', 'ttk.Label', 'ttk.Scrollbar', 'txt_frame.pack', 'ysb.pack']

class NoteEditorDialog(tk.Toplevel):
    '''Improved per-client notes editor.

    Features:
      - Dated and undated notes
      - Scope: Shared (both Regular/7x7) or This loan type
      - Left panel: list of existing notes (with search)
      - Autosave (debounced) + unsaved indicator
      - Safe switching between notes (prompts if needed)
    Notes storage is handled by get_client_note()/set_client_note() -> data/client_notes.json
    '''

    def __init__(self, master, client_name: str, default_date: str = "", loan_type: str | None = None, client_uid: str | None = None, person_uid: str | None = None):
        super().__init__(master)
        self.client_name = (client_name or "").strip()
        self.loan_type = loan_type
        self.client_uid = (client_uid or "").strip() or None
        self.person_uid = (person_uid or "").strip() or None

        # Best-effort: migrate any legacy name-based notes to stable-id keys
        try:
            self._migrate_legacy_notes_if_needed()
        except Exception as _e:
            try:
                _log_exc("notes:migrate_legacy", _e)
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_0041', 'suppressed exception excpass_0041', __spina_exc)
                pass

        self._dirty = False
        self._autosave_job = None
        self._switching = False
        self._last_saved_sig = ""
        self._active_item = None  # (date, scope)

        self.title(self._title_text())
        self.minsize(760, 440)
        self.transient(master)
        try:
            self.grab_set()
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0042', 'suppressed exception excpass_0042', __spina_exc)
            pass

        # Vars
        self.date_var = tk.StringVar(value=(default_date or "").strip())
        self.scope_var = tk.StringVar(value=("type" if loan_type else "shared"))
        self.search_var = tk.StringVar(value="")
        self.autosave_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="")

        # Choose scope based on existing note for the default date
        self._auto_choose_scope()

        self._build_ui()
        self._refresh_list()
        self._load_note(set_active=True)

        self.bind("<Escape>", lambda e: self._close())
        self.protocol("WM_DELETE_WINDOW", self._close)

        # Shortcuts
        self.bind("<Control-s>", lambda e: self._save_note(user_action=True))
        self.bind("<Control-S>", lambda e: self._save_note(user_action=True))
        self.bind("<Control-Return>", lambda e: self._save_and_close())
        self.bind("<Control-Enter>", lambda e: self._save_and_close())  # some keyboards
        self.bind("<Control-f>", lambda e: self._focus_search())
        self.bind("<Control-F>", lambda e: self._focus_search())

        # Center on parent (best-effort)
        try:
            self.update_idletasks()
            x = master.winfo_rootx() + (master.winfo_width() // 2 - self.winfo_width() // 2)
            y = master.winfo_rooty() + (master.winfo_height() // 2 - self.winfo_height() // 2)
            self.geometry(f"+{x}+{y}")
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0043', 'suppressed exception excpass_0043', __spina_exc)
            pass

    # ---------- helpers ----------
    def _migrate_legacy_notes_if_needed(self):
        """Move legacy name-based keys into stable-id keys for this client (best-effort).

        This prevents collisions if names repeat, and keeps notes attached even if a name changes.
        Runs only when we have a stable id (person_uid or client_uid).
        """
        # Determine stable targets
        key_shared = _note_id_key("PID", self.person_uid) or _note_id_key("CID", self.client_uid)
        key_type = _note_type_key(self.person_uid, self.loan_type) or _note_id_key("CID", self.client_uid)

        if not key_shared and not key_type:
            return

        notes = _load_client_notes()
        changed = False

        # Shared legacy keys: name variants
        try:
            legacy_shared = []
            for k in _candidate_note_keys(self.client_name):
                if k in notes:
                    legacy_shared.append(k)
            if key_shared and key_shared not in notes and legacy_shared:
                # merge legacy entries into stable key
                merged = {}
                for lk in legacy_shared:
                    ent = notes.get(lk)
                    if isinstance(ent, dict):
                        merged.update(ent)
                    elif ent:
                        merged.setdefault("__default__", str(ent).strip())
                if merged:
                    notes[key_shared] = merged
                    changed = True
                for lk in legacy_shared:
                    notes.pop(lk, None)
                    changed = True
        except Exception as e:
            _log_exc("notes:migrate_legacy_shared", e)

        # Type legacy keys: '<loan_type>::<name>' variants
        try:
            prefix = _note_scoped_prefix(self.loan_type)
            legacy_type = []
            for k in _candidate_note_keys(self.client_name):
                kk = prefix + k
                if kk in notes:
                    legacy_type.append(kk)
            if key_type and key_type not in notes and legacy_type:
                merged = {}
                for lk in legacy_type:
                    ent = notes.get(lk)
                    if isinstance(ent, dict):
                        merged.update(ent)
                    elif ent:
                        merged.setdefault("__default__", str(ent).strip())
                if merged:
                    notes[key_type] = merged
                    changed = True
                for lk in legacy_type:
                    notes.pop(lk, None)
                    changed = True
        except Exception as e:
            _log_exc("notes:migrate_legacy_type", e)

        if changed:
            try:
                _save_client_notes(notes)
            except Exception as e:
                _log_exc("notes:migrate_legacy_save", e)

    def _title_text(self):
        star = " *" if getattr(self, "_dirty", False) else ""
        return f"Notes - {self.client_name}{star}"

    def _set_dirty(self, val: bool):
        self._dirty = bool(val)
        try:
            self.title(self._title_text())
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0044', 'suppressed exception excpass_0044', __spina_exc)
            pass

    def _note_date_value(self):
        nd = (self.date_var.get() or "").strip()
        return nd if nd else None

    def _sig_for_text(self, t: str) -> str:
        try:
            import hashlib
            return hashlib.sha1((t or "").encode("utf-8")).hexdigest()
        except Exception:
            return str(len(t or ""))

    def _validate_date_or_warn(self) -> bool:
        nd = (self.date_var.get() or "").strip()
        if not nd:
            return True  # undated allowed
        try:
            datetime.strptime(nd[:10], "%Y-%m-%d")
            return True
        except Exception:
            try:
                messagebox.showerror("Invalid Date", "Use YYYY-MM-DD (example: 2026-02-06) or leave blank for default note.")
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_0045', 'suppressed exception excpass_0045', __spina_exc)
                pass
            return False

    def _auto_choose_scope(self):
        # Simplified notes scope: use THIS LOAN TYPE when loan_type is known.
        try:
            if self.loan_type:
                self.scope_var.set("type")
            else:
                self.scope_var.set("shared")
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0046', 'suppressed exception excpass_0046', __spina_exc)
            pass

    def _scope_label(self, scope: str) -> str:
        scope = (scope or ("type" if self.loan_type else "shared")).lower().strip()
        if scope == "type":
            lt = _normalize_loan_type_value(self.loan_type)
            return f"[{lt}]"
        return "[Note]"

    def _format_list_item(self, scope: str, d: str, text: str) -> str:
        date_part = (d if d else "(default)")
        snippet = (text or "").replace("\n", " ").strip()
        if len(snippet) > 50:
            snippet = snippet[:50].rstrip() + "…"
        return f"{self._scope_label(scope)} {date_part} — {snippet}"

    def _focus_search(self):
        try:
            self.search_entry.focus_set()
            self.search_entry.select_range(0, "end")
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0047', 'suppressed exception excpass_0047', __spina_exc)
            pass

    # ---------- UI ----------
    def _build_ui(self):
        outer = ttk.Frame(self, padding=10)
        outer.pack(fill="both", expand=True)

        hdr = ttk.Frame(outer)
        hdr.pack(fill="x")

        ttk.Label(hdr, text="Client:", width=8).pack(side="left")
        ttk.Label(hdr, text=self.client_name, font=("TkDefaultFont", 10, "bold")).pack(side="left")

        lt_txt = _normalize_loan_type_value(self.loan_type) if self.loan_type else "—"
        ttk.Label(hdr, text="   Loan Type:", padding=(12, 0, 0, 0)).pack(side="left")
        ttk.Label(hdr, text=lt_txt).pack(side="left")

        main = tk.PanedWindow(outer, orient="horizontal", sashrelief="raised")
        main.pack(fill="both", expand=True, pady=(10, 0))

        # Left panel
        left = ttk.Frame(main, padding=(0, 0, 10, 0))
        main.add(left, minsize=240)

        srow = ttk.Frame(left)
        srow.pack(fill="x", pady=(0, 6))
        ttk.Label(srow, text="Search:").pack(side="left")
        self.search_entry = ttk.Entry(srow, textvariable=self.search_var)
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(6, 0))
        self.search_entry.bind("<KeyRelease>", lambda e: self._refresh_list())

        self.listbox = tk.Listbox(left, activestyle="dotbox", height=14)
        lsb = ttk.Scrollbar(left, orient="vertical", command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=lsb.set)
        self.listbox.pack(side="left", fill="both", expand=True)
        lsb.pack(side="right", fill="y")
        self.listbox.bind("<<ListboxSelect>>", lambda e: self._on_list_select())

        lbtn = ttk.Frame(left)
        lbtn.pack(fill="x", pady=(6, 0))
        ttk.Button(lbtn, text="Refresh", command=self._refresh_list).pack(side="left")
        ttk.Button(lbtn, text="Today", command=self._jump_today).pack(side="left", padx=(6, 0))
        ttk.Button(lbtn, text="Default", command=self._jump_default).pack(side="left", padx=(6, 0))

        # Right panel
        right = ttk.Frame(main)
        main.add(right)

        ctrl = ttk.Frame(right)
        ctrl.pack(fill="x", pady=(0, 6))

        ttk.Label(ctrl, text="Note Date:").pack(side="left")
        self.date_entry = ttk.Entry(ctrl, textvariable=self.date_var, width=12)
        self.date_entry.pack(side="left", padx=(6, 4))
        ttk.Button(ctrl, text="📅", width=3, command=self._pick_date).pack(side="left")
        ttk.Button(ctrl, text="Load", command=lambda: self._load_note(set_active=True)).pack(side="left", padx=(6, 0))

        scope = ttk.Frame(right)
        scope.pack(fill="x", pady=(2, 6))
        if self.loan_type:
            self.scope_var.set("type")
            ttk.Label(scope, text=f"Scope: {_normalize_loan_type_value(self.loan_type)}").pack(side="left")
        else:
            self.scope_var.set("shared")
            ttk.Label(scope, text="Scope: Default").pack(side="left")

        txt_frame = ttk.Frame(right)
        txt_frame.pack(fill="both", expand=True)

        self.txt = tk.Text(txt_frame, wrap="word", height=10, undo=True, maxundo=2000, autoseparators=True)
        ysb = ttk.Scrollbar(txt_frame, orient="vertical", command=self.txt.yview)
        self.txt.configure(yscrollcommand=ysb.set)
        self.txt.pack(side="left", fill="both", expand=True)
        ysb.pack(side="right", fill="y")

        self.txt.bind("<<Modified>>", self._on_text_modified)

        status_row = ttk.Frame(right)
        status_row.pack(fill="x", pady=(6, 0))
        ttk.Checkbutton(status_row, text="Auto-save", variable=self.autosave_var).pack(side="left")
        ttk.Label(status_row, textvariable=self.status_var).pack(side="left", padx=(10, 0))

        footer = ttk.Frame(right)
        footer.pack(fill="x", pady=(8, 0))
        ttk.Button(footer, text="Open Notes File", command=self._open_notes_file).pack(side="left")
        ttk.Button(footer, text="Clear", command=self._clear_text).pack(side="left", padx=(6, 0))
        ttk.Button(footer, text="Save", command=lambda: self._save_note(user_action=True)).pack(side="right")
        ttk.Button(footer, text="Delete", command=self._delete_note).pack(side="right", padx=(0, 6))
        ttk.Button(footer, text="Close", command=self._close).pack(side="right", padx=(0, 6))

    # ---------- list handling ----------
    def _collect_items(self):
        items = []

        def add_scope(scope: str):
            try:
                notes = _load_client_notes()
                key = _resolve_note_key_scoped(
                    notes, self.client_name, self.loan_type, scope=scope,
                    client_uid=self.client_uid, person_uid=self.person_uid
                )
                entry = notes.get(key)
                if not isinstance(entry, dict):
                    entry = ({"__default__": str(entry).strip()} if entry else {})
                if not isinstance(entry, dict):
                    return
                _def = (entry.get("__default__") or "").strip()
                if _def:
                    items.append({"scope": scope, "date": "", "text": _def})
                dated = []
                for d, t in entry.items():
                    if d == "__default__":
                        continue
                    if not (t and str(t).strip()):
                        continue
                    dated.append((str(d), str(t).strip()))
                dated.sort(key=lambda it: it[0], reverse=True)
                for d, t in dated:
                    items.append({"scope": scope, "date": d, "text": t})
            except Exception:
                return

        if self.loan_type:
            add_scope("type")
        else:
            add_scope("shared")

        q = (self.search_var.get() or "").strip().lower()
        if q:
            items = [it for it in items if q in (it["date"] or "").lower() or q in (it["text"] or "").lower()]

        for it in items:
            it["display"] = self._format_list_item(it["scope"], it["date"], it["text"])

        return items

    def _refresh_list(self):
        try:
            self._items = self._collect_items()
        except Exception:
            self._items = []
        try:
            self.listbox.delete(0, "end")
            for it in self._items:
                self.listbox.insert("end", it.get("display", ""))
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0049', 'suppressed exception excpass_0049', __spina_exc)
            pass

        try:
            if self._active_item and self._items:
                ad, ascope = self._active_item
                for i, it in enumerate(self._items):
                    if it.get("date") == ad and it.get("scope") == ascope:
                        self.listbox.selection_clear(0, "end")
                        self.listbox.selection_set(i)
                        self.listbox.see(i)
                        break
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0050', 'suppressed exception excpass_0050', __spina_exc)
            pass

    def _on_list_select(self):
        if getattr(self, "_switching", False):
            return
        try:
            sel = self.listbox.curselection()
            if not sel:
                return
            idx = int(sel[0])
            if idx < 0 or idx >= len(getattr(self, "_items", [])):
                return
            it = self._items[idx]
            tgt_date = it.get("date", "")
            tgt_scope = it.get("scope", "shared")
        except Exception:
            return

        if not self._confirm_before_switch():
            self._refresh_list()
            return

        try:
            self._switching = True
            self.date_var.set(tgt_date)
            self.scope_var.set(tgt_scope)
            self._load_note(set_active=True)
        finally:
            self._switching = False

    # ---------- actions ----------
    def _pick_date(self):
        if not self._confirm_before_switch():
            return
        try:
            pick_date(self, self.date_var, initial=self.date_var.get(), title="Select Note Date")
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0051', 'suppressed exception excpass_0051', __spina_exc)
            pass
        self._load_note(set_active=True)

    def _jump_today(self):
        if not self._confirm_before_switch():
            return
        try:
            self.date_var.set(datetime.now().strftime("%Y-%m-%d"))
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0052', 'suppressed exception excpass_0052', __spina_exc)
            pass
        if self.loan_type:
            self.scope_var.set("type")
        self._load_note(set_active=True)

    def _jump_default(self):
        if not self._confirm_before_switch():
            return
        self.date_var.set("")
        if self.loan_type:
            self.scope_var.set("type")
        self._load_note(set_active=True)

    def _clear_text(self):
        if not self._confirm_before_switch(clear_only=True):
            return
        try:
            self.txt.delete("1.0", "end")
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0053', 'suppressed exception excpass_0053', __spina_exc)
            pass
        self._set_dirty(True)
        self._schedule_autosave()

    def _open_notes_file(self):
        try:
            _open_path(CLIENT_NOTES_PATH)
        except Exception:
            try:
                messagebox.showinfo("Notes File", CLIENT_NOTES_PATH)
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_0054', 'suppressed exception excpass_0054', __spina_exc)
                pass

    # ---------- load/save ----------
    def _load_note(self, set_active: bool = False):
        if not self._validate_date_or_warn():
            return
        nd = self._note_date_value()
        scope = ("type" if self.loan_type else (self.scope_var.get() or "shared").strip().lower())
        if scope not in ("shared", "type"):
            scope = ("type" if self.loan_type else "shared")

        try:
            note = get_client_note(self.client_name, nd, loan_type=self.loan_type, scope=scope, client_uid=self.client_uid, person_uid=self.person_uid) or ""
        except Exception:
            note = ""

        try:
            self.txt.delete("1.0", "end")
            self.txt.insert("1.0", note)
            self.txt.edit_modified(False)
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0055', 'suppressed exception excpass_0055', __spina_exc)
            pass

        self._last_saved_sig = self._sig_for_text(note)
        self._set_dirty(False)

        if set_active:
            self._active_item = (nd or "", scope)
            self._refresh_list()

        try:
            self.status_var.set("Loaded.")
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0056', 'suppressed exception excpass_0056', __spina_exc)
            pass

    def _save_note(self, user_action: bool = False, silent: bool = False):
        if not self._validate_date_or_warn():
            return False
        nd = self._note_date_value()
        scope = ("type" if self.loan_type else (self.scope_var.get() or "shared").strip().lower())
        if scope not in ("shared", "type"):
            scope = ("type" if self.loan_type else "shared")

        try:
            note = self.txt.get("1.0", "end").strip()
        except Exception:
            note = ""

        sig = self._sig_for_text(note)
        if sig == self._last_saved_sig and not self._dirty:
            if user_action and not silent:
                try:
                    self.status_var.set("Nothing to save.")
                except Exception as __spina_exc:
                    _log_suppressed_once('excpass_0057', 'suppressed exception excpass_0057', __spina_exc)
                    pass
            return True

        try:
            set_client_note(self.client_name, note, nd, loan_type=self.loan_type, scope=scope, client_uid=self.client_uid, person_uid=self.person_uid)
            self._last_saved_sig = sig
            self._set_dirty(False)
            self._active_item = (nd or "", scope)
            self._refresh_list()
            try:
                self.status_var.set(f"Saved {datetime.now().strftime('%H:%M:%S')}")
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_0058', 'suppressed exception excpass_0058', __spina_exc)
                pass
            return True
        except Exception as e:
            if not silent:
                try:
                    messagebox.showerror("Error", f"Failed to save note: {e}")
                except Exception as __spina_exc:
                    _log_suppressed_once('excpass_0059', 'suppressed exception excpass_0059', __spina_exc)
                    pass
            return False

    def _delete_note(self):
        if not self._validate_date_or_warn():
            return
        nd = self._note_date_value()
        scope = ("type" if self.loan_type else (self.scope_var.get() or "shared").strip().lower())
        if scope not in ("shared", "type"):
            scope = ("type" if self.loan_type else "shared")

        label = (nd if nd else "default")
        try:
            if not messagebox.askyesno("Delete Note", f"Delete {self._scope_label(scope)} {label} note?\n\nThis cannot be undone."):
                return
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0060', 'suppressed exception excpass_0060', __spina_exc)
            pass

        try:
            set_client_note(self.client_name, "", nd, loan_type=self.loan_type, scope=scope, client_uid=self.client_uid, person_uid=self.person_uid)
        except Exception as e:
            _log_exc('notes:delete_note', e)
            messagebox.showerror('Delete Note', f'Failed to delete note.\n\n{e}\n\nSee log: data/spina_app.log')
            return
        try:
            self.txt.delete("1.0", "end")
            self.txt.edit_modified(False)
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0061', 'suppressed exception excpass_0061', __spina_exc)
            pass

        self._last_saved_sig = self._sig_for_text("")
        self._set_dirty(False)
        self._active_item = (nd or "", scope)
        self._refresh_list()
        try:
            self.status_var.set("Deleted.")
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0062', 'suppressed exception excpass_0062', __spina_exc)
            pass

    # ---------- dirty / autosave / switching ----------
    def _on_text_modified(self, event=None):
        try:
            if self.txt.edit_modified():
                self.txt.edit_modified(False)
                self._set_dirty(True)
                self._schedule_autosave()
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0063', 'suppressed exception excpass_0063', __spina_exc)
            pass

    def _schedule_autosave(self):
        if not bool(self.autosave_var.get()):
            return
        try:
            if self._autosave_job:
                self.after_cancel(self._autosave_job)
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0064', 'suppressed exception excpass_0064', __spina_exc)
            pass
        try:
            self._autosave_job = self.after(1200, lambda: self._save_note(user_action=False, silent=True))
        except Exception:
            self._autosave_job = None

    def _confirm_before_switch(self, clear_only: bool = False) -> bool:
        if not self._dirty:
            return True

        if bool(self.autosave_var.get()):
            ok = self._save_note(user_action=False, silent=True)
            return bool(ok)

        try:
            resp = messagebox.askyesnocancel("Unsaved changes", "You have unsaved changes.\n\nYes = Save\nNo = Discard\nCancel = Keep editing")
        except Exception:
            resp = None

        if resp is None:
            return False
        if resp is True:
            return bool(self._save_note(user_action=True, silent=False))
        self._set_dirty(False)
        return True

    def _save_and_close(self):
        if self._save_note(user_action=True, silent=False):
            self._close()

    def _close(self):
        if not self._confirm_before_switch():
            return
        try:
            self.grab_release()
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0065', 'suppressed exception excpass_0065', __spina_exc)
            pass
        self.destroy()
