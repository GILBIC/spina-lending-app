#!/usr/bin/env python3
"""Installer regression for the complete Reports Wave 80 architecture."""
from __future__ import annotations

import tempfile
from pathlib import Path

from spina_app.features.reports import install_reports_feature


def main() -> None:
    class DummyApp:
        pass

    root = Path(tempfile.mkdtemp(prefix="spina_reports_wave80_"))
    namespace = {
        "os": __import__("os"),
        "re": __import__("re"),
        "date": __import__("datetime").date,
        "datetime": __import__("datetime").datetime,
        "DATA_DIR": str(root),
        "PDF_DIR": str(root),
        "tk": __import__("tkinter"),
        "messagebox": __import__("tkinter.messagebox", fromlist=["messagebox"]),
        "_load_ledger_prefs": lambda: {},
        "_save_ledger_prefs": lambda _prefs: None,
        "_log_exc": lambda *_args, **_kwargs: None,
        "_log_suppressed_once": lambda *_args, **_kwargs: None,
        "_log_ignored": lambda *_args, **_kwargs: None,
        "pick_date": lambda *_args, **_kwargs: None,
        "pick_date_range": lambda *_args, **_kwargs: None,
        # Intentionally omit _spina__client_due_meta and _spina__fmt_client_money.
        # Reports must resolve these from modular service/utility modules even when
        # Wave 80 runs before the Wave 81 Clients installer.
        "get_client_note": lambda *_args, **_kwargs: "",
        "set_client_note": lambda *_args, **_kwargs: None,
        "get_client_notes_in_range": lambda *_args, **_kwargs: [],
        "_open_path": lambda *_args, **_kwargs: True,
        "_safe_filename_component": lambda value, fallback="", max_len=80: str(value or fallback)[:max_len],
        "_can_use_dir": lambda _path: True,
        "load_settings": lambda: {},
        "_read_json_file": lambda _path: {},
        "_write_json_atomic": lambda _path, _value: True,
        "_normalize_loan_type_value": lambda value: "7x7" if "7x7" in str(value).lower() else "Regular",
        "_sum_paid_per_day": lambda _rows: 0.0,
        "_wave74_x7_daily_interest": lambda principal: float(principal or 0) / 1000.0 * 7.0,
        "parse_advance_ranges": lambda _text: [],
        "_normalize_client_name_for_lookup": lambda value: str(value or "").strip(),
        "fmt_currency": lambda value: str(value),
    }
    assert "_spina__client_due_meta" not in namespace
    assert "_spina__fmt_client_money" not in namespace
    assert install_reports_feature(DummyApp, namespace=namespace)
    assert DummyApp._spina_reports_wave80_installed is True

    required = (
        "_build_reports_tab",
        "refresh_reports",
        "generate_pdf_selected",
        "open_report_generation_log",
        "_get_selected_report_client",
        "_get_report_note_text",
        "_set_report_note_text",
        "_save_dated_note_for_client",
        "_auto_load_report_note",
        "_save_report_note_for_client",
        "_load_report_note_for_client",
    )
    for name in required:
        assert callable(getattr(DummyApp, name, None)), name

    # Reproduce the user-visible failure: a stale installed marker exists but the
    # Generate Report callback is missing. The installer must repair the class.
    delattr(DummyApp, "generate_pdf_selected")
    DummyApp._spina_reports_wave80_installed = True
    assert install_reports_feature(DummyApp, namespace=namespace)
    assert callable(getattr(DummyApp, "generate_pdf_selected", None))

    first = {name: getattr(DummyApp, name) for name in required}
    assert install_reports_feature(DummyApp, namespace=namespace)
    for name, value in first.items():
        assert getattr(DummyApp, name) is value, name

    assert callable(namespace.get("generate_client_pdf"))
    assert callable(namespace.get("_spina_record_report_generation"))
    assert str(namespace.get("REPORT_GENERATION_LOG_CSV", "")).endswith("report_generation_logs.csv")
    print("Wave 80 Reports installer tests passed.")


if __name__ == "__main__":
    main()
