"""Client add/edit form presentation extracted in Wave 38."""
from __future__ import annotations

_CLIENT_FORM_DEPENDENCIES = {}
_PROTECTED_GLOBALS = {
    "__builtins__", "__cached__", "__doc__", "__file__", "__loader__",
    "__name__", "__package__", "__spec__", "_CLIENT_FORM_DEPENDENCIES",
    "_PROTECTED_GLOBALS", "configure_client_form_dependencies",
    "CLIENT_FORM_SOURCE_SHA256", "CLIENT_FORM_TARGET",
}


def configure_client_form_dependencies(namespace):
    _CLIENT_FORM_DEPENDENCIES.clear()
    _CLIENT_FORM_DEPENDENCIES.update(namespace)
    for name, value in namespace.items():
        if name not in _PROTECTED_GLOBALS:
            globals()[name] = value


CLIENT_FORM_TARGET = '_app__client_form'
CLIENT_FORM_SOURCE_SHA256 = '27275a78cce0db295c824d3156f5dedb3945881ccf0de4ed25a075a2d31579b4'

def _app__client_form(self, title, initial=None, is_edit=False):
    # Client add/edit dialog with:
    # - Area dropdown (validated)
    # - Calendar pickers for dates
    # - Optional payment start offset (+1 day) checkbox stored as pay_start_offset_days
    init = dict(initial or {})
    lt = _app__norm_lt_value(self, init.get('loan_type') or self._mode_filter())

    win = tk.Toplevel(self.root)
    win.title(title)
    # Bigger client editor window; allow resizing for long fields / dropdowns.
    win.resizable(True, True)
    try:
        win.transient(self.root)
        win.grab_set()
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_0623', 'suppressed exception excpass_0623', __spina_exc)
        pass

    # Larger, easier-to-read editor text.
    try:
        import tkinter.font as _tkfont_client_editor
        _client_editor_font = _tkfont_client_editor.Font(family="Segoe UI", size=11)
        _client_editor_label_font = _tkfont_client_editor.Font(family="Segoe UI", size=11, weight="bold")
        _client_editor_button_font = _tkfont_client_editor.Font(family="Segoe UI", size=10)
    except Exception:
        _client_editor_font = None
        _client_editor_label_font = None
        _client_editor_button_font = None
    try:
        win.option_add("*TCombobox*Listbox.font", _client_editor_font)
    except Exception:
        pass

    # Vars
    name_var = tk.StringVar(value=str(init.get('name') or '').strip())
    contact_var = tk.StringVar(value=str(init.get('contact_number') or '').strip())
    loan_type_var = tk.StringVar(value=lt)
    area_var = tk.StringVar(value=str(init.get('area') or '').strip())
    principal_var = tk.StringVar(value=str(init.get('principal') or 0).strip())
    # interest rate stored as decimal (0.20) - only for Regular
    ir_init = init.get('interest_rate')
    if ir_init is None:
        ir_init = 0.20
    interest_var = tk.StringVar(value=str(ir_init))
    released_var = tk.StringVar(value=str(init.get('date_released') or '').strip())
    new_until_var = tk.StringVar(value=str(init.get('new_until') or '').strip())


    # Payment Term / Payment Amount / Payment Mode (optional)
    payterm_var = tk.StringVar(value=str(init.get('payment_term') or 'Daily').strip() or 'Daily')
    payamt_var = tk.StringVar(value=str(init.get('payment_amount') or '').strip())
    _pm_base0, _pm_other0 = _spina__split_payment_mode(init.get('payment_mode') or 'Cash')
    paymode_var = tk.StringVar(value=_pm_base0)
    paymode_other_var = tk.StringVar(value=_pm_other0)
    due_weekday_var = tk.StringVar(value=_spina__norm_weekday(init.get('due_weekday') or ''))
    semi_due_day1_var = tk.StringVar(value='' if init.get('semi_due_day1') in (None, '') else str(init.get('semi_due_day1')))
    semi_due_day2_var = tk.StringVar(value='' if init.get('semi_due_day2') in (None, '') else str(init.get('semi_due_day2')))
    monthly_due_day_var = tk.StringVar(value='' if init.get('monthly_due_day') in (None, '') else str(init.get('monthly_due_day')))
    flex_due_rule_var = tk.StringVar(value=str(init.get('flex_due_rule') or '').strip())

    # Friendly dropdown for flexible due schedules.
    # The database still stores compact rule codes, so existing collector-route logic remains stable.
    def _flex_due_options():
        opts = [
            ("Follow Payment Term", ""),

            ("Salary 5/20 - exact 5 and 20", "salary 5/20 window 0"),
            ("Salary 5/20 - before & after 1 day", "salary 5/20 window 1"),
            ("Salary 5/20 - before & after 2 days", "salary 5/20 window 2"),
            ("Salary 5/20 - before & after 3 days", "salary 5/20 window 3"),
            ("Salary 5/20 - common window dates", "days 4,5,6,19,20,21"),

            ("Salary 10/25 - exact 10 and 25", "salary 10/25 window 0"),
            ("Salary 10/25 - before & after 1 day", "salary 10/25 window 1"),
            ("Salary 10/25 - before & after 2 days", "salary 10/25 window 2"),
            ("Salary 10/25 - before & after 3 days", "salary 10/25 window 3"),
            ("Salary 10/25 - common window dates", "days 9,10,11,24,25,26"),

            ("Salary 15/30 - exact 15 and month-end", "salary 15/30 window 0"),
            ("Salary 15/30 - before & after 1 day", "salary 15/30 window 1"),
            ("Salary 15/30 - before & after 2 days", "salary 15/30 window 2"),
            ("Salary 15/30 - before & after 3 days", "salary 15/30 window 3"),
            ("Salary 15/30 - common window dates", "days 14,15,16,29,30,31"),

            ("Specific dates: 4,5,6,19,20,21", "days 4,5,6,19,20,21"),
            ("Specific dates: 9,10,11,24,25,26", "days 9,10,11,24,25,26"),
            ("Specific dates: 14,15,16,29,30,31", "days 14,15,16,29,30,31"),
        ]
        weekdays_full = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

        # Twice-a-week payment/reminder schedules.
        # These cover clients who are paid twice weekly or collect reliably on two weekdays.
        # Stored as compact codes like: "weekly Monday Thursday".
        common_twice_weekly = [
            ("Monday", "Thursday"),
            ("Tuesday", "Friday"),
            ("Wednesday", "Saturday"),
            ("Monday", "Wednesday"),
            ("Monday", "Friday"),
            ("Tuesday", "Saturday"),
        ]
        seen_twice = set()
        for a, b in common_twice_weekly:
            key = tuple(sorted((a, b)))
            seen_twice.add(key)
            opts.append((f"Twice weekly: {a} and {b}", f"weekly {a} {b}"))

        # Add every possible pair too, so the dropdown can handle unusual work schedules.
        for i, a in enumerate(weekdays_full):
            for b in weekdays_full[i + 1:]:
                key = tuple(sorted((a, b)))
                if key in seen_twice:
                    continue
                opts.append((f"Twice weekly: {a} and {b}", f"weekly {a} {b}"))

        ordinals = [("1st", "1st"), ("2nd", "2nd"), ("3rd", "3rd"), ("4th", "4th"), ("5th", "5th"), ("Last", "last")]
        for lbl_ord, code_ord in ordinals:
            for wd in weekdays_full:
                opts.append((f"Every {lbl_ord} {wd}", f"{code_ord} {wd}"))
        return opts

    _flex_due_pairs = _flex_due_options()
    _flex_due_label_to_code = {lbl: code for lbl, code in _flex_due_pairs}
    _flex_due_code_to_label = {}
    for _lbl, _code in _flex_due_pairs:
        if _code not in _flex_due_code_to_label:
            _flex_due_code_to_label[_code] = _lbl

    def _flex_due_label_from_code(code):
        try:
            c = str(code or '').strip()
        except Exception:
            c = ''
        if not c:
            return "Follow Payment Term"
        if c in _flex_due_code_to_label:
            return _flex_due_code_to_label[c]
        return f"Custom / legacy: {c}"

    _initial_flex_label = _flex_due_label_from_code(flex_due_rule_var.get())
    _flex_due_values = [lbl for lbl, _code in _flex_due_pairs]
    if _initial_flex_label not in _flex_due_values:
        _flex_due_values.append(_initial_flex_label)
    flex_due_choice_var = tk.StringVar(value=_initial_flex_label)

    def _flex_due_code_from_choice():
        try:
            label = str(flex_due_choice_var.get() or '').strip()
        except Exception:
            label = ''
        if label.startswith('Custom / legacy:'):
            code = label.split(':', 1)[1].strip()
        else:
            code = _flex_due_label_to_code.get(label, '')
        try:
            flex_due_rule_var.set(code)
        except Exception:
            pass
        return code

    is_new_var = tk.IntVar(value=1 if str(init.get('new_until') or '').strip() else 0)

    # Pay start offset:
    # 0 = same-day start, 1 = next-day start (optional)
    psod = init.get('pay_start_offset_days')
    try:
        psod = int(psod or 0)
    except Exception:
        psod = 0

    psod_var = tk.IntVar(value=1 if psod >= 1 else 0)

    def _current_anchor_for_form():
        try:
            dr = (released_var.get() or '').strip()
            if not dr:
                return None
            d0 = datetime.strptime(dr, "%Y-%m-%d").date()
            return d0 + timedelta(days=(1 if psod_var.get() else 0))
        except Exception:
            return None

    def _prime_due_defaults(force=False):
        _term = (payterm_var.get() or '').strip().title()
        _anchor = _current_anchor_for_form()
        if not _anchor:
            return
        try:
            if _term == 'Weekly' and (force or not (due_weekday_var.get() or '').strip()):
                due_weekday_var.set(_anchor.strftime('%a'))
            elif _term == 'Monthly' and (force or not (monthly_due_day_var.get() or '').strip()):
                monthly_due_day_var.set(str(_anchor.day))
            elif _term == 'Semi':
                import calendar as _cal
                if force or not (semi_due_day1_var.get() or '').strip():
                    semi_due_day1_var.set(str(_anchor.day))
                if force or not (semi_due_day2_var.get() or '').strip():
                    _other = _anchor + timedelta(days=15)
                    semi_due_day2_var.set(str(min(_other.day, _cal.monthrange(_other.year, _other.month)[1])))
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0622due', 'suppressed exception excpass_0622due', __spina_exc)
            pass

    if not (due_weekday_var.get() or '').strip() and not (monthly_due_day_var.get() or '').strip() and not (semi_due_day1_var.get() or '').strip() and not (semi_due_day2_var.get() or '').strip():
        _prime_due_defaults(force=True)

    # Layout
    outer = ttk.Frame(win, padding=18)
    outer.pack(fill='both', expand=True)

    def row(label, widget, r):
        ttk.Label(outer, text=label, font=_client_editor_label_font).grid(row=r, column=0, sticky='w', padx=(0,14), pady=7)
        widget.grid(row=r, column=1, sticky='we', pady=7)
    outer.columnconfigure(1, weight=1)

    r = 0
    row("Name:", ttk.Entry(outer, textvariable=name_var, width=46), r); r += 1
    row("Contact No:", ttk.Entry(outer, textvariable=contact_var, width=46), r); r += 1

    # Loan type (readonly; locked on edit)
    lt_cb = ttk.Combobox(outer, textvariable=loan_type_var, values=('Regular','7x7'), state='readonly', width=44)
    row("Loan Type:", lt_cb, r); r += 1
    if is_edit:
        try: lt_cb.config(state='disabled')
        except Exception: pass

    # Managed hierarchical Area selector
    from spina_app.area_hierarchy_ui import build_simple_area_selector
    area_frame = build_simple_area_selector(self, outer, area_var, width=34)
    row("Area:", area_frame, r); r += 1

    row("Principal:", ttk.Entry(outer, textvariable=principal_var, width=46), r); r += 1

    ir_entry = ttk.Entry(outer, textvariable=interest_var, width=46)
    row("Interest Rate:", ir_entry, r); r += 1


    # Payment Term / Amount / Mode
    pt_cb = ttk.Combobox(outer, textvariable=payterm_var, values=('Daily','Weekly','Semi','Monthly'), state='readonly', width=44)
    row("Payment Term:", pt_cb, r); r += 1

    due_weekday_cb = ttk.Combobox(outer, textvariable=due_weekday_var, values=('Mon','Tue','Wed','Thu','Fri','Sat','Sun'), state='readonly', width=44)
    row("Due Weekday:", due_weekday_cb, r); r += 1

    def _dom_seed_date(_day_val=None):
        try:
            _base = _current_anchor_for_form() or date.today()
        except Exception:
            _base = date.today()
        try:
            _dom = _spina__norm_dom(_day_val)
        except Exception:
            _dom = None
        if _dom is None:
            return _base
        try:
            _last = calendar.monthrange(_base.year, _base.month)[1]
            return date(_base.year, _base.month, min(max(1, int(_dom)), _last))
        except Exception:
            return _base

    def _pick_dom(var_obj, title_text):
        try:
            _initial = _dom_seed_date(var_obj.get())
        except Exception:
            _initial = None
        _picked = pick_date(win, initial=(_initial.strftime("%Y-%m-%d") if _initial else None), title=title_text)
        try:
            if _picked is None:
                return
            var_obj.set(str(int(_picked.day)))
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0628dompick', 'suppressed exception excpass_0628dompick', __spina_exc)
            pass

    semi_frame = ttk.Frame(outer)
    semi1_frame = ttk.Frame(semi_frame)
    semi1_frame.pack(side='left')
    semi1_entry = ttk.Entry(semi1_frame, textvariable=semi_due_day1_var, width=12, state='readonly', justify='center')
    semi1_entry.pack(side='left')
    semi1_btn = ttk.Button(semi1_frame, text="📅", width=3, command=lambda: _pick_dom(semi_due_day1_var, "Semi Due Day 1"))
    semi1_btn.pack(side='left', padx=(4, 0))
    ttk.Label(semi_frame, text='/').pack(side='left', padx=6)
    semi2_frame = ttk.Frame(semi_frame)
    semi2_frame.pack(side='left')
    semi2_entry = ttk.Entry(semi2_frame, textvariable=semi_due_day2_var, width=12, state='readonly', justify='center')
    semi2_entry.pack(side='left')
    semi2_btn = ttk.Button(semi2_frame, text="📅", width=3, command=lambda: _pick_dom(semi_due_day2_var, "Semi Due Day 2"))
    semi2_btn.pack(side='left', padx=(4, 0))
    row("Semi Due Days:", semi_frame, r); r += 1

    monthly_due_frame = ttk.Frame(outer)
    monthly_due_entry = ttk.Entry(monthly_due_frame, textvariable=monthly_due_day_var, width=32, state='readonly', justify='center')
    monthly_due_entry.pack(side='left', fill='x', expand=True)
    monthly_due_btn = ttk.Button(monthly_due_frame, text="📅", width=3, command=lambda: _pick_dom(monthly_due_day_var, "Monthly Due Day"))
    monthly_due_btn.pack(side='left', padx=6)
    row("Monthly Due Day:", monthly_due_frame, r); r += 1

    flex_due_frame = ttk.Frame(outer)
    flex_due_cb = ttk.Combobox(
        flex_due_frame,
        textvariable=flex_due_choice_var,
        values=_flex_due_values,
        state='readonly',
        width=52,
    )
    flex_due_cb.pack(side='left', fill='x', expand=True)
    ttk.Label(
        flex_due_frame,
        text="Used for DUE TODAY reminders in Collector Route",
        foreground="#666666"
    ).pack(side='left', padx=(8,0))
    try:
        flex_due_cb.bind('<<ComboboxSelected>>', lambda _e=None: _flex_due_code_from_choice())
    except Exception:
        pass
    row("Flexible Due Rule:", flex_due_frame, r); r += 1

    row("Payment Amount:", ttk.Entry(outer, textvariable=payamt_var, width=46), r); r += 1
    pm_cb = ttk.Combobox(outer, textvariable=paymode_var, values=_SPINA_PAYMENT_MODE_OPTIONS, state='readonly', width=44)
    row("Mode of Payment:", pm_cb, r); r += 1
    pm_other_entry = ttk.Entry(outer, textvariable=paymode_other_var, width=46)
    row("Other Payment Mode:", pm_other_entry, r); r += 1
    # Date Released
    rel_frame = ttk.Frame(outer)
    rel_entry = ttk.Entry(rel_frame, textvariable=released_var, width=32)
    rel_entry.pack(side='left', fill='x', expand=True)
    ttk.Button(rel_frame, text="📅", width=3, command=lambda: pick_date(win, released_var, title="Date Released")).pack(side='left', padx=6)
    row("Date Released:", rel_frame, r); r += 1

    # Computed labels
    start_pay_lbl = ttk.Label(outer, text="")
    row("Start of Payment:", start_pay_lbl, r); r += 1

    due_lbl = ttk.Label(outer, text="")
    row("Due Date:", due_lbl, r); r += 1

    # New until
    new_frame = ttk.Frame(outer)
    new_chk = ttk.Checkbutton(new_frame, text="Mark as NEW", variable=is_new_var)
    new_chk.pack(side='left')
    nu_entry = ttk.Entry(new_frame, textvariable=new_until_var, width=24)
    nu_entry.pack(side='left', padx=6)
    ttk.Button(new_frame, text="📅", width=3, command=lambda: pick_date(win, new_until_var, title="New Until")).pack(side='left', padx=4)
    row("New Tag:", new_frame, r); r += 1

    # Payment start offset
    psod_chk = ttk.Checkbutton(outer, text="Next day start (+1 day after release)", variable=psod_var)
    psod_chk.grid(row=r, column=1, sticky='w', pady=6); r += 1

    def _toggle_new_until(*_):
        try:
            if is_new_var.get():
                nu_entry.config(state='normal')
            else:
                new_until_var.set("")
                nu_entry.config(state='disabled')
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0627', 'suppressed exception excpass_0627', __spina_exc)
            pass

    def _toggle_due_widgets(*_):
        _term = (payterm_var.get() or '').strip().title()
        try:
            due_weekday_cb.config(state='readonly' if _term == 'Weekly' else 'disabled')
        except Exception:
            pass
        try:
            semi_state = 'readonly' if _term == 'Semi' else 'disabled'
            semi_btn_state = 'normal' if _term == 'Semi' else 'disabled'
            semi1_entry.config(state=semi_state)
            semi2_entry.config(state=semi_state)
            semi1_btn.config(state=semi_btn_state)
            semi2_btn.config(state=semi_btn_state)
        except Exception:
            pass
        try:
            monthly_due_entry.config(state=('readonly' if _term == 'Monthly' else 'disabled'))
            monthly_due_btn.config(state=('normal' if _term == 'Monthly' else 'disabled'))
        except Exception:
            pass
        _prime_due_defaults(force=False)

    def _toggle_paymode_other(*_):
        try:
            is_other = ((paymode_var.get() or '').strip() == 'Others')
        except Exception:
            is_other = False
        try:
            pm_other_entry.config(state=('normal' if is_other else 'disabled'))
        except Exception:
            pass
        if not is_other:
            try:
                paymode_other_var.set('')
            except Exception:
                pass

    def _compute_dates(*_):
        lt_local = _app__norm_lt_value(self, loan_type_var.get())
        due_days = 49 if lt_local == '7x7' else 120
        try:
            dr = released_var.get().strip()
            d0 = datetime.strptime(dr, "%Y-%m-%d").date()
            offset = 1 if psod_var.get() else 0
            sp = d0 + timedelta(days=offset)
            start_pay_lbl.config(text=sp.strftime("%Y-%m-%d"))
            due_lbl.config(text=(d0 + timedelta(days=due_days)).strftime("%Y-%m-%d"))
        except Exception:
            start_pay_lbl.config(text="")
            due_lbl.config(text="")
        try:
            _prime_due_defaults(force=False)
        except Exception:
            pass
        try:
            if lt_local == '7x7':
                interest_var.set("0")
                ir_entry.config(state='disabled')
            else:
                ir_entry.config(state='normal')
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0628', 'suppressed exception excpass_0628', __spina_exc)
            pass

    try:
        is_new_var.trace_add('write', _toggle_new_until)
    except Exception as e:
        _log_ignored("ui.trace_add failed", e, key="ui.trace_add_failed")
    try:
        released_var.trace_add('write', _compute_dates)
        psod_var.trace_add('write', _compute_dates)
        loan_type_var.trace_add('write', _compute_dates)
        payterm_var.trace_add('write', _toggle_due_widgets)
        paymode_var.trace_add('write', _toggle_paymode_other)
    except Exception as e:
        _log_ignored("ui.trace_add failed", e, key="ui.trace_add_failed")
    _toggle_new_until()
    _toggle_due_widgets()
    _toggle_paymode_other()
    _compute_dates()

    # Buttons
    btns = ttk.Frame(outer)
    btns.grid(row=r, column=0, columnspan=2, sticky='e', pady=(10,0))
    result = {"ok": False}

    def _validate_date(s):
        s = (s or '').strip()
        if not s:
            return ""
        datetime.strptime(s[:10], "%Y-%m-%d")
        return s[:10]

    def save():
        nm = " ".join(name_var.get().strip().split())
        if not nm:
            messagebox.showerror("Required", "Client name is required.", parent=win)
            return
        lt_local = _app__norm_lt_value(self, loan_type_var.get())
        try:
            p = float(principal_var.get().strip() or 0)
        except Exception:
            messagebox.showerror("Invalid", "Principal must be a number.", parent=win)
            return
        try:
            dr = _validate_date(released_var.get())
        except Exception:
            messagebox.showerror("Invalid", "Date Released must be YYYY-MM-DD.", parent=win)
            return
        if is_new_var.get():
            try:
                nu = _validate_date(new_until_var.get())
            except Exception:
                messagebox.showerror("Invalid", "New Until must be YYYY-MM-DD.", parent=win)
                return
        else:
            nu = ""
        if lt_local == '7x7':
            ir = 0.0
        else:
            try:
                ir = float(interest_var.get().strip() or 0.20)
                if ir > 1.0:
                    ir = ir / 100.0
            except Exception:
                messagebox.showerror("Invalid", "Interest rate must be a number.", parent=win)
                return

        # Payment term / amount
        pt = (payterm_var.get() or '').strip() or 'Daily'
        if pt not in ('Daily','Weekly','Semi','Monthly'):
            pt2 = pt.lower().replace(' ', '').replace('-', '').replace('_', '')
            if 'week' in pt2:
                pt = 'Weekly'
            elif 'semi' in pt2 or 'bi' in pt2:
                pt = 'Semi'
            elif 'month' in pt2:
                pt = 'Monthly'
            else:
                pt = 'Daily'
        try:
            pa_txt = (payamt_var.get() or '').strip()
            pa = float(pa_txt.replace(',', '.').strip()) if pa_txt else 0.0
        except Exception:
            messagebox.showerror("Invalid", "Payment Amount must be a number.", parent=win)
            return

        due_weekday_val = _spina__norm_weekday(due_weekday_var.get())
        semi_due1_val = _spina__norm_dom(semi_due_day1_var.get())
        semi_due2_val = _spina__norm_dom(semi_due_day2_var.get())
        monthly_due_val = _spina__norm_dom(monthly_due_day_var.get())

        if pt == 'Weekly' and not due_weekday_val:
            messagebox.showerror("Required", "Due Weekday is required for Weekly payment term.", parent=win)
            return
        if pt == 'Semi' and (semi_due1_val is None or semi_due2_val is None):
            messagebox.showerror("Required", "Both Semi Due Days are required for Semi payment term.", parent=win)
            return
        if pt == 'Monthly' and monthly_due_val is None:
            messagebox.showerror("Required", "Monthly Due Day is required for Monthly payment term.", parent=win)
            return

        if pt != 'Weekly':
            due_weekday_val = ''
        if pt != 'Semi':
            semi_due1_val = None
            semi_due2_val = None
        if pt != 'Monthly':
            monthly_due_val = None

        flex_due_rule_val = (_flex_due_code_from_choice() or '').strip()

        res = {
            "name": nm,
            "contact_number": contact_var.get().strip(),
            "payment_term": pt,
            "payment_amount": pa,
            "payment_mode": _spina__merge_payment_mode((paymode_var.get() or '').strip() or 'Cash', (paymode_other_var.get() or '').strip()),
            "due_weekday": due_weekday_val,
            "semi_due_day1": semi_due1_val,
            "semi_due_day2": semi_due2_val,
            "monthly_due_day": monthly_due_val,
            "flex_due_rule": flex_due_rule_val,
            "loan_type": lt_local,
            "area": area_var.get().strip(),
            "principal": p,
            "interest_rate": ir,
            "date_released": dr,
            "new_until": nu,
            "pay_start_offset_days": 1 if psod_var.get() else 0,
        }
        result["ok"] = True
        result["data"] = res
        try:
            win.destroy()
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0629', 'suppressed exception excpass_0629', __spina_exc)
            pass

    def cancel():
        try:
            win.destroy()
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0630', 'suppressed exception excpass_0630', __spina_exc)
            pass

    ttk.Button(btns, text="Cancel", command=cancel).pack(side='right')
    ttk.Button(btns, text="Save", command=save).pack(side='right', padx=8)

    # Apply bigger font to all editor controls without changing app-wide styles.
    try:
        def _spina_apply_client_editor_font(_w):
            try:
                cls = _w.winfo_class()
            except Exception:
                cls = ""
            try:
                if cls in ("TEntry", "TCombobox", "TCheckbutton", "TLabel"):
                    if cls == "TLabel":
                        # Keep already-bold field labels; normal labels get the readable base font.
                        try:
                            if not str(_w.cget("font")).strip():
                                _w.configure(font=_client_editor_font)
                        except Exception:
                            _w.configure(font=_client_editor_font)
                    else:
                        _w.configure(font=_client_editor_font)
                elif cls in ("TButton",):
                    _w.configure(font=_client_editor_button_font)
            except Exception:
                pass
            try:
                for _ch in _w.winfo_children():
                    _spina_apply_client_editor_font(_ch)
            except Exception:
                pass

        _spina_apply_client_editor_font(win)
        win.minsize(760, 720)
    except Exception as __spina_exc:
        _log_suppressed_once('client_editor_font_patch', 'suppressed exception client_editor_font_patch', __spina_exc)
        pass

    try:
        win.bind("<Escape>", lambda e: cancel())
        win.bind("<Return>", lambda e: save())
    except Exception as e:
        _log_ignored("ui.bind failed", e, key="ui.bind_failed")


    # Center dialog on screen (or over main window)
    try:
        win.update_idletasks()
        try:
            self.root.update_idletasks()
        except Exception:
            pass

        w = win.winfo_width()
        h = win.winfo_height()

        pw = self.root.winfo_width()
        ph = self.root.winfo_height()
        if pw and ph and pw > 50 and ph > 50:
            px = self.root.winfo_rootx()
            py = self.root.winfo_rooty()
            x = px + (pw - w) // 2
            y = py + (ph - h) // 2
        else:
            sw = win.winfo_screenwidth()
            sh = win.winfo_screenheight()
            x = (sw - w) // 2
            y = (sh - h) // 2

        win.geometry(f"+{max(int(x), 0)}+{max(int(y), 0)}")
        try:
            win.lift()
        except Exception:
            pass
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_0642', 'suppressed exception excpass_0642', __spina_exc)
        pass

    self.root.wait_window(win)
    if result.get("ok"):
        return result.get("data")
    return None
