"""Collector Route controller and editor actions generated from the final active SPINA Wave 79 source."""
from __future__ import annotations

_PROTECTED_GLOBALS = {'_save_selected_collector_notes', '_show_unassigned_areas', '_save_collector_notes', '_clear_collectors_search_filters', '_show_no_area_clients', '_show_conflicts', 'configure_collector_route_controller_dependencies', '_collectors_export_selected', '_add_collector', '_collectors_areas_drag_motion', '_collectors_areas_drag_start', '_on_collectors_tree_click', '_on_collectors_tree_wheel', '_collectors_name_from_values', '_populate_collector_details', '_collectors_save_inline_edit', 'COLLECTOR_ROUTE_METHOD_NAMES', '_on_collectors_multi_toggle', '_collectors_delete_selected', '_edit_selected_collector', '_collectors_areas_drag_end', '_delete_selected_collector', '_schedule_collectors_refresh', '_spina_v27_get_route_master_areas'}

def configure_collector_route_controller_dependencies(namespace):
    for name, value in namespace.items():
        if name not in _PROTECTED_GLOBALS and not str(name).startswith('__'):
            globals()[name] = value


def _collectors_name_from_values(self, vals):
    """Return the collector name from a Treeview row values tuple.

    Backwards compatible with older layouts:
      - Old layout: first value is the collector name.
      - New layout: first value is a select marker (radio/checkbox/bullet), second is the collector name.
    """
    try:
        v = list(vals or [])
    except Exception:
        v = []
    if not v:
        return ""

    # First column may be a selection marker in the new UI.
    try:
        first = str(v[0] or "").strip()
    except Exception:
        first = ""

    # Marker set (different fonts render these slightly differently)
    markers = {
        "○","●","◯","◉","☐","☑",
        "•","∙","·","◦","▪","▫","■","□","",  # bullet variants / empties
    }

    if len(v) >= 2:
        try:
            second = str(v[1] or "").strip()
        except Exception:
            second = ""

        # Heuristic: treat the first value as a marker if it is short and non-alphanumeric,
        # or if it matches our marker set.
        try:
            looks_like_marker = (len(first) <= 2 and not any(ch.isalnum() for ch in first))
        except Exception:
            looks_like_marker = False

        if (first in markers) or (looks_like_marker and second):
            return second

    # Fallback: old layout (first column is the name)
    return first


def _on_collectors_multi_toggle(self):
    """Toggle multi-select mode for Collector Route list (checkbox Sel column)."""
    try:
        multi = bool(self.collector_route_multi_var.get())
    except Exception:
        multi = bool(getattr(self, "_collectors_multi_mode", False))
    try:
        self._collectors_multi_mode = multi
    except Exception:
        pass
    # When turning OFF multi mode, clear checked state
    if not multi:
        try:
            self._collectors_clear_checked()
        except Exception:
            pass
    try:
        self.refresh_collectors()
    except Exception:
        pass


def _on_collectors_tree_click(self, event):
    """Handle click in Sel / Actions columns without breaking row selection."""
    try:
        tv = getattr(self, "collectors_tree", None)
        if tv is None:
            return

        iid = tv.identify_row(event.y)
        col = tv.identify_column(event.x)  # '#1'..'#N'
        if not iid:
            return  # header or empty area

        # Always keep row selected + focused
        try:
            tv.selection_set(iid)
            tv.focus(iid)
        except Exception:
            pass

        # Determine multi mode
        try:
            multi = bool(self.collector_route_multi_var.get())
        except Exception:
            multi = bool(getattr(self, "_collectors_multi_mode", False))

        # Sel column (#1) toggles checkbox when in multi mode
        if col == "#1":
            if not multi:
                # Single-select mode: just select row and update details
                try:
                    self._on_collectors_select()
                except Exception:
                    pass
                return

            # Multi mode: toggle checked set
            try:
                vals = tv.item(iid, "values") or ()
            except Exception:
                vals = ()
            try:
                name = self._collectors_name_from_values(vals)
            except Exception:
                name = (vals[1] if len(vals) > 1 else (vals[0] if len(vals) else ""))

            name = (name or "").strip()
            if not name:
                return "break"

            checked = getattr(self, "_collectors_checked", None)
            if checked is None:
                checked = set()
                try:
                    self._collectors_checked = checked
                except Exception:
                    pass

            try:
                if name in checked:
                    checked.remove(name)
                else:
                    checked.add(name)
            except Exception:
                pass

            # Update checkbox markers + bulk bar
            try:
                self._collectors_apply_markers()
            except Exception:
                pass
            try:
                self._collectors_refresh_bulk_bar()
            except Exception:
                pass

            # keep selection visible
            try:
                tv.see(iid)
            except Exception:
                pass
            return "break"

        # Actions column: open context menu (safe and obvious)
        # Columns = sel, collector, areas_count, clients, main_area, sub_area, details, actions
        if col == "#8":
            try:
                m = getattr(self, "_collectors_ctx_menu", None)
                if m is not None:
                    m.tk_popup(event.x_root, event.y_root)
                    return "break"
            except Exception:
                return "break"

        # Default behavior: update details panel
        try:
            self._on_collectors_select()
        except Exception:
            pass
    except Exception:
        return
    return


def _collectors_delete_selected(self):
    from tkinter import messagebox
    checked = sorted(list(getattr(self, "_collectors_checked", set()) or set()), key=lambda s: str(s).lower())
    if not checked:
        messagebox.showinfo("Delete", "No collectors are checked.")
        return
    if not messagebox.askyesno("Confirm Delete", f"Delete {len(checked)} checked collector(s)?"):
        return

    path = data_path("collectors.json")
    try:
        with open(path, 'r', encoding='utf-8') as _f:
            raw = json.load(_f)
    except Exception:
        raw = {}

    # Normalize to dict
    data = {}
    if isinstance(raw, dict):
        data = dict(raw)
    elif isinstance(raw, list):
        for el in raw:
            if isinstance(el, dict):
                nm = (el.get("name") or el.get("collector") or "").strip()
                if not nm:
                    continue
                data[nm] = {"areas": el.get("areas") or el.get("route") or [], "notes": str(el.get("notes") or "")}

    deleted = 0
    for nm in checked:
        if nm in data:
            del data[nm]
            deleted += 1

    try:
        if not _write_json_atomic(path, data):
            raise IOError("Failed to save collectors.json (atomic write failed)")
    except Exception as e:
        _log_exc("collectors:bulk_delete", e)
        messagebox.showwarning("Save Error", "Failed to save collectors.json. See data/spina_app.log")
        return

    try:
        self._collectors_checked = set()
    except Exception:
        self._collectors_checked = set()

    self.refresh_collectors()
    try:
        self.status_var.set(f"Deleted {deleted} collector(s).")
    except Exception:
        pass


def _collectors_export_selected(self):
    from tkinter import messagebox, filedialog
    checked = sorted(list(getattr(self, "_collectors_checked", set()) or set()), key=lambda s: str(s).lower())
    if not checked:
        messagebox.showinfo("Export", "No collectors are checked.")
        return
    fp = filedialog.asksaveasfilename(
        title="Export checked collectors",
        defaultextension=".csv",
        filetypes=[("CSV", "*.csv"), ("JSON", "*.json"), ("All files", "*.*")]
    )
    if not fp:
        return

    path = data_path("collectors.json")
    try:
        with open(path, 'r', encoding='utf-8') as _f:
            raw = json.load(_f)
    except Exception:
        raw = {}

    data = {}
    if isinstance(raw, dict):
        data = raw
    elif isinstance(raw, list):
        for el in raw:
            if isinstance(el, dict):
                nm = (el.get("name") or el.get("collector") or "").strip()
                if not nm:
                    continue
                data[nm] = {"areas": el.get("areas") or el.get("route") or [], "notes": str(el.get("notes") or "")}

    try:
        if str(fp).lower().endswith(".json"):
            out = {nm: data.get(nm, {}) for nm in checked}
            with open(fp, "w", encoding="utf-8") as f:
                json.dump(out, f, ensure_ascii=False, indent=2)
        else:
            import csv
            with open(fp, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["collector", "areas", "notes"])
                for nm in checked:
                    rec = data.get(nm, {}) or {}
                    areas = rec.get("areas") or rec.get("route") or []
                    areas_txt = " | ".join([str(a).strip() for a in (areas or []) if str(a).strip()])
                    notes = str(rec.get("notes") or "")
                    w.writerow([nm, areas_txt, notes])
    except Exception as e:
        _log_exc("collectors:export_checked", e)
        messagebox.showwarning("Export", "Failed to export. See data/spina_app.log")
        return

    messagebox.showinfo("Export", f"Exported {len(checked)} collector(s).")


def _collectors_save_inline_edit(self):
    """Save inline edits to collectors.json (atomic), then refresh UI."""
    from tkinter import messagebox
    if not bool(getattr(self, "_collectors_inline_editing", False)):
        return

    old_name = (getattr(self, "_collectors_inline_original_name", "") or "").strip()
    new_name = ""
    try:
        new_name = str(self.collector_route_edit_name_var.get() or "").strip()
    except Exception:
        new_name = old_name

    if not new_name:
        messagebox.showwarning("Missing Name", "Please enter a collector name.")
        return

    # Gather areas list
    areas = []
    try:
        areas = [self.collector_route_areas_lb.get(i) for i in range(self.collector_route_areas_lb.size())]
        areas = [str(a).strip() for a in (areas or []) if str(a).strip()]
    except Exception:
        areas = []
    if not areas:
        messagebox.showwarning("No Areas", "Please add at least one area.")
        return

    # Notes
    try:
        notes = self.collector_route_notes_txt.get("1.0", "end").strip()
    except Exception:
        notes = ""

    # Load collectors.json and normalize to dict
    path = data_path("collectors.json")
    try:
        with open(path, 'r', encoding='utf-8') as _f:
            raw = json.load(_f)
    except Exception:
        raw = {}

    data = {}
    if isinstance(raw, dict):
        data = dict(raw)
    elif isinstance(raw, list):
        for el in raw:
            if isinstance(el, dict):
                nm = (el.get("name") or el.get("collector") or "").strip()
                if not nm:
                    continue
                data[nm] = {"areas": el.get("areas") or el.get("route") or [], "notes": str(el.get("notes") or "")}

    # Prevent accidental overwrite when renaming
    if old_name != new_name and new_name in data:
        if not messagebox.askyesno("Rename Conflict", f"'{new_name}' already exists. Overwrite it?"):
            return

    # Update / rename
    if old_name and old_name in data and old_name != new_name:
        try:
            del data[old_name]
        except Exception:
            pass
    data[new_name] = {"areas": areas, "notes": notes}

    try:
        if not _write_json_atomic(path, data):
            raise IOError("Failed to save collectors.json (atomic write failed)")
    except Exception as e:
        _log_exc("collectors:inline_save", e)
        messagebox.showwarning("Save Error", "Failed to save collectors.json. See data/spina_app.log")
        return

    # Exit edit mode and refresh
    self._collectors_inline_editing = False
    try:
        self._selected_collector_name = new_name
    except Exception:
        self._selected_collector_name = new_name

    try:
        self.refresh_collectors()
    except Exception:
        pass

    # Reselect saved row (best effort)
    try:
        tree = getattr(self, "collectors_tree", None)
        if tree:
            for iid in tree.get_children():
                vals = tree.item(iid, "values") or ()
                nm = self._collectors_name_from_values(vals)
                if nm == new_name:
                    tree.selection_set(iid)
                    tree.focus(iid)
                    break
    except Exception:
        pass

    # Restore view UI widgets
    try:
        self._collectors_cancel_inline_edit()
    except Exception:
        pass

    try:
        self.status_var.set(f"Saved '{new_name}'.")
    except Exception:
        pass


def _collectors_areas_drag_start(self, event):
    try:
        self._areas_drag_index = self.collector_route_areas_lb.nearest(event.y)
    except Exception:
        self._areas_drag_index = None


def _collectors_areas_drag_motion(self, event):
    """Drag-to-reorder areas listbox (MOVE item) without index-shift bugs."""
    try:
        lb = getattr(self, "collector_route_areas_lb", None)
        if lb is None:
            return
        i = getattr(self, "_areas_drag_index", None)
        if i is None:
            return
        try:
            i = int(i)
        except Exception:
            return

        try:
            j = int(lb.nearest(event.y))
        except Exception:
            return

        if j == i:
            return

        items = list(lb.get(0, "end"))
        if i < 0 or i >= len(items) or j < 0 or j >= len(items):
            return

        item = items.pop(i)
        items.insert(j, item)

        lb.delete(0, "end")
        for it in items:
            lb.insert("end", it)

        self._areas_drag_index = j
        try:
            lb.selection_clear(0, "end")
            lb.selection_set(j)
            lb.activate(j)
            lb.see(j)
        except Exception:
            pass
    except Exception:
        pass


def _collectors_areas_drag_end(self, event):
    try:
        self._areas_drag_index = None
    except Exception:
        self._areas_drag_index = None
    def _on_collectors_tree_wheel(self, event):
        """Ensure mousewheel scroll works on Collector Route list."""
        try:
            tv = getattr(self, "collectors_tree", None)
            if not tv:
                return
            delta = 0
            if hasattr(event, "delta") and event.delta:
                delta = -1 if event.delta > 0 else 1
            elif getattr(event, "num", None) in (4, 5):
                delta = -1 if event.num == 4 else 1
            if delta:
                tv.yview_scroll(delta, "units")
        except Exception:
            pass
        return "break"

    def _schedule_collectors_refresh(self, delay_ms=220):
        """Debounce refresh_collectors while typing in Search."""
        try:
            after_id = getattr(self, "_collectors_refresh_after_id", None)
            if after_id:
                try:
                    self.root.after_cancel(after_id)
                except Exception:
                    pass
        except Exception:
            pass
        try:
            self._collectors_refresh_after_id = self.root.after(delay_ms, self.refresh_collectors)
        except Exception:
            try:
                self.refresh_collectors()
            except Exception:
                pass

    def _clear_collectors_search_filters(self):
        try:
            if hasattr(self, "collector_route_search_var"):
                self.collector_route_search_var.set("")
        except Exception:
            pass
        try:
            if hasattr(self, "collector_route_filter_main_var"):
                self.collector_route_filter_main_var.set("(All)")
        except Exception:
            pass
        try:
            if hasattr(self, "collector_route_filter_conflicts_var"):
                self.collector_route_filter_conflicts_var.set(False)
        except Exception:
            pass
        try:
            if hasattr(self, "collector_route_filter_unknown_var"):
                self.collector_route_filter_unknown_var.set(False)
        except Exception:
            pass
        try:
            self.refresh_collectors()
        except Exception:
            pass


def _schedule_collectors_refresh(self, delay_ms=220):
    """Debounce refresh_collectors while typing in Search."""
    try:
        after_id = getattr(self, "_collectors_refresh_after_id", None)
        if after_id:
            try:
                self.root.after_cancel(after_id)
            except Exception:
                pass
    except Exception:
        pass
    try:
        self._collectors_refresh_after_id = self.root.after(delay_ms, self.refresh_collectors)
    except Exception:
        try:
            self.refresh_collectors()
        except Exception:
            pass


def _clear_collectors_search_filters(self):
    """Clear search + quick filters for Collector's Route UI."""
    try:
        if hasattr(self, "collector_route_search_var"):
            self.collector_route_search_var.set("")
    except Exception:
        pass
    try:
        if hasattr(self, "collector_route_filter_main_var"):
            self.collector_route_filter_main_var.set("(All)")
    except Exception:
        pass
    try:
        if hasattr(self, "collector_route_filter_conflicts_var"):
            self.collector_route_filter_conflicts_var.set(False)
    except Exception:
        pass
    try:
        if hasattr(self, "collector_route_filter_unknown_var"):
            self.collector_route_filter_unknown_var.set(False)
    except Exception:
        pass
    try:
        self.refresh_collectors()
    except Exception:
        pass


def _on_collectors_tree_wheel(self, event):
    """Mouse wheel scroll for Collector Route list (Treeview)."""
    try:
        tv = None
        try:
            # Prefer the widget under the cursor
            tv = event.widget
        except Exception:
            tv = None
        if tv is None or not hasattr(tv, "yview_scroll"):
            tv = getattr(self, "collectors_tree", None)

        if tv is None:
            return

        delta = 0
        if hasattr(event, "delta") and event.delta:
            # Windows: 120 per notch; trackpads may be smaller
            try:
                delta = int(-1 * (event.delta / 120))
            except Exception:
                delta = -1 if event.delta > 0 else 1
            if delta == 0:
                delta = -1 if event.delta > 0 else 1
        elif getattr(event, "num", None) in (4, 5):
            # Linux
            delta = -1 if event.num == 4 else 1

        if delta:
            tv.yview_scroll(delta, "units")
            return "break"
    except Exception:
        return
    return


def _save_collector_notes(self, collector_name, notes_text):
    """Update one collector's notes in collectors.json (atomic, normalized schema)."""
    try:
        collector_name = (collector_name or "").strip()
        if not collector_name:
            return False
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
        except Exception:
            pass
        path = data_path("collectors.json")
        data = _read_json_file(path) or {}

        # Normalize to dict[name] -> {areas:[...], notes:"..."}
        norm = {}

        if isinstance(data, dict):
            for k, v in data.items():
                name = (k or "").strip()
                if not name:
                    continue
                if isinstance(v, dict):
                    areas = v.get("areas", v.get("route", v.get("areas_list", []))) or []
                    notes = v.get("notes", v.get("note", "")) or ""
                elif isinstance(v, list):
                    areas = v
                    notes = ""
                elif isinstance(v, str):
                    areas = []
                    notes = v
                else:
                    areas = []
                    notes = ""
                norm[name] = {"areas": list(areas) if isinstance(areas, (list, tuple)) else [], "notes": str(notes or "")}
        elif isinstance(data, list):
            # Could be list of dicts or list of names
            for item in data:
                if isinstance(item, dict):
                    name = (item.get("name") or item.get("collector") or "").strip()
                    if not name:
                        continue
                    areas = item.get("areas", item.get("route", [])) or []
                    notes = item.get("notes", item.get("note", "")) or ""
                    norm[name] = {"areas": list(areas) if isinstance(areas, (list, tuple)) else [], "notes": str(notes or "")}
                elif isinstance(item, str):
                    name = item.strip()
                    if name:
                        norm[name] = {"areas": [], "notes": ""}
        else:
            norm = {}

        # Preserve existing areas, update notes
        entry = norm.get(collector_name, {"areas": [], "notes": ""})
        areas_keep = entry.get("areas", [])
        norm[collector_name] = {"areas": areas_keep if isinstance(areas_keep, list) else [], "notes": str(notes_text or "").strip()}

        return bool(_write_json_atomic(path, norm))
    except Exception as e:
        try:
            _log_exc("collectors:save_notes", e)
        except Exception:
            pass
        return False


def _save_selected_collector_notes(self):
    """Save Notes from the right panel to collectors.json (atomic)."""
    from tkinter import messagebox
    # Prefer stored selection name, fallback to tree selection
    name = (getattr(self, "_selected_collector_name", "") or "").strip()
    if not name:
        try:
            name = (self._collectors_get_selected_name() or "").strip()
        except Exception:
            name = ""
    if not name:
        messagebox.showwarning("Notes", "Select a collector first.")
        return

    txtw = getattr(self, "collector_route_notes_txt", None)
    notes = ""
    try:
        if txtw:
            notes = (txtw.get("1.0", "end") or "").strip()
    except Exception:
        notes = ""

    ok = False
    try:
        ok = self._save_collector_notes(name, notes)
    except Exception:
        ok = False

    if ok:
        try:
            self.status_var.set(f"Notes saved for '{name}'.")
        except Exception:
            pass
        try:
            self.refresh_collectors()
        except Exception:
            pass
    else:
        messagebox.showwarning("Save Error", "Failed to save notes.\n\nSee log: data/spina_app.log")


def _populate_collector_details(self, collector_name):
    """Update the right panel: selected name, stats, areas tree, notes."""
    try:
        self._selected_collector_name = collector_name or ""
    except Exception:
        self._selected_collector_name = collector_name or ""

    try:
        if hasattr(self, "collector_route_selected_name_var"):
            self.collector_route_selected_name_var.set("Select a collector…" if not collector_name else str(collector_name))
    except Exception:
        pass
    try:
        if hasattr(self, "collector_route_selected_stats_var"):
            self.collector_route_selected_stats_var.set("")
    except Exception:
        pass

    try:
        tv = getattr(self, "collector_route_area_tree", None)
        if tv:
            for iid in tv.get_children():
                tv.delete(iid)
    except Exception:
        pass

    try:
        txtw = getattr(self, "collector_route_notes_txt", None)
        if txtw:
            txtw.delete("1.0", "end")
    except Exception:
        pass

    if not collector_name:
        return

    data = getattr(self, "_collectors_data_cache", {}) or {}
    rowinfo = (getattr(self, "_collectors_row_cache", {}) or {}).get(str(collector_name), {}) or {}
    rec = data.get(str(collector_name), {}) or {}
    areas_list = [str(a).strip() for a in (rec.get("areas") or []) if str(a).strip()]
    notes_txt = (rec.get("notes") or "").strip()

    try:
        reg = int(rowinfo.get("reg", 0) or 0)
        sev = int(rowinfo.get("sev", 0) or 0)
        areas_count = int(rowinfo.get("areas_count", len(areas_list)) or 0)
        flags = []
        if rowinfo.get("any_conflict"):
            flags.append("conflict")
        if rowinfo.get("any_unknown"):
            flags.append("unknown")
        flag_txt = (" • " + ", ".join(flags)) if flags else ""
        if hasattr(self, "collector_route_selected_stats_var"):
            self.collector_route_selected_stats_var.set(f"Areas: {areas_count}    Clients: R:{reg}  7:{sev}{flag_txt}")
    except Exception:
        pass

    try:
        txtw = getattr(self, "collector_route_notes_txt", None)
        if txtw is not None:
            txtw.insert("1.0", notes_txt or "")
    except Exception:
        pass

    try:
        tv = getattr(self, "collector_route_area_tree", None)
        if not tv:
            return

        main_nodes = {}
        order = []
        loose = []
        for a in areas_list:
            ma, su = split_area_main_sub(a)
            ma = (ma or "").strip()
            su = (su or "").strip()
            if not ma:
                loose.append(a)
                continue
            if ma not in main_nodes:
                main_nodes[ma] = []
                order.append(ma)
            if su and su not in main_nodes[ma]:
                main_nodes[ma].append(su)

        for ma in order:
            iid = tv.insert("", "end", text=ma, values=("",))
            for su in main_nodes[ma]:
                tv.insert(iid, "end", text=f"  - {su}", values=("",))
            tv.item(iid, open=True)

        for a in loose:
            tv.insert("", "end", text=a, values=("",))
    except Exception:
        pass


def _spina_v27_get_route_master_areas(self):
    areas = []
    try:
        # Prefer active/master areas from the last route refresh because it already normalizes route area names.
        m = getattr(self, "_last_master_area_name_map", {}) or {}
        if m:
            areas = list(m.values())
    except Exception:
        areas = []

    if not areas:
        try:
            areas = list(self.db.get_all_areas() or [])
        except Exception:
            areas = []

    cleaned = []
    seen = set()
    for a in areas:
        s = str(a or "").strip()
        if not s:
            continue
        k = " ".join(s.split()).lower()
        if k in seen:
            continue
        seen.add(k)
        cleaned.append(s)
    try:
        cleaned = sorted(cleaned, key=lambda x: str(x).lower())
    except Exception:
        pass
    return cleaned


def _show_conflicts(self):
    """Show areas assigned to multiple collectors."""
    from tkinter import messagebox

    conflicts = getattr(self, "_last_conflict_areas", None)
    if conflicts is None:
        try:
            self.refresh_collectors()
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0232', 'suppressed exception excpass_0232', __spina_exc)
            pass
        conflicts = getattr(self, "_last_conflict_areas", {}) or {}

    if not conflicts:
        messagebox.showinfo("Conflicts", "No conflicts found. (No area is assigned to multiple collectors.)")
        return

    name_map = getattr(self, "_last_master_area_name_map", {}) or {}
    lines = []
    for k in sorted(conflicts.keys(), key=lambda s: str(s).lower()):
        area_name = name_map.get(k, k)
        cols = conflicts.get(k) or []
        lines.append(f"• {area_name}: " + ", ".join(cols))
    msg = "Areas assigned to multiple collectors:\n\n" + "\n".join(lines)
    messagebox.showinfo("Conflicts", msg)


def _show_unassigned_areas(self):
    """Show areas not assigned to any collector (plus any unknown route areas)."""
    from tkinter import messagebox

    areas = getattr(self, "_last_unassigned_areas", None)
    unknown = getattr(self, "_last_unknown_route_areas", None)

    # If summary wasn't computed yet, compute now
    if areas is None or unknown is None:
        try:
            self.refresh_collectors()
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0233', 'suppressed exception excpass_0233', __spina_exc)
            pass
        areas = getattr(self, "_last_unassigned_areas", []) or []
        unknown = getattr(self, "_last_unknown_route_areas", []) or []

    if not areas and not unknown:
        messagebox.showinfo("Unassigned Areas", "All areas are assigned to a collector, and all route areas exist in your Areas list.")
        return

    parts = []
    if areas:
        parts.append("Areas NOT assigned to any collector:\n" + "\n".join(f"• {a}" for a in areas))
    if unknown:
        parts.append("Areas in collectors.json NOT found in Areas list:\n" + "\n".join(f"• {a}" for a in unknown))

    messagebox.showinfo("Unassigned Areas", "\n\n".join(parts))


def _show_no_area_clients(self):
    """Show clients that still have blank area (needs assignment)."""
    from tkinter import messagebox

    items = []
    try:
        cur = self.db.conn.cursor()
        rows = cur.execute(
            "SELECT name, loan_type FROM clients WHERE IFNULL(TRIM(area),'')='' "
            "ORDER BY loan_type, name COLLATE NOCASE LIMIT 200"
        ).fetchall()
        for r in (rows or []):
            if isinstance(r, sqlite3.Row):
                items.append((r["name"], r["loan_type"]))
            else:
                items.append((r[0], r[1]))
    except Exception:
        items = []

    if not items:
        messagebox.showinfo("No-Area Clients", "No clients have blank area.")
        return

    msg = "Clients with blank area (showing up to 200):\n\n" + "\n".join(f"• {n} [{lt}]" for n, lt in items)
    messagebox.showinfo("No-Area Clients", msg)


def _delete_selected_collector(self):
    from tkinter import messagebox
    tree = getattr(self, "collectors_tree", None)
    if not tree:
        messagebox.showwarning("Collectors", "Collectors table not ready.")
        return

    sel = ()
    try:
        sel = tree.selection()
    except Exception:
        sel = ()
    sel_id = sel[0] if sel else tree.focus()
    if not sel_id:
        messagebox.showwarning("Select", "Please select a collector to delete.")
        return

    vals = tree.item(sel_id, "values") or ()
    try:
        name = self._collectors_name_from_values(vals)
    except Exception:
        name = (vals[0] if vals else "") or ""
    name = (name or "").strip()
    if not name:
        messagebox.showwarning("Select", "Please select a valid collector row.")
        return

    if not messagebox.askyesno("Confirm Delete", f"Delete collector '{name}'?"):
        return

    path = data_path( "collectors.json")
    try:
        with open(path, 'r', encoding='utf-8') as _f:
            raw = json.load(_f)
    except Exception:
        raw = {}

    data = {}
    if isinstance(raw, dict):
        data = raw
    elif isinstance(raw, list):
        for el in raw:
            if isinstance(el, dict):
                nm = (el.get("name") or el.get("collector") or "").strip()
                if not nm:
                    continue
                aa = el.get("areas") or el.get("route") or []
                data[nm] = {"areas": aa, "notes": str(el.get("notes") or "")}

    if name in data:
        del data[name]
        try:
            if not _write_json_atomic(path, data):
                raise IOError('Failed to save collectors.json (atomic write failed)')
        except Exception as e:
            _log_exc('collectors:save_json', e)
            try:
                messagebox.showwarning('Save Error', 'Failed to save collectors.json.\n\nCheck permissions/disk space.\nSee log: data/spina_app.log')
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_0234', 'suppressed exception excpass_0234', __spina_exc)
                pass
    self.refresh_collectors()
    try:
        self.status_var.set(f"Collector '{name}' deleted.")
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_0235', 'suppressed exception excpass_0235', __spina_exc)
        pass


def _edit_selected_collector(self):
    from tkinter import messagebox

    tree = getattr(self, "collectors_tree", None)
    if not tree:
        messagebox.showwarning("Collectors", "Collectors table not ready.")
        return

    sel = ()
    try:
        sel = tree.selection()
    except Exception:
        sel = ()
    sel_id = sel[0] if sel else tree.focus()
    if not sel_id:
        messagebox.showwarning("Select", "Please select a collector to edit.")
        return

    vals = tree.item(sel_id, "values") or ()
    try:
        cur_name = self._collectors_name_from_values(vals)
    except Exception:
        cur_name = (vals[0] if vals else "") or ""
    cur_name = (cur_name or "").strip()
    if not cur_name:
        messagebox.showwarning("Select", "Please select a valid collector row.")
        return

    path = data_path("collectors.json")
    try:
        with open(path, 'r', encoding='utf-8') as _f:
            raw = json.load(_f)
    except Exception:
        raw = {}

    # normalize to dict schema: {name: {areas:[], notes:""}}
    data = {}
    if isinstance(raw, dict):
        data = raw
    elif isinstance(raw, list):
        for el in raw:
            if isinstance(el, dict):
                nm = (el.get("name") or el.get("collector") or "").strip()
                if not nm:
                    continue
                aa = el.get("areas") or el.get("route") or []
                data[nm] = {"areas": aa, "notes": str(el.get("notes") or "")}

    rec = data.get(cur_name, {"areas": [], "notes": ""})
    dlg = self._collector_editor_dialog(
        title="Edit Collector",
        initial_name=cur_name,
        initial_areas=(rec.get("areas") or []),
        initial_notes=(rec.get("notes") or "")
    )
    if not dlg:
        return  # cancelled

    new_name = (dlg.get("name") or cur_name).strip() or cur_name
    new_areas = dlg.get("areas") or []
    new_notes = (dlg.get("notes") or "").strip()

    if new_name != cur_name and new_name in data:
        messagebox.showerror("Exists", "Another collector already has that name.")
        return

    # rename key if needed
    if new_name != cur_name and cur_name in data:
        data[new_name] = data.pop(cur_name)
    elif new_name not in data:
        data[new_name] = {}

    data[new_name]["areas"] = list(new_areas)
    data[new_name]["notes"] = str(new_notes or "")

    os.makedirs(DATA_DIR, exist_ok=True)
    try:
        if not _write_json_atomic(path, data):
            raise IOError('Failed to save collectors.json (atomic write failed)')
    except Exception as e:
        _log_exc('collectors:save_json', e)
        try:
            messagebox.showwarning('Save Error', 'Failed to save collectors.json.\n\nCheck permissions/disk space.\nSee log: data/spina_app.log')
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0241', 'suppressed exception excpass_0241', __spina_exc)
            pass
    self.refresh_collectors()
    try:
        self.status_var.set(f"Collector '{new_name}' saved.")
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_0242', 'suppressed exception excpass_0242', __spina_exc)
        pass


def _add_collector(self):
    from tkinter import messagebox

    dlg = self._collector_editor_dialog(title="Add Collector", initial_name="", initial_areas=[], initial_notes="")
    if not dlg:
        return

    name = (dlg.get("name") or "").strip()
    areas = dlg.get("areas") or []
    notes = (dlg.get("notes") or "").strip()

    if not name:
        return

    os.makedirs(DATA_DIR, exist_ok=True)
    path = data_path("collectors.json")
    try:
        with open(path, 'r', encoding='utf-8') as _f:
            raw = json.load(_f)
    except Exception:
        raw = {}

    data = {}
    if isinstance(raw, dict):
        data = raw
    elif isinstance(raw, list):
        for el in raw:
            if isinstance(el, dict):
                nm = (el.get("name") or el.get("collector") or "").strip()
                if nm:
                    data[nm] = {"areas": el.get("areas") or el.get("route") or [], "notes": str(el.get("notes") or "")}

    if name in data:
        messagebox.showwarning("Exists", f"{name} already exists.")
        return

    data[name] = {"areas": list(areas), "notes": str(notes or "")}
    try:
        if not _write_json_atomic(path, data):
            raise IOError('Failed to save collectors.json (atomic write failed)')
    except Exception as e:
        _log_exc('collectors:save_json', e)
        try:
            messagebox.showwarning('Save Error', 'Failed to save collectors.json.\n\nCheck permissions/disk space.\nSee log: data/spina_app.log')
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0243', 'suppressed exception excpass_0243', __spina_exc)
            pass
    self.refresh_collectors()
    try:
        self.status_var.set(f"Collector '{name}' added.")
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_0244', 'suppressed exception excpass_0244', __spina_exc)
        pass


COLLECTOR_ROUTE_METHOD_NAMES = ('_collectors_name_from_values', '_on_collectors_multi_toggle', '_on_collectors_tree_click', '_collectors_delete_selected', '_collectors_export_selected', '_collectors_save_inline_edit', '_collectors_areas_drag_start', '_collectors_areas_drag_motion', '_collectors_areas_drag_end', '_schedule_collectors_refresh', '_clear_collectors_search_filters', '_on_collectors_tree_wheel', '_save_collector_notes', '_save_selected_collector_notes', '_populate_collector_details', '_spina_v27_get_route_master_areas', '_show_conflicts', '_show_unassigned_areas', '_show_no_area_clients', '_delete_selected_collector', '_edit_selected_collector', '_add_collector')
