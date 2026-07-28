"""Client statement generation orchestration extracted in Wave 67."""
from __future__ import annotations

_CLIENT_STATEMENT_GENERATION_DEPENDENCIES = {}
_PROTECTED_GLOBALS = {
    '__name__', '__doc__', '__package__', '__loader__', '__spec__',
    '__file__', '__cached__', '__builtins__',
    '_CLIENT_STATEMENT_GENERATION_DEPENDENCIES', '_PROTECTED_GLOBALS',
    'CLIENT_STATEMENT_GENERATION_METHODS',
    'configure_client_statement_generation_dependencies',
    'generate_pdf_selected',
}

def configure_client_statement_generation_dependencies(namespace):
    _CLIENT_STATEMENT_GENERATION_DEPENDENCIES.clear()
    _CLIENT_STATEMENT_GENERATION_DEPENDENCIES.update(namespace)
    for name, value in namespace.items():
        if name not in _PROTECTED_GLOBALS:
            globals()[name] = value

CLIENT_STATEMENT_GENERATION_METHODS = {"generate_pdf_selected": {"calls": ["_can_use_dir", "_date.today", "_date.today.replace", "_date.today.replace.strftime", "_de.strftime", "_ds.strftime", "_dt.strptime", "_dt.strptime.date", "_effective_cycle_start", "_json.dumps", "_log_exc", "_log_suppressed_once", "_open_path", "_safe_filename_component", "_settings.get", "_td", "_time.strftime", "bool", "bucket.append", "date.today", "date.today.replace", "date.today.replace.strftime", "date.today.strftime", "f.write", "generate_client_pdf", "get", "get_client_notes_in_range", "getattr", "getattr.get", "int", "join", "load_settings", "messagebox.showerror", "messagebox.showwarning", "meta.get", "open", "os.makedirs", "os.path.join", "self._mode_filter", "self._run_long_task", "self.db.get_client_info", "self.db.get_client_link_meta", "self.end_date_var.get", "self.reports_tree.item", "self.reports_tree.selection", "self.start_date_var.get", "self.status_var.set", "str", "str.strip", "strftime", "strip"], "db_calls": ["self.db.get_client_info", "self.db.get_client_link_meta"], "dedented_sha256": "d4ec35bd06b51915de73d04eade629d05cbaa1353565fb9b41a8bbe5f7ae06e8", "lines": 258, "signature": "self", "source_sha256": "8225a64ebbaf150af577a34f185fafbef8d4310d56132a45a86e53acebe5e2df"}}

def generate_pdf_selected(self):
    """Generate a client statement PDF without freezing the UI."""
    sel = self.reports_tree.selection()
    if not sel:
        messagebox.showwarning('Select', 'Please select one client to generate a report.')
        return

    name = self.reports_tree.item(sel[0], 'values')[0]

    lt = self._mode_filter()
    info = self.db.get_client_info(name, loan_type=lt) or {}

    def _effective_cycle_start(_row):
        """Normalize the current cycle start the same way the client screen and report body do.
        This prevents renewed clients from inheriting a stale earlier report start range.
        """
        try:
            from datetime import datetime as _dt, timedelta as _td, date as _date

            _ps = str((_row or {}).get('payment_start_date') or '').strip()[:10]
            _dr = str((_row or {}).get('date_released') or '').strip()[:10]
            try:
                _off = int((_row or {}).get('pay_start_offset_days') or 0)
            except Exception:
                _off = 0
            _off = 1 if _off >= 1 else 0

            _start = ''
            if _ps:
                try:
                    _dt.strptime(_ps, '%Y-%m-%d')
                    _start = _ps
                except Exception:
                    _start = ''

            if _start and _dr:
                try:
                    _dt.strptime(_dr, '%Y-%m-%d')
                    if _start < _dr or (_off == 1 and _start == _dr):
                        _start = ''
                except Exception:
                    pass

            if not _start and _dr:
                try:
                    _start = (_dt.strptime(_dr, '%Y-%m-%d').date() + _td(days=_off)).strftime('%Y-%m-%d')
                except Exception:
                    _start = _dr

            if not _start:
                _start = _date.today().replace(day=1).strftime('%Y-%m-%d')
            return _start
        except Exception:
            try:
                return date.today().replace(day=1).strftime('%Y-%m-%d')
            except Exception:
                return ''

    cycle_start = _effective_cycle_start(info)

    # Determine the export date range from the Reports tab.
    # Respect the user's typed range exactly; only fill missing values locally for this
    # export and never write the computed range back into the Reports fields.
    try:
        s = (self.start_date_var.get() or '').strip()
    except Exception:
        s = ''
    try:
        e = (self.end_date_var.get() or '').strip()
    except Exception:
        e = ''

    if not s:
        s = cycle_start
    if not e:
        e = date.today().strftime('%Y-%m-%d')

    # Validate date range (YYYY-MM-DD)
    try:
        from datetime import datetime as _dt
        _ds = _dt.strptime(str(s)[:10], '%Y-%m-%d').date()
        _de = _dt.strptime(str(e)[:10], '%Y-%m-%d').date()
    except Exception:
        messagebox.showerror('Invalid Date', 'Please use YYYY-MM-DD for Start/End dates (example: 2026-02-06).')
        return

    # Auto-swap if end < start to match range picker behavior, but keep it local to export.
    if _de < _ds:
        _ds, _de = _de, _ds

    # Respect a manually typed Start Date exactly.
    # Only fall back to the current cycle start when Start Date was left blank.
    try:
        _user_typed_start = bool((self.start_date_var.get() or '').strip())
    except Exception:
        _user_typed_start = False
    try:
        _cycle_ds = _dt.strptime(str(cycle_start)[:10], '%Y-%m-%d').date() if cycle_start else None
    except Exception:
        _cycle_ds = None
    if _cycle_ds and (not _user_typed_start) and _ds < _cycle_ds:
        _ds = _cycle_ds
        if _de < _ds:
            _de = _ds

    s = _ds.strftime('%Y-%m-%d')
    e = _de.strftime('%Y-%m-%d')

    safe = _safe_filename_component(name, fallback='client')
    safe_lt = _safe_filename_component(lt or 'Regular', fallback='Regular')

    # --- Auto-save per-client, track every generated report ---
    # Choose root for saved PDFs:
    # - If settings["reports_root"] is set and writable, use it
    # - Else use the app's default PDF_DIR
    _settings = {}
    try:
        _settings = load_settings() or {}
    except Exception:
        _settings = {}
    _root = ""
    try:
        _root = str(_settings.get("reports_root") or "").strip()
    except Exception:
        _root = ""
    if _root and _can_use_dir(_root):
        reports_root = _root
    else:
        reports_root = PDF_DIR

    # Use a per-loan-type folder, then per-client folder (name + client_uid suffix when available)
    client_uid = ""
    try:
        client_uid = str((info or {}).get("client_uid") or "").strip()
    except Exception:
        client_uid = ""
    try:
        meta = self.db.get_client_link_meta(name, loan_type=lt)
        if meta:
            client_uid = str(meta.get("client_uid") or "").strip() or client_uid
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_0410', 'suppressed exception excpass_0410', __spina_exc)
        pass

    safe_uid = ""
    try:
        if client_uid:
            safe_uid = _safe_filename_component(client_uid, fallback="", max_len=18)
    except Exception:
        safe_uid = ""

    client_folder_name = f"{safe}__{safe_uid}" if safe_uid else safe
    client_dir = os.path.join(reports_root, safe_lt, client_folder_name)
    try:
        os.makedirs(client_dir, exist_ok=True)
    except Exception:
        # fallback to PDF_DIR if custom root fails
        client_dir = os.path.join(PDF_DIR, safe_lt, client_folder_name)
        try:
            os.makedirs(client_dir, exist_ok=True)
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0411', 'suppressed exception excpass_0411', __spina_exc)
            pass

    import time as _time
    ts = _time.strftime('%Y%m%d_%H%M%S')
    safe_s = _safe_filename_component(str(s)[:10], fallback='start', max_len=20)
    safe_e = _safe_filename_component(str(e)[:10], fallback='end', max_len=20)
    out = os.path.join(
        client_dir,
        f'ClientStatement_{safe_lt}_{safe}_{safe_s}_to_{safe_e}_{ts}.pdf'
    )

    page_size_name = (getattr(self, 'report_page_size_var', None).get()
                      if getattr(self, 'report_page_size_var', None) else 'A4')

    def _work():
        # Build note text for THIS loan type only (no shared / no other-type notes)
        note = ""
        try:
            bucket = []
            client_uid = None
            person_uid = None
            try:
                meta = self.db.get_client_link_meta(name, loan_type=lt)
                if meta:
                    client_uid = (meta.get('client_uid') or '').strip() or None
                    person_uid = (meta.get('person_uid') or '').strip() or None
            except Exception as _e:
                try:
                    _log_exc('notes:pdf_link_meta', _e)
                except Exception as __spina_exc:
                    _log_suppressed_once('excpass_0412', 'suppressed exception excpass_0412', __spina_exc)
                    pass

            for _d, _t in get_client_notes_in_range(
                name, s, e,
                loan_type=lt,
                include_shared=False,
                include_type=True,
                include_other_type=False,
                client_uid=client_uid,
                person_uid=person_uid,
            ):
                bucket.append(f"{_d}: {_t}" if _d else _t)
            note = "\n".join(bucket)
        except Exception:
            note = ""

        generate_client_pdf(
            self.db, name, s, e, out,
            note_text=note,
            loan_type=lt,
            page_size_name=page_size_name,
        )

        # Track generated reports per client (append-only log)
        try:
            import json as _json
            idx_path = os.path.join(client_dir, "reports_index.jsonl")
            rec = {
                "generated_at": _time.strftime("%Y-%m-%d %H:%M:%S"),
                "start_date": str(s)[:10],
                "end_date": str(e)[:10],
                "loan_type": lt,
                "client_name": name,
                "client_uid": client_uid or None,
                "pdf_path": out,
                "page_size": page_size_name,
            }
            with open(idx_path, "a", encoding="utf-8") as f:
                f.write(_json.dumps(rec, ensure_ascii=False) + "\n")
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0413', 'suppressed exception excpass_0413', __spina_exc)
            pass

        return out

    def _done(out_path):
        try:
            self.status_var.set('Report generated successfully.')
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0414', 'suppressed exception excpass_0414', __spina_exc)
            pass
        try:
            _open_path(out_path)
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0415', 'suppressed exception excpass_0415', __spina_exc)
            pass

    def _err(ex):
        try:
            messagebox.showerror('PDF Error', f'Failed to generate PDF for {name}: {ex}\n\nSee log: data/spina_app.log')
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0416', 'suppressed exception excpass_0416', __spina_exc)
            pass

    self._run_long_task(f'Generating PDF for {name}...', _work, on_success=_done, on_error=_err)
