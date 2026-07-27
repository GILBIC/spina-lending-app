"""Audit tab presentation extracted in Wave 54."""
from __future__ import annotations

_AUDIT_PRESENTATION_DEPENDENCIES = {}
_PROTECTED_GLOBALS = {'AUDIT_PRESENTATION_SOURCE_SHA256', 'AUDIT_PRESENTATION_SIGNATURES', 'AUDIT_PRESENTATION_CALLS', 'AUDIT_PRESENTATION_TOTAL_SOURCE_LINES', '__loader__', '_PROTECTED_GLOBALS', 'configure_audit_presentation_dependencies', '__doc__', 'refresh_audit_tab', '__spec__', '__package__', 'AUDIT_PRESENTATION_SOURCE_LINES', '_build_audit_tab', 'AUDIT_PRESENTATION_TARGETS', '_AUDIT_PRESENTATION_DEPENDENCIES', '__cached__', '__builtins__', '__file__', '__name__'}

def configure_audit_presentation_dependencies(namespace):
    _AUDIT_PRESENTATION_DEPENDENCIES.clear()
    _AUDIT_PRESENTATION_DEPENDENCIES.update(namespace)
    for name, value in namespace.items():
        if name not in _PROTECTED_GLOBALS:
            globals()[name] = value

AUDIT_PRESENTATION_TARGETS = ['_build_audit_tab', 'refresh_audit_tab']
AUDIT_PRESENTATION_SOURCE_LINES = {name: item['lines'] for name, item in {'_build_audit_tab': {'lines': 70, 'sha256': 'd4e603a9c902e4eef8b198f3d3f421fa0e1405e37953e5cbe8a4960f78386d27', 'signature': 'self', 'calls': ['_date.today', 'detail_vsb.grid', 'details.columnconfigure', 'details.grid', 'details.rowconfigure', 'filters.columnconfigure', 'filters.grid', 'grid', 'outer.columnconfigure', 'outer.rowconfigure', 'range', 'self._audit_show_selected', 'self._audit_tree_factory', 'self.audit_detail_text.configure', 'self.audit_detail_text.grid', 'self.audit_nb.add', 'self.audit_nb.grid', 'self.audit_new_tree.bind', 'self.audit_renew_tree.bind', 'strftime', 'title.columnconfigure', 'title.grid', 'tk.StringVar', 'tk.Text', 'ttk.Button', 'ttk.Entry', 'ttk.Frame', 'ttk.Label', 'ttk.LabelFrame', 'ttk.Notebook', 'ttk.Scrollbar']}, 'refresh_audit_tab': {'lines': 113, 'sha256': '1a5a34adc75231b60cb235cbcd46be5ddee3718e5c49f6de2ba555952a08ce06', 'signature': 'self', 'calls': ['enumerate', 'float', 'iter', 'len', 'list', 'lower', 'next', 'r.get', 'row.get', 'self._audit_money_text', 'self._audit_new_rows_map.keys', 'self._audit_parse_date_filters', 'self._audit_renew_rows_map.keys', 'self._audit_set_detail_text', 'self._audit_show_selected', 'self.audit_name_var.get', 'self.audit_new_tree.delete', 'self.audit_new_tree.focus', 'self.audit_new_tree.get_children', 'self.audit_new_tree.insert', 'self.audit_new_tree.selection_set', 'self.audit_renew_tree.delete', 'self.audit_renew_tree.focus', 'self.audit_renew_tree.get_children', 'self.audit_renew_tree.insert', 'self.audit_renew_tree.selection_set', 'self.audit_summary_var.set', 'self.db.get_audit_new_loan_rows', 'self.db.get_audit_renewal_rows', 'str', 'strip']}}.items()}
AUDIT_PRESENTATION_SOURCE_SHA256 = {name: item['sha256'] for name, item in {'_build_audit_tab': {'lines': 70, 'sha256': 'd4e603a9c902e4eef8b198f3d3f421fa0e1405e37953e5cbe8a4960f78386d27', 'signature': 'self', 'calls': ['_date.today', 'detail_vsb.grid', 'details.columnconfigure', 'details.grid', 'details.rowconfigure', 'filters.columnconfigure', 'filters.grid', 'grid', 'outer.columnconfigure', 'outer.rowconfigure', 'range', 'self._audit_show_selected', 'self._audit_tree_factory', 'self.audit_detail_text.configure', 'self.audit_detail_text.grid', 'self.audit_nb.add', 'self.audit_nb.grid', 'self.audit_new_tree.bind', 'self.audit_renew_tree.bind', 'strftime', 'title.columnconfigure', 'title.grid', 'tk.StringVar', 'tk.Text', 'ttk.Button', 'ttk.Entry', 'ttk.Frame', 'ttk.Label', 'ttk.LabelFrame', 'ttk.Notebook', 'ttk.Scrollbar']}, 'refresh_audit_tab': {'lines': 113, 'sha256': '1a5a34adc75231b60cb235cbcd46be5ddee3718e5c49f6de2ba555952a08ce06', 'signature': 'self', 'calls': ['enumerate', 'float', 'iter', 'len', 'list', 'lower', 'next', 'r.get', 'row.get', 'self._audit_money_text', 'self._audit_new_rows_map.keys', 'self._audit_parse_date_filters', 'self._audit_renew_rows_map.keys', 'self._audit_set_detail_text', 'self._audit_show_selected', 'self.audit_name_var.get', 'self.audit_new_tree.delete', 'self.audit_new_tree.focus', 'self.audit_new_tree.get_children', 'self.audit_new_tree.insert', 'self.audit_new_tree.selection_set', 'self.audit_renew_tree.delete', 'self.audit_renew_tree.focus', 'self.audit_renew_tree.get_children', 'self.audit_renew_tree.insert', 'self.audit_renew_tree.selection_set', 'self.audit_summary_var.set', 'self.db.get_audit_new_loan_rows', 'self.db.get_audit_renewal_rows', 'str', 'strip']}}.items()}
AUDIT_PRESENTATION_SIGNATURES = {name: item['signature'] for name, item in {'_build_audit_tab': {'lines': 70, 'sha256': 'd4e603a9c902e4eef8b198f3d3f421fa0e1405e37953e5cbe8a4960f78386d27', 'signature': 'self', 'calls': ['_date.today', 'detail_vsb.grid', 'details.columnconfigure', 'details.grid', 'details.rowconfigure', 'filters.columnconfigure', 'filters.grid', 'grid', 'outer.columnconfigure', 'outer.rowconfigure', 'range', 'self._audit_show_selected', 'self._audit_tree_factory', 'self.audit_detail_text.configure', 'self.audit_detail_text.grid', 'self.audit_nb.add', 'self.audit_nb.grid', 'self.audit_new_tree.bind', 'self.audit_renew_tree.bind', 'strftime', 'title.columnconfigure', 'title.grid', 'tk.StringVar', 'tk.Text', 'ttk.Button', 'ttk.Entry', 'ttk.Frame', 'ttk.Label', 'ttk.LabelFrame', 'ttk.Notebook', 'ttk.Scrollbar']}, 'refresh_audit_tab': {'lines': 113, 'sha256': '1a5a34adc75231b60cb235cbcd46be5ddee3718e5c49f6de2ba555952a08ce06', 'signature': 'self', 'calls': ['enumerate', 'float', 'iter', 'len', 'list', 'lower', 'next', 'r.get', 'row.get', 'self._audit_money_text', 'self._audit_new_rows_map.keys', 'self._audit_parse_date_filters', 'self._audit_renew_rows_map.keys', 'self._audit_set_detail_text', 'self._audit_show_selected', 'self.audit_name_var.get', 'self.audit_new_tree.delete', 'self.audit_new_tree.focus', 'self.audit_new_tree.get_children', 'self.audit_new_tree.insert', 'self.audit_new_tree.selection_set', 'self.audit_renew_tree.delete', 'self.audit_renew_tree.focus', 'self.audit_renew_tree.get_children', 'self.audit_renew_tree.insert', 'self.audit_renew_tree.selection_set', 'self.audit_summary_var.set', 'self.db.get_audit_new_loan_rows', 'self.db.get_audit_renewal_rows', 'str', 'strip']}}.items()}
AUDIT_PRESENTATION_CALLS = {name: item['calls'] for name, item in {'_build_audit_tab': {'lines': 70, 'sha256': 'd4e603a9c902e4eef8b198f3d3f421fa0e1405e37953e5cbe8a4960f78386d27', 'signature': 'self', 'calls': ['_date.today', 'detail_vsb.grid', 'details.columnconfigure', 'details.grid', 'details.rowconfigure', 'filters.columnconfigure', 'filters.grid', 'grid', 'outer.columnconfigure', 'outer.rowconfigure', 'range', 'self._audit_show_selected', 'self._audit_tree_factory', 'self.audit_detail_text.configure', 'self.audit_detail_text.grid', 'self.audit_nb.add', 'self.audit_nb.grid', 'self.audit_new_tree.bind', 'self.audit_renew_tree.bind', 'strftime', 'title.columnconfigure', 'title.grid', 'tk.StringVar', 'tk.Text', 'ttk.Button', 'ttk.Entry', 'ttk.Frame', 'ttk.Label', 'ttk.LabelFrame', 'ttk.Notebook', 'ttk.Scrollbar']}, 'refresh_audit_tab': {'lines': 113, 'sha256': '1a5a34adc75231b60cb235cbcd46be5ddee3718e5c49f6de2ba555952a08ce06', 'signature': 'self', 'calls': ['enumerate', 'float', 'iter', 'len', 'list', 'lower', 'next', 'r.get', 'row.get', 'self._audit_money_text', 'self._audit_new_rows_map.keys', 'self._audit_parse_date_filters', 'self._audit_renew_rows_map.keys', 'self._audit_set_detail_text', 'self._audit_show_selected', 'self.audit_name_var.get', 'self.audit_new_tree.delete', 'self.audit_new_tree.focus', 'self.audit_new_tree.get_children', 'self.audit_new_tree.insert', 'self.audit_new_tree.selection_set', 'self.audit_renew_tree.delete', 'self.audit_renew_tree.focus', 'self.audit_renew_tree.get_children', 'self.audit_renew_tree.insert', 'self.audit_renew_tree.selection_set', 'self.audit_summary_var.set', 'self.db.get_audit_new_loan_rows', 'self.db.get_audit_renewal_rows', 'str', 'strip']}}.items()}
AUDIT_PRESENTATION_TOTAL_SOURCE_LINES = 183

def _build_audit_tab(self):
    import tkinter as tk
    from tkinter import ttk
    from datetime import date as _date

    outer = self.tab_audit
    outer.columnconfigure(0, weight=1)
    outer.rowconfigure(2, weight=1)
    outer.rowconfigure(3, weight=0)

    title = ttk.Frame(outer)
    title.grid(row=0, column=0, sticky='ew', pady=(0, 10))
    title.columnconfigure(0, weight=1)
    ttk.Label(title, text='Audit & Logs', font=('TkDefaultFont', 12, 'bold')).grid(row=0, column=0, sticky='w')
    ttk.Label(title, text='Separate audit views for new client loans and renewals.').grid(row=1, column=0, sticky='w', pady=(2, 0))

    filters = ttk.LabelFrame(outer, text='Filters', padding=10)
    filters.grid(row=1, column=0, sticky='ew', pady=(0, 10))
    for col in range(10):
        filters.columnconfigure(col, weight=0)
    filters.columnconfigure(8, weight=1)

    self.audit_from_var = tk.StringVar(value=_date.today().strftime('%Y-%m-%d'))
    self.audit_to_var = tk.StringVar(value=_date.today().strftime('%Y-%m-%d'))
    self.audit_name_var = tk.StringVar(value='')
    self.audit_summary_var = tk.StringVar(value='Audit ready.')
    self._audit_new_rows_map = {}
    self._audit_renew_rows_map = {}

    ttk.Label(filters, text='From').grid(row=0, column=0, sticky='w')
    ttk.Entry(filters, textvariable=self.audit_from_var, width=12).grid(row=0, column=1, sticky='w', padx=(4, 10))
    ttk.Label(filters, text='To').grid(row=0, column=2, sticky='w')
    ttk.Entry(filters, textvariable=self.audit_to_var, width=12).grid(row=0, column=3, sticky='w', padx=(4, 10))
    ttk.Label(filters, text='Client').grid(row=0, column=4, sticky='w')
    ttk.Entry(filters, textvariable=self.audit_name_var, width=22).grid(row=0, column=5, sticky='w', padx=(4, 10))
    ttk.Button(filters, text='Refresh', command=self.refresh_audit_tab).grid(row=0, column=6, sticky='w')
    ttk.Button(filters, text='Today', command=self._audit_set_today).grid(row=0, column=7, sticky='w', padx=(6, 0))
    ttk.Button(filters, text='Last 7 Days', command=self._audit_set_last7).grid(row=0, column=8, sticky='w', padx=(6, 0))
    ttk.Button(filters, text='All', command=self._audit_set_all).grid(row=0, column=9, sticky='w', padx=(6, 0))
    ttk.Label(filters, textvariable=self.audit_summary_var).grid(row=1, column=0, columnspan=10, sticky='w', pady=(8, 0))

    self.audit_nb = ttk.Notebook(outer)
    self.audit_nb.grid(row=2, column=0, sticky='nsew')

    self.audit_tab_new = ttk.Frame(self.audit_nb, padding=0)
    self.audit_tab_renew = ttk.Frame(self.audit_nb, padding=0)
    self.audit_nb.add(self.audit_tab_new, text='New Loans')
    self.audit_nb.add(self.audit_tab_renew, text='Renewals')

    new_cols = ('ts', 'name', 'loan_type', 'date_released', 'payment_start_date', 'principal', 'area', 'payment_term', 'payment_amount', 'source')
    new_heads = ('Logged At', 'Client', 'Loan Type', 'Release Date', 'Start Date', 'Principal', 'Area', 'Term', 'Payment', 'Source')
    new_widths = (150, 220, 90, 100, 100, 110, 130, 80, 100, 110)
    self.audit_new_tree = self._audit_tree_factory(self.audit_tab_new, new_cols, new_heads, new_widths)
    self.audit_new_tree.bind('<<TreeviewSelect>>', lambda e: self._audit_show_selected('new'))

    renew_cols = ('ts', 'name', 'loan_type', 'renew_date', 'old_start_date', 'new_start_date', 'released_cash', 'old_principal', 'new_principal', 'renew_count', 'source')
    renew_heads = ('Logged At', 'Client', 'Loan Type', 'Renew Date', 'Old Start', 'New Start', 'Released Cash', 'Old Principal', 'New Principal', 'Count', 'Source')
    renew_widths = (150, 220, 90, 100, 100, 100, 110, 110, 110, 70, 110)
    self.audit_renew_tree = self._audit_tree_factory(self.audit_tab_renew, renew_cols, renew_heads, renew_widths)
    self.audit_renew_tree.bind('<<TreeviewSelect>>', lambda e: self._audit_show_selected('renew'))

    details = ttk.LabelFrame(outer, text='Selected Audit Row', padding=8)
    details.grid(row=3, column=0, sticky='nsew', pady=(10, 0))
    details.columnconfigure(0, weight=1)
    details.rowconfigure(0, weight=1)
    self.audit_detail_text = tk.Text(details, height=9, wrap='word')
    self.audit_detail_text.grid(row=0, column=0, sticky='nsew')
    detail_vsb = ttk.Scrollbar(details, orient='vertical', command=self.audit_detail_text.yview)
    detail_vsb.grid(row=0, column=1, sticky='ns')
    self.audit_detail_text.configure(yscrollcommand=detail_vsb.set, state='disabled')

def refresh_audit_tab(self):
    filters = self._audit_parse_date_filters()
    if filters is None:
        return
    start_s, end_s = filters
    try:
        name_filter = (self.audit_name_var.get() or '').strip().lower()
    except Exception:
        name_filter = ''

    try:
        new_rows = list(self.db.get_audit_new_loan_rows(start_date=start_s, end_date=end_s, limit=3000) or [])
    except Exception:
        new_rows = []
    try:
        renew_rows = list(self.db.get_audit_renewal_rows(start_date=start_s, end_date=end_s, limit=3000) or [])
    except Exception:
        renew_rows = []

    if name_filter:
        new_rows = [r for r in new_rows if name_filter in str(r.get('name') or '').lower()]
        renew_rows = [r for r in renew_rows if name_filter in str(r.get('name') or '').lower()]

    try:
        for iid in self.audit_new_tree.get_children():
            self.audit_new_tree.delete(iid)
    except Exception:
        pass
    try:
        for iid in self.audit_renew_tree.get_children():
            self.audit_renew_tree.delete(iid)
    except Exception:
        pass

    self._audit_new_rows_map = {}
    self._audit_renew_rows_map = {}

    total_new_principal = 0.0
    for idx, row in enumerate(new_rows, start=1):
        iid = f'new_{idx}'
        self._audit_new_rows_map[iid] = row
        try:
            total_new_principal += float(row.get('principal') or 0)
        except Exception:
            pass
        vals = (
            row.get('ts') or '',
            row.get('name') or '',
            row.get('loan_type') or '',
            row.get('date_released') or '',
            row.get('payment_start_date') or '',
            self._audit_money_text(row.get('principal')),
            row.get('area') or '',
            row.get('payment_term') or '',
            self._audit_money_text(row.get('payment_amount')),
            row.get('source') or '',
        )
        try:
            self.audit_new_tree.insert('', 'end', iid=iid, values=vals)
        except Exception:
            pass

    total_released_cash = 0.0
    for idx, row in enumerate(renew_rows, start=1):
        iid = f'renew_{idx}'
        self._audit_renew_rows_map[iid] = row
        try:
            total_released_cash += float(row.get('released_cash') or 0)
        except Exception:
            pass
        vals = (
            row.get('ts') or '',
            row.get('name') or '',
            row.get('loan_type') or '',
            row.get('renew_date') or '',
            row.get('old_start_date') or '',
            row.get('new_start_date') or '',
            self._audit_money_text(row.get('released_cash')),
            self._audit_money_text(row.get('old_principal')),
            self._audit_money_text(row.get('new_principal')),
            row.get('renew_count') or 0,
            row.get('source') or '',
        )
        try:
            self.audit_renew_tree.insert('', 'end', iid=iid, values=vals)
        except Exception:
            pass

    summary = f"New Loans: {len(new_rows)} | Total Principal: {self._audit_money_text(total_new_principal)} | Renewals: {len(renew_rows)} | Total Released Cash: {self._audit_money_text(total_released_cash)}"
    try:
        self.audit_summary_var.set(summary)
    except Exception:
        pass

    if new_rows:
        try:
            first = next(iter(self._audit_new_rows_map.keys()))
            self.audit_new_tree.selection_set(first)
            self.audit_new_tree.focus(first)
            self._audit_show_selected('new')
            return
        except Exception:
            pass
    if renew_rows:
        try:
            first = next(iter(self._audit_renew_rows_map.keys()))
            self.audit_renew_tree.selection_set(first)
            self.audit_renew_tree.focus(first)
            self._audit_show_selected('renew')
            return
        except Exception:
            pass
    self._audit_set_detail_text('No audit rows found for the current filters.')
