"""Complete Data Bank feature installer for SPINA Wave 82."""
from __future__ import annotations

from typing import Any, MutableMapping

DATA_BANK_DB_METHODS = (
    "_log_transaction_history",
    "get_databank_daily_total",
    "get_databank_day_close",
    "is_databank_day_closed",
    "_append_databank_day_close_history",
    "list_databank_day_close_history",
    "list_databank_day_collectors",
    "get_databank_day_collector_totals",
    "replace_databank_day_collectors",
    "set_databank_day_close",
    "reopen_databank_day",
    "set_databank_day_workflow",
    "list_databank_day_close_records",
    "add_or_update_transaction",
    "delete_transaction",
    "delete_transactions_for_day",
    "get_transaction",
    "get_transaction_by_uid",
    "add_or_update_transaction_by_uid",
    "import_missing_clients_from_transactions",
)

DATA_BANK_APP_METHODS = (
    "_build_data_tab",
    "refresh_data_grid",
    "goto_current_month",
    "prev_month",
    "next_month",
    "_begin_cell_edit",
    "_save_cell_edit",
    "delete_selected_cell",
    "_mark_missed_for_selected",
    "open_delete_day_dialog",
    "open_databank_close_dialog",
    "open_databank_close_history_dialog",
    "open_databank_close_records_dialog",
    "print_databank_close_report",
    "export_range_template",
    "run_auto_daily_close",
    "_schedule_auto_daily_close",
    "save_closed_collector_route_copy",
    "_audit_money_text",
    "_audit_parse_date_filters",
    "_audit_set_today",
    "_audit_set_last7",
    "_audit_set_all",
    "_audit_tree_factory",
    "_audit_set_detail_text",
    "_audit_show_selected",
)


def _set(namespace: MutableMapping[str, Any], name: str, value: Any) -> Any:
    namespace[name] = value
    return value


def _db_close_bucket(self, loan_type=None):
    from spina_app.services.data_bank import combined_close_bucket
    return combined_close_bucket(loan_type)


def _db_normalize_workflow(self, workflow_status, variance=0.0, is_closed=True):
    from spina_app.services.data_bank import normalize_close_workflow
    return normalize_close_workflow(workflow_status, variance=variance, is_closed=is_closed)


def _db_variance_status(self, variance):
    from spina_app.services.data_bank import variance_status
    return variance_status(variance)


def install_data_bank_feature(
    app_cls,
    *,
    loan_db_cls=None,
    namespace: MutableMapping[str, Any] | None = None,
    log_exc=None,
    log_suppressed_once=None,
) -> bool:
    """Configure all Data Bank layers and install one final runtime boundary.

    Repeated calls refresh dependencies and assignments without growing wrapper
    chains. Only the once-per-class auto-close startup hook wraps ``App.__init__``.
    """
    if app_cls is None:
        return False

    ns: MutableMapping[str, Any] = namespace if namespace is not None else {}
    if loan_db_cls is None:
        loan_db_cls = ns.get("LoanDB")
    if loan_db_cls is None:
        return False

    if log_exc is not None:
        ns["_log_exc"] = log_exc
    if log_suppressed_once is not None:
        ns["_log_suppressed_once"] = log_suppressed_once

    from spina_app.repositories import data_bank as repository
    from spina_app import (
        audit_presentation,
        data_bank_audit,
        data_bank_auto_close,
        data_bank_exports,
        databank_cell_writes,
        databank_close_history_presentation,
        databank_close_records_presentation,
        databank_delete_day,
        databank_editor_presentation,
        databank_feature,
        databank_grid_presentation,
        databank_presentation,
        import_log_presentation,
        system_data_presentation,
        system_data_summary_presentation,
    )
    from spina_app.tabs import data_bank_shell

    repository.configure_data_bank_repository_dependencies(ns)
    data_bank_audit.configure_data_bank_audit_dependencies(ns)
    data_bank_exports.configure_data_bank_export_dependencies(ns)
    data_bank_auto_close.configure_data_bank_auto_close_dependencies(ns)

    loan_db_cls._databank_day_close_bucket = _db_close_bucket
    loan_db_cls._dayclose_norm_workflow = _db_normalize_workflow
    loan_db_cls._dayclose_variance_status = _db_variance_status
    for name in DATA_BANK_DB_METHODS:
        setattr(loan_db_cls, name, getattr(repository, name))

    # Compatibility globals required by the existing Wave 72 controller.
    _set(ns, "_spina_perf_month_transactions", repository._spina_perf_month_transactions)
    _set(ns, "_spina_auto_close_after_days_value", data_bank_auto_close._spina_auto_close_after_days_value)
    _set(ns, "_spina_auto_close_candidate_dates", data_bank_auto_close._spina_auto_close_candidate_dates)
    _set(ns, "import_from_excel_with_reasons", databank_feature.import_from_excel_with_reasons)
    _set(ns, "_spina_perf_refresh_data_grid", databank_feature._spina_perf_refresh_data_grid)
    _set(ns, "_spina_auto_close_one_day", databank_feature._spina_auto_close_one_day)
    _set(ns, "_spina_run_auto_daily_close", databank_feature._spina_run_auto_daily_close)
    _set(ns, "_spina_save_closed_collector_route_copy", databank_feature._spina_save_closed_collector_route_copy)

    # Configure the controller after the final Clients, Reports, route, theme and
    # navigation dependencies are available at the end of the desktop module.
    databank_feature.configure_databank_feature_dependencies(ns)
    audit_presentation.configure_audit_presentation_dependencies(ns)
    system_data_presentation.configure_system_data_presentation_dependencies(ns)
    databank_close_history_presentation.configure_databank_close_history_presentation_dependencies(ns)
    system_data_summary_presentation.configure_system_data_summary_dependencies(ns)
    databank_grid_presentation.configure_databank_grid_dependencies(ns)
    databank_editor_presentation.configure_databank_editor_dependencies(ns)
    databank_cell_writes.configure_databank_cell_write_dependencies(ns)
    databank_delete_day.configure_databank_delete_day_dependencies(ns)
    databank_close_records_presentation.configure_databank_close_records_dependencies(ns)
    import_log_presentation.configure_import_log_dependencies(ns)
    data_bank_shell.configure_data_bank_shell_dependencies(
        log_suppressed_once=ns.get("_log_suppressed_once"),
        log_ignored=ns.get("_log_ignored"),
    )

    # Capture non-Data-Bank originals only once. Reinstalling must not capture the
    # already wrapped callbacks and create recursion.
    if not hasattr(app_cls, "_spina_data_bank_wave82_base_update_toolbar"):
        app_cls._spina_data_bank_wave82_base_update_toolbar = getattr(app_cls, "_update_data_toolbar", None)
    if not hasattr(app_cls, "_spina_data_bank_wave82_base_apply_theme"):
        app_cls._spina_data_bank_wave82_base_apply_theme = getattr(app_cls, "_apply_ui_theme", None)

    _set(ns, "_spina_v15_orig_refresh_data_grid", databank_grid_presentation.refresh_data_grid)
    _set(ns, "_spina_v16_prev_refresh_data_grid", databank_presentation._spina_v15_refresh_data_grid)
    _set(ns, "_spina_v15_orig_update_data_toolbar", app_cls._spina_data_bank_wave82_base_update_toolbar)
    _set(ns, "_spina_v15_orig_apply_theme", app_cls._spina_data_bank_wave82_base_apply_theme)
    databank_presentation.configure_databank_presentation_dependencies(ns)

    app_bindings = {
        "_clear_preview": databank_feature._clear_preview,
        "_get_databank_focus_date": databank_feature._get_databank_focus_date,
        "_show_system_data_tab": databank_feature._show_system_data_tab,
        "_hide_system_data_tab": databank_feature._hide_system_data_tab,
        "_system_data_open_close": databank_feature._system_data_open_close,
        "_system_data_open_history": databank_feature._system_data_open_history,
        "_system_data_open_records": databank_feature._system_data_open_records,
        "_system_data_print_report": databank_feature._system_data_print_report,
        "_load_collectors_route_map": databank_feature._load_collectors_route_map,
        "_build_databank_collector_defaults_for_date": databank_feature._build_databank_collector_defaults_for_date,
        "print_databank_close_report": databank_feature.print_databank_close_report,
        "open_databank_close_dialog": databank_feature.open_databank_close_dialog,
        "on_day_double": databank_feature.on_day_double,
        "_start_edit": databank_feature._start_edit,
        "_import_from_excel_entry": databank_feature._import_from_excel_entry,
        "_import_from_excel_entry_worker": databank_feature._import_from_excel_entry_worker,
        "_import_encoder_batch": databank_feature._import_encoder_batch,
        "_import_from_excel_core": databank_feature._import_from_excel_core,
        "_build_audit_tab": audit_presentation._build_audit_tab,
        "refresh_audit_tab": audit_presentation.refresh_audit_tab,
        "_build_system_data_tab": system_data_presentation._build_system_data_tab,
        "open_databank_close_history_dialog": databank_close_history_presentation.open_databank_close_history_dialog,
        "_system_data_get_date": system_data_summary_presentation._system_data_get_date,
        "_system_data_use_focus_date": system_data_summary_presentation._system_data_use_focus_date,
        "_system_data_refresh_summary": system_data_summary_presentation._system_data_refresh_summary,
        "goto_current_month": databank_grid_presentation.goto_current_month,
        "prev_month": databank_grid_presentation.prev_month,
        "next_month": databank_grid_presentation.next_month,
        "_pick_missed_reason": databank_editor_presentation._pick_missed_reason,
        "_walk_widgets": databank_editor_presentation._walk_widgets,
        "_begin_cell_edit": databank_editor_presentation._begin_cell_edit,
        "_remember_cell_click": databank_editor_presentation._remember_cell_click,
        "_save_cell_edit": databank_cell_writes._save_cell_edit,
        "delete_selected_cell": databank_cell_writes.delete_selected_cell,
        "_mark_missed_for_selected": databank_cell_writes._mark_missed_for_selected,
        "open_delete_day_dialog": databank_delete_day.open_delete_day_dialog,
        "open_databank_close_records_dialog": databank_close_records_presentation.open_databank_close_records_dialog,
        "_show_import_log_window": import_log_presentation._show_import_log_window,
        "_looks_like_data_grid": data_bank_shell._looks_like_data_grid,
        "_locate_data_tree": data_bank_shell._locate_data_tree,
        "_ensure_databank_edit_bindings": data_bank_shell._ensure_databank_edit_bindings,
        "_show_audit_tab": data_bank_shell._show_audit_tab,
        "_hide_audit_tab": data_bank_shell._hide_audit_tab,
        "_resize_databank_columns": data_bank_shell._resize_databank_columns,
        "_build_data_tab": databank_presentation._spina_v15_build_data_tab,
        "_setup_databank_styles": databank_presentation._spina_v15_setup_databank_styles,
        "_update_databank_summary_cards": databank_presentation._spina_v15_update_databank_cards,
        "refresh_data_grid": databank_feature._spina_perf_refresh_data_grid,
        "_update_data_toolbar": databank_presentation._spina_v15_update_data_toolbar,
        "_apply_ui_theme": databank_presentation._spina_v15_apply_ui_theme,
        "export_range_template": data_bank_exports.export_range_template,
        "run_auto_daily_close": databank_feature._spina_run_auto_daily_close,
        "_schedule_auto_daily_close": data_bank_auto_close._spina_schedule_auto_daily_close,
        "save_closed_collector_route_copy": databank_feature._spina_save_closed_collector_route_copy,
        "_audit_money_text": data_bank_audit._audit_money_text,
        "_audit_parse_date_filters": data_bank_audit._audit_parse_date_filters,
        "_audit_set_today": data_bank_audit._audit_set_today,
        "_audit_set_last7": data_bank_audit._audit_set_last7,
        "_audit_set_all": data_bank_audit._audit_set_all,
        "_audit_tree_factory": data_bank_audit._audit_tree_factory,
        "_audit_set_detail_text": data_bank_audit._audit_set_detail_text,
        "_audit_show_selected": data_bank_audit._audit_show_selected,
    }
    for name, callback in app_bindings.items():
        setattr(app_cls, name, callback)

    for name in (
        "_spina_v15_palette", "_spina_v15_setup_databank_styles",
        "_spina_v15_update_databank_cards", "_spina_v16_apply_bigger_payment_grid",
    ):
        _set(ns, name, getattr(databank_presentation, name))

    if not bool(getattr(app_cls, "_spina_data_bank_wave82_init_wrapped", False)):
        original_init = app_cls.__init__

        def _wave82_app_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            try:
                self._schedule_auto_daily_close()
            except Exception as exc:
                logger = ns.get("_log_exc")
                if callable(logger):
                    logger("auto_daily_close.init", exc)

        _wave82_app_init.__name__ = "_wave82_app_init"
        app_cls.__init__ = _wave82_app_init
        app_cls._spina_data_bank_wave82_init_wrapped = True

    app_cls._spina_data_bank_feature_wave82_installed = True
    return True
