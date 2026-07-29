"""Reports list, note, and report-log controller for SPINA Wave 80."""
from __future__ import annotations

import csv
import os
from typing import Any, Mapping

from spina_app.repositories.reports import (
    fetch_client_info,
    fetch_client_link_meta,
    fetch_client_type_presence,
    fetch_report_clients,
)
from spina_app.services.reports import build_report_row, build_report_summary

_DEPENDENCIES: dict[str, Any] = {}
_REQUIRED = (
    "_spina__client_due_meta",
    "_spina__fmt_client_money",
    "get_client_note",
    "set_client_note",
    "_open_path",
    "REPORT_GENERATION_LOG_CSV",
    "DATA_DIR",
)


def configure_report_controller_dependencies(namespace: Mapping[str, Any]) -> tuple[str, ...]:
    _DEPENDENCIES.clear()
    _DEPENDENCIES.update(namespace)
    missing = []
    for name in _REQUIRED:
        value = namespace.get(name)
        if value is None:
            missing.append(name)
            continue
        globals()[name] = value
    for name in ("_log_exc", "_log_suppressed_once", "messagebox", "tk"):
        if name in namespace:
            globals()[name] = namespace[name]
    return tuple(missing)


def _safe_log(context: str, exc: BaseException | None = None) -> None:
    callback = globals().get("_log_exc")
    if callable(callback):
        try:
            callback(context, exc)
        except Exception:
            pass


def _safe_suppressed(key: str, message: str, exc: BaseException | None = None) -> None:
    callback = globals().get("_log_suppressed_once")
    if callable(callback):
        try:
            callback(key, message, exc)
        except Exception:
            pass


def _mode(app: Any) -> str:
    try:
        return str(app._mode_filter() or "").strip()
    except Exception:
        return ""


def _var_text(app: Any, name: str) -> str:
    try:
        value = getattr(app, name, None)
        return str(value.get() or "").strip() if value is not None else ""
    except Exception:
        return ""


def refresh_reports(app: Any) -> None:
    tree = getattr(app, "reports_tree", None)
    if tree is None:
        return
    search = _var_text(app, "search_reports_var")
    try:
        for row_id in tree.get_children():
            tree.delete(row_id)
    except Exception:
        return

    include_archived = False
    try:
        variable = getattr(app, "show_archived_reports_var", None)
        include_archived = bool(variable.get()) if variable is not None else False
    except Exception:
        include_archived = False

    active_filter = _mode(app)
    names = fetch_report_clients(
        app,
        search=search,
        loan_type=active_filter,
        include_archived=include_archived,
    )
    rows = []
    for name in names:
        info = fetch_client_info(app, name, active_filter)
        rows.append((name, info))

    for index, (name, info) in enumerate(rows):
        has_regular, has_7x7 = fetch_client_type_presence(app, name)
        try:
            due_label, _due_today = _spina__client_due_meta(info, as_of=None)
        except Exception:
            due_label = ""
        values = build_report_row(
            name,
            info,
            active_filter=active_filter,
            has_regular=has_regular,
            has_7x7=has_7x7,
            due_label=due_label,
            format_money=_spina__fmt_client_money,
        )
        try:
            tree.insert(
                "",
                "end",
                values=values,
                tags=("even" if index % 2 == 0 else "odd",),
            )
        except Exception as exc:
            _safe_log("reports.refresh.insert", exc)

    try:
        summary_var = getattr(app, "report_summary_var", None)
        if summary_var is not None:
            summary_var.set(
                build_report_summary(
                    len(rows),
                    active_filter=active_filter or "All",
                    start_date=_var_text(app, "start_date_var"),
                    end_date=_var_text(app, "end_date_var"),
                )
            )
    except Exception:
        pass
    try:
        app._clear_preview()
    except Exception:
        pass


def open_report_generation_log(app: Any) -> None:
    try:
        target = REPORT_GENERATION_LOG_CSV
        if not os.path.exists(target):
            try:
                os.makedirs(os.path.dirname(target), exist_ok=True)
                fields = [
                    "generated_at",
                    "generated_date",
                    "client_name",
                    "loan_type",
                    "start_date",
                    "end_date",
                    "daily_total",
                    "client_daily_count",
                    "pdf_path",
                ]
                with open(target, "w", newline="", encoding="utf-8-sig") as handle:
                    csv.DictWriter(handle, fieldnames=fields).writeheader()
            except Exception:
                target = DATA_DIR
        if not _open_path(target):
            _open_path(DATA_DIR)
    except Exception as exc:
        _safe_suppressed(
            "reports_open_generation_log",
            "suppressed exception opening report generation log",
            exc,
        )
        try:
            messagebox.showerror(
                "Report Logs",
                f"Cannot open report log.\n\nFolder: {DATA_DIR}",
            )
        except Exception:
            pass


def get_selected_report_client(app: Any) -> str | None:
    try:
        tree = app.reports_tree
        selected = tree.selection()
        if selected:
            values = tree.item(selected[0], "values") or ()
            return str(values[0]) if values else None
    except Exception as exc:
        _safe_suppressed("reports_selected_client", "suppressed report selection error", exc)
    return None


def get_report_note_text(app: Any) -> str:
    try:
        widget = getattr(app, "report_note_txt", None)
        if widget is not None:
            return str(widget.get("1.0", "end-1c") or "").strip()
    except Exception:
        pass
    try:
        return str(app.report_note_var.get() or "").strip()
    except Exception:
        return ""


def set_report_note_text(app: Any, value: Any) -> None:
    text = str(value or "")
    try:
        variable = getattr(app, "report_note_var", None)
        if variable is not None:
            variable.set(text)
    except Exception:
        pass
    try:
        widget = getattr(app, "report_note_txt", None)
        if widget is not None:
            widget.delete("1.0", "end")
            if text:
                widget.insert("1.0", text)
    except Exception:
        pass
    try:
        name = get_selected_report_client(app)
        note_date = _var_text(app, "note_date_var")
        status = getattr(app, "report_note_status_var", None)
        if status is not None:
            if name and note_date:
                status.set(f"Notes for {name} on {note_date}")
            elif name:
                status.set(f"Notes for {name}")
            else:
                status.set("Select a client to view notes.")
    except Exception:
        pass


def _link_ids(app: Any, name: str) -> tuple[str | None, str | None]:
    meta = fetch_client_link_meta(app, name, _mode(app))
    client_uid = str(meta.get("client_uid") or "").strip() or None
    person_uid = str(meta.get("person_uid") or "").strip() or None
    return client_uid, person_uid


def save_dated_note_for_client(app: Any) -> None:
    name = get_selected_report_client(app)
    if not name:
        messagebox.showwarning("Save Note", "Select a client in the Reports list first.")
        return
    note_date = _var_text(app, "note_date_var")
    if not note_date:
        messagebox.showwarning("Save Note", "Enter a note date (YYYY-MM-DD).")
        return
    client_uid, person_uid = _link_ids(app, name)
    try:
        set_client_note(
            name,
            get_report_note_text(app),
            note_date,
            scope="shared",
            client_uid=client_uid,
            person_uid=person_uid,
        )
    except Exception as exc:
        _safe_log("reports:save_dated_note", exc)
        messagebox.showerror(
            "Save Error",
            f"Failed to save note.\n\n{exc}\n\nSee log: data/spina_app.log",
        )
        return
    messagebox.showinfo("Saved", f"Note saved for {name} on {note_date}.")


def auto_load_report_note(app: Any, *_args: Any) -> None:
    try:
        name = get_selected_report_client(app)
        note_date = _var_text(app, "note_date_var")
        client_uid, person_uid = _link_ids(app, name) if name else (None, None)
        note = (
            get_client_note(
                name,
                note_date,
                scope="effective",
                client_uid=client_uid,
                person_uid=person_uid,
            )
            if name and note_date
            else ""
        )
        set_report_note_text(app, note)
    except Exception as exc:
        _safe_suppressed("reports_auto_note", "suppressed report auto-note error", exc)


def save_report_note_for_client(app: Any) -> None:
    name = get_selected_report_client(app)
    if not name:
        messagebox.showwarning("Save Note", "Select a client in the Reports list first.")
        return
    client_uid, person_uid = _link_ids(app, name)
    try:
        set_client_note(
            name,
            get_report_note_text(app),
            None,
            scope="shared",
            client_uid=client_uid,
            person_uid=person_uid,
        )
    except Exception as exc:
        _safe_log("reports:save_note", exc)
        messagebox.showerror(
            "Save Error",
            f"Failed to save note.\n\n{exc}\n\nSee log: data/spina_app.log",
        )
        return
    messagebox.showinfo("Saved", f"Note saved for {name}.")


def load_report_note_for_client(app: Any) -> None:
    name = get_selected_report_client(app)
    if not name:
        messagebox.showwarning("Load Note", "Select a client in the Reports list first.")
        return
    client_uid, person_uid = _link_ids(app, name)
    note = get_client_note(
        name,
        loan_type=_mode(app),
        scope="effective",
        client_uid=client_uid,
        person_uid=person_uid,
    )
    set_report_note_text(app, note)
    messagebox.showinfo(
        "Loaded",
        f"Loaded note for {name}." if note else f"No note saved for {name}.",
    )


REPORT_CONTROLLER_METHODS = {
    "refresh_reports": refresh_reports,
    "open_report_generation_log": open_report_generation_log,
    "_get_selected_report_client": get_selected_report_client,
    "_get_report_note_text": get_report_note_text,
    "_set_report_note_text": set_report_note_text,
    "_save_dated_note_for_client": save_dated_note_for_client,
    "_auto_load_report_note": auto_load_report_note,
    "_save_report_note_for_client": save_report_note_for_client,
    "_load_report_note_for_client": load_report_note_for_client,
}
