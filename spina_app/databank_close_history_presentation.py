"""Data Bank Close History dialog presentation extracted in Wave 57."""
from __future__ import annotations

_CLOSE_HISTORY_PRESENTATION_DEPENDENCIES = {}
_PROTECTED_GLOBALS = {'__spec__', '__file__', 'configure_databank_close_history_presentation_dependencies', 'CLOSE_HISTORY_PRESENTATION_DEDENTED_SHA256', 'CLOSE_HISTORY_PRESENTATION_SOURCE_SHA256', 'CLOSE_HISTORY_PRESENTATION_DB_CALLS', '__doc__', 'CLOSE_HISTORY_PRESENTATION_SOURCE_LINES', '_CLOSE_HISTORY_PRESENTATION_DEPENDENCIES', '_PROTECTED_GLOBALS', '__loader__', 'CLOSE_HISTORY_PRESENTATION_TARGET', 'CLOSE_HISTORY_PRESENTATION_CALLS', '__cached__', 'open_databank_close_history_dialog', '__builtins__', '__name__', 'CLOSE_HISTORY_PRESENTATION_SIGNATURE', '__package__'}

def configure_databank_close_history_presentation_dependencies(namespace):
    _CLOSE_HISTORY_PRESENTATION_DEPENDENCIES.clear()
    _CLOSE_HISTORY_PRESENTATION_DEPENDENCIES.update(namespace)
    for name, value in namespace.items():
        if name not in _PROTECTED_GLOBALS:
            globals()[name] = value

CLOSE_HISTORY_PRESENTATION_TARGET = 'open_databank_close_history_dialog'
CLOSE_HISTORY_PRESENTATION_SOURCE_LINES = 71
CLOSE_HISTORY_PRESENTATION_SOURCE_SHA256 = 'b08b9c7f4afe8513597a0ec0f0814a92e2bbd816b2ff06fcdc488da39eabfeed'
CLOSE_HISTORY_PRESENTATION_DEDENTED_SHA256 = '47e55f4f4b23dd1f27571c390e4425a995a5f877a6bde08a7bc12e461e39e6b3'
CLOSE_HISTORY_PRESENTATION_SIGNATURE = 'self, date_s, loan_type=None'
CLOSE_HISTORY_PRESENTATION_CALLS = ['abs', 'anchors.get', 'float', 'fmt_currency', 'grid', 'hasattr', 'headings.get', 'hsb.grid', 'outer.columnconfigure', 'outer.pack', 'outer.rowconfigure', 'rec.get', 'self.db.list_databank_day_close_history', 'strip', 'tk.Toplevel', 'top.geometry', 'top.grab_set', 'top.title', 'top.transient', 'tree.column', 'tree.configure', 'tree.grid', 'tree.heading', 'tree.insert', 'ttk.Button', 'ttk.Frame', 'ttk.Label', 'ttk.Scrollbar', 'ttk.Treeview', 'vsb.grid', 'widths.get']
CLOSE_HISTORY_PRESENTATION_DB_CALLS = ['self.db.list_databank_day_close_history']

def open_databank_close_history_dialog(self, date_s, loan_type=None):
    import tkinter as tk
    from tkinter import ttk

    rows = self.db.list_databank_day_close_history(date_s, loan_type=loan_type) if hasattr(self, 'db') else []

    top = tk.Toplevel(self.root)
    top.title(f'Daily Close History - {date_s}')
    top.transient(self.root)
    top.grab_set()
    top.geometry('980x420')

    outer = ttk.Frame(top, padding=10)
    outer.pack(fill='both', expand=True)
    outer.columnconfigure(0, weight=1)
    outer.rowconfigure(1, weight=1)

    ttk.Label(outer, text=f'Variance / Close History for {date_s}', style='Section.TLabel').grid(row=0, column=0, sticky='w', pady=(0, 8))

    cols = ('event_at', 'action', 'workflow', 'variance_status', 'expected', 'actual', 'variance', 'actor', 'note')
    tree = ttk.Treeview(outer, columns=cols, show='headings', height=14)
    vsb = ttk.Scrollbar(outer, orient='vertical', command=tree.yview)
    hsb = ttk.Scrollbar(outer, orient='horizontal', command=tree.xview)
    tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
    tree.grid(row=1, column=0, sticky='nsew')
    vsb.grid(row=1, column=1, sticky='ns')
    hsb.grid(row=2, column=0, sticky='ew')

    headings = {
        'event_at': 'When',
        'action': 'Action',
        'workflow': 'Workflow',
        'variance_status': 'Variance Type',
        'expected': 'Expected',
        'actual': 'Actual',
        'variance': 'Variance',
        'actor': 'By',
        'note': 'Note',
    }
    widths = {'event_at': 150, 'action': 130, 'workflow': 100, 'variance_status': 110, 'expected': 100, 'actual': 100, 'variance': 100, 'actor': 120, 'note': 300}
    anchors = {'expected': 'e', 'actual': 'e', 'variance': 'e'}
    for c in cols:
        tree.heading(c, text=headings.get(c, c))
        tree.column(c, width=widths.get(c, 120), anchor=anchors.get(c, 'w'), stretch=(c == 'note'))

    for rec in (rows or []):
        try:
            expected = fmt_currency(rec.get('expected_amount') or 0.0)
        except Exception:
            expected = f"{float(rec.get('expected_amount') or 0.0):,.2f}"
        try:
            actual = fmt_currency(rec.get('actual_cash') or 0.0)
        except Exception:
            actual = f"{float(rec.get('actual_cash') or 0.0):,.2f}"
        try:
            variance = fmt_currency(abs(float(rec.get('variance') or 0.0)))
        except Exception:
            variance = '0.00'
        tree.insert('', 'end', values=(
            (rec.get('event_at') or '').strip(),
            (rec.get('action') or '').strip(),
            (rec.get('workflow_status') or '').strip(),
            (rec.get('variance_status') or '').strip(),
            expected,
            actual,
            variance,
            (rec.get('actor') or '').strip(),
            (rec.get('note') or '').strip(),
        ))

    ttk.Button(outer, text='Close', command=top.destroy).grid(row=3, column=0, sticky='e', pady=(8, 0))
