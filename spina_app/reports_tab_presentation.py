"""Reports tab presentation extracted in Wave 64."""
from __future__ import annotations

_REPORTS_TAB_DEPENDENCIES = {}
_PROTECTED_GLOBALS = {
    '__name__', '__doc__', '__package__', '__loader__', '__spec__',
    '__file__', '__cached__', '__builtins__',
    '_REPORTS_TAB_DEPENDENCIES', '_PROTECTED_GLOBALS',
    'REPORTS_TAB_PRESENTATION_METHODS',
    'configure_reports_tab_dependencies', '_build_reports_tab',
}

def configure_reports_tab_dependencies(namespace):
    _REPORTS_TAB_DEPENDENCIES.clear()
    _REPORTS_TAB_DEPENDENCIES.update(namespace)
    for name, value in namespace.items():
        if name not in _PROTECTED_GLOBALS:
            globals()[name] = value

REPORTS_TAB_PRESENTATION_METHODS = {"_build_reports_tab": {"calls": ["_anchor.get", "_apply_report_range_from_fields", "_dt.strptime", "_dt.strptime.date", "_hdr.get", "_load_ledger_prefs", "_log_ignored", "_log_suppressed_once", "_prefs.get", "_ps_cb.bind", "_ps_cb.pack", "_rg_row.pack", "_save_ledger_prefs", "_save_reports_page_size", "_sync_reports_range", "_w.get", "body.pack", "bool", "box.pack", "box.pack_forget", "box.winfo_manager", "btn.configure", "c.title", "date.today", "date.today.replace", "date.today.replace.strftime", "date.today.strftime", "de.strftime", "ds.strftime", "getattr", "hscroll.pack", "messagebox.showerror", "notes_scroll.pack", "notes_text_row.pack", "notes_top.pack", "pick_date", "pick_date_range", "self._auto_load_report_note", "self._configure_tree_stripes", "self._set_report_note_text", "self.date_range_var.set", "self.end_date_var.get", "self.end_date_var.set", "self.end_date_var.trace_add", "self.note_date_var.get", "self.note_date_var.trace_add", "self.refresh_reports", "self.report_end_entry.bind", "self.report_end_entry.pack", "self.report_note_txt.configure", "self.report_note_txt.focus_set", "self.report_note_txt.pack", "self.report_notes_btn.configure", "self.report_notes_btn.pack", "self.report_page_size_var.get", "self.report_page_size_var.trace_add", "self.report_start_entry.bind", "self.report_start_entry.pack", "self.reports_notes_box.pack", "self.reports_notes_box.pack_forget", "self.reports_notes_sep.pack", "self.reports_notes_sep.pack_forget", "self.reports_tree.bind", "self.reports_tree.column", "self.reports_tree.configure", "self.reports_tree.heading", "self.reports_tree.pack", "self.search_reports_var.set", "self.search_reports_var.trace_add", "self.start_date_var.get", "self.start_date_var.set", "self.start_date_var.trace_add", "sep.pack", "sep.pack_forget", "strip", "tk.BooleanVar", "tk.StringVar", "tk.Text", "top1.pack", "top2.pack", "tree_frame.pack", "ttk.Button", "ttk.Button.pack", "ttk.Checkbutton", "ttk.Checkbutton.pack", "ttk.Combobox", "ttk.Entry", "ttk.Entry.pack", "ttk.Frame", "ttk.Frame.pack", "ttk.Label", "ttk.Label.pack", "ttk.LabelFrame", "ttk.Scrollbar", "ttk.Separator", "ttk.Separator.pack", "ttk.Treeview", "vscroll.pack"], "db_calls": [], "dedented_sha256": "acd429b0c746c0bddc6347d4c54a790d9e1acc2bc93be3715a635af235636591", "lines": 338, "signature": "self", "source_sha256": "7ee5ddb185c7dd34a0bd60c3219e72d1c5cbe2314b547b91f2946bca13a95bb3"}}

def _build_reports_tab(self):
    frm = self.tab_reports

    top1 = ttk.Frame(frm, style='Toolbar.TFrame')
    top1.pack(fill='x', pady=(0, 6))
    top2 = ttk.Frame(frm, style='Toolbar.TFrame')
    top2.pack(fill='x', pady=(0, 10))

    ttk.Label(top1, text='Reports', style='Section.TLabel').pack(side='left', padx=6)
    ttk.Label(top1, text='Search:').pack(side='left', padx=(10, 6))
    self.search_reports_var = tk.StringVar()
    ttk.Entry(top1, textvariable=self.search_reports_var, width=28).pack(side='left')
    self.search_reports_var.trace_add('write', lambda *_: self.refresh_reports())
    ttk.Button(top1, text='Clear', width=7, command=lambda: self.search_reports_var.set('')).pack(side='left', padx=(4, 10))

    self.show_archived_reports_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(top1, text='Show Archived', variable=self.show_archived_reports_var, command=self.refresh_reports).pack(side='left', padx=(0, 12))

    ttk.Label(top1, text='Date Range:').pack(side='left', padx=(0, 4))
    self.start_date_var = tk.StringVar(value=date.today().replace(day=1).strftime('%Y-%m-%d'))
    self.end_date_var = tk.StringVar(value=date.today().strftime('%Y-%m-%d'))
    self.date_range_var = tk.StringVar()

    def _sync_reports_range(*_):
        sd = (self.start_date_var.get() or '').strip()
        ed = (self.end_date_var.get() or '').strip()
        if sd and ed:
            try:
                from datetime import datetime as _dt
                dsd = _dt.strptime(sd[:10], '%Y-%m-%d').date()
                ded = _dt.strptime(ed[:10], '%Y-%m-%d').date()
            except Exception:
                self.date_range_var.set('Invalid date (use YYYY-MM-DD)')
                return
            if ded < dsd:
                self.date_range_var.set(f"{ed} to {sd}")
                return
            self.date_range_var.set(f"{sd} to {ed}")
        elif sd:
            self.date_range_var.set(sd)
        elif ed:
            self.date_range_var.set(ed)
        else:
            self.date_range_var.set('All dates')

    def _apply_report_range_from_fields(*_):
        sd = (self.start_date_var.get() or '').strip()
        ed = (self.end_date_var.get() or '').strip()
        try:
            from datetime import datetime as _dt
            ds = _dt.strptime(sd[:10], '%Y-%m-%d').date() if sd else None
            de = _dt.strptime(ed[:10], '%Y-%m-%d').date() if ed else None
        except Exception:
            messagebox.showerror('Invalid Date', 'Please use YYYY-MM-DD for Start/End dates (example: 2026-02-06).')
            _sync_reports_range()
            return 'break'
        if ds and de and de < ds:
            ds, de = de, ds
            self.start_date_var.set(ds.strftime('%Y-%m-%d'))
            self.end_date_var.set(de.strftime('%Y-%m-%d'))
        else:
            if ds and sd != ds.strftime('%Y-%m-%d'):
                self.start_date_var.set(ds.strftime('%Y-%m-%d'))
            if de and ed != de.strftime('%Y-%m-%d'):
                self.end_date_var.set(de.strftime('%Y-%m-%d'))
        _sync_reports_range()
        try:
            self.refresh_reports()
        except Exception:
            pass
        return 'break'

    def _pick_reports_range():
        pick_date_range(self.root, self.start_date_var, self.end_date_var, title='Select Date Range')
        _apply_report_range_from_fields()

    def _clear_reports_range():
        self.start_date_var.set('')
        self.end_date_var.set('')
        _sync_reports_range()
        try:
            self.refresh_reports()
        except Exception:
            pass

    try:
        self.start_date_var.trace_add('write', _sync_reports_range)
        self.end_date_var.trace_add('write', _sync_reports_range)
    except Exception as e:
        _log_ignored('ui.trace_add failed', e, key='ui.trace_add_failed')
    _sync_reports_range()

    _rg_row = ttk.Frame(top1)
    _rg_row.pack(side='left', padx=2)
    ttk.Label(_rg_row, text='Start').pack(side='left')
    self.report_start_entry = ttk.Entry(_rg_row, textvariable=self.start_date_var, width=12)
    self.report_start_entry.pack(side='left', padx=(4, 6))
    ttk.Label(_rg_row, text='End').pack(side='left')
    self.report_end_entry = ttk.Entry(_rg_row, textvariable=self.end_date_var, width=12)
    self.report_end_entry.pack(side='left', padx=(4, 6))
    try:
        self.report_start_entry.bind('<Return>', _apply_report_range_from_fields)
        self.report_start_entry.bind('<FocusOut>', _apply_report_range_from_fields)
        self.report_end_entry.bind('<Return>', _apply_report_range_from_fields)
        self.report_end_entry.bind('<FocusOut>', _apply_report_range_from_fields)
    except Exception as e:
        _log_ignored('ui.bind failed', e, key='ui.bind_failed')
    ttk.Button(_rg_row, text='📅', width=3, command=_pick_reports_range).pack(side='left', padx=(0, 0))
    ttk.Button(_rg_row, text='Clear', width=6, command=_clear_reports_range).pack(side='left', padx=(4, 0))

    ttk.Label(top1, text='Page:').pack(side='left', padx=(10, 2))
    try:
        _prefs = _load_ledger_prefs()
    except Exception:
        _prefs = {}
    _ps_values = ['A4', 'Letter 8.5 x 11', 'Folio 8.5 x 13', 'Legal 8.5 x 14']
    _default_ps = (_prefs.get('reports_page_size') or 'A4')
    if _default_ps not in _ps_values:
        _default_ps = 'A4'
    self.report_page_size_var = tk.StringVar(value=_default_ps)
    _ps_cb = ttk.Combobox(top1, textvariable=self.report_page_size_var, values=_ps_values, width=14, state='readonly')
    _ps_cb.pack(side='left')

    def _save_reports_page_size(*_):
        try:
            p = _load_ledger_prefs()
            p['reports_page_size'] = (self.report_page_size_var.get() or 'A4')
            _save_ledger_prefs(p)
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0403', 'suppressed exception excpass_0403', __spina_exc)
            pass

    try:
        self.report_page_size_var.trace_add('write', lambda *_: _save_reports_page_size())
    except Exception:
        try:
            _ps_cb.bind('<<ComboboxSelected>>', lambda e: _save_reports_page_size())
        except Exception as e:
            _log_ignored('ui.bind failed', e, key='ui.bind_failed')

    ttk.Button(top2, text='This Month', command=lambda: (self.start_date_var.set(date.today().replace(day=1).strftime('%Y-%m-%d')), self.end_date_var.set(date.today().strftime('%Y-%m-%d')), self.refresh_reports())).pack(side='left', padx=6)
    ttk.Button(top2, text='Today', command=lambda: (self.start_date_var.set(date.today().strftime('%Y-%m-%d')), self.end_date_var.set(date.today().strftime('%Y-%m-%d')), self.refresh_reports())).pack(side='left', padx=(0, 6))
    self.report_notes_btn = ttk.Button(top2, text='Notes…')
    self.report_notes_btn.pack(side='left', padx=6)
    ttk.Button(top2, text='Generate Report', style='Primary.TButton', command=self.generate_pdf_selected).pack(side='left', padx=6)
    ttk.Button(top2, text='Report Logs', command=self.open_report_generation_log).pack(side='left', padx=(0, 6))
    ttk.Separator(top2, orient='vertical').pack(side='left', fill='y', padx=10)
    ttk.Frame(top2).pack(side='left', fill='x', expand=True)
    self.report_summary_var = tk.StringVar(value='0 clients')
    ttk.Label(top2, textvariable=self.report_summary_var, anchor='e').pack(side='right', padx=6)

    body = ttk.Frame(frm)
    body.pack(fill='both', expand=True)

    cols = ('name', 'contact', 'loan_type', 'term', 'day_due', 'payment', 'mode', 'linked', 'area', 'principal', 'total', 'released', 'due')
    tree_frame = ttk.Frame(body)
    tree_frame.pack(fill='both', expand=True)

    self.reports_tree = ttk.Treeview(tree_frame, columns=cols, show='headings', height=18)
    try:
        self.reports_tree.bind('<<TreeviewSelect>>', lambda e: self._auto_load_report_note())
    except Exception as e:
        _log_ignored('ui.bind failed', e, key='ui.bind_failed')

    _hdr = {
        'name': 'Client',
        'contact': 'Contact',
        'loan_type': 'Loan Type',
        'term': 'Term',
        'day_due': 'Day Due',
        'payment': 'Payment',
        'mode': 'Mode',
        'linked': 'Also Has',
        'area': 'Area',
        'principal': 'Principal',
        'total': 'Total To Pay',
        'released': 'Date Released',
        'due': 'Due Date',
    }
    _w = {
        'name': 240,
        'contact': 128,
        'loan_type': 104,
        'term': 82,
        'day_due': 110,
        'payment': 98,
        'mode': 84,
        'linked': 126,
        'area': 175,
        'principal': 104,
        'total': 114,
        'released': 106,
        'due': 106,
    }
    _anchor = {
        'name': 'w',
        'contact': 'center',
        'loan_type': 'center',
        'term': 'center',
        'day_due': 'center',
        'payment': 'e',
        'mode': 'center',
        'linked': 'center',
        'area': 'w',
        'principal': 'e',
        'total': 'e',
        'released': 'center',
        'due': 'center',
    }
    for c in cols:
        self.reports_tree.heading(c, text=_hdr.get(c, c.title()))
        self.reports_tree.column(c, width=_w.get(c, 100), anchor=_anchor.get(c, 'w'))

    try:
        self._configure_tree_stripes(self.reports_tree)
    except Exception:
        pass

    vscroll = ttk.Scrollbar(tree_frame, orient='vertical', command=self.reports_tree.yview)
    hscroll = ttk.Scrollbar(body, orient='horizontal', command=self.reports_tree.xview)
    self.reports_tree.configure(yscrollcommand=vscroll.set, xscrollcommand=hscroll.set)
    self.reports_tree.pack(side='left', fill='both', expand=True)
    vscroll.pack(side='right', fill='y')
    hscroll.pack(side='bottom', fill='x')

    self.reports_notes_sep = ttk.Separator(body, orient='horizontal')
    self.reports_notes_sep.pack(fill='x', pady=(8, 6))
    self.reports_notes_box = ttk.LabelFrame(body, text='Reports Notes')
    self.reports_notes_box.pack(fill='x', pady=(0, 0))

    def _toggle_reports_notes_panel():
        try:
            box = getattr(self, 'reports_notes_box', None)
            sep = getattr(self, 'reports_notes_sep', None)
            btn = getattr(self, 'report_notes_btn', None)
            if box is None:
                return
            shown = bool(box.winfo_manager())
            if shown:
                try:
                    box.pack_forget()
                except Exception:
                    pass
                try:
                    if sep is not None:
                        sep.pack_forget()
                except Exception:
                    pass
                try:
                    if btn is not None:
                        btn.configure(text='Notes…')
                except Exception:
                    pass
            else:
                try:
                    if sep is not None:
                        sep.pack(fill='x', pady=(8, 6), before=box)
                except Exception:
                    try:
                        if sep is not None:
                            sep.pack(fill='x', pady=(8, 6))
                    except Exception:
                        pass
                try:
                    box.pack(fill='x', pady=(0, 0))
                except Exception:
                    pass
                try:
                    if btn is not None:
                        btn.configure(text='Hide Notes')
                except Exception:
                    pass
                try:
                    self._auto_load_report_note()
                except Exception:
                    pass
                try:
                    self.report_note_txt.focus_set()
                except Exception:
                    pass
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_reports_note_toggle_0001', 'suppressed exception excpass_reports_note_toggle_0001', __spina_exc)
            pass

    self.report_notes_btn.configure(command=self._open_note_dialog)
    try:
        self.report_notes_btn.configure(text='Notes…')
    except Exception:
        pass
    try:
        self.reports_notes_box.pack_forget()
    except Exception:
        pass
    try:
        self.reports_notes_sep.pack_forget()
    except Exception:
        pass

    notes_top = ttk.Frame(self.reports_notes_box)
    notes_top.pack(fill='x', padx=8, pady=(8, 4))

    self.note_date_var = tk.StringVar(value=(self.end_date_var.get() or date.today().strftime('%Y-%m-%d')))
    self.report_note_var = tk.StringVar(value='')
    self.report_note_status_var = tk.StringVar(value='Select a client to view notes.')

    ttk.Label(notes_top, text='Note Date:').pack(side='left')
    ttk.Entry(notes_top, textvariable=self.note_date_var, width=12).pack(side='left', padx=(4, 2))
    ttk.Button(
        notes_top,
        text='📅',
        width=3,
        command=lambda: pick_date(self.root, self.note_date_var, initial=self.note_date_var.get(), title='Select Note Date'),
    ).pack(side='left', padx=(0, 8))
    ttk.Button(notes_top, text='Load', command=self._load_report_note_for_client).pack(side='left', padx=(0, 4))
    ttk.Button(notes_top, text='Save Date', style='Primary.TButton', command=self._save_dated_note_for_client).pack(side='left', padx=(0, 4))
    ttk.Button(notes_top, text='Save Default', command=self._save_report_note_for_client).pack(side='left', padx=(0, 4))
    ttk.Button(notes_top, text='Clear', command=lambda: self._set_report_note_text('')).pack(side='left')
    ttk.Label(notes_top, textvariable=self.report_note_status_var, anchor='e').pack(side='right', fill='x', expand=True, padx=(12, 0))

    notes_text_row = ttk.Frame(self.reports_notes_box)
    notes_text_row.pack(fill='both', expand=True, padx=8, pady=(0, 8))
    self.report_note_txt = tk.Text(
        notes_text_row,
        height=6,
        wrap='word',
        undo=True,
        relief='solid',
        borderwidth=1,
    )
    self.report_note_txt.pack(side='left', fill='x', expand=True)
    notes_scroll = ttk.Scrollbar(notes_text_row, orient='vertical', command=self.report_note_txt.yview)
    self.report_note_txt.configure(yscrollcommand=notes_scroll.set)
    notes_scroll.pack(side='right', fill='y')

    try:
        self.note_date_var.trace_add('write', lambda *_: self._auto_load_report_note())
    except Exception as e:
        _log_ignored('ui.trace_add failed', e, key='ui.trace_add_failed')
