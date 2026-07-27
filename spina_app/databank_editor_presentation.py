"""Data Bank inline editor and missed-reason presentation extracted in Wave 60."""
from __future__ import annotations

_DATABANK_EDITOR_DEPENDENCIES = {}
_PROTECTED_GLOBALS = {'__package__', '_PROTECTED_GLOBALS', '_begin_cell_edit', '_remember_cell_click', '__loader__', '_walk_widgets', '__name__', '__file__', 'configure_databank_editor_dependencies', '__spec__', '__builtins__', 'DATABANK_EDITOR_PRESENTATION_METHODS', '_DATABANK_EDITOR_DEPENDENCIES', '__doc__', '_pick_missed_reason', '__cached__'}

def configure_databank_editor_dependencies(namespace):
    _DATABANK_EDITOR_DEPENDENCIES.clear()
    _DATABANK_EDITOR_DEPENDENCIES.update(namespace)
    for name, value in namespace.items():
        if name not in _PROTECTED_GLOBALS:
            globals()[name] = value

DATABANK_EDITOR_PRESENTATION_METHODS = {'_pick_missed_reason': {'lines': 145, 'source_sha256': 'e75ed29b15ad4f421b70289378b7f3d7b3a653cb712a1f6fed8cd1bcda5471ec', 'dedented_sha256': '3e40b963909160fe3887b1efa000a2f279ca830af51831fa13339bd88b6e08a3', 'signature': "self, parent, prefill_text=''", 'calls': ['_dt.strptime', '_log_suppressed_once', '_parse_any_date', '_re.fullmatch', 'adv_box.pack', 'adv_end_var.get', 'adv_end_var.set', 'adv_start_var.get', 'adv_start_var.set', 'advance_var.get', 'advance_var.trace_add', 'btns.pack', 'child.configure', 'd.strftime', 'date.today', 'enumerate', 'frm.pack', 'grid', 'hasattr', 'int', 'join', 'messagebox.showwarning', 'on_adv_toggle', 'on_cancel', 'on_ok', 'other_var.get', 'pack', 'parent.winfo_height', 'parent.winfo_rootx', 'parent.winfo_rooty', 'parent.winfo_width', 'picked.append', 's.split', 'set_enabled', 'strftime', 'strip', 't.startswith', 'tk.BooleanVar', 'tk.StringVar', 'tk.Toplevel', 'top.bind', 'top.destroy', 'top.geometry', 'top.grab_set', 'top.resizable', 'top.title', 'top.transient', 'top.update_idletasks', 'top.wait_window', 'top.winfo_height', 'top.winfo_width', 'ttk.Button', 'ttk.Checkbutton', 'ttk.Entry', 'ttk.Frame', 'ttk.Label', 'ttk.Labelframe', 'ttk.Separator', 'txt.startswith', 'v.get', 'vars_.append', 'widget.winfo_children'], 'db_calls': [], 'delegated_save': False}, '_walk_widgets': {'lines': 7, 'source_sha256': 'ebb27216245c3fa0d345c84a720dfdd79654b052024ee1c9adb9d202a051dc7c', 'dedented_sha256': '5bebfe0a0a4c45a619a630825f16c4cbc1d828f7a27bbd315af30707ad2dc6bc', 'signature': 'self, widget', 'calls': ['self._walk_widgets', 'widget.winfo_children'], 'db_calls': [], 'delegated_save': False}, '_begin_cell_edit': {'lines': 142, 'source_sha256': '7e2a682544179556392ed7f291dba538bed362d57979b0a0319115bf87b59bb7', 'dedented_sha256': 'fefbd3e586e7c5acd97aa381471ff49d898657c66af7bb550ee59a51ebb4ecba', 'signature': 'self, event=None', 'calls': ['_log_suppressed_once', 'cn.startswith', 'col_id.startswith', 'cur_txt.replace', 'cur_txt.strip', 'date', 'ent.bind', 'ent.destroy', 'ent.focus_set', 'ent.insert', 'ent.place', 'get', 'getattr', 'hasattr', 'head_txt.isdigit', 'int', 'isdigit', 'lower', 'self._mk_tk_entry', 'self._save_cell_edit', 'self.current_entry.destroy', 'self.root.bell', 'str', 'strftime', 'strip', 'tv.bbox', 'tv.get_children', 'tv.heading', 'tv.identify_column', 'tv.identify_row', 'tv.item', 'tv.see', 'tv.set', 'tv.update_idletasks'], 'db_calls': [], 'delegated_save': True}, '_remember_cell_click': {'lines': 19, 'source_sha256': 'b58c42ff67630fdaeb8a3dd8dc15392bec19a6163524db2f461fdb59ecaa1c1d', 'dedented_sha256': '5f9c3520c90f58fe98fb769fbc4547ff4d1dbe7c68b0cb969070d4898f14f156', 'signature': 'self, event', 'calls': ['col.startswith', 'getattr', 'hasattr', 'int', 'self._update_data_toolbar', 'tv.identify_column', 'tv.identify_row', 'tv.item'], 'db_calls': [], 'delegated_save': False}}

def _pick_missed_reason(self, parent, prefill_text=""):
    """
    Modal checkbox dialog to choose one or more missed-payment reasons,
    plus optional 'Other' note. If 'Advance' is selected, you can enter a date range.
    Returns a single string (joined reasons + optional [ADV:s..e] tag) or None if cancelled.
    """
    import tkinter as tk
    from tkinter import ttk, messagebox
    from datetime import date, datetime as _dt
    import re as _re

    COMMON = [
        "No funds today",
        "Sick",
        "Out of town",
        "Not at home / can't meet",
        "Advance (paid earlier)",
    ]

    top = tk.Toplevel(self.root if hasattr(self, "root") else parent)
    top.title("Missed Payment - Select reason(s)")
    top.transient(parent)
    top.grab_set()
    top.resizable(False, False)

    frm = ttk.Frame(top, padding=10)
    frm.pack(fill="both", expand=True)

    ttk.Label(frm, text="Tick the reason(s) for the missed payment:", font=('TkDefaultFont', 10, 'bold')).pack(anchor="w", pady=(0,6))

    vars_ = []
    advance_var = tk.BooleanVar(value=False)

    for txt in COMMON:
        v = advance_var if txt.startswith("Advance") else tk.BooleanVar(value=False)
        ttk.Checkbutton(frm, text=txt, variable=v).pack(anchor="w")
        vars_.append((v, txt))

    adv_box = ttk.Labelframe(frm, text="Advance date range (flexible formats OK)")
    adv_box.pack(fill="x", pady=(8,0))
    ttk.Label(adv_box, text="Start").grid(row=0, column=0, padx=(8,4), pady=6, sticky="w")
    adv_start_var = tk.StringVar()
    ttk.Entry(adv_box, textvariable=adv_start_var, width=16).grid(row=0, column=1, sticky="w")
    ttk.Label(adv_box, text="End").grid(row=0, column=2, padx=(12,4), sticky="w")
    adv_end_var = tk.StringVar()
    ttk.Entry(adv_box, textvariable=adv_end_var, width=16).grid(row=0, column=3, sticky="w")

    today_str = date.today().strftime("%Y-%m-%d")
    adv_start_var.set(today_str)
    adv_end_var.set(today_str)

    def set_enabled(widget, enabled: bool):
        state = "normal" if enabled else "disabled"
        for child in widget.winfo_children():
            try:
                child.configure(state=state)
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_0208', 'suppressed exception excpass_0208', __spina_exc)
                pass

    def on_adv_toggle(*_):
        set_enabled(adv_box, advance_var.get())

    advance_var.trace_add("write", on_adv_toggle)
    on_adv_toggle()

    ttk.Separator(frm, orient="horizontal").pack(fill="x", pady=8)

    ttk.Label(frm, text="Other (optional):").pack(anchor="w")
    other_var = tk.StringVar(value=(prefill_text or ""))
    ttk.Entry(frm, textvariable=other_var, width=48).pack(fill="x")

    btns = ttk.Frame(frm)
    btns.pack(fill="x", pady=(10,0))

    def _parse_any_date(s: str):
        s = (s or "").strip()
        if not s:
            return None
        fmts = ["%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%m-%d-%Y"]
        for f in fmts:
            try:
                d = _dt.strptime(s, f)
                return d.strftime("%Y-%m-%d")
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_0209', 'suppressed exception excpass_0209', __spina_exc)
                pass
        if _re.fullmatch(r"\d{4}-\d{1,2}-\d{1,2}", s):
            parts = s.split("-")
            s2 = f"{parts[0]}-{int(parts[1]):02d}-{int(parts[2]):02d}"
            try:
                d = _dt.strptime(s2, "%Y-%m-%d")
                return d.strftime("%Y-%m-%d")
            except Exception:
                return None
        return None

    def on_ok():
        picked = [txt for (v, txt) in vars_ if v.get()]
        adv_tag = ""
        if advance_var.get():
            s_norm = _parse_any_date(adv_start_var.get())
            e_norm = _parse_any_date(adv_end_var.get())
            if not (s_norm and e_norm):
                messagebox.showwarning("Invalid date", "Use dates like 2025-10-15 or 10/15/2025.")
                return
            if s_norm > e_norm:
                s_norm, e_norm = e_norm, s_norm
            for i, t in enumerate(picked):
                if t.startswith("Advance"):
                    picked[i] = f"Advance ({s_norm} to {e_norm})"
                    break
            else:
                picked.append(f"Advance ({s_norm} to {e_norm})")
            adv_tag = f" [ADV:{s_norm}..{e_norm}]"

        extra = other_var.get().strip()
        if extra:
            picked.append(extra)

        result["text"] = ("; ".join(picked).strip() + adv_tag).strip()
        top.destroy()

    def on_cancel():
        result["text"] = None
        top.destroy()

    result = {"text": None}
    ttk.Button(btns, text="Cancel", command=on_cancel).pack(side="right", padx=4)
    ttk.Button(btns, text="OK", command=on_ok).pack(side="right")

    top.bind("<Return>", lambda e: on_ok())
    top.bind("<Escape>", lambda e: on_cancel())

    try:
        top.update_idletasks()
        px = parent.winfo_rootx() + (parent.winfo_width()  - top.winfo_width())  // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - top.winfo_height()) // 2
        top.geometry(f"+{px}+{py}")
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_0210', 'suppressed exception excpass_0210', __spina_exc)
        pass

    top.wait_window()
    return result["text"]

def   _walk_widgets(self, widget):
    try:
        for child in widget.winfo_children():
            yield child
            yield from self._walk_widgets(child)
    except Exception:
        return

def _begin_cell_edit(self, event=None):
    """Create an Entry over the clicked (or remembered) day cell and save back to DB."""
    import tkinter as tk
    from tkinter import messagebox
    tv = getattr(self, "days_tree", None)
    if not tv:
        return

    # Identify row/column from the event or fallback to last-remembered
    col_id = None
    row_id = None
    if event is not None and hasattr(event, "x") and hasattr(event, "y"):
        try:
            col_id = tv.identify_column(event.x)  # '#1', '#2', ...
            row_id = tv.identify_row(event.y)
        except Exception:
            col_id, row_id = None, None

    if not col_id or not row_id or not col_id.startswith("#"):
        client = getattr(self, "_dbank_last_client", None)
        day    = getattr(self, "_dbank_last_day", None)
        if not client or not day:
            try:
                self.root.bell()
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_0251', 'suppressed exception excpass_0251', __spina_exc)
                pass
            return
        # Find the visible item for that client
        for item in tv.get_children():
            try:
                if tv.set(item, "client") == client:
                    row_id = item
                    col_id = f"#{int(day) + 2}"  # client=#1, area=#2, days start at #3 -> day+2
                    break
            except Exception:
                continue
        if not row_id or not col_id:
            return

    try:
        col_idx = int(col_id[1:])  # 1-based
    except Exception:
        return

    # Prevent edits on non-day columns
    if col_idx < 3:
        try:
            self.root.bell()
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0252', 'suppressed exception excpass_0252', __spina_exc)
            pass
        return


    # Compute target day number from column index and headings
    day = None
    try:
        # Primary: column name like d1..d31
        col_name = tv["columns"][col_idx-1]
        cn = str(col_name).lower()
        if cn.startswith("d") and cn[1:].isdigit():
            day = int(cn[1:])
    except Exception:
        day = None
    if day is None:
        # Fallback: numeric heading text
        try:
            head_txt = str(tv.heading(tv["columns"][col_idx-1]).get("text","")).strip()
            if head_txt.isdigit():
                day = int(head_txt)
        except Exception:
            day = None
    if day is None:
        # Last resort: positional mapping (#1 client, #2 area)
        day = col_idx - 2

    # Get client name from the row

    vals = tv.item(row_id, "values") or []
    if not vals:
        return
    client = vals[0]

    # Build the date for this grid month/year
    try:
        dt = date(self.grid_year, self.grid_month, int(day)).strftime("%Y-%m-%d")
    except Exception:
        return

    # Determine current value shown in the cell (strip currency formatting)
    try:
        cur_txt = tv.set(row_id, f"d{day}")
        for token in ("PHP", "", ","):
            cur_txt = cur_txt.replace(token, "")
        cur_txt = cur_txt.strip()
    except Exception:
        cur_txt = ""

    # Place an Entry exactly over the cell
    bbox = tv.bbox(row_id, col_id)
    if not bbox:
        try:
            tv.see(row_id)
            tv.update_idletasks()
            bbox = tv.bbox(row_id, col_id)
        except Exception:
            bbox = None
        if not bbox:
            return
    x, y, w, h = bbox

    # Clean up any prior editor
    if getattr(self, "current_entry", None):
        try:
            self.current_entry.destroy()
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0253', 'suppressed exception excpass_0253', __spina_exc)
            pass
        self.current_entry = None

    ent = self._mk_tk_entry(tv, justify="center")
    if cur_txt not in ("", "0"):
        try:
            ent.insert(0, cur_txt)
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0254', 'suppressed exception excpass_0254', __spina_exc)
            pass
    try:
        ent.place(x=x, y=y, width=w, height=h)
        ent.focus_set()
    except Exception:
        return
    self.current_entry = ent

    def _commit(*_):
        self._save_cell_edit(client, day, dt, ent)

    ent.bind("<Return>", _commit)
    ent.bind("<KP_Enter>", _commit)
    ent.bind("<Escape>", lambda e: ent.destroy())
    ent.bind("<FocusOut>", lambda e: ent.destroy())

def _remember_cell_click(self, event):
    try:
        tv = getattr(self, "days_tree", None)
        if not tv:
            return
        col = tv.identify_column(event.x)   # '#1', '#2', ...
        row = tv.identify_row(event.y)
        if not col or not row or not col.startswith('#'):
            return
        idx = int(col[1:])  # 1=Client, 2=Area, 3=day1...
        # Day column starts at 3
        self._dbank_last_day = (idx - 2) if idx >= 3 else None
        # Read client name from first column
        vals = tv.item(row, 'values')
        self._dbank_last_client = vals[0] if vals else None
    finally:
        # reflect availability of Delete immediately
        if hasattr(self, "_update_data_toolbar"):
            self._update_data_toolbar()

