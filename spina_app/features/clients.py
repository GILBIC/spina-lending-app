"""Complete Clients feature installer for SPINA Wave 81."""
from __future__ import annotations

from typing import Any, Mapping, MutableMapping

CLIENTS_FEATURE_APP_METHODS = (
    "_build_clients_tab",
    "refresh_clients",
    "_schedule_refresh_clients",
    "add_client_dialog",
    "on_client_edit",
    "delete_client_selected",
    "open_client_history_dialog",
    "open_archived_clients_dialog",
    "renew_client_selected",
    "link_selected_client",
    "unlink_selected_client",
    "_maybe_suggest_link_clients",
    "export_clients_template",
    "import_clients_from_excel",
    "import_missing",
    "set_area_for_selected_clients",
    "refresh_client_picture_panel",
    "set_selected_client_picture",
    "clear_selected_client_picture",
    "_install_clients_picture_ui",
    "_is_client_new",
)

CLIENTS_FEATURE_DB_METHODS = (
    "get_all_clients",
    "get_client_info",
    "get_client_link_meta",
    "find_clients_by_person_uid",
    "get_client_uid",
    "get_client_by_uid",
    "get_client_history",
    "get_person_uid_for_client_uid",
    "get_linked_client_uids",
    "get_transaction_history_for_client_uids",
    "get_transactions_for_client_uids",
    "count_clients_in_area",
    "get_client_by_person_uid_and_loan_type",
    "get_transactions_for_client",
    "get_client_picture",
    "set_client_picture",
    "clear_client_picture",
    "archive_client",
    "restore_client",
    "restore_client_by_uid",
    "get_archived_clients",
    "restore_client_by_id",
)


def _set(namespace: MutableMapping[str, Any], name: str, value: Any) -> Any:
    namespace[name] = value
    return value


def _refresh_clients_wave81(self, *args, **kwargs):
    """Final Clients refresh: optimized rows, then profile and summary cards."""
    from spina_app.tabs import clients as clients_tab

    result = clients_tab._spina_perf_refresh_clients(self, *args, **kwargs)
    try:
        clients_tab._spina_v23_refresh_client_profile(self)
        clients_tab._spina_v23_update_client_cards(self)
    except Exception:
        pass
    return result


def install_clients_feature(
    app_cls,
    *,
    loan_db_cls=None,
    namespace: MutableMapping[str, Any] | None = None,
    log_exc=None,
    log_suppressed_once=None,
) -> bool:
    """Configure all Clients layers and install the final runtime bindings.

    Repeated calls are safe. The installer performs assignments rather than wrapping
    already-installed methods, so it cannot grow a monkey-patch chain.
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

    # Existing focused read boundaries remain the source of truth; Wave 81 owns
    # their configuration and LoanDB installation.
    from spina_app import client_queries, linked_client_queries

    client_queries.configure_client_queries_dependencies(ns)
    linked_client_queries.configure_linked_client_query_dependencies(ns)

    client_read_bindings = {
        "get_all_clients": client_queries.get_all_clients,
        "get_client_info": client_queries.get_client_info,
        "get_client_link_meta": client_queries.get_client_link_meta,
        "find_clients_by_person_uid": client_queries.find_clients_by_person_uid,
        "get_client_uid": client_queries.get_client_uid,
        "get_client_by_uid": client_queries.get_client_by_uid,
        "get_client_history": client_queries.get_client_history,
        "get_person_uid_for_client_uid": client_queries.get_person_uid_for_client_uid,
        "get_linked_client_uids": linked_client_queries.get_linked_client_uids,
        "get_transaction_history_for_client_uids": linked_client_queries.get_transaction_history_for_client_uids,
        "get_transactions_for_client_uids": linked_client_queries.get_transactions_for_client_uids,
        "count_clients_in_area": linked_client_queries.count_clients_in_area,
        "get_client_by_person_uid_and_loan_type": linked_client_queries.get_client_by_person_uid_and_loan_type,
        "get_transactions_for_client": linked_client_queries.get_transactions_for_client,
    }
    for name, callback in client_read_bindings.items():
        setattr(loan_db_cls, name, callback)
        _set(ns, f"_wave81_client_db_{name}", callback)

    # Generated Wave 81 layers contain the exact active source moved from the
    # desktop entry module.
    from spina_app import (
        client_application,
        client_archive,
        client_controller,
        client_pictures,
        client_renewal,
    )
    from spina_app.services import clients as client_services
    from spina_app.tabs import clients as clients_tab

    client_services.configure_client_service_dependencies(ns)
    _set(ns, "_spina__client_schedule_anchor", client_services._spina__client_schedule_anchor)
    _set(ns, "_spina__client_due_meta_base", client_services._spina__client_due_meta_base)
    _set(ns, "_spina__parse_flexible_due_rule", client_services._spina__parse_flexible_due_rule)
    _set(ns, "_spina__client_due_meta", client_services._spina__client_due_meta)

    client_controller.configure_client_controller_dependencies(ns)
    client_pictures.configure_client_picture_dependencies(ns)
    client_archive.configure_client_archive_dependencies(ns)
    client_renewal.configure_client_renewal_dependencies(ns)

    # Make moved callbacks visible to modules that historically consumed the
    # desktop namespace through dependency injection.
    controller_exports = (
        "_app__get_selected_client_name",
        "_app_refresh_clients",
        "_app_schedule_refresh_clients",
        "_app_delete_client_selected",
        "_app_link_selected_client",
        "_app_unlink_selected_client",
        "_app__maybe_suggest_link_clients",
        "_app_export_clients_template",
        "_app_import_clients_from_excel",
        "_app_import_missing",
        "set_area_for_selected_clients",
    )
    for name in controller_exports:
        _set(ns, name, getattr(client_controller, name))

    picture_exports = (
        "_spina__ensure_client_picture_column",
        "_spina__client_pictures_dir",
        "_spina__store_client_picture_file",
        "_spina__delete_client_picture_file",
        "_db_set_client_picture",
        "_db_clear_client_picture",
        "_app_refresh_client_picture_panel",
        "_app_set_selected_client_picture",
        "_app_clear_selected_client_picture",
    )
    for name in picture_exports:
        _set(ns, name, getattr(client_pictures, name))

    # Modern presentation palette remains shared with Reports.
    if not ns.get("_spina_v23_clients_colors") and ns.get("_spina_v22_reports_colors"):
        ns["_spina_v23_clients_colors"] = ns["_spina_v22_reports_colors"]

    # Configure the existing presentation module before configuring the modern
    # application form, whose callbacks depend on its selection/profile helpers.
    _set(ns, "_spina_v23_button", clients_tab._spina_v23_button)
    _set(ns, "_spina_v23_card", clients_tab._spina_v23_card)
    _set(ns, "_spina_v23_selected_name_lt", clients_tab._spina_v23_selected_name_lt)
    _set(ns, "_spina_v23_refresh_client_profile", clients_tab._spina_v23_refresh_client_profile)
    _set(ns, "_spina_v23_build_clients_tab", clients_tab._spina_v23_build_clients_tab)
    _set(ns, "_spina_v23_entry", clients_tab._spina_v23_entry)
    _set(ns, "_spina_v23_update_client_cards", clients_tab._spina_v23_update_client_cards)
    _set(ns, "_db_get_client_picture", clients_tab._db_get_client_picture)
    _set(ns, "_app__selected_client_name_and_lt", clients_tab._app__selected_client_name_and_lt)
    _set(ns, "_app_install_clients_picture_ui", clients_tab._app_install_clients_picture_ui)
    _set(ns, "_spina_perf_clients_rows", clients_tab._spina_perf_clients_rows)
    _set(ns, "_spina_perf_refresh_clients", clients_tab._spina_perf_refresh_clients)
    _set(ns, "_spina_route_notice_for_client", clients_tab._spina_route_notice_for_client)

    client_application.configure_client_application_dependencies(ns)
    _set(ns, "_spina_v23_client_loan_summary", client_application._spina_v23_client_loan_summary)
    _set(ns, "_spina_v23_client_form", client_application._spina_v23_client_form)
    _set(ns, "_spina_v23_add_client_dialog", client_application._spina_v23_add_client_dialog)
    _set(ns, "_spina_v23_on_client_edit", client_application._spina_v23_on_client_edit)

    # Reconfigure presentation now that the moved loan-summary callback exists.
    clients_tab.configure_clients_dependencies(ns)

    # Preserve earlier public module APIs for callers and focused regressions.
    from spina_app import (
        client_form_presentation,
        client_history_presentation,
        client_new_status,
        clients_tab_presentation,
    )

    client_form_presentation.configure_client_form_dependencies(ns)
    client_history_presentation.configure_client_history_dependencies(ns)
    clients_tab_presentation.configure_clients_tab_presentation_dependencies(ns)
    client_new_status.configure_client_new_status_dependencies(ns)

    # Database picture/archive/renewal behavior.
    loan_db_cls.get_client_picture = clients_tab._db_get_client_picture
    loan_db_cls.set_client_picture = client_pictures._db_set_client_picture
    loan_db_cls.clear_client_picture = client_pictures._db_clear_client_picture
    loan_db_cls.archive_client = client_archive._spina_fixed_archive_client
    loan_db_cls.restore_client = client_archive._spina_fixed_restore_client
    loan_db_cls.restore_client_by_uid = client_archive._spina_fixed_restore_client_by_uid
    loan_db_cls.get_archived_clients = client_archive._spina_fixed_get_archived_clients_with_id
    loan_db_cls.restore_client_by_id = client_archive._spina_fixed_restore_client_by_id
    if bool(ns.get("SPINA_POSTGRESQL_TEST_MODE", False)):
        loan_db_cls.renew_client = client_renewal._spina_pg_renew_client_direct

    # One final App binding table. No wrapper captures another App method.
    app_bindings = {
        "_build_clients_tab": clients_tab._spina_v23_build_clients_tab,
        "refresh_clients": _refresh_clients_wave81,
        "_schedule_refresh_clients": client_controller._app_schedule_refresh_clients,
        "add_client_dialog": client_application._spina_v23_add_client_dialog,
        "on_client_edit": client_application._spina_v23_on_client_edit,
        "delete_client_selected": client_controller._app_delete_client_selected,
        "open_client_history_dialog": client_history_presentation._app_open_client_history_dialog,
        "open_archived_clients_dialog": client_archive._spina_fixed_open_archived_clients_dialog_rowid,
        "renew_client_selected": client_renewal._app_renew_client_selected,
        "link_selected_client": client_controller._app_link_selected_client,
        "unlink_selected_client": client_controller._app_unlink_selected_client,
        "_maybe_suggest_link_clients": client_controller._app__maybe_suggest_link_clients,
        "export_clients_template": client_controller._app_export_clients_template,
        "import_clients_from_excel": client_controller._app_import_clients_from_excel,
        "import_missing": client_controller._app_import_missing,
        "set_area_for_selected_clients": client_controller.set_area_for_selected_clients,
        "refresh_client_picture_panel": client_pictures._app_refresh_client_picture_panel,
        "set_selected_client_picture": client_pictures._app_set_selected_client_picture,
        "clear_selected_client_picture": client_pictures._app_clear_selected_client_picture,
        "_install_clients_picture_ui": clients_tab._app_install_clients_picture_ui,
        "_is_client_new": client_new_status._is_client_new,
    }
    for name, callback in app_bindings.items():
        setattr(app_cls, name, callback)

    app_cls._spina_clients_feature_wave81_installed = True
    return True
