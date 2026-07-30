"""Data Bank audit controller helpers extracted in SPINA Wave 82."""
from __future__ import annotations

import calendar
import json
import os
import sqlite3
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Mapping

_DEPENDENCIES: dict[str, Any] = {}
_PROTECTED = {"__name__", "__file__", "__package__", "__builtins__", "_DEPENDENCIES", "_PROTECTED", "configure_data_bank_audit_dependencies"}


def configure_data_bank_audit_dependencies(namespace: Mapping[str, Any]) -> None:
    _DEPENDENCIES.clear()
    _DEPENDENCIES.update(namespace)
    for name, value in namespace.items():
        if name not in _PROTECTED:
            globals()[name] = value

def _audit_money_text(self, value):
        try:
            return fmt_currency(value)
        except Exception:
            try:
                return f"PHP {float(value or 0):,.2f}"
            except Exception:
                return 'PHP 0.00'

def _audit_parse_date_filters(self):
        from datetime import datetime as _dt
        from tkinter import messagebox
        start_s = ''
        end_s = ''
        try:
            start_s = (self.audit_from_var.get() or '').strip()
        except Exception:
            start_s = ''
        try:
            end_s = (self.audit_to_var.get() or '').strip()
        except Exception:
            end_s = ''
        if start_s:
            try:
                start_s = _dt.strptime(start_s[:10], '%Y-%m-%d').strftime('%Y-%m-%d')
            except Exception:
                messagebox.showerror('Audit', 'From date must use YYYY-MM-DD.')
                return None
        if end_s:
            try:
                end_s = _dt.strptime(end_s[:10], '%Y-%m-%d').strftime('%Y-%m-%d')
            except Exception:
                messagebox.showerror('Audit', 'To date must use YYYY-MM-DD.')
                return None
        if start_s and end_s and start_s > end_s:
            messagebox.showerror('Audit', 'From date cannot be after To date.')
            return None
        return (start_s, end_s)

def _audit_set_today(self):
        from datetime import date as _date
        ds = _date.today().strftime('%Y-%m-%d')
        try:
            self.audit_from_var.set(ds)
            self.audit_to_var.set(ds)
        except Exception:
            pass
        self.refresh_audit_tab()

def _audit_set_last7(self):
        from datetime import date as _date, timedelta as _td
        end_s = _date.today().strftime('%Y-%m-%d')
        start_s = (_date.today() - _td(days=6)).strftime('%Y-%m-%d')
        try:
            self.audit_from_var.set(start_s)
            self.audit_to_var.set(end_s)
        except Exception:
            pass
        self.refresh_audit_tab()

def _audit_set_all(self):
        try:
            self.audit_from_var.set('')
            self.audit_to_var.set('')
        except Exception:
            pass
        self.refresh_audit_tab()

def _audit_tree_factory(self, parent, columns, headings, widths):
        import tkinter as tk
        from tkinter import ttk
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        tree = ttk.Treeview(parent, columns=columns, show='headings', height=14)
        vsb = ttk.Scrollbar(parent, orient='vertical', command=tree.yview)
        hsb = ttk.Scrollbar(parent, orient='horizontal', command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        for col, head, width in zip(columns, headings, widths):
            tree.heading(col, text=head)
            anchor = 'e' if col in ('principal', 'payment_amount', 'released_cash', 'old_principal', 'new_principal') else 'w'
            tree.column(col, width=width, stretch=True, anchor=anchor)
        return tree

def _audit_set_detail_text(self, text):
        try:
            self.audit_detail_text.configure(state='normal')
            self.audit_detail_text.delete('1.0', 'end')
            self.audit_detail_text.insert('1.0', text or '')
            self.audit_detail_text.configure(state='disabled')
        except Exception:
            pass

def _audit_show_selected(self, bucket):
        row = None
        try:
            if bucket == 'renew':
                sel = self.audit_renew_tree.selection()
                if sel:
                    row = self._audit_renew_rows_map.get(sel[0])
            else:
                sel = self.audit_new_tree.selection()
                if sel:
                    row = self._audit_new_rows_map.get(sel[0])
        except Exception:
            row = None

        if not row:
            self._audit_set_detail_text('')
            return

        lines = []
        if bucket == 'renew':
            lines.extend([
                'Audit Type: Renewal',
                f"Logged At: {row.get('ts') or ''}",
                f"Client: {row.get('name') or ''}",
                f"Loan Type: {row.get('loan_type') or ''}",
                f"Renew Date: {row.get('renew_date') or ''}",
                f"Old Start Date: {row.get('old_start_date') or ''}",
                f"New Start Date: {row.get('new_start_date') or ''}",
                f"Released Cash: {self._audit_money_text(row.get('released_cash'))}",
                f"Old Principal: {self._audit_money_text(row.get('old_principal'))}",
                f"New Principal: {self._audit_money_text(row.get('new_principal'))}",
                f"Renew Count: {row.get('renew_count') or 0}",
                f"Area: {row.get('area') or ''}",
                f"Payment Term: {row.get('payment_term') or ''}",
                f"Payment Amount: {self._audit_money_text(row.get('payment_amount'))}",
                f"Source: {row.get('source') or ''}",
                f"Note: {row.get('note') or ''}",
                f"Client UID: {row.get('client_uid') or ''}",
            ])
        else:
            lines.extend([
                'Audit Type: New Loan',
                f"Logged At: {row.get('ts') or ''}",
                f"Client: {row.get('name') or ''}",
                f"Loan Type: {row.get('loan_type') or ''}",
                f"Release Date: {row.get('date_released') or ''}",
                f"Payment Start Date: {row.get('payment_start_date') or ''}",
                f"Principal: {self._audit_money_text(row.get('principal'))}",
                f"Area: {row.get('area') or ''}",
                f"Payment Term: {row.get('payment_term') or ''}",
                f"Payment Amount: {self._audit_money_text(row.get('payment_amount'))}",
                f"Source: {row.get('source') or ''}",
                f"Note: {row.get('note') or ''}",
                f"Client UID: {row.get('client_uid') or ''}",
            ])
        self._audit_set_detail_text('\n'.join(lines))
