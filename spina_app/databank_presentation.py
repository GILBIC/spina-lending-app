"""Data Bank presentation extracted in Wave 49."""
from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk

_DATABANK_PRESENTATION_DEPENDENCIES = {}
_PROTECTED_GLOBALS = {
    "__builtins__", "__cached__", "__doc__", "__file__", "__loader__",
    "__name__", "__package__", "__spec__", "os", "tk", "ttk",
    "_DATABANK_PRESENTATION_DEPENDENCIES", "_PROTECTED_GLOBALS",
    "configure_databank_presentation_dependencies",
    "DATABANK_PRESENTATION_TARGETS", "DATABANK_PRESENTATION_SOURCE_LINES",
    "DATABANK_PRESENTATION_SOURCE_SHA256", "DATABANK_PRESENTATION_SIGNATURES",
    "DATABANK_PRESENTATION_CALLS", "DATABANK_PRESENTATION_TOTAL_SOURCE_LINES",
    "_spina_v15_palette", "_spina_v15_setup_databank_styles",
    "_spina_v15_stat_card", "_spina_v15_build_data_tab",
    "_spina_v15_update_databank_cards", "_spina_v15_refresh_data_grid",
    "_spina_v15_update_data_toolbar", "_spina_v15_apply_ui_theme",
    "_spina_v16_apply_bigger_payment_grid", "_spina_v16_refresh_data_grid",
}


def configure_databank_presentation_dependencies(namespace):
    _DATABANK_PRESENTATION_DEPENDENCIES.clear()
    _DATABANK_PRESENTATION_DEPENDENCIES.update(namespace)
    for name, value in namespace.items():
        if name not in _PROTECTED_GLOBALS:
            globals()[name] = value

DATABANK_PRESENTATION_TARGETS = ['_spina_v15_palette', '_spina_v15_setup_databank_styles', '_spina_v15_stat_card', '_spina_v15_build_data_tab', '_spina_v15_update_databank_cards', '_spina_v15_refresh_data_grid', '_spina_v15_update_data_toolbar', '_spina_v15_apply_ui_theme', '_spina_v16_apply_bigger_payment_grid', '_spina_v16_refresh_data_grid']
DATABANK_PRESENTATION_SOURCE_LINES = {'_spina_v15_palette': 17, '_spina_v15_setup_databank_styles': 48, '_spina_v15_stat_card': 5, '_spina_v15_build_data_tab': 136, '_spina_v15_update_databank_cards': 39, '_spina_v15_refresh_data_grid': 18, '_spina_v15_update_data_toolbar': 7, '_spina_v15_apply_ui_theme': 11, '_spina_v16_apply_bigger_payment_grid': 21, '_spina_v16_refresh_data_grid': 7}
DATABANK_PRESENTATION_SOURCE_SHA256 = {'_spina_v15_palette': 'a3f62850e60b84110fe96e601061be175730d07a7df1a273c64a2628a49eb037', '_spina_v15_setup_databank_styles': '55f92454aaf29af7e5f2a8995769ff109a9153c50835132a337bac5e86248212', '_spina_v15_stat_card': '44552d9fec3486c45f7e5f56aed237dd3cf035bd55ae0219b7f34cd46ad75657', '_spina_v15_build_data_tab': '06715b426fc112b66bf2cfca76ed844f7b5544276d6e9c867b6656e6b2c211ad', '_spina_v15_update_databank_cards': 'ceaf5045cfade6235e8acfceee400ddf2211b89f09e364d257938fbc543e1780', '_spina_v15_refresh_data_grid': '8c2bc3d43da89ca2f770f5f03c5af71356d38cb2d32eac1cce72a0c27b4b0441', '_spina_v15_update_data_toolbar': '567bf6416e53cc0e9543227e37540d07308a43e192a2495e09693580ebef6632', '_spina_v15_apply_ui_theme': 'cf7b8980b2617457ff3d40aa543c1c0f80cbfe60c951611fe3cf2beedc52ac9a', '_spina_v16_apply_bigger_payment_grid': '38daa05d54931f818a0252ec98bb84d8fd92aec332f7cd3aa87cfeacac9c6d97', '_spina_v16_refresh_data_grid': '0de5180c884ed6c8c2e6168efe7a8d8d4891b738f17ba1b9cbd404108e6e82ff'}
DATABANK_PRESENTATION_SIGNATURES = {'_spina_v15_palette': 'self', '_spina_v15_setup_databank_styles': 'self', '_spina_v15_stat_card': 'parent, title, textvar', '_spina_v15_build_data_tab': 'self', '_spina_v15_update_databank_cards': 'self', '_spina_v15_refresh_data_grid': 'self, *args, **kwargs', '_spina_v15_update_data_toolbar': 'self, *args, **kwargs', '_spina_v15_apply_ui_theme': 'self, *args, **kwargs', '_spina_v16_apply_bigger_payment_grid': 'self', '_spina_v16_refresh_data_grid': 'self, *args, **kwargs'}
DATABANK_PRESENTATION_CALLS = {'_spina_v15_palette': ['getattr', 'isinstance', 'lower', 'self._theme_palette', 'startswith', 'str'], '_spina_v15_setup_databank_styles': ['_log_suppressed_once', '_spina_v15_palette', 'getattr', 'lower', 'p.get', 'st.configure', 'st.map', 'startswith', 'str', 'ttk.Style'], '_spina_v15_stat_card': ['pack', 'ttk.Frame', 'ttk.Label'], '_spina_v15_build_data_tab': ['_spina_v15_palette', '_spina_v15_setup_databank_styles', '_spina_v15_stat_card', '_spina_v15_update_databank_cards', 'actions.pack', 'body_card.pack', 'c.grid', 'child.destroy', 'enumerate', 'frm.configure', 'frm.winfo_children', 'getattr', 'grid_head.pack', 'hasattr', 'header.pack', 'left.pack', 'left_actions.pack', 'lower', 'nav.pack', 'nav_row.pack', 'p.get', 'pack', 'page.pack', 'range', 'right_actions.pack', 'search_box.pack', 'search_row.pack', 'self._mode_filter', 'self._month_label', 'self._update_data_toolbar', 'self.db_search_entry.bind', 'self.db_search_entry.pack', 'self.inner.pack', 'self.month_lbl.pack', 'self.refresh_data_grid', 'self.search_db_var.set', 'self.search_db_var.trace_add', 'startswith', 'stats.grid_columnconfigure', 'stats.pack', 'str', 'tk.StringVar', 'ttk.Button', 'ttk.Entry', 'ttk.Frame', 'ttk.Label'], '_spina_v15_update_databank_cards': ['_log_suppressed_once', 'get', 'getattr', 'hasattr', 'self._db_card_clients_var.set', 'self._db_card_close_var.set', 'self._db_card_month_var.set', 'self._db_card_view_var.set', 'self._mode_filter', 'self._month_label', 'str', 'strip', 'tv.get_children', 'tv.item'], '_spina_v15_refresh_data_grid': ['_spina_v15_orig_refresh_data_grid', '_spina_v15_setup_databank_styles', '_spina_v15_update_databank_cards', 'getattr', 'self.days_tree.configure', 'self.name_tree.configure'], '_spina_v15_update_data_toolbar': ['_spina_v15_orig_update_data_toolbar', '_spina_v15_update_databank_cards'], '_spina_v15_apply_ui_theme': ['_spina_v15_orig_apply_theme', '_spina_v15_setup_databank_styles', '_spina_v15_update_databank_cards'], '_spina_v16_apply_bigger_payment_grid': ['_spina_v15_setup_databank_styles', 'getattr', 'self.days_tree.column', 'self.days_tree.configure', 'self.name_tree.column', 'self.name_tree.configure', 'startswith', 'str'], '_spina_v16_refresh_data_grid': ['_spina_v16_apply_bigger_payment_grid', '_spina_v16_prev_refresh_data_grid']}
DATABANK_PRESENTATION_TOTAL_SOURCE_LINES = 309

def _spina_v15_palette(self):
        try:
            p = getattr(self, '_ui_colors', None) or self._theme_palette()
            if isinstance(p, dict):
                return p
        except Exception:
            pass
        is_dark = str(getattr(self, 'ui_theme', 'dark')).lower().startswith('d')
        return {
            'bg': '#111217' if is_dark else '#f6f7fb',
            'panel': '#181a20' if is_dark else '#ffffff',
            'fg': '#ffffff' if is_dark else '#17181c',
            'muted': '#a9a9b3' if is_dark else '#6b7280',
            'accent': '#ffd1e6' if is_dark else '#ffd1e6',
            'border': '#30323a' if is_dark else '#e5e7eb',
            'button_active': '#2a2d36' if is_dark else '#f3f4f6',
        }

def _spina_v15_setup_databank_styles(self):
        try:
            st = ttk.Style()
            p = _spina_v15_palette(self)
            is_dark = str(getattr(self, 'ui_theme', 'dark')).lower().startswith('d')
            bg = p.get('bg', '#111217' if is_dark else '#f6f7fb')
            panel = p.get('panel', '#181a20' if is_dark else '#ffffff')
            fg = p.get('fg', '#ffffff' if is_dark else '#17181c')
            muted = p.get('muted', '#a9a9b3' if is_dark else '#6b7280')
            border = p.get('border', '#30323a' if is_dark else '#e5e7eb')
            accent = p.get('accent', '#ffd1e6')
            active = p.get('button_active', '#2a2d36' if is_dark else '#f3f4f6')
            family = 'Segoe UI' if os.name == 'nt' else 'TkDefaultFont'

            st.configure('DataBank.Page.TFrame', background=bg)
            st.configure('DataBank.Card.TFrame', background=panel, relief='flat')
            st.configure('DataBank.Inner.TFrame', background=panel)
            st.configure('DataBank.Title.TLabel', background=panel, foreground=fg, font=(family, 18, 'bold'))
            st.configure('DataBank.Subtitle.TLabel', background=panel, foreground=muted, font=(family, 9))
            st.configure('DataBank.Label.TLabel', background=panel, foreground=fg, font=(family, 10, 'bold'))
            st.configure('DataBank.Muted.TLabel', background=panel, foreground=muted, font=(family, 9))
            st.configure('DataBank.StatTitle.TLabel', background=panel, foreground=muted, font=(family, 8, 'bold'))
            st.configure('DataBank.StatValue.TLabel', background=panel, foreground=fg, font=(family, 12, 'bold'))
            st.configure('DataBank.Pill.TLabel', background=active, foreground=fg, font=(family, 9, 'bold'), padding=(10, 5))
            st.configure('DataBank.Treeview',
                         background=panel,
                         fieldbackground=panel,
                         foreground=fg,
                         rowheight=34,
                         borderwidth=0,
                         relief='flat',
                         font=(family, 10))
            st.configure('DataBank.Treeview.Heading',
                         background=active,
                         foreground=fg,
                         relief='flat',
                         font=(family, 10, 'bold'))
            try:
                st.map('DataBank.Treeview',
                       background=[('selected', accent if not is_dark else '#3c4451')],
                       foreground=[('selected', '#111217' if not is_dark else '#ffffff')])
            except Exception:
                pass
        except Exception as __spina_exc:
            try:
                _log_suppressed_once('v15_databank_styles', 'modern databank style failed', __spina_exc)
            except Exception:
                pass

def _spina_v15_stat_card(parent, title, textvar):
        card = ttk.Frame(parent, style='DataBank.Card.TFrame', padding=(14, 10))
        ttk.Label(card, text=title, style='DataBank.StatTitle.TLabel').pack(anchor='w')
        ttk.Label(card, textvariable=textvar, style='DataBank.StatValue.TLabel').pack(anchor='w', pady=(4, 0))
        return card

def _spina_v15_build_data_tab(self):
        """Modern Data Bank page: card header, fast search, summary cards, grouped actions, same grid logic."""
        frm = self.tab_data
        try:
            for child in frm.winfo_children():
                child.destroy()
        except Exception:
            pass

        _spina_v15_setup_databank_styles(self)
        p = _spina_v15_palette(self)
        is_dark = str(getattr(self, 'ui_theme', 'dark')).lower().startswith('d')
        bg = p.get('bg', '#111217' if is_dark else '#f6f7fb')
        panel = p.get('panel', '#181a20' if is_dark else '#ffffff')
        fg = p.get('fg', '#ffffff' if is_dark else '#17181c')
        muted = p.get('muted', '#a9a9b3' if is_dark else '#6b7280')
        border = p.get('border', '#30323a' if is_dark else '#e5e7eb')
        family = 'Segoe UI' if os.name == 'nt' else 'TkDefaultFont'

        try:
            frm.configure(style='DataBank.Page.TFrame')
        except Exception:
            pass

        page = ttk.Frame(frm, style='DataBank.Page.TFrame', padding=(14, 12, 14, 12))
        page.pack(fill='both', expand=True)

        # Header card
        header = ttk.Frame(page, style='DataBank.Card.TFrame', padding=(16, 14, 16, 14))
        header.pack(fill='x', pady=(0, 12))
        try:
            # subtle card border using tk frame behind ttk contents is avoided for theme safety
            pass
        except Exception:
            pass

        left = ttk.Frame(header, style='DataBank.Card.TFrame')
        left.pack(side='left', fill='x', expand=True)
        ttk.Label(left, text='Data Bank', style='DataBank.Title.TLabel').pack(anchor='w')
        ttk.Label(left, text='Monthly payment ledger • view-only grid • import entries from Excel/JSONL', style='DataBank.Subtitle.TLabel').pack(anchor='w', pady=(2, 0))

        # Search area
        search_box = ttk.Frame(header, style='DataBank.Card.TFrame')
        search_box.pack(side='left', padx=(16, 0), fill='x')
        self.search_db_var = tk.StringVar()
        ttk.Label(search_box, text='Search client / area', style='DataBank.Label.TLabel').pack(anchor='w')
        search_row = ttk.Frame(search_box, style='DataBank.Card.TFrame')
        search_row.pack(fill='x', pady=(5, 0))
        self.db_search_entry = ttk.Entry(search_row, textvariable=self.search_db_var, width=34)
        self.db_search_entry.pack(side='left', ipady=3)
        ttk.Button(search_row, text='Clear', command=lambda: self.search_db_var.set('')).pack(side='left', padx=(6, 0))
        self.search_db_var.trace_add('write', lambda *_: self.refresh_data_grid())
        try:
            self.db_search_entry.bind('<Return>', lambda *_: self.refresh_data_grid(), add='+')
            self.db_search_entry.bind('<Escape>', lambda *_: self.search_db_var.set(''), add='+')
        except Exception:
            pass

        # Month navigator
        nav = ttk.Frame(header, style='DataBank.Card.TFrame')
        nav.pack(side='right', padx=(16, 0))
        ttk.Label(nav, text='Month', style='DataBank.Label.TLabel').pack(anchor='e')
        nav_row = ttk.Frame(nav, style='DataBank.Card.TFrame')
        nav_row.pack(anchor='e', pady=(5, 0))
        ttk.Button(nav_row, text='‹', width=3, command=self.prev_month).pack(side='left', padx=(0, 4))
        ttk.Button(nav_row, text='Today', command=self.goto_current_month).pack(side='left', padx=2)
        self.month_lbl = ttk.Label(nav_row, text=self._month_label(), style='DataBank.Pill.TLabel')
        self.month_lbl.pack(side='left', padx=6)
        ttk.Button(nav_row, text='›', width=3, command=self.next_month).pack(side='left', padx=(4, 0))

        # Summary cards
        self._db_rows_var = tk.StringVar(value='')
        self._db_close_info_var = tk.StringVar(value='')
        self._db_card_clients_var = tk.StringVar(value='0 clients')
        self._db_card_view_var = tk.StringVar(value=str(self._mode_filter() if hasattr(self, '_mode_filter') else 'Regular'))
        self._db_card_month_var = tk.StringVar(value=self._month_label())
        self._db_card_close_var = tk.StringVar(value='Select a payment day')

        stats = ttk.Frame(page, style='DataBank.Page.TFrame')
        stats.pack(fill='x', pady=(0, 12))
        for i in range(4):
            try:
                stats.grid_columnconfigure(i, weight=1, uniform='dbstats')
            except Exception:
                pass
        cards = [
            ('CLIENTS', self._db_card_clients_var),
            ('CURRENT VIEW', self._db_card_view_var),
            ('MONTH', self._db_card_month_var),
            ('DAY CLOSE STATUS', self._db_card_close_var),
        ]
        for i, (title, var) in enumerate(cards):
            c = _spina_v15_stat_card(stats, title, var)
            c.grid(row=0, column=i, sticky='ew', padx=(0 if i == 0 else 6, 0 if i == 3 else 6))

        # Action toolbar card
        actions = ttk.Frame(page, style='DataBank.Card.TFrame', padding=(12, 10, 12, 10))
        actions.pack(fill='x', pady=(0, 12))
        left_actions = ttk.Frame(actions, style='DataBank.Card.TFrame')
        left_actions.pack(side='left', fill='x', expand=True)
        right_actions = ttk.Frame(actions, style='DataBank.Card.TFrame')
        right_actions.pack(side='right')

        ttk.Label(left_actions, text='Actions', style='DataBank.Label.TLabel').pack(side='left', padx=(0, 10))
        # SPINA removed legacy Clients-tab action button statement
        ttk.Button(left_actions, text='Daily Close / View', command=self.open_databank_close_dialog).pack(side='left', padx=3)
        ttk.Button(left_actions, text='Delete Day', command=self.open_delete_day_dialog).pack(side='left', padx=3)
        ttk.Button(left_actions, text='Close Records', command=self.open_databank_close_records_dialog).pack(side='left', padx=3)

        # SPINA removed legacy Data Bank export UI control
        # SPINA removed Data Bank export control statement
        # SPINA removed Data Bank export control statement
        # SPINA removed Data Bank export control statement

        # Grid card
        body_card = ttk.Frame(page, style='DataBank.Card.TFrame', padding=(10, 10, 10, 10))
        body_card.pack(fill='both', expand=True)
        grid_head = ttk.Frame(body_card, style='DataBank.Card.TFrame')
        grid_head.pack(fill='x', pady=(0, 8))
        ttk.Label(grid_head, text='Payment Grid', style='DataBank.Label.TLabel').pack(side='left')
        ttk.Label(grid_head, textvariable=self._db_rows_var, style='DataBank.Muted.TLabel').pack(side='left', padx=(10, 0))
        ttk.Label(grid_head, textvariable=self._db_close_info_var, style='DataBank.Muted.TLabel').pack(side='right')

        self.inner = ttk.Frame(body_card, style='DataBank.Inner.TFrame')
        self.inner.pack(fill='both', expand=True)

        self.refresh_data_grid()
        try:
            if hasattr(self, '_update_data_toolbar'):
                self._update_data_toolbar()
        except Exception:
            pass
        try:
            _spina_v15_update_databank_cards(self)
        except Exception:
            pass

def _spina_v15_update_databank_cards(self):
        try:
            tv = getattr(self, 'name_tree', None)
            count = 0
            if tv is not None:
                try:
                    for iid in tv.get_children():
                        vals = tv.item(iid, 'values') or ()
                        if vals and str(vals[0]).strip() != '(no clients)':
                            count += 1
                except Exception:
                    pass
            if hasattr(self, '_db_card_clients_var'):
                self._db_card_clients_var.set(f"{count} client{'s' if count != 1 else ''}")
            if hasattr(self, '_db_card_view_var'):
                try:
                    self._db_card_view_var.set(str(self._mode_filter()))
                except Exception:
                    self._db_card_view_var.set('Regular')
            if hasattr(self, '_db_card_month_var'):
                try:
                    self._db_card_month_var.set(self._month_label())
                except Exception:
                    pass
            if hasattr(self, '_db_card_close_var'):
                close_txt = ''
                try:
                    close_txt = (getattr(self, '_db_close_info_var', None).get() or '').strip()
                except Exception:
                    close_txt = ''
                if close_txt:
                    self._db_card_close_var.set(close_txt)
                else:
                    self._db_card_close_var.set('Select a payment day')
        except Exception as __spina_exc:
            try:
                _log_suppressed_once('v15_databank_cards', 'modern databank cards update failed', __spina_exc)
            except Exception:
                pass

def _spina_v15_refresh_data_grid(self, *args, **kwargs):
                res = _spina_v15_orig_refresh_data_grid(self, *args, **kwargs)
                try:
                    _spina_v15_setup_databank_styles(self)
                except Exception:
                    pass
                try:
                    if getattr(self, 'name_tree', None) is not None:
                        self.name_tree.configure(style='DataBank.Treeview')
                    if getattr(self, 'days_tree', None) is not None:
                        self.days_tree.configure(style='DataBank.Treeview')
                except Exception:
                    pass
                try:
                    _spina_v15_update_databank_cards(self)
                except Exception:
                    pass
                return res

def _spina_v15_update_data_toolbar(self, *args, **kwargs):
                res = _spina_v15_orig_update_data_toolbar(self, *args, **kwargs)
                try:
                    _spina_v15_update_databank_cards(self)
                except Exception:
                    pass
                return res

def _spina_v15_apply_ui_theme(self, *args, **kwargs):
                res = _spina_v15_orig_apply_theme(self, *args, **kwargs)
                try:
                    _spina_v15_setup_databank_styles(self)
                except Exception:
                    pass
                try:
                    _spina_v15_update_databank_cards(self)
                except Exception:
                    pass
                return res

def _spina_v16_apply_bigger_payment_grid(self):
        """Make the Data Bank payment grid easier to read: bigger rows, wider client/area/day columns."""
        try:
            _spina_v15_setup_databank_styles(self)
        except Exception:
            pass
        try:
            if getattr(self, "name_tree", None) is not None:
                self.name_tree.configure(height=31, style="DataBank.Treeview")
                self.name_tree.column("client", width=330, stretch=False)
                self.name_tree.column("area", width=185, stretch=False)
        except Exception:
            pass
        try:
            if getattr(self, "days_tree", None) is not None:
                self.days_tree.configure(height=31, style="DataBank.Treeview")
                for c in self.days_tree["columns"]:
                    if str(c).startswith("d"):
                        self.days_tree.column(c, width=86, anchor="center", stretch=False)
        except Exception:
            pass

def _spina_v16_refresh_data_grid(self, *args, **kwargs):
                res = _spina_v16_prev_refresh_data_grid(self, *args, **kwargs)
                try:
                    _spina_v16_apply_bigger_payment_grid(self)
                except Exception:
                    pass
                return res


# Wave 53 desktop-test repair: restore the active Data Bank payment-import control.
# The exact Wave 49 presentation function above remains source-hash unchanged.
_spina_v15_build_data_tab_without_import_repair = _spina_v15_build_data_tab


def _spina_v53_widget_text(widget):
    try:
        return " ".join(str(widget.cget("text") or "").strip().split())
    except Exception:
        return ""


def _spina_v53_walk_widgets(widget):
    try:
        children = list(widget.winfo_children())
    except Exception:
        children = []
    for child in children:
        yield child
        yield from _spina_v53_walk_widgets(child)


def _spina_v53_restore_databank_import_control(self):
    callback = getattr(self, "_import_from_excel_entry", None)
    root = getattr(self, "tab_data", None)
    if not callable(callback) or root is None:
        return None

    widgets = list(_spina_v53_walk_widgets(root))
    for widget in widgets:
        if _spina_v53_widget_text(widget) == "Import Excel":
            self._db_import_excel_btn = widget
            return widget

    daily_close = next(
        (widget for widget in widgets if _spina_v53_widget_text(widget) == "Daily Close / View"),
        None,
    )
    if daily_close is None:
        return None

    try:
        parent = daily_close.master
        button = ttk.Button(
            parent,
            text="Import Excel",
            style="Primary.TButton",
            command=callback,
        )
        button.pack(side="left", padx=3, before=daily_close)
        self._db_import_excel_btn = button
        return button
    except Exception as exc:
        try:
            _log_suppressed_once(
                "wave53_restore_databank_import_control",
                "Data Bank Import Excel control restore failed",
                exc,
            )
        except Exception:
            pass
        return None


def _spina_v53_build_data_tab_with_import_control(self):
    result = _spina_v15_build_data_tab_without_import_repair(self)
    _spina_v53_restore_databank_import_control(self)
    return result


_spina_v15_build_data_tab = _spina_v53_build_data_tab_with_import_control
