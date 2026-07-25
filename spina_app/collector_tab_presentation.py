"""Active collector-tab presentation extracted in Wave 44."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

_COLLECTOR_TAB_DEPENDENCIES = {}
_PROTECTED_GLOBALS = {
    '__builtins__', '__cached__', '__doc__', '__file__', '__loader__',
    '__name__', '__package__', '__spec__',
    '_COLLECTOR_TAB_DEPENDENCIES', '_PROTECTED_GLOBALS',
    'configure_collector_tab_dependencies',
    'COLLECTOR_TAB_TARGET', 'COLLECTOR_TAB_SOURCE_LINES',
    'COLLECTOR_TAB_SOURCE_SHA256', 'COLLECTOR_TAB_SIGNATURE',
    'COLLECTOR_TAB_NESTED_CALLBACKS', 'COLLECTOR_TAB_CALLS',
    'tk', 'messagebox', 'ttk',
}


def configure_collector_tab_dependencies(namespace):
    _COLLECTOR_TAB_DEPENDENCIES.clear()
    _COLLECTOR_TAB_DEPENDENCIES.update(namespace)
    for name, value in namespace.items():
        if name not in _PROTECTED_GLOBALS:
            globals()[name] = value


COLLECTOR_TAB_TARGET = '_spina_v27_build_collectors_tab'
COLLECTOR_TAB_SOURCE_LINES = 293
COLLECTOR_TAB_SOURCE_SHA256 = '5ce718e8f43404331b044d2f3f43b81dc34b0782a15d45a317121e61da6701cb'
COLLECTOR_TAB_SIGNATURE = 'self'
COLLECTOR_TAB_NESTED_CALLBACKS = []
COLLECTOR_TAB_CALLS = ['_log_exc', '_set_sort', '_spina_v27_hidden_collector_widgets', '_spina_v27_route_button', '_spina_v27_route_card', '_spina_v27_route_colors', '_spina_v27_style_route_trees', '_spina_v27_update_route_cards', 'bool', 'card.grid', 'cards.columnconfigure', 'cards.pack', 'controls.pack', 'ctx.add_command', 'ctx.add_separator', 'ctx.grab_release', 'ctx.tk_popup', 'ent_search.focus_set', 'ent_search.pack', 'enumerate', 'filter_box.pack', 'frm.winfo_children', 'getattr', 'guide.grid', 'hasattr', 'header.pack', 'health.grid', 'hsb.grid', 'lbl.pack', 'menu.add_command', 'menu.add_separator', 'messagebox.showerror', 'more.configure', 'more.pack', 'outer.pack', 'pack', 'range', 'row.pack', 'search_box.pack', 'search_line.pack', 'self._collectors_name_from_values', 'self._delete_selected_collector', 'self._edit_selected_collector', 'self._schedule_collectors_refresh', 'self.collector_route_filter_main_cmb.bind', 'self.collector_route_filter_main_cmb.pack', 'self.collector_route_search_var.trace_add', 'self.collector_route_table_status_var.set', 'self.refresh_collectors', 'set', 'table_card.pack', 'table_head.pack', 'titlebox.pack', 'tk.BooleanVar', 'tk.Frame', 'tk.Label', 'tk.Menu', 'tk.Menubutton', 'tk.StringVar', 'top_split.columnconfigure', 'top_split.pack', 'tree.bind', 'tree.column', 'tree.configure', 'tree.focus', 'tree.grid', 'tree.heading', 'tree.identify_row', 'tree.item', 'tree.selection', 'tree.selection_set', 'tree.tag_configure', 'tree_frm.grid_columnconfigure', 'tree_frm.grid_rowconfigure', 'tree_frm.pack', 'ttk.Combobox', 'ttk.Entry', 'ttk.Scrollbar', 'ttk.Treeview', 'vsb.grid', 'w.destroy']

def _spina_v27_build_collectors_tab(self):
    try:
        frm = self.tab_collectors
        try:
            for w in frm.winfo_children():
                w.destroy()
        except Exception:
            pass

        c = _spina_v27_route_colors(self)
        _spina_v27_style_route_trees(self)

        # Vars used by existing route logic
        self.collector_route_search_var = tk.StringVar(value="")
        self.collector_route_filter_main_var = tk.StringVar(value="(All)")
        self.collector_route_filter_conflicts_var = tk.BooleanVar(value=False)
        self.collector_route_filter_unknown_var = tk.BooleanVar(value=False)
        self.collector_route_multi_var = tk.BooleanVar(value=False)
        self.collector_route_unassigned_var = tk.StringVar(value="Unassigned areas: 0")
        self.collector_route_noarea_var = tk.StringVar(value="No-area clients: 0")
        self.collector_route_unknown_var = tk.StringVar(value="")
        self.collector_route_conflict_var = tk.StringVar(value="")
        self.collectors_bulk_count_var = tk.StringVar(value="")
        self._collectors_checked = set()
        self._collector_route_cards = {}
        self._route_health_labels = {}

        outer = tk.Frame(frm, bg=c["bg"])
        outer.pack(fill="both", expand=True)

        # Header
        header = tk.Frame(outer, bg=c["bg"])
        header.pack(fill="x", padx=18, pady=(16, 10))

        titlebox = tk.Frame(header, bg=c["bg"])
        titlebox.pack(side="left", fill="x", expand=True)
        tk.Label(titlebox, text="Collector Route", bg=c["bg"], fg=c["fg"], font=("Segoe UI", 20, "bold"), anchor="w").pack(fill="x")
        tk.Label(
            titlebox,
            text="Daily route overview. Select a collector, print the route, or open the bigger route editor.",
            bg=c["bg"],
            fg=c["muted"],
            font=("Segoe UI", 10),
            anchor="w",
        ).pack(fill="x", pady=(2, 0))

        _spina_v27_route_button(header, "Print Selected Route", command=self.print_collector_route_daily_ledger, kind="primary").pack(side="right", padx=(8, 0))
        _spina_v27_route_button(header, "Edit Route", command=self._edit_selected_collector, kind="success").pack(side="right", padx=(8, 0))
        _spina_v27_route_button(header, "Add Collector", command=self._add_collector, kind="soft").pack(side="right", padx=(8, 0))

        # Route health + simple instructions
        top_split = tk.Frame(outer, bg=c["bg"])
        top_split.pack(fill="x", padx=18, pady=(0, 12))
        top_split.columnconfigure(0, weight=2)
        top_split.columnconfigure(1, weight=1)

        guide = tk.Frame(top_split, bg=c["panel"], highlightbackground=c["border"], highlightthickness=1, bd=0)
        guide.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        tk.Label(guide, text="Daily route workflow", bg=c["panel"], fg=c["fg"], font=("Segoe UI", 11, "bold"), anchor="w").pack(fill="x", padx=14, pady=(10, 0))
        tk.Label(
            guide,
            text="1) Check route health.  2) Select collector.  3) Print selected route.  4) Use Edit Route only when you need to change assigned areas/order.",
            bg=c["panel"],
            fg=c["muted"],
            font=("Segoe UI", 9),
            anchor="w",
            justify="left",
            wraplength=900,
        ).pack(fill="x", padx=14, pady=(3, 10))

        health = tk.Frame(top_split, bg=c["panel"], highlightbackground=c["border"], highlightthickness=1, bd=0)
        health.grid(row=0, column=1, sticky="nsew")
        tk.Label(health, text="Route Health Check", bg=c["panel"], fg=c["fg"], font=("Segoe UI", 11, "bold"), anchor="w").pack(fill="x", padx=14, pady=(10, 4))
        for key in ("unassigned", "noarea", "unknown", "conflict"):
            lbl = tk.Label(health, text="✓ Checking…", bg=c["panel"], fg=c["muted"], font=("Segoe UI", 9, "bold"), anchor="w")
            lbl.pack(fill="x", padx=14, pady=(0, 4))
            self._route_health_labels[key] = lbl

        # Controls
        controls = tk.Frame(outer, bg=c["panel"], highlightbackground=c["border"], highlightthickness=1, bd=0)
        controls.pack(fill="x", padx=18, pady=(0, 12))
        row = tk.Frame(controls, bg=c["panel"])
        row.pack(fill="x", padx=12, pady=10)

        search_box = tk.Frame(row, bg=c["panel"])
        search_box.pack(side="left", fill="x", expand=True, padx=(0, 10))
        tk.Label(search_box, text="Search Collector / Route / Notes", bg=c["panel"], fg=c["muted"], font=("Segoe UI", 8, "bold"), anchor="w").pack(fill="x")
        search_line = tk.Frame(search_box, bg=c["panel"])
        search_line.pack(fill="x", pady=(3, 0))
        ent_search = ttk.Entry(search_line, textvariable=self.collector_route_search_var)
        ent_search.pack(side="left", fill="x", expand=True)
        _spina_v27_route_button(search_line, "Clear", command=self._clear_collectors_search_filters, kind="soft").pack(side="left", padx=(8, 0))

        filter_box = tk.Frame(row, bg=c["panel"])
        filter_box.pack(side="left", padx=(0, 10))
        tk.Label(filter_box, text="Main Area", bg=c["panel"], fg=c["muted"], font=("Segoe UI", 8, "bold"), anchor="w").pack(fill="x")
        self.collector_route_filter_main_cmb = ttk.Combobox(
            filter_box,
            textvariable=self.collector_route_filter_main_var,
            values=["(All)"],
            state="readonly",
            width=18,
        )
        self.collector_route_filter_main_cmb.pack(fill="x", pady=(3, 0))
        self.collector_route_filter_main_cmb.bind("<<ComboboxSelected>>", lambda e: self.refresh_collectors())

        # More options menu keeps advanced functions but removes visible clutter.
        more = tk.Menubutton(
            row,
            text="More Options",
            bg=c["card2"],
            fg=c["fg"],
            activebackground=c["soft"],
            activeforeground=c["fg"],
            relief="flat",
            bd=0,
            padx=14,
            pady=8,
            font=("Segoe UI", 9, "bold"),
            cursor="hand2",
        )
        menu = tk.Menu(more, tearoff=0)
        more.configure(menu=menu)
        menu.add_command(label="Show Unassigned Areas", command=self._show_unassigned_areas)
        menu.add_command(label="Show No-Area Clients", command=self._show_no_area_clients)
        menu.add_command(label="Show Route Conflicts", command=self._show_conflicts)
        menu.add_separator()
        menu.add_command(label="Refresh", command=self.refresh_collectors)
        menu.add_command(label="Delete Selected Collector", command=self._delete_selected_collector)
        more.pack(side="right", pady=(12, 0))

        # Summary cards
        cards = tk.Frame(outer, bg=c["bg"])
        cards.pack(fill="x", padx=18, pady=(0, 12))
        for i in range(4):
            cards.columnconfigure(i, weight=1, uniform="routecards")

        for i, (key, title, value, sub, accent) in enumerate([
            ("routes", "Routes Shown", "0", "Collectors shown", c["blue"]),
            ("unassigned", "Unassigned Areas", "0", "Active areas not assigned", c["orange"]),
            ("noarea", "No-Area Clients", "0", "Needs area assignment", c["purple"]),
            ("issues", "Route Issues", "0", "Unknown + conflicts", c["red"]),
        ]):
            card, val, sublbl = _spina_v27_route_card(cards, title, value, sub, accent)
            card.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 8, 0), ipady=2)
            self._collector_route_cards[key] = (val, sublbl)

        # Main table
        table_card = tk.Frame(outer, bg=c["panel"], highlightbackground=c["border"], highlightthickness=1, bd=0)
        table_card.pack(fill="both", expand=True, padx=18, pady=(0, 18))
        table_head = tk.Frame(table_card, bg=c["panel"])
        table_head.pack(fill="x", padx=12, pady=(10, 4))
        tk.Label(table_head, text="Collector Route List", bg=c["panel"], fg=c["fg"], font=("Segoe UI", 12, "bold"), anchor="w").pack(side="left")
        self.collector_route_table_status_var = tk.StringVar(value="Double-click a row to edit route.")
        tk.Label(table_head, textvariable=self.collector_route_table_status_var, bg=c["panel"], fg=c["muted"], font=("Segoe UI", 9), anchor="e").pack(side="right")

        tree_frm = tk.Frame(table_card, bg=c["panel"])
        tree_frm.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        cols = ("sel", "collector", "areas_count", "clients", "main_area", "sub_area", "details", "actions")
        self.collectors_tree = ttk.Treeview(
            tree_frm,
            columns=cols,
            displaycolumns=("collector", "areas_count", "clients", "main_area", "details", "actions"),
            show="headings",
            selectmode="browse",
            style="ModernRoute.Treeview",
        )
        tree = self.collectors_tree

        self._collectors_sort_col = "collector"
        self._collectors_sort_reverse = False

        def _set_sort(col):
            try:
                if getattr(self, "_collectors_sort_col", None) == col:
                    self._collectors_sort_reverse = not bool(getattr(self, "_collectors_sort_reverse", False))
                else:
                    self._collectors_sort_col = col
                    self._collectors_sort_reverse = False
            except Exception:
                self._collectors_sort_col = col
                self._collectors_sort_reverse = False
            self.refresh_collectors()

        headings = {
            "collector": ("Collector", 190, "w", "collector"),
            "areas_count": ("Areas", 75, "center", "areas_count"),
            "clients": ("Clients", 120, "center", "clients"),
            "main_area": ("Main Areas", 250, "w", "main_area"),
            "details": ("Route Summary / Notes", 480, "w", "details"),
            "actions": ("Action", 140, "center", None),
        }
        for col in cols:
            if col in headings:
                label, width, anchor, sort = headings[col]
                tree.heading(col, text=label, command=(lambda c=sort: _set_sort(c)) if sort else "")
                tree.column(col, width=width, minwidth=70, anchor=anchor, stretch=(col in ("main_area", "details")))
            else:
                tree.heading(col, text="")
                tree.column(col, width=1, minwidth=1, stretch=False)

        vsb = ttk.Scrollbar(tree_frm, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(tree_frm, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        tree_frm.grid_rowconfigure(0, weight=1)
        tree_frm.grid_columnconfigure(0, weight=1)

        try:
            tree.tag_configure("odd", background=c["panel"])
            tree.tag_configure("even", background=c["card2"])
            tree.tag_configure("warn", foreground=c["red"])
            tree.tag_configure("unknown", foreground=c["orange"])
        except Exception:
            pass

        # Double-click = modern editor. Selection only updates status/cards.
        def _select_status(_=None):
            try:
                vals = tree.item(tree.selection()[0], "values") if tree.selection() else ()
                nm = self._collectors_name_from_values(vals)
                self._selected_collector_name = nm
                if hasattr(self, "collector_route_table_status_var"):
                    self.collector_route_table_status_var.set(f"Selected: {nm}. Double-click to edit or click Print Selected Route.")
            except Exception:
                pass
            _spina_v27_update_route_cards(self)

        tree.bind("<<TreeviewSelect>>", _select_status)
        tree.bind("<Double-1>", lambda e: self._edit_selected_collector())
        tree.bind("<Return>", lambda e: self._edit_selected_collector())
        tree.bind("<Delete>", lambda e: self._delete_selected_collector())

        # Context menu
        ctx = tk.Menu(tree, tearoff=0)
        ctx.add_command(label="Edit Route", command=self._edit_selected_collector)
        ctx.add_command(label="Print Selected Route", command=self.print_collector_route_daily_ledger)
        ctx.add_separator()
        ctx.add_command(label="Delete Collector", command=self._delete_selected_collector)
        self._collectors_ctx_menu = ctx

        def _popup(event):
            try:
                iid = tree.identify_row(event.y)
                if iid:
                    tree.selection_set(iid)
                    tree.focus(iid)
                ctx.tk_popup(event.x_root, event.y_root)
            finally:
                try:
                    ctx.grab_release()
                except Exception:
                    pass

        tree.bind("<Button-3>", _popup)
        tree.bind("<Button-2>", _popup)

        _spina_v27_hidden_collector_widgets(self, outer)

        def _on_search(*_):
            try:
                self._schedule_collectors_refresh()
            except Exception:
                try:
                    self.refresh_collectors()
                except Exception:
                    pass

        try:
            self.collector_route_search_var.trace_add("write", _on_search)
        except Exception:
            pass

        try:
            ent_search.focus_set()
        except Exception:
            pass

        self.refresh_collectors()
        _spina_v27_update_route_cards(self)

    except Exception as e:
        try:
            _log_exc("v27.collector_route.build_tab", e)
        except Exception:
            pass
        try:
            messagebox.showerror("Collector Route", f"Unable to build Collector Route page.\n\n{e}")
        except Exception:
            pass
