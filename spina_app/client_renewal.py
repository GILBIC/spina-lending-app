from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Mapping

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

_CLIENT_RENEWAL_DEPENDENCIES: dict[str, Any] = {}


def configure_client_renewal_dependencies(namespace: Mapping[str, Any]) -> None:
    _CLIENT_RENEWAL_DEPENDENCIES.clear()
    _CLIENT_RENEWAL_DEPENDENCIES.update(namespace)
    protected = {"__name__", "__file__", "__package__", "__builtins__", "_CLIENT_RENEWAL_DEPENDENCIES", "configure_client_renewal_dependencies"}
    for name, value in namespace.items():
        if name not in protected:
            globals()[name] = value
    global _SPINA_ORIG_LOANDB_RENEW_CLIENT
    if _SPINA_ORIG_LOANDB_RENEW_CLIENT is None:
        loan_db = namespace.get("LoanDB")
        _SPINA_ORIG_LOANDB_RENEW_CLIENT = getattr(loan_db, "renew_client", None) if loan_db is not None else None


_SPINA_ORIG_LOANDB_RENEW_CLIENT = None

class RenewDialog(simpledialog.Dialog):
    """Renew (reloan) dialog.

    Auto-computes **Released Cash** using:
        released_cash = max(0, new_principal - remaining_due)

    remaining_due is based on the current cycle:
        Regular: remaining_due = max(0, total_to_pay - paid_total)
        7x7:     remaining_due = remaining_principal + unpaid_interest_arrears

    You can still override Released Cash manually; click **Auto** to recompute.
    """
    def __init__(self, parent, title=None, initial=None, loan_type='Regular', db=None):
        self.client = initial or {}
        self.loan_type = (loan_type or 'Regular')
        self.db = db
        self.result = None

        # When True, Released Cash keeps syncing from the auto-compute formula.
        self._auto_rc = True
        self._last_stats = None
        super().__init__(parent, title or 'Renew Client')

    def _parse_float(self, v):
        try:
            s = str(v or '').strip()
        except Exception:
            s = ''
        if not s:
            return None
        s = s.replace(',', '')
        try:
            return float(s)
        except Exception:
            return None

    def _valid_ymd(self, s):
        s = (s or '').strip()[:10]
        if not s:
            return None
        try:
            datetime.strptime(s, "%Y-%m-%d")
            return s
        except Exception:
            return None

    def _compute_stats(self):
        """Return dict with paid/remaining/suggested released cash (best-effort).

        Regular:
            remaining_due = max(0, total_to_pay - paid_total)

        7x7:
            remaining_due = remaining_principal + unpaid_interest_arrears (arrears must be cleared first).
            Uses the same rule as the SOA:
              - Daily interest = ceil(remaining_principal / 1000) * 7  (1..1000=7, 1001..2000=14, ...)
              - Interest accrues per day-gap; payment pays INTEREST first, then PRINCIPAL
              - Unpaid interest carries forward (arrears)
        """
        if not self.db:
            return None

        name = (self.client.get('name') or '').strip()
        if not name:
            return None

        # Normalize LT (Regular vs 7x7)
        try:
            lt = self.db._effective_lt(self.loan_type)
        except Exception:
            lt = (self.loan_type or 'Regular')

        lt_s = str(lt or '').lower().replace('×', 'x')
        is_7x7 = ('7x7' in lt_s) or ('emer' in lt_s)

        # Renew date (end of window)
        renew_date = self._valid_ymd(self.date_var.get()) or date.today().strftime("%Y-%m-%d")

        # Cycle start date:
        # Prefer manual payment_start_date, else date_released + pay_start_offset_days
        start_date = self._valid_ymd(str(self.client.get('payment_start_date') or ''))

        # Safety: after renew, a stale payment_start_date can remain (old cycle or equal to release date).
        # If it is <= date_released, ignore it so we fall back to Released + offset.
        try:
            _base_chk = self._valid_ymd(str(self.client.get('date_released') or ''))
        except Exception:
            _base_chk = None
        try:
            _off_chk = int(self.client.get('pay_start_offset_days') or 0)
        except Exception:
            _off_chk = 0
        _off_chk = 1 if _off_chk >= 1 else 0
        if start_date and _base_chk:
            if start_date < _base_chk or (_off_chk == 1 and start_date == _base_chk):
                start_date = None

        if not start_date:
            base = self._valid_ymd(str(self.client.get('date_released') or ''))
            start_date = base
            try:
                off = int(self.client.get('pay_start_offset_days') or 0)
            except Exception:
                off = 0
            off = 1 if off >= 1 else 0

            # Respect the saved start-of-payment offset only.

            if start_date and off:
                try:
                    start_date = (datetime.strptime(start_date, "%Y-%m-%d").date() + timedelta(days=off)).strftime("%Y-%m-%d")
                except Exception as __spina_exc:
                    _log_suppressed_once('excpass_0651', 'suppressed exception excpass_0651', __spina_exc)
                    pass

        # Pull rows in current cycle window
        try:
            rows = self.db.get_transactions_for_client(
                name,
                start_date=start_date,
                end_date=renew_date,
                loan_type=lt
            ) or []
        except Exception:
            rows = []

        # Paid total (same summing logic as reports)
        try:
            paid_total = float(_sum_paid_per_day(rows) or 0.0)
        except Exception:
            paid_total = 0.0

        # Current principal (original principal for this cycle)
        try:
            principal = float(self.client.get('principal') or 0.0)
        except Exception:
            principal = 0.0

        # New principal (use entry if present; else current principal)
        np = self._parse_float(self.new_principal_var.get())
        if np is None:
            np = principal

        # --- 7x7: compute principal balance using daily-interest split ---
        if is_7x7 and principal > 0:
            # Build per-day effective payments: last non-zero wins; 0 doesn't overwrite; ignore ADV-only marker rows
            per = {}
            for rr in rows:
                try:
                    ds = str(rr.get('date') if isinstance(rr, dict) else rr['date'])
                except Exception:
                    try:
                        ds = str(rr[0])
                    except Exception:
                        ds = ''
                ds = (ds or '')[:10].strip()
                if not ds:
                    continue
                try:
                    pay = float(rr.get('payment', 0) if isinstance(rr, dict) else rr['payment'])
                except Exception:
                    try:
                        pay = float(rr[2] or 0.0)
                    except Exception:
                        pay = 0.0
                try:
                    desc = str(rr.get('description', '') if isinstance(rr, dict) else rr['description'])
                except Exception:
                    try:
                        desc = str(rr[3] or '')
                    except Exception:
                        desc = ''
                if abs(pay) < 1e-9:
                    dl = desc.lower()
                    if 'adv' in dl and ('[' in dl or 'range' in dl or ':' in dl):
                        continue
                if ds not in per:
                    per[ds] = pay
                else:
                    if abs(pay) > 1e-9:
                        per[ds] = pay

            pay_days = []
            for ds, pay in per.items():
                try:
                    d = datetime.strptime(ds, "%Y-%m-%d").date()
                except Exception:
                    continue
                pay_days.append((d, float(pay or 0.0)))
            pay_days.sort(key=lambda x: x[0])

            # Daily interest is STEP-based from BALANCE principal:
            #   1..1000 = 7/day, 1001..2000 = 14/day, ...
            def _x7_daily_interest_for_balance(_bal):
                try:
                    b = float(_bal or 0.0)
                except Exception:
                    b = 0.0
                if b <= 0:
                    return 0.0
                try:
                    units = int((b + 999.999999) // 1000)
                except Exception:
                    units = 0
                if units < 1:
                    units = 1
                return float(units) * 7.0
            # Start DT for gap counting
            try:
                start_dt = datetime.strptime((start_date or renew_date)[:10], "%Y-%m-%d").date()
            except Exception:
                start_dt = None

            # User-requested 7x7 renew rule:
            #   renew amount / principal paid = total payment - (daily interest * number of days)
            # where daily interest is step-based from principal:
            #   1..1000 = 7/day, 1001..2000 = 14/day, ...
            try:
                renew_dt = datetime.strptime((renew_date or '')[:10], "%Y-%m-%d").date()
            except Exception:
                renew_dt = None

            try:
                daily_interest = float(_x7_daily_interest_for_principal(principal))
            except Exception:
                daily_interest = 0.0

            days_count = 0
            if start_dt and renew_dt:
                try:
                    days_count = max(0, int((renew_dt - start_dt).days) + 1)
                except Exception:
                    days_count = 0
            if days_count <= 0:
                try:
                    days_count = max(0, len(pay_days or []))
                except Exception:
                    days_count = 0

            interest_due_total = round(daily_interest * float(days_count), 2)
            paid_interest = round(min(float(paid_total or 0.0), interest_due_total), 2)
            paid_principal = round(max(0.0, float(paid_total or 0.0) - interest_due_total), 2)
            if paid_principal > float(principal or 0.0):
                paid_principal = round(float(principal or 0.0), 2)

            remaining_principal = round(max(0.0, float(principal or 0.0) - float(paid_principal or 0.0)), 2)
            remaining_due = remaining_principal
            suggested = round(np - remaining_due, 2)
            topup = 0.0
            if suggested < 0:
                topup = round(-suggested, 2)
                suggested = 0.0

            return {
                'paid': round(paid_total, 2),
                'paid_principal': round(paid_principal, 2),
                'paid_interest': round(paid_interest, 2),
                'interest_days': int(days_count),
                'daily_interest': round(daily_interest, 2),
                'interest_due_total': round(interest_due_total, 2),
                'total_to_pay': round(principal, 2),  # for 7x7, base is principal
                'remaining_due': remaining_due,       # remaining principal
                'new_principal': round(np, 2),
                'released_cash': suggested,
                'topup_needed': topup,
                'renew_date': renew_date,
                'start_date': start_date,
                'loan_type': lt,
                'is_7x7': True,
            }

        # --- Regular: remaining due is based on total_to_pay - paid_total ---
        try:
            interest_amount = float(self.client.get('interest_amount') or 0.0)
        except Exception:
            interest_amount = 0.0
        try:
            total_to_pay = float(self.client.get('total_to_pay') or 0.0)
        except Exception:
            total_to_pay = 0.0

        computed_total = round(principal + interest_amount, 2)
        if total_to_pay <= 0 or (interest_amount > 0 and abs(total_to_pay - principal) < 0.01):
            total_to_pay = computed_total

        remaining_due = max(0.0, round(total_to_pay - paid_total, 2))

        suggested = round(np - remaining_due, 2)
        topup = 0.0
        if suggested < 0:
            topup = round(-suggested, 2)
            suggested = 0.0

        return {
            'paid': round(paid_total, 2),
            'total_to_pay': round(total_to_pay, 2),
            'remaining_due': remaining_due,
            'new_principal': round(np, 2),
            'released_cash': suggested,
            'topup_needed': topup,
            'renew_date': renew_date,
            'start_date': start_date,
            'loan_type': lt,
            'is_7x7': False,
        }

    def _set_manual_rc(self, *_):
        self._auto_rc = False
        try:
            self.auto_hint_lbl.config(text="Released Cash: manual (click Auto to recompute)")
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0652', 'suppressed exception excpass_0652', __spina_exc)
            pass

    def _set_auto_rc(self):
        self._auto_rc = True
        try:
            self.auto_hint_lbl.config(text="Released Cash: auto")
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0653', 'suppressed exception excpass_0653', __spina_exc)
            pass
        self._recompute()

    def _recompute(self, *_):
        st = self._compute_stats()
        self._last_stats = st
        if not st:
            try:
                self.stats_lbl.config(text="")
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_0654', 'suppressed exception excpass_0654', __spina_exc)
                pass
            return

        # Sync Released Cash only in auto mode
        if self._auto_rc:
            try:
                self.released_cash_var.set(f"{st['released_cash']:.2f}")
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_0655', 'suppressed exception excpass_0655', __spina_exc)
                pass

        # Show computation summary
        try:
            msg = ""
            if st.get('is_7x7'):
                msg = f"Paid: {st['paid']:.2f} (Pr: {st.get('paid_principal', 0.0):.2f}, Int: {st.get('paid_interest', 0.0):.2f})   Daily Int: {st.get('daily_interest', 0.0):.2f} x {int(st.get('interest_days', 0) or 0)} day(s) = {st.get('interest_due_total', 0.0):.2f}   Remaining Principal: {st['remaining_due']:.2f}   Suggested Release: {st['released_cash']:.2f}"
            else:
                msg = f"Paid: {st['paid']:.2f}   Remaining: {st['remaining_due']:.2f}   Suggested Release: {st['released_cash']:.2f}"
            if st.get('topup_needed', 0.0) > 0:
                msg += f"   (Top-up needed: {st['topup_needed']:.2f})"
            self.stats_lbl.config(text=msg)
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0656', 'suppressed exception excpass_0656', __spina_exc)
            pass

    def body(self, master):
        frm = ttk.Frame(master)
        frm.pack(fill='both', expand=True, padx=12, pady=12)
        frm.columnconfigure(1, weight=1)

        def _row(r, label, widget):
            ttk.Label(frm, text=label).grid(row=r, column=0, sticky='w', pady=4, padx=(0, 10))
            widget.grid(row=r, column=1, sticky='ew', pady=4)
            return r + 1

        name = (self.client.get('name') or '')
        try:
            p0 = float(self.client.get('principal') or 0)
        except Exception:
            p0 = 0.0
        try:
            r0 = float(self.client.get('interest_rate') or 0.20)
        except Exception:
            r0 = 0.20

        self.date_var = tk.StringVar(value=date.today().strftime("%Y-%m-%d"))
        self.released_cash_var = tk.StringVar(value="")
        self.new_principal_var = tk.StringVar(value=f"{p0:g}")
        self.rate_var = tk.StringVar(value=str((r0 * 100.0) if r0 <= 1 else r0))
        self.note_var = tk.StringVar(value="")

        r = 0
        r = _row(r, "Client", ttk.Label(frm, text=name, font=('Segoe UI', 10, 'bold')))

        # Renew date
        r = _row(r, "Renew Date (YYYY-MM-DD)", ttk.Entry(frm, textvariable=self.date_var, width=18))

        # Start of Payment for the NEW cycle (after renew)
        # Checked = Next day, Unchecked = Same day as release
        try:
            _renew_off0 = int((self.client.get('pay_start_offset_days') if isinstance(self.client, dict) else 0) or 0)
        except Exception:
            _renew_off0 = 0
        self.pay_next_day_var = tk.BooleanVar(value=True if _renew_off0 >= 1 else False)
        r = _row(r, "Start of Payment", ttk.Checkbutton(frm, text="Next day (optional; uncheck = same day)", variable=self.pay_next_day_var))

        # Released Cash + Auto button
        rc_frame = ttk.Frame(frm)
        rc_frame.columnconfigure(0, weight=1)
        self.rc_entry = ttk.Entry(rc_frame, textvariable=self.released_cash_var, width=18)
        self.rc_entry.grid(row=0, column=0, sticky='ew')
        ttk.Button(rc_frame, text="Auto", width=6, command=self._set_auto_rc).grid(row=0, column=1, padx=(6, 0))
        r = _row(r, "Released Cash (PHP)", rc_frame)

        # New principal
        r = _row(r, "New Principal", ttk.Entry(frm, textvariable=self.new_principal_var, width=18))

        # Interest rate
        rate_entry = ttk.Entry(frm, textvariable=self.rate_var, width=18)
        r = _row(r, "Interest Rate (%)", rate_entry)
        if (self.loan_type or '').strip().lower() != 'regular':
            try:
                rate_entry.state(['disabled'])
            except Exception:
                rate_entry.configure(state='disabled')

        # Computation summary
        self.stats_lbl = ttk.Label(frm, text="", justify='left')
        self.stats_lbl.grid(row=r, column=0, columnspan=2, sticky='w', pady=(2, 2))
        r += 1

        self.auto_hint_lbl = ttk.Label(frm, text="Released Cash: auto")
        self.auto_hint_lbl.grid(row=r, column=0, columnspan=2, sticky='w', pady=(0, 8))
        r += 1

        ttk.Label(frm, text="Note (optional)").grid(row=r, column=0, sticky='nw', pady=4, padx=(0, 10))
        self.note_txt = tk.Text(frm, height=3, width=34)
        self.note_txt.grid(row=r, column=1, sticky='ew', pady=4)

        # Manual override detection
        try:
            self.rc_entry.bind("<KeyRelease>", self._set_manual_rc)
        except Exception as e:
            _log_ignored("ui.bind failed", e, key="ui.bind_failed")

        # Recompute on changes
        try:
            self.new_principal_var.trace_add("write", self._recompute)
        except Exception as e:
            _log_ignored("ui.trace_add failed", e, key="ui.trace_add_failed")
        try:
            self.date_var.trace_add("write", self._recompute)
        except Exception as e:
            _log_ignored("ui.trace_add failed", e, key="ui.trace_add_failed")

        # Initial compute
        self._recompute()
        return frm

    def validate(self):
        # Date
        d = (self.date_var.get() or "").strip()
        if d:
            try:
                datetime.strptime(d[:10], "%Y-%m-%d")
            except Exception:
                messagebox.showerror("Renew", "Invalid date. Use YYYY-MM-DD.")
                return False

        # Released cash (optional but if provided must be numeric)
        rc = (self.released_cash_var.get() or "").strip()
        if rc:
            try:
                float(rc.replace(",", ""))
            except Exception:
                messagebox.showerror("Renew", "Released Cash must be a number.")
                return False

        # New principal (optional but if provided must be numeric)
        np = (self.new_principal_var.get() or "").strip()
        if np:
            try:
                float(np.replace(",", ""))
            except Exception:
                messagebox.showerror("Renew", "New Principal must be a number.")
                return False

        # Interest rate for Regular
        if (self.loan_type or '').strip().lower() == 'regular':
            rv = (self.rate_var.get() or "").strip()
            if rv:
                try:
                    float(rv.replace(",", ""))
                except Exception:
                    messagebox.showerror("Renew", "Interest Rate must be a number.")
                    return False

        return True

    def apply(self):
        note = ""
        try:
            note = self.note_txt.get("1.0", "end").strip()
        except Exception:
            note = (self.note_var.get() or "").strip()

        released_cash = self._parse_float(self.released_cash_var.get())
        new_principal = self._parse_float(self.new_principal_var.get())

        # If user left Released Cash blank, compute it automatically
        if released_cash is None:
            st = self._compute_stats()
            if st:
                released_cash = st.get('released_cash', 0.0)

        ir = None
        if (self.loan_type or '').strip().lower() == 'regular':
            ir = self._parse_float(self.rate_var.get())

        self.result = {
            "renew_date": (self.date_var.get() or "").strip()[:10],
            "released_cash": released_cash,
            "new_principal": new_principal,
            "interest_rate": ir,
            "note": note,
            "pay_start_offset_days": (1 if bool(getattr(self, "pay_next_day_var", tk.BooleanVar(value=True)).get()) else 0),
        }

def _app_renew_client_selected(self):
    """Renew (reloan) the selected client and update the client row + report stats."""
    try:
        sel = self.clients_tree.selection()
    except Exception:
        sel = ()
    if not sel:
        messagebox.showwarning('Select', 'Please select one client to renew.')
        return

    iid = sel[0]
    vals = self.clients_tree.item(iid, 'values') or ()
    if not vals:
        messagebox.showwarning('Select', 'Please select one client to renew.')
        return

    name = vals[0]
    lt = self._mode_filter()
    # try to read the real loan type from row tags (if present)
    try:
        tags = self.clients_tree.item(iid, 'tags') or ()
        for t in tags:
            if str(t).startswith('lt:'):
                lt = str(t).split(':', 1)[1]
                break
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_0657', 'suppressed exception excpass_0657', __spina_exc)
        pass

    info = {}
    try:
        info = self.db.get_client_info(name, loan_type=lt) or {}
    except Exception:
        info = {}
    if not info:
        messagebox.showerror('Missing', 'Client not found in database.')
        return

    dlg = RenewDialog(self.root, initial=info, loan_type=lt, db=self.db)
    if not getattr(dlg, 'result', None):
        return

    r = dlg.result
    try:
        ok = self.db.renew_client(
            name,
            released_cash=r.get('released_cash'),
            renew_date=r.get('renew_date'),
            new_principal=r.get('new_principal'),
            loan_type=lt,
            interest_rate=r.get('interest_rate'),
            pay_start_offset_days=r.get('pay_start_offset_days'),
            note=r.get('note',''),
        )
    except Exception as e:
        messagebox.showerror('Renew Error', str(e))
        return

    if ok:
        try:
            messagebox.showinfo('Renewed', 'Client renewed successfully.')
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0658', 'suppressed exception excpass_0658', __spina_exc)
            pass
        try:
            self.refresh_clients()
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0659', 'suppressed exception excpass_0659', __spina_exc)
            pass
        try:
            self.refresh_reports()
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0660', 'suppressed exception excpass_0660', __spina_exc)
            pass
        try:
            self.refresh_data_grid()
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0661', 'suppressed exception excpass_0661', __spina_exc)
            pass
    else:
        reason = str(getattr(self.db, '_last_renew_error', '') or '').strip()
        messagebox.showerror('Error', ('Failed to renew client.\n\nReason: ' + reason) if reason else 'Failed to renew client.')

def _spina_pg__reset_id_sequence(cur, table_name):
    """Move a PostgreSQL BIGSERIAL/SERIAL sequence after the current MAX(id)."""
    try:
        t = str(table_name or '').strip()
        if t not in {'clients', 'transactions', 'transaction_history', 'renewals', 'client_history', 'databank_day_close', 'databank_day_close_history', 'databank_day_collector_close'}:
            return
        cur.execute("SELECT pg_get_serial_sequence(%s, 'id')", (f'public.{t}',))
        row = cur.fetchone()
        seq = row[0] if row else None
        if not seq:
            return
        cur.execute(f"SELECT COALESCE(MAX(id), 0) FROM public.{t}")
        row = cur.fetchone()
        max_id = int(row[0] or 0) if row else 0
        if max_id > 0:
            cur.execute("SELECT setval(%s::regclass, %s, true)", (seq, max_id))
        else:
            cur.execute("SELECT setval(%s::regclass, 1, false)", (seq,))
    except Exception:
        # Never block the main renew path only because sequence repair failed.
        pass

def _spina_pg__table_has_column(cur, table_name, column_name):
    try:
        cur.execute(
            """
            SELECT 1
              FROM information_schema.columns
             WHERE table_schema='public'
               AND table_name=%s
               AND column_name=%s
             LIMIT 1
            """,
            (str(table_name or ''), str(column_name or ''))
        )
        return cur.fetchone() is not None
    except Exception:
        return False

def _spina_pg_renew_client_direct(self, name, released_cash, renew_date=None, new_principal=None, loan_type=None, interest_rate=None, note='', pay_start_offset_days=None):
    """PostgreSQL-safe renew/reloan implementation for the TEST build."""
    if not globals().get('SPINA_POSTGRESQL_TEST_MODE', False):
        if _SPINA_ORIG_LOANDB_RENEW_CLIENT:
            return _SPINA_ORIG_LOANDB_RENEW_CLIENT(self, name, released_cash, renew_date, new_principal, loan_type, interest_rate, note, pay_start_offset_days)
        return False

    pg = getattr(getattr(self, 'conn', None), '_pg', None)
    if pg is None:
        if _SPINA_ORIG_LOANDB_RENEW_CLIENT:
            return _SPINA_ORIG_LOANDB_RENEW_CLIENT(self, name, released_cash, renew_date, new_principal, loan_type, interest_rate, note, pay_start_offset_days)
        return False

    try:
        self._last_renew_error = ''
    except Exception:
        pass

    try:
        lt = self._effective_lt(loan_type)
    except Exception:
        lt = '7x7' if str(loan_type or '').lower().replace('×', 'x').replace(' ', '') == '7x7' else 'Regular'

    try:
        info = self.get_client_info(name, loan_type=lt) or {}
    except Exception:
        info = {}
    if not info:
        try:
            self._last_renew_error = 'Client not found in database for renew.'
        except Exception:
            pass
        return False

    uid = str((info.get('client_uid') or '')).strip()
    old_row = dict(info)

    # Renew date
    if not renew_date:
        rd = date.today().strftime('%Y-%m-%d')
    else:
        try:
            rd = datetime.strptime(str(renew_date)[:10], '%Y-%m-%d').strftime('%Y-%m-%d')
        except Exception:
            rd = date.today().strftime('%Y-%m-%d')

    # Start-of-payment offset for the NEW cycle.
    if pay_start_offset_days is None:
        try:
            psod = int(info.get('pay_start_offset_days') or 0)
        except Exception:
            psod = 0
    else:
        try:
            psod = int(pay_start_offset_days or 0)
        except Exception:
            psod = 0
    psod = 1 if psod >= 1 else 0
    try:
        payment_start = (datetime.strptime(rd, '%Y-%m-%d').date() + timedelta(days=psod)).strftime('%Y-%m-%d')
    except Exception:
        payment_start = rd

    # Cash and principal.
    try:
        rc = float(str(released_cash or 0).replace(',', ''))
    except Exception:
        rc = 0.0
    if new_principal is None or str(new_principal).strip() == '':
        new_principal = rc
    try:
        p = float(str(new_principal or 0).replace(',', ''))
    except Exception:
        p = 0.0

    # Interest.
    try:
        r = float(str(interest_rate).replace(',', '')) if interest_rate is not None else float(info.get('interest_rate') or 0.20)
        if r > 1.0:
            r = r / 100.0
    except Exception:
        r = 0.20
    if str(lt).lower().replace('×', 'x').replace(' ', '') == '7x7':
        r = 0.0

    intr = round(float(p) * float(r), 2)
    total = round(float(p) + float(intr), 2)
    due_days = 49 if str(lt).lower().replace('×', 'x').replace(' ', '') == '7x7' else 120
    try:
        due = (datetime.strptime(rd, '%Y-%m-%d').date() + timedelta(days=due_days)).strftime('%Y-%m-%d')
    except Exception:
        due = rd

    try:
        with pg.cursor() as cur:
            # Make sure the columns used by the newer app exist in the PostgreSQL test database.
            try:
                cur.execute("ALTER TABLE public.clients ADD COLUMN IF NOT EXISTS payment_start_date TEXT")
            except Exception:
                try:
                    pg.rollback()
                except Exception:
                    pass
                cur = pg.cursor()

            _spina_pg__reset_id_sequence(cur, 'renewals')
            _spina_pg__reset_id_sequence(cur, 'client_history')

            has_payment_start = _spina_pg__table_has_column(cur, 'clients', 'payment_start_date')

            if uid:
                if has_payment_start:
                    cur.execute(
                        """
                        UPDATE public.clients
                           SET principal=%s,
                               interest_rate=%s,
                               interest_amount=%s,
                               total_to_pay=%s,
                               date_released=%s,
                               due_date=%s,
                               new_until=NULL,
                               last_released_cash=%s,
                               renew_count=COALESCE(renew_count,0)+1,
                               pay_start_offset_days=%s,
                               payment_start_date=%s
                         WHERE client_uid=%s
                        """,
                        (p, r, intr, total, rd, due, rc, psod, payment_start, uid)
                    )
                else:
                    cur.execute(
                        """
                        UPDATE public.clients
                           SET principal=%s,
                               interest_rate=%s,
                               interest_amount=%s,
                               total_to_pay=%s,
                               date_released=%s,
                               due_date=%s,
                               new_until=NULL,
                               last_released_cash=%s,
                               renew_count=COALESCE(renew_count,0)+1,
                               pay_start_offset_days=%s
                         WHERE client_uid=%s
                        """,
                        (p, r, intr, total, rd, due, rc, psod, uid)
                    )
            else:
                if has_payment_start:
                    cur.execute(
                        """
                        UPDATE public.clients
                           SET principal=%s,
                               interest_rate=%s,
                               interest_amount=%s,
                               total_to_pay=%s,
                               date_released=%s,
                               due_date=%s,
                               new_until=NULL,
                               last_released_cash=%s,
                               renew_count=COALESCE(renew_count,0)+1,
                               pay_start_offset_days=%s,
                               payment_start_date=%s
                         WHERE TRIM(name)=TRIM(%s) AND loan_type=%s
                        """,
                        (p, r, intr, total, rd, due, rc, psod, payment_start, name, lt)
                    )
                else:
                    cur.execute(
                        """
                        UPDATE public.clients
                           SET principal=%s,
                               interest_rate=%s,
                               interest_amount=%s,
                               total_to_pay=%s,
                               date_released=%s,
                               due_date=%s,
                               new_until=NULL,
                               last_released_cash=%s,
                               renew_count=COALESCE(renew_count,0)+1,
                               pay_start_offset_days=%s
                         WHERE TRIM(name)=TRIM(%s) AND loan_type=%s
                        """,
                        (p, r, intr, total, rd, due, rc, psod, name, lt)
                    )

            updated = int(cur.rowcount or 0)
            if updated <= 0:
                raise RuntimeError(f'No client row was updated. Name={name!r}, loan_type={lt!r}, client_uid={uid!r}')

            if uid:
                cur.execute(
                    """
                    INSERT INTO public.renewals
                        (client_uid, loan_type, renew_date, released_cash, principal_after, interest_rate, note, created_at)
                    VALUES
                        (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP::text)
                    """,
                    (uid, lt, rd, rc, p, r, str(note or '').strip())
                )

        pg.commit()
    except Exception as e:
        try:
            pg.rollback()
        except Exception:
            pass
        msg = str(e)
        try:
            self._last_renew_error = msg
        except Exception:
            pass
        try:
            _log_exc('postgres direct renew_client', e)
        except Exception:
            pass
        return False

    try:
        new_row = self.get_client_info(name, loan_type=lt) or {}
        self._log_client_history((new_row.get('client_uid') or uid), 'RENEW', old_row=old_row, new_row=new_row, source='clients:renew:postgres', note=str(note or '').strip())
    except Exception:
        pass

    return True

