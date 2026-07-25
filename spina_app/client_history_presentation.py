"""Read-only client-history dialog presentation extracted in Wave 36."""
from __future__ import annotations

_CLIENT_HISTORY_DEPENDENCIES = {}
_PROTECTED_GLOBALS = {
    "__builtins__", "__cached__", "__doc__", "__file__", "__loader__",
    "__name__", "__package__", "__spec__", "_CLIENT_HISTORY_DEPENDENCIES",
    "_PROTECTED_GLOBALS", "configure_client_history_dependencies",
    "CLIENT_HISTORY_SOURCE_SHA256", "CLIENT_HISTORY_TARGET",
}


def configure_client_history_dependencies(namespace):
    _CLIENT_HISTORY_DEPENDENCIES.clear()
    _CLIENT_HISTORY_DEPENDENCIES.update(namespace)
    for name, value in namespace.items():
        if name not in _PROTECTED_GLOBALS:
            globals()[name] = value


CLIENT_HISTORY_TARGET = '_app_open_client_history_dialog'
CLIENT_HISTORY_SOURCE_SHA256 = '570a2e0946cd702bfcdcbc1d3433b72ab9aed73fd61fba56be70e1ebb53555b8'

def _app_open_client_history_dialog(self):
    name = _app__get_selected_client_name(self)
    if not name:
        messagebox.showinfo("History", "Select a client first.")
        return

    lt = _app__norm_lt_value(self, self._mode_filter())
    try:
        uid = self.db.get_client_uid(name, loan_type=lt)
    except Exception:
        uid = None
    if not uid:
        messagebox.showerror("History", "Could not locate client UID.")
        return

    # Determine linked group (Regular + 7x7) if any.
    linked_uids = [uid]
    linked_label = ""
    try:
        linked_uids = self.db.get_linked_client_uids(uid) or [uid]
        if len(linked_uids) > 1:
            linked_label = " (linked Regular+7x7)"
    except Exception:
        linked_uids = [uid]

    def _coerce_rows(rows):
        out = []
        for r in (rows or []):
            try:
                out.append(dict(r))
            except Exception:
                try:
                    out.append({k: r[k] for k in r.keys()})
                except Exception:
                    pass
        return out

    def _ts_key(row):
        return str(row.get("changed_at") or row.get("ts") or "")

    def _safe_json_load(blob):
        if blob in (None, ""):
            return None
        try:
            return json.loads(blob) if isinstance(blob, str) else blob
        except Exception:
            return None

    def _pretty(obj_or_json):
        if obj_or_json in (None, ""):
            return ""
        obj = _safe_json_load(obj_or_json)
        if obj is None:
            try:
                return str(obj_or_json)
            except Exception:
                return ""
        try:
            return json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True, default=str)
        except Exception:
            try:
                return str(obj)
            except Exception:
                return ""

    def _fmt_scalar(v):
        if v is None:
            return "None"
        try:
            s = str(v).replace("\n", " ").strip()
        except Exception:
            s = repr(v)
        return (s[:57] + "…") if len(s) > 58 else s

    def _diff_pairs(old_json, new_json):
        old_obj = _safe_json_load(old_json)
        new_obj = _safe_json_load(new_json)
        if old_obj is None and new_obj is None:
            return []
        if old_obj is None and isinstance(new_obj, dict):
            return [(k, None, new_obj.get(k)) for k in sorted(new_obj.keys())]
        if new_obj is None and isinstance(old_obj, dict):
            return [(k, old_obj.get(k), None) for k in sorted(old_obj.keys())]
        if not isinstance(old_obj, dict) or not isinstance(new_obj, dict):
            if old_obj != new_obj:
                return [("value", old_obj, new_obj)]
            return []
        pairs = []
        for k in sorted(set(old_obj.keys()) | set(new_obj.keys())):
            ov = old_obj.get(k)
            nv = new_obj.get(k)
            if ov != nv:
                pairs.append((k, ov, nv))
        return pairs

    def _diff_summary(old_json, new_json):
        pairs = _diff_pairs(old_json, new_json)
        if not pairs:
            return ""
        if len(pairs) == 1 and pairs[0][0] == "value":
            return f"value: {_fmt_scalar(pairs[0][1])} → {_fmt_scalar(pairs[0][2])}"
        names = [p[0] for p in pairs]
        head = ", ".join(names[:4])
        if len(names) > 4:
            head += f" +{len(names)-4} more"
        return f"{len(names)} field(s): {head}"

    # Pull histories for the whole linked group so audit stays complete.
    client_rows_all = []
    try:
        seen_hist = set()
        for _uid in linked_uids:
            for row in _coerce_rows(self.db.get_client_history(client_uid=_uid, limit=1000) or []):
                key = (row.get("id"), row.get("client_uid"), row.get("changed_at"), row.get("action"), row.get("source"))
                if key in seen_hist:
                    continue
                seen_hist.add(key)
                client_rows_all.append(row)
        client_rows_all.sort(key=lambda r: (str(r.get("changed_at") or ""), int(r.get("id") or 0)), reverse=True)
    except Exception:
        client_rows_all = []

    try:
        tx_rows_all = _coerce_rows(self.db.get_transactions_for_client_uids(linked_uids) or [])
    except Exception:
        tx_rows_all = []

    try:
        tx_hist_all = _coerce_rows(self.db.get_transaction_history_for_client_uids(linked_uids) or [])
    except Exception:
        tx_hist_all = []

    # Summary counts.
    action_counts = {}
    for r in client_rows_all:
        a = str(r.get("action") or "UPDATED").strip().upper() or "UPDATED"
        action_counts[a] = action_counts.get(a, 0) + 1

    win = tk.Toplevel(self.root)
    win.title(f"Audit History: {name} ({lt}){linked_label}")
    win.geometry("1180x760")
    try:
        win.transient(self.root)
        win.grab_set()
    except Exception:
        pass

    outer = ttk.Frame(win, padding=8)
    outer.pack(fill='both', expand=True)

    hdr = ttk.Frame(outer)
    hdr.pack(fill='x', pady=(0, 8))
    ttk.Label(hdr, text=f"Audit Trail - {name}", font=('TkDefaultFont', 12, 'bold')).pack(side='left')
    ttk.Label(hdr, text=f"Loan: {lt}    UID: {uid}    Linked records: {len(linked_uids)}", foreground='#666666').pack(side='left', padx=(12,0))

    stats = ttk.Frame(outer)
    stats.pack(fill='x', pady=(0, 6))
    summary_parts = [
        f"Client Changes: {len(client_rows_all)}",
        f"Payments: {len(tx_rows_all)}",
        f"Payment Audit: {len(tx_hist_all)}",
    ]
    if action_counts:
        for k in sorted(action_counts.keys()):
            summary_parts.append(f"{k}: {action_counts[k]}")
    ttk.Label(stats, text="   |   ".join(summary_parts)).pack(anchor='w')

    nb = ttk.Notebook(outer)
    nb.pack(fill='both', expand=True)

    # ---------------- Tab 1: Client Changes ----------------
    tab1 = ttk.Frame(nb, padding=6)
    nb.add(tab1, text="Client Audit")

    t1_filters = ttk.Frame(tab1)
    t1_filters.pack(fill='x')
    ttk.Label(t1_filters, text="Search:").pack(side='left')
    q1 = tk.StringVar()
    ttk.Entry(t1_filters, textvariable=q1, width=34).pack(side='left', padx=(6,12))
    ttk.Label(t1_filters, text="Action:").pack(side='left')
    action_options = ["All"] + sorted(action_counts.keys())
    act1 = tk.StringVar(value="All")
    try:
        ttk.Combobox(t1_filters, textvariable=act1, values=action_options, width=16, state='readonly').pack(side='left', padx=(6,12))
    except Exception:
        ttk.Entry(t1_filters, textvariable=act1, width=16).pack(side='left', padx=(6,12))
    ttk.Label(t1_filters, text="Tip: select a row to see changed fields, before, and after.", foreground='#666666').pack(side='right')

    list_wrap1 = ttk.Frame(tab1)
    list_wrap1.pack(fill='both', expand=True, pady=(6, 0))
    cols1 = ("ts", "action", "loan_type", "source", "fields", "note")
    tree1 = ttk.Treeview(list_wrap1, columns=cols1, show='headings', height=14)
    cfg1 = {
        "ts": (160, 'w', 'When'),
        "action": (95, 'w', 'Action'),
        "loan_type": (85, 'center', 'Loan'),
        "source": (180, 'w', 'Source'),
        "fields": (360, 'w', 'Changed Fields'),
        "note": (220, 'w', 'Note'),
    }
    for c, (w, a, lbl) in cfg1.items():
        tree1.heading(c, text=lbl)
        tree1.column(c, width=w, anchor=a, stretch=(c in ('source', 'fields', 'note')))
    y1 = ttk.Scrollbar(list_wrap1, orient='vertical', command=tree1.yview)
    x1 = ttk.Scrollbar(list_wrap1, orient='horizontal', command=tree1.xview)
    tree1.configure(yscrollcommand=y1.set, xscrollcommand=x1.set)
    tree1.grid(row=0, column=0, sticky='nsew')
    y1.grid(row=0, column=1, sticky='ns')
    x1.grid(row=1, column=0, sticky='ew')
    list_wrap1.grid_rowconfigure(0, weight=1)
    list_wrap1.grid_columnconfigure(0, weight=1)

    for tag, opts in {
        'SNAPSHOT': {'foreground': '#666666'},
        'ADD': {'foreground': '#1f7a1f'},
        'CREATE': {'foreground': '#1f7a1f'},
        'UPDATE': {'foreground': '#0b5fa5'},
        'EDIT': {'foreground': '#0b5fa5'},
        'RENEW': {'foreground': '#8a4b00'},
        'ARCHIVE': {'foreground': '#7a3f00'},
        'RESTORE': {'foreground': '#2f6f3e'},
        'DELETE': {'foreground': '#a11a1a'},
    }.items():
        try:
            tree1.tag_configure(tag, **opts)
        except Exception:
            pass

    lower1 = ttk.PanedWindow(tab1, orient='horizontal')
    lower1.pack(fill='both', expand=True, pady=(8,0))

    def _mk_ro_text(parent):
        frm = ttk.Frame(parent)
        txt = tk.Text(frm, wrap='none', height=12)
        ys = ttk.Scrollbar(frm, orient='vertical', command=txt.yview)
        xs = ttk.Scrollbar(frm, orient='horizontal', command=txt.xview)
        txt.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        txt.grid(row=0, column=0, sticky='nsew')
        ys.grid(row=0, column=1, sticky='ns')
        xs.grid(row=1, column=0, sticky='ew')
        frm.grid_rowconfigure(0, weight=1)
        frm.grid_columnconfigure(0, weight=1)
        return frm, txt

    changed_frm, changed_txt = _mk_ro_text(lower1)
    before_frm, before_txt = _mk_ro_text(lower1)
    after_frm, after_txt = _mk_ro_text(lower1)
    lower1.add(changed_frm, weight=1)
    lower1.add(before_frm, weight=1)
    lower1.add(after_frm, weight=1)

    t1_rows = []

    def _set_ro(widget, content):
        widget.configure(state='normal')
        widget.delete('1.0', 'end')
        widget.insert('1.0', content or '')
        widget.configure(state='disabled')

    def _render_tab1():
        nonlocal t1_rows
        t1_rows = []
        tree1.delete(*tree1.get_children())
        q = (q1.get() or '').strip().lower()
        act_filter = (act1.get() or 'All').strip().upper()
        for r in (client_rows_all or []):
            act = str(r.get('action') or '').strip().upper()
            if act_filter != 'ALL' and act != act_filter:
                continue
            fields = _diff_summary(r.get('before_json') or r.get('old_json'), r.get('after_json') or r.get('new_json'))
            hay = ' '.join([
                str(r.get('ts') or r.get('changed_at') or ''),
                act,
                str(r.get('loan_type_after') or r.get('loan_type_before') or ''),
                str(r.get('source') or ''),
                str(r.get('note') or ''),
                fields,
            ]).lower()
            if q and q not in hay:
                continue
            t1_rows.append(r)
        for i, r in enumerate(t1_rows):
            iid = str(i)
            act = str(r.get('action') or '').strip().upper() or 'UPDATE'
            tree1.insert('', 'end', iid=iid, values=(
                r.get('ts') or r.get('changed_at') or '',
                act,
                r.get('loan_type_after') or r.get('loan_type_before') or '',
                r.get('source') or '',
                _diff_summary(r.get('before_json') or r.get('old_json'), r.get('after_json') or r.get('new_json')),
                r.get('note') or '',
            ), tags=(act,))
        if t1_rows:
            tree1.selection_set('0')
            _on_sel1()
        else:
            _set_ro(changed_txt, '')
            _set_ro(before_txt, '')
            _set_ro(after_txt, '')

    def _on_sel1(_=None):
        sel = tree1.selection()
        if not sel:
            return
        i = int(sel[0])
        if i < 0 or i >= len(t1_rows):
            return
        r = t1_rows[i]
        pairs = _diff_pairs(r.get('before_json') or r.get('old_json'), r.get('after_json') or r.get('new_json'))
        if not pairs:
            detail_lines = ["No field-level difference recorded."]
        else:
            detail_lines = []
            for k, ov, nv in pairs:
                detail_lines.append(f"{k}\n  Before: {_fmt_scalar(ov)}\n  After : {_fmt_scalar(nv)}")
        _set_ro(changed_txt, "\n\n".join(detail_lines))
        _set_ro(before_txt, _pretty(r.get('before_json') or r.get('old_json')))
        _set_ro(after_txt, _pretty(r.get('after_json') or r.get('new_json')))

    tree1.bind('<<TreeviewSelect>>', _on_sel1)
    q1.trace_add('write', lambda *_: _render_tab1())
    act1.trace_add('write', lambda *_: _render_tab1())
    _render_tab1()

    # ---------------- Tab 2: Payments ----------------
    tab2 = ttk.Frame(nb, padding=6)
    nb.add(tab2, text="Payments")

    t2_top = ttk.Frame(tab2)
    t2_top.pack(fill='x')
    ttk.Label(t2_top, text="Search:").pack(side='left')
    q2 = tk.StringVar()
    ttk.Entry(t2_top, textvariable=q2, width=34).pack(side='left', padx=(6,12))
    ttk.Label(t2_top, text="From:").pack(side='left')
    from_v = tk.StringVar()
    ttk.Entry(t2_top, textvariable=from_v, width=12).pack(side='left', padx=(6,8))
    ttk.Label(t2_top, text="To:").pack(side='left')
    to_v = tk.StringVar()
    ttk.Entry(t2_top, textvariable=to_v, width=12).pack(side='left', padx=(6,12))
    ttk.Label(t2_top, text=f"Rows: {len(tx_rows_all)}", foreground='#666666').pack(side='right')

    list_wrap2 = ttk.Frame(tab2)
    list_wrap2.pack(fill='both', expand=True, pady=(6,0))
    cols2 = ('date', 'loan_type', 'name', 'payment', 'description')
    tree2 = ttk.Treeview(list_wrap2, columns=cols2, show='headings', height=18)
    cfg2 = {
        'date': (110, 'w', 'Date'),
        'loan_type': (90, 'center', 'Loan'),
        'name': (220, 'w', 'Name'),
        'payment': (100, 'e', 'Payment'),
        'description': (520, 'w', 'Description'),
    }
    for c, (w, a, lbl) in cfg2.items():
        tree2.heading(c, text=lbl)
        tree2.column(c, width=w, anchor=a, stretch=(c in ('name','description')))
    y2 = ttk.Scrollbar(list_wrap2, orient='vertical', command=tree2.yview)
    x2 = ttk.Scrollbar(list_wrap2, orient='horizontal', command=tree2.xview)
    tree2.configure(yscrollcommand=y2.set, xscrollcommand=x2.set)
    tree2.grid(row=0, column=0, sticky='nsew')
    y2.grid(row=0, column=1, sticky='ns')
    x2.grid(row=1, column=0, sticky='ew')
    list_wrap2.grid_rowconfigure(0, weight=1)
    list_wrap2.grid_columnconfigure(0, weight=1)

    t2_rows = []

    def _in_date_range(ds):
        ds = (ds or '').strip()
        if not ds:
            return True
        f = (from_v.get() or '').strip()
        t = (to_v.get() or '').strip()
        if f and ds < f:
            return False
        if t and ds > t:
            return False
        return True

    def _render_tab2():
        nonlocal t2_rows
        t2_rows = []
        tree2.delete(*tree2.get_children())
        q = (q2.get() or '').strip().lower()
        for r in (tx_rows_all or []):
            dt = str(r.get('date') or '')
            if not _in_date_range(dt):
                continue
            pay = float(r.get('payment') or 0)
            rowtxt = ' '.join([dt, str(r.get('loan_type') or ''), str(r.get('name') or ''), str(pay), str(r.get('description') or '')]).lower()
            if q and q not in rowtxt:
                continue
            t2_rows.append(r)
        total_pay = sum(float(r.get('payment') or 0) for r in t2_rows)
        for i, r in enumerate(t2_rows):
            tree2.insert('', 'end', iid=str(i), values=(
                r.get('date') or '',
                r.get('loan_type') or '',
                r.get('name') or '',
                f"{float(r.get('payment') or 0):,.2f}",
                r.get('description') or '',
            ))
        try:
            tree2.heading('payment', text=f"Payment (Σ {total_pay:,.2f})")
        except Exception:
            pass

    q2.trace_add('write', lambda *_: _render_tab2())
    from_v.trace_add('write', lambda *_: _render_tab2())
    to_v.trace_add('write', lambda *_: _render_tab2())
    _render_tab2()

    # ---------------- Tab 3: Payment Audit ----------------
    tab3 = ttk.Frame(nb, padding=6)
    nb.add(tab3, text="Payment Audit")

    t3_top = ttk.Frame(tab3)
    t3_top.pack(fill='x')
    ttk.Label(t3_top, text="Search:").pack(side='left')
    q3 = tk.StringVar()
    ttk.Entry(t3_top, textvariable=q3, width=34).pack(side='left', padx=(6,12))
    ttk.Label(t3_top, text=f"Rows: {len(tx_hist_all)}", foreground='#666666').pack(side='right')

    list_wrap3 = ttk.Frame(tab3)
    list_wrap3.pack(fill='both', expand=True, pady=(6,0))
    cols3 = ('ts', 'action', 'source', 'date', 'loan_type', 'note')
    tree3 = ttk.Treeview(list_wrap3, columns=cols3, show='headings', height=12)
    cfg3 = {
        'ts': (160, 'w', 'When'),
        'action': (95, 'w', 'Action'),
        'source': (220, 'w', 'Source'),
        'date': (110, 'w', 'Date'),
        'loan_type': (90, 'center', 'Loan'),
        'note': (280, 'w', 'Note'),
    }
    for c, (w, a, lbl) in cfg3.items():
        tree3.heading(c, text=lbl)
        tree3.column(c, width=w, anchor=a, stretch=(c in ('source','note')))
    y3 = ttk.Scrollbar(list_wrap3, orient='vertical', command=tree3.yview)
    x3 = ttk.Scrollbar(list_wrap3, orient='horizontal', command=tree3.xview)
    tree3.configure(yscrollcommand=y3.set, xscrollcommand=x3.set)
    tree3.grid(row=0, column=0, sticky='nsew')
    y3.grid(row=0, column=1, sticky='ns')
    x3.grid(row=1, column=0, sticky='ew')
    list_wrap3.grid_rowconfigure(0, weight=1)
    list_wrap3.grid_columnconfigure(0, weight=1)

    for tag, opts in {
        'ADD': {'foreground': '#1f7a1f'},
        'UPDATE': {'foreground': '#0b5fa5'},
        'EDIT': {'foreground': '#0b5fa5'},
        'DELETE': {'foreground': '#a11a1a'},
    }.items():
        try:
            tree3.tag_configure(tag, **opts)
        except Exception:
            pass

    pan3 = ttk.PanedWindow(tab3, orient='horizontal')
    pan3.pack(fill='both', expand=True, pady=(8,0))
    old3_frm, old3 = _mk_ro_text(pan3)
    new3_frm, new3 = _mk_ro_text(pan3)
    pan3.add(old3_frm, weight=1)
    pan3.add(new3_frm, weight=1)

    t3_rows = []

    def _render_tab3():
        nonlocal t3_rows
        t3_rows = []
        tree3.delete(*tree3.get_children())
        q = (q3.get() or '').strip().lower()
        for r in (tx_hist_all or []):
            hay = ' '.join([
                str(r.get('ts') or r.get('changed_at') or ''),
                str(r.get('action') or ''),
                str(r.get('source') or ''),
                str(r.get('date') or ''),
                str(r.get('loan_type') or ''),
                str(r.get('note') or ''),
            ]).lower()
            if q and q not in hay:
                continue
            t3_rows.append(r)
        for i, r in enumerate(t3_rows):
            act = str(r.get('action') or '').strip().upper() or 'UPDATE'
            tree3.insert('', 'end', iid=str(i), values=(
                r.get('ts') or r.get('changed_at') or '',
                act,
                r.get('source') or '',
                r.get('date') or '',
                r.get('loan_type') or '',
                r.get('note') or '',
            ), tags=(act,))
        if t3_rows:
            tree3.selection_set('0')
            _on_sel3()
        else:
            _set_ro(old3, '')
            _set_ro(new3, '')

    def _on_sel3(_=None):
        sel = tree3.selection()
        if not sel:
            return
        i = int(sel[0])
        if i < 0 or i >= len(t3_rows):
            return
        r = t3_rows[i]
        _set_ro(old3, _pretty(r.get('before_json') or r.get('old_json')))
        _set_ro(new3, _pretty(r.get('after_json') or r.get('new_json')))

    tree3.bind('<<TreeviewSelect>>', _on_sel3)
    q3.trace_add('write', lambda *_: _render_tab3())
    _render_tab3()
