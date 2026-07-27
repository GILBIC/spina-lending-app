"""System Data tab presentation extracted in Wave 55."""
from __future__ import annotations

_SYSTEM_DATA_PRESENTATION_DEPENDENCIES = {}
_PROTECTED_GLOBALS = {'SYSTEM_DATA_PRESENTATION_CALLS', 'configure_system_data_presentation_dependencies', '__cached__', 'SYSTEM_DATA_PRESENTATION_TARGETS', '__builtins__', '_system_data_open_close', '__doc__', 'SYSTEM_DATA_PRESENTATION_SIGNATURES', '_system_data_use_focus_date', 'SYSTEM_DATA_PRESENTATION_TOTAL_SOURCE_LINES', '_system_data_open_history', '__package__', '__loader__', '_hide_system_data_tab', '_system_data_get_date', '__name__', '_system_data_print_report', 'SYSTEM_DATA_PRESENTATION_SOURCE_SHA256', '_show_system_data_tab', '_SYSTEM_DATA_PRESENTATION_DEPENDENCIES', '__spec__', '_PROTECTED_GLOBALS', '__file__', '_build_system_data_tab', '_system_data_open_records', 'SYSTEM_DATA_PRESENTATION_SOURCE_LINES', '_system_data_refresh_summary'}

def configure_system_data_presentation_dependencies(namespace):
    _SYSTEM_DATA_PRESENTATION_DEPENDENCIES.clear()
    _SYSTEM_DATA_PRESENTATION_DEPENDENCIES.update(namespace)
    for name, value in namespace.items():
        if name not in _PROTECTED_GLOBALS:
            globals()[name] = value

_SYSTEM_DATA_PRESENTATION_METADATA = {'_show_system_data_tab': {'lines': 10,
                           'sha256': '97518f51463e32f6b7222e505629edb860b144273485d3416e78cbf606b973ee',
                           'signature': 'self',
                           'calls': ['_log_suppressed_once', 'self.nb.add', 'self.nb.tab', 'self.nb.tabs', 'set', 'str']},
 '_hide_system_data_tab': {'lines': 6,
                           'sha256': '2cc94304e83ecae87891240bd36de8d2762137639004abd3a27be55200dd40f8',
                           'signature': 'self',
                           'calls': ['_log_suppressed_once', 'self.nb.hide']},
 '_system_data_get_date': {'lines': 19,
                           'sha256': 'f22b289a8087cb71d41add83764f8f8be19b78bf880c2b48f70fc1f5d8aaadc9',
                           'signature': 'self',
                           'calls': ['_dt.strptime',
                                     'messagebox.showerror',
                                     'self._get_databank_focus_date',
                                     'self.system_data_date_var.get',
                                     'self.system_data_date_var.set',
                                     'strftime',
                                     'strip']},
 '_system_data_use_focus_date': {'lines': 8,
                                 'sha256': '9901deaa24a7cefc43e532d31afb65e481c52ba08c09d4ea433836606ab1858d',
                                 'signature': 'self',
                                 'calls': ['_log_suppressed_once',
                                           'self._get_databank_focus_date',
                                           'self.system_data_date_var.set',
                                           'strip']},
 '_system_data_refresh_summary': {'lines': 60,
                                  'sha256': 'c6d42e2c651689494e4bded48d8754fdb8ee3ec1a9ecb85053819cea8cf7bcf6',
                                  'signature': 'self',
                                  'calls': ['_fmt_amt',
                                            'abs',
                                            'bool',
                                            'float',
                                            'fmt_currency',
                                            'hasattr',
                                            'int',
                                            'rec.get',
                                            'round',
                                            'self._system_data_get_date',
                                            'self.db.get_databank_daily_total',
                                            'self.db.get_databank_day_close',
                                            'self.system_data_summary_var.set',
                                            'strip']},
 '_system_data_open_close': {'lines': 11,
                             'sha256': 'c2a29a0b52164e57da672c065b5b983b7c81614b1f7f3114c768fe1fb85386e4',
                             'signature': 'self',
                             'calls': ['self._system_data_get_date',
                                       'self._system_data_refresh_summary',
                                       'self.open_databank_close_dialog']},
 '_system_data_open_history': {'lines': 5,
                               'sha256': '7deeb5e16c62824a50a62d186c5d80ee91fddc1494e5d417c75275ad0a94a4b4',
                               'signature': 'self',
                               'calls': ['self._system_data_get_date', 'self.open_databank_close_history_dialog']},
 '_system_data_open_records': {'lines': 5,
                               'sha256': '45c4ff9858104858fbe90f39a08fa5021aed8585f64f22b88680aaee717627ee',
                               'signature': 'self',
                               'calls': ['self._system_data_get_date', 'self.open_databank_close_records_dialog']},
 '_system_data_print_report': {'lines': 5,
                               'sha256': '1dd96e2737cca13fc2ae47a87536f62a23c417dc51174abf711cdb6e95341b3f',
                               'signature': 'self',
                               'calls': ['self._system_data_get_date', 'self.print_databank_close_report']},
 '_build_system_data_tab': {'lines': 46,
                            'sha256': 'a2b2a3727daf45822c8186a3262c6302a2ced138b68c01dcfee6fedd4ca4d30f',
                            'signature': 'self',
                            'calls': ['_dt.now',
                                      '_log_suppressed_once',
                                      'controls.columnconfigure',
                                      'controls.grid',
                                      'grid',
                                      'outer.columnconfigure',
                                      'outer.rowconfigure',
                                      'range',
                                      'self._get_databank_focus_date',
                                      'self._system_data_refresh_summary',
                                      'strftime',
                                      'summary.columnconfigure',
                                      'summary.grid',
                                      'summary.rowconfigure',
                                      'title.columnconfigure',
                                      'title.grid',
                                      'tk.StringVar',
                                      'ttk.Button',
                                      'ttk.Entry',
                                      'ttk.Frame',
                                      'ttk.Label',
                                      'ttk.LabelFrame']}}
SYSTEM_DATA_PRESENTATION_TARGETS = ['_show_system_data_tab', '_hide_system_data_tab', '_system_data_get_date', '_system_data_use_focus_date', '_system_data_refresh_summary', '_system_data_open_close', '_system_data_open_history', '_system_data_open_records', '_system_data_print_report', '_build_system_data_tab']
SYSTEM_DATA_PRESENTATION_SOURCE_LINES = {name: item['lines'] for name, item in _SYSTEM_DATA_PRESENTATION_METADATA.items()}
SYSTEM_DATA_PRESENTATION_SOURCE_SHA256 = {name: item['sha256'] for name, item in _SYSTEM_DATA_PRESENTATION_METADATA.items()}
SYSTEM_DATA_PRESENTATION_SIGNATURES = {name: item['signature'] for name, item in _SYSTEM_DATA_PRESENTATION_METADATA.items()}
SYSTEM_DATA_PRESENTATION_CALLS = {name: item['calls'] for name, item in _SYSTEM_DATA_PRESENTATION_METADATA.items()}
SYSTEM_DATA_PRESENTATION_TOTAL_SOURCE_LINES = 175

def _show_system_data_tab(self):
    try:
        tabs = set(self.nb.tabs())
        if str(self.tab_system_data) not in tabs:
            self.nb.add(self.tab_system_data, text='Data')
        else:
            self.nb.tab(self.tab_system_data, text='Data')
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_system_data_tab_show', 'suppressed exception excpass_system_data_tab_show', __spina_exc)
        pass

def _hide_system_data_tab(self):
    try:
        self.nb.hide(self.tab_system_data)
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_system_data_tab_hide', 'suppressed exception excpass_system_data_tab_hide', __spina_exc)
        pass

def _system_data_get_date(self):
    from datetime import datetime as _dt
    from tkinter import messagebox
    ds = ''
    try:
        ds = (self.system_data_date_var.get() or '').strip()
    except Exception:
        ds = ''
    if not ds:
        ds = (self._get_databank_focus_date() or '').strip()
        try:
            self.system_data_date_var.set(ds)
        except Exception:
            pass
    try:
        return _dt.strptime(ds, '%Y-%m-%d').strftime('%Y-%m-%d')
    except Exception:
        messagebox.showerror('Data', 'Use date format YYYY-MM-DD.')
        return ''

def _system_data_use_focus_date(self):
    try:
        ds = (self._get_databank_focus_date() or '').strip()
        if ds:
            self.system_data_date_var.set(ds)
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_system_data_focus_date', 'suppressed exception excpass_system_data_focus_date', __spina_exc)
        pass

def _system_data_refresh_summary(self):
    ds = self._system_data_get_date()
    if not ds:
        return

    def _fmt_amt(v):
        try:
            return fmt_currency(v)
        except Exception:
            try:
                return f"{float(v or 0.0):,.2f}"
            except Exception:
                return '0.00'

    try:
        reg_expected = round(float(self.db.get_databank_daily_total(ds, loan_type='Regular') or 0.0), 2)
    except Exception:
        reg_expected = 0.0
    try:
        x7_expected = round(float(self.db.get_databank_daily_total(ds, loan_type='7x7') or 0.0), 2)
    except Exception:
        x7_expected = 0.0

    rec = None
    try:
        rec = self.db.get_databank_day_close(ds) if hasattr(self, 'db') else None
    except Exception:
        rec = None

    if rec:
        expected = round(float(rec.get('expected_amount') or 0.0), 2)
        actual = round(float(rec.get('actual_cash') or 0.0), 2)
        variance = round(float(rec.get('variance') or 0.0), 2)
        variance_status = (rec.get('variance_status') or 'Balanced').strip()
        workflow = (rec.get('variance_workflow_status') or rec.get('workflow_status') or 'Open').strip()
        closed_txt = 'Closed' if bool(int(rec.get('is_closed') or 0)) else 'Open'
        note = (rec.get('note') or '').strip()
        note_txt = f"\nNote: {note}" if note else ''
        txt = (
            f"Date: {ds}\n"
            f"Regular Expected: {_fmt_amt(reg_expected)}\n"
            f"7x7 Expected: {_fmt_amt(x7_expected)}\n"
            f"Total Expected: {_fmt_amt(expected)}\n"
            f"Actual Cash: {_fmt_amt(actual)}\n"
            f"Variance: {_fmt_amt(abs(variance))} ({variance_status})\n"
            f"Workflow: {workflow} | Status: {closed_txt}{note_txt}"
        )
    else:
        combined = round(reg_expected + x7_expected, 2)
        txt = (
            f"Date: {ds}\n"
            f"Regular Expected: {_fmt_amt(reg_expected)}\n"
            f"7x7 Expected: {_fmt_amt(x7_expected)}\n"
            f"Total Expected: {_fmt_amt(combined)}\n"
            f"No Daily Close record yet for this date."
        )
    try:
        self.system_data_summary_var.set(txt)
    except Exception:
        pass

def _system_data_open_close(self):
    ds = self._system_data_get_date()
    if not ds:
        return
    try:
        self.open_databank_close_dialog(ds)
    finally:
        try:
            self._system_data_refresh_summary()
        except Exception:
            pass

def _system_data_open_history(self):
    ds = self._system_data_get_date()
    if not ds:
        return
    self.open_databank_close_history_dialog(ds)

def _system_data_open_records(self):
    ds = self._system_data_get_date()
    if not ds:
        return
    self.open_databank_close_records_dialog(start_date=ds, end_date=ds)

def _system_data_print_report(self):
    ds = self._system_data_get_date()
    if not ds:
        return
    self.print_databank_close_report(ds)

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

