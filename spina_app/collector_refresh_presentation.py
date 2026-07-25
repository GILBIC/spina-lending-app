"""Read-only collector-list refresh presentation extracted in Wave 39."""
from __future__ import annotations

_COLLECTOR_REFRESH_DEPENDENCIES = {}
_PROTECTED_GLOBALS = {
    "__builtins__", "__cached__", "__doc__", "__file__", "__loader__",
    "__name__", "__package__", "__spec__", "_COLLECTOR_REFRESH_DEPENDENCIES",
    "_PROTECTED_GLOBALS", "configure_collector_refresh_dependencies",
    "COLLECTOR_REFRESH_SOURCE_SHA256", "COLLECTOR_REFRESH_TARGET",
    "COLLECTOR_REFRESH_SQL",
}


def configure_collector_refresh_dependencies(namespace):
    _COLLECTOR_REFRESH_DEPENDENCIES.clear()
    _COLLECTOR_REFRESH_DEPENDENCIES.update(namespace)
    for name, value in namespace.items():
        if name not in _PROTECTED_GLOBALS:
            globals()[name] = value


COLLECTOR_REFRESH_TARGET = 'refresh_collectors'
COLLECTOR_REFRESH_SOURCE_SHA256 = '58bcc1ef246ac707440418d1ccf34006f653aa6d3a8e2ac9122f05d233a4b1dd'
COLLECTOR_REFRESH_SQL = ["SELECT DISTINCT TRIM(area) AS a FROM clients WHERE IFNULL(TRIM(area),'')<>'' AND COALESCE(is_archived,0)=0 ORDER BY a COLLATE NOCASE", "SELECT COUNT(*) AS c FROM clients WHERE IFNULL(TRIM(area),'')='' AND COALESCE(is_archived,0)=0", "SELECT TRIM(area) AS area, loan_type, COUNT(*) AS c FROM clients WHERE IFNULL(TRIM(area),'')<>'' AND COALESCE(is_archived,0)=0 GROUP BY TRIM(area), loan_type"]

def refresh_collectors(self):
    """Refresh the Collector's Route table (enhanced).

    - Supports older collectors.json schemas (dict/list/strings) and normalizes to:
        {name: {areas: [...], notes: "..."}}
    - Computes:
        * unassigned areas (master areas not in any route)
        * unknown route areas (route areas not found in master areas)
        * conflicts (same area assigned to multiple collectors)
        * client counts per collector (Regular + 7x7)
    - Applies optional search filter if collector_route_search_var exists.
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    path = data_path("collectors.json")
    try:
        with open(path, 'r', encoding='utf-8') as _f:
            raw = json.load(_f)
    except Exception:
        raw = {}

    # --- Normalize schema to dict[name] = {areas: [...], notes: "..."} ---
    data = {}
    if isinstance(raw, dict):
        for name, rec in (raw or {}).items():
            if not name:
                continue
            if isinstance(rec, dict):
                areas = rec.get("areas") or rec.get("route") or []
                notes = rec.get("notes") or ""
            elif isinstance(rec, list):
                areas = rec
                notes = ""
            else:
                areas = []
                notes = ""
            areas = [str(a).strip() for a in (areas or []) if str(a).strip()]
            data[str(name).strip()] = {"areas": areas, "notes": str(notes) if notes is not None else ""}
    elif isinstance(raw, list):
        for el in raw:
            if isinstance(el, dict):
                name = (el.get("name") or el.get("collector") or "").strip()
                if not name:
                    continue
                areas = el.get("areas") or el.get("route") or []
                areas = [str(a).strip() for a in (areas or []) if str(a).strip()]
                # merge if duplicate
                if name in data:
                    cur = data[name]["areas"]
                    for a in areas:
                        if a not in cur:
                            cur.append(a)
                else:
                    data[name] = {"areas": areas, "notes": str(el.get("notes") or "")}
            elif isinstance(el, str):
                s = el.strip()
                if not s:
                    continue
                # "Name: area1, area2" or "Name| area1, area2"
                if ":" in s or "|" in s:
                    sep = ":" if ":" in s else "|"
                    nm, rest = s.split(sep, 1)
                    name = nm.strip()
                    areas = [a.strip() for a in rest.split(",") if a.strip()]
                    if name:
                        if name in data:
                            cur = data[name]["areas"]
                            for a in areas:
                                if a not in cur:
                                    cur.append(a)
                        else:
                            data[name] = {"areas": areas, "notes": ""}
    else:
        data = {}

    # Cache normalized collectors data for the right-side details panel
    try:
        self._collectors_data_cache = data
    except Exception:
        self._collectors_data_cache = data

    def _norm_area(s: str) -> str:
        try:
            return " ".join(str(s or "").split()).strip().lower()
        except Exception:
            return str(s or "").strip().lower()

    def _lt_key(s: str) -> str:
        x = str(s or "").strip().lower().replace("×", "x")
        if "7x7" in x:
            return "7x7"
        return "regular"

            # --- Collector-route active areas + sets (normalized match to avoid whitespace/case issues) ---
    # Use ONLY areas that currently have at least one ACTIVE client.
    # This keeps unused master areas / archived-only areas from showing as
    # unassigned in the Collector Route screen.
    try:
        _cur_active = self.db.conn.cursor()
        _rows_active = _cur_active.execute(
            "SELECT DISTINCT TRIM(area) AS a FROM clients WHERE IFNULL(TRIM(area),'')<>'' AND COALESCE(is_archived,0)=0 ORDER BY a COLLATE NOCASE"
        ).fetchall()
        master_areas = []
        for _r in (_rows_active or []):
            try:
                _a = _r["a"] if isinstance(_r, sqlite3.Row) else _r[0]
            except Exception:
                _a = ""
            _a = str(_a or "").strip()
            if _a:
                master_areas.append(_a)
    except Exception:
        try:
            master_areas = [str(a).strip() for a in (self.db.get_all_areas() or []) if str(a).strip()]
        except Exception:
            master_areas = []
    master_norm_to_orig = {}
    for a in master_areas:
        k = _norm_area(a)
        if k and k not in master_norm_to_orig:
            master_norm_to_orig[k] = a
    master_norm_set = set(master_norm_to_orig.keys())
    master_order = {(_norm_area(a) or ''): i for i, a in enumerate(master_areas) if _norm_area(a)}
    self._last_master_area_name_map = master_norm_to_orig
    # Update Main filter options (from master areas) without losing current selection
    try:
        mains_opts = []
        seen = set()
        for a in master_areas:
            ma, _su = split_area_main_sub(a)
            ma = (ma or "").strip()
            if ma:
                k = ma.lower()
                if k not in seen:
                    seen.add(k)
                    mains_opts.append(ma)
        try:
            mains_opts = sorted(mains_opts, key=lambda x: str(x).lower())
        except Exception:
            pass

        cmb = getattr(self, "collector_route_filter_main_cmb", None)
        var = getattr(self, "collector_route_filter_main_var", None)
        if cmb is not None:
            new_vals = tuple(["(All)"] + (mains_opts or []))
            try:
                cur_vals = tuple(cmb.cget("values") or ())
            except Exception:
                cur_vals = ()
            if cur_vals != new_vals:
                try:
                    cmb.configure(values=new_vals)
                except Exception:
                    pass
            # If current selection is no longer valid, reset to (All)
            try:
                cur = str(var.get() if var is not None else "(All)")
                if cur not in new_vals:
                    if var is not None:
                        var.set("(All)")
            except Exception:
                pass
    except Exception:
        pass


    # --- NEW: main/sub aware master indexes (lets routes use MAIN-only to cover all sub areas) ---
    master_main_set = set()
    main_to_master_norms = {}   # main_norm -> set(full_area_norm)
    main_sub_to_norm = {}       # (main_norm, sub_norm) -> full_area_norm
    try:
        for a in master_areas:
            ma, su = split_area_main_sub(a)
            mn = _norm_area(ma)
            sn = _norm_area(su)
            full = _norm_area(a)
            if mn:
                master_main_set.add(mn)
                main_to_master_norms.setdefault(mn, set()).add(full)
            if mn and sn and (mn, sn) not in main_sub_to_norm:
                main_sub_to_norm[(mn, sn)] = full
    except Exception:
        master_main_set = set()
        main_to_master_norms = {}
        main_sub_to_norm = {}

    # --- Assigned areas + unknown + conflicts (main/sub aware) ---
    assigned_norm = set()
    area_to_collectors = {}     # full_area_norm -> set(collector_names)
    collector_coverage = {}     # collector_name -> set(full_area_norm)
    unknown_route_entries = set()

    def _expand_route_area_to_master_norms(route_area: str):
        """Return list of master area norms covered by this route entry.

        Rules:
        - If route entry has sub: match exact (main, sub) in master areas (separator-insensitive).
        - If route entry is MAIN-only: cover ALL master areas that share that main.
        - Legacy: if the full string matches a master area exactly, accept it.
        """
        aa = str(route_area or "").strip()
        if not aa:
            return []
        ma, su = split_area_main_sub(aa)
        mn = _norm_area(ma)
        sn = _norm_area(su)
        full = _norm_area(aa)

        # Exact (main, sub)
        if sn:
            k = main_sub_to_norm.get((mn, sn))
            if k:
                return [k]
            if full in master_norm_set:
                return [full]
            return []

        # MAIN-only
        # Prefer MAIN coverage: a MAIN entry covers ALL master areas that share that main,
        # even if there is also an exact master area named the same as the main.
        if mn and mn in main_to_master_norms:
            # stable order for consistent conflict lists
            return sorted(list(main_to_master_norms.get(mn) or []))
        if full in master_norm_set:
            return [full]
        return []

    try:
        for nm, rec in (data or {}).items():
            cov = set()
            for a in (rec.get("areas") or []):
                aa = str(a).strip()
                if not aa:
                    continue
                covered = _expand_route_area_to_master_norms(aa)
                if not covered:
                    unknown_route_entries.add(aa)
                    continue
                for k in covered:
                    assigned_norm.add(k)
                    area_to_collectors.setdefault(k, set()).add(str(nm))
                    cov.add(k)
            collector_coverage[str(nm)] = cov
    except Exception:
        assigned_norm = set()
        area_to_collectors = {}
        collector_coverage = {}
        unknown_route_entries = set()

    # unassigned = master areas not covered by any collector (after MAIN expansion)
    unassigned_areas = [a for a in master_areas if _norm_area(a) not in assigned_norm]
    unknown_route_areas = sorted(list(unknown_route_entries), key=lambda s: str(s).lower())

    # conflicts = same master area assigned to multiple collectors
    conflicts = {k: sorted(list(v), key=lambda s: s.lower()) for k, v in (area_to_collectors or {}).items() if len(v) > 1}
    self._last_conflict_areas = conflicts
    self._last_collector_coverage = collector_coverage

    # --- No-area ACTIVE clients count ---
    # Archived no-area clients should not inflate the Collector Route status bar.
    no_area_clients = 0
    try:
        cur2 = self.db.conn.cursor()
        r2 = cur2.execute(
            "SELECT COUNT(*) AS c FROM clients WHERE IFNULL(TRIM(area),'')='' AND COALESCE(is_archived,0)=0"
        ).fetchone()
        if r2 is not None:
            no_area_clients = int(r2["c"] if isinstance(r2, sqlite3.Row) else r2[0])
    except Exception:
        no_area_clients = 0

    # --- Client counts per area (normalized) ---
    counts = {}  # norm_area -> {regular:int, 7x7:int}
    try:
        cur3 = self.db.conn.cursor()
        rows = cur3.execute(
            "SELECT TRIM(area) AS area, loan_type, COUNT(*) AS c "
            "FROM clients WHERE IFNULL(TRIM(area),'')<>'' AND COALESCE(is_archived,0)=0 "
            "GROUP BY TRIM(area), loan_type"
        ).fetchall()
        for r in (rows or []):
            a = r["area"] if isinstance(r, sqlite3.Row) else r[0]
            lt = r["loan_type"] if isinstance(r, sqlite3.Row) else r[1]
            c = r["c"] if isinstance(r, sqlite3.Row) else r[2]
            k = _norm_area(a)
            if not k:
                continue
            d = counts.setdefault(k, {"regular": 0, "7x7": 0})
            d[_lt_key(lt)] = d.get(_lt_key(lt), 0) + int(c or 0)
    except Exception:
        counts = {}

    # Cache area client counts (norm_area -> {regular,7x7}) for UI
    try:
        self._collectors_area_counts_cache = counts
    except Exception:
        self._collectors_area_counts_cache = counts

    # Store for buttons
    self._last_unassigned_areas = unassigned_areas
    self._last_unknown_route_areas = unknown_route_areas
    self._last_no_area_clients_count = no_area_clients

    # Update status labels (if tab was built)
    try:
        if hasattr(self, "collector_route_unassigned_var"):
            self.collector_route_unassigned_var.set(f"Unassigned areas: {len(unassigned_areas)}")
        if hasattr(self, "collector_route_noarea_var"):
            self.collector_route_noarea_var.set(f"No-area clients: {no_area_clients}")
        if hasattr(self, "collector_route_unknown_var"):
            self.collector_route_unknown_var.set("" if not unknown_route_areas else f"Unknown in routes: {len(unknown_route_areas)}")
        if hasattr(self, "collector_route_conflict_var"):
            self.collector_route_conflict_var.set("" if not conflicts else f"Conflicts: {len(conflicts)}")
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_0229', 'suppressed exception excpass_0229', __spina_exc)
        pass

    tree = getattr(self, "collectors_tree", None)
    if not tree:
        return

    # Filters
    q = ""
    try:
        if hasattr(self, "collector_route_search_var"):
            q = str(self.collector_route_search_var.get() or "").strip().lower()
    except Exception:
        q = ""

    main_filter = "(All)"
    try:
        if hasattr(self, "collector_route_filter_main_var"):
            main_filter = str(self.collector_route_filter_main_var.get() or "(All)").strip()
    except Exception:
        main_filter = "(All)"

    only_conflicts = False
    try:
        only_conflicts = bool(getattr(self, "collector_route_filter_conflicts_var", None).get())
    except Exception:
        only_conflicts = False

    only_unknown = False
    try:
        only_unknown = bool(getattr(self, "collector_route_filter_unknown_var", None).get())
    except Exception:
        only_unknown = False

    # Clear tree
    for iid in tree.get_children():
        tree.delete(iid)

    names = list((data or {}).keys())
    try:
        names = sorted(names, key=lambda s: str(s).lower())
    except Exception:
        pass

    rows = []
    row_cache = {}

    for name in names:
        rec = data.get(name, {}) or {}
        areas_list = [str(a).strip() for a in (rec.get("areas") or []) if str(a).strip()]
        notes_txt = (rec.get("notes", "") or "").strip()

        # Expand route coverage (MAIN-only entries cover all its sub areas)
        try:
            cov = (getattr(self, "_last_collector_coverage", {}) or {}).get(str(name), set()) or set()
        except Exception:
            cov = set()

        # Unknown route entries (do not match any master area or master main)
        any_unknown = False
        try:
            for _a in (areas_list or []):
                aa = str(_a or "").strip()
                if not aa:
                    continue
                ma0, su0 = split_area_main_sub(aa)
                mn0 = _norm_area(ma0)
                sn0 = _norm_area(su0)
                full0 = _norm_area(aa)

                ok0 = False
                if sn0:
                    ok0 = ((mn0, sn0) in main_sub_to_norm) or (full0 in master_norm_set)
                else:
                    ok0 = (full0 in master_norm_set) or (mn0 and mn0 in main_to_master_norms)

                if not ok0:
                    any_unknown = True
                    break
        except Exception:
            any_unknown = False

        # Conflicts (after expansion)
        any_conflict = False
        try:
            for _k in (cov or []):
                if _k in conflicts:
                    any_conflict = True
                    break
        except Exception:
            any_conflict = False

        # Client counts (sum of covered master areas)
        reg = 0
        sev = 0
        try:
            for _k in (cov or []):
                d = counts.get(_k)
                if d:
                    reg += int(d.get("regular", 0) or 0)
                    sev += int(d.get("7x7", 0) or 0)
        except Exception:
            pass

        # Build Main/Sub lists from expanded master coverage for MAIN-only routes
        mains = []
        subs = []
        try:
            if cov:
                _m = []
                _s = []
                _cov_sorted = sorted(list(cov), key=lambda k: master_order.get(k, 10**9))
                for _k in _cov_sorted:
                    _full = (master_norm_to_orig.get(_k) or "").strip()
                    if not _full:
                        continue
                    _ma, _su = split_area_main_sub(_full)
                    if _ma and _ma not in _m:
                        _m.append(_ma)
                    if _su and _su not in _s:
                        _s.append(_su)
                # Keep unknown entries visible too
                for _a in (areas_list or []):
                    _ma2, _su2 = split_area_main_sub(_a)
                    if _ma2 and _ma2 not in _m:
                        _m.append(_ma2)
                    if _su2 and _su2 not in _s:
                        _s.append(_su2)
                mains = _m
                subs = _s
            else:
                for _a in (areas_list or []):
                    _ma, _su = split_area_main_sub(_a)
                    if _ma and _ma not in mains:
                        mains.append(_ma)
                    if _su and _su not in subs:
                        subs.append(_su)
        except Exception:
            pass

        areas_txt = " → ".join(areas_list)
        if areas_txt and notes_txt:
            details = f"{areas_txt}   •   {notes_txt}"
        else:
            details = areas_txt or notes_txt

        areas_count = len(areas_list)
        clients_txt = f"R:{reg} 7:{sev}" if (reg or sev) else ""

        # Apply filters
        if q:
            hay = " ".join([str(name), " ".join(areas_list), notes_txt]).lower()
            if q not in hay:
                continue

        if main_filter and main_filter != "(All)":
            try:
                if str(main_filter).strip() not in (mains or []):
                    continue
            except Exception:
                continue

        if only_conflicts and not any_conflict:
            continue
        if only_unknown and not any_unknown:
            continue

        tags_extra = []
        if any_conflict:
            tags_extra.append("warn")
        if any_unknown:
            tags_extra.append("unknown")

        row = {
            "name": name,
            "areas_count": areas_count,
            "clients_total": reg + sev,
            "clients_txt": clients_txt,
            "main_area": ", ".join(mains),
            "sub_area": ", ".join(subs),
            "details": details,
            "reg": reg,
            "sev": sev,
            "any_conflict": any_conflict,
            "any_unknown": any_unknown,
            "tags_extra": tags_extra,
        }
        rows.append(row)
        row_cache[str(name)] = row

    # Sort rows (by clicked column)
    sort_col = getattr(self, "_collectors_sort_col", "collector")
    reverse = bool(getattr(self, "_collectors_sort_reverse", False))

    def _sort_key(r):
        try:
            if sort_col in ("collector",):
                return str(r.get("name") or "").lower()
            if sort_col == "areas_count":
                return int(r.get("areas_count") or 0)
            if sort_col == "clients":
                return int(r.get("clients_total") or 0)
            if sort_col == "main_area":
                return str(r.get("main_area") or "").lower()
            if sort_col == "sub_area":
                return str(r.get("sub_area") or "").lower()
            if sort_col == "details":
                return str(r.get("details") or "").lower()
        except Exception:
            pass
        return str(r.get("name") or "").lower()

    try:
        rows.sort(key=_sort_key, reverse=reverse)
    except Exception:
        pass

    # Insert rows (with Sel + Actions)
    shown = 0
    multi = False
    try:
        multi = bool(getattr(self, "collector_route_multi_var", None).get())
    except Exception:
        multi = False
    try:
        checked = set(getattr(self, "_collectors_checked", set()) or set())
    except Exception:
        checked = set()
    cur_sel = ""
    try:
        cur_sel = (getattr(self, "_selected_collector_name", "") or "").strip()
    except Exception:
        cur_sel = ""

    for i, r in enumerate(rows):
        base_tag = "odd" if (i % 2 == 0) else "even"
        tags = [base_tag] + (r.get("tags_extra") or [])

        nm = str(r.get("name") or "").strip()
        if multi:
            sel_mark = "☑" if (nm and nm in checked) else "☐"
        else:
            sel_mark = "●" if (nm and cur_sel and nm == cur_sel) else "○"

        actions_txt = "View  Edit  Delete"

        try:
            tree.insert(
                "",
                "end",
                values=(sel_mark, nm, r.get("areas_count"), r.get("clients_txt"),
                        r.get("main_area"), r.get("sub_area"), r.get("details"), actions_txt),
                tags=tuple(tags),
            )
        except Exception:
            try:
                tree.insert("", "end",
                            values=(sel_mark, nm, r.get("main_area"), r.get("sub_area"), r.get("details"), actions_txt),
                            tags=(base_tag,))
            except Exception:
                pass
        shown += 1

    # cache for details panel
    # cache for details panel
    try:
        self._collectors_row_cache = row_cache
    except Exception:
        self._collectors_row_cache = row_cache

    # keep details panel in sync
    try:
        cur_sel = (getattr(self, "_selected_collector_name", "") or "").strip()
        if cur_sel and cur_sel in row_cache:
            self._populate_collector_details(cur_sel)
        else:
            # if there's exactly one row, auto-select it for convenience
            if not cur_sel and len(rows) == 1:
                nm = str(rows[0].get("name") or "").strip()
                if nm:
                    # select first
                    try:
                        iid = tree.get_children()[0]
                        tree.selection_set(iid)
                        tree.focus(iid)
                        self._populate_collector_details(nm)
                    except Exception:
                        pass
    except Exception:
        pass

    try:
        self._collectors_apply_markers()
    except Exception:
        pass
