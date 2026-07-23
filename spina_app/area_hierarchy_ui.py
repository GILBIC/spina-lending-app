"""Tkinter UI for managing and selecting unlimited hierarchical Areas."""

from __future__ import annotations

from typing import Any, Callable

from spina_app.area_hierarchy import add_area_node, build_area_tree, list_area_nodes
from spina_app.area_hierarchy_ops import (
    count_clients_for_area_node,
    find_area_node_by_path,
    move_area_node,
    move_area_node_order,
    rename_area_node,
    set_area_node_active,
)


def _connection(app: Any) -> Any:
    db = getattr(app, "db", None)
    conn = getattr(db, "conn", None)
    if conn is None:
        raise RuntimeError("The Area hierarchy database connection is unavailable.")
    return conn


def _refresh_app_area_views(app: Any) -> None:
    for name in (
        "_refresh_area_dropdowns",
        "_schedule_refresh_clients",
        "_schedule_collectors_refresh",
    ):
        try:
            callback = getattr(app, name, None)
            if callable(callback):
                callback()
        except Exception:
            pass


def _tree_visible_uids(nodes: list[dict[str, Any]], query: str) -> set[str] | None:
    term = str(query or "").strip().casefold()
    if not term:
        return None
    by_uid = {str(node.get("area_uid") or ""): node for node in nodes}
    visible: set[str] = set()
    for node in nodes:
        if term not in str(node.get("full_path") or "").casefold():
            continue
        uid = str(node.get("area_uid") or "")
        while uid and uid not in visible:
            visible.add(uid)
            parent_uid = str(by_uid.get(uid, {}).get("parent_uid") or "")
            uid = parent_uid
    return visible


def _populate_area_tree(
    tree: Any,
    nodes: list[dict[str, Any]],
    *,
    query: str = "",
    include_status: bool = False,
) -> None:
    for iid in tree.get_children(""):
        tree.delete(iid)
    visible = _tree_visible_uids(nodes, query)

    def insert_branch(items: list[dict[str, Any]], parent_iid: str = "") -> None:
        for node in items:
            uid = str(node.get("area_uid") or "")
            if not uid or (visible is not None and uid not in visible):
                continue
            values: tuple[Any, ...]
            if include_status:
                values = (
                    str(node.get("full_path") or ""),
                    "Active" if int(node.get("is_active") or 0) else "Inactive",
                )
            else:
                values = (str(node.get("full_path") or ""),)
            tree.insert(
                parent_iid,
                "end",
                iid=uid,
                text=str(node.get("name") or ""),
                values=values,
                open=True,
                tags=("inactive",) if not int(node.get("is_active") or 0) else (),
            )
            insert_branch(list(node.get("children") or []), uid)

    insert_branch(build_area_tree(nodes))


def select_area_node(
    app: Any,
    parent: Any = None,
    *,
    initial_path: str = "",
    allow_blank: bool = True,
    title: str = "Select Area",
) -> dict[str, Any] | None:
    """Open a modal hierarchy browser and return the selected active node."""
    import tkinter as tk
    from tkinter import ttk

    conn = _connection(app)
    nodes = list_area_nodes(conn, include_inactive=False)
    by_uid = {str(node.get("area_uid") or ""): node for node in nodes}
    result: dict[str, Any] = {"value": None}

    owner = parent or getattr(app, "root", None)
    win = tk.Toplevel(owner)
    win.title(title)
    win.geometry("760x560")
    win.minsize(620, 440)
    try:
        win.transient(owner)
        win.grab_set()
    except Exception:
        pass

    outer = ttk.Frame(win, padding=12)
    outer.pack(fill="both", expand=True)

    search_var = tk.StringVar(value="")
    search_row = ttk.Frame(outer)
    search_row.pack(fill="x", pady=(0, 8))
    ttk.Label(search_row, text="Search:").pack(side="left")
    search_entry = ttk.Entry(search_row, textvariable=search_var)
    search_entry.pack(side="left", fill="x", expand=True, padx=(6, 0))

    tree_box = ttk.Frame(outer)
    tree_box.pack(fill="both", expand=True)
    tree = ttk.Treeview(
        tree_box,
        columns=("path",),
        show="tree headings",
        selectmode="browse",
    )
    tree.heading("#0", text="Area")
    tree.heading("path", text="Full Path")
    tree.column("#0", width=230, minwidth=140, stretch=True)
    tree.column("path", width=430, minwidth=220, stretch=True)
    ysb = ttk.Scrollbar(tree_box, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=ysb.set)
    tree.pack(side="left", fill="both", expand=True)
    ysb.pack(side="right", fill="y")

    def refresh(*_args: Any) -> None:
        current = tree.selection()
        _populate_area_tree(tree, nodes, query=search_var.get())
        wanted_uid = current[0] if current else ""
        if not wanted_uid and initial_path:
            found = find_area_node_by_path(conn, initial_path, include_inactive=False)
            wanted_uid = str(found.get("area_uid") or "") if found else ""
        if wanted_uid and tree.exists(wanted_uid):
            tree.selection_set(wanted_uid)
            tree.focus(wanted_uid)
            tree.see(wanted_uid)

    def accept(*_args: Any) -> None:
        selected = tree.selection()
        if not selected:
            return
        node = by_uid.get(str(selected[0]))
        if node is None:
            return
        result["value"] = dict(node)
        win.destroy()

    def clear() -> None:
        result["value"] = {"area_uid": "", "full_path": "", "name": ""}
        win.destroy()

    buttons = ttk.Frame(outer)
    buttons.pack(fill="x", pady=(10, 0))
    ttk.Button(buttons, text="Select Area", command=accept).pack(side="right")
    ttk.Button(buttons, text="Cancel", command=win.destroy).pack(side="right", padx=(0, 6))
    if allow_blank:
        ttk.Button(buttons, text="Clear Area", command=clear).pack(side="left")

    search_var.trace_add("write", refresh)
    tree.bind("<Double-1>", accept)
    refresh()
    try:
        search_entry.focus_set()
    except Exception:
        pass
    win.wait_window()
    return result["value"]


def select_area_for_variable(
    app: Any,
    owner: Any,
    variable: Any,
    *,
    allow_blank: bool = True,
) -> dict[str, Any] | None:
    node = select_area_node(
        app,
        owner,
        initial_path=str(variable.get() or ""),
        allow_blank=allow_blank,
    )
    if node is not None:
        variable.set(str(node.get("full_path") or ""))
    return node


def build_simple_area_selector(
    app: Any,
    owner: Any,
    variable: Any,
    *,
    width: int = 34,
) -> Any:
    """Return a compact read-only selector row for legacy client forms."""
    from tkinter import ttk

    frame = ttk.Frame(owner)
    entry = ttk.Entry(frame, textvariable=variable, width=width, state="readonly")
    entry.pack(side="left", fill="x", expand=True)
    ttk.Button(
        frame,
        text="Select…",
        command=lambda: select_area_for_variable(app, owner, variable),
    ).pack(side="left", padx=(6, 0))
    ttk.Button(frame, text="Clear", command=lambda: variable.set("")).pack(side="left", padx=(4, 0))
    ttk.Button(frame, text="Manage", command=lambda: open_area_manager(app)).pack(side="left", padx=(4, 0))
    return frame


def build_area_selector_field(
    parent: Any,
    app: Any,
    owner: Any,
    variable: Any,
    *,
    label: str = "Area / Route",
    width: int = 24,
) -> tuple[Any, Any]:
    """Build the modern client form's labeled, read-only Area selector."""
    import tkinter as tk
    from tkinter import ttk

    try:
        background = parent.cget("background")
    except Exception:
        background = "#ffffff"
    box = tk.Frame(parent, bg=background)
    tk.Label(
        box,
        text=label,
        bg=background,
        fg="#6b6470",
        font=("Segoe UI", 8, "bold"),
        anchor="w",
    ).pack(fill="x")
    line = tk.Frame(box, bg=background)
    line.pack(fill="x", pady=(3, 0))
    entry = ttk.Entry(line, textvariable=variable, width=width, state="readonly")
    entry.pack(side="left", fill="x", expand=True)
    ttk.Button(
        line,
        text="Select…",
        command=lambda: select_area_for_variable(app, owner, variable),
    ).pack(side="left", padx=(6, 0))
    ttk.Button(line, text="Clear", command=lambda: variable.set("")).pack(side="left", padx=(4, 0))
    ttk.Button(
        line,
        text="Manage Areas",
        command=lambda: open_area_manager(app),
    ).pack(side="left", padx=(4, 0))
    return box, entry


def _select_parent_area(app: Any, owner: Any, moving_uid: str) -> str | None:
    """Select a new parent; an empty string means move to the root."""
    import tkinter as tk
    from tkinter import ttk

    conn = _connection(app)
    nodes = list_area_nodes(conn, include_inactive=False)
    by_uid = {str(node.get("area_uid") or ""): node for node in nodes}
    result: dict[str, Any] = {"value": None}

    win = tk.Toplevel(owner)
    win.title("Choose New Parent Area")
    win.geometry("700x520")
    try:
        win.transient(owner)
        win.grab_set()
    except Exception:
        pass
    outer = ttk.Frame(win, padding=12)
    outer.pack(fill="both", expand=True)
    ttk.Label(
        outer,
        text="Choose the new parent. Select ‘Top level’ to make it a main Area.",
    ).pack(anchor="w", pady=(0, 8))

    tree = ttk.Treeview(outer, columns=("path",), show="tree headings", selectmode="browse")
    tree.heading("#0", text="Area")
    tree.heading("path", text="Full Path")
    tree.column("#0", width=220)
    tree.column("path", width=420)
    tree.pack(fill="both", expand=True)
    root_iid = "__ROOT__"
    tree.insert("", "end", iid=root_iid, text="Top level", values=("Main Area",), open=True)

    def insert(items: list[dict[str, Any]], parent_iid: str) -> None:
        for node in items:
            uid = str(node.get("area_uid") or "")
            if not uid or uid == moving_uid:
                continue
            tree.insert(
                parent_iid,
                "end",
                iid=uid,
                text=str(node.get("name") or ""),
                values=(str(node.get("full_path") or ""),),
                open=True,
            )
            insert(list(node.get("children") or []), uid)

    insert(build_area_tree(nodes), root_iid)
    tree.selection_set(root_iid)

    def accept(*_args: Any) -> None:
        selected = tree.selection()
        if not selected:
            return
        uid = str(selected[0])
        if uid != root_iid and uid not in by_uid:
            return
        result["value"] = "" if uid == root_iid else uid
        win.destroy()

    buttons = ttk.Frame(outer)
    buttons.pack(fill="x", pady=(10, 0))
    ttk.Button(buttons, text="Move Here", command=accept).pack(side="right")
    ttk.Button(buttons, text="Cancel", command=win.destroy).pack(side="right", padx=(0, 6))
    tree.bind("<Double-1>", accept)
    win.wait_window()
    return result["value"]


def open_area_manager(app: Any) -> None:
    """Open the unlimited hierarchical Area Management tree."""
    import tkinter as tk
    from tkinter import messagebox, simpledialog, ttk

    try:
        existing = getattr(app, "_areas_win", None)
        if existing is not None and existing.winfo_exists():
            existing.lift()
            existing.focus_force()
            return
    except Exception:
        pass

    conn = _connection(app)
    owner = getattr(app, "root", None)
    win = tk.Toplevel(owner)
    app._areas_win = win
    win.title("Area Management")
    win.geometry("920x640")
    win.minsize(760, 520)
    try:
        win.transient(owner)
    except Exception:
        pass

    outer = ttk.Frame(win, padding=12)
    outer.pack(fill="both", expand=True)
    ttk.Label(
        outer,
        text="Area Management",
        font=("Segoe UI", 15, "bold"),
    ).pack(anchor="w")
    ttk.Label(
        outer,
        text="Create unlimited levels. Clients select these managed paths and cannot type new Areas in the client form.",
    ).pack(anchor="w", pady=(2, 10))

    tools = ttk.Frame(outer)
    tools.pack(fill="x", pady=(0, 8))
    search_var = tk.StringVar(value="")
    ttk.Label(tools, text="Search:").pack(side="left")
    ttk.Entry(tools, textvariable=search_var, width=34).pack(side="left", padx=(6, 12))

    tree_box = ttk.Frame(outer)
    tree_box.pack(fill="both", expand=True)
    tree = ttk.Treeview(
        tree_box,
        columns=("path", "status"),
        show="tree headings",
        selectmode="browse",
    )
    tree.heading("#0", text="Area Level")
    tree.heading("path", text="Full Path")
    tree.heading("status", text="Status")
    tree.column("#0", width=220, minwidth=130, stretch=True)
    tree.column("path", width=500, minwidth=260, stretch=True)
    tree.column("status", width=90, minwidth=70, anchor="center", stretch=False)
    tree.tag_configure("inactive", foreground="#888888")
    ysb = ttk.Scrollbar(tree_box, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=ysb.set)
    tree.pack(side="left", fill="both", expand=True)
    ysb.pack(side="right", fill="y")

    status_var = tk.StringVar(value="")
    ttk.Label(outer, textvariable=status_var).pack(anchor="w", pady=(7, 0))

    state: dict[str, Any] = {"nodes": [], "by_uid": {}}

    def selected_uid() -> str:
        selected = tree.selection()
        return str(selected[0]) if selected else ""

    def selected_node() -> dict[str, Any] | None:
        return state["by_uid"].get(selected_uid())

    def refresh(*_args: Any, keep_uid: str = "") -> None:
        current = keep_uid or selected_uid()
        nodes = list_area_nodes(conn, include_inactive=True)
        state["nodes"] = nodes
        state["by_uid"] = {str(node.get("area_uid") or ""): node for node in nodes}
        _populate_area_tree(
            tree,
            nodes,
            query=search_var.get(),
            include_status=True,
        )
        if current and tree.exists(current):
            tree.selection_set(current)
            tree.focus(current)
            tree.see(current)
        active_count = sum(1 for node in nodes if int(node.get("is_active") or 0))
        inactive_count = len(nodes) - active_count
        status_var.set(f"{active_count} active Area(s) · {inactive_count} inactive")
        _refresh_app_area_views(app)

    def add_main() -> None:
        name = simpledialog.askstring("Add Main Area", "Main Area name:", parent=win)
        if not name:
            return
        try:
            node = add_area_node(conn, name, "")
            refresh(keep_uid=str(node.get("area_uid") or ""))
        except Exception as exc:
            messagebox.showerror("Area", str(exc), parent=win)

    def add_child() -> None:
        parent_node = selected_node()
        if parent_node is None:
            messagebox.showwarning("Select", "Select the parent Area first.", parent=win)
            return
        if not int(parent_node.get("is_active") or 0):
            messagebox.showwarning("Inactive", "Activate the parent Area before adding a child.", parent=win)
            return
        name = simpledialog.askstring(
            "Add Child Area",
            f"Child name under:\n{parent_node.get('full_path')}",
            parent=win,
        )
        if not name:
            return
        try:
            node = add_area_node(conn, name, str(parent_node.get("area_uid") or ""))
            refresh(keep_uid=str(node.get("area_uid") or ""))
        except Exception as exc:
            messagebox.showerror("Area", str(exc), parent=win)

    def rename_selected() -> None:
        node = selected_node()
        if node is None:
            messagebox.showwarning("Select", "Select an Area to rename.", parent=win)
            return
        name = simpledialog.askstring(
            "Rename Area",
            "New name for this Area level:",
            initialvalue=str(node.get("name") or ""),
            parent=win,
        )
        if not name:
            return
        try:
            rename_area_node(conn, node["area_uid"], name)
            refresh(keep_uid=node["area_uid"])
        except Exception as exc:
            messagebox.showerror("Area", str(exc), parent=win)

    def move_selected() -> None:
        node = selected_node()
        if node is None:
            messagebox.showwarning("Select", "Select an Area to move.", parent=win)
            return
        parent_uid = _select_parent_area(app, win, str(node.get("area_uid") or ""))
        if parent_uid is None:
            return
        try:
            move_area_node(conn, node["area_uid"], parent_uid)
            refresh(keep_uid=node["area_uid"])
        except Exception as exc:
            messagebox.showerror("Area", str(exc), parent=win)

    def reorder(direction: int) -> None:
        node = selected_node()
        if node is None:
            return
        try:
            move_area_node_order(conn, node["area_uid"], direction)
            refresh(keep_uid=node["area_uid"])
        except Exception as exc:
            messagebox.showerror("Area", str(exc), parent=win)

    def toggle_active() -> None:
        node = selected_node()
        if node is None:
            messagebox.showwarning("Select", "Select an Area first.", parent=win)
            return
        becoming_active = not bool(int(node.get("is_active") or 0))
        action = "activate" if becoming_active else "deactivate"
        used = count_clients_for_area_node(
            conn,
            node["area_uid"],
            include_descendants=True,
        )
        if not becoming_active and used:
            messagebox.showwarning(
                "Area in use",
                f"This Area subtree is assigned to {used} client(s). Reassign them before deactivating it.",
                parent=win,
            )
            return
        if not messagebox.askyesno(
            "Confirm",
            f"{action.title()} this Area and its child Areas?",
            parent=win,
        ):
            return
        try:
            set_area_node_active(conn, node["area_uid"], becoming_active)
            refresh(keep_uid=node["area_uid"])
        except Exception as exc:
            messagebox.showerror("Area", str(exc), parent=win)

    actions = ttk.Frame(outer)
    actions.pack(fill="x", pady=(10, 0))
    ttk.Button(actions, text="Add Main", command=add_main).pack(side="left")
    ttk.Button(actions, text="Add Child", command=add_child).pack(side="left", padx=(6, 0))
    ttk.Button(actions, text="Rename", command=rename_selected).pack(side="left", padx=(6, 0))
    ttk.Button(actions, text="Move", command=move_selected).pack(side="left", padx=(6, 0))
    ttk.Button(actions, text="Move Up", command=lambda: reorder(-1)).pack(side="left", padx=(6, 0))
    ttk.Button(actions, text="Move Down", command=lambda: reorder(1)).pack(side="left", padx=(6, 0))
    ttk.Button(actions, text="Activate / Deactivate", command=toggle_active).pack(side="left", padx=(6, 0))
    ttk.Button(actions, text="Close", command=win.destroy).pack(side="right")

    def close() -> None:
        _refresh_app_area_views(app)
        try:
            app._areas_win = None
        except Exception:
            pass
        win.destroy()

    win.protocol("WM_DELETE_WINDOW", close)
    search_var.trace_add("write", refresh)
    refresh()
