#!/usr/bin/env python3
"""Focused regression coverage for the complete Clients feature Wave 81."""
from __future__ import annotations

import ast
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"

MODULES = {
    "service": ROOT / "spina_app" / "services" / "clients.py",
    "controller": ROOT / "spina_app" / "client_controller.py",
    "pictures": ROOT / "spina_app" / "client_pictures.py",
    "archive": ROOT / "spina_app" / "client_archive.py",
    "renewal": ROOT / "spina_app" / "client_renewal.py",
    "application": ROOT / "spina_app" / "client_application.py",
    "feature": ROOT / "spina_app" / "features" / "clients.py",
}


def parse_day(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value or "")[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def structural_checks() -> None:
    app = APP_PATH.read_text(encoding="utf-8")
    ast.parse(app, filename=str(APP_PATH))
    assert app.count("# --- BEGIN: Clients feature installer Wave 81 ---") == 1
    assert app.count("# --- END: Clients feature installer Wave 81 ---") == 1
    assert app.count("install_clients_feature as _wave81_install_clients_feature") == 1

    forbidden = (
        "# --- BEGIN: Clients tab picture support ---",
        "# --- BEGIN: ARCHIVED CLIENT RESTORE FIX",
        "# --- BEGIN: ARCHIVED CLIENT RESTORE ROW-ID FIX",
        "# --- BEGIN: Flexible Due Schedule rules ---",
        "# --- BEGIN: PostgreSQL TEST renew direct-write fix ---",
        "# --- BEGIN: v23 Modern Clients UI + Application Form Editor ---",
        "def _app_refresh_clients(",
        "def _app_link_selected_client(",
        "def _spina_v23_client_form(",
        "class RenewDialog(",
        "App.refresh_clients = _spina_v23_refresh_clients",
        "LoanDB.renew_client = _spina_pg_renew_client_direct",
    )
    for token in forbidden:
        assert token not in app, token

    required_by_module = {
        "service": (
            "def configure_client_service_dependencies(",
            "def _spina__client_schedule_anchor(",
            "def _spina__client_due_meta_base(",
            "def _spina__parse_flexible_due_rule(",
            "def _spina__client_due_meta(",
        ),
        "controller": (
            "def configure_client_controller_dependencies(",
            "def _app_refresh_clients(",
            "def _app_link_selected_client(",
            "def _app_import_clients_from_excel(",
            "def set_area_for_selected_clients(",
        ),
        "pictures": (
            "def configure_client_picture_dependencies(",
            "def _db_set_client_picture(",
            "def _app_refresh_client_picture_panel(",
        ),
        "archive": (
            "def configure_client_archive_dependencies(",
            "def _spina_fixed_archive_client(",
            "def _spina_fixed_restore_client_by_id(",
            "def _spina_fixed_open_archived_clients_dialog_rowid(",
        ),
        "renewal": (
            "def configure_client_renewal_dependencies(",
            "class RenewDialog(",
            "def _app_renew_client_selected(",
            "def _spina_pg_renew_client_direct(",
        ),
        "application": (
            "def configure_client_application_dependencies(",
            "def _spina_v23_client_loan_summary(",
            "def _spina_v23_client_form(",
            "def _spina_v23_add_client_dialog(",
            "def _spina_v23_on_client_edit(",
        ),
    }
    for key, path in MODULES.items():
        text = path.read_text(encoding="utf-8")
        ast.parse(text, filename=str(path))
        for token in required_by_module.get(key, ()):
            assert token in text, (key, token)


def service_behavior_checks() -> None:
    from spina_app.services import clients

    clients.configure_client_service_dependencies(
        {
            "_spina__parse_day_ymd": parse_day,
            "_spina__norm_weekday": lambda value: str(value or "")[:3].title(),
            "_spina__norm_dom": lambda value: int(value) if str(value or "").isdigit() else None,
        }
    )

    daily = {
        "payment_term": "Daily",
        "date_released": "2026-07-01",
        "pay_start_offset_days": 1,
    }
    assert clients._spina__client_due_meta(daily, as_of="2026-07-02") == ("Daily", True)

    weekly = {
        "payment_term": "Weekly",
        "date_released": "2026-07-01",
        "due_weekday": "Wed",
    }
    assert clients._spina__client_due_meta(weekly, as_of="2026-07-08") == ("Wed", True)
    assert clients._spina__client_due_meta(weekly, as_of="2026-07-09") == ("Wed", False)

    salary = {
        "payment_term": "Semi",
        "date_released": "2026-07-01",
        "flex_due_rule": "salary 5/20 window 1",
    }
    assert clients._spina__client_due_meta(salary, as_of="2026-07-04") == ("5/20 flex (±1d)", True)
    assert clients._spina__client_due_meta(salary, as_of="2026-07-07") == ("5/20 flex (±1d)", False)

    twice_weekly = {
        "payment_term": "Weekly",
        "date_released": "2026-07-01",
        "flex_due_rule": "weekly Tuesday Friday",
    }
    label, due = clients._spina__client_due_meta(twice_weekly, as_of="2026-07-03")
    assert label == "Weekly Tue/Fri"
    assert due is True


def installer_checks() -> None:
    from spina_app.features.clients import (
        CLIENTS_FEATURE_APP_METHODS,
        CLIENTS_FEATURE_DB_METHODS,
        install_clients_feature,
    )

    class FakeApp:
        pass

    class FakeLoanDB:
        def renew_client(self, *args, **kwargs):
            return "legacy-renew"

    def no_op(*args, **kwargs):
        return None

    namespace = {
        "App": FakeApp,
        "LoanDB": FakeLoanDB,
        "SPINA_POSTGRESQL_TEST_MODE": False,
        "_log_exc": no_op,
        "_log_suppressed_once": no_op,
        "_log_ignored": no_op,
        "_spina_v22_reports_colors": lambda *_args, **_kwargs: {
            "bg": "#fff", "panel": "#fff", "card": "#fff", "card2": "#fff",
            "border": "#ddd", "fg": "#111", "muted": "#666", "blue": "#00f",
            "green": "#080", "red": "#f00", "soft": "#eee", "purple": "#808",
            "orange": "#f80",
        },
        "_spina_perf_dict_rows": lambda rows: list(rows or []),
        "_spina_perf_ensure_indexes": no_op,
        "_spina_perf_norm_lt": lambda value: "7x7" if "7" in str(value) else "Regular",
        "_spina__fmt_client_money": lambda value: str(value),
        "_spina_route_notice_key": lambda *args: "key",
        "_spina_route_notice_load": lambda: {},
        "_spina_route_notice_norm_lt": lambda value: str(value or "Regular"),
        "_spina_route_notice_norm_name": lambda value: str(value or "").lower(),
        "_spina__parse_day_ymd": parse_day,
        "_spina__norm_weekday": lambda value: str(value or "")[:3].title(),
        "_spina__norm_dom": lambda value: int(value) if str(value or "").isdigit() else None,
        "_app__norm_lt_value": lambda _self, value: "7x7" if "7" in str(value) else "Regular",
        "_app__other_lt": lambda _self, value: "Regular" if "7" in str(value) else "7x7",
    }

    assert install_clients_feature(FakeApp, loan_db_cls=FakeLoanDB, namespace=namespace)
    first_app = {name: getattr(FakeApp, name) for name in CLIENTS_FEATURE_APP_METHODS}
    first_db = {name: getattr(FakeLoanDB, name) for name in CLIENTS_FEATURE_DB_METHODS}
    original_renew = FakeLoanDB.renew_client

    assert install_clients_feature(FakeApp, loan_db_cls=FakeLoanDB, namespace=namespace)
    second_app = {name: getattr(FakeApp, name) for name in CLIENTS_FEATURE_APP_METHODS}
    second_db = {name: getattr(FakeLoanDB, name) for name in CLIENTS_FEATURE_DB_METHODS}

    assert first_app == second_app
    assert first_db == second_db
    assert FakeLoanDB.renew_client is original_renew
    assert FakeApp._spina_clients_feature_wave81_installed is True
    assert FakeApp.refresh_clients.__module__ == "spina_app.features.clients"
    assert FakeApp.add_client_dialog.__module__ == "spina_app.client_application"
    assert FakeApp.renew_client_selected.__module__ == "spina_app.client_renewal"
    assert FakeApp.open_archived_clients_dialog.__module__ == "spina_app.client_archive"


def main() -> None:
    structural_checks()
    service_behavior_checks()
    installer_checks()
    print("Wave 81 complete Clients feature regressions passed")


if __name__ == "__main__":
    main()
