#!/usr/bin/env python3
"""Structural proof for complete Data Bank extraction Wave 82."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULES = {
    "repository": ROOT / "spina_app" / "repositories" / "data_bank.py",
    "audit": ROOT / "spina_app" / "data_bank_audit.py",
    "exports": ROOT / "spina_app" / "data_bank_exports.py",
    "auto_close": ROOT / "spina_app" / "data_bank_auto_close.py",
    "service": ROOT / "spina_app" / "services" / "data_bank.py",
    "feature": ROOT / "spina_app" / "features" / "data_bank.py",
}

DB_METHODS = (
    "_log_transaction_history", "get_databank_daily_total", "get_databank_day_close",
    "is_databank_day_closed", "_append_databank_day_close_history",
    "list_databank_day_close_history", "list_databank_day_collectors",
    "get_databank_day_collector_totals", "replace_databank_day_collectors",
    "set_databank_day_close", "reopen_databank_day", "set_databank_day_workflow",
    "list_databank_day_close_records", "add_or_update_transaction",
    "delete_transaction", "delete_transactions_for_day", "get_transaction",
    "get_transaction_by_uid", "add_or_update_transaction_by_uid",
    "import_missing_clients_from_transactions",
)
AUDIT_METHODS = (
    "_audit_money_text", "_audit_parse_date_filters", "_audit_set_today",
    "_audit_set_last7", "_audit_set_all", "_audit_tree_factory",
    "_audit_set_detail_text", "_audit_show_selected",
)


def main() -> None:
    app = APP.read_text(encoding="utf-8")
    ast.parse(app, filename=str(APP))

    assert app.count("# --- BEGIN: Data Bank feature installer Wave 82 ---") == 1
    assert app.count("# --- END: Data Bank feature installer Wave 82 ---") == 1
    assert app.count("install_data_bank_feature as _wave82_install_data_bank_feature") == 1

    forbidden = (
        "_wave72_databank_feature",
        "# --- Wave 54 Audit presentation wiring ---",
        "# Wave 57: Data Bank Close History dialog presentation.",
        "# Wave 59: Data Bank month navigation and grid presentation.",
        "# Wave 60: Data Bank inline editor and missed-reason presentation.",
        "# Wave 61: Data Bank cell write actions.",
        "# Wave 62: Data Bank Delete Day destructive workflow.",
        "# Wave 66: Data Bank close-records presentation.",
        "# --- BEGIN: Configurable Auto Daily Close ---",
        "# --- BEGIN: v15 modern Data Bank UI ---",
        "# --- BEGIN: v16 bigger Data Bank payment grid tuning ---",
        "App.refresh_data_grid =",
        "setattr(App, \"refresh_data_grid\"",
        "def _spina_perf_month_transactions(",
        "def export_range_template(",
        "def _spina_auto_close_after_days_value(",
        "def _spina_auto_close_candidate_dates(",
        "def _spina_schedule_auto_daily_close(",
    )
    for token in forbidden:
        assert token not in app, token

    for name in DB_METHODS + (
        "_databank_day_close_bucket", "_dayclose_norm_workflow", "_dayclose_variance_status",
    ):
        assert f"    def {name}(" not in app, name
    for name in AUDIT_METHODS:
        assert f"    def {name}(" not in app, name

    # Shared helpers are intentionally retained because Clients Wave 81 uses them.
    assert "def _spina_perf_ensure_indexes(" in app
    assert "def _spina_perf_norm_lt(" in app
    assert "App._month_label = _wave29_nav_month_label" in app
    assert "from spina_app.navigation import (" in app
    assert "from spina_app.tabs.data_bank_shell import (" not in app

    for path in MODULES.values():
        text = path.read_text(encoding="utf-8")
        ast.parse(text, filename=str(path))

    repository = MODULES["repository"].read_text(encoding="utf-8")
    for name in DB_METHODS:
        assert f"def {name}(" in repository, name
    assert "def _spina_perf_month_transactions(" in repository

    audit = MODULES["audit"].read_text(encoding="utf-8")
    for name in AUDIT_METHODS:
        assert f"def {name}(" in audit, name

    exports = MODULES["exports"].read_text(encoding="utf-8")
    assert "def export_range_template(" in exports

    auto = MODULES["auto_close"].read_text(encoding="utf-8")
    for name in (
        "_spina_auto_close_after_days_value",
        "_spina_auto_close_candidate_dates",
        "_spina_schedule_auto_daily_close",
    ):
        assert f"def {name}(" in auto, name

    print("Wave 82 Data Bank extraction structure regressions passed")


if __name__ == "__main__":
    main()
