"""Data Bank shell and layout helpers extracted from the SPINA desktop entry module."""

from __future__ import annotations


def _noop_log(*args, **kwargs):
    return None


_log_suppressed_once = _noop_log
_log_ignored = _noop_log


def configure_data_bank_shell_dependencies(*, log_suppressed_once, log_ignored):
    """Bind application-owned logging helpers used by Data Bank presentation code."""
    global _log_suppressed_once, _log_ignored
    _log_suppressed_once = log_suppressed_once or _noop_log
    _log_ignored = log_ignored or _noop_log


def _looks_like_data_grid(self, tv):
    """Heuristic: columns contain 'client' + 'area' and many day columns (d1..d31 or numeric headings)."""
    try:
        cols = list(tv["columns"])
    except Exception as __spina_exc:
        __spina_logger = globals().get('_log_suppressed_once')
        if callable(__spina_logger):
            __spina_logger('silent_ui_13176__looks_like_data_grid', 'suppressed UI/startup exception at line 13176', __spina_exc)
        return False
    cols_l = [str(c).lower() for c in cols]
    if not cols:
        return False
    # Must have at least two non-day columns
    has_client = any("client" in c for c in cols_l)
    has_area   = any("area" in c for c in cols_l)
    # Count day-like columns
    day_like = 0
    for c in cols:
        cl = str(c).lower()
        if cl.startswith("d") and cl[1:].isdigit():
            day_like += 1
    # If headings are numeric, the column names might be generic: check heading text
    if day_like < 10:
        try:
            for i, c in enumerate(cols, start=1):
                try:
                    txt = str(tv.heading(c).get("text", "")).strip()
                    if txt.isdigit():
                        day_like += 1
                except Exception:
                    continue
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0245', 'suppressed exception excpass_0245', __spina_exc)
            pass
    return has_client and has_area and day_like >= 10


def _locate_data_tree(self):
    """Find and memoize the actual Treeview used by the Data grid."""
    try:
        import tkinter.ttk as ttk
        # If already valid and exists, return it
        tv = getattr(self, "days_tree", None)
        if tv and str(tv.winfo_class()).lower() == "treeview":
            try:
                tv["columns"]
                return tv
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_0246', 'suppressed exception excpass_0246', __spina_exc)
                pass
        # Walk the UI starting at root to find a matching Treeview
        for w in self._walk_widgets(self.root):
            try:
                if str(w.winfo_class()).lower() == "treeview":
                    if self._looks_like_data_grid(w):
                        self.days_tree = w
                        return w
            except Exception:
                continue
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_0247', 'suppressed exception excpass_0247', __spina_exc)
        pass
    return None


def _ensure_databank_edit_bindings(self):
    """Bind double-click/F2 editing for Data grid (auto-detected) only once per Treeview instance."""
    tv = self._locate_data_tree()
    if tv is None:
        return
    # Use a per-instance flag on the widget itself to avoid rebinding
    try:
        if getattr(tv, "_edit_bindings_done", False):
            return
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_0248', 'suppressed exception excpass_0248', __spina_exc)
        pass
    try:
        tv.bind('<Double-1>', self._begin_cell_edit)
        tv.bind('<F2>', self._begin_cell_edit, add='+')
        tv.bind('<Button-1>', self._remember_cell_click, add='+')
        tv.bind('<Delete>', self.delete_selected_cell, add='+')
        try:
            tv.bind('<MouseWheel>', self._on_mousewheel_sync, add='+')
            tv.bind('<Button-4>', self._on_mousewheel_sync, add='+')
            tv.bind('<Button-5>', self._on_mousewheel_sync, add='+')
        except Exception as e:
            _log_ignored("ui.bind failed", e, key="ui.bind_failed")
        try:
            setattr(tv, "_edit_bindings_done", True)
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0249', 'suppressed exception excpass_0249', __spina_exc)
            pass
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_0250', 'suppressed exception excpass_0250', __spina_exc)
        pass


def _show_audit_tab(self):
    try:
        self.nb.add(self.tab_audit, text='Audit')
    except Exception:
        try:
            self.nb.tab(self.tab_audit, text='Audit')
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_audit_tab_show', 'suppressed exception excpass_audit_tab_show', __spina_exc)
            pass


def _hide_audit_tab(self):
    try:
        self.nb.hide(self.tab_audit)
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_audit_tab_hide', 'suppressed exception excpass_audit_tab_hide', __spina_exc)
        pass


def _resize_databank_columns(self, *_):
    """Resize Data Bank columns responsively.

    Supports 'freeze panes' layout:
    - name_tree shows Client + Area (fixed, no horizontal scroll)
    - days_tree shows day columns with horizontal scroll
    """
    try:
        name_tv = getattr(self, "name_tree", None)
        days_tv = getattr(self, "days_tree", None)
        if not days_tv:
            return

        # Determine days list from columns (prefer explicit day cols)
        cols = list(getattr(days_tv, "cget", lambda k: ())("columns") or days_tv["columns"])
        day_cols = [c for c in cols if str(c).lower().startswith("d") and str(c)[1:].isdigit()]

        # Basic guards
        if not day_cols:
            return

        # Available width inside container
        try:
            total_w = max(400, int(self.inner.winfo_width()))
        except Exception:
            total_w = 900

        # Left pane widths (Client + Area)
        client_w = 280
        area_w = 150

        # Auto-fit area a little based on content (from name_tv if available, else days_tv)
        try:
            import tkinter.font as tkfont
            f = tkfont.nametofont("TkDefaultFont")
            sample = []
            tv_for_area = name_tv if name_tv else days_tv
            for iid in tv_for_area.get_children()[:200]:
                try:
                    sample.append(str(tv_for_area.set(iid, "area")))
                except Exception as __spina_exc:
                    _log_suppressed_once('excpass_0372', 'suppressed exception excpass_0372', __spina_exc)
                    pass
            if sample:
                m = max(sample, key=len)
                area_w = min(240, max(110, f.measure(m) + 34))
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0373', 'suppressed exception excpass_0373', __spina_exc)
            pass

        if name_tv:
            try:
                name_tv.column("client", width=client_w, minwidth=160, stretch=False, anchor="w")
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_0374', 'suppressed exception excpass_0374', __spina_exc)
                pass
            try:
                name_tv.column("area", width=area_w, minwidth=110, stretch=False, anchor="w")
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_0375', 'suppressed exception excpass_0375', __spina_exc)
                pass

        # Keep client/area hidden in the right pane (still present for logic, but 0-width)
        try:
            days_tv.column("client", width=0, minwidth=0, stretch=False)
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0376', 'suppressed exception excpass_0376', __spina_exc)
            pass
        try:
            days_tv.column("area", width=0, minwidth=0, stretch=False)
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0377', 'suppressed exception excpass_0377', __spina_exc)
            pass

        # Day column width calculation for the right pane
        # Reserve left pane + scrollbar gutter
        reserve = client_w + area_w + 26  # scrollbar + padding
        avail_days_w = max(200, total_w - reserve)
        day_min = 64
        per = max(day_min, int(avail_days_w / max(1, len(day_cols))))

        for c in day_cols:
            try:
                days_tv.column(c, width=per, minwidth=day_min, stretch=False, anchor="center")
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_0378', 'suppressed exception excpass_0378', __spina_exc)
                pass
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_0379', 'suppressed exception excpass_0379', __spina_exc)
        pass
