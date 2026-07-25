"""Calendar and date-picker presentation extracted in Wave 41."""
from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
import tkinter as tk
from tkinter import messagebox, ttk

_CALENDAR_DEPENDENCIES = {}
_PROTECTED_GLOBALS = {
    '__builtins__', '__cached__', '__doc__', '__file__', '__loader__',
    '__name__', '__package__', '__spec__', '_CALENDAR_DEPENDENCIES',
    '_PROTECTED_GLOBALS', 'configure_calendar_dependencies',
    'CALENDAR_TARGETS', 'CALENDAR_SOURCE_LINES', 'CALENDAR_SOURCE_SHA256',
    'CALENDAR_METHODS', 'calendar', 'date', 'datetime', 'timedelta',
    'tk', 'ttk', 'messagebox',
}


def configure_calendar_dependencies(namespace):
    _CALENDAR_DEPENDENCIES.clear()
    _CALENDAR_DEPENDENCIES.update(namespace)
    for name, value in namespace.items():
        if name not in _PROTECTED_GLOBALS:
            globals()[name] = value


CALENDAR_TARGETS = ['_CalendarPopup', '_CalendarRangePopup', 'pick_date_range', 'pick_date']
CALENDAR_SOURCE_LINES = {'_CalendarPopup': 129, '_CalendarRangePopup': 196, 'pick_date_range': 44, 'pick_date': 30}
CALENDAR_SOURCE_SHA256 = {'_CalendarPopup': '2b3d53bd8311c04e77e487523032f81f815ddd9042c2561f528fb2d9201a4566', '_CalendarRangePopup': '948417432b06896c6ffe6099ab754837716cff5b85eadbb0ee2294e022dddf3d', 'pick_date_range': '3af01720d3a2295fd618a442abbb1ae814742bf662b954bba85427abee05df45', 'pick_date': '1d19e6cb0141bd22531b37ae48748dac1c24dbde39479c84f3406922820cf9ad'}
CALENDAR_METHODS = {'_CalendarPopup': ['__init__', '_build_ui', '_render', '_pick', '_prev_month', '_next_month', '_today', '_clear', '_close'], '_CalendarRangePopup': ['__init__', '_build_ui', '_render', '_refresh_info', '_pick', '_apply', '_prev_month', '_next_month', '_today', '_clear', '_close']}

class _CalendarPopup(tk.Toplevel):
    def __init__(self, master, init_date=None, title="Select Date"):
        super().__init__(master)
        self.title(title)
        self.resizable(False, False)
        self.transient(master)
        try:
            self.grab_set()
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0017', 'suppressed exception excpass_0017', __spina_exc)
            pass

        self.selected = None
        if init_date is None:
            init_date = date.today()
        self._year = int(init_date.year)
        self._month = int(init_date.month)

        self._cal = calendar.Calendar(firstweekday=6)  # Sunday-first
        self._build_ui()
        self._render()

        self.bind("<Escape>", lambda e: self._close())
        self.protocol("WM_DELETE_WINDOW", self._close)

        self.update_idletasks()
        try:
            x = master.winfo_rootx() + (master.winfo_width() // 2 - self.winfo_width() // 2)
            y = master.winfo_rooty() + (master.winfo_height() // 2 - self.winfo_height() // 2)
            self.geometry(f"+{x}+{y}")
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0018', 'suppressed exception excpass_0018', __spina_exc)
            pass

    def _build_ui(self):
        outer = ttk.Frame(self, padding=10)
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer)
        header.pack(fill="x")

        ttk.Button(header, text="◀", width=3, command=self._prev_month).pack(side="left")
        self._lbl = ttk.Label(header, text="", width=18, anchor="center", font=("TkDefaultFont", 10, "bold"))
        self._lbl.pack(side="left", padx=6)
        ttk.Button(header, text="▶", width=3, command=self._next_month).pack(side="left")

        days = ttk.Frame(outer)
        days.pack(fill="x", pady=(8, 2))
        for d in ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]:
            ttk.Label(days, text=d, width=4, anchor="center").pack(side="left")

        self._grid = ttk.Frame(outer)
        self._grid.pack(fill="both", expand=True)

        self._btns = []
        for _r in range(6):
            row = ttk.Frame(self._grid)
            row.pack(fill="x")
            row_btns = []
            for _c in range(7):
                b = ttk.Button(row, text="", width=4)
                b.pack(side="left", padx=1, pady=1)
                row_btns.append(b)
            self._btns.append(row_btns)

        footer = ttk.Frame(outer)
        footer.pack(fill="x", pady=(8, 0))
        ttk.Button(footer, text="Today", command=self._today).pack(side="left")
        ttk.Button(footer, text="Clear", command=self._clear).pack(side="left", padx=6)
        ttk.Button(footer, text="Close", command=self._close).pack(side="right")

    def _render(self):
        try:
            month_name = datetime(self._year, self._month, 1).strftime("%B %Y")
        except Exception:
            month_name = f"{self._year}-{self._month:02d}"
        self._lbl.configure(text=month_name)

        weeks = self._cal.monthdayscalendar(self._year, self._month)
        while len(weeks) < 6:
            weeks.append([0]*7)

        for r in range(6):
            for c in range(7):
                day = weeks[r][c]
                b = self._btns[r][c]
                if day == 0:
                    b.configure(text="", state="disabled", command=lambda: None)
                else:
                    b.configure(text=str(day), state="normal")
                    b.configure(command=lambda d=day: self._pick(d))

    def _pick(self, day):
        try:
            self.selected = date(self._year, self._month, int(day))
        except Exception:
            self.selected = None
        self._close()

    def _prev_month(self):
        self._month -= 1
        if self._month <= 0:
            self._month = 12
            self._year -= 1
        self._render()

    def _next_month(self):
        self._month += 1
        if self._month >= 13:
            self._month = 1
            self._year += 1
        self._render()

    def _today(self):
        td = date.today()
        self._year, self._month = td.year, td.month
        self._render()

    def _clear(self):
        self.selected = None
        self._close()

    def _close(self):
        try:
            self.grab_release()
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0019', 'suppressed exception excpass_0019', __spina_exc)
            pass
        self.destroy()


class _CalendarRangePopup(tk.Toplevel):
    def __init__(self, master, init_date=None, init_start=None, init_end=None, title="Select Date Range"):
        super().__init__(master)
        self.title(title)
        self.resizable(False, False)
        self.transient(master)
        try:
            self.grab_set()
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0020', 'suppressed exception excpass_0020', __spina_exc)
            pass

        self.selected_start = init_start
        self.selected_end = init_end
        self._stage = 0  # 0=pick start, 1=pick end
        if self.selected_start and self.selected_end:
            self._stage = 0
        elif self.selected_start and not self.selected_end:
            self._stage = 1

        if init_date is None:
            if self.selected_start:
                init_date = self.selected_start
            elif self.selected_end:
                init_date = self.selected_end
            else:
                init_date = date.today()

        self._year = int(init_date.year)
        self._month = int(init_date.month)

        self._cal = calendar.Calendar(firstweekday=6)  # Sunday-first
        self._build_ui()
        self._render()
        self._refresh_info()

        self.bind("<Escape>", lambda e: self._close())
        self.protocol("WM_DELETE_WINDOW", self._close)

        self.update_idletasks()
        try:
            x = master.winfo_rootx() + (master.winfo_width() // 2 - self.winfo_width() // 2)
            y = master.winfo_rooty() + (master.winfo_height() // 2 - self.winfo_height() // 2)
            self.geometry(f"+{x}+{y}")
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0021', 'suppressed exception excpass_0021', __spina_exc)
            pass

    def _build_ui(self):
        outer = ttk.Frame(self, padding=10)
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer)
        header.pack(fill="x")

        ttk.Button(header, text="◀", width=3, command=self._prev_month).pack(side="left")
        self._lbl = ttk.Label(header, text="", width=18, anchor="center", font=("TkDefaultFont", 10, "bold"))
        self._lbl.pack(side="left", padx=6)
        ttk.Button(header, text="▶", width=3, command=self._next_month).pack(side="left")

        self._info = ttk.Label(outer, text="", anchor="center")
        self._info.pack(fill="x", pady=(6, 2))

        days = ttk.Frame(outer)
        days.pack(fill="x", pady=(6, 2))
        for d in ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]:
            ttk.Label(days, text=d, width=4, anchor="center").pack(side="left")

        self._grid = ttk.Frame(outer)
        self._grid.pack(fill="both", expand=True)

        self._btns = []
        for _r in range(6):
            row = ttk.Frame(self._grid)
            row.pack(fill="x")
            row_btns = []
            for _c in range(7):
                b = ttk.Button(row, text="", width=4)
                b.pack(side="left", padx=1, pady=1)
                row_btns.append(b)
            self._btns.append(row_btns)

        footer = ttk.Frame(outer)
        footer.pack(fill="x", pady=(8, 0))
        ttk.Button(footer, text="Today", command=self._today).pack(side="left")
        ttk.Button(footer, text="Clear", command=self._clear).pack(side="left", padx=6)
        self._btn_apply = ttk.Button(footer, text="Apply", command=self._apply)
        self._btn_apply.pack(side="right", padx=(6, 0))
        ttk.Button(footer, text="Close", command=self._close).pack(side="right")

    def _render(self):
        try:
            month_name = datetime(self._year, self._month, 1).strftime("%B %Y")
        except Exception:
            month_name = f"{self._year}-{self._month:02d}"
        self._lbl.configure(text=month_name)

        weeks = self._cal.monthdayscalendar(self._year, self._month)
        while len(weeks) < 6:
            weeks.append([0]*7)

        for r in range(6):
            for c in range(7):
                day = weeks[r][c]
                b = self._btns[r][c]
                if day == 0:
                    b.configure(text="", state="disabled", command=lambda: None)
                else:
                    b.configure(text=str(day), state="normal")
                    b.configure(command=lambda d=day: self._pick(d))

        # Apply enabled only if a start is selected
        try:
            if self.selected_start is None:
                self._btn_apply.state(["disabled"])
            else:
                self._btn_apply.state(["!disabled"])
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0022', 'suppressed exception excpass_0022', __spina_exc)
            pass

    def _refresh_info(self):
        s = self.selected_start.strftime("%Y-%m-%d") if self.selected_start else "—"
        e = self.selected_end.strftime("%Y-%m-%d") if self.selected_end else "—"
        hint = "Click START date, then END date."
        if self.selected_start and not self.selected_end:
            hint = "Now click the END date (or click Apply for 1-day range)."
        self._info.configure(text=f"Start: {s}    End: {e}    • {hint}")

    def _pick(self, day):
        try:
            d = date(self._year, self._month, int(day))
        except Exception:
            return
        if self.selected_start is None or (self.selected_start is not None and self.selected_end is not None):
            # start new selection
            self.selected_start = d
            self.selected_end = None
            self._stage = 1
            self._refresh_info()
            self._render()
            return

        # choosing end
        if self.selected_start is not None and self.selected_end is None:
            if d < self.selected_start:
                self.selected_end = self.selected_start
                self.selected_start = d
            else:
                self.selected_end = d
            self._stage = 0
            # auto-apply once both are chosen
            self._apply()
            return

    def _apply(self):
        if self.selected_start is None:
            return
        if self.selected_end is None:
            self.selected_end = self.selected_start
        self._close()

    def _prev_month(self):
        self._month -= 1
        if self._month <= 0:
            self._month = 12
            self._year -= 1
        self._render()
        self._refresh_info()

    def _next_month(self):
        self._month += 1
        if self._month >= 13:
            self._month = 1
            self._year += 1
        self._render()
        self._refresh_info()

    def _today(self):
        td = date.today()
        self._year, self._month = td.year, td.month
        self._render()
        self._refresh_info()

    def _clear(self):
        self.selected_start = None
        self.selected_end = None
        self._close()

    def _close(self):
        try:
            self.grab_release()
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0023', 'suppressed exception excpass_0023', __spina_exc)
            pass
        self.destroy()

def pick_date_range(parent, start_var, end_var, initial_start=None, initial_end=None, title="Select Date Range"):
    # Open a simple date-range picker. Click start then end. Apply sets end=start if omitted.
    init_start = None
    init_end = None
    try:
        if initial_start:
            init_start = _parse_ymd(initial_start)
        elif start_var is not None and str(start_var.get()).strip():
            init_start = _parse_ymd(start_var.get())
    except Exception:
        init_start = None
    try:
        if initial_end:
            init_end = _parse_ymd(initial_end)
        elif end_var is not None and str(end_var.get()).strip():
            init_end = _parse_ymd(end_var.get())
    except Exception:
        init_end = None

    init_date = init_start or init_end or date.today()
    pop = _CalendarRangePopup(parent, init_date=init_date, init_start=init_start, init_end=init_end, title=title)
    parent.wait_window(pop)

    if pop.selected_start is None and pop.selected_end is None:
        # User clicked Clear in the range picker -> clear bound vars too
        try:
            if start_var is not None:
                start_var.set("")
            if end_var is not None:
                end_var.set("")
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0024', 'suppressed exception excpass_0024', __spina_exc)
            pass
        return None

    try:
        if start_var is not None and pop.selected_start is not None:
            start_var.set(pop.selected_start.strftime("%Y-%m-%d"))
        if end_var is not None and pop.selected_end is not None:
            end_var.set(pop.selected_end.strftime("%Y-%m-%d"))
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_0025', 'suppressed exception excpass_0025', __spina_exc)
        pass
    return (pop.selected_start, pop.selected_end)

def pick_date(parent, var=None, initial=None, title="Select Date"):
    # Open a simple calendar popup. If var is provided, sets var to YYYY-MM-DD (or '' if cleared).
    init_date = None
    try:
        if initial:
            init_date = _parse_ymd(initial)
        elif var is not None and str(var.get()).strip():
            init_date = _parse_ymd(var.get())
    except Exception:
        init_date = None
    if init_date is None:
        init_date = date.today()

    pop = _CalendarPopup(parent, init_date=init_date, title=title)
    parent.wait_window(pop)
    if pop.selected is None:
        if var is not None:
            try:
                var.set("")
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_0026', 'suppressed exception excpass_0026', __spina_exc)
                pass
        return None
    if var is not None:
        try:
            var.set(pop.selected.strftime("%Y-%m-%d"))
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0027', 'suppressed exception excpass_0027', __spina_exc)
            pass
    return pop.selected
