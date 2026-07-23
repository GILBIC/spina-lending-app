"""Tkinter UI for managing and selecting unlimited hierarchical Areas."""

from __future__ import annotations

from typing import Any

from spina_app.area_hierarchy import add_area_node, build_area_tree, list_area_nodes
from spina_app.area_hierarchy_ops import (
    count_clients_for_area_node,
    find_area_node_by_path,
    move_area_node,
    move_area_node_order,
    rename_area_node,
    set_area_node_active,
)

_FOLDER_CLOSED = "📁"
_FOLDER_OPEN = "📂"


def _connection(app: Any) -> Any:
    db = getattr(app, "db", None)
    conn = getattr(db, "conn", None)
    if conn is None:
        raise RuntimeError("The Area hierarchy database connection is unavailable.")
    return conn


def _refresh_app_area_views(app: Any) -> None:
    """Refresh legacy Area consumers only after the manager actually changed data."""
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


def _restore_parent_grab(parent: Any) -> None:
    """Return modal control to the form that opened the Area window."""
    try:
        if parent is not None and parent.winfo_exists():
            parent.grab_set()
            parent.lift()
            parent.focus_force()
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
            uid = str(by_uid.get(uid, {}).get("parent_uid") or "")
    return visible


def _folder_text(name: Any, opened: bool) -> str:
    icon = _FOLDER_OPEN if opened else _FOLDER_CLOSED
    return f"{icon} {str(name or '').strip()}"


def _remember_open_folders(tree: Any) -> set[str]:
    opened: set[str] = set()

    def walk(parent: str = "") -> None:
        for iid in tree.get_children(parent):
            try:
                if bool(tree.item(iid, "open")):
                    opened.add(str(iid))
            except Exception:
                pass
            walk(str(iid))

    walk()
    return opened


def _refresh_folder_icons(tree: Any, by_uid: dict[str, dict[str, Any]]) -> None:
    def walk(parent: str = "") -> None:
        for iid in tree.get_children(parent):
            uid = str(iid)
            node = by_uid.get(uid, {})
            opened = bool(tree.item(iid, "open"))
            tree.item(iid, text=_folder_text(node.get("name"), opened))
            walk(uid)

    walk()


def _set_all_folders(tree: Any, opened: bool) -> None:
    def walk(parent: str = "") -> None:
        for iid in tree.get_children(parent):
            tree.item(iid, open=opened)
            walk(str(iid))

    walk()


def _populate_area_tree(
    tree: Any,
    nodes: list[dict[str, Any]],
    *,
    query: str = "",
    include_status: bool = False,
    open_uids: set[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Render a true parent/child folder tree and return its UID lookup."""
    for iid in tree.get_children(""):
        tree.delete(iid)

    by_uid = {
        str(node.get("area_uid") or ""): dict(node)
        for node in nodes
        if str(node.get("area_uid") or "")
    }
    visible = _tree_visible_uids(nodes, query)
    filtering = visible is not None
    wanted_open = set(open_uids or ())

    def insert_branch(items: list[dict[str, Any]], parent_iid: str = "") -> None:
        for node in items:
            uid = str(node.get("area_uid") or "")
            if not uid or (visible is not None and uid not in visible):
                continue
            opened = filtering or uid in wanted_open
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
                text=_folder_text(node.get("name"), opened),
                values=values,
                open=opened,
                tags=("inactive",) if not int(node.get("is_active") or 0) else (),
            )
            insert_branch(list(node.get("children") or []), uid)

    insert_branch(build_area_tree(nodes))
    return by_uid


def select_area_node(
    app: Any,
    parent: Any = None,
    *,
    initial_path: str = "",
    allow_blank: bool = True,
    title: str = "Select Area",
) -> dict[str, Any] | None:
    """Open a modal folder browser and return the selected active Area node."""
    import tkinter as tk
    from tkinter import ttk

    conn = _connection(app)
    nodes = list_area_nodes(conn, include_inactive=False)
    by_uid = {str(node.get("area_uid") or ""): node for node in nodes}
    result: dict[str, Any] = {"value": None}

    owner = parent or getattr(app, "root", None)
    win = tk.Toplevel(owner)
    win.title(title)
    win.geometry("820x580")
    win.minsize(660, 460)
    try:
        win.transient(owner)
        win.grab_set()
    except Exception:
        pass

    outer = ttk.Frame(win, padding=12)
    outer.pack(fill="both", expand=True)

    ttk.Label(
        outer,
        text="Choose an Area folder. Use the arrows to expand or collapse child Areas.",
    ).pack(anchor="w", pady=(0, 8))

    search_var = tk.StringVar(value="")
    search_row = ttk.Frame(outer)
    search_row.pack(fill="x", pady=(0, 8))
    ttk.Label(search_row, text="Search:").pack(side="left")
    search_entry = ttk.Entry(search_row, textvariable=search_var)
    search_entry.pack(side="left", fill="x", expand=True, padx=(6, 10))

    tree_box = ttk.Frame(outer)
    tree_box.pack(fill="both", expand=True)
    tree = ttk.Treeview(
        tree_box,
        columns=("path",),
        show="tree headings",
        selectmode="browse",
    )
    tree.heading("#0", text="Area folders")
    tree.heading("path", text="Complete Area path")
    tree.column("#0", width=300, minwidth=180, stretch=True)
    tree.column("path", width=470, minwidth=260, stretch=True)
    ysb = ttk.Scrollbar(tree_box, orient="vertical", command=tree.yview)
    xsb = ttk.Scrollbar(tree_box, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=ysb.set, xscrollcommand=xsb.set)
    tree.grid(row=0, column=0, sticky="nsew")
    ysb.grid(row=0, column=1, sticky="ns")
    xsb.grid(row=1, column=0, sticky="ew")
    tree_box.rowconfigure(0, weight=1)
    tree_box.columnconfigure(0, weight=1)

    found = find_area_node_by_path(conn, initial_path, include_inactive=False) if initial_path else None
    initial_uid = str(found.get("area_uid") or "") if found else ""

    def refresh(*_args: Any) -> None:
        current = tree.selection()
        open_uids = _remember_open_folders(tree)
        rendered = _populate_area_tree(
            tree,
            nodes,
            query=search_var.get(),
            open_uids=open_uids,
        )
        wanted_uid = str(current[0]) if current else initial_uid
        if wanted_uid and wanted_uid in rendered and tree.exists(wanted_uid):
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
        close()

    def clear() -> None:
        result["value"] = {"area_uid": "", "full_path": "", "name": ""}
        close()

    def close() -> None:
        try:
            win.grab_release()
        except Exception:
            pass
        win.destroy()
        _restore_parent_grab(owner)

    controls = ttk.Frame(outer)
    controls.pack(fill="x", pady=(8, 0))
    ttk.Button(controls, text="Expand All", command=lambda: (_set_all_folders(tree, True), _refresh_folder_icons(tree, by_uid))).pack(side="left")
    ttk.Button(controls, text="Collapse All", command=lambda: (_set_all_folders(tree, False), _refresh_folder_icons(tree, by_uid))).pack(side="left", padx=(6, 0))
    if allow_blank:
        ttk.Button(controls, text="Clear Area", command=clear).pack(side="left", padx=(12, 0))
    ttk.Button(controls, text="Select Area", command=accept).pack(side="right")
    ttk.Button(controls, text="Cancel", command=close).pack(side="right", padx=(0, 6))

    search_var.trace_add("write", refresh)
    tree.bind("<Double-1>", accept)
    tree.bind("<<TreeviewOpen>>", lambda _event: _refresh_folder_icons(tree, by_uid))
    tree.bind("<<TreeviewClose>>", lambda _event: _refresh_folder_icons(tree, by_uid))
    win.protocol("WM_DELETE_WINDOW", close)
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
    ttk.Button(
        frame,
        text="Manage Areas",
        command=lambda: open_area_manager(app, owner),
    ).pack(side="left", padx=(4, 0))
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
        command=lambda: open_area_manager(app, owner),
    ).pack(side="left", padx=(4, 0))
    return box, entry


def _select_parent_area(app: Any, owner: Any, moving_uid: str) -> str | None:
    """Select a new parent folder; an empty string means move to the root."""
    import tkinter as tk
    from tkinter import ttk

    conn = _connection(app)
    nodes = list_area_nodes(conn, include_inactive=False)
    by_uid = {str(node.get("area_uid") or ""): node for node in nodes}
    result: dict[str, Any] = {"value": None}

    win = tk.Toplevel(owner)
    win.title("Choose New Parent Area")
    win.geometry("760x540")
    try:
        win.transient(owner)
        win.grab_set()
    except Exception:
        pass
    outer = ttk.Frame(win, padding=12)
    outer.pack(fill="both", expand=True)
    ttk.Label(
        outer,
        text="Choose the destination folder. Select Top level to make it a main Area.",
    ).pack(anchor="w", pady=(0, 8))

    tree = ttk.Treeview(outer, columns=("path",), show="tree headings", selectmode="browse")
    tree.heading("#0", text="Area folders")
    tree.heading("path", text="Complete Area path")
    tree.column("#0", width=280)
    tree.column("path", width=430)
    tree.pack(fill="both", expand=True)
    root_iid = "__ROOT__"
    tree.insert("", "end", iid=root_iid, text=f"{_FOLDER_OPEN} Top level", values=("Main Area",), open=True)

    def insert(items: list[dict[str, Any]], parent_iid: str) -> None:
        for node in items:
            uid = str(node.get("area_uid") or "")
            if not uid or uid == moving_uid:
                continue
            tree.insert(
                parent_iid,
                "end",
                iid=uid,
                text=_folder_text(node.get("name"), True),
                values=(str(node.get("full_path") or ""),),
                open=True,
            )
            insert(list(node.get("children") or []), uid)

    insert(build_area_tree(nodes), root_iid)
    tree.selection_set(root_iid)

    def close() -> None:
        try:
            win.grab_release()
        except Exception:
            pass
        win.destroy()
        _restore_parent_grab(owner)

    def accept(*_args: Any) -> None:
        selected = tree.selection()
        if not selected:
            return
        uid = str(selected[0])
        if uid != root_iid and uid not in by_uid:
            return
        result["value"] = "" if uid == root_iid else uid
        close()

    buttons = ttk.Frame(outer)
    buttons.pack(fill="x", pady=(10, 0))
    ttk.Button(buttons, text="Move Here", command=accept).pack(side="right")
    ttk.Button(buttons, text="Cancel", command=close).pack(side="right", padx=(0, 6))
    tree.bind("<Double-1>", accept)
    win.protocol("WM_DELETE_WINDOW", close)
    win.wait_window()
    return result["value"]


def open_area_manager(app: Any, parent: Any = None) -> None:
    """Open the folder-style unlimited hierarchical Area manager."""
    import tkinter as tk
    from tkinter import messagebox, simpledialog, ttk

    owner = parent or getattr(app, "root", None)
    try:
        existing = getattr(app, "_areas_win", None)
        if existing is not None and existing.winfo_exists():
            existing.lift()
            existing.focus_force()
            try:
                existing.grab_set()
            except Exception:
                pass
            return
    except Exception:
        pass

    conn = _connection(app)
    win = tk.Toplevel(owner)
    app._areas_win = win
    win.title("Area Management")
    win.geometry("980x680")
    win.minsize(800, 540)
    try:
        win.transient(owner)
        win.grab_set()
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
        text="Areas are organized like folders. Expand a folder to see its child Areas.",
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
    tree.heading("#0", text="Area folders")
    tree.heading("path", text="Complete Area path")
    tree.heading("status", text="Status")
    tree.column("#0", width=310, minwidth=180, stretch=True)
    tree.column("path", width=500, minwidth=280, stretch=True)
    tree.column("status", width=90, minwidth=70, anchor="center", stretch=False)
    tree.tag_configure("inactive", foreground="#888888")
    ysb = ttk.Scrollbar(tree_box, orient="vertical", command=tree.yview)
    xsb = ttk.Scrollbar(tree_box, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=ysb.set, xscrollcommand=xsb.set)
    tree.grid(row=0, column=0, sticky="nsew")
    ysb.grid(row=0, column=1, sticky="ns")
    xsb.grid(row=1, column=0, sticky="ew")
    tree_box.rowconfigure(0, weight=1)
    tree_box.columnconfigure(0, weight=1)

    status_var = tk.StringVar(value="")
    ttk.Label(outer, textvariable=status_var).pack(anchor="w", pady=(7, 0))

    state: dict[str, Any] = {
        "nodes": [],
        "by_uid": {},
        "changed": False,
    }

    def selected_uid() -> str:
        selected = tree.selection()
        return str(selected[0]) if selected else ""

    def selected_node() -> dict[str, Any] | None:
        return state["by_uid"].get(selected_uid())

    def render(*_args: Any, keep_uid: str = "") -> None:
        current = keep_uid or selected_uid()
        opened = _remember_open_folders(tree)
        state["by_uid"] = _populate_area_tree(
            tree,
            state["nodes"],
            query=search_var.get(),
            include_status=True,
            open_uids=opened,
        )
        if current and tree.exists(current):
            tree.selection_set(current)
            tree.focus(current)
            tree.see(current)
        active_count = sum(1 for node in state["nodes"] if int(node.get("is_active") or 0))
        inactive_count = len(state["nodes"]) - active_count
        status_var.set(f"{active_count} active Area folder(s) · {inactive_count} inactive")

    def reload_tree(*, keep_uid: str = "") -> None:
        state["nodes"] = list_area_nodes(conn, include_inactive=True)
        render(keep_uid=keep_uid)

    def mark_changed() -> None:
        state["changed"] = True

    def add_main() -> None:
        name = simpledialog.askstring("Add Main Area", "Main Area folder name:", parent=win)
        if not name:
            return
        try:
            node = add_area_node(conn, name, "")
            mark_changed()
            reload_tree(keep_uid=str(node.get("area_uid") or ""))
        except Exception as exc:
            messagebox.showerror("Area", str(exc), parent=win)

    def add_child() -> None:
        parent_node = selected_node()
        if parent_node is None:
            messagebox.showwarning("Select", "Select the parent Area folder first.", parent=win)
            return
        if not int(parent_node.get("is_active") or 0):
            messagebox.showwarning("Inactive", "Activate the parent Area before adding a child.", parent=win)
            return
        name = simpledialog.askstring(
            "Add Child Area",
            f"Child folder name under:\n{parent_node.get('full_path')}",
            parent=win,
        )
        if not name:
            return
        try:
            node = add_area_node(conn, name, str(parent_node.get("area_uid") or ""))
            mark_changed()
            reload_tree(keep_uid=str(node.get("area_uid") or ""))
        except Exception as exc:
            messagebox.showerror("Area", str(exc), parent=win)

    def rename_selected() -> None:
        node = selected_node()
        if node is None:
            messagebox.showwarning("Select", "Select an Area folder to rename.", parent=win)
            return
        name = simpledialog.askstring(
            "Rename Area",
            "New name for this Area folder:",
            initialvalue=str(node.get("name") or ""),
            parent=win,
        )
        if not name:
            return
        try:
            rename_area_node(conn, node["area_uid"], name)
            mark_changed()
            reload_tree(keep_uid=node["area_uid"])
        except Exception as exc:
            messagebox.showerror("Area", str(exc), parent=win)

    def move_selected() -> None:
        node = selected_node()
        if node is None:
            messagebox.showwarning("Select", "Select an Area folder to move.", parent=win)
            return
        parent_uid = _select_parent_area(app, win, str(node.get("area_uid") or ""))
        if parent_uid is None:
            return
        try:
            move_area_node(conn, node["area_uid"], parent_uid)
            mark_changed()
            reload_tree(keep_uid=node["area_uid"])
        except Exception as exc:
            messagebox.showerror("Area", str(exc), parent=win)

    def reorder(direction: int) -> None:
        node = selected_node()
        if node is None:
            return
        try:
            if move_area_node_order(conn, node["area_uid"], direction):
                mark_changed()
            reload_tree(keep_uid=node["area_uid"])
        except Exception as exc:
            messagebox.showerror("Area", str(exc), parent=win)

    def toggle_active() -> None:
        node = selected_node()
        if node is None:
            messagebox.showwarning("Select", "Select an Area folder first.", parent=win)
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
                f"This Area folder and its children are assigned to {used} client(s). Reassign them before deactivating it.",
                parent=win,
            )
            return
        if not messagebox.askyesno(
            "Confirm",
            f"{action.title()} this Area folder and all child folders?",
            parent=win,
        ):
            return
        try:
            set_area_node_active(conn, node["area_uid"], becoming_active)
            mark_changed()
            reload_tree(keep_uid=node["area_uid"])
        except Exception as exc:
            messagebox.showerror("Area", str(exc), parent=win)

    actions = ttk.Frame(outer)
    actions.pack(fill="x", pady=(10, 0))
    ttk.Button(actions, text="Add Main Folder", command=add_main).pack(side="left")
    ttk.Button(actions, text="Add Child Folder", command=add_child).pack(side="left", padx=(6, 0))
    ttk.Button(actions, text="Rename", command=rename_selected).pack(side="left", padx=(6, 0))
    ttk.Button(actions, text="Move", command=move_selected).pack(side="left", padx=(6, 0))
    ttk.Button(actions, text="Move Up", command=lambda: reorder(-1)).pack(side="left", padx=(6, 0))
    ttk.Button(actions, text="Move Down", command=lambda: reorder(1)).pack(side="left", padx=(6, 0))
    ttk.Button(actions, text="Activate / Deactivate", command=toggle_active).pack(side="left", padx=(6, 0))

    view_actions = ttk.Frame(outer)
    view_actions.pack(fill="x", pady=(8, 0))
    ttk.Button(
        view_actions,
        text="Expand All",
        command=lambda: (_set_all_folders(tree, True), _refresh_folder_icons(tree, state["by_uid"])),
    ).pack(side="left")
    ttk.Button(
        view_actions,
        text="Collapse All",
        command=lambda: (_set_all_folders(tree, False), _refresh_folder_icons(tree, state["by_uid"])),
    ).pack(side="left", padx=(6, 0))

    def close() -> None:
        if state.get("changed"):
            try:
                win.after_idle(lambda: _refresh_app_area_views(app))
            except Exception:
                _refresh_app_area_views(app)
        try:
            app._areas_win = None
        except Exception:
            pass
        try:
            win.grab_release()
        except Exception:
            pass
        win.destroy()
        _restore_parent_grab(owner)

    ttk.Button(view_actions, text="Close", command=close).pack(side="right")
    win.protocol("WM_DELETE_WINDOW", close)
    search_var.trace_add("write", render)
    tree.bind("<<TreeviewOpen>>", lambda _event: _refresh_folder_icons(tree, state["by_uid"]))
    tree.bind("<<TreeviewClose>>", lambda _event: _refresh_folder_icons(tree, state["by_uid"]))
    reload_tree()
