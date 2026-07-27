"""System Data tab construction presentation extracted in Wave 56."""
from __future__ import annotations

_SYSTEM_DATA_PRESENTATION_DEPENDENCIES = {}
_PROTECTED_GLOBALS = {'SYSTEM_DATA_PRESENTATION_SOURCE_SHA256', '__spec__', '__name__', 'SYSTEM_DATA_PRESENTATION_DEDENTED_SHA256', '_SYSTEM_DATA_PRESENTATION_DEPENDENCIES', '__loader__', '__cached__', '_build_system_data_tab', '_PROTECTED_GLOBALS', 'SYSTEM_DATA_PRESENTATION_SOURCE_LINES', 'SYSTEM_DATA_PRESENTATION_SELF_ATTRIBUTES', 'SYSTEM_DATA_PRESENTATION_LABEL_TEXTS', '__doc__', '__file__', 'SYSTEM_DATA_PRESENTATION_TARGET', 'SYSTEM_DATA_PRESENTATION_BUTTON_CALLBACKS', 'SYSTEM_DATA_PRESENTATION_BUTTON_TEXTS', 'SYSTEM_DATA_PRESENTATION_CALLS', '__package__', 'SYSTEM_DATA_PRESENTATION_SIGNATURE', 'configure_system_data_presentation_dependencies', '__builtins__'}

def configure_system_data_presentation_dependencies(namespace):
    _SYSTEM_DATA_PRESENTATION_DEPENDENCIES.clear()
    _SYSTEM_DATA_PRESENTATION_DEPENDENCIES.update(namespace)
    for name, value in namespace.items():
        if name not in _PROTECTED_GLOBALS:
            globals()[name] = value

SYSTEM_DATA_PRESENTATION_TARGET = '_build_system_data_tab'
SYSTEM_DATA_PRESENTATION_SOURCE_LINES = 46
SYSTEM_DATA_PRESENTATION_SOURCE_SHA256 = 'b4d8ff8e73daca66a7aa4d6d5e8e08fe5d91648f04c7a2e485fb0677add79f3d'
SYSTEM_DATA_PRESENTATION_DEDENTED_SHA256 = '3bc94f4af5ae75cc1a287f262e4c647d9d929a0906ebe73318f167dd472a119b'
SYSTEM_DATA_PRESENTATION_SIGNATURE = 'self'
SYSTEM_DATA_PRESENTATION_CALLS = ['_dt.now', '_log_suppressed_once', 'controls.columnconfigure', 'controls.grid', 'grid', 'outer.columnconfigure', 'outer.rowconfigure', 'range', 'self._get_databank_focus_date', 'self._system_data_refresh_summary', 'strftime', 'summary.columnconfigure', 'summary.grid', 'summary.rowconfigure', 'title.columnconfigure', 'title.grid', 'tk.StringVar', 'ttk.Button', 'ttk.Entry', 'ttk.Frame', 'ttk.Label', 'ttk.LabelFrame']
SYSTEM_DATA_PRESENTATION_SELF_ATTRIBUTES = ['system_data_date_var', 'system_data_summary_var']
SYSTEM_DATA_PRESENTATION_BUTTON_TEXTS = ['History', 'Open Daily Close / Variance', 'Print Report', 'Records', 'Refresh', 'Use Focus Date']
SYSTEM_DATA_PRESENTATION_LABEL_TEXTS = ['Daily Close Tools', 'Data', 'Date', 'Summary', 'System account daily close / variance workspace']
SYSTEM_DATA_PRESENTATION_BUTTON_CALLBACKS = [('Use Focus Date', '_system_data_use_focus_date'), ('Refresh', '_system_data_refresh_summary'), ('Open Daily Close / Variance', '_system_data_open_close'), ('History', '_system_data_open_history'), ('Records', '_system_data_open_records'), ('Print Report', '_system_data_print_report')]

def _build_system_data_tab(self):
    import tkinter as tk
    from tkinter import ttk
    from datetime import datetime as _dt

    outer = self.tab_system_data
    outer.columnconfigure(0, weight=1)
    outer.rowconfigure(2, weight=1)

    title = ttk.Frame(outer)
    title.grid(row=0, column=0, sticky='ew', pady=(0, 10))
    title.columnconfigure(0, weight=1)

    ttk.Label(title, text='Data', font=('TkDefaultFont', 12, 'bold')).grid(row=0, column=0, sticky='w')
    ttk.Label(title, text='System account daily close / variance workspace').grid(row=1, column=0, sticky='w', pady=(2, 0))

    controls = ttk.LabelFrame(outer, text='Daily Close Tools', padding=10)
    controls.grid(row=1, column=0, sticky='ew')
    for col in range(8):
        controls.columnconfigure(col, weight=0)
    controls.columnconfigure(7, weight=1)

    self.system_data_date_var = tk.StringVar(value=(self._get_databank_focus_date() or _dt.now().strftime('%Y-%m-%d')))
    self.system_data_summary_var = tk.StringVar(value='Select a date, then open or review the daily close record.')

    ttk.Label(controls, text='Date').grid(row=0, column=0, sticky='w')
    ttk.Entry(controls, textvariable=self.system_data_date_var, width=14).grid(row=0, column=1, sticky='w', padx=(6, 10))
    ttk.Button(controls, text='Use Focus Date', command=self._system_data_use_focus_date).grid(row=0, column=2, sticky='w', padx=(0, 6))
    ttk.Button(controls, text='Refresh', command=self._system_data_refresh_summary).grid(row=0, column=3, sticky='w', padx=(0, 6))
    ttk.Button(controls, text='Open Daily Close / Variance', command=self._system_data_open_close).grid(row=0, column=4, sticky='w', padx=(0, 6))
    ttk.Button(controls, text='History', command=self._system_data_open_history).grid(row=0, column=5, sticky='w', padx=(0, 6))
    ttk.Button(controls, text='Records', command=self._system_data_open_records).grid(row=0, column=6, sticky='w', padx=(0, 6))
    ttk.Button(controls, text='Print Report', command=self._system_data_print_report).grid(row=0, column=7, sticky='w')

    summary = ttk.LabelFrame(outer, text='Summary', padding=10)
    summary.grid(row=2, column=0, sticky='nsew', pady=(10, 0))
    summary.columnconfigure(0, weight=1)
    summary.rowconfigure(0, weight=1)

    ttk.Label(summary, textvariable=self.system_data_summary_var, justify='left', anchor='nw').grid(row=0, column=0, sticky='nsew')

    try:
        self._system_data_refresh_summary()
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_system_data_init_refresh', 'suppressed exception excpass_system_data_init_refresh', __spina_exc)
        pass
