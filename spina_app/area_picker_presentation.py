"""Read-only route area-picker presentation extracted in Wave 37."""
from __future__ import annotations

_AREA_PICKER_DEPENDENCIES = {}
_PROTECTED_GLOBALS = {
    "__builtins__", "__cached__", "__doc__", "__file__", "__loader__",
    "__name__", "__package__", "__spec__", "_AREA_PICKER_DEPENDENCIES",
    "_PROTECTED_GLOBALS", "configure_area_picker_dependencies",
    "AREA_PICKER_SOURCE_SHA256", "AREA_PICKER_TARGET",
    "AREA_PICKER_SELECT_SQL",
}


def configure_area_picker_dependencies(namespace):
    _AREA_PICKER_DEPENDENCIES.clear()
    _AREA_PICKER_DEPENDENCIES.update(namespace)
    for name, value in namespace.items():
        if name not in _PROTECTED_GLOBALS:
            globals()[name] = value


AREA_PICKER_TARGET = '_area_picker_dialog'
AREA_PICKER_SOURCE_SHA256 = 'a4c345a42eba11320782ef12cba951c1a5d365bbb0d70e1139c2343aa98624c1'
AREA_PICKER_SELECT_SQL = ["SELECT DISTINCT TRIM(area) AS a FROM clients WHERE IFNULL(TRIM(area),'')<>'' AND COALESCE(is_archived,0)=0 ORDER BY a COLLATE NOCASE"]

def _area_picker_dialog(self, initial=None, title="Select Route Areas", allow_empty: bool = False):
        """Route area picker (Main/Sub Tree + ordered selection).

        What you get:
        - Left: Tree of Main Areas with Sub Areas underneath
        - Right: Selected Route (ordered) as MAIN or MAIN - SUB entries
        - MAIN entry covers all its Sub Areas when printing/validating routes.
        """
        from tkinter import messagebox

        # --- Gather master areas (prefer DB master list) ---
        master_areas = []
        try:
            master_areas = [str(a).strip() for a in (self.db.get_all_areas() or []) if str(a).strip()]
        except Exception:
            master_areas = []
        if not master_areas:
            # Fallback: collect from clients table (no mode filter)
            try:
                cur = self.db.conn.cursor()
                rows = cur.execute(
                    "SELECT DISTINCT TRIM(area) AS a FROM clients WHERE IFNULL(TRIM(area),'')<>'' AND COALESCE(is_archived,0)=0 ORDER BY a COLLATE NOCASE"
                ).fetchall()
                for r in (rows or []):
                    a = (r["a"] if hasattr(r, "keys") else r[0]) if r is not None else ""
                    a = str(a or "").strip()
                    if a:
                        master_areas.append(a)
            except Exception:
                master_areas = []

        # Unique, stable
        uniq = []
        seen = set()
        for a in master_areas:
            if a and a not in seen:
                uniq.append(a)
                seen.add(a)
        master_areas = uniq

        # Normalize initial
        initial = list(initial or [])
        initial = [str(a).strip() for a in initial if str(a).strip()]

        def _norm(s: str) -> str:
            try:
                return " ".join(str(s or "").split()).strip().lower()
            except Exception as __spina_exc:
                __spina_logger = globals().get('_log_suppressed_once')
                if callable(__spina_logger):
                    __spina_logger('silent_ui_11659__norm', 'suppressed UI/startup exception at line 11659', __spina_exc)
                return str(s or "").strip().lower()

        # Build main -> subs mapping (include any initial unknowns so the tree can show them too)
        main_to_subs = {}   # main(str) -> set(sub(str))
        mains = set()
        for a in (master_areas or []) + (initial or []):
            ma, su = split_area_main_sub(a)
            ma = str(ma or "").strip()
            su = str(su or "").strip()
            if not ma and not su:
                continue
            if not ma and su:
                ma = su
                su = ""
            mains.add(ma)
            if su:
                main_to_subs.setdefault(ma, set()).add(su)
            else:
                main_to_subs.setdefault(ma, set())

        # Window
        top = tk.Toplevel(self.root)
        top.title(title)
        top.transient(self.root)
        try:
            top.grab_set()
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0211', 'suppressed exception excpass_0211', __spina_exc)
            pass
        # Size/position: fit within screen so OK/Cancel never fall off-screen (high-DPI safe)
        try:
            top.update_idletasks()
            sw = top.winfo_screenwidth()
            sh = top.winfo_screenheight()
            w = min(980, max(760, sw - 80))
            h = min(560, max(460, sh - 160))
            # center relative to root, then clamp to screen
            try:
                rx, ry = self.root.winfo_rootx(), self.root.winfo_rooty()
                rw, rh = self.root.winfo_width(), self.root.winfo_height()
                px = rx + (rw - w) // 2
                py = ry + (rh - h) // 2
            except Exception:
                px = (sw - w) // 2
                py = (sh - h) // 2
            px = max(10, min(px, sw - w - 10))
            py = max(10, min(py, sh - h - 60))
            top.geometry(f"{w}x{h}+{px}+{py}")
            top.minsize(760, 460)
        except Exception:
            top.geometry("980x560")

        outer = ttk.Frame(top, padding=10)
        outer.pack(fill="both", expand=True)

        # Header: search + quick add
        hdr = ttk.Frame(outer)
        hdr.pack(fill="x")

        ttk.Label(hdr, text="Search:").pack(side="left")
        search_var = tk.StringVar(value="")
        ent_search = ttk.Entry(hdr, textvariable=search_var, width=28)
        ent_search.pack(side="left", padx=(6, 10))

        ttk.Button(hdr, text="Expand all", command=lambda: _expand_all(True)).pack(side="left", padx=(0, 6))
        ttk.Button(hdr, text="Collapse", command=lambda: _expand_all(False)).pack(side="left", padx=(0, 12))

        ttk.Label(hdr, text="New Main:").pack(side="left")
        new_main_var = tk.StringVar(value="")
        ent_main = ttk.Entry(hdr, textvariable=new_main_var, width=18)
        ent_main.pack(side="left", padx=(6, 8))

        ttk.Label(hdr, text="New Sub (optional):").pack(side="left")
        new_sub_var = tk.StringVar(value="")
        ent_sub = ttk.Entry(hdr, textvariable=new_sub_var, width=18)
        ent_sub.pack(side="left", padx=(6, 6))

        # Body: tree + selected list
        body = ttk.Frame(outer)
        body.pack(fill="both", expand=True, pady=(10, 0))

        ttk.Label(body, text="Areas (Main → Sub)").grid(row=0, column=0, sticky="w")
        ttk.Label(body, text="Selected Route (ordered)").grid(row=0, column=2, sticky="w")

        tree = ttk.Treeview(body, show="tree", selectmode="extended", height=18)
        lb_right = tk.Listbox(body, selectmode="extended", exportselection=False)

        tree.grid(row=1, column=0, sticky="nsew")
        lb_right.grid(row=1, column=2, sticky="nsew")

        sb_tree = ttk.Scrollbar(body, orient="vertical", command=tree.yview)
        sb_right = ttk.Scrollbar(body, orient="vertical", command=lb_right.yview)
        tree.configure(yscrollcommand=sb_tree.set)
        lb_right.configure(yscrollcommand=sb_right.set)
        sb_tree.grid(row=1, column=1, sticky="ns")
        sb_right.grid(row=1, column=3, sticky="ns")

        # Middle buttons
        btns = ttk.Frame(body)
        btns.grid(row=1, column=4, padx=10, sticky="ns")

        info_var = tk.StringVar(value="")
        lbl_info = ttk.Label(outer, textvariable=info_var)
        lbl_info.pack(fill="x", pady=(8, 0))

        # Track tree item info
        node_kind = {}  # iid -> ("main", main) or ("sub", main, sub)

        def _set_info():
            try:
                info_var.set(f"Selected: {lb_right.size()}   • Tip: double-click tree to add, double-click selected list to remove.")
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_0212', 'suppressed exception excpass_0212', __spina_exc)
                pass

        def _current_selected_values():
            try:
                return list(lb_right.get(0, "end"))
            except Exception:
                return []

        def _has_main_selected(main_name: str) -> bool:
            mn = _norm(main_name)
            for v in _current_selected_values():
                ma, su = split_area_main_sub(v)
                if _norm(ma) == mn and not _norm(su):
                    return True
            return False

        def _remove_subs_of_main(main_name: str):
            mn = _norm(main_name)
            vals = _current_selected_values()
            keep = []
            for v in vals:
                ma, su = split_area_main_sub(v)
                if _norm(ma) == mn and _norm(su):
                    continue
                keep.append(v)
            _replace_right(keep)

        def _replace_right(vals):
            try:
                lb_right.delete(0, "end")
                for v in vals:
                    if str(v).strip():
                        lb_right.insert("end", str(v).strip())
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_0213', 'suppressed exception excpass_0213', __spina_exc)
                pass
            _set_info()

        def _add_to_right(values_to_add):
            # values_to_add is ordered list of route strings
            cur = _current_selected_values()
            cur_set = set(cur)
            for val in values_to_add:
                val = str(val or "").strip()
                if not val:
                    continue
                ma, su = split_area_main_sub(val)
                ma = str(ma or "").strip()
                su = str(su or "").strip()

                # MAIN selection covers all sub-areas -> remove subs of same main
                if ma and not su:
                    _remove_subs_of_main(ma)

                # If adding a sub but MAIN already selected, skip
                if ma and su and _has_main_selected(ma):
                    continue

                if val not in cur_set:
                    lb_right.insert("end", val)
                    cur_set.add(val)
            _set_info()

        def _get_tree_selection_route_values():
            out = []
            for iid in (tree.selection() or []):
                info = node_kind.get(iid)
                if not info:
                    continue
                if info[0] == "main":
                    ma = str(info[1] or "").strip()
                    if ma:
                        out.append(ma)
                elif info[0] == "sub":
                    ma = str(info[1] or "").strip()
                    su = str(info[2] or "").strip()
                    if ma and su:
                        out.append(join_area_main_sub(ma, su))
            return out

        def add_sel():
            vals = _get_tree_selection_route_values()
            if not vals:
                return
            _add_to_right(vals)

        def remove_sel():
            sel = list(lb_right.curselection() or [])
            if not sel:
                return
            vals = _current_selected_values()
            keep = [v for i, v in enumerate(vals) if i not in set(sel)]
            _replace_right(keep)

        def move_up():
            sel = list(lb_right.curselection() or [])
            if not sel:
                return
            vals = _current_selected_values()
            for i in sel:
                if i <= 0:
                    continue
                vals[i-1], vals[i] = vals[i], vals[i-1]
            _replace_right(vals)
            for i in [max(0, x-1) for x in sel]:
                try:
                    lb_right.selection_set(i)
                except Exception as __spina_exc:
                    _log_suppressed_once('excpass_0214', 'suppressed exception excpass_0214', __spina_exc)
                    pass

        def move_down():
            sel = list(lb_right.curselection() or [])
            if not sel:
                return
            vals = _current_selected_values()
            for i in reversed(sel):
                if i >= len(vals) - 1:
                    continue
                vals[i+1], vals[i] = vals[i], vals[i+1]
            _replace_right(vals)
            for i in [min(lb_right.size()-1, x+1) for x in sel]:
                try:
                    lb_right.selection_set(i)
                except Exception as __spina_exc:
                    _log_suppressed_once('excpass_0215', 'suppressed exception excpass_0215', __spina_exc)
                    pass

        def _selected_main_from_tree():
            """Try to infer the current Main area from the left tree selection."""
            try:
                iid = tree.focus()
                if iid:
                    info = node_kind.get(iid)
                    if info:
                        if info[0] == "main":
                            return str(info[1] or "").strip()
                        if info[0] == "sub":
                            return str(info[1] or "").strip()
                for iid in (tree.selection() or []):
                    info = node_kind.get(iid)
                    if not info:
                        continue
                    if info[0] == "main":
                        return str(info[1] or "").strip()
                    if info[0] == "sub":
                        return str(info[1] or "").strip()
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_0216', 'suppressed exception excpass_0216', __spina_exc)
                pass
            return ""

        def _on_tree_select_fill(_evt=None):
            """Clicking a Main fills the Main entry, so you can add Sub areas quickly."""
            try:
                iid = tree.focus()
                info = node_kind.get(iid)
                if not info:
                    sel = tree.selection() or []
                    if sel:
                        info = node_kind.get(sel[0])
                if not info:
                    return
                if info[0] == "main":
                    ma = str(info[1] or "").strip()
                    if ma:
                        new_main_var.set(ma)
                        try:
                            ent_sub.focus_set()
                        except Exception as __spina_exc:
                            _log_suppressed_once('excpass_0217', 'suppressed exception excpass_0217', __spina_exc)
                            pass
                elif info[0] == "sub":
                    ma = str(info[1] or "").strip()
                    su = str(info[2] or "").strip()
                    if ma:
                        new_main_var.set(ma)
                    if su:
                        new_sub_var.set(su)
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_0218', 'suppressed exception excpass_0218', __spina_exc)
                pass

        def add_new_area():
            # Areas are created as Main + Sub (e.g. "MAIN - SUB").
            ma = str(new_main_var.get() or "").strip()
            su = str(new_sub_var.get() or "").strip()

            # Allow Sub-only add after the user clicks a Main on the left tree
            if (not ma) and su:
                ma = _selected_main_from_tree()
                if ma:
                    try:
                        new_main_var.set(ma)
                    except Exception as __spina_exc:
                        _log_suppressed_once('excpass_0219', 'suppressed exception excpass_0219', __spina_exc)
                        pass

            if not ma:
                try:
                    messagebox.showwarning("Add Area", "Select a Main area (click one on the left) or type a Main name first.")
                except Exception as __spina_exc:
                    _log_suppressed_once('excpass_0220', 'suppressed exception excpass_0220', __spina_exc)
                    pass
                return

            if not su:
                # Per your rule: all areas should start in Sub areas (no Main-only entries here)
                try:
                    messagebox.showwarning("Add Area", "Please enter a Sub area. Areas are saved as 'Main - Sub'.")
                except Exception as __spina_exc:
                    _log_suppressed_once('excpass_0221', 'suppressed exception excpass_0221', __spina_exc)
                    pass
                try:
                    ent_sub.focus_set()
                except Exception as __spina_exc:
                    _log_suppressed_once('excpass_0222', 'suppressed exception excpass_0222', __spina_exc)
                    pass
                return

            # Add into tree mapping
            mains.add(ma)
            main_to_subs.setdefault(ma, set()).add(su)
            val = join_area_main_sub(ma, su)

            _refresh_tree()
            _add_to_right([val])

            # Keep Main for quick multiple Sub additions; clear only Sub
            try:
                new_sub_var.set("")
                ent_sub.focus_set()
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_0223', 'suppressed exception excpass_0223', __spina_exc)
                pass

        def _expand_all(expand: bool):
            try:
                for iid in tree.get_children():
                    tree.item(iid, open=expand)
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_0224', 'suppressed exception excpass_0224', __spina_exc)
                pass

        def _refresh_tree():
            node_kind.clear()
            try:
                tree.delete(*tree.get_children())
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_0225', 'suppressed exception excpass_0225', __spina_exc)
                pass

            q = _norm(search_var.get())
            mains_sorted = sorted(list(mains), key=lambda s: str(s).lower())

            for ma in mains_sorted:
                subs = sorted(list(main_to_subs.get(ma, set()) or []), key=lambda s: str(s).lower())
                ma_match = (not q) or (q in _norm(ma))
                matched_subs = []
                if q:
                    for su in subs:
                        full = f"{ma} - {su}"
                        if (q in _norm(su)) or (q in _norm(full)) or (q in _norm(ma)):
                            matched_subs.append(su)
                else:
                    matched_subs = subs

                if (not q) or ma_match or matched_subs:
                    iid_main = tree.insert("", "end", text=str(ma), open=True)
                    node_kind[iid_main] = ("main", ma)
                    for su in matched_subs:
                        iid_sub = tree.insert(iid_main, "end", text=str(su))
                        node_kind[iid_sub] = ("sub", ma, su)

            _set_info()

        ttk.Button(btns, text="Add →", command=add_sel).pack(fill="x", pady=(0, 6))
        ttk.Button(btns, text="← Remove", command=remove_sel).pack(fill="x", pady=(0, 10))
        ttk.Separator(btns, orient="horizontal").pack(fill="x", pady=(0, 10))
        ttk.Button(btns, text="Move Up", command=move_up).pack(fill="x", pady=(0, 6))
        ttk.Button(btns, text="Move Down", command=move_down).pack(fill="x", pady=(0, 12))
        ttk.Separator(btns, orient="horizontal").pack(fill="x", pady=(0, 10))
        ttk.Button(btns, text="Add New", command=add_new_area).pack(fill="x")

        # Footer
        footer = ttk.Frame(outer)
        footer.pack(fill="x", pady=(10, 0))

        result = {"areas": None}

        def on_ok():
            vals = _current_selected_values()
            if (not vals) and (not allow_empty):
                messagebox.showwarning("Route Areas", "Please select at least one area (or enable empty routes).")
                return
            result["areas"] = vals
            try:
                top.grab_release()
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_0226', 'suppressed exception excpass_0226', __spina_exc)
                pass
            top.destroy()

        def on_cancel():
            result["areas"] = None
            try:
                top.grab_release()
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_0227', 'suppressed exception excpass_0227', __spina_exc)
                pass
            top.destroy()

        ttk.Button(footer, text="Cancel", command=on_cancel).pack(side="right", padx=4)
        ttk.Button(footer, text="OK", command=on_ok).pack(side="right")

        # Bindings
        tree.bind("<Double-1>", lambda e: add_sel())
        tree.bind("<<TreeviewSelect>>", _on_tree_select_fill)
        lb_right.bind("<Double-1>", lambda e: remove_sel())
        ent_main.bind("<Return>", lambda e: add_new_area())
        ent_sub.bind("<Return>", lambda e: add_new_area())

        def _on_search(*_):
            _refresh_tree()
        try:
            search_var.trace_add("write", _on_search)
        except Exception as e:
            _log_ignored("ui.trace_add failed", e, key="ui.trace_add_failed")

        # Layout weights
        body.grid_rowconfigure(1, weight=1)
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(2, weight=1)

        # Initial fill
        _refresh_tree()
        _replace_right(initial)

        try:
            ent_search.focus_set()
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0228', 'suppressed exception excpass_0228', __spina_exc)
            pass

        top.protocol("WM_DELETE_WINDOW", on_cancel)
        top.wait_window()
        return result.get("areas")
