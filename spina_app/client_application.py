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

_CLIENT_APPLICATION_DEPENDENCIES: dict[str, Any] = {}


def configure_client_application_dependencies(namespace: Mapping[str, Any]) -> None:
    _CLIENT_APPLICATION_DEPENDENCIES.clear()
    _CLIENT_APPLICATION_DEPENDENCIES.update(namespace)
    protected = {"__name__", "__file__", "__package__", "__builtins__", "_CLIENT_APPLICATION_DEPENDENCIES", "configure_client_application_dependencies"}
    for name, value in namespace.items():
        if name not in protected:
            globals()[name] = value


def _spina_v23_client_loan_summary(app, info):
    out = {
        "paid": 0.0,
        "balance": 0.0,
        "progress": 0.0,
        "renewals": 0,
        "last_cash": 0.0,
        "interest_amount": 0.0,
        "total_to_pay": 0.0,
    }
    try:
        total = float(info.get("total_to_pay") or 0)
        principal = float(info.get("principal") or 0)
        rate = float(info.get("interest_rate") or 0)
        if total <= 0:
            if str(info.get("loan_type") or "").lower().replace("×", "x").replace(" ", "") == "7x7":
                total = principal
            else:
                if rate > 1:
                    rate = rate / 100.0
                total = principal + (principal * rate)
        out["total_to_pay"] = total
        out["interest_amount"] = max(0.0, total - principal)
    except Exception:
        pass

    try:
        name = info.get("name") or ""
        lt = info.get("loan_type") or None
        rows = app.db.get_transactions_for_client(name, loan_type=lt) or []
        paid = 0.0
        for r in rows:
            try:
                paid += float(r.get("payment") if hasattr(r, "get") else r["payment"] or 0)
            except Exception:
                pass
        out["paid"] = paid
    except Exception:
        pass

    try:
        out["balance"] = max(0.0, float(out.get("total_to_pay") or 0) - float(out.get("paid") or 0))
        total = float(out.get("total_to_pay") or 0)
        out["progress"] = (float(out.get("paid") or 0) / total * 100.0) if total > 0 else 0.0
    except Exception:
        pass

    try:
        uid = info.get("client_uid") or ""
        if uid:
            stats = app.db.get_renewal_stats(uid, loan_type=info.get("loan_type")) or {}
            out["renewals"] = int(stats.get("count") or stats.get("renew_count") or 0)
            out["last_cash"] = float(stats.get("last_cash_released") or stats.get("last_released_cash") or 0)
    except Exception:
        pass

    return out

def _spina_v23_client_form(self, title, initial=None, is_edit=False):
    init = dict(initial or {})
    c = _spina_v23_clients_colors(self)

    def norm_lt(v):
        try:
            return _app__norm_lt_value(self, v)
        except Exception:
            s = str(v or "").strip().lower().replace(" ", "").replace("×", "x")
            return "7x7" if s == "7x7" else "Regular"

    lt0 = norm_lt(init.get("loan_type") or self._mode_filter())
    result = {"ok": False, "data": None}

    win = tk.Toplevel(self.root)
    win.title(title)
    win.configure(bg=c["bg"])
    win.geometry("1020x780")
    win.minsize(900, 680)
    win.resizable(True, True)
    try:
        win.transient(self.root)
        win.grab_set()
    except Exception:
        pass

    # Variables
    name_var = tk.StringVar(value=str(init.get("name") or "").strip())
    contact_var = tk.StringVar(value=str(init.get("contact_number") or "").strip())
    loan_type_var = tk.StringVar(value=lt0)
    area_var = tk.StringVar(value=str(init.get("area") or "").strip())
    principal_var = tk.StringVar(value=str(init.get("principal") or 0).strip())
    ir0 = init.get("interest_rate")
    if ir0 is None:
        ir0 = 0.20
    interest_var = tk.StringVar(value=str(ir0))
    released_var = tk.StringVar(value=str(init.get("date_released") or date.today().strftime("%Y-%m-%d")).strip())
    new_until_var = tk.StringVar(value=str(init.get("new_until") or "").strip())
    is_new_var = tk.IntVar(value=1 if str(init.get("new_until") or "").strip() else 0)

    payterm_var = tk.StringVar(value=str(init.get("payment_term") or "Daily").strip() or "Daily")
    payamt_var = tk.StringVar(value=str(init.get("payment_amount") or "").strip())
    try:
        _pm_base0, _pm_other0 = _spina__split_payment_mode(init.get("payment_mode") or "Cash")
    except Exception:
        _pm_base0, _pm_other0 = "Cash", ""
    paymode_var = tk.StringVar(value=_pm_base0)
    paymode_other_var = tk.StringVar(value=_pm_other0)
    due_weekday_var = tk.StringVar(value=str(init.get("due_weekday") or "").strip())
    semi_due_day1_var = tk.StringVar(value="" if init.get("semi_due_day1") in (None, "") else str(init.get("semi_due_day1")))
    semi_due_day2_var = tk.StringVar(value="" if init.get("semi_due_day2") in (None, "") else str(init.get("semi_due_day2")))
    monthly_due_day_var = tk.StringVar(value="" if init.get("monthly_due_day") in (None, "") else str(init.get("monthly_due_day")))
    flex_due_rule_var = tk.StringVar(value=str(init.get("flex_due_rule") or "").strip())
    try:
        psod = int(init.get("pay_start_offset_days") or 0)
    except Exception:
        psod = 0
    psod_var = tk.IntVar(value=1 if psod >= 1 else 0)

    picture_source_var = tk.StringVar(value="")
    picture_clear_var = tk.BooleanVar(value=False)
    current_picture_var = tk.StringVar(value=str(init.get("client_picture") or "").strip())

    # Header
    header = tk.Frame(win, bg=c["bg"])
    header.pack(fill="x", padx=18, pady=(16, 10))
    tk.Label(header, text=title, bg=c["bg"], fg=c["fg"], font=("Segoe UI", 20, "bold"), anchor="w").pack(side="left")
    tk.Label(header, text="Application Form", bg=c["blue"], fg="#ffffff", font=("Segoe UI", 9, "bold"), padx=10, pady=5).pack(side="left", padx=12)

    # Scrollable body
    body_wrap = tk.Frame(win, bg=c["bg"])
    body_wrap.pack(fill="both", expand=True, padx=18, pady=(0, 12))
    canvas = tk.Canvas(body_wrap, bg=c["bg"], highlightthickness=0, bd=0)
    scroll = ttk.Scrollbar(body_wrap, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=scroll.set)
    canvas.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")
    content = tk.Frame(canvas, bg=c["bg"])
    content_id = canvas.create_window((0, 0), window=content, anchor="nw")

    def _on_content_config(_e=None):
        try:
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfigure(content_id, width=canvas.winfo_width())
        except Exception:
            pass
    content.bind("<Configure>", _on_content_config)
    canvas.bind("<Configure>", _on_content_config)

    # Layout columns
    content.columnconfigure(0, weight=0)
    content.columnconfigure(1, weight=1)

    # Picture column
    left = tk.Frame(content, bg=c["panel"], width=290, highlightbackground=c["border"], highlightthickness=1, bd=0)
    left.grid(row=0, column=0, sticky="ns", padx=(0, 12), pady=(0, 12))
    left.grid_propagate(False)
    tk.Label(left, text="Client Picture", bg=c["panel"], fg=c["fg"], font=("Segoe UI", 13, "bold"), anchor="w").pack(fill="x", padx=14, pady=(14, 8))

    pic_box = tk.Frame(left, bg=c["card2"], highlightbackground=c["border"], highlightthickness=1, bd=0)
    pic_box.pack(fill="x", padx=14, pady=(0, 10))
    pic_preview = tk.Label(pic_box, text="No picture", bg=c["card2"], fg=c["muted"], width=26, height=12, anchor="center", justify="center")
    pic_preview.pack(fill="x", padx=10, pady=10)
    pic_path_label = tk.Label(left, text="", bg=c["panel"], fg=c["muted"], font=("Segoe UI", 8), wraplength=250, justify="left")
    pic_path_label.pack(fill="x", padx=14, pady=(0, 10))

    _form_pic_img = {"img": None}

    def _load_pic_preview(path_or_token):
        try:
            p = str(path_or_token or "").strip()
            if not p:
                pic_preview.configure(image="", text="No picture")
                _form_pic_img["img"] = None
                return
            abs_path = _spina__resolve_app_path(p) if "_spina__resolve_app_path" in globals() else p
            if not abs_path or not os.path.exists(abs_path):
                pic_preview.configure(image="", text="Picture not found")
                _form_pic_img["img"] = None
                return
            try:
                from PIL import Image, ImageTk
                with Image.open(abs_path) as im:
                    img = im.copy()
                img.thumbnail((230, 230), Image.LANCZOS)
                _form_pic_img["img"] = ImageTk.PhotoImage(img)
                pic_preview.configure(image=_form_pic_img["img"], text="")
            except Exception:
                try:
                    _form_pic_img["img"] = tk.PhotoImage(file=abs_path)
                    pic_preview.configure(image=_form_pic_img["img"], text="")
                except Exception:
                    pic_preview.configure(image="", text="Preview failed")
                    _form_pic_img["img"] = None
        except Exception:
            pass

    def _choose_picture():
        fp = filedialog.askopenfilename(
            parent=win,
            title="Select Client Picture",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.gif *.bmp *.webp"), ("All files", "*.*")],
        )
        if not fp:
            return
        picture_source_var.set(fp)
        picture_clear_var.set(False)
        pic_path_label.configure(text=os.path.basename(fp))
        _load_pic_preview(fp)

    def _clear_picture():
        picture_source_var.set("")
        picture_clear_var.set(True)
        current_picture_var.set("")
        pic_path_label.configure(text="Picture will be cleared when saved.")
        pic_preview.configure(image="", text="Picture will be cleared")
        _form_pic_img["img"] = None

    _spina_v23_button(left, "Choose Picture", command=_choose_picture, kind="primary").pack(fill="x", padx=14, pady=(0, 8))
    _spina_v23_button(left, "Clear Picture", command=_clear_picture, kind="soft").pack(fill="x", padx=14, pady=(0, 12))

    if current_picture_var.get():
        pic_path_label.configure(text="Saved picture")
        _load_pic_preview(current_picture_var.get())

    # Loan info quick summary in form
    summary = _spina_v23_client_loan_summary(self, init) if is_edit else {}
    info_card = tk.Frame(left, bg=c["card"], highlightbackground=c["border"], highlightthickness=1, bd=0)
    info_card.pack(fill="x", padx=14, pady=(8, 12))
    tk.Label(info_card, text="Loan Snapshot", bg=c["card"], fg=c["fg"], font=("Segoe UI", 11, "bold"), anchor="w").pack(fill="x", padx=12, pady=(10, 4))
    snapshot_text = tk.StringVar(value="")
    tk.Label(info_card, textvariable=snapshot_text, bg=c["card"], fg=c["muted"], font=("Segoe UI", 9), justify="left", anchor="w", wraplength=240).pack(fill="x", padx=12, pady=(0, 10))

    # Right form area
    right = tk.Frame(content, bg=c["bg"])
    right.grid(row=0, column=1, sticky="nsew", pady=(0, 12))
    right.columnconfigure(0, weight=1)

    def section(parent, title, subtitle=""):
        f = tk.Frame(parent, bg=c["panel"], highlightbackground=c["border"], highlightthickness=1, bd=0)
        f.pack(fill="x", pady=(0, 12))
        tk.Label(f, text=title, bg=c["panel"], fg=c["fg"], font=("Segoe UI", 13, "bold"), anchor="w").pack(fill="x", padx=14, pady=(12, 0))
        if subtitle:
            tk.Label(f, text=subtitle, bg=c["panel"], fg=c["muted"], font=("Segoe UI", 9), anchor="w").pack(fill="x", padx=14, pady=(2, 8))
        inner = tk.Frame(f, bg=c["panel"])
        inner.pack(fill="x", padx=14, pady=(6, 14))
        for i in range(3):
            inner.columnconfigure(i, weight=1)
        return inner

    sec1 = section(right, "1. Borrower Information", "Basic identity and route information.")
    _spina_v23_entry(sec1, "Full Name *", name_var, 28)[0].grid(row=0, column=0, sticky="ew", padx=(0, 10), pady=(0, 8))
    _spina_v23_entry(sec1, "Contact Number", contact_var, 20)[0].grid(row=0, column=1, sticky="ew", padx=(0, 10), pady=(0, 8))
    from spina_app.area_hierarchy_ui import build_area_selector_field
    area_box, area_cb = build_area_selector_field(
        sec1, self, win, area_var, label="Area / Route", width=24
    )
    area_box.grid(row=0, column=2, sticky="ew", pady=(0, 8))

    sec2 = section(right, "2. Loan Details", "Amounts, release date, and start-of-payment rule.")
    _spina_v23_entry(sec2, "Loan Type *", loan_type_var, 18, kind="combo", values=["Regular", "7x7"], readonly=True)[0].grid(row=0, column=0, sticky="ew", padx=(0, 10), pady=(0, 8))
    _spina_v23_entry(sec2, "Principal / Loan Amount *", principal_var, 18)[0].grid(row=0, column=1, sticky="ew", padx=(0, 10), pady=(0, 8))
    _spina_v23_entry(sec2, "Interest Rate (Regular)", interest_var, 18)[0].grid(row=0, column=2, sticky="ew", pady=(0, 8))

    date_box = tk.Frame(sec2, bg=c["panel"])
    date_box.grid(row=1, column=0, sticky="ew", padx=(0, 10), pady=(0, 8))
    tk.Label(date_box, text="Date Released *", bg=c["panel"], fg=c["muted"], font=("Segoe UI", 8, "bold"), anchor="w").pack(fill="x")
    date_line = tk.Frame(date_box, bg=c["panel"])
    date_line.pack(fill="x", pady=(3, 0))
    ttk.Entry(date_line, textvariable=released_var, width=14).pack(side="left", fill="x", expand=True)
    _spina_v23_button(date_line, "📅", command=lambda: pick_date(win, released_var, title="Select Release Date"), kind="soft", width=3).pack(side="left", padx=(6, 0))

    paystart_var = tk.StringVar(value="")
    pay_box = tk.Frame(sec2, bg=c["panel"])
    pay_box.grid(row=1, column=1, sticky="ew", padx=(0, 10), pady=(0, 8))
    tk.Label(pay_box, text="Start of Payment", bg=c["panel"], fg=c["muted"], font=("Segoe UI", 8, "bold"), anchor="w").pack(fill="x")
    pay_line = tk.Frame(pay_box, bg=c["panel"])
    pay_line.pack(fill="x", pady=(3, 0))
    ttk.Entry(pay_line, textvariable=paystart_var, width=14, state="readonly").pack(side="left", fill="x", expand=True)
    ttk.Checkbutton(pay_line, text="+1 day", variable=psod_var).pack(side="left", padx=(6, 0))

    new_box = tk.Frame(sec2, bg=c["panel"])
    new_box.grid(row=1, column=2, sticky="ew", pady=(0, 8))
    ttk.Checkbutton(new_box, text="Mark as NEW", variable=is_new_var).pack(anchor="w")
    new_line = tk.Frame(new_box, bg=c["panel"])
    new_line.pack(fill="x", pady=(3, 0))
    ttk.Entry(new_line, textvariable=new_until_var, width=14).pack(side="left", fill="x", expand=True)
    _spina_v23_button(new_line, "📅", command=lambda: pick_date(win, new_until_var, title="Select New Until Date"), kind="soft", width=3).pack(side="left", padx=(6, 0))

    sec3 = section(right, "3. Payment Plan", "How the client pays and when due indicators should appear.")
    _spina_v23_entry(sec3, "Payment Term *", payterm_var, 18, kind="combo", values=["Daily", "Weekly", "Semi", "Monthly"], readonly=True)[0].grid(row=0, column=0, sticky="ew", padx=(0, 10), pady=(0, 8))
    _spina_v23_entry(sec3, "Payment Amount *", payamt_var, 18)[0].grid(row=0, column=1, sticky="ew", padx=(0, 10), pady=(0, 8))
    _spina_v23_entry(sec3, "Mode of Payment", paymode_var, 18, kind="combo", values=["Cash", "GCASH", "ATM", "Others"], readonly=True)[0].grid(row=0, column=2, sticky="ew", pady=(0, 8))
    _spina_v23_entry(sec3, "If Others, specify", paymode_other_var, 18)[0].grid(row=1, column=2, sticky="ew", pady=(0, 8))

    weekdays = ["", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    _spina_v23_entry(sec3, "Weekly Due Day", due_weekday_var, 18, kind="combo", values=weekdays, readonly=False)[0].grid(row=1, column=0, sticky="ew", padx=(0, 10), pady=(0, 8))
    semi = tk.Frame(sec3, bg=c["panel"])
    semi.grid(row=1, column=1, sticky="ew", padx=(0, 10), pady=(0, 8))
    tk.Label(semi, text="Semi Due Days", bg=c["panel"], fg=c["muted"], font=("Segoe UI", 8, "bold"), anchor="w").pack(fill="x")
    semi_line = tk.Frame(semi, bg=c["panel"])
    semi_line.pack(fill="x", pady=(3, 0))
    ttk.Entry(semi_line, textvariable=semi_due_day1_var, width=5).pack(side="left")
    tk.Label(semi_line, text=" and ", bg=c["panel"], fg=c["muted"]).pack(side="left")
    ttk.Entry(semi_line, textvariable=semi_due_day2_var, width=5).pack(side="left")
    _spina_v23_entry(sec3, "Monthly Due Day", monthly_due_day_var, 18)[0].grid(row=2, column=0, sticky="ew", padx=(0, 10), pady=(0, 8))
    _spina_v23_entry(sec3, "Flexible Due Rule", flex_due_rule_var, 40)[0].grid(row=2, column=1, columnspan=2, sticky="ew", pady=(0, 8))

    sec4 = section(right, "4. Relevant Loan Information", "This is for checking before saving. It does not change the saved values by itself.")
    calc_vars = {k: tk.StringVar(value="—") for k in ("interest", "total", "paid", "balance", "progress", "daily_note")}
    def calc_row(r, label, key, col):
        box = tk.Frame(sec4, bg=c["card2"], highlightbackground=c["border"], highlightthickness=1)
        box.grid(row=r, column=col, sticky="ew", padx=(0 if col == 0 else 8, 0), pady=(0, 8))
        tk.Label(box, text=label, bg=c["card2"], fg=c["muted"], font=("Segoe UI", 8, "bold"), anchor="w").pack(fill="x", padx=10, pady=(8, 0))
        tk.Label(box, textvariable=calc_vars[key], bg=c["card2"], fg=c["fg"], font=("Segoe UI", 11, "bold"), anchor="w").pack(fill="x", padx=10, pady=(2, 8))
    calc_row(0, "Interest Amount", "interest", 0)
    calc_row(0, "Total To Pay", "total", 1)
    calc_row(0, "Current Paid", "paid", 2)
    calc_row(1, "Current Balance", "balance", 0)
    calc_row(1, "Completion", "progress", 1)
    calc_row(1, "7x7 Reminder", "daily_note", 2)

    def _parse_float_var(var, default=0.0):
        try:
            s = str(var.get() or "").replace(",", ".").strip()
            return float(s) if s else default
        except Exception:
            return default

    def _sync_dates_and_calc(*_):
        try:
            s = (released_var.get() or "").strip()[:10]
            if s:
                d = datetime.strptime(s, "%Y-%m-%d").date()
                paystart_var.set((d + timedelta(days=(1 if psod_var.get() else 0))).strftime("%Y-%m-%d"))
            else:
                paystart_var.set("")
        except Exception:
            paystart_var.set("")

        pval = _parse_float_var(principal_var, 0.0)
        rate = _parse_float_var(interest_var, 0.20)
        if rate > 1:
            rate = rate / 100.0
        lt = norm_lt(loan_type_var.get())
        if lt == "7x7":
            interest = 0.0
            total = pval
            calc_vars["daily_note"].set("₱7 per ₱1,000 per day")
        else:
            interest = pval * rate
            total = pval + interest
            calc_vars["daily_note"].set("Regular interest applies")
        paid = float(summary.get("paid") or 0) if is_edit else 0.0
        bal = max(0.0, total - paid)
        prog = (paid / total * 100.0) if total > 0 else 0.0
        calc_vars["interest"].set(_spina_v23_money(interest))
        calc_vars["total"].set(_spina_v23_money(total))
        calc_vars["paid"].set(_spina_v23_money(paid))
        calc_vars["balance"].set(_spina_v23_money(bal))
        calc_vars["progress"].set(_spina_v23_percent(prog))
        snapshot_text.set(
            f"Type: {lt}\n"
            f"Principal: {_spina_v23_money(pval)}\n"
            f"Paid: {_spina_v23_money(paid)}\n"
            f"Balance: {_spina_v23_money(bal)}\n"
            f"Renewals: {summary.get('renewals', 0) if is_edit else 0}"
        )

    for var in (released_var, principal_var, interest_var, loan_type_var, psod_var):
        try:
            var.trace_add("write", _sync_dates_and_calc)
        except Exception:
            pass
    _sync_dates_and_calc()

    # Footer buttons
    footer = tk.Frame(win, bg=c["bg"])
    footer.pack(fill="x", padx=18, pady=(0, 16))
    status_var = tk.StringVar(value="Required fields: Full Name, Principal, Date Released, Loan Type, Payment Term, Payment Amount.")
    tk.Label(footer, textvariable=status_var, bg=c["bg"], fg=c["muted"], font=("Segoe UI", 9), anchor="w").pack(side="left", fill="x", expand=True)

    def _validate_date(value, field):
        s = str(value or "").strip()
        if not s:
            raise ValueError(f"{field} is required.")
        datetime.strptime(s[:10], "%Y-%m-%d")
        return s[:10]

    def _norm_dom(value):
        try:
            if "_spina__norm_dom" in globals():
                return _spina__norm_dom(value)
        except Exception:
            pass
        s = str(value or "").strip()
        if not s:
            return None
        n = int(s)
        if not (1 <= n <= 31):
            return None
        return n

    def save():
        try:
            nm = (name_var.get() or "").strip()
            if not nm:
                messagebox.showerror("Required", "Client name is required.", parent=win)
                return
            principal = _parse_float_var(principal_var, None)
            if principal is None:
                messagebox.showerror("Invalid", "Principal must be a number.", parent=win)
                return
            dr = _validate_date(released_var.get(), "Date Released")

            lt = norm_lt(loan_type_var.get())
            if lt == "7x7":
                ir = 0.0
            else:
                ir = _parse_float_var(interest_var, 0.20)
                if ir > 1:
                    ir = ir / 100.0

            pt = (payterm_var.get() or "Daily").strip()
            if pt not in ("Daily", "Weekly", "Semi", "Monthly"):
                pt = "Daily"
            pa = _parse_float_var(payamt_var, 0.0)

            due_weekday_val = str(due_weekday_var.get() or "").strip()
            try:
                if "_spina__norm_weekday" in globals():
                    due_weekday_val = _spina__norm_weekday(due_weekday_val)
            except Exception:
                pass
            semi_due1_val = _norm_dom(semi_due_day1_var.get())
            semi_due2_val = _norm_dom(semi_due_day2_var.get())
            monthly_due_val = _norm_dom(monthly_due_day_var.get())

            if pt == "Weekly" and not due_weekday_val:
                messagebox.showerror("Required", "Weekly payment needs a due weekday.", parent=win)
                return
            if pt == "Semi" and (semi_due1_val is None or semi_due2_val is None):
                messagebox.showerror("Required", "Semi payment needs two due days.", parent=win)
                return
            if pt == "Monthly" and monthly_due_val is None:
                messagebox.showerror("Required", "Monthly payment needs a due day.", parent=win)
                return

            if pt != "Weekly":
                due_weekday_val = ""
            if pt != "Semi":
                semi_due1_val = None
                semi_due2_val = None
            if pt != "Monthly":
                monthly_due_val = None

            if is_new_var.get():
                nu = _validate_date(new_until_var.get(), "New Until")
            else:
                nu = ""

            try:
                pmode = _spina__merge_payment_mode((paymode_var.get() or "Cash").strip(), (paymode_other_var.get() or "").strip())
            except Exception:
                pmode = (paymode_var.get() or "Cash").strip() or "Cash"

            result["ok"] = True
            result["data"] = {
                "name": nm,
                "contact_number": contact_var.get().strip(),
                "loan_type": lt,
                "area": area_var.get().strip(),
                "principal": principal,
                "interest_rate": ir,
                "date_released": dr,
                "new_until": nu,
                "pay_start_offset_days": 1 if psod_var.get() else 0,
                "payment_term": pt,
                "payment_amount": pa,
                "payment_mode": pmode,
                "due_weekday": due_weekday_val,
                "semi_due_day1": semi_due1_val,
                "semi_due_day2": semi_due2_val,
                "monthly_due_day": monthly_due_val,
                "flex_due_rule": (flex_due_rule_var.get() or "").strip(),
                "_picture_source_path": (picture_source_var.get() or "").strip(),
                "_picture_clear": bool(picture_clear_var.get()),
            }
            win.destroy()
        except Exception as e:
            messagebox.showerror("Invalid", str(e), parent=win)

    def cancel():
        try:
            win.destroy()
        except Exception:
            pass

    _spina_v23_button(footer, "Cancel", command=cancel, kind="soft").pack(side="right", padx=(8, 0))
    _spina_v23_button(footer, "Save Application", command=save, kind="primary").pack(side="right", padx=(8, 0))

    try:
        win.bind("<Escape>", lambda e: cancel())
    except Exception:
        pass

    try:
        win.update_idletasks()
        pw, ph = self.root.winfo_width(), self.root.winfo_height()
        px, py = self.root.winfo_rootx(), self.root.winfo_rooty()
        w, h = win.winfo_width(), win.winfo_height()
        win.geometry(f"{w}x{h}+{max(px + (pw-w)//2,0)}+{max(py + (ph-h)//2,0)}")
    except Exception:
        pass

    self.root.wait_window(win)
    return result.get("data") if result.get("ok") else None

def _spina_v23_add_client_dialog(self):
    data = _spina_v23_client_form(self, "Add Client", initial={"loan_type": self._mode_filter()}, is_edit=False)
    if not data:
        return
    try:
        ok = self.db.add_client(
            data["name"],
            principal=data.get("principal", 0.0),
            date_released=data.get("date_released"),
            area=data.get("area", ""),
            interest_rate=data.get("interest_rate", None),
            new_until=data.get("new_until", ""),
            loan_type=data.get("loan_type"),
            pay_start_offset_days=data.get("pay_start_offset_days", 0),
            contact_number=data.get("contact_number", ""),
            payment_term=data.get("payment_term", "Daily"),
            payment_amount=data.get("payment_amount", 0.0),
            payment_mode=data.get("payment_mode", "Cash"),
            due_weekday=data.get("due_weekday", ""),
            semi_due_day1=data.get("semi_due_day1"),
            semi_due_day2=data.get("semi_due_day2"),
            monthly_due_day=data.get("monthly_due_day"),
            flex_due_rule=data.get("flex_due_rule", ""),
        )
        if not ok:
            messagebox.showerror("Failed", "Could not add client. Maybe duplicate name in the same loan type.")
            return

        pic = data.get("_picture_source_path") or ""
        if pic and hasattr(self.db, "set_client_picture"):
            try:
                self.db.set_client_picture(data["name"], pic, loan_type=data.get("loan_type"))
            except Exception as e:
                messagebox.showwarning("Picture", f"Client was added, but picture failed to save.\n\n{e}")
    except Exception as e:
        messagebox.showerror("Add Client Failed", str(e))
        return

    try:
        _app__maybe_suggest_link_clients(self, data.get("name"), data.get("loan_type"))
    except Exception:
        pass

    try:
        self.refresh_clients()
        self.refresh_reports()
        self.refresh_data_grid()
    except Exception:
        pass
    messagebox.showinfo("Added", f"Client '{data.get('name')}' added.")

def _spina_v23_on_client_edit(self, event=None):
    name, lt = _spina_v23_selected_name_lt(self)
    if not name:
        return
    info = self.db.get_client_info(name, loan_type=lt, include_archived=True) or {}
    if not info:
        messagebox.showerror("Client", "Client not found.")
        return

    data = _spina_v23_client_form(self, "Edit Client Application", initial=info, is_edit=True)
    if not data:
        return

    try:
        ok = self.db.update_client(
            old_name=name,
            new_name=data.get("name"),
            principal=data.get("principal"),
            date_released=data.get("date_released"),
            area=data.get("area"),
            interest_rate=data.get("interest_rate"),
            new_until=data.get("new_until"),
            loan_type=lt,
            pay_start_offset_days=data.get("pay_start_offset_days"),
            contact_number=data.get("contact_number"),
            payment_term=data.get("payment_term"),
            payment_amount=data.get("payment_amount"),
            payment_mode=data.get("payment_mode"),
            due_weekday=data.get("due_weekday"),
            semi_due_day1=data.get("semi_due_day1"),
            semi_due_day2=data.get("semi_due_day2"),
            monthly_due_day=data.get("monthly_due_day"),
            flex_due_rule=data.get("flex_due_rule", ""),
        )
        if not ok:
            messagebox.showerror("Failed", "Update failed.")
            return

        new_name = data.get("name") or name
        if data.get("_picture_clear") and hasattr(self.db, "clear_client_picture"):
            try:
                self.db.clear_client_picture(new_name, loan_type=lt)
            except Exception:
                pass
        pic = data.get("_picture_source_path") or ""
        if pic and hasattr(self.db, "set_client_picture"):
            try:
                self.db.set_client_picture(new_name, pic, loan_type=lt)
            except Exception as e:
                messagebox.showwarning("Picture", f"Client was updated, but picture failed to save.\n\n{e}")
    except Exception as e:
        messagebox.showerror("Update Client Failed", str(e))
        return

    try:
        _app__maybe_suggest_link_clients(self, data.get("name"), lt)
    except Exception:
        pass

    try:
        self.refresh_clients()
        self.refresh_reports()
        self.refresh_data_grid()
        _spina_v23_refresh_client_profile(self)
    except Exception:
        pass
    messagebox.showinfo("Updated", "Client application updated.")

