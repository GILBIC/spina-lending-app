"""Modern Clients tab presentation extracted from the SPINA desktop entry module.

Client application-form validation, add/update database writes, picture/file handling,
loan balance and interest calculations, and the original refresh chain remain owned by
the desktop application. This module owns only Clients presentation and display helpers.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Mapping

from spina_app.ui_controls import _spina_v23_style_clients_tree
from spina_app.utilities.formatting import _spina_v23_money, _spina_v23_percent

_REQUIRED_DEPENDENCIES = (
    "_spina_v23_clients_colors",
    "_app__norm_lt_value",
    "_spina_v23_client_loan_summary",
    "_log_exc",
    "_spina__ensure_client_picture_column",
    "_spina_perf_dict_rows",
    "_spina_perf_ensure_indexes",
    "_spina_perf_norm_lt",
    "_app_refresh_clients",
    "_log_suppressed_once",
    "_spina__fmt_client_money",
    "_spina__parse_flexible_due_rule",
    "_spina__client_due_meta_base",
    "_spina_route_notice_key",
    "_spina_route_notice_load",
    "_spina_route_notice_norm_lt",
    "_spina_route_notice_norm_name",
)


def configure_clients_dependencies(namespace: Mapping[str, Any]) -> tuple[str, ...]:
    """Bind application-owned callbacks used by the Clients presentation module."""
    missing = []
    for name in _REQUIRED_DEPENDENCIES:
        value = namespace.get(name)
        if value is None:
            missing.append(name)
            continue
        globals()[name] = value
    return tuple(missing)


def _spina_v23_button(parent, text, command=None, kind="normal", width=None):
    c = _spina_v23_clients_colors()
    bg = c["card2"]
    fg = c["fg"]
    if kind == "primary":
        bg, fg = c["blue"], "#ffffff"
    elif kind == "success":
        bg, fg = c["green"], "#ffffff"
    elif kind == "danger":
        bg, fg = c["red"], "#ffffff"
    elif kind == "soft":
        bg, fg = c["soft"], c["fg"]

    return tk.Button(
        parent,
        text=text,
        command=command,
        bg=bg,
        fg=fg,
        activebackground=bg,
        activeforeground=fg,
        relief="flat",
        bd=0,
        padx=14,
        pady=8,
        font=("Segoe UI", 9, "bold"),
        cursor="hand2",
        width=width,
    )

def _spina_v23_card(parent, title, value="—", subtitle="", accent=None):
    c = _spina_v23_clients_colors()
    frame = tk.Frame(parent, bg=c["card"], highlightbackground=c["border"], highlightthickness=1, bd=0)
    if accent:
        tk.Frame(frame, bg=accent, height=4).pack(fill="x", side="top")
    tk.Label(frame, text=title, bg=c["card"], fg=c["muted"], font=("Segoe UI", 9, "bold"), anchor="w").pack(fill="x", padx=14, pady=(10, 0))
    value_lbl = tk.Label(frame, text=value, bg=c["card"], fg=c["fg"], font=("Segoe UI", 16, "bold"), anchor="w")
    value_lbl.pack(fill="x", padx=14, pady=(4, 0))
    sub_lbl = tk.Label(frame, text=subtitle, bg=c["card"], fg=c["muted"], font=("Segoe UI", 8), anchor="w")
    sub_lbl.pack(fill="x", padx=14, pady=(2, 10))
    return frame, value_lbl, sub_lbl

def _spina_v23_selected_name_lt(self):
    try:
        sel = self.clients_tree.selection()
        if not sel:
            return "", _app__norm_lt_value(self, self._mode_filter())
        iid = sel[0]
        vals = self.clients_tree.item(iid, "values") or ()
        name = str(vals[0] if vals else "").strip()
        lt = _app__norm_lt_value(self, self._mode_filter())
        try:
            tags = self.clients_tree.item(iid, "tags") or ()
            for t in tags:
                if str(t).startswith("lt:"):
                    lt = _app__norm_lt_value(self, str(t).split(":", 1)[1])
                    break
        except Exception:
            pass
        return name, lt
    except Exception:
        return "", _app__norm_lt_value(self, self._mode_filter())

def _spina_v23_refresh_client_profile(self):
    try:
        vars_map = getattr(self, "_clients_profile_vars", {}) or {}
        name, lt = _spina_v23_selected_name_lt(self)
        if not name:
            for k, v in vars_map.items():
                try:
                    v.set("—")
                except Exception:
                    pass
            try:
                if hasattr(self, "clients_picture_preview"):
                    self.clients_picture_preview.configure(image="", text="No client selected")
                    self._clients_picture_img = None
            except Exception:
                pass
            return

        info = self.db.get_client_info(name, loan_type=lt, include_archived=True) or {}
        summary = _spina_v23_client_loan_summary(self, info)
        data = {
            "name": info.get("name") or name,
            "type": info.get("loan_type") or lt,
            "area": info.get("area") or "—",
            "contact": info.get("contact_number") or "—",
            "term": info.get("payment_term") or "—",
            "payment": _spina_v23_money(info.get("payment_amount") or 0),
            "mode": info.get("payment_mode") or "Cash",
            "principal": _spina_v23_money(info.get("principal") or 0),
            "total": _spina_v23_money(summary.get("total_to_pay") or info.get("total_to_pay") or 0),
            "paid": _spina_v23_money(summary.get("paid") or 0),
            "balance": _spina_v23_money(summary.get("balance") or 0),
            "progress": _spina_v23_percent(summary.get("progress") or 0),
            "released": info.get("date_released") or "—",
            "due": info.get("due_date") or "—",
            "renewals": str(summary.get("renewals") or 0),
            "last_cash": _spina_v23_money(summary.get("last_cash") or 0),
        }
        for k, value in data.items():
            try:
                if k in vars_map:
                    vars_map[k].set(str(value))
            except Exception:
                pass

        try:
            self.refresh_client_picture_panel()
        except Exception:
            pass
    except Exception as e:
        try:
            _log_exc("v23.refresh_client_profile", e)
        except Exception:
            pass

def _spina_v23_build_clients_tab(self):
    try:
        frm = self.tab_clients
        try:
            for w in frm.winfo_children():
                w.destroy()
        except Exception:
            pass

        c = _spina_v23_clients_colors(self)
        _spina_v23_style_clients_tree(self)

        self.search_clients_var = tk.StringVar(value="")
        self.clients_search_mode_var = tk.StringVar(value="All")
        self.bulk_area_var = tk.StringVar(value="")
        self.clients_count_var = tk.StringVar(value="Rows: 0")
        self._clients_stat_labels = {}
        self._clients_profile_vars = {}

        outer = tk.Frame(frm, bg=c["bg"])
        outer.pack(fill="both", expand=True)

        header = tk.Frame(outer, bg=c["bg"])
        header.pack(fill="x", padx=18, pady=(16, 10))

        titlebox = tk.Frame(header, bg=c["bg"])
        titlebox.pack(side="left", fill="x", expand=True)
        tk.Label(titlebox, text="Clients", bg=c["bg"], fg=c["fg"], font=("Segoe UI", 20, "bold"), anchor="w").pack(fill="x")
        tk.Label(
            titlebox,
            text="Modern client file with profile picture, loan summary, linking, area assignment, and application-form editing.",
            bg=c["bg"], fg=c["muted"], font=("Segoe UI", 10), anchor="w"
        ).pack(fill="x", pady=(2, 0))

        _spina_v23_button(header, "Add Client", command=self.add_client_dialog, kind="primary").pack(side="right", padx=(8, 0))
        _spina_v23_button(header, "Renew", command=self.renew_client_selected, kind="success").pack(side="right", padx=(8, 0))
        _spina_v23_button(header, "History", command=self.open_client_history_dialog, kind="soft").pack(side="right", padx=(8, 0))

        controls = tk.Frame(outer, bg=c["panel"], highlightbackground=c["border"], highlightthickness=1, bd=0)
        controls.pack(fill="x", padx=18, pady=(0, 12))

        row = tk.Frame(controls, bg=c["panel"])
        row.pack(fill="x", padx=12, pady=10)

        search_box = tk.Frame(row, bg=c["panel"])
        search_box.pack(side="left", fill="x", expand=True, padx=(0, 10))
        tk.Label(search_box, text="Search Client / Area / Loan Info", bg=c["panel"], fg=c["muted"], font=("Segoe UI", 8, "bold"), anchor="w").pack(fill="x")
        search_line = tk.Frame(search_box, bg=c["panel"])
        search_line.pack(fill="x", pady=(3, 0))
        ent = ttk.Entry(search_line, textvariable=self.search_clients_var)
        ent.pack(side="left", fill="x", expand=True)
        _spina_v23_button(search_line, "Clear", command=lambda: self.search_clients_var.set(""), kind="soft").pack(side="left", padx=(8, 0))

        mode_box = tk.Frame(row, bg=c["panel"])
        mode_box.pack(side="left", padx=(0, 10))
        tk.Label(mode_box, text="Search In", bg=c["panel"], fg=c["muted"], font=("Segoe UI", 8, "bold"), anchor="w").pack(fill="x")
        cb_mode = ttk.Combobox(
            mode_box,
            textvariable=self.clients_search_mode_var,
            values=("All", "Client", "Area", "Linked", "Unlinked", "Suggested Link", "Blanks", "Principal", "Released", "Start Date", "Due Date"),
            state="readonly",
            width=16,
        )
        cb_mode.pack(fill="x", pady=(3, 0))

        area_box = tk.Frame(row, bg=c["panel"])
        area_box.pack(side="left", padx=(0, 10))
        tk.Label(area_box, text="Bulk Area", bg=c["panel"], fg=c["muted"], font=("Segoe UI", 8, "bold"), anchor="w").pack(fill="x")
        area_line = tk.Frame(area_box, bg=c["panel"])
        area_line.pack(fill="x", pady=(3, 0))
        self.bulk_area_cb = ttk.Combobox(area_line, textvariable=self.bulk_area_var, width=18, state="readonly")
        self.bulk_area_cb.pack(side="left")
        _spina_v23_button(area_line, "Set", command=self.set_area_for_selected_clients, kind="soft").pack(side="left", padx=(6, 0))
        _spina_v23_button(area_line, "Manage", command=self.open_areas_manager, kind="soft").pack(side="left", padx=(6, 0))

        try:
            self.search_clients_var.trace_add("write", self._schedule_refresh_clients)
            cb_mode.bind("<<ComboboxSelected>>", lambda e: self._schedule_refresh_clients())
        except Exception:
            pass

        actions = tk.Frame(controls, bg=c["panel"])
        actions.pack(fill="x", padx=12, pady=(0, 10))
        _spina_v23_button(actions, "Link", command=self.link_selected_client, kind="soft").pack(side="left", padx=(0, 6))
        _spina_v23_button(actions, "Unlink", command=self.unlink_selected_client, kind="soft").pack(side="left", padx=(0, 6))
        _spina_v23_button(actions, "Archived", command=self.open_archived_clients_dialog, kind="soft").pack(side="left", padx=(0, 6))
        self._del_client_btn = _spina_v23_button(actions, "Archive Client", command=self.delete_client_selected, kind="danger")
        self._del_client_btn.pack(side="left", padx=(0, 6))
        try:
            self._del_client_btn.config(state="disabled")
        except Exception:
            pass

        # SPINA removed legacy Clients-tab action button statement
        # SPINA removed legacy Clients-tab action button statement
        # SPINA removed legacy Clients-tab action button statement
        # SPINA removed legacy Clients-tab action button statement

        cards = tk.Frame(outer, bg=c["bg"])
        cards.pack(fill="x", padx=18, pady=(0, 12))
        for i in range(4):
            cards.columnconfigure(i, weight=1, uniform="clientcards")
        for i, (key, title, value, sub, accent) in enumerate([
            ("rows", "Clients Listed", "0", "Current view", c["blue"]),
            ("view", "Loan View", "Regular", "Regular / 7x7", c["purple"]),
            ("selected", "Selected Client", "—", "Profile panel on right", c["green"]),
            ("balance", "Selected Balance", "—", "Remaining loan balance", c["orange"]),
        ]):
            card, val, sublbl = _spina_v23_card(cards, title, value, sub, accent)
            card.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 8, 0), ipady=2)
            self._clients_stat_labels[key] = (val, sublbl)

        main = tk.Frame(outer, bg=c["bg"])
        main.pack(fill="both", expand=True, padx=18, pady=(0, 18))
        main.columnconfigure(0, weight=1)
        main.columnconfigure(1, weight=0)
        main.rowconfigure(0, weight=1)

        table_card = tk.Frame(main, bg=c["panel"], highlightbackground=c["border"], highlightthickness=1, bd=0)
        table_card.grid(row=0, column=0, sticky="nsew", padx=(0, 12))

        table_head = tk.Frame(table_card, bg=c["panel"])
        table_head.pack(fill="x", padx=12, pady=(10, 4))
        tk.Label(table_head, text="Client List", bg=c["panel"], fg=c["fg"], font=("Segoe UI", 12, "bold"), anchor="w").pack(side="left")
        tk.Label(table_head, textvariable=self.clients_count_var, bg=c["panel"], fg=c["muted"], font=("Segoe UI", 9), anchor="e").pack(side="right")

        cols = ("name", "area", "term", "day_due", "payment", "mode", "linked", "contact", "principal", "interest", "total", "released", "due")
        self.clients_tree = ttk.Treeview(table_card, columns=cols, show="headings", height=20, selectmode="extended", style="ModernClients.Treeview")

        _hdr = {
            "name": "Client", "area": "Area", "term": "Term", "day_due": "Day Due", "payment": "Payment",
            "mode": "Mode", "linked": "Linked", "contact": "Contact", "principal": "Principal",
            "interest": "Interest", "total": "Total", "released": "Released", "due": "Due",
        }
        _w = {
            "name": 250, "area": 190, "term": 86, "day_due": 105, "payment": 100,
            "mode": 85, "linked": 95, "contact": 125, "principal": 110,
            "interest": 95, "total": 115, "released": 108, "due": 108,
        }
        _anchors = {
            "name": "w", "area": "w", "term": "center", "day_due": "center", "payment": "e",
            "mode": "center", "linked": "center", "contact": "w", "principal": "e",
            "interest": "e", "total": "e", "released": "center", "due": "center",
        }
        for col in cols:
            self.clients_tree.heading(col, text=_hdr.get(col, col.title()), anchor=_anchors.get(col, "w"))
            self.clients_tree.column(col, width=_w.get(col, 100), minwidth=70, anchor=_anchors.get(col, "w"), stretch=(col in ("name", "area")))

        ysb = ttk.Scrollbar(table_card, orient="vertical", command=self.clients_tree.yview)
        xsb = ttk.Scrollbar(table_card, orient="horizontal", command=self.clients_tree.xview)
        self.clients_tree.configure(yscrollcommand=ysb.set, xscrollcommand=xsb.set)
        self.clients_tree.pack(side="left", fill="both", expand=True, padx=(12, 0), pady=(0, 12))
        ysb.pack(side="right", fill="y", padx=(0, 12), pady=(0, 12))
        xsb.pack(side="bottom", fill="x", padx=12, pady=(0, 10))

        try:
            self.clients_tree.tag_configure("even", background=c["panel"])
            self.clients_tree.tag_configure("odd", background=c["card2"])
            self.clients_tree.tag_configure("extra7x7", foreground=c["orange"])
        except Exception:
            pass

        # Right profile/picture panel
        profile = tk.Frame(main, width=330, bg=c["panel"], highlightbackground=c["border"], highlightthickness=1, bd=0)
        profile.grid(row=0, column=1, sticky="ns")
        profile.grid_propagate(False)

        tk.Label(profile, text="Client Profile", bg=c["panel"], fg=c["fg"], font=("Segoe UI", 13, "bold"), anchor="w").pack(fill="x", padx=14, pady=(12, 4))

        pic_frame = tk.Frame(profile, bg=c["card2"], highlightbackground=c["border"], highlightthickness=1, bd=0)
        pic_frame.pack(fill="x", padx=14, pady=(4, 10))
        self.clients_picture_preview = tk.Label(pic_frame, text="No client selected", bg=c["card2"], fg=c["muted"], width=28, height=8, anchor="center", justify="center")
        self.clients_picture_preview.pack(fill="x", padx=10, pady=10)
        self.clients_picture_info_var = tk.StringVar(value="Select a client.")
        self.clients_picture_path_var = tk.StringVar(value="")
        self.clients_picture_box = profile
        self._clients_picture_img = None

        pic_btns = tk.Frame(profile, bg=c["panel"])
        pic_btns.pack(fill="x", padx=14, pady=(0, 10))
        _spina_v23_button(pic_btns, "Set Picture", command=lambda: self.set_selected_client_picture(), kind="soft").pack(side="left", fill="x", expand=True, padx=(0, 6))
        _spina_v23_button(pic_btns, "Clear", command=lambda: self.clear_selected_client_picture(), kind="soft").pack(side="left", fill="x", expand=True)

        profile_vars = {}
        def add_profile_row(label, key):
            box = tk.Frame(profile, bg=c["panel"])
            box.pack(fill="x", padx=14, pady=(0, 7))
            tk.Label(box, text=label, bg=c["panel"], fg=c["muted"], font=("Segoe UI", 8, "bold"), anchor="w").pack(fill="x")
            var = tk.StringVar(value="—")
            tk.Label(box, textvariable=var, bg=c["panel"], fg=c["fg"], font=("Segoe UI", 10, "bold"), anchor="w", wraplength=290, justify="left").pack(fill="x")
            profile_vars[key] = var

        for label, key in [
            ("Name", "name"),
            ("Loan Type", "type"),
            ("Area", "area"),
            ("Contact", "contact"),
            ("Payment Plan", "term"),
            ("Payment Amount", "payment"),
            ("Balance", "balance"),
            ("Progress", "progress"),
            ("Renewals", "renewals"),
            ("Last Cash Released", "last_cash"),
        ]:
            add_profile_row(label, key)
        self._clients_profile_vars = profile_vars

        try:
            self.clients_tree.bind("<Double-1>", self.on_client_edit)
            self.clients_tree.bind("<<TreeviewSelect>>", lambda e: (_spina_v23_refresh_client_profile(self), self._update_toolbar_states()))
        except Exception:
            pass

        try:
            self._update_toolbar_states()
        except Exception:
            pass
        try:
            self._refresh_area_dropdowns()
        except Exception:
            pass

        self.refresh_clients()

    except Exception as e:
        try:
            _log_exc("v23.clients.build_tab", e)
        except Exception:
            pass
        try:
            messagebox.showerror("Clients", f"Unable to build Clients page.\n\n{e}")
        except Exception:
            pass

def _spina_v23_entry(parent, label, var, width=22, kind="entry", values=None, readonly=False):
    c = _spina_v23_clients_colors()
    box = tk.Frame(parent, bg=c["panel"])
    tk.Label(box, text=label, bg=c["panel"], fg=c["muted"], font=("Segoe UI", 8, "bold"), anchor="w").pack(fill="x")
    if kind == "combo":
        w = ttk.Combobox(box, textvariable=var, values=values or [], width=width, state=("readonly" if readonly else "normal"))
    else:
        w = ttk.Entry(box, textvariable=var, width=width)
    w.pack(fill="x", pady=(3, 0))
    return box, w

def _spina_v23_update_client_cards(self):
    try:
        cards = getattr(self, "_clients_stat_labels", {}) or {}
        count = len(self.clients_tree.get_children()) if hasattr(self, "clients_tree") else 0
        mode = str(self._mode_filter() or "Regular")
        name, lt = _spina_v23_selected_name_lt(self)
        bal = "—"
        if name:
            try:
                info = self.db.get_client_info(name, loan_type=lt, include_archived=True) or {}
                bal = _spina_v23_money(_spina_v23_client_loan_summary(self, info).get("balance") or 0)
            except Exception:
                pass
        values = {
            "rows": (str(count), "Current list"),
            "view": (mode, "Current loan view"),
            "selected": (name or "—", lt if name else "Select a client"),
            "balance": (bal, "Selected remaining balance"),
        }
        for k, (v, s) in values.items():
            try:
                val, sub = cards.get(k, (None, None))
                if val is not None:
                    val.configure(text=v)
                if sub is not None:
                    sub.configure(text=s)
            except Exception:
                pass
    except Exception:
        pass


def _db_get_client_picture(self, name, loan_type=None, include_archived=True):
    try:
        _spina__ensure_client_picture_column(self)
    except Exception:
        pass
    try:
        info = self.get_client_info(name, loan_type=loan_type, include_archived=include_archived) or {}
    except Exception:
        info = {}
    return str(info.get('client_picture') or '').strip()

def _app__selected_client_name_and_lt(self):
    try:
        sel = self.clients_tree.selection()
    except Exception:
        sel = ()
    if not sel:
        return ('', _app__norm_lt_value(self, self._mode_filter()))
    iid = sel[0]
    try:
        vals = self.clients_tree.item(iid, 'values') or ()
    except Exception:
        vals = ()
    name = str(vals[0] if vals else '').strip()
    lt = _app__norm_lt_value(self, self._mode_filter())
    try:
        tags = self.clients_tree.item(iid, 'tags') or ()
        for t in tags:
            if str(t).startswith('lt:'):
                lt = _app__norm_lt_value(self, str(t).split(':', 1)[1])
                break
    except Exception:
        pass
    return (name, lt)

def _app_install_clients_picture_ui(self):
    if getattr(self, '_clients_picture_ui_ready', False):
        try:
            self.refresh_client_picture_panel()
        except Exception:
            pass
        return

    try:
        box = ttk.LabelFrame(self.tab_clients, text='Client Picture')
        box.pack(fill='x', padx=8, pady=(0, 8))
    except Exception:
        return

    top = ttk.Frame(box)
    top.pack(fill='x', padx=8, pady=8)

    preview = ttk.Label(top, text='No picture selected', anchor='center', width=22)
    try:
        preview.configure(relief='solid', padding=8)
    except Exception:
        pass
    preview.pack(side='left', padx=(0, 12), pady=2)

    right = ttk.Frame(top)
    right.pack(side='left', fill='x', expand=True)

    info_var = tk.StringVar(value='Select a client to view picture.')
    path_var = tk.StringVar(value='')
    ttk.Label(right, textvariable=info_var, font=('TkDefaultFont', 10, 'bold')).pack(anchor='w')
    ttk.Label(right, textvariable=path_var, foreground='#666', wraplength=520, justify='left').pack(anchor='w', pady=(4, 8))

    btns = ttk.Frame(right)
    btns.pack(anchor='w')
    ttk.Button(btns, text='Set Picture', command=lambda: self.set_selected_client_picture()).pack(side='left', padx=(0, 6))
    ttk.Button(btns, text='Clear Picture', command=lambda: self.clear_selected_client_picture()).pack(side='left')

    self.clients_picture_box = box
    self.clients_picture_preview = preview
    self.clients_picture_info_var = info_var
    self.clients_picture_path_var = path_var
    self._clients_picture_img = None
    self._clients_picture_ui_ready = True

    try:
        self.clients_tree.bind('<<TreeviewSelect>>', lambda e: self.refresh_client_picture_panel(), add='+')
    except Exception:
        try:
            self.clients_tree.bind('<<TreeviewSelect>>', lambda e: self.refresh_client_picture_panel())
        except Exception:
            pass

    try:
        self.refresh_client_picture_panel()
    except Exception:
        pass

def _spina_perf_clients_rows(db, loan_type="Regular", search=None, search_by="all", include_extra_7x7=True):
    """Bulk load rows for Clients tab in one/few queries, avoiding per-row get_client_info()."""
    _spina_perf_ensure_indexes(db)
    lt = _spina_perf_norm_lt(loan_type)
    term = (search or "").strip()
    sb = (search_by or "all").strip().lower()
    cur = db.conn.cursor()

    # Map search mode aliases
    try:
        if sb.startswith("cli"):
            sb = "client"
        elif sb.startswith("are"):
            sb = "area"
        elif sb.startswith("link"):
            sb = "linked"
        elif sb.startswith("unl"):
            sb = "unlinked"
        elif sb.startswith("sug"):
            sb = "suggested"
        elif sb.startswith("blank"):
            sb = "blanks"
        elif sb.startswith("pri"):
            sb = "principal"
        elif sb.startswith("rel"):
            sb = "released"
        elif sb.startswith("sta"):
            sb = "start_date"
        elif sb.startswith("due"):
            sb = "due_date"
        else:
            sb = "all"
    except Exception:
        sb = "all"

    where = ["IFNULL(c.loan_type,'Regular') = ?", "COALESCE(c.is_archived,0)=0"]
    params = [lt]
    like = f"%{term}%"

    # Special typed commands in All search
    tlow = term.lower()
    if sb == "all" and tlow in ("blanks", "blank", "missing", "incomplete"):
        sb, term = "blanks", ""
    elif sb == "all" and tlow in ("linked", "link"):
        sb, term = "linked", ""
    elif sb == "all" and tlow in ("unlinked", "not linked", "notlinked"):
        sb, term = "unlinked", ""
    elif sb == "all" and tlow in ("suggested", "suggest", "suggestion", "suggested link", "suggestedlink"):
        sb, term = "suggested", ""

    if sb == "blanks":
        where.append("(IFNULL(c.area,'')='' OR IFNULL(c.date_released,'')='' OR IFNULL(c.due_date,'')='' OR IFNULL(c.principal,0)=0)")
    elif sb == "linked":
        where.append("TRIM(IFNULL(c.person_uid,'')) <> ''")
        where.append("EXISTS(SELECT 1 FROM clients c2 WHERE c2.person_uid=c.person_uid AND c2.id<>c.id AND IFNULL(c2.loan_type,'Regular')<>IFNULL(c.loan_type,'Regular') AND COALESCE(c2.is_archived,0)=0)")
    elif sb == "suggested":
        where.append("TRIM(IFNULL(c.person_uid,'')) = ''")
        where.append("EXISTS(SELECT 1 FROM clients c2 WHERE c2.name=c.name AND c2.id<>c.id AND IFNULL(c2.loan_type,'Regular')<>IFNULL(c.loan_type,'Regular') AND COALESCE(c2.is_archived,0)=0)")
        if term:
            where.append("c.name LIKE ?")
            params.append(like)
    elif sb == "unlinked":
        where.append("TRIM(IFNULL(c.person_uid,'')) = ''")
        where.append("(EXISTS(SELECT 1 FROM clients c2 WHERE c2.name=c.name AND c2.id<>c.id AND IFNULL(c2.loan_type,'Regular')<>IFNULL(c.loan_type,'Regular') AND COALESCE(c2.is_archived,0)=0) OR (IFNULL(c.loan_type,'Regular')='7x7' AND NOT EXISTS(SELECT 1 FROM clients c2 WHERE c2.name=c.name AND IFNULL(c2.loan_type,'Regular')='Regular' AND COALESCE(c2.is_archived,0)=0)))")
        if term:
            where.append("c.name LIKE ?")
            params.append(like)
    elif term:
        if sb == "client":
            where.append("c.name LIKE ?"); params.append(like)
        elif sb == "area":
            where.append("IFNULL(c.area,'') LIKE ?"); params.append(like)
        elif sb == "principal":
            where.append("CAST(IFNULL(c.principal,0) AS TEXT) LIKE ?"); params.append(like)
        elif sb == "released":
            where.append("IFNULL(c.date_released,'') LIKE ?"); params.append(like)
        elif sb == "due_date":
            where.append("IFNULL(c.due_date,'') LIKE ?"); params.append(like)
        elif sb == "start_date":
            where.append("IFNULL(date(c.date_released, '+' || IFNULL(c.pay_start_offset_days,0) || ' day'),'') LIKE ?"); params.append(like)
        else:
            where.append("""(
                c.name LIKE ?
                OR IFNULL(c.area,'') LIKE ?
                OR CAST(IFNULL(c.principal,0) AS TEXT) LIKE ?
                OR IFNULL(c.date_released,'') LIKE ?
                OR IFNULL(c.due_date,'') LIKE ?
                OR IFNULL(date(c.date_released, '+' || IFNULL(c.pay_start_offset_days,0) || ' day'),'') LIKE ?
                OR IFNULL(c.person_uid,'') LIKE ?
            )""")
            params.extend([like, like, like, like, like, like, like])

    sql = "SELECT c.* FROM clients c WHERE " + " AND ".join(where) + " ORDER BY c.name COLLATE NOCASE"
    rows = _spina_perf_dict_rows(cur.execute(sql, params).fetchall())

    # Build fast lookup sets for link labels, no per-row DB calls.
    try:
        active = _spina_perf_dict_rows(cur.execute(
            "SELECT name, loan_type, person_uid FROM clients WHERE COALESCE(is_archived,0)=0"
        ).fetchall())
    except Exception:
        active = []

    other_by_name = set()
    pu_types = {}
    for r in active:
        nm = str(r.get("name") or "").strip().lower()
        rlt = _spina_perf_norm_lt(r.get("loan_type"))
        pu = str(r.get("person_uid") or "").strip()
        if rlt != lt and nm:
            other_by_name.add(nm)
        if pu:
            pu_types.setdefault(pu, set()).add(rlt)

    other_lt = "7x7" if lt == "Regular" else "Regular"
    final = []
    seen = set()
    for r in rows:
        nm_key = str(r.get("name") or "").strip().lower()
        pu = str(r.get("person_uid") or "").strip()
        link_label = ""
        if pu and len(pu_types.get(pu, set())) > 1:
            link_label = f"{other_lt}✓"
        elif pu:
            link_label = "Linked✓"
        elif nm_key in other_by_name:
            link_label = other_lt
        r["_spina_link_label"] = link_label
        r["_spina_row_lt"] = lt
        r["_spina_extra7x7"] = False
        final.append(r)
        seen.add(nm_key)

    # In Regular view, append unpaired 7x7 clients using one SQL query.
    if lt == "Regular" and include_extra_7x7 and sb not in ("linked", "suggested"):
        extra_where = [
            "IFNULL(c.loan_type,'Regular')='7x7'",
            "COALESCE(c.is_archived,0)=0",
            "TRIM(IFNULL(c.person_uid,''))=''",
            "NOT EXISTS(SELECT 1 FROM clients r WHERE r.name=c.name AND IFNULL(r.loan_type,'Regular')='Regular' AND COALESCE(r.is_archived,0)=0)"
        ]
        extra_params = []
        if term:
            if sb == "area":
                extra_where.append("IFNULL(c.area,'') LIKE ?"); extra_params.append(like)
            elif sb == "principal":
                extra_where.append("CAST(IFNULL(c.principal,0) AS TEXT) LIKE ?"); extra_params.append(like)
            elif sb == "released":
                extra_where.append("IFNULL(c.date_released,'') LIKE ?"); extra_params.append(like)
            elif sb == "due_date":
                extra_where.append("IFNULL(c.due_date,'') LIKE ?"); extra_params.append(like)
            elif sb == "start_date":
                extra_where.append("IFNULL(date(c.date_released, '+' || IFNULL(c.pay_start_offset_days,0) || ' day'),'') LIKE ?"); extra_params.append(like)
            else:
                extra_where.append("(c.name LIKE ? OR IFNULL(c.area,'') LIKE ?)")
                extra_params.extend([like, like])
        extra_sql = "SELECT c.* FROM clients c WHERE " + " AND ".join(extra_where) + " ORDER BY c.name COLLATE NOCASE"
        for r in _spina_perf_dict_rows(cur.execute(extra_sql, extra_params).fetchall()):
            nm_key = str(r.get("name") or "").strip().lower()
            if nm_key in seen:
                continue
            r["_spina_link_label"] = "7x7 ONLY"
            r["_spina_row_lt"] = "7x7"
            r["_spina_extra7x7"] = True
            final.append(r)
            seen.add(nm_key)

    return final

def _spina_perf_refresh_clients(self):
    """Fast Clients tab refresh for large datasets."""
    try:
        term = (getattr(self, "search_clients_var", tk.StringVar()).get() or "").strip()
    except Exception:
        term = ""
    try:
        lt = _app__norm_lt_value(self, self._mode_filter())
    except Exception:
        lt = "Regular"
    try:
        mode = (getattr(self, "clients_search_mode_var", tk.StringVar(value="All")).get() or "Both").strip().lower()
    except Exception:
        mode = "both"

    try:
        tree = self.clients_tree
        try:
            tree.delete(*tree.get_children())
        except Exception:
            for rid in tree.get_children():
                tree.delete(rid)
    except Exception:
        return

    try:
        rows = _spina_perf_clients_rows(self.db, loan_type=lt, search=term if term else None, search_by=mode, include_extra_7x7=True)
    except Exception as e:
        try:
            _log_exc("perf_refresh_clients: bulk load failed; using old loader", e)
        except Exception:
            pass
        try:
            return _app_refresh_clients(self)
        except Exception:
            return

    for idx, info in enumerate(rows or []):
        try:
            row_lt = _spina_perf_norm_lt(info.get("_spina_row_lt") or info.get("loan_type") or lt)
            is_extra_7x7 = bool(info.get("_spina_extra7x7"))
            _day_due, _due_today = _spina__client_due_meta(info)
            tags = [f"lt:{row_lt}", "even" if (idx % 2 == 0) else "odd"]
            if is_extra_7x7:
                tags.append("extra7x7")
            iid = (str(info.get("client_uid") or "").strip() or None)
            row_values = (
                info.get("name", ""),
                info.get("area", ""),
                info.get("payment_term", ""),
                _day_due,
                _spina__fmt_client_money(info.get("payment_amount", 0)),
                info.get("payment_mode", "Cash"),
                info.get("_spina_link_label", ""),
                info.get("contact_number", ""),
                _spina__fmt_client_money(info.get("principal", 0)),
                _spina__fmt_client_money(info.get("interest_amount", 0)),
                _spina__fmt_client_money(info.get("total_to_pay", 0)),
                info.get("date_released", ""),
                info.get("due_date", ""),
            )
            try:
                tree.insert("", "end", iid=iid, tags=tuple(tags), values=row_values)
            except Exception:
                tree.insert("", "end", tags=tuple(tags), values=row_values)
        except Exception as e:
            try:
                _log_suppressed_once("perf_client_row_insert", "client row insert skipped", e)
            except Exception:
                pass

    try:
        if hasattr(self, "clients_count_var"):
            self.clients_count_var.set(f"Rows: {len(tree.get_children())}")
    except Exception:
        pass
    try:
        self._update_toolbar_states()
    except Exception:
        pass
    if not term:
        try:
            self._refresh_area_dropdowns()
        except Exception:
            pass
    try:
        if hasattr(self, "refresh_client_picture_panel"):
            self.refresh_client_picture_panel()
    except Exception:
        pass

def _spina__client_due_meta(info: dict | None, as_of=None) -> tuple[str, bool]:
    try:
        flex = _spina__parse_flexible_due_rule(info or {}, target=as_of)
        if flex is not None:
            return flex
    except Exception:
        pass
    try:
        if callable(_spina__client_due_meta_base):
            return _spina__client_due_meta_base(info, as_of=as_of)
    except Exception:
        pass
    return ('', False)

def _spina_route_notice_for_client(db, client: str, loan_type: str, day_iso: str) -> str:
    try:
        day_iso = str(day_iso or "").strip()[:10]
        if not day_iso:
            return ""
        lt = _spina_route_notice_norm_lt(loan_type)
        client = str(client or "").strip()
        data = _spina_route_notice_load()
        bucket = data.get(day_iso)
        if not isinstance(bucket, dict):
            return ""

        # Try stable client_uid first if available.
        uid = ""
        try:
            if db is not None and hasattr(db, "get_client_uid"):
                uid = str(db.get_client_uid(client, loan_type=lt) or "").strip()
        except Exception:
            uid = ""
        if uid:
            rec = bucket.get(_spina_route_notice_key(client, lt, uid))
            if isinstance(rec, dict) and str(rec.get("notice") or "").strip():
                return str(rec.get("notice") or "").strip()

        # Fallback by normalized name and loan type.
        n_client = _spina_route_notice_norm_name(client)
        rec = bucket.get(_spina_route_notice_key(client, lt, ""))
        if isinstance(rec, dict) and str(rec.get("notice") or "").strip():
            return str(rec.get("notice") or "").strip()

        for _k, rec in bucket.items():
            try:
                if not isinstance(rec, dict):
                    continue
                if _spina_route_notice_norm_lt(rec.get("loan_type")) != lt:
                    continue
                if str(rec.get("client_uid") or "").strip() and uid and str(rec.get("client_uid") or "").strip() == uid:
                    return str(rec.get("notice") or "").strip()
                if _spina_route_notice_norm_name(rec.get("client") or rec.get("client_norm")) == n_client:
                    return str(rec.get("notice") or "").strip()
            except Exception:
                continue
        return ""
    except Exception:
        return ""
