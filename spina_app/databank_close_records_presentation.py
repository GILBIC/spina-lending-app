"""Data Bank close-records presentation extracted in Wave 66."""
from __future__ import annotations

_DATABANK_CLOSE_RECORDS_DEPENDENCIES = {}
_PROTECTED_GLOBALS = {
    '__name__', '__doc__', '__package__', '__loader__', '__spec__',
    '__file__', '__cached__', '__builtins__',
    '_DATABANK_CLOSE_RECORDS_DEPENDENCIES', '_PROTECTED_GLOBALS',
    'DATABANK_CLOSE_RECORDS_PRESENTATION_METHODS',
    'configure_databank_close_records_dependencies',
    'open_databank_close_records_dialog',
}

def configure_databank_close_records_dependencies(namespace):
    _DATABANK_CLOSE_RECORDS_DEPENDENCIES.clear()
    _DATABANK_CLOSE_RECORDS_DEPENDENCIES.update(namespace)
    for name, value in namespace.items():
        if name not in _PROTECTED_GLOBALS:
            globals()[name] = value

DATABANK_CLOSE_RECORDS_PRESENTATION_METHODS = {"open_databank_close_records_dialog": {"calls": ["ValueError", "_coerce_date", "_dt.strptime", "_dt.strptime.strftime", "_fmt_amt", "_load_records", "_selected_date", "abs", "base_dt.replace", "base_dt.replace.strftime", "base_dt.strftime", "bool", "btns.grid", "datetime.now", "datetime.now.strftime", "end_var.get", "filters.columnconfigure", "filters.grid", "filters.rowconfigure", "float", "fmt_currency", "footer.columnconfigure", "footer.grid", "hasattr", "hsb.grid", "int", "len", "load_btn.configure", "load_btn.pack", "messagebox.showerror", "messagebox.showinfo", "open_btn.configure", "open_btn.pack", "outer.columnconfigure", "outer.pack", "outer.rowconfigure", "print_btn.configure", "print_btn.pack", "rec.get", "replace", "replace.strip", "self._get_databank_focus_date", "self.db.list_databank_day_close_records", "self.open_databank_close_dialog", "self.print_databank_close_report", "start_var.get", "str", "str.strip", "strip", "summary_var.set", "tk.StringVar", "tk.Toplevel", "top.geometry", "top.grab_set", "top.title", "top.transient", "tree.bind", "tree.column", "tree.configure", "tree.delete", "tree.focus", "tree.get_children", "tree.grid", "tree.heading", "tree.insert", "tree.item", "tree.selection", "tree.selection_set", "tree_wrap.columnconfigure", "tree_wrap.grid", "tree_wrap.rowconfigure", "ttk.Button", "ttk.Button.pack", "ttk.Entry", "ttk.Entry.grid", "ttk.Frame", "ttk.Label", "ttk.Label.grid", "ttk.Scrollbar", "ttk.Treeview", "vsb.grid"], "db_calls": ["self.db.list_databank_day_close_records"], "dedented_sha256": "9fd127d82e39cec7f59c98cae90b09af3465a2a6287a4bfebf2f5280f8471b6a", "lines": 224, "signature": "self, start_date=None, end_date=None", "source_sha256": "2b3050213b1861f3b0a085742a1b9d277dd0cb2999337b8f5df83fc832435c74"}}

def open_databank_close_records_dialog(self, start_date=None, end_date=None):
    import tkinter as tk
    from tkinter import ttk, messagebox
    from datetime import datetime as _dt

    def _coerce_date(txt):
        s = (str(txt or '').strip())
        if not s:
            return ''
        try:
            return _dt.strptime(s, '%Y-%m-%d').strftime('%Y-%m-%d')
        except Exception:
            raise ValueError('Use date format YYYY-MM-DD.')

    base_date = (start_date or self._get_databank_focus_date() or datetime.now().strftime('%Y-%m-%d')).strip()
    try:
        base_dt = _dt.strptime(base_date, '%Y-%m-%d')
    except Exception:
        base_dt = datetime.now()
        base_date = base_dt.strftime('%Y-%m-%d')
    default_start = (start_date or base_dt.replace(day=1).strftime('%Y-%m-%d'))
    default_end = (end_date or base_date)

    top = tk.Toplevel(self.root)
    top.title('Daily Close Records')
    top.transient(self.root)
    top.grab_set()
    top.geometry('1220x520')

    outer = ttk.Frame(top, padding=12)
    outer.pack(fill='both', expand=True)
    outer.columnconfigure(0, weight=1)
    outer.rowconfigure(2, weight=1)

    ttk.Label(outer, text='Daily Close Records', style='Section.TLabel').grid(row=0, column=0, sticky='w')
    ttk.Label(outer, text='View Daily Close / Variance records for a date range. You can open a date or print the selected report directly from this list.').grid(row=1, column=0, sticky='w', pady=(4, 10))

    filters = ttk.Frame(outer)
    filters.grid(row=2, column=0, sticky='nsew')
    filters.columnconfigure(8, weight=1)
    ttk.Label(filters, text='From').grid(row=0, column=0, sticky='w')
    start_var = tk.StringVar(value=default_start)
    end_var = tk.StringVar(value=default_end)
    ttk.Entry(filters, textvariable=start_var, width=14).grid(row=0, column=1, sticky='w', padx=(6, 12))
    ttk.Label(filters, text='To').grid(row=0, column=2, sticky='w')
    ttk.Entry(filters, textvariable=end_var, width=14).grid(row=0, column=3, sticky='w', padx=(6, 12))
    summary_var = tk.StringVar(value='')

    tree_wrap = ttk.Frame(filters)
    tree_wrap.grid(row=1, column=0, columnspan=9, sticky='nsew', pady=(10, 0))
    filters.rowconfigure(1, weight=1)
    filters.columnconfigure(8, weight=1)

    cols = ('close_date', 'lock_state', 'status', 'regular_total', 'x7_total', 'expected_amount', 'actual_cash', 'variance', 'closed_by', 'closed_at', 'note')
    tree = ttk.Treeview(tree_wrap, columns=cols, show='headings', height=16)
    headings = {
        'close_date': 'Date',
        'lock_state': 'Lock',
        'status': 'Status',
        'regular_total': 'Regular',
        'x7_total': '7x7',
        'expected_amount': 'Expected',
        'actual_cash': 'Actual',
        'variance': 'Variance',
        'closed_by': 'Closed By',
        'closed_at': 'Closed At',
        'note': 'Note',
    }
    widths = {
        'close_date': 90,
        'lock_state': 75,
        'status': 90,
        'regular_total': 95,
        'x7_total': 95,
        'expected_amount': 100,
        'actual_cash': 100,
        'variance': 100,
        'closed_by': 110,
        'closed_at': 145,
        'note': 300,
    }
    anchors = {
        'close_date': 'center',
        'lock_state': 'center',
        'status': 'center',
        'regular_total': 'e',
        'x7_total': 'e',
        'expected_amount': 'e',
        'actual_cash': 'e',
        'variance': 'e',
        'closed_by': 'w',
        'closed_at': 'w',
        'note': 'w',
    }
    for c in cols:
        tree.heading(c, text=headings[c])
        tree.column(c, width=widths[c], anchor=anchors[c], stretch=(c == 'note'))

    vsb = ttk.Scrollbar(tree_wrap, orient='vertical', command=tree.yview)
    hsb = ttk.Scrollbar(tree_wrap, orient='horizontal', command=tree.xview)
    tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
    tree.grid(row=0, column=0, sticky='nsew')
    vsb.grid(row=0, column=1, sticky='ns')
    hsb.grid(row=1, column=0, sticky='ew')
    tree_wrap.rowconfigure(0, weight=1)
    tree_wrap.columnconfigure(0, weight=1)

    footer = ttk.Frame(outer)
    footer.grid(row=3, column=0, sticky='ew', pady=(10, 0))
    footer.columnconfigure(0, weight=1)
    ttk.Label(footer, textvariable=summary_var, foreground='#666666').grid(row=0, column=0, sticky='w')
    btns = ttk.Frame(footer)
    btns.grid(row=0, column=1, sticky='e')
    load_btn = ttk.Button(btns, text='Load List')
    load_btn.pack(side='left', padx=4)
    open_btn = ttk.Button(btns, text='Open Selected')
    open_btn.pack(side='left', padx=4)
    print_btn = ttk.Button(btns, text='Print Selected')
    print_btn.pack(side='left', padx=4)
    ttk.Button(btns, text='Close Window', command=top.destroy).pack(side='left', padx=4)

    def _fmt_amt(val):
        try:
            return fmt_currency(val)
        except Exception:
            try:
                return f"{float(val or 0.0):,.2f}"
            except Exception:
                return '0.00'

    def _selected_date():
        sel = tree.selection()
        if not sel:
            return ''
        vals = tree.item(sel[0], 'values') or []
        return (vals[0] if vals else '').strip()

    def _load_records(*_):
        try:
            s = _coerce_date(start_var.get())
            e = _coerce_date(end_var.get())
            if s and e and s > e:
                raise ValueError('From date cannot be later than To date.')
        except ValueError as ve:
            messagebox.showerror('Daily Close Records', str(ve), parent=top)
            return

        for iid in tree.get_children(''):
            tree.delete(iid)

        try:
            rows = self.db.list_databank_day_close_records(s, e) if hasattr(self, 'db') else []
        except Exception:
            rows = []

        closed_count = open_count = over_count = short_count = balanced_count = 0
        sum_expected = sum_actual = sum_variance = 0.0
        for rec in rows:
            ds = (rec.get('close_date') or '').strip()
            is_closed = bool(int(rec.get('is_closed') or 0))
            lock_txt = 'CLOSED' if is_closed else 'OPEN'
            stat_txt = (rec.get('variance_status') or 'Balanced').strip() or 'Balanced'
            reg_total = float(rec.get('regular_total') or 0.0)
            x7_total = float(rec.get('x7_total') or 0.0)
            expected = float(rec.get('expected_amount') or 0.0)
            actual = float(rec.get('actual_cash') or 0.0)
            variance = float(rec.get('variance') or 0.0)
            if abs(variance) < 0.005:
                variance = 0.0
            note_txt = (rec.get('note') or '').replace('\n', ' ').strip()
            tree.insert('', 'end', values=(
                ds,
                lock_txt,
                stat_txt,
                _fmt_amt(reg_total),
                _fmt_amt(x7_total),
                _fmt_amt(expected),
                _fmt_amt(actual),
                _fmt_amt(abs(variance)) if variance else _fmt_amt(0.0),
                (rec.get('closed_by') or '').strip(),
                (rec.get('closed_at') or '').strip(),
                note_txt,
            ))
            closed_count += 1 if is_closed else 0
            open_count += 0 if is_closed else 1
            over_count += 1 if stat_txt == 'Overage' else 0
            short_count += 1 if stat_txt == 'Short' else 0
            balanced_count += 1 if stat_txt == 'Balanced' else 0
            sum_expected += expected
            sum_actual += actual
            sum_variance += variance

        if rows:
            summary_var.set(
                f"Records: {len(rows)} | Closed: {closed_count} | Open: {open_count} | "
                f"Overage: {over_count} | Short: {short_count} | Balanced: {balanced_count} | "
                f"Expected: {_fmt_amt(sum_expected)} | Actual: {_fmt_amt(sum_actual)} | Variance: {_fmt_amt(abs(sum_variance)) if abs(sum_variance) >= 0.005 else _fmt_amt(0.0)}"
            )
            first = tree.get_children('')
            if first:
                tree.selection_set(first[0])
                tree.focus(first[0])
        else:
            summary_var.set('No Daily Close records found for the selected date range.')

    def _open_selected(*_):
        ds = _selected_date()
        if not ds:
            messagebox.showinfo('Daily Close Records', 'Select a row first.', parent=top)
            return
        self.open_databank_close_dialog(ds)

    def _print_selected():
        ds = _selected_date()
        if not ds:
            messagebox.showinfo('Daily Close Records', 'Select a row first.', parent=top)
            return
        self.print_databank_close_report(ds)

    load_btn.configure(command=_load_records)
    open_btn.configure(command=_open_selected)
    print_btn.configure(command=_print_selected)
    tree.bind('<Double-1>', _open_selected)
    _load_records()
