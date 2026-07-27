"""Data Bank month navigation and grid presentation extracted in Wave 59."""
from __future__ import annotations

_DATABANK_GRID_DEPENDENCIES = {}
_PROTECTED_GLOBALS = {'__file__', '__builtins__', '_PROTECTED_GLOBALS', '__cached__', 'DATABANK_GRID_PRESENTATION_METHODS', 'goto_current_month', 'next_month', '__name__', '__package__', '__spec__', '__loader__', 'configure_databank_grid_dependencies', 'prev_month', 'refresh_data_grid', '__doc__', '_DATABANK_GRID_DEPENDENCIES'}

def configure_databank_grid_dependencies(namespace):
    _DATABANK_GRID_DEPENDENCIES.clear()
    _DATABANK_GRID_DEPENDENCIES.update(namespace)
    for name, value in namespace.items():
        if name not in _PROTECTED_GLOBALS:
            globals()[name] = value

DATABANK_GRID_PRESENTATION_METHODS = {'goto_current_month': {'lines': 5, 'source_sha256': '42ecd7e7b76492b3e568621109b166249426f32199a9ed8d3c3966b7f9d44a96', 'dedented_sha256': '478fd8e11b972e47656ed78794331548073c07d8c4de26bd42c55fef371e4cf1', 'signature': 'self', 'calls': ['date.today', 'self.refresh_data_grid'], 'db_calls': []}, 'prev_month': {'lines': 4, 'source_sha256': 'e0b005e9000e608a411637ef7996cbd886c0d11babfad98f3679cb68ad217753', 'dedented_sha256': 'ffb617393a0c9f736fa0ff95512ad908464b754e0c83e17fc4cab7eef7dd15d3', 'signature': 'self', 'calls': ['self._month_label', 'self.month_lbl.config', 'self.refresh_data_grid'], 'db_calls': []}, 'next_month': {'lines': 4, 'source_sha256': '7e03166f967729a5f940e707332ce385e194f07c6f3a119bfd4ed9f48bfab41b', 'dedented_sha256': '2d3727c306f3be2a4229dde2808e6a5d219fc70bc22a2d2af9b849e80ee843f5', 'signature': 'self', 'calls': ['self._month_label', 'self.month_lbl.config', 'self.refresh_data_grid'], 'db_calls': []}, 'refresh_data_grid': {'lines': 271, 'source_sha256': 'e3ecfaae3f958c4d06ac7aa75b41ab5f0f0ab027b2dcc58dafa9e197779b31aa', 'dedented_sha256': 'a3e7d1d4fe903e20d1141aa0ecdf77497aabd88f3083b804b0902e41d9741b31', 'signature': 'self', 'calls': ['_log_ignored', '_log_suppressed_once', '_sync_selection', 'c.get', 'calendar.monthrange', 'date', 'enumerate', 'float', 'fmt_currency', 'from_tv.selection', 'grid.grid', 'grid.grid_columnconfigure', 'grid.grid_rowconfigure', 'h.grid', 'hasattr', 'info.get', 'int', 'isinstance', 'len', 'range', 'self._configure_tree_stripes', 'self._db_menu.add_command', 'self._db_menu.add_separator', 'self._db_menu.grab_release', 'self._db_menu.tk_popup', 'self._db_rows_var.set', 'self._ensure_databank_edit_bindings', 'self._mode_filter', 'self._month_label', 'self._remember_cell_click', 'self._resize_databank_columns', 'self._update_data_toolbar', 'self.days_tree.bind', 'self.days_tree.column', 'self.days_tree.configure', 'self.days_tree.focus', 'self.days_tree.grid', 'self.days_tree.heading', 'self.days_tree.identify_row', 'self.days_tree.insert', 'self.days_tree.selection_set', 'self.days_tree.yview', 'self.db.get_all_clients', 'self.db.get_client_info', 'self.db.get_transaction', 'self.inner.bind', 'self.inner.grid_columnconfigure', 'self.inner.grid_rowconfigure', 'self.inner.winfo_children', 'self.name_tree.bind', 'self.name_tree.column', 'self.name_tree.configure', 'self.name_tree.focus', 'self.name_tree.grid', 'self.name_tree.heading', 'self.name_tree.identify_row', 'self.name_tree.insert', 'self.name_tree.selection_set', 'self.name_tree.yview', 'self.root.bell', 'self.search_db_var.get', 'self.status_var.set', 'str', 'strftime', 'strip', 'tk.Menu', 'to_tv.focus', 'to_tv.selection', 'to_tv.selection_set', 'ttk.Frame', 'ttk.Scrollbar', 'ttk.Treeview', 'tuple', 'tv.bind', 'v.grid', 'vals.append', 'w.destroy'], 'db_calls': ['self.db.get_all_clients', 'self.db.get_client_info', 'self.db.get_transaction']}}

def goto_current_month(self):
    today = date.today()
    self.grid_year = today.year
    self.grid_month = today.month
    self.refresh_data_grid()

def prev_month(self):
    if self.grid_month == 1: self.grid_month = 12; self.grid_year -= 1
    else: self.grid_month -= 1
    self.month_lbl.config(text=self._month_label()); self.refresh_data_grid()

def next_month(self):
    if self.grid_month == 12: self.grid_month = 1; self.grid_year += 1
    else: self.grid_month += 1
    self.month_lbl.config(text=self._month_label()); self.refresh_data_grid()

def refresh_data_grid(self):

    # View-only reminder
    try:
        self.status_var.set('Data Bank is view-only. Encode in Excel, then Import.')
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_0380', 'suppressed exception excpass_0380', __spina_exc)
        pass

    # Clear container
    for w in self.inner.winfo_children():
        try:
            w.destroy()
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0381', 'suppressed exception excpass_0381', __spina_exc)
            pass

    days = calendar.monthrange(self.grid_year, self.grid_month)[1]
    day_cols = tuple(f'd{d}' for d in range(1, days + 1))
    cols = ('client', 'area') + day_cols

    # --- Freeze panes layout: left (client+area) + right (days) ---
    grid = ttk.Frame(self.inner)
    grid.grid(row=0, column=0, sticky='nsew')
    try:
        self.inner.grid_rowconfigure(0, weight=1)
        self.inner.grid_columnconfigure(0, weight=1)
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_0382', 'suppressed exception excpass_0382', __spina_exc)
        pass
    grid.grid_rowconfigure(0, weight=1)
    grid.grid_columnconfigure(1, weight=1)

    # Left pane: Client + Area (no horizontal scroll)
    self.name_tree = ttk.Treeview(grid, columns=('client', 'area'), show='headings', height=27)
    self._configure_tree_stripes(self.name_tree)
    self.name_tree.heading('client', text='Client Name')
    self.name_tree.heading('area', text='Area')
    self.name_tree.column('client', width=280, anchor='w', stretch=False)
    self.name_tree.column('area', width=150, anchor='w', stretch=False)

    # Right pane: Days (with horizontal scroll); keep hidden 'client'/'area' columns for existing logic
    self.days_tree = ttk.Treeview(grid, columns=cols, show='headings', height=27)
    self._configure_tree_stripes(self.days_tree)

    # Hidden columns to keep column indices stable (day1 starts at #3)
    self.days_tree.heading('client', text='')
    self.days_tree.heading('area', text='')
    self.days_tree.column('client', width=0, minwidth=0, stretch=False)
    self.days_tree.column('area', width=0, minwidth=0, stretch=False)

    for c in day_cols:
        d = int(c[1:])
        self.days_tree.heading(c, text=str(d))
        self.days_tree.column(c, width=72, anchor='center', stretch=False)

    # Scrollbars (shared vertical)
    def _yview(*args):
        try:
            self.name_tree.yview(*args)
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0383', 'suppressed exception excpass_0383', __spina_exc)
            pass
        try:
            self.days_tree.yview(*args)
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0384', 'suppressed exception excpass_0384', __spina_exc)
            pass

    v = ttk.Scrollbar(grid, orient='vertical', command=_yview)
    h = ttk.Scrollbar(grid, orient='horizontal', command=self.days_tree.xview)

    self.name_tree.configure(yscrollcommand=v.set)
    self.days_tree.configure(yscrollcommand=v.set, xscrollcommand=h.set)

    # Layout
    self.name_tree.grid(row=0, column=0, sticky='ns')
    self.days_tree.grid(row=0, column=1, sticky='nsew')
    v.grid(row=0, column=2, sticky='ns')
    h.grid(row=1, column=1, sticky='ew')

    # Sync selection between panes
    def _sync_selection(from_tv, to_tv):
        try:
            sel = from_tv.selection()
            if not sel:
                return
            if to_tv.selection() != sel:
                to_tv.selection_set(sel)
            try:
                to_tv.focus(sel[0])
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_0385', 'suppressed exception excpass_0385', __spina_exc)
                pass
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0386', 'suppressed exception excpass_0386', __spina_exc)
            pass

    def _on_sel_left(_e=None):
        _sync_selection(self.name_tree, self.days_tree)

    def _on_sel_right(_e=None):
        _sync_selection(self.days_tree, self.name_tree)

    try:
        self.name_tree.bind('<<TreeviewSelect>>', _on_sel_left, add='+')
        self.days_tree.bind('<<TreeviewSelect>>', _on_sel_right, add='+')
    except Exception as e:
        _log_ignored("ui.bind failed", e, key="ui.bind_failed")

    # Ensure clicks set focus on the right pane so Delete / edit hotkeys work naturally
    def _focus_right_from_left(e):
        try:
            iid = self.name_tree.identify_row(e.y)
            if iid:
                self.days_tree.selection_set((iid,))
                self.days_tree.focus(iid)
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0387', 'suppressed exception excpass_0387', __spina_exc)
            pass

    def _focus_left_from_right(e):
        try:
            iid = self.days_tree.identify_row(e.y)
            if iid:
                self.name_tree.selection_set((iid,))
                self.name_tree.focus(iid)
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0388', 'suppressed exception excpass_0388', __spina_exc)
            pass

    try:
        self.name_tree.bind('<Button-1>', _focus_right_from_left, add='+')
        self.days_tree.bind('<Button-1>', _focus_left_from_right, add='+')
    except Exception as e:
        _log_ignored("ui.bind failed", e, key="ui.bind_failed")

    # Bindings (always bind to the current widgets; they are recreated on refresh)
    try:
        self.days_tree.bind('<Double-1>', self._begin_cell_edit, add='+')
    except Exception:
        # If _begin_cell_edit was removed, just bell
        try:
            self.days_tree.bind('<Double-1>', lambda e: self.root.bell(), add='+')
        except Exception as e:
            _log_ignored("ui.bind failed", e, key="ui.bind_failed")

    try:
        self.days_tree.bind('<Button-1>', self._remember_cell_click, add='+')
    except Exception as e:
        _log_ignored("ui.bind failed", e, key="ui.bind_failed")

    try:
        self.days_tree.bind('<Delete>', self.delete_selected_cell, add='+')
        self.name_tree.bind('<Delete>', self.delete_selected_cell, add='+')
    except Exception as e:
        _log_ignored("ui.bind failed", e, key="ui.bind_failed")

    # Mousewheel should scroll both panes
    try:
        for tv in (self.name_tree, self.days_tree):
            tv.bind('<MouseWheel>', self._on_mousewheel_sync, add='+')
            tv.bind('<Button-4>', self._on_mousewheel_sync, add='+')
            tv.bind('<Button-5>', self._on_mousewheel_sync, add='+')
    except Exception as e:
        _log_ignored("ui.bind failed", e, key="ui.bind_failed")

    # Right-click context menu: mark missed with reason
    try:
        self._db_menu = tk.Menu(self.days_tree, tearoff=0)
        self._db_menu.add_command(label="Mark as missed (enter reason)", command=self._mark_missed_for_selected)
        self._db_menu.add_separator()
        self._db_menu.add_command(label="Delete this payment cell", command=self.delete_selected_cell)

        def _popup_db_menu(ev):
            try:
                self._remember_cell_click(ev)
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_0389', 'suppressed exception excpass_0389', __spina_exc)
                pass
            try:
                self._db_menu.tk_popup(ev.x_root, ev.y_root)
            finally:
                try:
                    self._db_menu.grab_release()
                except Exception as __spina_exc:
                    _log_suppressed_once('excpass_0390', 'suppressed exception excpass_0390', __spina_exc)
                    pass

        self.days_tree.bind("<Button-3>", _popup_db_menu, add="+")
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_0391', 'suppressed exception excpass_0391', __spina_exc)
        pass

    # Resize columns when container changes
    try:
        self.inner.bind('<Configure>', self._resize_databank_columns, add='+')
    except Exception as e:
        _log_ignored("ui.bind failed", e, key="ui.bind_failed")

    # Fill rows
    search_term = self.search_db_var.get().strip()
    clients = self.db.get_all_clients(search=search_term if search_term else None, loan_type=self._mode_filter(), search_by='all')
    try:
        mode_txt = self._mode_filter()
    except Exception:
        mode_txt = 'Regular'
    try:
        rows_txt = f"{len(clients or [])} row{'s' if len(clients or []) != 1 else ''} • {mode_txt} • {self._month_label()}"
        if search_term:
            rows_txt += f" • filter: {search_term}"
        if hasattr(self, '_db_rows_var') and self._db_rows_var is not None:
            self._db_rows_var.set(rows_txt)
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_databank_rows_var', 'suppressed exception excpass_databank_rows_var', __spina_exc)
        pass
    if not clients:
        iid = 'r0'
        self.name_tree.insert('', 'end', iid=iid, values=('(no clients)', ''), tags=('odd',))
        self.days_tree.insert('', 'end', iid=iid, values=('(no clients)', '', *(['']*days)), tags=('odd',))
    else:
        for idx, c in enumerate(clients):
            if isinstance(c, dict):
                name = c.get('name','')
                area = c.get('area','')
            else:
                info = self.db.get_client_info(c, loan_type=self._mode_filter()) or {}
                name = c
                area = info.get('area','')

            vals = [name, area]
            for d in range(1, days + 1):
                dt = date(self.grid_year, self.grid_month, d).strftime('%Y-%m-%d')
                tx = self.db.get_transaction(name, dt)
                if tx and tx['payment'] and float(tx['payment']) != 0:
                    vals.append(fmt_currency(tx['payment']))
                elif tx and (tx['payment'] == 0 or tx['payment'] == '0'):
                    vals.append('0')
                else:
                    vals.append('')

            tag = 'odd' if (idx % 2) == 0 else 'even'
            iid = f"r{idx}"
            try:
                self.name_tree.insert('', 'end', iid=iid, values=(name, area), tags=(tag,))
            except Exception:
                self.name_tree.insert('', 'end', values=(name, area), tags=(tag,))
            try:
                self.days_tree.insert('', 'end', iid=iid, values=tuple(vals), tags=(tag,))
            except Exception:
                self.days_tree.insert('', 'end', values=tuple(vals), tags=(tag,))

    # Update sizes / toolbar safely
    try:
        self._resize_databank_columns()
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_0392', 'suppressed exception excpass_0392', __spina_exc)
        pass

    try:
        if hasattr(self, '_update_data_toolbar'):
            self._update_data_toolbar()
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_0393', 'suppressed exception excpass_0393', __spina_exc)
        pass

    try:
        self._ensure_databank_edit_bindings()
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_0394', 'suppressed exception excpass_0394', __spina_exc)
        pass
