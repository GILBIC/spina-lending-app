"""Collectors summary presentation helpers extracted from the SPINA desktop entry module.

Collector records, route assignment, database access, printing, notes, and calculations remain
owned by the desktop application. This module owns only summary-card construction, Treeview
styling, and display-card refresh behavior.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from spina_app.theme_palettes import _spina_v25_collector_colors
from spina_app.utilities.numbers import _spina_v25_parse_count_from_var

def _spina_v25_collector_card(parent, title, value="—", subtitle="", accent=None):
    c = _spina_v25_collector_colors()
    frame = tk.Frame(parent, bg=c["card"], highlightbackground=c["border"], highlightthickness=1, bd=0)
    if accent:
        tk.Frame(frame, bg=accent, height=4).pack(fill="x", side="top")
    tk.Label(frame, text=title, bg=c["card"], fg=c["muted"], font=("Segoe UI", 9, "bold"), anchor="w").pack(fill="x", padx=14, pady=(10, 0))
    value_lbl = tk.Label(frame, text=value, bg=c["card"], fg=c["fg"], font=("Segoe UI", 16, "bold"), anchor="w")
    value_lbl.pack(fill="x", padx=14, pady=(4, 0))
    sub_lbl = tk.Label(frame, text=subtitle, bg=c["card"], fg=c["muted"], font=("Segoe UI", 8), anchor="w")
    sub_lbl.pack(fill="x", padx=14, pady=(2, 10))
    return frame, value_lbl, sub_lbl


def _spina_v25_style_collector_trees(self):
    try:
        c = _spina_v25_collector_colors(self)
        st = ttk.Style()
        st.configure(
            "ModernCollector.Treeview",
            rowheight=32,
            font=("Segoe UI", 10),
            background=c["panel"],
            fieldbackground=c["panel"],
            foreground=c["fg"],
            borderwidth=0,
        )
        st.configure(
            "ModernCollector.Treeview.Heading",
            font=("Segoe UI", 10, "bold"),
            background=c["card2"],
            foreground=c["fg"],
            relief="flat",
        )
        st.map("ModernCollector.Treeview", background=[("selected", c["blue"])])
    except Exception:
        pass


def _spina_v25_update_collector_cards(self):
    try:
        cards = getattr(self, "_collector_route_cards", {}) or {}
        tree = getattr(self, "collectors_tree", None)
        shown = 0
        try:
            shown = len(tree.get_children()) if tree is not None else 0
        except Exception:
            shown = 0

        unassigned = _spina_v25_parse_count_from_var(getattr(self, "collector_route_unassigned_var", tk.StringVar(value="0")).get())
        noarea = _spina_v25_parse_count_from_var(getattr(self, "collector_route_noarea_var", tk.StringVar(value="0")).get())
        unknown = _spina_v25_parse_count_from_var(getattr(self, "collector_route_unknown_var", tk.StringVar(value="0")).get())
        conflicts = _spina_v25_parse_count_from_var(getattr(self, "collector_route_conflict_var", tk.StringVar(value="0")).get())

        selected = str(getattr(self, "_selected_collector_name", "") or "").strip()
        view_sub = "Current filtered list"
        try:
            q = str(getattr(self, "collector_route_search_var", tk.StringVar(value="")).get() or "").strip()
            main_filter = str(getattr(self, "collector_route_filter_main_var", tk.StringVar(value="(All)")).get() or "(All)")
            filters = []
            if q:
                filters.append("search")
            if main_filter and main_filter != "(All)":
                filters.append(main_filter)
            if bool(getattr(self, "collector_route_filter_conflicts_var", tk.BooleanVar(value=False)).get()):
                filters.append("conflicts")
            if bool(getattr(self, "collector_route_filter_unknown_var", tk.BooleanVar(value=False)).get()):
                filters.append("unknown")
            if filters:
                view_sub = "Filter: " + ", ".join(filters[:3])
        except Exception:
            pass

        data = {
            "routes": (str(shown), view_sub),
            "unassigned": (str(unassigned), "Active areas not routed"),
            "noarea": (str(noarea), "Active clients needing area"),
            "issues": (str(int(unknown) + int(conflicts)), f"Unknown {unknown} • Conflict {conflicts}"),
            "selected": (selected or "—", "Selected collector"),
        }

        for key, (value, sub) in data.items():
            try:
                val, sublbl = cards.get(key, (None, None))
                if val is not None:
                    val.configure(text=value)
                if sublbl is not None:
                    sublbl.configure(text=sub)
            except Exception:
                pass
    except Exception:
        pass

# Collectors editor and view-state helpers extracted in Wave 26.

def _collectors_get_selected_name(self):
    tree = getattr(self, "collectors_tree", None)
    if not tree:
        return ""
    sel = ()
    try:
        sel = tree.selection()
    except Exception:
        sel = ()
    sel_id = sel[0] if sel else tree.focus()
    if not sel_id:
        return ""
    vals = tree.item(sel_id, "values") or ()
    return self._collectors_name_from_values(vals)

def _collectors_toggle_sections(self):
    try:
        show_areas = bool(getattr(self, "collector_route_show_areas_var", None).get())
    except Exception:
        show_areas = True
    try:
        show_notes = bool(getattr(self, "collector_route_show_notes_var", None).get())
    except Exception:
        show_notes = True

    try:
        if show_areas:
            if not self.collector_route_areas_box.winfo_ismapped():
                self.collector_route_areas_box.pack(fill="both", expand=True, pady=(6, 6))
        else:
            if self.collector_route_areas_box.winfo_ismapped():
                self.collector_route_areas_box.pack_forget()
    except Exception:
        pass

    try:
        if show_notes:
            if not self.collector_route_notes_box.winfo_ismapped():
                self.collector_route_notes_box.pack(fill="both", expand=False)
        else:
            if self.collector_route_notes_box.winfo_ismapped():
                self.collector_route_notes_box.pack_forget()
    except Exception:
        pass

def _collectors_apply_markers(self):
    """Update the Sel column (radio/checkbox) based on current selection/multi checks."""
    tree = getattr(self, "collectors_tree", None)
    if not tree:
        return
    multi = False
    try:
        multi = bool(getattr(self, "collector_route_multi_var", None).get())
    except Exception:
        multi = False

    checked = set(getattr(self, "_collectors_checked", set()) or set())
    cur_name = (getattr(self, "_selected_collector_name", "") or "").strip()
    for iid in tree.get_children():
        vals = list(tree.item(iid, "values") or ())
        if not vals:
            continue
        name = self._collectors_name_from_values(vals)
        if not name:
            continue
        if multi:
            mark = "☑" if name in checked else "☐"
        else:
            mark = "●" if (cur_name and name == cur_name) else "○"
        # Update only the first cell (Sel)
        try:
            if str(vals[0]) != mark:
                vals[0] = mark
                tree.item(iid, values=tuple(vals))
        except Exception:
            pass

    try:
        self._collectors_refresh_bulk_bar()
    except Exception:
        pass

def _collectors_refresh_bulk_bar(self):
    try:
        multi = bool(getattr(self, "collector_route_multi_var", None).get())
    except Exception:
        multi = False
    checked = set(getattr(self, "_collectors_checked", set()) or set())
    bar = getattr(self, "collectors_bulk_bar", None)
    if not bar:
        return
    if multi and checked:
        try:
            self.collectors_bulk_count_var.set(f"Selected: {len(checked)}")
        except Exception:
            pass
        try:
            if not bar.winfo_ismapped():
                bar.pack(fill="x", pady=(0, 6), padx=8)
        except Exception:
            pass
    else:
        try:
            if bar.winfo_ismapped():
                bar.pack_forget()
        except Exception:
            pass

def _collectors_clear_checked(self):
    try:
        self._collectors_checked = set()
    except Exception:
        self._collectors_checked = set()
    try:
        self._collectors_refresh_bulk_bar()
    except Exception:
        pass
    try:
        self._collectors_apply_markers()
    except Exception:
        pass

def _collectors_start_inline_edit(self):
    """Start inline editing for the currently selected collector (right panel)."""
    from tkinter import messagebox
    if bool(getattr(self, "_collectors_inline_editing", False)):
        return
    name = (getattr(self, "_selected_collector_name", "") or "").strip()
    if not name:
        # try from tree selection
        name = self._collectors_get_selected_name()
    if not name:
        messagebox.showwarning("Edit", "Please select a collector first.")
        return

    # Load fields
    self._collectors_inline_editing = True
    self._collectors_inline_original_name = name

    # swap name label -> entry
    try:
        self.collector_route_selected_name_lbl.pack_forget()
    except Exception:
        pass
    try:
        self.collector_route_edit_name_var.set(name)
    except Exception:
        pass
    try:
        self.collector_route_selected_name_ent.pack(side="left", padx=(0, 8))
    except Exception:
        pass

    # swap buttons
    try:
        self.collector_route_btn_edit.pack_forget()
    except Exception:
        pass
    try:
        self.collector_route_btn_save.pack(side="left", padx=(0, 6))
        self.collector_route_btn_cancel.pack(side="left", padx=(0, 8))
    except Exception:
        pass

    # show areas editor and hide view tree
    try:
        self.collector_route_area_tree.grid_remove()
    except Exception:
        pass
    try:
        self.collector_route_areas_edit_frm.grid()
    except Exception:
        pass

    # load current areas + notes into edit widgets
    try:
        self._collectors_load_inline_edit_fields(name)
    except Exception:
        pass

    # Disable list interactions to prevent accidental switching
    try:
        tv = getattr(self, "collectors_tree", None)
        if tv:
            tv.configure(selectmode="browse")
    except Exception:
        pass

def _collectors_load_inline_edit_fields(self, name):
    """Populate the right-side edit widgets from collectors.json cache."""
    # areas
    try:
        self.collector_route_areas_lb.delete(0, "end")
    except Exception:
        pass

    areas = []
    notes = ""
    try:
        cache = getattr(self, "_collectors_data_cache", {}) or {}
        rec = cache.get(name) or {}
        areas = rec.get("areas") or []
        notes = rec.get("notes") or ""
    except Exception:
        areas, notes = [], ""

    # keep the order as stored
    for a in (areas or []):
        s = str(a).strip()
        if s:
            try:
                self.collector_route_areas_lb.insert("end", s)
            except Exception:
                pass

    # notes text
    try:
        self.collector_route_notes_txt.delete("1.0", "end")
        self.collector_route_notes_txt.insert("1.0", str(notes or ""))
    except Exception:
        pass

def _collectors_cancel_inline_edit(self):
    """Cancel inline editing and restore view widgets."""
    if not bool(getattr(self, "_collectors_inline_editing", False)):
        return
    self._collectors_inline_editing = False

    # restore name label
    try:
        self.collector_route_selected_name_ent.pack_forget()
    except Exception:
        pass
    try:
        self.collector_route_selected_name_lbl.pack(side="left")
    except Exception:
        pass

    # restore buttons
    try:
        self.collector_route_btn_save.pack_forget()
        self.collector_route_btn_cancel.pack_forget()
    except Exception:
        pass
    try:
        self.collector_route_btn_edit.pack(side="left", padx=(0, 6))
    except Exception:
        pass

    # restore areas view tree
    try:
        self.collector_route_areas_edit_frm.grid_remove()
    except Exception:
        pass
    try:
        self.collector_route_area_tree.grid()
    except Exception:
        pass

    # repopulate view details for current selection
    try:
        self._populate_collector_details((getattr(self, "_selected_collector_name", "") or "").strip() or None)
    except Exception:
        pass

def _collectors_choose_areas(self):
    """Pick areas via existing picker dialog, then load into listbox."""
    picked = self._area_picker_dialog(initial=[self.collector_route_areas_lb.get(i) for i in range(self.collector_route_areas_lb.size())],
                                      title="Select Route Areas")
    if picked is None:
        return
    try:
        self.collector_route_areas_lb.delete(0, "end")
    except Exception:
        pass
    for a in (picked or []):
        s = str(a).strip()
        if s:
            try:
                self.collector_route_areas_lb.insert("end", s)
            except Exception:
                pass

def _collectors_add_area_text(self):
    s = ""
    try:
        s = str(self.collector_route_area_add_var.get() or "").strip()
    except Exception:
        s = ""
    if not s:
        return
    # avoid duplicates (case-insensitive)
    existing = []
    try:
        existing = [str(self.collector_route_areas_lb.get(i) or "").strip().lower() for i in range(self.collector_route_areas_lb.size())]
    except Exception:
        existing = []
    if s.lower() in existing:
        return
    try:
        self.collector_route_areas_lb.insert("end", s)
        self.collector_route_area_add_var.set("")
    except Exception:
        pass

def _collectors_remove_area(self):
    try:
        idx = self.collector_route_areas_lb.curselection()
        if not idx:
            return
        i = int(idx[0])
        self.collector_route_areas_lb.delete(i)
    except Exception:
        pass

def _collectors_move_area(self, delta):
    try:
        idxs = self.collector_route_areas_lb.curselection()
        if not idxs:
            return
        i = int(idxs[0])
        j = max(0, min(self.collector_route_areas_lb.size() - 1, i + int(delta)))
        if i == j:
            return
        item = self.collector_route_areas_lb.get(i)
        self.collector_route_areas_lb.delete(i)
        self.collector_route_areas_lb.insert(j, item)
        self.collector_route_areas_lb.selection_clear(0, "end")
        self.collector_route_areas_lb.selection_set(j)
    except Exception:
        pass
