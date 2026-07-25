"""Active collector editor dialog presentation extracted in Wave 43."""
from __future__ import annotations

import re
import tkinter as tk
from tkinter import messagebox, ttk

_COLLECTOR_DIALOG_DEPENDENCIES = {}
_PROTECTED_GLOBALS = {
    '__builtins__', '__cached__', '__doc__', '__file__', '__loader__',
    '__name__', '__package__', '__spec__',
    '_COLLECTOR_DIALOG_DEPENDENCIES', '_PROTECTED_GLOBALS',
    'configure_collector_dialog_dependencies',
    'COLLECTOR_DIALOG_TARGET', 'COLLECTOR_DIALOG_SOURCE_LINES',
    'COLLECTOR_DIALOG_SOURCE_SHA256', 'COLLECTOR_DIALOG_SIGNATURE',
    'COLLECTOR_DIALOG_NESTED_CALLBACKS', 'COLLECTOR_DIALOG_CALLS',
    're', 'tk', 'messagebox', 'ttk',
}


def configure_collector_dialog_dependencies(namespace):
    _COLLECTOR_DIALOG_DEPENDENCIES.clear()
    _COLLECTOR_DIALOG_DEPENDENCIES.update(namespace)
    for name, value in namespace.items():
        if name not in _PROTECTED_GLOBALS:
            globals()[name] = value


COLLECTOR_DIALOG_TARGET = '_spina_v27_collector_editor_dialog'
COLLECTOR_DIALOG_SOURCE_LINES = 350
COLLECTOR_DIALOG_SOURCE_SHA256 = 'acc8e500cd9e62435bd24d7e998c0dc3c6145e396437f22ca4ee8781c3bbe0f6'
COLLECTOR_DIALOG_SIGNATURE = "self, title='Collector', initial_name='', initial_areas=None, initial_notes=''"
COLLECTOR_DIALOG_NESTED_CALLBACKS = ['_panel', '_assigned_keys', '_refresh_lists', '_clean_assigned_display', '_add_selected', '_remove_selected', '_move_selected', '_move_top', '_move_bottom', '_add_all_visible', '_clear_assigned', '_save', '_cancel']
COLLECTOR_DIALOG_CALLS = ['_add_selected', '_assigned_keys', '_cancel', '_clean_assigned_display', '_move_selected', '_panel', '_refresh_lists', '_remove_selected', '_spina_v27_get_route_master_areas', '_spina_v27_route_button', '_spina_v27_route_colors', 'append', 'assigned_frame.pack', 'assigned_lb.bind', 'assigned_lb.configure', 'assigned_lb.curselection', 'assigned_lb.delete', 'assigned_lb.get', 'assigned_lb.insert', 'assigned_lb.pack', 'assigned_lb.see', 'assigned_lb.selection_clear', 'assigned_lb.selection_set', 'assigned_lb.size', 'assigned_panel.grid', 'assigned_vsb.pack', 'avail_frame.pack', 'avail_vsb.pack', 'available_lb.bind', 'available_lb.configure', 'available_lb.curselection', 'available_lb.delete', 'available_lb.get', 'available_lb.insert', 'available_lb.pack', 'available_lb.size', 'available_panel.grid', 'body.columnconfigure', 'body.pack', 'body.rowconfigure', 'clean.append', 'enumerate', 'footer.pack', 'header.pack', 'initial.append', 'insert', 'join', 'len', 'list', 'lower', 'master_areas.append', 'max', 'messagebox.askyesno', 'messagebox.showwarning', 'middle.grid', 'middle.grid_propagate', 'min', 'name_panel.pack', 'name_var.get', 'next', 'notes_panel.pack', 'notes_txt.get', 'notes_txt.insert', 'notes_txt.pack', 'pack', 'picks.append', 'pop', 'range', 're.sub', 'result.get', 'result.update', 's.lower', 's.split', 'search_a.pack', 'search_assigned_var.get', 'search_assigned_var.set', 'search_assigned_var.trace_add', 'search_available_var.get', 'search_available_var.set', 'search_available_var.trace_add', 'search_s.pack', 'seen.add', 'seen_init.add', 'self.root.winfo_height', 'self.root.winfo_rootx', 'self.root.winfo_rooty', 'self.root.winfo_width', 'set', 'split', 'status_var.set', 'str', 'strip', 'titlebox.pack', 'tk.Frame', 'tk.Label', 'tk.Listbox', 'tk.StringVar', 'tk.Text', 'tk.Toplevel', 'top.bind', 'top.configure', 'top.destroy', 'top.geometry', 'top.grab_release', 'top.grab_set', 'top.minsize', 'top.protocol', 'top.title', 'top.transient', 'top.wait_window', 'top.winfo_screenheight', 'top.winfo_screenwidth', 'ttk.Entry', 'ttk.Scrollbar', 'used.add']

def _spina_v27_collector_editor_dialog(self, title="Collector", initial_name="", initial_areas=None, initial_notes=""):
    """Modern route editor: Available Areas vs Assigned Route Order."""
    c = _spina_v27_route_colors(self)
    result = {"ok": False, "name": None, "areas": None, "notes": None}

    top = tk.Toplevel(self.root)
    top.title(title)
    top.configure(bg=c["bg"])
    try:
        top.transient(self.root)
        top.grab_set()
    except Exception:
        pass

    try:
        sw, sh = top.winfo_screenwidth(), top.winfo_screenheight()
        w = min(1120, max(940, sw - 120))
        h = min(780, max(680, sh - 160))
        rx, ry = self.root.winfo_rootx(), self.root.winfo_rooty()
        rw, rh = self.root.winfo_width(), self.root.winfo_height()
        px = max(10, min(rx + (rw - w) // 2, sw - w - 10))
        py = max(10, min(ry + (rh - h) // 2, sh - h - 60))
        top.geometry(f"{w}x{h}+{px}+{py}")
        top.minsize(900, 640)
    except Exception:
        top.geometry("1040x720")

    name_var = tk.StringVar(value=str(initial_name or "").strip())
    search_available_var = tk.StringVar(value="")
    search_assigned_var = tk.StringVar(value="")
    status_var = tk.StringVar(value="Use Add → / ← Remove or double-click areas. Assigned order is the print order.")

    initial = []
    seen_init = set()
    for a in (initial_areas or []):
        s = str(a or "").strip()
        if not s:
            continue
        k = " ".join(s.split()).lower()
        if k not in seen_init:
            seen_init.add(k)
            initial.append(s)

    assigned = {"areas": list(initial)}
    master_areas = _spina_v27_get_route_master_areas(self)
    # Include initial legacy/unknown areas so user can see and decide to keep/remove them.
    for a in initial:
        if a not in master_areas:
            master_areas.append(a)

    header = tk.Frame(top, bg=c["bg"])
    header.pack(fill="x", padx=18, pady=(16, 10))
    titlebox = tk.Frame(header, bg=c["bg"])
    titlebox.pack(side="left", fill="x", expand=True)
    tk.Label(titlebox, text=title, bg=c["bg"], fg=c["fg"], font=("Segoe UI", 20, "bold"), anchor="w").pack(fill="x")
    tk.Label(titlebox, text="Route Editor", bg=c["bg"], fg=c["muted"], font=("Segoe UI", 10), anchor="w").pack(fill="x", pady=(2, 0))

    name_panel = tk.Frame(top, bg=c["panel"], highlightbackground=c["border"], highlightthickness=1, bd=0)
    name_panel.pack(fill="x", padx=18, pady=(0, 12))
    tk.Label(name_panel, text="Collector Name", bg=c["panel"], fg=c["muted"], font=("Segoe UI", 8, "bold"), anchor="w").pack(fill="x", padx=14, pady=(10, 0))
    ttk.Entry(name_panel, textvariable=name_var, font=("Segoe UI", 12)).pack(fill="x", padx=14, pady=(3, 10))

    body = tk.Frame(top, bg=c["bg"])
    body.pack(fill="both", expand=True, padx=18, pady=(0, 12))
    body.columnconfigure(0, weight=1)
    body.columnconfigure(1, weight=0)
    body.columnconfigure(2, weight=1)
    body.rowconfigure(0, weight=1)

    def _panel(parent, title_text, subtitle):
        p = tk.Frame(parent, bg=c["panel"], highlightbackground=c["border"], highlightthickness=1, bd=0)
        tk.Label(p, text=title_text, bg=c["panel"], fg=c["fg"], font=("Segoe UI", 13, "bold"), anchor="w").pack(fill="x", padx=14, pady=(12, 0))
        tk.Label(p, text=subtitle, bg=c["panel"], fg=c["muted"], font=("Segoe UI", 9), anchor="w").pack(fill="x", padx=14, pady=(2, 8))
        return p

    available_panel = _panel(body, "Available Areas", "Areas not yet assigned to this collector.")
    available_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

    search_a = tk.Frame(available_panel, bg=c["panel"])
    search_a.pack(fill="x", padx=14, pady=(0, 8))
    ttk.Entry(search_a, textvariable=search_available_var).pack(side="left", fill="x", expand=True)
    _spina_v27_route_button(search_a, "Clear", command=lambda: search_available_var.set(""), kind="soft").pack(side="left", padx=(8, 0))

    avail_frame = tk.Frame(available_panel, bg=c["panel"])
    avail_frame.pack(fill="both", expand=True, padx=14, pady=(0, 14))
    available_lb = tk.Listbox(avail_frame, selectmode="extended", bg=c["entry"], fg=c["fg"], selectbackground=c["blue"], relief="flat", font=("Segoe UI", 10), activestyle="none")
    avail_vsb = ttk.Scrollbar(avail_frame, orient="vertical", command=available_lb.yview)
    available_lb.configure(yscrollcommand=avail_vsb.set)
    available_lb.pack(side="left", fill="both", expand=True)
    avail_vsb.pack(side="right", fill="y")

    middle = tk.Frame(body, bg=c["bg"], width=135)
    middle.grid(row=0, column=1, sticky="ns", padx=(0, 10))
    middle.grid_propagate(False)

    assigned_panel = _panel(body, "Assigned Route Order", "This order is used when printing the collector route.")
    assigned_panel.grid(row=0, column=2, sticky="nsew")

    search_s = tk.Frame(assigned_panel, bg=c["panel"])
    search_s.pack(fill="x", padx=14, pady=(0, 8))
    ttk.Entry(search_s, textvariable=search_assigned_var).pack(side="left", fill="x", expand=True)
    _spina_v27_route_button(search_s, "Clear", command=lambda: search_assigned_var.set(""), kind="soft").pack(side="left", padx=(8, 0))

    assigned_frame = tk.Frame(assigned_panel, bg=c["panel"])
    assigned_frame.pack(fill="both", expand=True, padx=14, pady=(0, 14))
    assigned_lb = tk.Listbox(assigned_frame, selectmode="extended", bg=c["entry"], fg=c["fg"], selectbackground=c["green"], relief="flat", font=("Segoe UI", 10), activestyle="none")
    assigned_vsb = ttk.Scrollbar(assigned_frame, orient="vertical", command=assigned_lb.yview)
    assigned_lb.configure(yscrollcommand=assigned_vsb.set)
    assigned_lb.pack(side="left", fill="both", expand=True)
    assigned_vsb.pack(side="right", fill="y")

    def _assigned_keys():
        return {" ".join(str(a).split()).lower() for a in assigned["areas"]}

    def _refresh_lists(select_assigned_index=None):
        try:
            available_lb.delete(0, "end")
            assigned_lb.delete(0, "end")
        except Exception:
            pass

        q_avail = search_available_var.get().strip().lower()
        q_assigned = search_assigned_var.get().strip().lower()
        used = _assigned_keys()

        for a in master_areas:
            s = str(a or "").strip()
            if not s:
                continue
            if " ".join(s.split()).lower() in used:
                continue
            if q_avail and q_avail not in s.lower():
                continue
            available_lb.insert("end", s)

        for idx, a in enumerate(assigned["areas"], start=1):
            s = str(a or "").strip()
            if not s:
                continue
            display = f"{idx}. {s}"
            if q_assigned and q_assigned not in s.lower():
                continue
            assigned_lb.insert("end", display)

        if select_assigned_index is not None:
            try:
                idx = max(0, min(select_assigned_index, assigned_lb.size() - 1))
                assigned_lb.selection_clear(0, "end")
                assigned_lb.selection_set(idx)
                assigned_lb.see(idx)
            except Exception:
                pass

        status_var.set(f"Available: {available_lb.size()} • Assigned: {len(assigned['areas'])}")

    def _clean_assigned_display(value):
        try:
            s = str(value or "")
            return re.sub(r"^\s*\d+\.\s*", "", s).strip()
        except Exception:
            return str(value or "").strip()

    def _add_selected():
        picks = []
        try:
            for i in available_lb.curselection():
                picks.append(available_lb.get(i))
        except Exception:
            picks = []
        if not picks:
            return
        used = _assigned_keys()
        for a in picks:
            s = str(a or "").strip()
            k = " ".join(s.split()).lower()
            if s and k not in used:
                assigned["areas"].append(s)
                used.add(k)
        _refresh_lists(select_assigned_index=len(assigned["areas"]) - 1)

    def _remove_selected():
        picks = []
        try:
            for i in assigned_lb.curselection():
                picks.append(_clean_assigned_display(assigned_lb.get(i)))
        except Exception:
            picks = []
        if not picks:
            return
        rm = {" ".join(str(a).split()).lower() for a in picks}
        assigned["areas"] = [a for a in assigned["areas"] if " ".join(str(a).split()).lower() not in rm]
        _refresh_lists()

    def _move_selected(delta):
        try:
            sel = list(assigned_lb.curselection())
        except Exception:
            sel = []
        if not sel:
            return
        # For filtered view, move by value in real assigned list.
        value = _clean_assigned_display(assigned_lb.get(sel[0]))
        try:
            idx = next(i for i, a in enumerate(assigned["areas"]) if str(a).strip() == value)
        except Exception:
            return
        new_idx = max(0, min(len(assigned["areas"]) - 1, idx + delta))
        if new_idx == idx:
            return
        item = assigned["areas"].pop(idx)
        assigned["areas"].insert(new_idx, item)
        _refresh_lists(select_assigned_index=new_idx)

    def _move_top():
        try:
            sel = list(assigned_lb.curselection())
            if not sel:
                return
            value = _clean_assigned_display(assigned_lb.get(sel[0]))
            idx = next(i for i, a in enumerate(assigned["areas"]) if str(a).strip() == value)
            item = assigned["areas"].pop(idx)
            assigned["areas"].insert(0, item)
            _refresh_lists(select_assigned_index=0)
        except Exception:
            pass

    def _move_bottom():
        try:
            sel = list(assigned_lb.curselection())
            if not sel:
                return
            value = _clean_assigned_display(assigned_lb.get(sel[0]))
            idx = next(i for i, a in enumerate(assigned["areas"]) if str(a).strip() == value)
            item = assigned["areas"].pop(idx)
            assigned["areas"].append(item)
            _refresh_lists(select_assigned_index=len(assigned["areas"]) - 1)
        except Exception:
            pass

    def _add_all_visible():
        used = _assigned_keys()
        for i in range(available_lb.size()):
            s = str(available_lb.get(i) or "").strip()
            k = " ".join(s.split()).lower()
            if s and k not in used:
                assigned["areas"].append(s)
                used.add(k)
        _refresh_lists(select_assigned_index=len(assigned["areas"]) - 1)

    def _clear_assigned():
        if not assigned["areas"]:
            return
        try:
            if not messagebox.askyesno("Clear Assigned Areas", "Remove all assigned areas from this collector?", parent=top):
                return
        except Exception:
            pass
        assigned["areas"] = []
        _refresh_lists()

    # Middle buttons
    tk.Frame(middle, bg=c["bg"], height=45).pack(fill="x")
    _spina_v27_route_button(middle, "Add →", command=_add_selected, kind="primary").pack(fill="x", pady=(0, 8))
    _spina_v27_route_button(middle, "← Remove", command=_remove_selected, kind="soft").pack(fill="x", pady=(0, 18))
    _spina_v27_route_button(middle, "Move Up", command=lambda: _move_selected(-1), kind="soft").pack(fill="x", pady=(0, 8))
    _spina_v27_route_button(middle, "Move Down", command=lambda: _move_selected(1), kind="soft").pack(fill="x", pady=(0, 8))
    _spina_v27_route_button(middle, "Top", command=_move_top, kind="soft").pack(fill="x", pady=(0, 8))
    _spina_v27_route_button(middle, "Bottom", command=_move_bottom, kind="soft").pack(fill="x", pady=(0, 18))
    _spina_v27_route_button(middle, "Add All", command=_add_all_visible, kind="soft").pack(fill="x", pady=(0, 8))
    _spina_v27_route_button(middle, "Clear All", command=_clear_assigned, kind="danger").pack(fill="x")

    try:
        available_lb.bind("<Double-1>", lambda e: _add_selected())
        assigned_lb.bind("<Double-1>", lambda e: _remove_selected())
        search_available_var.trace_add("write", lambda *_: _refresh_lists())
        search_assigned_var.trace_add("write", lambda *_: _refresh_lists())
    except Exception:
        pass

    # Notes section
    notes_panel = tk.Frame(top, bg=c["panel"], highlightbackground=c["border"], highlightthickness=1, bd=0)
    notes_panel.pack(fill="x", padx=18, pady=(0, 12))
    tk.Label(notes_panel, text="Route Notes / Instructions", bg=c["panel"], fg=c["fg"], font=("Segoe UI", 11, "bold"), anchor="w").pack(fill="x", padx=14, pady=(10, 0))
    notes_txt = tk.Text(notes_panel, height=4, wrap="word", bg=c["entry"], fg=c["fg"], insertbackground=c["fg"], relief="flat", font=("Segoe UI", 10))
    notes_txt.pack(fill="x", padx=14, pady=(6, 12))
    try:
        notes_txt.insert("1.0", str(initial_notes or ""))
    except Exception:
        pass

    # Footer
    footer = tk.Frame(top, bg=c["bg"])
    footer.pack(fill="x", padx=18, pady=(0, 16))
    tk.Label(footer, textvariable=status_var, bg=c["bg"], fg=c["muted"], font=("Segoe UI", 9), anchor="w").pack(side="left", fill="x", expand=True)

    def _save():
        nm = (name_var.get() or "").strip()
        if not nm:
            messagebox.showwarning("Missing Name", "Please enter a collector name.", parent=top)
            return
        clean = []
        seen = set()
        for a in assigned["areas"]:
            s = str(a or "").strip()
            if not s:
                continue
            k = " ".join(s.split()).lower()
            if k in seen:
                continue
            seen.add(k)
            clean.append(s)
        if not clean:
            messagebox.showwarning("No Areas", "Please assign at least one area to this collector.", parent=top)
            return
        try:
            nt = notes_txt.get("1.0", "end").strip()
        except Exception:
            nt = ""
        result.update({"ok": True, "name": nm, "areas": clean, "notes": nt})
        try:
            top.grab_release()
        except Exception:
            pass
        top.destroy()

    def _cancel():
        result.update({"ok": False})
        try:
            top.grab_release()
        except Exception:
            pass
        top.destroy()

    _spina_v27_route_button(footer, "Cancel", command=_cancel, kind="soft").pack(side="right", padx=(8, 0))
    _spina_v27_route_button(footer, "Save Route", command=_save, kind="primary").pack(side="right", padx=(8, 0))

    try:
        top.protocol("WM_DELETE_WINDOW", _cancel)
        top.bind("<Escape>", lambda e: _cancel())
    except Exception:
        pass

    _refresh_lists()
    try:
        top.wait_window()
    except Exception:
        pass
    if result.get("ok"):
        return {"name": result["name"], "areas": result["areas"], "notes": result["notes"]}
    return None
