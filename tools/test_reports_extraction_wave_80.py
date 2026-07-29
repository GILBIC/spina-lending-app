#!/usr/bin/env python3
"""Static validation for the committed Reports Wave 80 architecture."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
ENGINE = ROOT / "spina_app" / "report_engine.py"
CONTROLLER = ROOT / "spina_app" / "report_controller.py"
FEATURE = ROOT / "spina_app" / "features" / "reports.py"

REPORT_METHODS = (
    "refresh_reports",
    "open_report_generation_log",
    "_get_report_note_text",
    "_set_report_note_text",
    "_save_dated_note_for_client",
    "_auto_load_report_note",
    "_get_selected_report_client",
    "_save_report_note_for_client",
    "_load_report_note_for_client",
)


def main() -> None:
    app = APP.read_text(encoding="utf-8")
    engine = ENGINE.read_text(encoding="utf-8")
    controller = CONTROLLER.read_text(encoding="utf-8")
    feature = FEATURE.read_text(encoding="utf-8")

    assert app.count("# --- BEGIN: Reports feature installer Wave 80 ---") == 1
    assert app.count("# --- END: Reports feature installer Wave 80 ---") == 1
    assert "# ==== BEGIN: SOA ADV/RANGE RENDERING PATCH ====" not in app
    assert "def generate_client_pdf(" not in app
    assert "def _spina_record_report_generation(" not in app
    assert "_configure_wave64_reports_tab" not in app
    assert "_configure_wave67_client_statement_generation" not in app
    for name in REPORT_METHODS:
        assert f"    def {name}(" not in app, name

    required_engine = (
        "def configure_report_engine_dependencies(",
        "def _parse_adv_range_any(",
        "def _collect_day_flags_for_month(",
        "def _spina_record_report_generation(",
        "def generate_client_pdf(",
        "Layout: 3 columns per page, 11 rows per column.",
        "_wave74_x7_daily_interest",
        "interest_due = (_di * float(gap)) + float(arrears)",
    )
    for token in required_engine:
        assert token in engine, token

    assert "REPORT_CONTROLLER_METHODS" in controller
    assert "fetch_report_clients(" in controller
    assert "build_report_row(" in controller
    assert "def install_reports_feature(" in feature
    assert "app_class.generate_pdf_selected = _generation.generate_pdf_selected" in feature
    assert "namespace[\"generate_client_pdf\"] = _engine.generate_client_pdf" in feature
    print("Wave 80 committed Reports extraction tests passed.")


if __name__ == "__main__":
    main()
