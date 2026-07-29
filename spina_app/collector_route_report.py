"""Collector Route and Daily Ledger report engine generated from the final active SPINA Wave 79 source."""
from __future__ import annotations

_PROTECTED_GLOBALS = {'_spina_save_closed_collector_route_copy_same_format', '_spina_route_notice_upsert', '_spina_crc_copy_existing_route_pdfs', '_spina_route_balance_like_generate_report', '_spina_crc_key', '_spina_route_notice_norm_lt', '_spina_crc_split_area', '_spina_crc_wrap', 'print_full_daily_ledger', '_spina_route_notice_save', '_spina_crc_load_collectors', '_spina_crc_clean_reason', '_spina_route_notice_key', 'COLLECTOR_ROUTE_METHOD_NAMES', '_spina_crc_collector_for_area', '_normalize_client_name_for_lookup', 'print_collector_route_daily_ledger', '_spina_route_adv_marker_for', '_spina_route_notice_load', 'configure_collector_route_report_dependencies', '_spina_crc_route_area_matches', '_spina_crc_active_filtered_areas_for_collector', '_spina_crc_build_paid_cache_for_date', '_spina_crc_fetch_close_rows', '_spina_crc_norm_lt'}

def configure_collector_route_report_dependencies(namespace):
    for name, value in namespace.items():
        if name not in _PROTECTED_GLOBALS and not str(name).startswith('__'):
            globals()[name] = value


def _spina_route_adv_marker_for(db, name: str, day_yyyy_mm_dd: str, loan_type: str = "Regular"):
    """Collector Route ADV lookup with stronger PostgreSQL migration fallback.

    This version does not rely only on the printed route name. It finds the
    client_uid/person_uid from clients first, then checks every matching
    transaction name/uid for the selected loan type. This fixes migrated data
    where a linked 7x7 account name differs from the Regular display name.
    """
    try:
        import re as _re_v7
        day = str(day_yyyy_mm_dd or "")[:10].strip()
        raw_name = str(name or "").strip()
        if not day or not raw_name:
            return (False, "")

        def _norm_name_v7(v):
            s = str(v or "").strip()
            s = _re_v7.sub(r"\s*\((?:7x7|7×7|regular|reg)\)\s*$", "", s, flags=_re_v7.IGNORECASE).strip()
            s = _re_v7.sub(r"\s+", " ", s)
            return s

        def _lt_key_v7(v):
            z = str(v or "Regular").lower().replace(" ", "").replace("×", "x")
            return "7x7" if "7x7" in z else "regular"

        lt_key = _lt_key_v7(loan_type)
        display_name = _norm_name_v7(raw_name)
        names = set([display_name, raw_name])
        uids = set()
        person_uids = set()

        cur = db.conn.cursor()

        # 1) Resolve client rows by name + requested loan type.
        try:
            cur.execute(
                """
                SELECT client_uid, person_uid, name, loan_type
                  FROM clients
                 WHERE UPPER(TRIM(name)) = UPPER(TRIM(?))
                   AND (CASE WHEN LOWER(REPLACE(REPLACE(COALESCE(loan_type,'Regular'),' ',''),'×','x')) LIKE '%7x7%' THEN '7x7' ELSE 'regular' END) = ?
                """,
                (display_name, lt_key),
            )
            for r in (cur.fetchall() or []):
                try:
                    if r['client_uid']:
                        uids.add(str(r['client_uid']).strip())
                    if r['person_uid']:
                        person_uids.add(str(r['person_uid']).strip())
                    if r['name']:
                        names.add(_norm_name_v7(r['name']))
                except Exception:
                    pass
        except Exception:
            pass

        # 2) If helper exists, try it too because it may resolve client_uid better.
        try:
            if hasattr(db, 'get_client_uid'):
                _uid = str(db.get_client_uid(display_name, loan_type=("7x7" if lt_key == "7x7" else "Regular")) or "").strip()
                if _uid:
                    uids.add(_uid)
        except Exception:
            pass

        # 3) If a person_uid is known, include same-person account names/uids for the same requested loan type.
        try:
            for pu in list(person_uids):
                if not pu:
                    continue
                cur.execute(
                    """
                    SELECT client_uid, person_uid, name, loan_type
                      FROM clients
                     WHERE TRIM(COALESCE(person_uid,'')) = TRIM(?)
                    """,
                    (pu,),
                )
                for r in (cur.fetchall() or []):
                    try:
                        r_lt = _lt_key_v7(r['loan_type'])
                        if r_lt != lt_key:
                            continue
                        if r['client_uid']:
                            uids.add(str(r['client_uid']).strip())
                        if r['person_uid']:
                            person_uids.add(str(r['person_uid']).strip())
                        if r['name']:
                            names.add(_norm_name_v7(r['name']))
                    except Exception:
                        pass
        except Exception:
            pass

        # Clean sets.
        names = {n for n in names if str(n or '').strip()}
        uids = {u for u in uids if str(u or '').strip()}

        # 4) Build a broad-but-safe transaction lookup.
        clauses = []
        params = []
        if uids:
            clauses.append("client_uid IN (" + ",".join(["?"] * len(uids)) + ")")
            params.extend(sorted(uids))
        if names:
            clauses.append("UPPER(TRIM(name)) IN (" + ",".join(["UPPER(TRIM(?))"] * len(names)) + ")")
            params.extend(sorted(names))
        if not clauses:
            return (False, "")

        sql = """
            SELECT date, description, name, client_uid, loan_type
              FROM transactions
             WHERE description IS NOT NULL
               AND TRIM(description) <> ''
               AND UPPER(description) LIKE '%ADV%'
               AND (CASE WHEN LOWER(REPLACE(REPLACE(COALESCE(loan_type,'Regular'),' ',''),'×','x')) LIKE '%7x7%' THEN '7x7' ELSE 'regular' END) = ?
               AND (""" + " OR ".join(clauses) + ")"
        cur.execute(sql, tuple([lt_key] + params))
        rows = cur.fetchall() or []

        best_end = ""
        for r in rows:
            try:
                desc = r['description'] if hasattr(r, 'keys') else r[1]
            except Exception:
                desc = ""
            for s, e in (parse_advance_ranges(desc or "") or []):
                ss = str(s or "")[:10]
                ee = str(e or "")[:10]
                if not ss or not ee:
                    continue
                if ee < ss:
                    ss, ee = ee, ss
                if ss <= day <= ee:
                    if (not best_end) or ee > best_end:
                        best_end = ee

        # 5) Last fallback: ignore loan type, but only when exact client_uid/name matches.
        # This catches old ADV entries saved with blank/wrong loan_type after import.
        if not best_end:
            sql2 = """
                SELECT date, description, name, client_uid, loan_type
                  FROM transactions
                 WHERE description IS NOT NULL
                   AND TRIM(description) <> ''
                   AND UPPER(description) LIKE '%ADV%'
                   AND (""" + " OR ".join(clauses) + ")"
            cur.execute(sql2, tuple(params))
            for r in (cur.fetchall() or []):
                try:
                    desc = r['description'] if hasattr(r, 'keys') else r[1]
                except Exception:
                    desc = ""
                for s, e in (parse_advance_ranges(desc or "") or []):
                    ss = str(s or "")[:10]
                    ee = str(e or "")[:10]
                    if not ss or not ee:
                        continue
                    if ee < ss:
                        ss, ee = ee, ss
                    if ss <= day <= ee:
                        if (not best_end) or ee > best_end:
                            best_end = ee

        return (bool(best_end), best_end)
    except Exception as __spina_exc:
        try:
            _log_suppressed_once('route_adv_marker_lookup_failed_v7', 'collector route ADV lookup failed v7', __spina_exc)
        except Exception:
            pass
        return (False, "")


def _normalize_client_name_for_lookup(name: str) -> str:
    """Normalize a display name back to the DB name (Collector Route / PDFs).

    Some PDF layouts append markers like "(7x7)" to the displayed name to avoid duplicates.
    Those markers must be stripped before looking up transactions/reasons/ADV in SQLite.
    We also trim and normalize whitespace.
    """
    try:
        s = str(name or "").strip()
    except Exception:
        return ""
    # Strip trailing markers like "(7x7)", "(7x7-only)", etc.
    try:
        s = re.sub(r"\s*\(\s*7x7[^)]*\)\s*$", "", s, flags=re.IGNORECASE)
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_0591', 'suppressed exception excpass_0591', __spina_exc)
        pass
    # Collapse whitespace
    try:
        s = re.sub(r"\s{2,}", " ", s).strip()
    except Exception:
        s = (s or "").strip()
    return s


def print_collector_route_daily_ledger(self):
    """Print the SELECTED collector's route using the same 3-column
    Daily Collection Ledger layout as `print_full_daily_ledger`, but ONLY
    for that collector's areas (no 'arrange all areas' step).

    - Uses selection() first (more reliable than focus()).
    - Reads collectors.json in multiple historical schemas.
    - Sets temporary flags consumed by print_full_daily_ledger, then cleans them up.
    """
    from tkinter import messagebox
    import os, json

    tree = getattr(self, "collectors_tree", None) or getattr(self, "collector_tree", None)
    if tree is None:
        messagebox.showwarning("Collectors", "Collectors table not ready.")
        return

    sel = ()
    try:
        sel = tree.selection()
    except Exception:
        sel = ()
    sel_id = sel[0] if sel else tree.focus()
    if not sel_id:
        messagebox.showwarning("Select collector", "Please select a collector first.")
        return

    vals = tree.item(sel_id, "values") or ()
    # New UI layout: (Sel, Collector, ...). Extract collector name robustly.
    collector_name = ""
    try:
        collector_name = (getattr(self, "_selected_collector_name", "") or "").strip()
    except Exception:
        collector_name = ""
    if not collector_name:
        try:
            collector_name = self._collectors_name_from_values(vals)
        except Exception:
            collector_name = ""
    if not collector_name:
        try:
            collector_name = (vals[1] if len(vals) > 1 else (vals[0] if len(vals) > 0 else ""))
        except Exception:
            collector_name = ""
    collector_name = (str(collector_name or "")).strip()
    if not collector_name:
        messagebox.showwarning("Select collector", "Please select a valid collector row.")
        return

    os.makedirs(DATA_DIR, exist_ok=True)
    path = data_path( "collectors.json")
    try:
        with open(path, 'r', encoding='utf-8') as _f:
            raw = json.load(_f)
    except Exception:
        raw = {}

    areas = []

    if isinstance(raw, dict):
        val = raw.get(collector_name)
        if isinstance(val, dict):
            aa = val.get("areas") or val.get("route") or []
            areas = [str(a).strip() for a in (aa or []) if str(a).strip()]
        elif isinstance(val, list):
            areas = [str(a).strip() for a in val if str(a).strip()]
    elif isinstance(raw, list):
        for el in raw:
            if isinstance(el, dict):
                nm = (el.get("name") or el.get("collector") or "").strip()
                if nm == collector_name:
                    aa = el.get("areas") or el.get("route") or []
                    areas = [str(a).strip() for a in (aa or []) if str(a).strip()]
                    break
        if not areas:
            for el in raw:
                if isinstance(el, str):
                    s = el.strip()
                    if s.startswith(collector_name + ":") or s.startswith(collector_name + "|"):
                        parts = s.split(":", 1) if ":" in s else s.split("|", 1)
                        if len(parts) == 2:
                            areas = [a.strip() for a in parts[1].split(",") if a.strip()]
                            break

    # Filter saved route entries against CURRENT ACTIVE client areas so archived/empty
    # route entries do not print as blank 0-client headers in the collector route PDF.
    try:
        def _route_norm(_s):
            try:
                return " ".join(str(_s or "").split()).strip().lower()
            except Exception:
                return str(_s or "").strip().lower()

        _active_rows = []
        try:
            _cur = self.db.conn.cursor()
            _active_rows = _cur.execute(
                "SELECT DISTINCT TRIM(area) AS a FROM clients WHERE IFNULL(TRIM(area),'')<>'' AND COALESCE(is_archived,0)=0 ORDER BY a COLLATE NOCASE"
            ).fetchall()
        except Exception:
            _active_rows = []

        _active_areas = []
        for _r in (_active_rows or []):
            try:
                _a = (_r['a'] if hasattr(_r, 'keys') else _r[0])
            except Exception:
                _a = ''
            _a = str(_a or '').strip()
            if _a:
                _active_areas.append(_a)

        _active_full = set()
        _active_main = set()
        _active_pairs = set()
        for _ma_src in (_active_areas or []):
            _full = _route_norm(_ma_src)
            if _full:
                _active_full.add(_full)
            try:
                _m_main, _m_sub = split_area_main_sub(_ma_src)
            except Exception:
                _m_main, _m_sub = (str(_ma_src or "").strip(), "")
            _mn = _route_norm(_m_main)
            _sn = _route_norm(_m_sub)
            if _mn:
                _active_main.add(_mn)
            if _mn and _sn:
                _active_pairs.add((_mn, _sn))

        _filtered = []
        _seen = set()
        for _ra in (areas or []):
            _ra = str(_ra or "").strip()
            if not _ra:
                continue
            try:
                _r_main, _r_sub = split_area_main_sub(_ra)
            except Exception:
                _r_main, _r_sub = (_ra, "")
            _rn = _route_norm(_ra)
            _rmn = _route_norm(_r_main)
            _rsn = _route_norm(_r_sub)

            _ok = False
            if _rsn:
                _ok = ((_rmn, _rsn) in _active_pairs) or (_rn in _active_full)
            else:
                _ok = (_rmn in _active_main) or (_rn in _active_full)

            if _ok and _ra not in _seen:
                _filtered.append(_ra)
                _seen.add(_ra)
        areas = _filtered
    except Exception:
        pass

    if not areas:
        messagebox.showwarning("No areas", f"{collector_name} has no active areas configured.")
        return

    try:
        self._ledger_forced_areas = areas
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_0470', 'suppressed exception excpass_0470', __spina_exc)
        pass

    try:
        self._ledger_forced_collector_name = collector_name
        # Collector Route: restore the classic TWO payment columns (Regular + 7x7)
        self._route_payment_two_cols = True
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_0471', 'suppressed exception excpass_0471', __spina_exc)
        pass

    try:
        self.print_full_daily_ledger()
    finally:
        for attr, fallback in [
            ("_ledger_forced_collector_name", ""),
            ("_route_payment_two_cols", False),
        ]:
            try:
                delattr(self, attr)
            except Exception:
                try:
                    setattr(self, attr, fallback)
                except Exception as __spina_exc:
                    _log_suppressed_once('excpass_0472', 'suppressed exception excpass_0472', __spina_exc)
                    pass

        # Also clear forced areas in case print_full_daily_ledger returned early
        try:
            if hasattr(self, "_ledger_forced_areas"):
                delattr(self, "_ledger_forced_areas")
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0473', 'suppressed exception excpass_0473', __spina_exc)
            pass


def print_full_daily_ledger(self):
    """
    Print a 3-column DAILY COLLECTION LEDGER with a small UI to change:
      - Ledger Date
      - Paper size and orientation
      - Areas order (arrange ALL areas)
    """

    # --- Ensure a base row height is always defined to avoid UnboundLocalError ---
    try:
        row_h  # type: ignore  # may be set later for route layouts
    except NameError:
        row_h = 14  # default row height in points
    # --- Dependencies (local import) ---
    try:
        from reportlab.pdfgen import canvas as _cv
        from reportlab.pdfbase.pdfmetrics import stringWidth
        from reportlab.lib.pagesizes import A4, LETTER, LEGAL
        from reportlab.lib.pagesizes import landscape as _landscape
        from reportlab.lib.units import inch
    except Exception as _e:
        try:
            _alert_user("Print", "Printing requires the 'reportlab' package. Install it with:\n\n    pip install reportlab", kind="error")
        except Exception:
            pass
        return

    import os
    from datetime import date as _today, datetime
    # --- Gather base rows ---
    # NOTE: Collector Route print is REGULAR-only (7x7 is ignored).
    # If a two-payment layout is enabled elsewhere via _route_payment_two_cols, we include BOTH loan types.
    try:
        _route_two_cols = bool(getattr(self, "_route_payment_two_cols", False))
    except Exception:
        _route_two_cols = False

    def _fetch_clients_for(_loan_type):
        try:
            return self.db.fetch_all_clients(loan_type=_loan_type) or []
        except Exception:
            try:
                return [{"name": n, "area": ""} for n in (self.db.get_all_clients(loan_type=_loan_type) or [])]
            except Exception:
                return []


    if _route_two_cols:
        # Two-payment layout: show 2 payment columns, but DO NOT add 7x7-only clients.
        # We only list Regular clients; the 7x7 column is computed for linked 7x7 records of those Regular clients.
        rows_regular = _fetch_clients_for("Regular")
        rows_7x7     = _fetch_clients_for("7x7")
        rows = (rows_regular or [])
    else:
        # Collector Route print: REGULAR ONLY (no 7x7 detection)
        rows_regular = []
        rows_7x7 = []
        try:
            _forced_collector = getattr(self, "_ledger_forced_collector_name", "") or ""
        except Exception:
            _forced_collector = ""
        if _forced_collector:
            rows = _fetch_clients_for("Regular")
        else:
            rows = _fetch_clients_for(self._mode_filter())

    # Distinct areas (A→Z, blank last)
    def _s(v): return (v or "").strip()
    distinct_areas = sorted({_s(r.get("area") if isinstance(r, dict) else getattr(r, "area", "")) for r in rows},
                            key=lambda s: (s == "" or s is None, (s or "").lower()))

    # --- UI 1: Options (date + paper) ---
    def _options_dialog(parent, default_date=None):
        import tkinter as tk
        from tkinter import ttk
        top = tk.Toplevel(parent)
        top.title("Ledger Options")
        top.resizable(False, False)
        try:
            top.attributes("-topmost", True)
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0474', 'suppressed exception excpass_0474', __spina_exc)
            pass
        frm = ttk.Frame(top, padding=12); frm.pack(fill="both", expand=True)

        # Date
        ttk.Label(frm, text="Ledger date (YYYY-MM-DD):").grid(row=0, column=0, sticky="w")
        var_date = tk.StringVar(value=default_date or _today.today().strftime("%Y-%m-%d"))
        _ld_row = ttk.Frame(frm)
        _ld_row.grid(row=0, column=1, sticky='w', padx=(6,0))
        ent_date = ttk.Entry(_ld_row, textvariable=var_date, width=18)
        ent_date.pack(side='left')
        ttk.Button(_ld_row, text='📅', width=3, command=lambda: pick_date(top, var_date, title='Select Ledger Date')).pack(side='left', padx=(4,0))

        # Paper
        ttk.Label(frm, text="Paper size:").grid(row=1, column=0, sticky="w", pady=(8,0))
        papers = ["Folio (8 x 13 in)", "A4 (210 x 297 mm)", "Letter (8.5 x 11 in)", "Legal (8.5 x 14 in)"]
        var_paper = tk.StringVar(value=papers[0])
        cbp = ttk.Combobox(frm, textvariable=var_paper, values=papers, state="readonly", width=24)
        cbp.grid(row=1, column=1, sticky="we", padx=(6,0), pady=(8,0))

        # Orientation
        ttk.Label(frm, text="Orientation:").grid(row=2, column=0, sticky="w", pady=(8,0))
        orients = ["Portrait", "Landscape"]
        var_orient = tk.StringVar(value="Portrait")
        cbo = ttk.Combobox(frm, textvariable=var_orient, values=orients, state="readonly", width=24)
        cbo.grid(row=2, column=1, sticky="we", padx=(6,0), pady=(8,0))

        # Buttons
        btns = ttk.Frame(frm); btns.grid(row=3, column=0, columnspan=2, pady=(10,0), sticky="e")
        out = {"ok": False}
        def _ok():
            out["ok"] = True
            top.destroy()
        def _cancel():
            out["ok"] = False
            top.destroy()
        ttk.Button(btns, text="Cancel", command=_cancel).pack(side="right", padx=6)
        ttk.Button(btns, text="OK", command=_ok).pack(side="right")

        frm.columnconfigure(1, weight=1)
        # Center
        top.update_idletasks()
        try:
            x = parent.winfo_rootx() + (parent.winfo_width()//2 - top.winfo_width()//2)
            y = parent.winfo_rooty() + (parent.winfo_height()//2 - top.winfo_height()//2)
            top.geometry(f"+{max(0,x)}+{max(0,y)}")
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0475', 'suppressed exception excpass_0475', __spina_exc)
            pass
        top.grab_set(); top.wait_window()
        if not out["ok"]:
            return None, None, None
        return var_date.get(), var_paper.get(), var_orient.get()

    # --- UI 2: Arrange Areas (order only, all included) ---
    def _arrange_areas_dialog(parent, areas_list):
        import tkinter as tk
        from tkinter import ttk
        top = tk.Toplevel(parent)
        top.title("Arrange Areas (All will be printed)")
        top.resizable(False, False)
        try:
            top.attributes("-topmost", True)
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0476', 'suppressed exception excpass_0476', __spina_exc)
            pass
        frm = ttk.Frame(top, padding=12); frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="Reorder areas:").grid(row=0, column=0, columnspan=2, sticky="w")
        lb = tk.Listbox(frm, height=14, width=34, exportselection=False)
        lb.grid(row=1, column=0, rowspan=6, sticky="nsw")
        sb = ttk.Scrollbar(frm, orient="vertical", command=lb.yview); sb.grid(row=1, column=1, rowspan=6, sticky="ns")
        lb.config(yscrollcommand=sb.set)

        # NEW: seed with last saved order (if any)

        prefs = _load_ledger_prefs()

        _saved = (prefs.get("areas_order") or [])

        _saved = [a for a in _saved if a in areas_list]

        _rest  = [a for a in areas_list if a not in _saved]

        order = _saved + _rest
        for a in order:
            lb.insert("end", a if a != "" else "(UNASSIGNED)")

        def _move(up=True, to_edge=False):
            sel = lb.curselection()
            if not sel:
                return
            i = sel[0]
            j = 0 if (up and to_edge) else (len(order)-1 if (not up and to_edge) else (i-1 if up else i+1))
            if j < 0 or j >= len(order):
                return
            item = order.pop(i)
            order.insert(j, item)
            lb.delete(0, "end")
            for a in order:
                lb.insert("end", a if a != "" else "(UNASSIGNED)")
            lb.selection_clear(0, "end"); lb.selection_set(j); lb.see(j)

        btns = ttk.Frame(frm); btns.grid(row=1, column=2, rowspan=6, padx=(10,0), sticky="ns")
        ttk.Button(btns, text="Move Up", command=lambda:_move(True, False)).pack(fill="x", pady=2)
        ttk.Button(btns, text="Move Down", command=lambda:_move(False, False)).pack(fill="x", pady=2)
        ttk.Button(btns, text="Top", command=lambda:_move(True, True)).pack(fill="x", pady=6)
        ttk.Button(btns, text="Bottom", command=lambda:_move(False, True)).pack(fill="x", pady=2)

        act = {"ok": False}
        def _ok():
            act["ok"] = True; top.destroy()
        def _cancel():
            act["ok"] = False; top.destroy()
        row_last = 7
        ttk.Button(frm, text="Cancel", command=_cancel).grid(row=row_last, column=2, sticky="e", pady=(10,0))
        ttk.Button(frm, text="OK", command=_ok).grid(row=row_last, column=3, sticky="e", padx=6, pady=(10,0))

        # Center
        top.update_idletasks()
        try:
            x = parent.winfo_rootx() + (parent.winfo_width()//2 - top.winfo_width()//2)
            y = parent.winfo_rooty() + (parent.winfo_height()//2 - top.winfo_height()//2)
            top.geometry(f"+{max(0,x)}+{max(0,y)}")
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0477', 'suppressed exception excpass_0477', __spina_exc)
            pass
        top.grab_set(); top.wait_window()
        return order if act["ok"] else None

    # --- Run dialogs ---
    try:
        _silent_route_copy = bool(getattr(self, "_ledger_silent_route_copy", False))
    except Exception:
        _silent_route_copy = False
    if _silent_route_copy:
        opts = (
            str(getattr(self, "_ledger_forced_date", _today.today().strftime("%Y-%m-%d")) or _today.today().strftime("%Y-%m-%d")),
            str(getattr(self, "_ledger_forced_paper_label", "Folio (8 x 13 in)") or "Folio (8 x 13 in)"),
            str(getattr(self, "_ledger_forced_orientation", "Portrait") or "Portrait"),
        )
    else:
        opts = _options_dialog(self.root, default_date=_today.today().strftime("%Y-%m-%d"))
    if not opts or not all(opts):
        return
    ledger_date, paper_label, orient = opts

    # Resolve page size

    # Load NEW-client highlight setting (days; 0 = off) from prefs
    try:
        highlight_days = int(_load_ledger_prefs().get('new_highlight_days', 7))
    except Exception:
        highlight_days = 7
    page_size = (8*inch, 13*inch)  # default Folio
    if paper_label.startswith("A4"):
        page_size = A4
    elif paper_label.startswith("Letter"):
        page_size = LETTER
    elif paper_label.startswith("Legal"):
        page_size = LEGAL
    elif paper_label.startswith("Folio"):
        page_size = (8*inch, 13*inch)
    if str(orient).lower().startswith("land"):
        page_size = _landscape(page_size)
    width, height = page_size
# Arrange areas
    _forced = getattr(self, '_ledger_forced_areas', None)
    if _forced:
        # Use only the collector's route (preserve their order)
        ordered = [a for a in _forced if a is not None]
    else:
        ordered = _arrange_areas_dialog(self.root, distinct_areas)
    if not ordered:
        return


    # Persist chosen order only for the all-areas (non-forced) flow
    if not getattr(self, '_ledger_forced_areas', None):
        try:
            prefs = _load_ledger_prefs()
            prefs["areas_order"] = ordered
            _save_ledger_prefs(prefs)
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0478', 'suppressed exception excpass_0478', __spina_exc)
            pass
    # --- Build area -> clients map in chosen order ---
    by_area = {}

    if _route_two_cols:
        # Collector Route "Regular-first" logic:
        # - Place clients by their REGULAR record area when they exist in Regular.
        # - Only add 7x7 clients that do NOT have a Regular record (7x7-only), placed by their 7x7 area.
        # This prevents duplicates when a client exists in both types but has different areas.
        def _iter_rows(rr):
            for r in (rr or []):
                if isinstance(r, dict):
                    yield _s(r.get("name")), _s(r.get("area"))
                else:
                    yield _s(getattr(r, "name", "")), _s(getattr(r, "area", ""))

        reg_name_to_area = {}
        reg_name_to_disp = {}
        sev_name_to_area = {}
        sev_name_to_disp = {}

        for nm, ar in _iter_rows(rows_regular):
            if not nm:
                continue
            key = nm.strip().lower()
            reg_name_to_area[key] = ar
            reg_name_to_disp[key] = nm

        for nm, ar in _iter_rows(rows_7x7):
            if not nm:
                continue
            key = nm.strip().lower()
            sev_name_to_area[key] = ar
            sev_name_to_disp[key] = nm

        # Add ALL Regular clients (Regular area wins)
        for key, ar in reg_name_to_area.items():
            disp = reg_name_to_disp.get(key) or key
            by_area.setdefault(ar, []).append(disp)

        # Add 7x7-only (UNLINKED) clients to the collector route.
        # These are 7x7 records that have NO same-name Regular record and blank person_uid.
        # We mark them as "(7x7)" in display, but lookup functions strip the marker when querying SQLite.
        try:
            extra_7x7 = []
            if getattr(self, "db", None) is not None:
                extra_7x7 = self.db.get_unpaired_7x7_names(search=None, search_by='all') or []
        except Exception:
            extra_7x7 = []

        if extra_7x7:
            for nm7 in extra_7x7:
                try:
                    nm7s = str(nm7 or "").strip()
                except Exception:
                    nm7s = nm7
                if not nm7s:
                    continue
                key7 = nm7s.strip().lower()
                # Just in case: never duplicate a Regular-listed name
                if key7 in reg_name_to_area:
                    continue

                # Place by its 7x7 area (fallback to rows_7x7 area map if needed)
                ar7 = ""
                try:
                    info7 = self.db.get_client_info(nm7s, loan_type='7x7') or {}
                    ar7 = _s(info7.get("area"))
                except Exception:
                    ar7 = sev_name_to_area.get(key7, "")

                disp7 = (sev_name_to_disp.get(key7) or nm7s or "").strip()
                if not disp7:
                    continue
                by_area.setdefault(ar7, []).append(f"{disp7} (7x7)")

        # Sort per area (ignore marker)
        def _sort_key(s):
            ss = str(s)
            is7 = 1 if "(7x7)" in ss else 0
            base = ss.replace("(7x7)", "").strip().lower()
            return (is7, base)

        for ar in list(by_area.keys()):
            by_area[ar] = sorted(by_area[ar], key=_sort_key)

    else:
        for r in rows:
            ar = _s(r.get("area") if isinstance(r, dict) else getattr(r, "area", ""))
            nm = _s(r.get("name") if isinstance(r, dict) else getattr(r, "name", ""))
            by_area.setdefault(ar, []).append(nm)
        for k in list(by_area.keys()):
            by_area[k] = sorted(by_area[k], key=lambda s: s.lower())

    # Decide which areas to print
    if getattr(self, '_ledger_forced_areas', None):
        # Main/Sub-aware: MAIN-only route entries cover all matching sub-areas found in client data.
        def _n(_s):
            try:
                return " ".join(str(_s or "").split()).strip().lower()
            except Exception:
                return str(_s or "").strip().lower()

        # Index client areas by (main, sub)
        main_to_keys = {}
        main_sub_to_key = {}
        try:
            for _ak in list(by_area.keys()):
                _ma, _su = split_area_main_sub(_ak)
                _mn = _n(_ma)
                _sn = _n(_su)
                if _mn:
                    main_to_keys.setdefault(_mn, []).append(_ak)
                if _mn and _sn and (_mn, _sn) not in main_sub_to_key:
                    main_sub_to_key[(_mn, _sn)] = _ak
        except Exception:
            main_to_keys = {}
            main_sub_to_key = {}

        # Build route buckets in the collector's order; de-dupe clients across buckets
        by_route = {}
        area_keys = []
        assigned_clients = set()

        for _route in (ordered or []):
            _route = str(_route or "").strip()
            if not _route:
                continue

            _ma, _su = split_area_main_sub(_route)
            _mn = _n(_ma)
            _sn = _n(_su)

            matched_keys = []

            # Exact (main, sub)
            if _sn:
                _k = main_sub_to_key.get((_mn, _sn))
                if _k:
                    matched_keys = [_k]
                else:
                    # fallback: exact string match
                    for _ak in by_area.keys():
                        if _n(_ak) == _n(_route):
                            matched_keys = [_ak]
                            break
            else:
                # MAIN-only -> cover all sub-areas under that main (if any)
                matched_keys = list(main_to_keys.get(_mn, [])) if _mn else []
                if not matched_keys:
                    # fallback: exact string match
                    for _ak in by_area.keys():
                        if _n(_ak) == _n(_route):
                            matched_keys = [_ak]
                            break

            if not matched_keys:
                # Skip route entries that no longer have any ACTIVE matching client area.
                # This prevents archived/empty areas from printing as 0-client headers.
                continue

            matched_keys = sorted(matched_keys, key=lambda s: str(s).lower())
            clients = []
            for _ak in matched_keys:
                for _nm in (by_area.get(_ak) or []):
                    if _nm in assigned_clients:
                        continue
                    assigned_clients.add(_nm)
                    clients.append(_nm)

            if not clients:
                # After de-duplication, do not keep empty route buckets.
                continue

            by_route[_route] = clients
            area_keys.append(_route)

        by_area = by_route
    else:
        # Otherwise, print arranged areas first and then any remaining areas
        area_keys = [a for a in ordered if a in by_area] + [a for a in distinct_areas if a not in ordered and a in by_area]
    # --- Collector Route prefetch cache (fast path; avoids per-client DB scans) ---
    route_adv_cache = {}
    route_reason_cache = {}
    try:
        _is_route_print = bool(getattr(self, "_route_payment_two_cols", False) or getattr(self, "_ledger_forced_collector_name", "") or _route_two_cols)
    except Exception:
        _is_route_print = False

    if _is_route_print:
        try:
            import re as _re
            from datetime import date as _d, timedelta as _td

            _target = _d.fromisoformat(str(ledger_date)[:10])
            # Scan a bounded window for tags to keep printing fast even on huge DBs.
            # If you routinely use UNTIL dates far in the future, increase this (e.g., 1825 for 5 years).
            _from = (_target - _td(days=730)).isoformat()  # last 2 years
            _to = str(ledger_date)[:10]

            # Build base names list for ADV/Reason prefetch.
            # IMPORTANT: keep the exact DB name (including user annotations like "(SUSAN)")
            # and only add a stripped alias when the trailing (...) looks like a legacy loan-type marker
            # such as "(7x7)" / "(7×7)" / "(Regular)".
            _bases = []
            for _ar in (area_keys or []):
                for _nm in (by_area.get(_ar, []) or []):
                    _full = str(_nm or "").strip()
                    if not _full:
                        continue
                    _bases.append(_full)
                    # Add a stripped alias ONLY for known legacy loan-type suffix markers.
                    try:
                        _m = _re.search(r"\(([^)]*)\)\s*$", _full)
                        if _m:
                            _tag = str(_m.group(1) or "").strip().lower()
                            _tag_norm = _tag.replace("×", "x").replace(" ", "")
                            if _tag_norm in ("7x7", "regular", "reg"):
                                _alias = _re.sub(r"\s*\([^)]*\)\s*$", "", _full).strip()
                                if _alias and _alias != _full:
                                    _bases.append(_alias)
                    except Exception:
                        pass

            # unique preserve order (these names come from DB already, so exact match is fine)
            _seen = set()
            _uniq = []
            for _b in _bases:
                if _b in _seen:
                    continue
                _seen.add(_b)
                _uniq.append(_b)

            # Expand name list to include linked Regular/7x7 names (via person_uid).
            # This prevents missing ADV markers in the 7x7 half when the linked record uses a different name.
            try:
                if getattr(self, "db", None) and getattr(self.db, "conn", None) and _uniq:
                    _cur_link = self.db.conn.cursor()
                    _ph0 = ",".join(["?"] * len(_uniq))
                    _cur_link.execute(
                        f"SELECT DISTINCT person_uid FROM clients WHERE name IN ({_ph0}) AND COALESCE(is_archived,0)=0 AND person_uid IS NOT NULL AND TRIM(person_uid) <> ''",
                        tuple(_uniq),
                    )
                    _pus = []
                    for _r0 in (_cur_link.fetchall() or []):
                        try:
                            _pu0 = _r0[0] if not isinstance(_r0, dict) else _r0.get("person_uid")
                        except Exception:
                            _pu0 = None
                        _pu0 = str(_pu0 or "").strip()
                        if _pu0:
                            _pus.append(_pu0)
                    if _pus:
                        _ph_pu = ",".join(["?"] * len(_pus))
                        _cur_link.execute(
                            f"SELECT DISTINCT name FROM clients WHERE person_uid IN ({_ph_pu}) AND COALESCE(is_archived,0)=0 AND name IS NOT NULL AND TRIM(name) <> ''",
                            tuple(_pus),
                        )
                        for _r1 in (_cur_link.fetchall() or []):
                            try:
                                _nm2 = _r1[0] if not isinstance(_r1, dict) else _r1.get("name")
                            except Exception:
                                _nm2 = None
                            _nm2 = str(_nm2 or "").strip()
                            if _nm2 and (_nm2 not in _seen):
                                _seen.add(_nm2)
                                _uniq.append(_nm2)
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_0479', 'suppressed exception excpass_0479', __spina_exc)
                pass


            if _uniq and getattr(self, "db", None) and getattr(self.db, "conn", None):
                _ph = ",".join(["?"] * len(_uniq))
                _cur = self.db.conn.cursor()

                                    # --- PREFETCH ADV rows (route-window aware; day-specific) ---
                # NOTE: We fetch ALL ADV-tagged transactions for the involved names (not just within the route dates),
                # then keep only those whose ADV ranges overlap the route window. This matches Generate Report behavior.
                _route_from = str(_from or "")[:10]
                _route_to = str(_to or "")[:10]
                try:
                    if _route_from and _route_to and (_route_to < _route_from):
                        _route_from, _route_to = _route_to, _route_from
                except Exception as __spina_exc:
                    _log_suppressed_once('excpass_0480', 'suppressed exception excpass_0480', __spina_exc)
                    pass

                _sql_adv = f"""SELECT name, loan_type, date, description
                               FROM transactions
                               WHERE name IN ({_ph})
                                 AND description LIKE '%ADV%'
                                 AND description IS NOT NULL AND TRIM(description) <> ''"""
                _adv_rows = []
                try:
                    _cur.execute(_sql_adv, (*_uniq,))
                    _adv_rows = _cur.fetchall() or []
                except Exception as _e_adv:
                    # Avoid SQLite "too many SQL variables" (e.g., >999 names in IN clause)
                    if "too many sql variables" in str(_e_adv).lower():
                        _adv_rows = []
                        try:
                            _uniq_list = list(_uniq)
                        except Exception:
                            _uniq_list = []
                        for _i in range(0, len(_uniq_list), 900):
                            _chunk = _uniq_list[_i:_i+900]
                            if not _chunk:
                                continue
                            _ph2 = ",".join(["?"] * len(_chunk))
                            _sql_adv2 = f"""SELECT name, loan_type, date, description
                               FROM transactions
                               WHERE name IN ({_ph2})
                                 AND description LIKE '%ADV%'
                                 AND description IS NOT NULL AND TRIM(description) <> ''"""
                            try:
                                _cur.execute(_sql_adv2, (*_chunk,))
                                _adv_rows.extend(_cur.fetchall() or [])
                            except Exception as __spina_exc:
                                _log_suppressed_once('excpass_0481a', 'suppressed exception excpass_0481a', __spina_exc)
                                pass
                    else:
                        raise

                for _r in _adv_rows:
                    try:
                        _nm = _r["name"] if isinstance(_r, dict) else _r[0]
                        _lt = _r["loan_type"] if isinstance(_r, dict) else _r[1]
                        _pay_dt = _r["date"] if isinstance(_r, dict) else _r[2]
                        _desc = _r["description"] if isinstance(_r, dict) else _r[3]
                    except Exception:
                        continue
                    _nm = str(_nm or "").strip()
                    if not _nm:
                        continue
                    _nkey = _nm.lower()
                    _lt_clean = str(_lt or "").lower().replace(" ", "")
                    _lt_norm = "7x7" if ("7x7" in _lt_clean or "7×7" in _lt_clean) else "Regular"
                    _pay_s = str(_pay_dt or "")[:10]
                    _dsc = str(_desc or "")
                    try:
                        for _s, _e in (parse_advance_ranges(_dsc) or []):
                            _s_s = str(_s or "")[:10]
                            _e_s = str(_e or "")[:10]
                            if not _s_s or not _e_s:
                                continue
                            if _e_s < _s_s:
                                _s_s, _e_s = _e_s, _s_s

                            # Keep only ranges that overlap the route window
                            if _route_from and _route_to:
                                if (_e_s < _route_from) or (_s_s > _route_to):
                                    continue

                            _k = (_nkey, _lt_norm)
                            lst = route_adv_cache.get(_k)
                            if not isinstance(lst, list):
                                lst = []
                            tpl = (_s_s, _e_s, _pay_s)  # (range_start, range_end, payment_date)
                            if tpl not in lst:
                                lst.append(tpl)
                            route_adv_cache[_k] = lst
                    except Exception as __spina_exc:
                        _log_suppressed_once('excpass_0481', 'suppressed exception excpass_0481', __spina_exc)
                        pass
# --- PREFETCH RC rows (restricted date range) ---
                _sql_rc = f"""SELECT name, loan_type, date, description
                              FROM transactions
                              WHERE name IN ({_ph})
                                AND date BETWEEN ? AND ?
                                AND description LIKE '%[RC:%'
                                AND description IS NOT NULL AND TRIM(description) <> ''"""
                _rc_rows = []
                try:
                    _cur.execute(_sql_rc, (*_uniq, _from, _to))
                    _rc_rows = _cur.fetchall() or []
                except Exception as _e_rc:
                    if "too many sql variables" in str(_e_rc).lower():
                        _rc_rows = []
                        try:
                            _uniq_list = list(_uniq)
                        except Exception:
                            _uniq_list = []
                        for _i in range(0, len(_uniq_list), 900):
                            _chunk = _uniq_list[_i:_i+900]
                            if not _chunk:
                                continue
                            _ph2 = ",".join(["?"] * len(_chunk))
                            _sql_rc2 = f"""SELECT name, loan_type, date, description
                              FROM transactions
                              WHERE name IN ({_ph2})
                                AND date BETWEEN ? AND ?
                                AND description LIKE '%[RC:%'
                                AND description IS NOT NULL AND TRIM(description) <> ''"""
                            try:
                                _cur.execute(_sql_rc2, (*_chunk, _from, _to))
                                _rc_rows.extend(_cur.fetchall() or [])
                            except Exception as __spina_exc:
                                _log_suppressed_once('excpass_0482a', 'suppressed exception excpass_0482a', __spina_exc)
                                pass
                    else:
                        raise


                _best = {}  # (nkey, lt) -> (start_date_obj, hex)
                for _r in _rc_rows:
                    try:
                        _nm = _r["name"] if isinstance(_r, dict) else _r[0]
                        _lt = _r["loan_type"] if isinstance(_r, dict) else _r[1]
                        _dt = _r["date"] if isinstance(_r, dict) else _r[2]
                        _desc = _r["description"] if isinstance(_r, dict) else _r[3]
                    except Exception:
                        continue

                    _nm = str(_nm or "").strip()
                    if not _nm:
                        continue
                    _nkey = _nm.lower()
                    _lt_clean = str(_lt or "").lower().replace(" ", "")
                    _lt_norm = "7x7" if ("7x7" in _lt_clean or "7×7" in _lt_clean) else "Regular"
                    try:
                        _start = _d.fromisoformat(str(_dt)[:10])
                    except Exception:
                        continue
                    _dsc = str(_desc or "")

                    try:
                        _rt, _hex, _meta = _extract_reason_color_meta_from_desc(_dsc)
                        if not _rt:
                            continue

                        _end = _start
                        _until = None
                        _days = None
                        try:
                            if isinstance(_meta, dict):
                                _until = _meta.get("until")
                                _days = _meta.get("days")
                        except Exception as __spina_exc:
                            _log_suppressed_once('excpass_0482', 'suppressed exception excpass_0482', __spina_exc)
                            pass

                        if _until:
                            try:
                                _end = _until
                            except Exception:
                                _end = _start
                        elif _days:
                            try:
                                _end = _start + _td(days=int(_days) - 1)
                            except Exception:
                                _end = _start

                        if _start <= _target <= _end:
                            _k = (_nkey, _lt_norm)
                            prev = _best.get(_k)
                            if (prev is None) or (_start > prev[0]):
                                _best[_k] = (_start, (_hex or "#d32f2f"))
                    except Exception as __spina_exc:
                        _log_suppressed_once('excpass_0483', 'suppressed exception excpass_0483', __spina_exc)
                        pass

                for _k, (_sd, _hx) in _best.items():
                    route_reason_cache[_k] = _hx
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0484', 'suppressed exception excpass_0484', __spina_exc)
            pass
    # --- End Collector Route prefetch cache ---

    # --- Collector Route link map (FAST: avoids per-row DB queries to resolve Regular vs 7x7 pairs) ---
    route_link_map = {}
    if _is_route_print:
        try:
            import re as _re
            _names = []
            for _ar in (area_keys or []):
                for _nm in (by_area.get(_ar, []) or []):
                    _raw = str(_nm or "").strip()
                    _base = _re.sub(r"\s*\([^)]*\)\s*$", "", _raw).strip()
                    if _raw:
                        _names.append(_raw)
                    if _base and (_base != _raw):
                        _names.append(_base)

            _seen = set()
            _uniq_names = []
            for _n in _names:
                if _n in _seen:
                    continue
                _seen.add(_n)
                _uniq_names.append(_n)

            if _uniq_names and getattr(self, "db", None) and getattr(self.db, "conn", None):
                _cur2 = self.db.conn.cursor()
                try:
                    _sql_lm_tpl = "SELECT name, loan_type, person_uid FROM clients WHERE name IN ({ph}) AND COALESCE(is_archived,0)=0"
                    _crow = _sqlite_fetchall_in_chunks(_cur2, _sql_lm_tpl, _uniq_names, chunk=900)
                except Exception:
                    _crow = []

                _by_pu = {}
                for _r in _crow:
                    try:
                        _nm = _r["name"]
                        _lt = _r["loan_type"]
                        _pu = _r["person_uid"]
                    except Exception:
                        try:
                            _nm, _lt, _pu = _r[0], _r[1], _r[2]
                        except Exception:
                            continue
                    _nm = str(_nm or "").strip()
                    _pu = str(_pu or "").strip()
                    if not _nm:
                        continue
                    _lt_clean = str(_lt or "").lower().replace(" ", "")
                    _lt_norm = "7x7" if ("7x7" in _lt_clean or "7×7" in _lt_clean) else "Regular"
                    if _pu:
                        _by_pu.setdefault(_pu, {})
                        _by_pu[_pu][_lt_norm] = _nm


                # Expand with all linked names for those person_uids (so Regular-tab routes can still resolve 7x7 names).
                try:
                    _pus = [str(_pu or "").strip() for _pu in _by_pu.keys() if str(_pu or "").strip()]
                    if _pus:
                        _ph_pu = ",".join(["?"] * len(_pus))
                        _cur2.execute(
                            f"SELECT name, loan_type, person_uid FROM clients WHERE person_uid IN ({_ph_pu}) AND COALESCE(is_archived,0)=0",
                            tuple(_pus),
                        )
                        _crow_all = _cur2.fetchall() or []
                        for _r in _crow_all:
                            try:
                                _nm2 = _r["name"]
                                _lt2 = _r["loan_type"]
                                _pu2 = _r["person_uid"]
                            except Exception:
                                try:
                                    _nm2, _lt2, _pu2 = _r[0], _r[1], _r[2]
                                except Exception:
                                    continue
                            _nm2 = str(_nm2 or "").strip()
                            _pu2 = str(_pu2 or "").strip()
                            if (not _nm2) or (not _pu2):
                                continue
                            _lt2_clean = str(_lt2 or "").lower().replace(" ", "")
                            _lt2_norm = "7x7" if ("7x7" in _lt2_clean or "7×7" in _lt2_clean) else "Regular"
                            _by_pu.setdefault(_pu2, {})
                            # Prefer existing values but fill missing sides
                            if (_lt2_norm not in _by_pu[_pu2]) or (not str(_by_pu[_pu2].get(_lt2_norm) or "").strip()):
                                _by_pu[_pu2][_lt2_norm] = _nm2
                except Exception as __spina_exc:
                    _log_suppressed_once('excpass_0485', 'suppressed exception excpass_0485', __spina_exc)
                    pass

                def _route_aliases(_name):
                    try:
                        _raw = str(_name or "").strip()
                    except Exception:
                        _raw = ""
                    if not _raw:
                        return []
                    _base = _re.sub(r"\s*\([^)]*\)\s*$", "", _raw).strip()
                    _out = []
                    for _cand in (_raw, _base):
                        _cand = str(_cand or "").strip()
                        if _cand and (_cand.lower() not in _out):
                            _out.append(_cand.lower())
                    return _out

                for _pu, _pair in _by_pu.items():
                    if not isinstance(_pair, dict):
                        continue
                    # Mark whether this person_uid truly has BOTH loan types.
                    try:
                        _pair["_linked"] = bool(str(_pair.get("Regular") or "").strip() and str(_pair.get("7x7") or "").strip())
                    except Exception:
                        _pair["_linked"] = False

                    # Store by exact and stripped aliases for fast lookup
                    for _nm in (_pair.get("Regular"), _pair.get("7x7")):
                        for _alias in _route_aliases(_nm):
                            route_link_map[_alias] = _pair

            # Ensure every visible route name resolves to something (even if person_uid missing)
            for _nm in _uniq_names:
                _rawk = str(_nm or "").strip().lower()
                if _rawk and (_rawk not in route_link_map):
                    route_link_map[_rawk] = {"Regular": "", "7x7": "", "_linked": False}
        except Exception:
            route_link_map = {}
    # --- End Collector Route link map ---


    # --- Collector Route expected totals per area ---
    area_expected_map = {}
    try:
        import re as _re

        def _expected_amt_for(_name, _loan_type):
            try:
                _nm = str(_name or "").strip()
            except Exception:
                _nm = ""
            if not _nm:
                return 0.0
            try:
                _row = self.db.get_client_info(_nm, loan_type=_loan_type) or {}
            except Exception:
                _row = {}
            try:
                return float((_row or {}).get("payment_amount") or 0)
            except Exception:
                try:
                    return float(str((_row or {}).get("payment_amount") or "0").replace(",", "").strip() or 0)
                except Exception:
                    return 0.0

        def _resolve_expected_pair(_display_name):
            try:
                _disp = str(_display_name or "").strip()
            except Exception:
                _disp = ""
            if not _disp:
                return (0.0, 0.0)

            _base = _re.sub(r"\s*\([^)]*\)\s*$", "", _disp).strip()
            _is_7x7_only = bool(_re.search(r"\(\s*7x7\s*\)\s*$", _disp, _re.I))
            _sum_reg = 0.0
            _sum_7 = 0.0

            if getattr(self, "_route_payment_two_cols", False):
                if _is_7x7_only:
                    _sum_7 += _expected_amt_for(_base, "7x7")
                else:
                    _sum_reg += _expected_amt_for(_base, "Regular")
                    try:
                        _pair = route_link_map.get(str(_disp).lower(), None)
                        if not isinstance(_pair, dict):
                            _pair = route_link_map.get(str(_base).lower(), None)
                    except Exception:
                        _pair = None
                    _nm_7 = None
                    _is_true_link = False
                    if isinstance(_pair, dict):
                        try:
                            _is_true_link = bool(_pair.get("_linked"))
                        except Exception:
                            _is_true_link = False
                        if _is_true_link:
                            _nm_7 = str(_pair.get("7x7") or "").strip() or None
                    if not _nm_7:
                        try:
                            _reg_row = self.db.get_client_info(_disp, loan_type="Regular") or self.db.get_client_info(_base, loan_type="Regular") or {}
                            _pu = str((_reg_row or {}).get("person_uid") or "").strip()
                            if _pu:
                                for _r in (self.db.find_clients_by_person_uid(_pu) or []):
                                    _lt = str((_r or {}).get("loan_type") or "").strip().lower().replace(" ", "")
                                    if _lt in ("7x7", "7×7"):
                                        _nm_7 = str((_r or {}).get("name") or "").strip() or None
                                        if _nm_7:
                                            break
                        except Exception:
                            pass
                    if _nm_7:
                        _sum_7 += _expected_amt_for(_nm_7, "7x7")
            else:
                _lt = "7x7" if _is_7x7_only else self._mode_filter()
                try:
                    _lt_clean = str(_lt or "").strip().lower().replace(" ", "")
                except Exception:
                    _lt_clean = "regular"
                _sum = _expected_amt_for(_base, "7x7" if _lt_clean in ("7x7", "7×7") else "Regular")
                if _lt_clean in ("7x7", "7×7"):
                    _sum_7 += _sum
                else:
                    _sum_reg += _sum
            return (_sum_reg, _sum_7)

        def _closed_paid_amt_for(_name, _loan_type):
            """Paid amount for closed Collector Route copy. ADV markers do not count here.

            This uses the same lookup used when printing the paid amount in each route box,
            so the AREA TOTAL row matches what the collector sees in the payment columns.
            """
            try:
                if not bool(getattr(self, "_ledger_closed_copy_show_paid", False)):
                    return 0.0
            except Exception:
                return 0.0
            try:
                _nm = str(_name or "").strip()
            except Exception:
                _nm = ""
            if not _nm:
                return 0.0
            try:
                _nm = _re.sub(r"\s*\([^)]*\)\s*$", "", _nm).strip()
            except Exception:
                pass
            try:
                _lt_key = "7x7" if ("7x7" in str(_loan_type or "Regular").lower().replace(" ", "").replace("×", "x")) else "regular"
                _cache = getattr(self, "_ledger_closed_paid_cache", None)
                if isinstance(_cache, dict):
                    _v = _cache.get((_nm.lower(), _lt_key))
                    if _v is not None:
                        return round(float(_v or 0.0), 2)
            except Exception:
                pass
            try:
                _conn = getattr(getattr(self, "db", None), "conn", None)
                if _conn is None:
                    return 0.0
                _row = _conn.execute(
                    """SELECT COALESCE(SUM(COALESCE(payment,0)),0)
                          FROM transactions
                         WHERE date(date)=date(?)
                           AND UPPER(TRIM(name))=UPPER(TRIM(?))
                           AND (CASE WHEN LOWER(REPLACE(REPLACE(IFNULL(loan_type,'Regular'),' ',''),'×','x')) LIKE '%7x7%' THEN '7x7' ELSE 'regular' END)=?""",
                    (ledger_date, _nm, _lt_key),
                ).fetchone()
                return round(float((_row[0] if _row else 0.0) or 0.0), 2)
            except Exception:
                return 0.0

        def _resolve_closed_paid_pair(_display_name):
            try:
                _disp = str(_display_name or "").strip()
            except Exception:
                _disp = ""
            if not _disp:
                return (0.0, 0.0)
            _base = _re.sub(r"\s*\([^)]*\)\s*$", "", _disp).strip()
            _is_7x7_only = bool(_re.search(r"\(\s*7x7\s*\)\s*$", _disp, _re.I))
            _sum_reg = 0.0
            _sum_7 = 0.0

            if getattr(self, "_route_payment_two_cols", False):
                if _is_7x7_only:
                    _sum_7 += _closed_paid_amt_for(_base, "7x7")
                else:
                    _sum_reg += _closed_paid_amt_for(_base, "Regular")
                    try:
                        _pair = route_link_map.get(str(_disp).lower(), None)
                        if not isinstance(_pair, dict):
                            _pair = route_link_map.get(str(_base).lower(), None)
                    except Exception:
                        _pair = None
                    _nm_7 = None
                    _is_true_link = False
                    if isinstance(_pair, dict):
                        try:
                            _is_true_link = bool(_pair.get("_linked"))
                        except Exception:
                            _is_true_link = False
                        if _is_true_link:
                            _nm_7 = str(_pair.get("7x7") or "").strip() or None
                    if not _nm_7:
                        try:
                            _reg_row = self.db.get_client_info(_disp, loan_type="Regular") or self.db.get_client_info(_base, loan_type="Regular") or {}
                            _pu = str((_reg_row or {}).get("person_uid") or "").strip()
                            if _pu:
                                for _r in (self.db.find_clients_by_person_uid(_pu) or []):
                                    _lt = str((_r or {}).get("loan_type") or "").strip().lower().replace(" ", "").replace("×", "x")
                                    if "7x7" in _lt:
                                        _nm_7 = str((_r or {}).get("name") or "").strip() or None
                                        if _nm_7:
                                            break
                        except Exception:
                            pass
                    if _nm_7:
                        _sum_7 += _closed_paid_amt_for(_nm_7, "7x7")
            else:
                _lt = "7x7" if _is_7x7_only else self._mode_filter()
                _lt_clean = str(_lt or "Regular").strip().lower().replace(" ", "").replace("×", "x")
                if "7x7" in _lt_clean:
                    _sum_7 += _closed_paid_amt_for(_base, "7x7")
                else:
                    _sum_reg += _closed_paid_amt_for(_base, "Regular")
            return (_sum_reg, _sum_7)

        for _area_name in (area_keys or []):
            _er = 0.0
            _e7 = 0.0
            _paid_r = 0.0
            _paid_7 = 0.0
            for _disp_name in (by_area.get(_area_name) or []):
                _pr, _p7 = _resolve_expected_pair(_disp_name)
                _er += float(_pr or 0)
                _e7 += float(_p7 or 0)
                _cr, _c7 = _resolve_closed_paid_pair(_disp_name)
                _paid_r += float(_cr or 0)
                _paid_7 += float(_c7 or 0)
            area_expected_map[_area_name if _area_name else "UNASSIGNED"] = {
                "reg": _er,
                "7x7": _e7,
                "all": float(_er) + float(_e7),
                "paid_reg": _paid_r,
                "paid_7x7": _paid_7,
                "paid_all": float(_paid_r) + float(_paid_7),
            }
    except Exception:
        area_expected_map = {}

    # --- Collector Route: Dashboard completion labels per client ---
    # Shows only [90%], [75%], and [COMPLETE] directly under the client name.
    # Linked 7x7 accounts are looked up through the linked Regular name when possible.
    area_dashboard_map = {}  # kept for backward compatibility; no bottom-area list is printed.
    route_dashboard_client_map = {}
    try:
        _is_collector_route_print = bool(getattr(self, "_ledger_forced_collector_name", "") or getattr(self, "_route_payment_two_cols", False))
    except Exception:
        _is_collector_route_print = False

    if _is_collector_route_print:
        try:
            def _dash_norm_name(_v):
                try:
                    return " ".join(str(_v or "").split()).strip().lower()
                except Exception:
                    return str(_v or "").strip().lower()

            def _dash_norm_lt(_v):
                try:
                    _s = str(_v or "Regular").strip().lower().replace(" ", "").replace("×", "x")
                except Exception:
                    _s = "regular"
                return "7x7" if _s == "7x7" or "7x7" in _s else "Regular"

            def _dash_fmt_money_short(_v):
                try:
                    _n = float(_v or 0)
                except Exception:
                    _n = 0.0
                try:
                    if abs(_n - int(_n)) < 0.005:
                        return f"{int(_n):,}"
                except Exception:
                    pass
                return f"{_n:,.2f}"

            _dash_rows = []
            try:
                _dash_rows = list(self._dashboard_fetch_rows() or []) if hasattr(self, "_dashboard_fetch_rows") else list(_spina_dashboard_fetch_rows(self) or [])
            except Exception:
                try:
                    _dash_rows = list(getattr(self, "_dashboard_rows", []) or [])
                except Exception:
                    _dash_rows = []

            _status_rank = {"Finishing Now": 1, "Near Completion": 2, "Complete": 3}
            _status_label = {"Finishing Now": "[90%]", "Near Completion": "[75%]", "Complete": "[COMPLETE]"}

            def _dash_put(_name, _lt, _entry):
                try:
                    _nk = _dash_norm_name(_name)
                    _ltk = _dash_norm_lt(_lt)
                    if not _nk:
                        return
                    _old = route_dashboard_client_map.get((_nk, _ltk))
                    if (not isinstance(_old, dict)) or (int(_entry.get("rank", 9)) < int(_old.get("rank", 9))):
                        route_dashboard_client_map[(_nk, _ltk)] = _entry
                except Exception:
                    pass

            for _dr in (_dash_rows or []):
                try:
                    _st = str((_dr or {}).get("status") or "")
                    if _st not in _status_rank:
                        continue
                    _nm = str((_dr or {}).get("name") or "").strip()
                    _lt = _dash_norm_lt((_dr or {}).get("loan_type") or "Regular")
                    if not _nm:
                        continue
                    _rem = 0.0
                    try:
                        _rem = float((_dr or {}).get("remaining") or 0.0)
                    except Exception:
                        _rem = 0.0

                    # Match the Collector Route balance to the Generate Report PDF balance.
                    # This avoids the route/dashboard showing a different remaining amount.
                    try:
                        if '_spina_route_balance_like_generate_report' in globals():
                            _report_rem = _spina_route_balance_like_generate_report(self, _nm, _lt, ledger_date)
                            if _report_rem is not None:
                                _rem = round(max(0.0, float(_report_rem or 0.0)), 2)
                        # If the report-based balance is zero, show complete.
                        # If a dashboard row says Complete but the report still has balance, keep it visible as 90%.
                        if _rem <= 0.004:
                            _st = "Complete"
                        elif _st == "Complete":
                            _st = "Finishing Now"
                    except Exception as __spina_exc:
                        try:
                            _log_suppressed_once("route_report_based_balance", "collector route report-based balance failed", __spina_exc)
                        except Exception:
                            pass

                    _prefix = "7x7" if _lt == "7x7" else "REG"
                    # Store status + balance in ONE wrapped dashboard line.
                    # This keeps the balance tied to the status, but wraps instead of clipping.
                    if _st == "Complete":
                        _badge_text = f"{_prefix} COMPLETE - ASK RENEW"
                    elif _st == "Finishing Now":
                        _badge_text = f"{_prefix} 90%"
                        if _rem > 0:
                            _badge_text += f" - BAL {_dash_fmt_money_short(_rem)}"
                    else:
                        _badge_text = f"{_prefix} 75%"
                        if _rem > 0:
                            _badge_text += f" - BAL {_dash_fmt_money_short(_rem)}"
                    _line = f"__DASH_BADGE__|{_st}|{_badge_text}"
                    _entry = {
                        "rank": _status_rank.get(_st, 9),
                        "line": _line,
                        "principal": float((_dr or {}).get("principal") or 0.0),
                    }
                    _dash_put(_nm, _lt, _entry)
                except Exception:
                    continue
        except Exception as __spina_exc:
            route_dashboard_client_map = {}
            try:
                _log_suppressed_once("route_dashboard_client_labels", "route dashboard client labels failed", __spina_exc)
            except Exception:
                pass

    # --- Output path ---
    # Use the global PDF_DIR if available; otherwise pick a safe writable folder.
    out_dir = None
    try:
        _forced_out_dir = getattr(self, "_ledger_forced_output_dir", None)
    except Exception:
        _forced_out_dir = None
    if _forced_out_dir:
        out_dir = str(_forced_out_dir)
    else:
        try:
            out_dir = globals().get("PDF_DIR", None)
        except Exception:
            out_dir = None
    if not out_dir:
        # Prefer DATA_DIR so generated files stay alongside other app data.
        try:
            out_dir = data_path("reports")
        except Exception:
            out_dir = os.path.join(APP_DIR, "reports")
    try:
        out_dir = _pick_writable_dir([
            out_dir,
            os.path.join(DATA_DIR, "reports"),
            os.path.join(APP_DIR, "reports"),
            os.path.join(os.path.expanduser("~"), "Documents", "Spina_Reports"),
        ], fallback=os.path.join(APP_DIR, "reports"))
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_0486', 'suppressed exception excpass_0486', __spina_exc)
        pass
    try:
        os.makedirs(out_dir, exist_ok=True)
    except Exception:
        try:
            import tempfile
            out_dir = os.path.join(tempfile.gettempdir(), "Spina_Reports")
            os.makedirs(out_dir, exist_ok=True)
        except Exception:
            # Last resort: current folder (may still fail on locked locations)
            out_dir = os.path.join(APP_DIR, "reports")
            try:
                os.makedirs(out_dir, exist_ok=True)
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_0487', 'suppressed exception excpass_0487', __spina_exc)
                pass
    # Keep global PDF_DIR updated (best-effort)
    try:
        globals()["PDF_DIR"] = out_dir
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_0488', 'suppressed exception excpass_0488', __spina_exc)
        pass

    # If this is a Collector Route print, include the collector name in the filename
    try:
        _collector_tag = getattr(self, "_ledger_forced_collector_name", "") or ""
    except Exception:
        _collector_tag = ""
    if _collector_tag:
        _safe_tag = _safe_filename_component(_collector_tag, fallback='Collector')
        out_path = os.path.join(out_dir, f"CollectorRoute_{_safe_tag}_{ledger_date}.pdf")
    else:
        out_path = os.path.join(out_dir, f"FullDailyLedger_{ledger_date}.pdf")

    # --- Fonts & helpers ---
    try:
        _ = _PDF_FONT_BASE
    except NameError:
        _PDF_FONT_BASE = "Helvetica"
    try:
        _ = _PDF_FONT_BOLD
    except NameError:
        _PDF_FONT_BOLD = "Helvetica-Bold"
    try:
        _safe = _safe_string
    except NameError:
        _safe = lambda s: ("" if s is None else str(s))

    c = _cv.Canvas(out_path, pagesize=page_size)
    margin_top = 44
    margin_side = 28
    margin_bottom = 30
    inner_w = width - (margin_side * 2)
    inner_h = height - (margin_top + margin_bottom)
    table_w = inner_w / 3.0
    idx_w = 18
    pay_w = 56
    name_w = table_w - idx_w - pay_w - 8

    # If printing a collector route, make the Payment column a bit wider
    try:
        _is_route = bool(getattr(self, "_route_payment_two_cols", False) or getattr(self, "_ledger_forced_collector_name", ""))
    except Exception:
        _is_route = False
    if _is_route:
        pay_w = pay_w + 12  # widen payment by ~12pt
        name_w = table_w - idx_w - pay_w - 8  # keep total width constant
        row_h = 14
    rows_per_col = max(1, int((inner_h - 110) // row_h))

    def _wrap_text_to_width(text, max_w, font_name=_PDF_FONT_BASE, font_size=9.5):
        s = (text or "").strip()
        if not s:
            return [""]
        words, lines, cur = s.split(), [], ""
        def _fits(t): return stringWidth(t, font_name, font_size) <= max_w
        for w in words:
            trial = (cur + " " + w).strip()
            if _fits(trial):
                cur = trial
            else:
                if cur:
                    lines.append(cur)
                if not _fits(w):
                    acc = ""
                    for ch in w:
                        if _fits(acc + ch):
                            acc += ch
                        else:
                            if acc:
                                lines.append(acc)
                            acc = ch
                    cur = acc
                else:
                    cur = w
        if cur:
            lines.append(cur)
        return lines

    def _draw_page_number():
        try:
            c.setFont(_PDF_FONT_BASE, 9)
            c.drawRightString(width - margin_side, margin_bottom - 10, f"Page {c.getPageNumber()}")
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0489', 'suppressed exception excpass_0489', __spina_exc)
            pass

    def _draw_final_footer():
        try:
            c.setFont(_PDF_FONT_BASE, 10)
            # If this is a Collectors route print, show Total Payment line; otherwise show signature line
            try:
                _collector_name = getattr(self, "_ledger_forced_collector_name", "") or ""
            except Exception:
                _collector_name = ""
            if _collector_name:
                footer_txt = "Total Payment ______________________"
            else:
                footer_txt = "Written by: __________    Date: __________    Encoded by: __________    Date: __________"
            c.drawString(margin_side, margin_bottom - 24, _safe(footer_txt))
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0490', 'suppressed exception excpass_0490', __spina_exc)
            pass
    def _draw_global_header():
        y = height - margin_top + 6
        try:
            _collector_name = getattr(self, "_ledger_forced_collector_name", "") or ""
        except Exception:
            _collector_name = ""

        if not _collector_name:
            # --- Clients tab header ---
            c.setFont(_PDF_FONT_BOLD, 16)
            c.drawCentredString(width/2, y, _safe("SPINA."))
            y -= 20
            c.setFont(_PDF_FONT_BOLD, 14)
            try:
                disp_date = datetime.strptime(ledger_date, "%Y-%m-%d").strftime("%B %d, %Y")
            except Exception:
                disp_date = ledger_date
            c.drawCentredString(width/2, y, _safe("DAILY COLLECTION LEDGER - " + str(disp_date)))
            y -= 6
        else:
            # --- Collectors tab header ---
            c.setFont(_PDF_FONT_BOLD, 14)
            c.drawCentredString(width/2, y, _safe("DAILY COLLECTION LEDGER"))
            y -= 18
            c.setFont(_PDF_FONT_BASE, 12)
            # Left: Collector
            c.drawString(margin_side, y, _safe("Collector: " + str(_collector_name)))
            # Right: Date
            try:
                disp_date = datetime.strptime(ledger_date, "%Y-%m-%d").strftime("%B %d, %Y")
            except Exception:
                disp_date = ledger_date
            right_label = _safe("Date: " + str(disp_date))
            tw = stringWidth(str(right_label), _PDF_FONT_BASE, 12)
            c.drawString(width - margin_side - tw, y, str(right_label))
            y -= 6

        # underline for header
        try:
            c.setLineWidth(0.6)
            c.line(margin_side, y+6, width - margin_side, y+6)
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0491', 'suppressed exception excpass_0491', __spina_exc)
            pass

        return y - 28
    flat_rows = []
    for area_name in area_keys:
        items = [ {"name": n} for n in by_area.get(area_name, []) ]
        total = len(items)
        area_label = area_name if area_name else "UNASSIGNED"
        flat_rows.append(("__AREA__", area_label, total))
        for r in items:
            flat_rows.append(("__CLIENT__", r["name"], None))
        # Add an area total line with expected subtotal info
        flat_rows.append(("__AREA_TOTAL__", area_label, area_expected_map.get(area_label, {"reg": 0.0, "7x7": 0.0, "all": 0.0})))
    y_after = _draw_global_header()
    col_left = [margin_side + i * table_w for i in range(3)]
    col_top = y_after - 8
    col_bottom = margin_bottom

    line_h = 12.0
    cell_pad_x = 2.0
    cell_pad_y = 2.0
    def new_page_headers():
        c.setFont(_PDF_FONT_BOLD, 9.5)
        for i in range(3):
            x0 = col_left[i]
            c.drawString(x0 + cell_pad_x, col_top, "#")
            c.drawString(x0 + idx_w + cell_pad_x, col_top, _safe("Client Name"))

            # Payment header: single column (normal) OR split (Regular | 7x7) for Collector Route prints
            if getattr(self, "_route_payment_two_cols", False):
                _x_pay_left  = x0 + idx_w + name_w
                _x_pay_right = x0 + idx_w + name_w + pay_w - cell_pad_x
                _x_mid = _x_pay_left + (_x_pay_right - _x_pay_left) / 2.0

                c.setFont(_PDF_FONT_BOLD, 8.5)
                c.drawCentredString(_x_pay_left + (_x_mid - _x_pay_left) / 2.0, col_top, _safe("Regular"))
                c.drawCentredString(_x_mid + (_x_pay_right - _x_mid) / 2.0, col_top, _safe("7x7"))

                # divider inside the header cell
                try:
                    c.setLineWidth(0.5)
                    c.line(_x_mid, col_top + 10, _x_mid, col_top - 8)
                except Exception as __spina_exc:
                    _log_suppressed_once('excpass_0492', 'suppressed exception excpass_0492', __spina_exc)
                    pass

                c.setFont(_PDF_FONT_BOLD, 9.5)
            else:
                c.drawRightString(x0 + idx_w + name_w + pay_w - cell_pad_x, col_top, _safe("Payment"))

            c.setLineWidth(0.6)
            c.line(x0, col_top - 2.5, x0 + table_w - 6, col_top - 2.5)

    new_page_headers()
    y_cursor = col_top - 10
    col_idx = 0

    def ensure_space(h_required):
        nonlocal y_cursor, col_idx, col_top
        if y_cursor - h_required < col_bottom:
            col_idx += 1
            if col_idx >= 3:
                _draw_page_number()
                # Page number is enough on intermediate pages; the final totals footer
                # is drawn only on the last page.
                c.showPage()
                # Compact top for subsequent pages in Collectors print
                try:
                    _collector_name = getattr(self, "_ledger_forced_collector_name", "") or ""
                except Exception:
                    _collector_name = ""
                if _collector_name:
                    # Start columns closer to the top (skip big global header)
                    col_top = height - margin_top + 6 - 2
                new_page_headers()
                col_idx = 0
            y_cursor = col_top - 10

    local_index = 0

    for kind, text, tcount in flat_rows:
        if kind == "__AREA__":
            local_index = 0
            ma, su = split_area_main_sub(text)
            if su:
                label = f"AREA: {ma} | {su} - {tcount} clients"
            else:
                label = f"AREA: {ma} - {tcount} clients"
            avail_w = table_w - 6 - 2*cell_pad_x
            lines_lbl = _wrap_text_to_width(label, avail_w, _PDF_FONT_BOLD, 10.5)
            h = len(lines_lbl) * line_h + cell_pad_y * 2
            ensure_space(h)

            # Soft pink band (no colors.HexColor dependency)
            c.saveState()
            try:
                c.setFillColorRGB(1.0, 0.89, 0.94)  # ~#FFE3F0
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_0494', 'suppressed exception excpass_0494', __spina_exc)
                pass
            c.rect(col_left[col_idx], y_cursor - h, table_w - 6, h, stroke=0, fill=1)
            c.restoreState()

            x0 = col_left[col_idx]
            c.setLineWidth(0.4)
            # Light-green fill for NEW clients
            # Light-green fill for NEW clients (uses new_until or created_at+days; respects ledger_date)
            try:
                if self._is_client_new(text, ledger_date, highlight_days):
                    c.saveState()
                    try:
                        c.setFillColorRGB(0.88, 1.0, 0.88)
                    except Exception as __spina_exc:
                        _log_suppressed_once('excpass_0495', 'suppressed exception excpass_0495', __spina_exc)
                        pass
                    c.rect(x0, y_cursor - h, table_w - 6, h, stroke=0, fill=1)
                    c.restoreState()
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_0496', 'suppressed exception excpass_0496', __spina_exc)
                pass
            c.rect(x0, y_cursor - h, table_w - 6, h, stroke=1, fill=0)
            c.setFont(_PDF_FONT_BOLD, 10.5)
            base_y = y_cursor - cell_pad_y - (line_h - 2)
            for i, ln in enumerate(lines_lbl):
                c.drawString(x0 + cell_pad_x, base_y - i * line_h, _safe(ln))
            y_cursor -= h
            continue

        if kind == "__AREA_TOTAL__":
            # --- Area total row ---
            # Normal route: expected total + writable payment line.
            # Closed route copy: show an AREA payment summary and the paid total,
            # using the same paid amounts printed inside the route payment boxes.
            label = "TOTAL"
            try:
                _closed_total_mode = bool(getattr(self, "_ledger_closed_copy_show_paid", False))
            except Exception:
                _closed_total_mode = False

            # Keep the route page compact. Detailed closed-payment summaries are printed
            # on a separate summary page at the end of the PDF.
            h = (2 * line_h) + (cell_pad_y * 2)
            ensure_space(h)
            x0 = col_left[col_idx]

            try:
                c.saveState()
                try:
                    c.setFillColorRGB(0.95, 0.95, 0.95)
                except Exception as __spina_exc:
                    _log_suppressed_once('excpass_0494b', 'suppressed exception excpass_0494b', __spina_exc)
                    pass
                c.rect(x0, y_cursor - h, table_w - 6, h, stroke=0, fill=1)
                c.restoreState()
            except Exception:
                pass

            c.setLineWidth(0.4)
            c.rect(x0, y_cursor - h, table_w - 6, h, stroke=1, fill=0)
            c.line(x0 + idx_w, y_cursor - h, x0 + idx_w, y_cursor)
            c.line(x0 + idx_w + name_w, y_cursor - h, x0 + idx_w + name_w, y_cursor)

            _x_pay_left  = x0 + idx_w + name_w
            _x_pay_right = x0 + (table_w - 6)

            # Expected and paid totals for this specific AREA.
            _exp_all = 0.0
            _paid_reg = 0.0
            _paid_7 = 0.0
            _paid_all = 0.0
            try:
                if isinstance(tcount, dict):
                    _exp_all = float(tcount.get('all') or 0)
                    _paid_reg = float(tcount.get('paid_reg') or 0)
                    _paid_7 = float(tcount.get('paid_7x7') or 0)
                    _paid_all = float(tcount.get('paid_all') or 0)
                elif tcount is not None:
                    _exp_all = float(tcount or 0)
            except Exception:
                try:
                    _exp_all = float(str(tcount or '0').replace(',', '').strip() or 0)
                except Exception:
                    _exp_all = 0.0

            def _fmt_total_money(_v):
                try:
                    _n = float(_v or 0)
                except Exception:
                    _n = 0.0
                try:
                    if abs(_n - int(_n)) < 0.005:
                        return f"{int(_n):,}"
                except Exception:
                    pass
                return f"{_n:,.2f}"

            # Left side: area-level payment summary.
            try:
                c.setFont(_PDF_FONT_BOLD, 10.0)
            except Exception:
                c.setFont(_PDF_FONT_BOLD, 10.0)
            _ty = y_cursor - cell_pad_y - (line_h - 2)
            c.drawString(x0 + idx_w + cell_pad_x, _ty, _safe(label))

            try:
                _left_x = x0 + idx_w + cell_pad_x + 10
                _line_y = _ty - 9.0
                c.setFont(_PDF_FONT_BASE, 8.0)
                c.drawString(_left_x, _line_y, _safe(f"Expected: {_fmt_total_money(_exp_all)}"))
                try:
                    c.setFont(_PDF_FONT_BOLD, 10.0)
                except Exception:
                    c.setFont(_PDF_FONT_BOLD, 10.0)
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_0494cx', 'suppressed exception excpass_0494cx', __spina_exc)
                pass

            # Payment column: big actual total payment for that area.
            # ADV markers are visual only and are not included unless an actual payment exists.
            try:
                if _closed_total_mode:
                    _total_txt = _fmt_total_money(_paid_all) if abs(float(_paid_all or 0.0)) >= 0.005 else "0"
                    _font_t = _PDF_FONT_BOLD
                    _size_t = 13.0
                    _max_w_t = max(12.0, (_x_pay_right - _x_pay_left) - 8.0)
                    try:
                        while _size_t > 8.5 and c.stringWidth(_safe(_total_txt), _font_t, _size_t) > _max_w_t:
                            _size_t -= 0.25
                    except Exception:
                        pass
                    _mid_x_t = (_x_pay_left + _x_pay_right) / 2.0
                    _mid_y_t = (y_cursor - h) + (h / 2.0)
                    _base_t = _mid_y_t - (_size_t * 0.32)
                    c.saveState()
                    c.setFont(_font_t, _size_t)
                    c.setFillColorRGB(0, 0, 0)
                    c.drawCentredString(_mid_x_t, _base_t, _safe(_total_txt))
                    c.restoreState()
                else:
                    y_line = (y_cursor - h) + cell_pad_y + line_h
                    c.setLineWidth(1.0)
                    c.line(_x_pay_left + 3, y_line, _x_pay_right - 3, y_line)
                    c.setLineWidth(0.4)
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_0494c', 'suppressed exception excpass_0494c', __spina_exc)
                pass

            y_cursor -= h
            continue


        # Client row
        def _fmt_pay_amount(_v):
            try:
                _n = float(_v or 0)
            except Exception:
                return ""
            try:
                if abs(_n - int(_n)) < 0.005:
                    return f"{int(_n):,}"
            except Exception:
                pass
            return f"{_n:,.2f}"

        def _norm_pay_term(_v):
            try:
                _s = str(_v or "").strip().title()
            except Exception:
                _s = ""
            return _s or "Daily"

        def _pay_meta_for(_name, _loan_type):
            try:
                _nm = str(_name or "").strip()
            except Exception:
                _nm = ""
            if not _nm:
                return ""
            try:
                _row = self.db.get_client_info(_nm, loan_type=_loan_type) or {}
            except Exception:
                _row = {}
            if not isinstance(_row, dict) or not _row:
                return ""
            _term = _norm_pay_term(_row.get("payment_term") or "Daily")
            _amt = _fmt_pay_amount(_row.get("payment_amount") or 0)
            try:
                _mode_raw = str(_row.get("payment_mode") or "").strip()
            except Exception:
                _mode_raw = ""
            _mode_key = _mode_raw.lower().replace(" ", "")
            if _mode_key == "gcash":
                _mode = "GCASH"
            elif _mode_key == "atm":
                _mode = "ATM"
            elif _mode_key == "cash":
                _mode = "Cash"
            else:
                _mode = _mode_raw
            _parts = []
            if _amt:
                _parts.append(f"{_term} {_amt}")
            elif _term:
                _parts.append(_term)
            if _mode:
                _parts.append(_mode)
            return " - ".join([p for p in _parts if str(p or "").strip()])

        _display_name = str(text or "")
        _meta_lines_src = []
        _meta_group_break_idx = None
        try:
            import re as _re
            _base_name = _re.sub(r"\s*\([^)]*\)\s*$", "", str(text or "")).strip()
            _is_7x7_only = bool(_re.search(r"\(\s*7x7\s*\)\s*$", str(text or ""), _re.I))
            if _is_7x7_only:
                _display_name = _base_name
            if getattr(self, "_route_payment_two_cols", False):
                _meta_reg = ""
                _meta_7x7 = ""
                if _is_7x7_only:
                    _meta_7x7 = _pay_meta_for(_base_name, "7x7")
                else:
                    _meta_reg = _pay_meta_for(_base_name, "Regular")
                    try:
                        _pair = route_link_map.get(str(str(text or "").strip()).lower(), None)
                        if not isinstance(_pair, dict):
                            _pair = route_link_map.get(str(_base_name).lower(), None)
                    except Exception:
                        _pair = None
                    _nm_7 = _pair.get("7x7") if isinstance(_pair, dict) else None
                    if _nm_7 and str(_nm_7).strip().lower() != str(_base_name).strip().lower():
                        _meta_7x7 = _pay_meta_for(_nm_7, "7x7")
                    if not _meta_7x7:
                        try:
                            _reg_row = self.db.get_client_info(str(text or "").strip(), loan_type="Regular") or self.db.get_client_info(_base_name, loan_type="Regular") or {}
                            _pu = str((_reg_row or {}).get("person_uid") or "").strip()
                            if _pu:
                                for _r in (self.db.find_clients_by_person_uid(_pu) or []):
                                    _lt = str((_r or {}).get("loan_type") or "").strip().lower().replace(" ", "")
                                    if _lt in ("7x7", "7×7"):
                                        _meta_7x7 = _pay_meta_for((_r or {}).get("name") or "", "7x7")
                                        if _meta_7x7:
                                            break
                        except Exception:
                            pass
                if _meta_7x7:
                    if _meta_reg:
                        _meta_lines_src.append(f"REG {_meta_reg}")
                    _meta_lines_src.append(f"7x7 {_meta_7x7}")
                elif _meta_reg:
                    _meta_lines_src.append(_meta_reg)
            else:
                _lt = "7x7" if (_is_7x7_only or str(self._mode_filter() or "Regular").lower().replace(" ", "") in ("7x7", "7×7")) else "Regular"
                _meta = _pay_meta_for(_base_name, _lt)
                if _meta:
                    if _is_7x7_only and not str(_meta).lower().startswith("7x7 "):
                        _meta = f"7x7 {_meta}"
                    _meta_lines_src.append(_meta)
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0496pm', 'suppressed exception excpass_0496pm', __spina_exc)
            _display_name = str(text or "")
            _meta_lines_src = []

        # Canonical client name used by payment/ADV lookups below.
        try:
            lookup_name = str(_base_name or _display_name or text or "").strip()
        except Exception:
            lookup_name = str(text or "").strip()

        _due_today_badge = False
        try:
            def _route_due_today(_name, _loan_type, _ledger_date_s):
                try:
                    _row = self.db.get_client_info(_name, loan_type=_loan_type) or {}
                except Exception:
                    _row = {}
                if not isinstance(_row, dict) or not _row:
                    return False
                try:
                    _term = str(_row.get('payment_term') or '').strip().title()
                except Exception:
                    _term = ''
                try:
                    if str(_row.get('flex_due_rule') or '').strip():
                        _lbl, _is_due = _spina__client_due_meta(_row, as_of=_ledger_date_s)
                        return bool(_is_due)
                except Exception:
                    pass
                if _term not in ('Weekly', 'Semi', 'Monthly'):
                    return False
                try:
                    _lbl, _is_due = _spina__client_due_meta(_row, as_of=_ledger_date_s)
                    return bool(_is_due)
                except Exception:
                    return False

            _due_loan_type = '7x7' if _is_7x7_only else 'Regular'
            _due_today_badge = bool(_route_due_today(_base_name or _display_name, _due_loan_type, ledger_date))
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0496due', 'suppressed exception excpass_0496due', __spina_exc)
            _due_today_badge = False

        # Add Dashboard completion status directly under the client name.
        try:
            def _route_dash_norm_name(_v):
                try:
                    return " ".join(str(_v or "").split()).strip().lower()
                except Exception:
                    return str(_v or "").strip().lower()

            def _route_dash_norm_lt(_v):
                try:
                    _s = str(_v or "Regular").strip().lower().replace(" ", "").replace("×", "x")
                except Exception:
                    _s = "regular"
                return "7x7" if _s == "7x7" or "7x7" in _s else "Regular"

            def _route_dash_lookup(_name, _lt):
                try:
                    _entry = route_dashboard_client_map.get((_route_dash_norm_name(_name), _route_dash_norm_lt(_lt)))
                    if isinstance(_entry, dict):
                        return str(_entry.get("line") or "").strip()
                    return str(_entry or "").strip()
                except Exception:
                    return ""

            _dash_status_lines = []
            _dash_status_seen = set()

            def _route_dash_add(_name, _lt):
                try:
                    _ln = _route_dash_lookup(_name, _lt)
                    _key = (_route_dash_norm_name(_name), _route_dash_norm_lt(_lt), _ln)
                    if _ln and _key not in _dash_status_seen:
                        _dash_status_seen.add(_key)
                        _dash_status_lines.append(_ln)
                except Exception:
                    pass

            if _is_route_print and route_dashboard_client_map:
                import re as _re_dash
                _dash_raw = str(text or "").strip()
                _dash_base = _re_dash.sub(r"\s*\([^)]*\)\s*$", "", _dash_raw).strip()
                _dash_is_7x7 = bool(_re_dash.search(r"\(\s*7x7\s*\)\s*$", _dash_raw, _re_dash.I))
                if _dash_base:
                    if getattr(self, "_route_payment_two_cols", False):
                        if _dash_is_7x7:
                            _route_dash_add(_dash_base, "7x7")
                        else:
                            _route_dash_add(_dash_base, "Regular")
                            _dash_7_name = ""
                            try:
                                _dash_pair = route_link_map.get(_route_dash_norm_name(_dash_raw), None)
                                if not isinstance(_dash_pair, dict):
                                    _dash_pair = route_link_map.get(_route_dash_norm_name(_dash_base), None)
                                if isinstance(_dash_pair, dict):
                                    _dash_7_name = str(_dash_pair.get("7x7") or "").strip()
                            except Exception:
                                _dash_7_name = ""
                            if not _dash_7_name:
                                try:
                                    _dash_reg_row = self.db.get_client_info(_dash_raw, loan_type="Regular") or self.db.get_client_info(_dash_base, loan_type="Regular") or {}
                                    _dash_pu = str((_dash_reg_row or {}).get("person_uid") or "").strip()
                                    if _dash_pu:
                                        for _dash_r in (self.db.find_clients_by_person_uid(_dash_pu) or []):
                                            _dash_lt = str((_dash_r or {}).get("loan_type") or "").strip().lower().replace(" ", "").replace("×", "x")
                                            if _dash_lt == "7x7" or "7x7" in _dash_lt:
                                                _dash_7_name = str((_dash_r or {}).get("name") or "").strip()
                                                if _dash_7_name:
                                                    break
                                except Exception:
                                    pass
                            if _dash_7_name:
                                _route_dash_add(_dash_7_name, "7x7")
                    else:
                        _dash_lt = "7x7" if (_dash_is_7x7 or str(self._mode_filter() or "Regular").lower().replace(" ", "").replace("×", "x") == "7x7") else "Regular"
                        _route_dash_add(_dash_base, _dash_lt)
            if _dash_status_lines:
                _meta_lines_src = list(_dash_status_lines) + list(_meta_lines_src or [])
        except Exception as __spina_exc:
            try:
                _log_suppressed_once("route_dashboard_under_name", "route dashboard under-name labels failed", __spina_exc)
            except Exception:
                pass
        # Add route notes imported from the Encoder.
        # v30 fix:
        # - Use the ACTIVE print_full_daily_ledger block, not the older inactive copy.
        # - Notes are fetched more strongly by name, uid/person_uid, and linked Regular/7x7 pair.
        # - Same REG + 7x7 note is printed once only.
        # - If exact route date has no notice, also checks the next-day notice bucket so
        #   "tomorrow notes" entered today can still show on the collector route print.
        try:
            if _is_route_print and ("_spina_route_notice_for_client" in globals()):
                _notice_lines = []
                _seen_notice_texts = set()
                _seen_notice_lines = set()

                def _notice_norm(_v):
                    try:
                        return " ".join(str(_v or "").split()).strip().lower()
                    except Exception:
                        return str(_v or "").strip().lower()

                def _notice_norm_name(_v):
                    try:
                        if "_spina_route_notice_norm_name" in globals():
                            return _spina_route_notice_norm_name(_v)
                    except Exception:
                        pass
                    try:
                        import re as _re_notice
                        _s = str(_v or "").strip().lower()
                        _s = _re_notice.sub(r"\s+", " ", _s)
                        _s = _re_notice.sub(r"\s*\([^)]*\)\s*$", "", _s).strip()
                        return _s
                    except Exception:
                        return str(_v or "").strip().lower()

                def _notice_norm_lt(_v):
                    try:
                        if "_spina_route_notice_norm_lt" in globals():
                            return _spina_route_notice_norm_lt(_v)
                    except Exception:
                        pass
                    try:
                        _s = str(_v or "Regular").strip().lower().replace(" ", "").replace("×", "x")
                        return "7x7" if "7x7" in _s else "Regular"
                    except Exception:
                        return "Regular"

                def _notice_day_candidates(_day):
                    _days = []
                    try:
                        _d0 = str(_day or "").strip()[:10]
                        if _d0:
                            _days.append(_d0)
                            try:
                                from datetime import datetime as _dt_notice, timedelta as _td_notice
                                _d1 = (_dt_notice.strptime(_d0, "%Y-%m-%d").date() + _td_notice(days=1)).strftime("%Y-%m-%d")
                                # Fallback only. If exact date has a note, it wins.
                                if _d1 not in _days:
                                    _days.append(_d1)
                            except Exception:
                                pass
                    except Exception:
                        pass
                    return _days

                def _candidate_names_for_notice(_nm, _lt):
                    _names = []
                    def _add_name(_x):
                        _x = str(_x or "").strip()
                        if _x and _notice_norm_name(_x) not in {_notice_norm_name(n) for n in _names}:
                            _names.append(_x)

                    _add_name(_nm)
                    try:
                        import re as _re_notice
                        _add_name(_re_notice.sub(r"\s*\([^)]*\)\s*$", "", str(_nm or "")).strip())
                    except Exception:
                        pass

                    try:
                        _info = self.db.get_client_info(str(_nm or "").strip(), loan_type=_notice_norm_lt(_lt)) or {}
                        _pu = str((_info or {}).get("person_uid") or "").strip()
                        if _pu and hasattr(self.db, "find_clients_by_person_uid"):
                            for _r in (self.db.find_clients_by_person_uid(_pu) or []):
                                try:
                                    _rlt = _notice_norm_lt((_r or {}).get("loan_type"))
                                    if _rlt == _notice_norm_lt(_lt):
                                        _add_name((_r or {}).get("name") or "")
                                except Exception:
                                    pass
                    except Exception:
                        pass

                    return _names

                def _lookup_notice_direct(_names, _lt, _day):
                    try:
                        if "_spina_route_notice_load" not in globals():
                            return ""
                        _data = _spina_route_notice_load()
                        _bucket = _data.get(str(_day or "").strip()[:10])
                        if not isinstance(_bucket, dict):
                            return ""
                        _lt_norm = _notice_norm_lt(_lt)
                        _name_norms = {_notice_norm_name(_n) for _n in (_names or []) if _notice_norm_name(_n)}

                        # Try by key first.
                        try:
                            for _n in (_names or []):
                                if "_spina_route_notice_key" in globals():
                                    _rec = _bucket.get(_spina_route_notice_key(_n, _lt_norm, ""))
                                    if isinstance(_rec, dict) and str(_rec.get("notice") or "").strip():
                                        return str(_rec.get("notice") or "").strip()
                        except Exception:
                            pass

                        # Then scan bucket records.
                        for _k, _rec in _bucket.items():
                            try:
                                if not isinstance(_rec, dict):
                                    continue
                                if _notice_norm_lt(_rec.get("loan_type")) != _lt_norm:
                                    continue
                                _rec_names = {
                                    _notice_norm_name(_rec.get("client")),
                                    _notice_norm_name(_rec.get("client_norm")),
                                }
                                if _name_norms.intersection({x for x in _rec_names if x}):
                                    return str(_rec.get("notice") or "").strip()
                            except Exception:
                                continue
                    except Exception:
                        return ""
                    return ""

                def _fetch_route_notice(_nm, _lt):
                    _lt_norm = _notice_norm_lt(_lt)
                    _names = _candidate_names_for_notice(_nm, _lt_norm)
                    for _day in _notice_day_candidates(ledger_date):
                        # Existing function first.
                        for _name in (_names or []):
                            try:
                                _txt = _spina_route_notice_for_client(self.db, _name, _lt_norm, _day)
                            except Exception:
                                _txt = ""
                            _txt = str(_txt or "").strip()
                            if _txt:
                                return _txt

                        # Strong direct fallback.
                        _txt = _lookup_notice_direct(_names, _lt_norm, _day)
                        if str(_txt or "").strip():
                            return str(_txt or "").strip()
                    return ""

                def _append_notice(_txt, _prefix=""):
                    _txt = str(_txt or "").strip()
                    if not _txt:
                        return

                    _text_key = _notice_norm(_txt)
                    if _text_key in _seen_notice_texts:
                        return

                    _prefix_txt = str(_prefix or "").strip()
                    if _prefix_txt.upper().startswith("REG"):
                        _label = "REG NOTE: "
                    elif _prefix_txt.lower().startswith("7x7"):
                        _label = "7x7 NOTE: "
                    else:
                        _label = "NOTE: "

                    _line_text = (_label + _txt).strip()
                    _line = "__ROUTE_NOTE__|" + _line_text
                    _line_key = _notice_norm(_line_text)

                    if _line_key in _seen_notice_lines:
                        return

                    _seen_notice_texts.add(_text_key)
                    _seen_notice_lines.add(_line_key)
                    _notice_lines.append(_line)

                if getattr(self, "_route_payment_two_cols", False):
                    if _is_7x7_only:
                        _append_notice(_fetch_route_notice(_base_name or _display_name, "7x7"))
                    else:
                        _reg_notice = _fetch_route_notice(_base_name or _display_name, "Regular")

                        _notice_7_name = ""
                        try:
                            _notice_pair = route_link_map.get(_notice_norm_name(str(text or "").strip()), None)
                            if not isinstance(_notice_pair, dict):
                                _notice_pair = route_link_map.get(_notice_norm_name(_base_name or ""), None)
                            if isinstance(_notice_pair, dict):
                                _notice_7_name = str(_notice_pair.get("7x7") or "").strip()
                        except Exception:
                            _notice_7_name = ""

                        if not _notice_7_name:
                            try:
                                _reg_row = self.db.get_client_info(_base_name or _display_name, loan_type="Regular") or {}
                                _pu = str((_reg_row or {}).get("person_uid") or "").strip()
                                if _pu and hasattr(self.db, "find_clients_by_person_uid"):
                                    for _rr in (self.db.find_clients_by_person_uid(_pu) or []):
                                        try:
                                            if _notice_norm_lt((_rr or {}).get("loan_type")) == "7x7":
                                                _notice_7_name = str((_rr or {}).get("name") or "").strip()
                                                if _notice_7_name:
                                                    break
                                        except Exception:
                                            pass
                            except Exception:
                                pass

                        if not _notice_7_name:
                            _notice_7_name = _base_name or _display_name

                        _seven_notice = _fetch_route_notice(_notice_7_name, "7x7")

                        if _reg_notice and _seven_notice:
                            if _notice_norm(_reg_notice) == _notice_norm(_seven_notice):
                                _append_notice(_reg_notice)
                            else:
                                _append_notice(_reg_notice, "REG ")
                                _append_notice(_seven_notice, "7x7 ")
                        elif _reg_notice:
                            _append_notice(_reg_notice)
                        elif _seven_notice:
                            _append_notice(_seven_notice)
                else:
                    _append_notice(_fetch_route_notice(_base_name or _display_name, _due_loan_type))

                if _notice_lines:
                    # Put route notes first so collectors see them immediately.
                    _meta_lines_src = list(_notice_lines) + list(_meta_lines_src or [])
        except Exception as __spina_exc:
            try:
                _log_suppressed_once('route_notice_pdf_lines', 'route notice PDF lines failed', __spina_exc)
            except Exception:
                pass

        name_lines = _wrap_text_to_width(_display_name, name_w - 2 * cell_pad_x, _PDF_FONT_BOLD, 9.5) or [str(_display_name or "")]
        meta_lines = []
        for _ix, _meta_src in enumerate(_meta_lines_src):
            # Dashboard status/balance stays together but WRAPS instead of being clipped.
            if str(_meta_src or "").startswith("__DASH_BADGE__|"):
                try:
                    _parts0 = str(_meta_src or "").split("|", 2)
                    _dash_status0 = _parts0[1] if len(_parts0) > 1 else ""
                    _dash_text0 = _parts0[2] if len(_parts0) > 2 else str(_meta_src or "").replace("__DASH_BADGE__|", "")
                except Exception:
                    _dash_status0 = ""
                    _dash_text0 = str(_meta_src or "").replace("__DASH_BADGE__|", "")
                _dash_width0 = max(38.0, name_w - (cell_pad_x * 2.0) - 9.0)
                _dash_parts0 = _wrap_text_to_width(_dash_text0, _dash_width0, _PDF_FONT_BOLD, 7.2) or [_dash_text0]
                if len(_dash_parts0) > 3:
                    _dash_parts0 = _dash_parts0[:3]
                    try:
                        _dash_parts0[-1] = str(_dash_parts0[-1]).rstrip(".") + "..."
                    except Exception:
                        pass
                for _dash_part0 in _dash_parts0:
                    meta_lines.append(f"__DASH_BADGE__|{_dash_status0}|{str(_dash_part0 or '').strip()}")
            elif str(_meta_src or "").startswith("__DASH_BALANCE__|"):
                # Backward compatibility for old cached/older lines: draw balance as a wrapped dashboard line.
                try:
                    _legacy_bal = str(_meta_src or "").split("|", 1)[1].strip()
                except Exception:
                    _legacy_bal = str(_meta_src or "").replace("__DASH_BALANCE__|", "").strip()
                _dash_width0 = max(38.0, name_w - (cell_pad_x * 2.0) - 9.0)
                for _dash_part0 in (_wrap_text_to_width(_legacy_bal, _dash_width0, _PDF_FONT_BOLD, 7.2) or [_legacy_bal]):
                    meta_lines.append(f"__DASH_BADGE__|Balance|{str(_dash_part0 or '').strip()}")
            elif str(_meta_src or "").startswith("__ROUTE_NOTE__|"):
                try:
                    _rn_txt = str(_meta_src or "").split("|", 1)[1].strip()
                except Exception:
                    _rn_txt = str(_meta_src or "").replace("__ROUTE_NOTE__|", "").strip()
                _rn_width = max(40.0, name_w - 2 * cell_pad_x - 9.0)
                _rn_parts = _wrap_text_to_width(_rn_txt, _rn_width, _PDF_FONT_BOLD, 7.8) or [_rn_txt]
                # Keep a practical cap so route rows stay compact, but do not hide the first part.
                if len(_rn_parts) > 4:
                    _rn_parts = _rn_parts[:4]
                    try:
                        _rn_parts[-1] = str(_rn_parts[-1]).rstrip(".") + "..."
                    except Exception:
                        pass
                for _rn_part in _rn_parts:
                    meta_lines.append("__ROUTE_NOTE__|" + str(_rn_part or ""))
            else:
                _wrapped_meta = _wrap_text_to_width(_meta_src, name_w - 2 * cell_pad_x, _PDF_FONT_BASE, 8.0) or [str(_meta_src or "")]
                meta_lines.extend(_wrapped_meta)
            if _ix == 0 and len(_meta_lines_src) > 1:
                _meta_group_break_idx = len(meta_lines)
        if _due_today_badge:
            meta_lines.append('__DUE_TODAY_BADGE__')
        n_name_lines = max(1, len(name_lines))
        n_meta_lines = len(meta_lines)
        try:
            _has_route_note_badge = any(str(_ln or "").startswith("__ROUTE_NOTE__|") for _ln in meta_lines)
        except Exception:
            _has_route_note_badge = False
        meta_line_h = 10.8 if _has_route_note_badge else 10.0
        meta_gap = 2.5 if n_meta_lines else 0.0
        h = (n_name_lines * line_h) + (n_meta_lines * meta_line_h) + cell_pad_y * 2 + meta_gap
        # Give collectors writing space and allow ADV marker to sit at the bottom of the payment cell
        if _is_route_print:
            try:
                min_h_route = (2 * line_h) + (cell_pad_y * 2)
                if h < min_h_route:
                    h = min_h_route
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_0497', 'suppressed exception excpass_0497', __spina_exc)
                pass
        ensure_space(h)
        x0 = col_left[col_idx]

        c.setLineWidth(0.4)
        # Light-green fill for NEW clients
        # Light-green fill for NEW clients (uses new_until or created_at+days; respects ledger_date)
        try:
            if self._is_client_new(text, ledger_date, highlight_days):
                c.saveState()
                try:
                    c.setFillColorRGB(0.88, 1.0, 0.88)
                except Exception as __spina_exc:
                    _log_suppressed_once('excpass_0498', 'suppressed exception excpass_0498', __spina_exc)
                    pass
                c.rect(x0, y_cursor - h, table_w - 6, h, stroke=0, fill=1)
                c.restoreState()
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0499', 'suppressed exception excpass_0499', __spina_exc)
            pass
        # Tomorrow notes keep a colored note box; the full cell only gets a very subtle warm tint.
        try:
            if _has_route_note_badge:
                c.saveState()
                c.setFillColorRGB(1.0, 0.985, 0.940)
                c.rect(x0 + idx_w, y_cursor - h, name_w, h, stroke=0, fill=1)
                c.restoreState()
        except Exception as __spina_exc:
            _log_suppressed_once('route_note_name_highlight', 'route note name highlight failed', __spina_exc)
        # Dashboard status stays clean: no colored side strip, to keep the route print easy on the eyes.
        c.rect(x0, y_cursor - h, table_w - 6, h, stroke=1, fill=0)
        c.line(x0 + idx_w, y_cursor - h, x0 + idx_w, y_cursor)
        c.line(x0 + idx_w + name_w, y_cursor - h, x0 + idx_w + name_w, y_cursor)
        # If route print requests two payments, draw mid-line inside the Payment cell
        if getattr(self, '_route_payment_two_cols', False):
            _x_pay_left  = x0 + idx_w + name_w
            _x_pay_right = x0 + (table_w - 6)
            _x_mid = _x_pay_left + (_x_pay_right - _x_pay_left) / 2.0
            c.line(_x_mid, y_cursor - h, _x_mid, y_cursor)

        local_index += 1
        text_y = y_cursor - cell_pad_y - (line_h - 2)
        # Bottom baseline for ADV marker in collector route (keeps top area clear for writing)
        adv_y = (y_cursor - h) + cell_pad_y + 1.2



        # Row number (neutral by default; 7x7-only pink fill is applied later inside the 7x7 highlight block)
        try:
            c.saveState()
            c.setFont(_PDF_FONT_BOLD, 9.5)
            c.setFillColorRGB(0, 0, 0)
            c.drawRightString(x0 + idx_w - cell_pad_x, text_y, str(local_index))
            c.restoreState()
        except Exception:
            c.setFont(_PDF_FONT_BOLD, 9.5)
            c.drawRightString(x0 + idx_w - cell_pad_x, text_y, str(local_index))
        # Payment column: keep amounts blank (collector writes), but SHOW ADV markers so skips are obvious
        try:
            if getattr(self, "_route_payment_two_cols", False):
                # Resolve linked names (FAST: precomputed map; avoids per-row DB queries)
                _nm_reg = None
                _nm_7x7 = None
                _linked_flag = False
                try:
                    import re as _re
                    _raw_text = str(text or "").strip()
                    _base = _re.sub(r"\s*\([^)]*\)\s*$", "", _raw_text).strip()
                    _pair = route_link_map.get(str(_raw_text).lower(), None)
                    if not isinstance(_pair, dict):
                        _pair = route_link_map.get(str(_base).lower(), None)
                    if isinstance(_pair, dict):
                        _nm_reg = _pair.get("Regular") or None
                        _nm_7x7 = _pair.get("7x7") or None
                        try:
                            _linked_flag = bool(_pair.get("_linked"))
                        except Exception:
                            _linked_flag = False
                    # Fallback: keep the side implied by the marker/name, and leave the other side empty
                    # so we can resolve it via person_uid (or keep blank if truly missing).
                    _is7_marker = "(7x7)" in _raw_text.lower()
                    if not _nm_reg and (not _is7_marker):
                        _nm_reg = _raw_text or _base
                    if not _nm_7x7 and _is7_marker:
                        _nm_7x7 = _base or _raw_text
                except Exception:
                    _fallback_text = str(text or "").strip()
                    _fallback_is7 = "(7x7)" in _fallback_text.lower()
                    _fallback_base = _fallback_text.replace("(7x7)", "").strip()
                    _nm_reg = None if _fallback_is7 else (_fallback_text or _fallback_base)
                    _nm_7x7 = (_fallback_base or _fallback_text) if _fallback_is7 else None
# If only one side exists, try finding the linked other-side name via person_uid
                try:
                    if (not _nm_reg) or (not _nm_7x7):
                        _base_lt = "Regular" if _nm_reg else ("7x7" if _nm_7x7 else None)
                        if _base_lt:
                            _base_row = self.db.get_client_info(_raw_text, loan_type=_base_lt) or self.db.get_client_info(_base, loan_type=_base_lt) or {}
                            _pu = (_base_row.get("person_uid") or "").strip()
                            if _pu:
                                for _r in (self.db.find_clients_by_person_uid(_pu) or []):
                                    _lt = (_r.get("loan_type") or "").strip()
                                    _lt_norm = "7x7" if _lt.lower().replace(" ", "") in ("7x7", "7×7") else "Regular"
                                    if _lt_norm == "Regular" and not _nm_reg:
                                        _nm_reg = (_r.get("name") or "").strip() or _nm_reg
                                    if _lt_norm == "7x7" and not _nm_7x7:
                                        _nm_7x7 = (_r.get("name") or "").strip() or _nm_7x7
                except Exception as __spina_exc:
                    _log_suppressed_once('excpass_0501', 'suppressed exception excpass_0501', __spina_exc)
                    pass

                # If we managed to resolve BOTH sides, treat this row as linked even if the prefetch map was missing.
                try:
                    if (not _linked_flag) and _nm_reg and _nm_7x7:
                        if str(_nm_reg).strip().lower() != str(_nm_7x7).strip().lower():
                            _linked_flag = True
                except Exception:
                    pass

                def _adv_txt(_nm, _lt):
                    if not _nm:
                        return ""
                    # Collector Route PDF ADV marker:
                    #   - Route print: "A-<day>" (use the covered END day if we know it), else "A"
                    #   - Other prints: keep "ADV"
                    def _adv_lbl(_end=None, _fallback=None):
                        if not _is_route_print:
                            return "ADV"
                        try:
                            _s = str(_end or _fallback or "")[:10]
                            if len(_s) >= 10:
                                _dd = int(_s[8:10])
                                if _dd > 0:
                                    return f"A-{_dd}"
                        except Exception as __spina_exc:
                            _log_suppressed_once('excpass_0502', 'suppressed exception excpass_0502', __spina_exc)
                            pass
                        return "A"

                    # Fast-path: prefetch cache
                    try:
                        _k = str(_nm).strip().lower()
                        _lt_clean = str(_lt or "").lower().replace(" ", "")
                        _lt_norm = "7x7" if ("7x7" in _lt_clean or "7×7" in _lt_clean) else "Regular"
                        _v = route_adv_cache.get((_k, _lt_norm))
                        if _v:
                            if _v is True:
                                return "A" if _is_route_print else "ADV"
                            try:
                                if isinstance(_v, (list, tuple, set)):
                                    for _it in _v:
                                        if isinstance(_it, tuple) and len(_it) >= 2:
                                            _s_s = str(_it[0] or "")[:10]
                                            _e_s = str(_it[1] or "")[:10]
                                            _p_s = str(_it[2] or "")[:10] if len(_it) >= 3 else ""
                                            if _s_s and _e_s and (_s_s <= ledger_date <= _e_s) and True:
                                                return _adv_lbl(_e_s, ledger_date)
                                        else:
                                            if str(_it or "")[:10] == ledger_date:
                                                return _adv_lbl(str(_it or "")[:10], ledger_date)
                                else:
                                    return "A" if _is_route_print else "ADV"
                            except Exception:
                                return "A" if _is_route_print else "ADV"
                    except Exception as __spina_exc:
                        _log_suppressed_once('excpass_0503', 'suppressed exception excpass_0503', __spina_exc)
                        pass

                    # Robust fallback: Collector Route cache can miss when PostgreSQL name/case/link matching differs.
                    # Use a direct ADV lookup for route prints too, preserving the route A-<day> format.
                    try:
                        if "_spina_route_adv_marker_for" in globals():
                            _ok_adv, _adv_end = _spina_route_adv_marker_for(self.db, _nm, ledger_date, _lt)
                            if _ok_adv:
                                return _adv_lbl(_adv_end or ledger_date, ledger_date)
                    except Exception as __spina_exc:
                        _log_suppressed_once('excpass_0504_route_adv', 'collector route ADV fallback failed', __spina_exc)
                        pass
                    try:
                        if (not _is_route_print) and ("_adv_paid_on_dates_covering" in globals()):
                            _srcs = _adv_paid_on_dates_covering(self.db, _nm, ledger_date, _lt)
                            if _srcs:
                                return "ADV"
                    except Exception as __spina_exc:
                        _log_suppressed_once('excpass_0504', 'suppressed exception excpass_0504', __spina_exc)
                        pass
                    try:
                        if (not _is_route_print) and ("_is_advance_on" in globals()):
                            if _is_advance_on(self.db, _nm, ledger_date, _lt):
                                return "ADV"
                    except Exception as __spina_exc:
                        _log_suppressed_once('excpass_0505', 'suppressed exception excpass_0505', __spina_exc)
                        pass
                    return ""


                _x_pay_left  = x0 + idx_w + name_w
                _x_pay_right = x0 + idx_w + name_w + pay_w - cell_pad_x
                _x_mid = _x_pay_left + (_x_pay_right - _x_pay_left) / 2.0
                _half_w = max(10.0, (_x_mid - _x_pay_left) - (cell_pad_x * 1.2))

                def _closed_paid_txt(_nm, _lt):
                    try:
                        if not bool(getattr(self, "_ledger_closed_copy_show_paid", False)):
                            return ""
                    except Exception:
                        return ""
                    try:
                        _nm0 = str(_nm or "").strip()
                        if not _nm0:
                            return ""
                        import re as _re_paid
                        _nm0 = _re_paid.sub(r"\s*\([^)]*\)\s*$", "", _nm0).strip()
                        _lt0 = "7x7" if ("7x7" in str(_lt or "").lower().replace(" ", "").replace("×", "x")) else "Regular"
                        _cache = getattr(self, "_ledger_closed_paid_cache", None)
                        _key = (_nm0.lower(), _lt0.lower())
                        _amt = None
                        if isinstance(_cache, dict):
                            _amt = _cache.get(_key)
                        if _amt is None:
                            _conn = getattr(getattr(self, "db", None), "conn", None)
                            if _conn is None:
                                return ""
                            _row = _conn.execute(
                                """SELECT COALESCE(SUM(COALESCE(payment,0)),0)
                                      FROM transactions
                                     WHERE date(date)=date(?)
                                       AND UPPER(TRIM(name))=UPPER(TRIM(?))
                                       AND (CASE WHEN LOWER(REPLACE(REPLACE(IFNULL(loan_type,'Regular'),' ',''),'×','x')) LIKE '%7x7%' THEN '7x7' ELSE 'regular' END)=?""",
                                (ledger_date, _nm0, _lt0.lower()),
                            ).fetchone()
                            _amt = float((_row[0] if _row else 0.0) or 0.0)
                        if abs(float(_amt or 0.0)) < 0.005:
                            return ""
                        return _fmt_pay_amount(_amt)
                    except Exception:
                        return ""

                _closed_route_paid_mode = bool(getattr(self, "_ledger_closed_copy_show_paid", False))
                _txt_reg_is_paid = False
                _txt_7x7_is_paid = False
                _txt_reg_adv_extra = ""
                _txt_7x7_adv_extra = ""
                if _closed_route_paid_mode:
                    # Closed route copy: if a client is both PAID today and ADV-covered,
                    # show BOTH. Paid amount goes in the true center; ADV stays in the normal route format.
                    _adv_reg_marker = _adv_txt(_nm_reg, "Regular")
                    _adv_7x7_marker = _adv_txt(_nm_7x7, "7x7")
                    _paid_reg_marker = _closed_paid_txt(_nm_reg, "Regular")
                    _paid_7x7_marker = _closed_paid_txt(_nm_7x7, "7x7")

                    if _paid_reg_marker:
                        _txt_reg = _paid_reg_marker
                        _txt_reg_is_paid = True
                        _txt_reg_adv_extra = _adv_reg_marker or ""
                    else:
                        _txt_reg = _adv_reg_marker

                    if _paid_7x7_marker:
                        _txt_7x7 = _paid_7x7_marker
                        _txt_7x7_is_paid = True
                        _txt_7x7_adv_extra = _adv_7x7_marker or ""
                    else:
                        _txt_7x7 = _adv_7x7_marker
                else:
                    _txt_reg = _adv_txt(_nm_reg, "Regular")
                    _txt_7x7 = _adv_txt(_nm_7x7, "7x7")
                # Highlight payment halves by the real account state of this printed row:
                #   Regular-only -> left half
                #   7x7-only     -> right half
                #   both         -> both halves
                _acct_has_reg = False
                _acct_has_7x7 = False
                try:
                    import re as _re
                    _row_text = str(text or "").strip()
                    _base_name = _re.sub(r"\s*\([^)]*\)\s*$", "", _row_text).strip()
                    _is7_marker = "(7x7)" in _row_text
                    # Use the resolved side names first, not only the printed base name.
                    # Some linked pairs use different Regular vs 7x7 names, and using only
                    # the printed base name can miss one side and skip the payment-column highlight.
                    _lookup_reg_name = (_nm_reg or _base_name or "").strip()
                    _lookup_7x7_name = (_nm_7x7 or _base_name or "").strip()
                    _row_reg = self.db.get_client_info(_lookup_reg_name, loan_type="Regular") or {}
                    _row_7x7 = self.db.get_client_info(_lookup_7x7_name, loan_type="7x7") or {}
                    if _is7_marker:
                        _acct_has_7x7 = bool(_row_7x7)
                        if _row_reg:
                            _acct_has_reg = True
                    else:
                        if _row_reg:
                            _acct_has_reg = True
                        if _row_7x7:
                            _acct_has_7x7 = True
                    _seed_row = _row_7x7 if (_is7_marker and _row_7x7) else (_row_reg or _row_7x7)
                    _pu = (_seed_row.get("person_uid") or "").strip() if isinstance(_seed_row, dict) else ""
                    if _pu:
                        for _r in (self.db.find_clients_by_person_uid(_pu) or []):
                            _lt = (_r.get("loan_type") or "").strip().lower().replace(" ", "")
                            if _lt in ("7x7", "7×7"):
                                _acct_has_7x7 = True
                            elif _lt:
                                _acct_has_reg = True
                    else:
                        # No stable person_uid. Do not infer BOTH sides from the resolved names
                        # unless a true linked pair was already confirmed.
                        if _linked_flag:
                            _acct_has_reg = _acct_has_reg or bool(_nm_reg)
                            _acct_has_7x7 = _acct_has_7x7 or bool(_nm_7x7)
                except Exception as __spina_exc:
                    _log_suppressed_once('excpass_9990a', 'suppressed exception excpass_9990a', __spina_exc)
                    if _linked_flag:
                        _acct_has_reg = _acct_has_reg or bool(_nm_reg)
                        _acct_has_7x7 = _acct_has_7x7 or bool(_nm_7x7)
                try:
                    if _is_route_print and (_acct_has_reg or _acct_has_7x7):
                        c.saveState()
                        _in = 1.2
                        try:
                            try:
                                c.setFillColorRGB(1, 0, 0)
                                try:
                                    c.setFillAlpha(0.12)
                                except Exception:
                                    c.setFillColorRGB(1.0, 0.85, 0.85)
                            except Exception:
                                c.setFillColorRGB(1.0, 0.85, 0.85)
                        except Exception as __spina_exc:
                            _log_suppressed_once('excpass_9990', 'suppressed exception excpass_9990', __spina_exc)
                            try:
                                c.setFillColorRGB(1.0, 0.85, 0.85)
                            except Exception:
                                pass
                        if _acct_has_reg:
                            _xl = _x_pay_left
                            _xr = _x_mid
                            try:
                                c.rect(_xl + (_in / 2.0), (y_cursor - h) + (_in / 2.0),
                                       max(0.0, (_xr - _xl) - _in), max(0.0, h - _in),
                                       stroke=0, fill=1)
                            except Exception:
                                c.rect(_xl, (y_cursor - h), max(0.0, (_xr - _xl)), h, stroke=0, fill=1)
                        if _acct_has_7x7:
                            _xl = _x_mid
                            _xr = _x_pay_right + cell_pad_x
                            try:
                                c.rect(_xl + (_in / 2.0), (y_cursor - h) + (_in / 2.0),
                                       max(0.0, (_xr - _xl) - _in), max(0.0, h - _in),
                                       stroke=0, fill=1)
                            except Exception:
                                c.rect(_xl, (y_cursor - h), max(0.0, (_xr - _xl)), h, stroke=0, fill=1)
                        c.restoreState()
                except Exception as __spina_exc:
                    _log_suppressed_once('excpass_9992', 'suppressed exception excpass_9992', __spina_exc)
                    pass
# Closed route paid amounts are centered, slightly bigger, and black.
                # Normal ADV markers keep the original route format.
                def _draw_payment_half(_txt, _is_paid, _center_x, _right_x):
                    try:
                        _txt = str(_txt or '').strip()
                        if not _txt:
                            return
                        _font = _PDF_FONT_BOLD
                        _size = 11.2 if _is_paid else 8.0
                        _max_w = max(8.0, _half_w - 1.0)
                        if _is_paid:
                            try:
                                while _size > 7.2 and c.stringWidth(_safe(_txt), _font, _size) > _max_w:
                                    _size -= 0.25
                            except Exception:
                                pass
                            # Paid amount in closed-route copy should sit in the TRUE center
                            # of the payment box, not on the normal ADV/detail baseline.
                            try:
                                _cell_mid_y = (y_cursor - h) + (h / 2.0)
                                _baseline = _cell_mid_y - (_size * 0.32)
                            except Exception:
                                _baseline = (adv_y if _is_route_print else text_y)
                            c.saveState()
                            c.setFont(_font, _size)
                            c.setFillColorRGB(0, 0, 0)
                            c.drawCentredString(_center_x, _baseline, _safe(_txt))
                            c.restoreState()
                        else:
                            # ADV / A-xx stays in the original route format.
                            _baseline = (adv_y if _is_route_print else text_y)
                            c.saveState()
                            c.setFont(_font, _size)
                            c.setFillColorRGB(1, 0, 0)
                            c.drawRightString(_right_x, _baseline, _safe(_txt))
                            c.restoreState()
                    except Exception as __spina_exc:
                        try:
                            _log_suppressed_once('closed_route_payment_draw_failed', 'closed route payment draw failed', __spina_exc)
                        except Exception:
                            pass

                _draw_payment_half(_txt_reg, _txt_reg_is_paid, (_x_pay_left + _x_mid) / 2.0, _x_mid - cell_pad_x)
                if _txt_reg_adv_extra:
                    _draw_payment_half(_txt_reg_adv_extra, False, (_x_pay_left + _x_mid) / 2.0, _x_mid - cell_pad_x)
                _draw_payment_half(_txt_7x7, _txt_7x7_is_paid, (_x_mid + _x_pay_right) / 2.0, _x_pay_right)
                if _txt_7x7_adv_extra:
                    _draw_payment_half(_txt_7x7_adv_extra, False, (_x_mid + _x_pay_right) / 2.0, _x_pay_right)
            else:
                # Explicit 7x7 rows only: RED HIGHLIGHT for the Payment cell (route print only)
                try:
                    _linked2 = False
                    _has_7x7_row = False
                    if _is_route_print:
                        import re as _re
                        _raw_text = str(text or "")
                        _base = _re.sub(r"\s*\([^)]*\)\s*$", "", _raw_text).strip()
                        _pair = route_link_map.get(str(_raw_text).lower(), None)
                        if not isinstance(_pair, dict):
                            _pair = route_link_map.get(str(_base).lower(), None)
                        if isinstance(_pair, dict):
                            _linked2 = bool(_pair.get("_linked"))
                            _has_7x7_row = bool(_pair.get("7x7"))
                        if (not _has_7x7_row) and ("(7x7)" in _raw_text):
                            _has_7x7_row = True
                    if _has_7x7_row:
                        # No single-column fill here; column-specific highlighting only applies in two-column route print.
                        pass
                except Exception as __spina_exc:
                    _log_suppressed_once('excpass_9993', 'suppressed exception excpass_9993', __spina_exc)
                    pass
                pay_txt = ""
                pay_adv_end = ""
                try:
                    # Fast-path: prefetch cache
                    try:
                        _k = str(lookup_name or "").strip().lower()
                        _lt_norm = "7x7" if str(self._mode_filter() or "Regular").lower().replace(" ", "") == "7x7" else "Regular"
                        _v = route_adv_cache.get((_k, _lt_norm))
                        if _v:
                            if _v is True:
                                pay_txt = "ADV"
                                pay_adv_end = pay_adv_end or ledger_date
                            else:
                                try:
                                    if isinstance(_v, (list, tuple, set)):
                                        for _it in _v:
                                            if isinstance(_it, tuple) and len(_it) >= 2:
                                                _s_s = str(_it[0] or "")[:10]
                                                _e_s = str(_it[1] or "")[:10]
                                                _p_s = str(_it[2] or "")[:10] if len(_it) >= 3 else ""
                                                if _s_s and _e_s and (_s_s <= ledger_date <= _e_s) and True:
                                                    pay_txt = "ADV"
                                                    pay_adv_end = (_e_s or ledger_date)
                                                    break
                                            else:
                                                if str(_it or "")[:10] == ledger_date:
                                                    pay_txt = "ADV"
                                                    pay_adv_end = (str(_it or "")[:10] or ledger_date)
                                                    break
                                    else:
                                        pay_txt = "ADV"
                                        pay_adv_end = pay_adv_end or ledger_date
                                except Exception:
                                    pay_txt = "ADV"
                                    pay_adv_end = pay_adv_end or ledger_date
                    except Exception as __spina_exc:
                        _log_suppressed_once('excpass_0510', 'suppressed exception excpass_0510', __spina_exc)
                        pass
                    if (not pay_txt) and ("_spina_route_adv_marker_for" in globals()):
                        _ok_adv, _adv_end = _spina_route_adv_marker_for(self.db, lookup_name, ledger_date, self._mode_filter())
                        if _ok_adv:
                            pay_txt = "ADV"
                            pay_adv_end = (_adv_end or ledger_date)
                    if (not _is_route_print) and ("_adv_paid_on_dates_covering" in globals()):
                        _srcs = _adv_paid_on_dates_covering(self.db, lookup_name, ledger_date, self._mode_filter())
                        if _srcs:
                            pay_txt = "ADV"
                            pay_adv_end = pay_adv_end or ledger_date
                    if (not pay_txt) and ("_is_advance_on" in globals()):
                        if _is_advance_on(self.db, lookup_name, ledger_date, self._mode_filter()):
                            pay_txt = "ADV"
                            pay_adv_end = pay_adv_end or ledger_date
                except Exception as __spina_exc:
                    _log_suppressed_once('excpass_0511', 'suppressed exception excpass_0511', __spina_exc)
                    pass
                # Convert ADV marker to compact "A-<day>" in Collector Route PDF
                if pay_txt and _is_route_print:
                    try:
                        _s = str(pay_adv_end or ledger_date)[:10]
                        _dd = int(_s[8:10]) if (len(_s) >= 10) else 0
                        pay_txt = (f"A-{_dd}" if _dd > 0 else "A")
                    except Exception:
                        pay_txt = "A"

                _single_closed_paid = False
                _single_adv_extra = ""
                if bool(getattr(self, "_ledger_closed_copy_show_paid", False)):
                    try:
                        # If this route date is ADV-covered, preserve that ADV marker and still show
                        # the real closed-day payment amount in the middle when a payment exists.
                        _single_adv_extra = str(pay_txt or "").strip()
                        import re as _re_paid2
                        _nm_paid2 = _re_paid2.sub(r"\s*\([^)]*\)\s*$", "", str(lookup_name or text or "")).strip()
                        _lt_paid2 = "7x7" if str(self._mode_filter() or "Regular").lower().replace(" ", "").replace("×", "x") == "7x7" else "Regular"
                        _row_paid2 = self.db.conn.execute(
                            """SELECT COALESCE(SUM(COALESCE(payment,0)),0)
                                  FROM transactions
                                 WHERE date(date)=date(?)
                                   AND UPPER(TRIM(name))=UPPER(TRIM(?))
                                   AND (CASE WHEN LOWER(REPLACE(REPLACE(IFNULL(loan_type,'Regular'),' ',''),'×','x')) LIKE '%7x7%' THEN '7x7' ELSE 'regular' END)=?""",
                            (ledger_date, _nm_paid2, _lt_paid2.lower()),
                        ).fetchone()
                        _amt_paid2 = float((_row_paid2[0] if _row_paid2 else 0.0) or 0.0)
                        _paid_txt2 = _fmt_pay_amount(_amt_paid2) if abs(_amt_paid2) >= 0.005 else ""
                        if _paid_txt2:
                            pay_txt = _paid_txt2
                            _single_closed_paid = True
                        elif _single_adv_extra:
                            pay_txt = _single_adv_extra
                            _single_adv_extra = ""
                    except Exception:
                        # If the paid lookup fails, keep the normal ADV route display unchanged.
                        pass

                if pay_txt:
                    try:
                        _baseline2 = (adv_y if _is_route_print else text_y)
                        if _single_closed_paid:
                            _font2 = _PDF_FONT_BOLD
                            _size2 = 11.2
                            _max_w2 = max(10.0, pay_w - (cell_pad_x * 2.0))
                            try:
                                while _size2 > 7.2 and c.stringWidth(_safe(pay_txt), _font2, _size2) > _max_w2:
                                    _size2 -= 0.25
                            except Exception:
                                pass
                            try:
                                _cell_mid_y2 = (y_cursor - h) + (h / 2.0)
                                _baseline2 = _cell_mid_y2 - (_size2 * 0.32)
                            except Exception:
                                _baseline2 = (adv_y if _is_route_print else text_y)
                            c.saveState()
                            c.setFont(_font2, _size2)
                            c.setFillColorRGB(0, 0, 0)
                            c.drawCentredString(x0 + idx_w + name_w + (pay_w / 2.0), _baseline2, _safe(pay_txt))
                            c.restoreState()
                            if _single_adv_extra:
                                # Keep ADV / A-xx in the original route format too.
                                c.saveState()
                                c.setFillColorRGB(1, 0, 0)
                                c.drawRightString(x0 + idx_w + name_w + pay_w - cell_pad_x, (adv_y if _is_route_print else text_y), _safe(_single_adv_extra))
                                c.restoreState()
                        else:
                            # ADV / A-xx stays in the original route format.
                            c.saveState()
                            c.setFillColorRGB(1, 0, 0)
                            c.drawRightString(x0 + idx_w + name_w + pay_w - cell_pad_x, _baseline2, _safe(pay_txt))
                            c.restoreState()
                    except Exception as __spina_exc:
                        try:
                            _log_suppressed_once('closed_route_single_payment_draw_failed', 'closed route single payment draw failed', __spina_exc)
                        except Exception:
                            pass
        except Exception:
            c.drawRightString(x0 + idx_w + name_w + pay_w - cell_pad_x, text_y, "")

        # Name cell highlight by Reason color window (Encoder reason tokens like [RC:...;D:n] or [RC:...;UNTIL:...])
        try:
            _hex = ""
            _nm_lookup = str(text or "").strip()
            try:
                import re as _re
                _nm_lookup = _re.sub(r"\s*\([^)]*\)\s*$", "", _nm_lookup)  # strip trailing markers like "(7x7)"
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_0514', 'suppressed exception excpass_0514', __spina_exc)
                pass
            # Fast-path: use prefetch cache (no per-client DB scan)
            try:
                _k = str(_nm_lookup or "").strip().lower()
                if _k:
                    _ltp = "7x7" if str(self._mode_filter() or "Regular").lower().replace(" ", "") == "7x7" else "Regular"
                    _lto = "7x7" if _ltp != "7x7" else "Regular"
                    _hex = route_reason_cache.get((_k, _ltp), "") or route_reason_cache.get((_k, _lto), "")
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_0515', 'suppressed exception excpass_0515', __spina_exc)
                pass

            # Fallback (older behavior) - can be slow on huge DB if indexes are missing
            if (not _hex) and (not _is_route_print) and ("_get_reason_color_for_client_date" in globals()):
                _hex = _get_reason_color_for_client_date(self.db, _nm_lookup, ledger_date, self._mode_filter())
            if _hex:
                r1, g1, b1 = _hex_to_rgb01(_hex)
                # blend with white to create a readable highlight
                alpha = 0.22
                r_bg = 1.0 - alpha + alpha * r1
                g_bg = 1.0 - alpha + alpha * g1
                b_bg = 1.0 - alpha + alpha * b1
                c.saveState()
                try:
                    c.setFillColorRGB(r_bg, g_bg, b_bg)
                except Exception as __spina_exc:
                    _log_suppressed_once('excpass_0516', 'suppressed exception excpass_0516', __spina_exc)
                    pass
                inset = 0.6
                c.rect(x0 + idx_w + inset/2.0, y_cursor - h + inset/2.0, name_w - inset, h - inset, stroke=0, fill=1)
                c.restoreState()
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0517', 'suppressed exception excpass_0517', __spina_exc)
            pass

        try:
            c.setFont(_PDF_FONT_BOLD, 9.5)
        except Exception:
            c.setFont(_PDF_FONT_BASE, 9.5)
        for i, ln in enumerate(name_lines):
            c.drawString(x0 + idx_w + cell_pad_x, text_y - i * line_h, _safe(ln))

        if meta_lines:
            _meta_y = text_y - (len(name_lines) * line_h) - meta_gap
            try:
                c.setFont(_PDF_FONT_BASE, 8.0)
            except Exception:
                c.setFont(_PDF_FONT_BASE, 8.0)
            for i, ln in enumerate(meta_lines):
                _yy = _meta_y - i * meta_line_h
                if str(ln or '').startswith('__DASH_BADGE__|'):
                    # Noticeable Dashboard completion badge under the client name.
                    try:
                        _parts = str(ln or '').split('|', 2)
                        _dash_status = _parts[1] if len(_parts) > 1 else ''
                        _badge_txt = _parts[2] if len(_parts) > 2 else str(ln or '').replace('__DASH_BADGE__|', '')
                    except Exception:
                        _dash_status = ''
                        _badge_txt = str(ln or '')
                    try:
                        _badge_font = 7.4
                        _badge_pad_x = 3.5
                        _badge_h = 9.2
                        _max_w = max(30.0, name_w - (cell_pad_x * 2.0) - 1.0)
                        _badge_w = stringWidth(_badge_txt, _PDF_FONT_BOLD, _badge_font) + (_badge_pad_x * 2.0)
                        if _badge_w > _max_w:
                            _badge_w = _max_w
                    except Exception:
                        _badge_font = 7.2
                        _badge_pad_x = 3.5
                        _badge_h = 9.2
                        _badge_w = min(90.0, max(30.0, name_w - (cell_pad_x * 2.0)))
                    _bx = x0 + idx_w + cell_pad_x
                    _by = _yy - 2.0
                    try:
                        # Clean, aligned, blended-color status: fixed-width soft label.
                        # Muted fills match the route PDF style without hurting the eyes.
                        c.saveState()
                        _badge_w = max(36.0, name_w - (cell_pad_x * 2.0) - 1.0)
                        _badge_h = 8.4
                        _badge_font = 7.1
                        _badge_pad_x = 3.2
                        _by = _yy - 1.7

                        # Soft colors: 90%=warm amber, 75%=calm blue, Complete=soft green.
                        # Keep all labels same size and subtle borders for clean alignment.
                        try:
                            _ds = str(_dash_status or '').strip().lower()
                        except Exception:
                            _ds = ''
                        if 'complete' in _ds:
                            _fill_rgb = (0.925, 0.975, 0.925)
                            _stroke_rgb = (0.620, 0.760, 0.620)
                            _text_rgb = (0.120, 0.300, 0.140)
                        elif 'finishing' in _ds or '90' in str(_badge_txt):
                            _fill_rgb = (1.000, 0.955, 0.875)
                            _stroke_rgb = (0.820, 0.690, 0.430)
                            _text_rgb = (0.330, 0.230, 0.110)
                        else:
                            _fill_rgb = (0.925, 0.955, 0.990)
                            _stroke_rgb = (0.590, 0.690, 0.820)
                            _text_rgb = (0.100, 0.210, 0.340)

                        c.setFillColorRGB(*_fill_rgb)
                        c.setStrokeColorRGB(*_stroke_rgb)
                        c.setLineWidth(0.35)
                        c.roundRect(_bx, _by, _badge_w, _badge_h, 1.5, stroke=1, fill=1)
                        c.setFont(_PDF_FONT_BOLD, _badge_font)
                        c.setFillColorRGB(*_text_rgb)
                        _txt = _safe(_badge_txt)
                        try:
                            _max_txt_w = _badge_w - (_badge_pad_x * 2.0)
                            # Do not cut the balance. Shrink a little instead; wrapping already happened above.
                            while _badge_font > 5.6 and stringWidth(_txt, _PDF_FONT_BOLD, _badge_font) > _max_txt_w:
                                _badge_font -= 0.25
                            c.setFont(_PDF_FONT_BOLD, _badge_font)
                        except Exception:
                            pass
                        c.drawString(_bx + _badge_pad_x, _by + 1.85, _txt)
                        c.restoreState()
                    except Exception:
                        try:
                            c.setFont(_PDF_FONT_BOLD, 7.4)
                        except Exception:
                            pass
                        c.drawString(_bx, _yy, _safe(_badge_txt))
                elif str(ln or '').startswith('__DASH_BALANCE__|'):
                    try:
                        _bal_txt = str(ln or '').split('|', 1)[1]
                    except Exception:
                        _bal_txt = str(ln or '').replace('__DASH_BALANCE__|', '')
                    try:
                        _bal_font = 7.4
                        _bal_pad_x = 3.4
                        _bal_h = 8.8
                        _bal_w = max(40.0, name_w - (cell_pad_x * 2.0) - 1.0)
                        _bx = x0 + idx_w + cell_pad_x
                        _by = _yy - 1.9
                        c.saveState()
                        c.setFillColorRGB(0.925, 0.955, 0.990)
                        c.setStrokeColorRGB(0.590, 0.690, 0.820)
                        c.setLineWidth(0.35)
                        c.roundRect(_bx, _by, _bal_w, _bal_h, 1.5, stroke=1, fill=1)
                        _txt = _safe(_bal_txt)
                        # Shrink rather than hide or ellipsis, so the balance is always visible.
                        try:
                            while _bal_font > 5.4 and stringWidth(_txt, _PDF_FONT_BOLD, _bal_font) > (_bal_w - (_bal_pad_x * 2.0)):
                                _bal_font -= 0.35
                        except Exception:
                            pass
                        c.setFont(_PDF_FONT_BOLD, _bal_font)
                        c.setFillColorRGB(0.100, 0.210, 0.340)
                        c.drawString(_bx + _bal_pad_x, _by + 2.05, _txt)
                        c.restoreState()
                    except Exception:
                        try:
                            c.setFont(_PDF_FONT_BOLD, 7.0)
                        except Exception:
                            pass
                        c.drawString(x0 + idx_w + cell_pad_x, _yy, _safe(_bal_txt))
                elif str(ln or '').startswith('__ROUTE_NOTE__|'):
                    try:
                        _note_txt = str(ln or '').split('|', 1)[1]
                    except Exception:
                        _note_txt = str(ln or '').replace('__ROUTE_NOTE__|', '')
                    try:
                        _note_font = 7.8
                        _note_pad_x = 3.6
                        _note_h = 9.6
                        _note_w = max(48.0, name_w - (cell_pad_x * 2.0) - 1.0)
                        _bx = x0 + idx_w + cell_pad_x
                        _by = _yy - 2.0
                        c.saveState()
                        # Soft amber note box: noticeable, but harmonized with status/balance badges.
                        c.setFillColorRGB(1.000, 0.955, 0.875)
                        c.setStrokeColorRGB(0.820, 0.690, 0.430)
                        c.setLineWidth(0.40)
                        c.roundRect(_bx, _by, _note_w, _note_h, 1.8, stroke=1, fill=1)
                        c.setFont(_PDF_FONT_BOLD, _note_font)
                        c.setFillColorRGB(0.330, 0.230, 0.110)
                        # Text was already wrapped during meta-line preparation; do not cut it with ellipsis.
                        try:
                            while _note_font > 5.8 and stringWidth(_safe(_note_txt), _PDF_FONT_BOLD, _note_font) > (_note_w - (_note_pad_x * 2.0)):
                                _note_font -= 0.25
                            c.setFont(_PDF_FONT_BOLD, _note_font)
                        except Exception:
                            pass
                        c.drawString(_bx + _note_pad_x, _by + 2.15, _safe(_note_txt))
                        c.restoreState()
                    except Exception:
                        try:
                            c.setFont(_PDF_FONT_BOLD, 8.2)
                            c.setFillColorRGB(0.42, 0.09, 0.00)
                        except Exception:
                            pass
                        c.drawString(x0 + idx_w + cell_pad_x, _yy, _safe(_note_txt))
                elif str(ln or '') == '__DUE_TODAY_BADGE__':
                    _badge_txt = 'DUE TODAY'
                    try:
                        _badge_font = 7.0
                        _badge_pad_x = 3.0
                        _badge_h = 8.5
                        _badge_w = stringWidth(_badge_txt, _PDF_FONT_BOLD, _badge_font) + (_badge_pad_x * 2.0)
                    except Exception:
                        _badge_font = 7.0
                        _badge_pad_x = 3.0
                        _badge_h = 8.5
                        _badge_w = 42.0
                    _bx = x0 + idx_w + cell_pad_x
                    _by = _yy - 2.0
                    try:
                        c.saveState()
                        c.setFillColorRGB(1.0, 0.9529, 0.7490)
                        c.setStrokeColorRGB(0.7176, 0.4745, 0.1216)
                        c.roundRect(_bx, _by, _badge_w, _badge_h, 2.0, stroke=1, fill=1)
                        c.setFont(_PDF_FONT_BOLD, _badge_font)
                        c.setFillColorRGB(0.7176, 0.4745, 0.1216)
                        c.drawString(_bx + _badge_pad_x, _by + 2.0, _badge_txt)
                        c.restoreState()
                    except Exception:
                        try:
                            c.setFont(_PDF_FONT_BOLD, 7.0)
                        except Exception:
                            pass
                        c.drawString(_bx, _yy, _badge_txt)
                else:
                    c.drawString(x0 + idx_w + cell_pad_x, _yy, _safe(ln))

            try:
                if False and _meta_group_break_idx and _meta_group_break_idx < len(meta_lines):
                    _div_y = _meta_y - ((_meta_group_break_idx - 1) * meta_line_h) - (meta_line_h * 0.58)
                    c.saveState()
                    c.setLineWidth(0.25)
                    c.line(x0 + idx_w + cell_pad_x,
                           _div_y,
                           x0 + idx_w + name_w - cell_pad_x,
                           _div_y)
                    c.restoreState()
            except Exception:
                pass

        y_cursor -= h

    def _draw_closed_route_payment_summary_page():
        """Append closed-route payment summaries on a separate page.

        This keeps the route pages in the normal collector format while still saving
        a complete area-by-area payment summary plus grand total.
        """
        try:
            _closed_mode = bool(getattr(self, "_ledger_closed_copy_show_paid", False))
        except Exception:
            _closed_mode = False
        if not _closed_mode:
            return

        def _fmt_summary_money(_v):
            try:
                _n = float(_v or 0)
            except Exception:
                _n = 0.0
            try:
                if abs(_n - int(_n)) < 0.005:
                    return f"{int(_n):,}"
            except Exception:
                pass
            return f"{_n:,.2f}"

        def _as_float(_v):
            try:
                return float(_v or 0)
            except Exception:
                return 0.0

        try:
            _collector_name = str(getattr(self, "_ledger_forced_collector_name", "") or "All Collectors")
        except Exception:
            _collector_name = "All Collectors"
        try:
            _disp_date = datetime.strptime(str(ledger_date)[:10], "%Y-%m-%d").strftime("%B %d, %Y")
        except Exception:
            _disp_date = str(ledger_date or "")

        _summary_rows = []
        _grand_expected = 0.0
        _grand_reg = 0.0
        _grand_7 = 0.0
        _grand_paid = 0.0
        try:
            _keys = list(area_keys or [])
        except Exception:
            _keys = []
        if not _keys:
            try:
                _keys = list((area_expected_map or {}).keys())
            except Exception:
                _keys = []

        for _area in _keys:
            _label = str(_area or "UNASSIGNED")
            try:
                _m = area_expected_map.get(_label, {}) if isinstance(area_expected_map, dict) else {}
            except Exception:
                _m = {}
            if not isinstance(_m, dict):
                _m = {"all": _m}
            _exp = _as_float(_m.get("all"))
            _reg = _as_float(_m.get("paid_reg"))
            _sev = _as_float(_m.get("paid_7x7"))
            _paid = _as_float(_m.get("paid_all"))
            if abs(_paid) < 0.005:
                _paid = _reg + _sev
            _grand_expected += _exp
            _grand_reg += _reg
            _grand_7 += _sev
            _grand_paid += _paid
            _summary_rows.append((_label, _exp, _reg, _sev, _paid))

        def _draw_summary_header(_continued=False):
            _y = height - margin_top + 6
            try:
                c.setFont(_PDF_FONT_BOLD, 14)
                _title = "CLOSED COLLECTOR ROUTE - PAYMENT SUMMARY"
                if _continued:
                    _title += " (CONTINUED)"
                c.drawCentredString(width / 2.0, _y, _safe(_title))
                _y -= 18
                c.setFont(_PDF_FONT_BASE, 10)
                c.drawString(margin_side, _y, _safe("Collector: " + _collector_name))
                _right = _safe("Date: " + _disp_date)
                try:
                    _tw = stringWidth(str(_right), _PDF_FONT_BASE, 10)
                except Exception:
                    _tw = 120
                c.drawString(width - margin_side - _tw, _y, str(_right))
                _y -= 14
                c.setLineWidth(0.6)
                c.line(margin_side, _y, width - margin_side, _y)
                _y -= 18
                c.setFont(_PDF_FONT_BOLD, 9)
                _cols = [
                    ("Area", margin_side, inner_w * 0.42, "left"),
                    ("Expected", margin_side + inner_w * 0.42, inner_w * 0.145, "right"),
                    ("Regular Paid", margin_side + inner_w * 0.565, inner_w * 0.145, "right"),
                    ("7x7 Paid", margin_side + inner_w * 0.710, inner_w * 0.125, "right"),
                    ("Total Payment", margin_side + inner_w * 0.835, inner_w * 0.165, "right"),
                ]
                _header_y = _y
                c.setFillColorRGB(0.94, 0.94, 0.94)
                c.rect(margin_side, _header_y - 5, inner_w, 16, stroke=0, fill=1)
                c.setFillColorRGB(0, 0, 0)
                for _txt, _x, _w, _align in _cols:
                    if _align == "right":
                        c.drawRightString(_x + _w - 4, _header_y, _safe(_txt))
                    else:
                        c.drawString(_x + 4, _header_y, _safe(_txt))
                c.setLineWidth(0.5)
                c.line(margin_side, _header_y - 7, width - margin_side, _header_y - 7)
                return _header_y - 20
            except Exception:
                return height - margin_top - 60

        def _draw_summary_row(_y, _area, _exp, _reg, _sev, _paid, _bold=False, _fill=False):
            _row_h = 17
            try:
                if _fill:
                    c.saveState()
                    c.setFillColorRGB(0.94, 0.94, 0.94)
                    c.rect(margin_side, _y - 5, inner_w, _row_h, stroke=0, fill=1)
                    c.restoreState()
                c.setFont(_PDF_FONT_BOLD if _bold else _PDF_FONT_BASE, 8.6)
                _area_w = inner_w * 0.42
                _area_txt = str(_area or "")
                try:
                    while len(_area_txt) > 4 and stringWidth(_safe(_area_txt), _PDF_FONT_BOLD if _bold else _PDF_FONT_BASE, 8.6) > (_area_w - 8):
                        _area_txt = _area_txt[:-2].rstrip() + "."
                except Exception:
                    pass
                c.drawString(margin_side + 4, _y, _safe(_area_txt))
                _x_exp = margin_side + inner_w * 0.42
                _x_reg = margin_side + inner_w * 0.565
                _x_7 = margin_side + inner_w * 0.710
                _x_total = margin_side + inner_w * 0.835
                c.drawRightString(_x_exp + inner_w * 0.145 - 4, _y, _safe(_fmt_summary_money(_exp)))
                c.drawRightString(_x_reg + inner_w * 0.145 - 4, _y, _safe(_fmt_summary_money(_reg)))
                c.drawRightString(_x_7 + inner_w * 0.125 - 4, _y, _safe(_fmt_summary_money(_sev)))
                c.drawRightString(_x_total + inner_w * 0.165 - 4, _y, _safe(_fmt_summary_money(_paid)))
                c.setLineWidth(0.25)
                c.line(margin_side, _y - 6, width - margin_side, _y - 6)
            except Exception:
                pass
            return _y - _row_h

        try:
            c.showPage()
            _y = _draw_summary_header(False)
            for _area, _exp, _reg, _sev, _paid in _summary_rows:
                if _y < margin_bottom + 36:
                    _draw_page_number()
                    c.showPage()
                    _y = _draw_summary_header(True)
                _y = _draw_summary_row(_y, _area, _exp, _reg, _sev, _paid)

            if _y < margin_bottom + 44:
                _draw_page_number()
                c.showPage()
                _y = _draw_summary_header(True)

            _y -= 6
            _y = _draw_summary_row(
                _y,
                "TOTAL - ALL AREAS",
                _grand_expected,
                _grand_reg,
                _grand_7,
                _grand_paid,
                _bold=True,
                _fill=True,
            )
            _y -= 12
            try:
                c.setFont(_PDF_FONT_BOLD, 12)
                c.drawRightString(width - margin_side, _y, _safe("TOTAL PAYMENT OF ALL AREAS: " + _fmt_summary_money(_grand_paid)))
            except Exception:
                pass
            _draw_page_number()
        except Exception as __spina_exc:
            try:
                _log_suppressed_once('closed_route_summary_page_failed', 'closed route payment summary page failed', __spina_exc)
            except Exception:
                pass

    try:
        _draw_page_number()
        _draw_final_footer()
        _draw_closed_route_payment_summary_page()
        c.save()
    except Exception:
        return

    try:
        self._last_printed_daily_ledger_path = out_path
    except Exception:
        pass
    # Auto-open unless this was a silent closed-route save.
    try:
        _silent_route_copy = bool(getattr(self, "_ledger_silent_route_copy", False))
    except Exception:
        _silent_route_copy = False
    if not _silent_route_copy:
        try:
            # Cross-platform safe open (no shell, handles quotes/spaces)
            _open_path(out_path)
        except Exception as e:
            try:
                _log_exc("Open generated PDF failed", e)
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_0518', 'suppressed exception excpass_0518', __spina_exc)
                pass
    # Cleanup forced areas flag if set
    try:
        if hasattr(self, '_ledger_forced_areas'):
            delattr(self, '_ledger_forced_areas')
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_0519', 'suppressed exception excpass_0519', __spina_exc)
        pass


def _spina_route_notice_norm_lt(value: str) -> str:
    try:
        s = str(value or "Regular").strip().lower().replace(" ", "").replace("×", "x")
        return "7x7" if "7x7" in s else "Regular"
    except Exception:
        return "Regular"


def _spina_route_notice_key(client: str, loan_type: str, client_uid: str = "") -> str:
    lt = _spina_route_notice_norm_lt(loan_type)
    uid = str(client_uid or "").strip()
    if uid:
        return f"{lt}|uid:{uid}"
    return f"{lt}|name:{_spina_route_notice_norm_name(client)}"


def _spina_route_notice_load() -> dict:
    try:
        if os.path.exists(ROUTE_NOTICES_FILE):
            with open(ROUTE_NOTICES_FILE, "r", encoding="utf-8") as f:
                obj = json.load(f)
            return obj if isinstance(obj, dict) else {}
    except Exception as e:
        try:
            _log_exc("route_notices.load", e)
        except Exception:
            pass
    return {}


def _spina_route_notice_save(data: dict) -> bool:
    try:
        if not isinstance(data, dict):
            data = {}
        os.makedirs(os.path.dirname(ROUTE_NOTICES_FILE), exist_ok=True)
        return bool(_write_json_atomic(ROUTE_NOTICES_FILE, data))
    except Exception as e:
        try:
            _log_exc("route_notices.save", e)
        except Exception:
            pass
        return False


def _spina_route_notice_upsert(day_iso: str, client: str, loan_type: str, notice: str,
                               client_uid: str = "", source_date: str = "",
                               record_id: str = "", collector: str = "") -> bool:
    try:
        day_iso = str(day_iso or "").strip()[:10]
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day_iso or ""):
            return False
        notice = str(notice or "").strip()
        if not notice:
            return False
        client = str(client or "").strip()
        lt = _spina_route_notice_norm_lt(loan_type)
        key = _spina_route_notice_key(client, lt, client_uid)
        data = _spina_route_notice_load()
        day_bucket = data.setdefault(day_iso, {})
        day_bucket[key] = {
            "client": client,
            "client_norm": _spina_route_notice_norm_name(client),
            "client_uid": str(client_uid or "").strip(),
            "loan_type": lt,
            "notice": notice,
            "source_date": str(source_date or "").strip()[:10],
            "record_id": str(record_id or "").strip(),
            "collector": str(collector or "").strip(),
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        return _spina_route_notice_save(data)
    except Exception as e:
        try:
            _log_exc("route_notices.upsert", e)
        except Exception:
            pass
        return False


def _spina_route_balance_like_generate_report(app, client_name, loan_type, asof_date):
    """Return the same Balance basis used by Generate Report PDF.

    Regular: total_to_pay (corrected to principal + interest when needed) minus
    effective current-cycle payments.

    7x7: remaining principal after the Generate Report interest-first payment
    split. This intentionally matches the report header Balance, not a separate
    route/dashboard estimate.
    """
    try:
        db = getattr(app, 'db', None)
        if db is None:
            return None
        lt_raw = str(loan_type or 'Regular').strip()
        lt_norm = '7x7' if ('7x7' in lt_raw.lower().replace('×', 'x')) else 'Regular'
        name = str(client_name or '').strip()
        if not name:
            return None
        try:
            info = db.get_client_info(name, loan_type=lt_norm) or {}
        except Exception:
            info = {}
        if not isinstance(info, dict) or not info:
            return None

        try:
            end_dt = datetime.strptime(str(asof_date)[:10], '%Y-%m-%d').date()
        except Exception:
            try:
                end_dt = date.today()
            except Exception:
                end_dt = datetime.now().date()
        end_s = end_dt.strftime('%Y-%m-%d')

        def _f(v):
            try:
                return float(v or 0.0)
            except Exception:
                try:
                    return float(str(v or '0').replace(',', '').strip() or 0.0)
                except Exception:
                    return 0.0

        # Match Generate Report cycle start: payment_start_date if valid, otherwise release date + offset.
        cycle_start = ''
        try:
            ps = str(info.get('payment_start_date') or '').strip()[:10]
            if ps:
                datetime.strptime(ps, '%Y-%m-%d')
                cycle_start = ps
            if cycle_start:
                dr0 = str(info.get('date_released') or '').strip()[:10]
                if dr0:
                    datetime.strptime(dr0, '%Y-%m-%d')
                    try:
                        off_chk = int(info.get('pay_start_offset_days') or 0)
                    except Exception:
                        off_chk = 0
                    off_chk = 1 if off_chk >= 1 else 0
                    if cycle_start < dr0 or (off_chk == 1 and cycle_start == dr0):
                        cycle_start = ''
        except Exception:
            cycle_start = ''
        if not cycle_start:
            cycle_start = str(info.get('date_released') or '').strip()[:10]
            try:
                datetime.strptime(cycle_start, '%Y-%m-%d')
            except Exception:
                cycle_start = end_s
            try:
                off = int(info.get('pay_start_offset_days') or 0)
            except Exception:
                off = 0
            off = 1 if off >= 1 else 0
            try:
                cycle_start = (datetime.strptime(cycle_start, '%Y-%m-%d').date() + timedelta(days=off)).strftime('%Y-%m-%d')
            except Exception:
                pass

        try:
            rows = db.get_transactions_for_client(name, cycle_start, end_s, loan_type=lt_norm) or []
        except Exception:
            rows = []

        # Same effective-payment rule used by Generate Report: last non-zero wins, zero ADV-only rows do not override.
        per = {}
        def _gv(r, k, default=None):
            try:
                return r[k]
            except Exception:
                try:
                    return dict(r).get(k, default)
                except Exception:
                    return default
        for r in rows or []:
            ds = str(_gv(r, 'date', '') or '').strip()[:10]
            if not ds:
                continue
            try:
                pay = float(_gv(r, 'payment', 0) or 0.0)
            except Exception:
                pay = 0.0
            desc = str(_gv(r, 'description', '') or '')
            if abs(pay) < 1e-9:
                dl = desc.lower()
                if 'adv' in dl and ('[' in dl or 'range' in dl or ':' in dl):
                    continue
            if ds not in per:
                per[ds] = pay
            else:
                if abs(pay) > 1e-9:
                    per[ds] = pay
        pay_days = []
        for ds, pay in per.items():
            try:
                pay_days.append((datetime.strptime(ds, '%Y-%m-%d').date(), float(pay or 0.0)))
            except Exception:
                continue
        pay_days.sort(key=lambda x: x[0])
        total_paid_cycle = sum(max(0.0, float(p or 0.0)) for _, p in pay_days)

        principal = _f(info.get('principal'))
        interest = _f(info.get('interest_amount'))
        total_to_pay = _f(info.get('total_to_pay'))
        computed_total = round(principal + interest, 2)
        if total_to_pay <= 0 or (interest > 0 and abs(total_to_pay - principal) < 0.01):
            total_to_pay = computed_total

        if lt_norm != '7x7':
            return round(max(0.0, float(total_to_pay) - float(total_paid_cycle)), 2)

        # 7x7 Generate Report split: interest-first, balance displayed is remaining principal.
        def _x7_daily_interest_for_balance(bal):
            try:
                b = float(bal or 0.0)
            except Exception:
                b = 0.0
            if b <= 0:
                return 0.0
            try:
                units = int((b + 999.999999) // 1000)
            except Exception:
                units = 0
            if units < 1:
                units = 1
            return float(units) * 7.0

        try:
            start_dt = datetime.strptime(str(cycle_start)[:10], '%Y-%m-%d').date()
        except Exception:
            start_dt = end_dt
        rem = float(principal or 0.0)
        arrears = 0.0
        prev_dt = start_dt - timedelta(days=1)
        for d, amt in pay_days:
            if d < start_dt:
                continue
            if d > end_dt:
                break
            try:
                gap = (d - prev_dt).days
            except Exception:
                gap = 1
            if gap <= 0:
                gap = 1
            interest_due = (_x7_daily_interest_for_principal(principal) * float(gap)) + float(arrears)
            interest_paid = min(float(amt or 0.0), float(interest_due))
            principal_pay_raw = max(0.0, float(amt or 0.0) - float(interest_paid))
            apply_p = min(principal_pay_raw, rem) if rem > 0 else 0.0
            rem = max(0.0, float(rem) - float(apply_p))
            arrears = max(0.0, float(interest_due) - float(interest_paid))
            prev_dt = d
            if rem <= 0.004:
                rem = 0.0
                break
        return round(max(0.0, float(rem)), 2)
    except Exception as e:
        try:
            _log_exc('collector_route.report_based_balance', e)
        except Exception:
            pass
        return None


def _spina_crc_norm_lt(_v):
    try:
        s = str(_v or "Regular").strip().lower().replace(" ", "").replace("×", "x")
    except Exception:
        s = "regular"
    return "7x7" if ("7x7" in s) else "Regular"


def _spina_crc_clean_reason(_v):
    try:
        s = str(_v or "").strip()
    except Exception:
        s = ""
    if not s:
        return ""
    try:
        s = re.sub(r"\[RC:[^\]]+\]", "", s, flags=re.I).strip()
        s = re.sub(r"\[ADV:[^\]]+\]", "", s, flags=re.I).strip()
        s = re.sub(r"\s+", " ", s).strip()
    except Exception:
        pass
    return s


def _spina_crc_load_collectors():
    """Load collector route definitions from data/collectors.json in any supported schema."""
    path = ""
    try:
        path = data_path("collectors.json")
    except Exception:
        try:
            path = os.path.join(DATA_DIR, "collectors.json")
        except Exception:
            path = "collectors.json"
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:
        raw = {}
    out = []
    try:
        if isinstance(raw, dict):
            for nm, rec in raw.items():
                areas = []
                notes = ""
                if isinstance(rec, dict):
                    areas = rec.get("areas") or rec.get("route") or []
                    notes = rec.get("notes") or ""
                elif isinstance(rec, list):
                    areas = rec
                areas = [str(a).strip() for a in (areas or []) if str(a).strip()]
                if str(nm or "").strip():
                    out.append({"name": str(nm).strip(), "areas": areas, "notes": str(notes or "")})
        elif isinstance(raw, list):
            for rec in raw:
                if isinstance(rec, dict):
                    nm = rec.get("name") or rec.get("collector") or rec.get("id") or ""
                    areas = rec.get("areas") or rec.get("route") or []
                    notes = rec.get("notes") or ""
                    areas = [str(a).strip() for a in (areas or []) if str(a).strip()]
                    if str(nm or "").strip():
                        out.append({"name": str(nm).strip(), "areas": areas, "notes": str(notes or "")})
                elif isinstance(rec, str) and rec.strip():
                    out.append({"name": rec.strip(), "areas": [], "notes": ""})
    except Exception:
        out = []
    return out


def _spina_crc_split_area(_area):
    try:
        if 'split_area_main_sub' in globals():
            return split_area_main_sub(_area)
    except Exception:
        pass
    a = str(_area or "").strip()
    for sep in [" | ", " / ", " - ", " > ", " : ", " — ", " – ", "|", "/", ">", ":"]:
        if sep in a:
            left, right = a.split(sep, 1)
            if left.strip() and right.strip():
                return left.strip(), right.strip()
    return a, ""


def _spina_crc_route_area_matches(route_area, client_area):
    """Match route area to client area, including MAIN-only collector routes covering subareas."""
    ra = str(route_area or "").strip()
    ca = str(client_area or "").strip()
    if not ra or not ca:
        return False
    nr = _spina_crc_norm_text(ra)
    nc = _spina_crc_norm_text(ca)
    if nr == nc:
        return True
    try:
        r_main, r_sub = _spina_crc_split_area(ra)
        c_main, c_sub = _spina_crc_split_area(ca)
        r_main_n = _spina_crc_norm_text(r_main)
        r_sub_n = _spina_crc_norm_text(r_sub)
        c_main_n = _spina_crc_norm_text(c_main)
        c_sub_n = _spina_crc_norm_text(c_sub)
        if r_main_n and r_main_n == c_main_n:
            # MAIN-only collector assignment covers all subareas under the same main area.
            if not r_sub_n:
                return True
            return bool(c_sub_n and r_sub_n == c_sub_n)
    except Exception:
        pass
    return False


def _spina_crc_collector_for_area(collectors, client_area):
    try:
        for col in (collectors or []):
            for ra in (col.get("areas") or []):
                if _spina_crc_route_area_matches(ra, client_area):
                    return col.get("name") or "Unassigned"
    except Exception:
        pass
    return "Unassigned"


def _spina_crc_key(uid, name, lt):
    uid = str(uid or "").strip()
    if uid:
        return ("UID", uid)
    return ("NAME", _spina_crc_norm_text(name), _spina_crc_norm_lt(lt))


def _spina_crc_fetch_close_rows(app, ds, collectors):
    """Build route rows with amount paid on the close date."""
    conn = getattr(getattr(app, "db", None), "conn", None)
    if conn is None:
        return []
    cur = conn.cursor()

    # Fetch active clients with a tolerant fallback for older schemas.
    try:
        cols = [r[1] for r in cur.execute("PRAGMA table_info(clients)").fetchall()]
    except Exception:
        cols = []
    wanted = ["client_uid", "name", "loan_type", "area", "payment_term", "payment_amount", "payment_mode"]
    select_cols = []
    for c in wanted:
        select_cols.append(c if c in cols else f"'' AS {c}")
    where = ""
    if "is_archived" in cols:
        where = "WHERE COALESCE(is_archived,0)=0"
    try:
        clients = cur.execute(
            "SELECT " + ", ".join(select_cols) + f" FROM clients {where} ORDER BY area COLLATE NOCASE, name COLLATE NOCASE"
        ).fetchall()
    except Exception:
        clients = []

    # Fetch all payments/entries for the closed day.
    try:
        txs = cur.execute(
            """
            SELECT client_uid, name, IFNULL(loan_type,'Regular') AS loan_type,
                   COALESCE(payment,0) AS payment, description
              FROM transactions
             WHERE date(date)=date(?)
             ORDER BY name COLLATE NOCASE, loan_type, id
            """,
            (ds,),
        ).fetchall()
    except Exception:
        txs = []

    paid_by_uid = {}
    paid_by_name = {}
    desc_by_key = {}
    tx_seen_keys = set()

    def _add_pay(store, key, pay, desc):
        try:
            store[key] = round(float(store.get(key, 0.0) or 0.0) + float(pay or 0.0), 2)
        except Exception:
            store[key] = float(pay or 0.0) if pay else 0.0
        d = _spina_crc_clean_reason(desc)
        if d:
            cur_txt = desc_by_key.get(key, "")
            if d not in cur_txt:
                desc_by_key[key] = (cur_txt + "; " + d).strip("; ").strip()

    for r in txs or []:
        try:
            d = dict(r)
        except Exception:
            d = {}
        uid = str(d.get("client_uid") or "").strip()
        nm = str(d.get("name") or "").strip()
        lt = _spina_crc_norm_lt(d.get("loan_type") or "Regular")
        pay = d.get("payment") or 0.0
        desc = d.get("description") or ""
        if uid:
            key = ("UID", uid)
            _add_pay(paid_by_uid, key, pay, desc)
            tx_seen_keys.add(key)
        key2 = ("NAME", _spina_crc_norm_text(nm), lt)
        _add_pay(paid_by_name, key2, pay, desc)
        tx_seen_keys.add(key2)

    out = []
    matched_tx_keys = set()
    for r in clients or []:
        try:
            d = dict(r)
        except Exception:
            d = {}
        nm = str(d.get("name") or "").strip()
        if not nm:
            continue
        lt = _spina_crc_norm_lt(d.get("loan_type") or "Regular")
        area = str(d.get("area") or "").strip()
        uid = str(d.get("client_uid") or "").strip()
        k_uid = ("UID", uid) if uid else None
        k_name = ("NAME", _spina_crc_norm_text(nm), lt)
        paid = 0.0
        reason = ""
        if k_uid and k_uid in paid_by_uid:
            paid = paid_by_uid.get(k_uid, 0.0)
            reason = desc_by_key.get(k_uid, "")
            matched_tx_keys.add(k_uid)
        elif k_name in paid_by_name:
            paid = paid_by_name.get(k_name, 0.0)
            reason = desc_by_key.get(k_name, "")
            matched_tx_keys.add(k_name)
        collector = _spina_crc_collector_for_area(collectors, area)
        term = str(d.get("payment_term") or "").strip()
        mode = str(d.get("payment_mode") or "").strip()
        try:
            sched_amt = float(d.get("payment_amount") or 0.0)
        except Exception:
            sched_amt = 0.0
        detail = ""
        try:
            parts = []
            if term:
                parts.append(term)
            if sched_amt:
                parts.append(_spina_crc_fmt_money(sched_amt))
            if mode:
                parts.append(mode)
            detail = " / ".join(parts)
        except Exception:
            detail = ""
        out.append({
            "collector": collector,
            "area": area or "-",
            "name": nm,
            "loan_type": lt,
            "paid": round(float(paid or 0.0), 2),
            "reason": reason,
            "detail": detail,
        })

    # Include payment rows that are not matched to active clients, so the close copy still ties to the day total.
    for r in txs or []:
        try:
            d = dict(r)
        except Exception:
            d = {}
        uid = str(d.get("client_uid") or "").strip()
        nm = str(d.get("name") or "").strip()
        lt = _spina_crc_norm_lt(d.get("loan_type") or "Regular")
        k = ("UID", uid) if uid else ("NAME", _spina_crc_norm_text(nm), lt)
        k2 = ("NAME", _spina_crc_norm_text(nm), lt)
        if (k in matched_tx_keys) or (k2 in matched_tx_keys):
            continue
        # Avoid duplicate unmatched rows when both UID and NAME keys are in tx_seen_keys.
        matched_tx_keys.add(k)
        if k2:
            matched_tx_keys.add(k2)
        try:
            pay = float(d.get("payment") or 0.0)
        except Exception:
            pay = 0.0
        if abs(pay) < 0.005:
            continue
        out.append({
            "collector": "Unassigned",
            "area": "-",
            "name": nm or "Unknown payment row",
            "loan_type": lt,
            "paid": round(pay, 2),
            "reason": _spina_crc_clean_reason(d.get("description") or ""),
            "detail": "payment row not matched to active client",
        })

    try:
        out.sort(key=lambda x: (str(x.get("collector") or "").lower(), str(x.get("area") or "").lower(), str(x.get("name") or "").lower(), str(x.get("loan_type") or "")))
    except Exception:
        pass
    return out


def _spina_crc_wrap(c, text, width, font="Helvetica", size=8.0):
    try:
        words = str(text or "").split()
    except Exception:
        words = []
    if not words:
        return [""]
    lines = []
    cur = ""
    for w in words:
        test = (cur + " " + w).strip()
        try:
            ok = c.stringWidth(test, font, size) <= width
        except Exception:
            ok = len(test) * size * 0.5 <= width
        if ok or not cur:
            cur = test
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [""]


def _spina_crc_copy_existing_route_pdfs(ds, out_dir):
    copied = []
    try:
        import glob as _glob
        import shutil as _shutil
        roots = []
        for r in [globals().get("PDF_DIR"), os.path.join(APP_DIR, "Client_Statements") if 'APP_DIR' in globals() else None]:
            if r and str(r) not in roots:
                roots.append(str(r))
        try:
            rr = data_path("reports")
            if rr not in roots:
                roots.append(rr)
        except Exception:
            pass
        for root in roots:
            if not root or not os.path.isdir(root):
                continue
            for pat in (f"*CollectorRoute*{ds}*.pdf", f"*FullDailyLedger*{ds}*.pdf"):
                for src in _glob.glob(os.path.join(root, pat)):
                    try:
                        if os.path.abspath(os.path.dirname(src)) == os.path.abspath(out_dir):
                            continue
                        base = os.path.basename(src)
                        dst = os.path.join(out_dir, "OriginalCopy_" + base)
                        if not os.path.exists(dst):
                            _shutil.copy2(src, dst)
                        copied.append(dst)
                    except Exception:
                        pass
    except Exception:
        pass
    return copied


def _spina_crc_build_paid_cache_for_date(app, ds):
    """Return {(lower_name, lower_loan_type): paid_amount} for the closed date."""
    out = {}
    try:
        conn = getattr(getattr(app, "db", None), "conn", None)
        if conn is None:
            return out
        rows = conn.execute(
            """
            SELECT name,
                   CASE WHEN LOWER(REPLACE(REPLACE(IFNULL(loan_type,'Regular'),' ',''),'×','x')) LIKE '%7x7%' THEN '7x7' ELSE 'regular' END AS lt,
                   COALESCE(SUM(COALESCE(payment,0)),0) AS paid
              FROM transactions
             WHERE date(date)=date(?)
             GROUP BY UPPER(TRIM(name)), lt
            """,
            (str(ds or '')[:10],),
        ).fetchall()
        for r in rows or []:
            try:
                nm = str(r['name'] if hasattr(r, 'keys') else r[0] or '').strip().lower()
                lt = str(r['lt'] if hasattr(r, 'keys') else r[1] or 'regular').strip().lower()
                paid = float(r['paid'] if hasattr(r, 'keys') else r[2] or 0.0)
                if nm:
                    out[(nm, lt)] = round(paid, 2)
            except Exception:
                continue
    except Exception as __spina_exc:
        try:
            _log_suppressed_once('closed_route_paid_cache_failed', 'closed route paid cache failed', __spina_exc)
        except Exception:
            pass
    return out


def _spina_crc_active_filtered_areas_for_collector(app, areas):
    """Match the Collector Route screen filtering so blank/archived-only areas are skipped."""
    try:
        def _route_norm(_s):
            return " ".join(str(_s or '').split()).strip().lower()
        cur = app.db.conn.cursor()
        active_rows = cur.execute(
            "SELECT DISTINCT TRIM(area) AS a FROM clients WHERE IFNULL(TRIM(area),'')<>'' AND COALESCE(is_archived,0)=0 ORDER BY a COLLATE NOCASE"
        ).fetchall()
        active_areas = []
        for r in active_rows or []:
            try:
                a = r['a'] if hasattr(r, 'keys') else r[0]
            except Exception:
                a = ''
            a = str(a or '').strip()
            if a:
                active_areas.append(a)
        active_full, active_main, active_pairs = set(), set(), set()
        for a in active_areas:
            full = _route_norm(a)
            if full:
                active_full.add(full)
            try:
                ma, su = split_area_main_sub(a)
            except Exception:
                ma, su = a, ''
            mn, sn = _route_norm(ma), _route_norm(su)
            if mn:
                active_main.add(mn)
            if mn and sn:
                active_pairs.add((mn, sn))
        filtered, seen = [], set()
        for ra in areas or []:
            ra = str(ra or '').strip()
            if not ra:
                continue
            try:
                rma, rsu = split_area_main_sub(ra)
            except Exception:
                rma, rsu = ra, ''
            rn, rmn, rsn = _route_norm(ra), _route_norm(rma), _route_norm(rsu)
            ok = False
            if rsn:
                ok = ((rmn, rsn) in active_pairs) or (rn in active_full)
            else:
                ok = (rmn in active_main) or (rn in active_full)
            if ok and ra not in seen:
                filtered.append(ra)
                seen.add(ra)
        return filtered
    except Exception:
        return [str(a).strip() for a in (areas or []) if str(a).strip()]


def _spina_save_closed_collector_route_copy_same_format(self, date_s, rec=None, collector_rows=None, open_after=False):
    """Save final closed Collector Route copy using the SAME Collector Route PDF layout.

    Difference from normal print: the payment columns are filled with the actual amount
    paid on the closed date, and the PDF is saved silently under data/Closed_Collector_Routes.
    """
    import os as _os
    import shutil as _shutil
    from datetime import datetime as _dt

    ds = str(date_s or '').strip()[:10]
    try:
        _dt.strptime(ds, '%Y-%m-%d')
    except Exception:
        raise ValueError('Use date format YYYY-MM-DD.')

    if rec is None:
        try:
            rec = self.db.get_databank_day_close(ds) if hasattr(self, 'db') else None
        except Exception:
            rec = None
    if not rec:
        raise ValueError('No Daily Close record exists yet for that date.')

    try:
        base_dir = data_path('Closed_Collector_Routes', ds)
    except Exception:
        base_dir = _os.path.join(DATA_DIR if 'DATA_DIR' in globals() else _os.getcwd(), 'Closed_Collector_Routes', ds)
    _os.makedirs(base_dir, exist_ok=True)

    collectors = _spina_crc_load_collectors() if '_spina_crc_load_collectors' in globals() else []
    paid_cache = _spina_crc_build_paid_cache_for_date(self, ds)
    saved_paths = []
    old_pdf_dir = globals().get('PDF_DIR', None)

    def _safe_tag(_v, fallback='Collector'):
        try:
            return _safe_filename_component(_v, fallback=fallback)
        except Exception:
            return str(_v or fallback).replace(' ', '_')

    def _generate_one(collector_name, areas):
        collector_name = str(collector_name or 'All Collectors').strip() or 'All Collectors'
        areas = [str(a).strip() for a in (areas or []) if str(a).strip()]
        if not areas:
            return None
        # Use the exact Collector Route generator, but force date/output and suppress dialogs/opening.
        old_attrs = {}
        for attr in (
            '_ledger_forced_areas', '_ledger_forced_collector_name', '_route_payment_two_cols',
            '_ledger_silent_route_copy', '_ledger_forced_date', '_ledger_forced_output_dir',
            '_ledger_forced_paper_label', '_ledger_forced_orientation', '_ledger_closed_copy_show_paid',
            '_ledger_closed_paid_cache', '_last_printed_daily_ledger_path'
        ):
            try:
                old_attrs[attr] = (True, getattr(self, attr))
            except Exception:
                old_attrs[attr] = (False, None)
        try:
            self._ledger_forced_areas = areas
            self._ledger_forced_collector_name = collector_name
            self._route_payment_two_cols = True
            self._ledger_silent_route_copy = True
            self._ledger_forced_date = ds
            self._ledger_forced_output_dir = base_dir
            self._ledger_forced_paper_label = 'Folio (8 x 13 in)'
            self._ledger_forced_orientation = 'Portrait'
            self._ledger_closed_copy_show_paid = True
            self._ledger_closed_paid_cache = paid_cache
            self._last_printed_daily_ledger_path = ''
            try:
                globals()['PDF_DIR'] = base_dir
            except Exception:
                pass
            self.print_full_daily_ledger()
            p = str(getattr(self, '_last_printed_daily_ledger_path', '') or '')
            if p and _os.path.exists(p):
                stamp = _dt.now().strftime('%H%M%S')
                final_name = f"ClosedCollectorRoute_{_safe_tag(collector_name)}_{ds}_{stamp}.pdf"
                final_path = _os.path.join(base_dir, final_name)
                try:
                    if _os.path.abspath(p) != _os.path.abspath(final_path):
                        if _os.path.exists(final_path):
                            _os.remove(final_path)
                        _shutil.move(p, final_path)
                    p = final_path
                except Exception:
                    pass
                return p
            return None
        finally:
            for attr, (exists, value) in old_attrs.items():
                try:
                    if exists:
                        setattr(self, attr, value)
                    else:
                        if hasattr(self, attr):
                            delattr(self, attr)
                except Exception:
                    pass

    if collectors:
        for col in collectors:
            try:
                cname = str((col or {}).get('name') or '').strip()
                areas = list((col or {}).get('areas') or [])
                areas = _spina_crc_active_filtered_areas_for_collector(self, areas)
                if not cname or not areas:
                    continue
                p = _generate_one(cname, areas)
                if p:
                    saved_paths.append(p)
            except Exception as __spina_exc:
                try:
                    _log_suppressed_once('closed_route_generate_one_failed', 'closed route same-format collector copy failed', __spina_exc)
                except Exception:
                    pass
    else:
        # Fallback: use all active areas in the same ledger layout.
        try:
            cur = self.db.conn.cursor()
            rows = cur.execute("SELECT DISTINCT TRIM(area) AS a FROM clients WHERE IFNULL(TRIM(area),'')<>'' AND COALESCE(is_archived,0)=0 ORDER BY a COLLATE NOCASE").fetchall()
            all_areas = [str((r['a'] if hasattr(r, 'keys') else r[0]) or '').strip() for r in rows]
        except Exception:
            all_areas = []
        p = _generate_one('All Collectors', all_areas)
        if p:
            saved_paths.append(p)

    try:
        if old_pdf_dir:
            globals()['PDF_DIR'] = old_pdf_dir
    except Exception:
        pass

    if not saved_paths:
        raise RuntimeError('No collector route PDF was generated. Check collectors.json and active client areas.')

    # Small text manifest only; the PDFs remain the same Collector Route format.
    try:
        manifest = _os.path.join(base_dir, f'ClosedCollectorRoute_{ds}_MANIFEST.txt')
        def _rec_get(k, default=''):
            try:
                return rec.get(k, default)
            except Exception:
                try:
                    return dict(rec).get(k, default)
                except Exception:
                    return default
        with open(manifest, 'w', encoding='utf-8') as f:
            f.write(f'Closed Collector Route copies for {ds}\n')
            f.write(f'Expected: {_rec_get("expected_amount", "")}\n')
            f.write(f'Actual / Amount Paid Today: {_rec_get("actual_cash", "")}\n')
            f.write(f'Variance: {_rec_get("variance", "")}\n')
            f.write('\nFiles:\n')
            for p in saved_paths:
                f.write('- ' + _os.path.basename(p) + '\n')
    except Exception:
        pass

    try:
        self._last_closed_collector_route_copy_path = saved_paths[0] if len(saved_paths) == 1 else base_dir
    except Exception:
        pass
    if open_after:
        try:
            _open_path(base_dir if len(saved_paths) != 1 else saved_paths[0])
        except Exception:
            pass
    return base_dir if len(saved_paths) != 1 else saved_paths[0]


COLLECTOR_ROUTE_METHOD_NAMES = ('_spina_route_adv_marker_for', '_normalize_client_name_for_lookup', 'print_collector_route_daily_ledger', 'print_full_daily_ledger', '_spina_route_notice_norm_lt', '_spina_route_notice_key', '_spina_route_notice_load', '_spina_route_notice_save', '_spina_route_notice_upsert', '_spina_route_balance_like_generate_report', '_spina_crc_norm_lt', '_spina_crc_clean_reason', '_spina_crc_load_collectors', '_spina_crc_split_area', '_spina_crc_route_area_matches', '_spina_crc_collector_for_area', '_spina_crc_key', '_spina_crc_fetch_close_rows', '_spina_crc_wrap', '_spina_crc_copy_existing_route_pdfs', '_spina_crc_build_paid_cache_for_date', '_spina_crc_active_filtered_areas_for_collector', '_spina_save_closed_collector_route_copy_same_format')
