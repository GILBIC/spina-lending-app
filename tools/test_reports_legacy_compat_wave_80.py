#!/usr/bin/env python3
"""Verify Wave 64 and Wave 67 capabilities under the Wave 80 installer."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
PRESENTATION_PATH = ROOT / "spina_app" / "reports_tab_presentation.py"
GENERATION_PATH = ROOT / "spina_app" / "client_statement_generation.py"
FEATURE_PATH = ROOT / "spina_app" / "features" / "reports.py"
ENGINE_PATH = ROOT / "spina_app" / "report_engine.py"


def main() -> None:
    app_source = APP_PATH.read_text(encoding="utf-8")
    presentation_source = PRESENTATION_PATH.read_text(encoding="utf-8")
    generation_source = GENERATION_PATH.read_text(encoding="utf-8")
    feature_source = FEATURE_PATH.read_text(encoding="utf-8")
    engine_source = ENGINE_PATH.read_text(encoding="utf-8")

    # Wave 64 presentation remains the active Reports tab implementation.
    assert "def _build_reports_tab(" in presentation_source
    assert "configure_reports_tab_dependencies" in presentation_source
    assert "app_class._build_reports_tab = _build_reports_tab" in feature_source

    # Wave 67 statement orchestration remains active through the Wave 80 installer.
    assert "def generate_pdf_selected(" in generation_source
    assert "configure_client_statement_generation_dependencies" in generation_source
    assert (
        "app_class.generate_pdf_selected = _generation.generate_pdf_selected"
        in feature_source
    )

    # The PDF engine that Wave 67 resolves is now modular and retains the protected layout.
    assert "def generate_client_pdf(" in engine_source
    assert "Layout: 3 columns per page, 11 rows per column." in engine_source
    assert "_wave74_x7_daily_interest" in engine_source

    # The desktop entry point must use one consolidated binding instead of old aliases.
    assert app_source.count("# --- BEGIN: Reports feature installer Wave 80 ---") == 1
    assert app_source.count("# --- END: Reports feature installer Wave 80 ---") == 1
    assert "_configure_wave64_reports_tab" not in app_source
    assert "_wave64_build_reports_tab" not in app_source
    assert "_configure_wave67_client_statement_generation" not in app_source
    assert "_wave67_generate_pdf_selected" not in app_source

    print("Wave 64/67 Reports capabilities are preserved under Wave 80.")


if __name__ == "__main__":
    main()
