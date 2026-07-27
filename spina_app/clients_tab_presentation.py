"""Clients tab construction presentation extracted in Wave 55."""
from __future__ import annotations

_CLIENTS_TAB_PRESENTATION_DEPENDENCIES = {}
_PROTECTED_GLOBALS = {'__loader__', '__builtins__', 'CLIENTS_TAB_PRESENTATION_TARGET', '__cached__', 'configure_clients_tab_presentation_dependencies', '__spec__', 'CLIENTS_TAB_PRESENTATION_BUTTON_TEXTS', '__name__', 'CLIENTS_TAB_PRESENTATION_CALLS', 'CLIENTS_TAB_PRESENTATION_SOURCE_LINES', 'CLIENTS_TAB_PRESENTATION_SOURCE_SHA256', '__file__', '_build_clients_tab', '__package__', '_PROTECTED_GLOBALS', '_CLIENTS_TAB_PRESENTATION_DEPENDENCIES', 'CLIENTS_TAB_PRESENTATION_LABEL_TEXTS', 'CLIENTS_TAB_PRESENTATION_SIGNATURE', '__doc__'}

def configure_clients_tab_presentation_dependencies(namespace):
    _CLIENTS_TAB_PRESENTATION_DEPENDENCIES.clear()
    _CLIENTS_TAB_PRESENTATION_DEPENDENCIES.update(namespace)
    for name, value in namespace.items():
        if name not in _PROTECTED_GLOBALS:
            globals()[name] = value

CLIENTS_TAB_PRESENTATION_TARGET = '_build_clients_tab'
CLIENTS_TAB_PRESENTATION_SOURCE_LINES = 156
CLIENTS_TAB_PRESENTATION_SOURCE_SHA256 = '21bd95f29f41585b1d27aea3296657e91b7a0e4dcaebb13c9820c63a7abb83b4'
CLIENTS_TAB_PRESENTATION_SIGNATURE = 'self'
CLIENTS_TAB_PRESENTATION_CALLS = ['_anchors.get', '_hdr.get', '_log_ignored', '_log_suppressed_once', '_w.get', 'actions.pack', 'area_box.pack', 'c.title', 'filters.pack', 'getattr', 'mode_cb.bind', 'mode_cb.pack', 'pack', 'self._configure_tree_stripes', 'self._del_client_btn.config', 'self._del_client_btn.pack', 'self._refresh_area_dropdowns', 'self._schedule_refresh_clients', 'self._update_toolbar_states', 'self.bulk_area_cb.pack', 'self.clients_tree.bind', 'self.clients_tree.column', 'self.clients_tree.configure', 'self.clients_tree.grid', 'self.clients_tree.heading', 'self.clients_tree.tag_configure', 'self.search_clients_var.trace_add', 'tk.StringVar', 'top_wrap.pack', 'tree_box.grid_columnconfigure', 'tree_box.grid_rowconfigure', 'tree_box.pack', 'ttk.Button', 'ttk.Combobox', 'ttk.Entry', 'ttk.Frame', 'ttk.Label', 'ttk.Scrollbar', 'ttk.Treeview', 'xsb.grid', 'ysb.grid']
CLIENTS_TAB_PRESENTATION_BUTTON_TEXTS = ['Delete Client', 'Add Client', 'Renew', 'Link', 'Unlink', 'History', 'Archived', 'Set Area (Selected)', 'Manage Areas']
CLIENTS_TAB_PRESENTATION_LABEL_TEXTS = ['Clients', 'Search:', 'In:', 'Set Area:']

def _build_clients_tab(self):
    frm = self.tab_clients

    # Top controls split into 2 rows so the tab stays readable on wide datasets.
    top_wrap = ttk.Frame(frm, style='Toolbar.TFrame')
    top_wrap.pack(fill='x', pady=(0, 8))

    filters = ttk.Frame(top_wrap, style='Toolbar.TFrame')
    filters.pack(fill='x', pady=(0, 4))

    ttk.Label(filters, text='Clients', style='Section.TLabel').pack(side='left', padx=(0, 10))
    ttk.Label(filters, text='Search:').pack(side='left', padx=(0, 6))
    self.search_clients_var = tk.StringVar()
    ttk.Entry(filters, textvariable=self.search_clients_var, width=28).pack(side='left')
    self.search_clients_var.trace_add('write', self._schedule_refresh_clients)

    self.clients_search_mode_var = tk.StringVar(value='All')
    ttk.Label(filters, text='In:').pack(side='left', padx=(12, 4))
    mode_cb = ttk.Combobox(
        filters,
        textvariable=self.clients_search_mode_var,
        values=('All','Client','Area','Linked','Unlinked','Suggested Link','Blanks','Principal','Released','Start Date','Due Date'),
        state='readonly',
        width=14,
    )
    mode_cb.pack(side='left')
    try:
        mode_cb.bind('<<ComboboxSelected>>', lambda e: self._schedule_refresh_clients())
    except Exception as e:
        _log_ignored("ui.bind failed", e, key="ui.bind_failed")

    try:
        area_box = ttk.Frame(filters)
        area_box.pack(side='left', padx=(14, 0))
        ttk.Label(area_box, text='Set Area:').pack(side='left')
        self.bulk_area_var = tk.StringVar(value='')
        self.bulk_area_cb = ttk.Combobox(area_box, textvariable=self.bulk_area_var, width=18, state='readonly')
        self.bulk_area_cb.pack(side='left', padx=4)
        ttk.Button(area_box, text='Set Area (Selected)', command=self.set_area_for_selected_clients).pack(side='left', padx=4)
        ttk.Button(area_box, text='Manage Areas', command=self.open_areas_manager).pack(side='left', padx=4)
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_0446', 'suppressed exception excpass_0446', __spina_exc)
        pass

    self.clients_count_var = tk.StringVar(value='Rows: 0')
    ttk.Label(filters, textvariable=self.clients_count_var).pack(side='right', padx=(8, 0))

    actions = ttk.Frame(top_wrap, style='Toolbar.TFrame')
    actions.pack(fill='x')

    # Main actions
    ttk.Button(actions, text='Add Client', command=self.add_client_dialog).pack(side='left', padx=(0, 6))
    ttk.Button(actions, text='Renew', command=self.renew_client_selected).pack(side='left', padx=6)
    ttk.Button(actions, text='Link', command=self.link_selected_client).pack(side='left', padx=6)
    ttk.Button(actions, text='Unlink', command=self.unlink_selected_client).pack(side='left', padx=6)
    ttk.Button(actions, text='History', command=self.open_client_history_dialog).pack(side='left', padx=6)
    ttk.Button(actions, text='Archived', command=self.open_archived_clients_dialog).pack(side='left', padx=6)

    # SPINA removed legacy Clients-tab action button statement
    # SPINA removed legacy Clients-tab action button statement
    # SPINA removed legacy Clients-tab action button statement
    # SPINA removed legacy Clients-tab action button statement
    self._del_client_btn = ttk.Button(actions, text='Delete Client', command=self.delete_client_selected)
    self._del_client_btn.pack(side='right', padx=6)
    try:
        self._del_client_btn.config(state='disabled')
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_0447', 'suppressed exception excpass_0447', __spina_exc)
        pass

    tree_box = ttk.Frame(frm)
    tree_box.pack(fill='both', expand=True, padx=8, pady=6)

    cols = ('name','area','term','day_due','payment','mode','linked','contact','principal','interest','total','released','due')
    self.clients_tree = ttk.Treeview(tree_box, columns=cols, show='headings', height=22, selectmode='extended')
    _hdr = {
        'name': 'Name',
        'area': 'Area',
        'term': 'Term',
        'day_due': 'Day Due',
        'payment': 'Payment',
        'mode': 'Mode',
        'linked': 'Linked',
        'contact': 'Contact',
        'principal': 'Principal',
        'interest': 'Interest',
        'total': 'Total',
        'released': 'Released',
        'due': 'Due',
    }
    _w = {
        'name': 230,
        'area': 185,
        'term': 80,
        'day_due': 95,
        'payment': 95,
        'mode': 78,
        'linked': 90,
        'contact': 125,
        'principal': 105,
        'interest': 95,
        'total': 110,
        'released': 104,
        'due': 104,
    }
    _anchors = {
        'name': 'w',
        'area': 'w',
        'term': 'center',
        'day_due': 'center',
        'payment': 'e',
        'mode': 'center',
        'linked': 'center',
        'contact': 'w',
        'principal': 'e',
        'interest': 'e',
        'total': 'e',
        'released': 'center',
        'due': 'center',
    }
    for c in cols:
        self.clients_tree.heading(c, text=_hdr.get(c, c.title()), anchor=_anchors.get(c, 'w'))
        self.clients_tree.column(c, width=_w.get(c, 110), minwidth=70, anchor=_anchors.get(c, 'w'), stretch=(c in ('name', 'area')))

    ysb = ttk.Scrollbar(tree_box, orient='vertical', command=self.clients_tree.yview)
    xsb = ttk.Scrollbar(tree_box, orient='horizontal', command=self.clients_tree.xview)
    self.clients_tree.configure(yscrollcommand=ysb.set, xscrollcommand=xsb.set)
    self.clients_tree.grid(row=0, column=0, sticky='nsew')
    ysb.grid(row=0, column=1, sticky='ns')
    xsb.grid(row=1, column=0, sticky='ew')
    tree_box.grid_rowconfigure(0, weight=1)
    tree_box.grid_columnconfigure(0, weight=1)

    try:
        self._configure_tree_stripes(self.clients_tree)
        self.clients_tree.tag_configure('extra7x7', foreground='#ffb366')
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_0447b', 'suppressed exception excpass_0447b', __spina_exc)
        pass

    self.clients_tree.bind('<Double-1>', self.on_client_edit)
    try:
        self.clients_tree.bind('<<TreeviewSelect>>', lambda e: getattr(self, '_del_client_btn', None) and self._update_toolbar_states())
    except Exception as e:
        _log_ignored("ui.bind failed", e, key="ui.bind_failed")

    try:
        self._update_toolbar_states()
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_0448', 'suppressed exception excpass_0448', __spina_exc)
        pass
    try:
        self._refresh_area_dropdowns()
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_0449', 'suppressed exception excpass_0449', __spina_exc)
        pass
