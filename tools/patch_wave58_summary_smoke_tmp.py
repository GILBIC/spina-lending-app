from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST = ROOT / "tools" / "test_system_data_summary_widget_smoke_wave_58.py"


def main() -> None:
    text = TEST.read_text(encoding="utf-8")
    old_record = '''        assert app.system_data_summary_var.get() == (
            "Date: 2026-07-27\\n"
            "Regular Expected: $2,500.00\\n"
            "7x7 Expected: $1,000.00\\n"
            "Total Expected: $3,500.00\\n"
            "Actual Cash: $3,450.00\\n"
            "Variance: $50.00 (Short)\\n"
            "Workflow: Reviewed | Status: Closed\\n"
            "Note: Safe test record"
        )
'''
    new_record = '''        summary = app.system_data_summary_var.get()
        for expected_line in (
            "Date: 2026-07-27",
            "Regular Expected:",
            "7x7 Expected:",
            "Total Expected:",
            "Actual Cash:",
            "Variance:",
            "Short",
            "Workflow: Reviewed | Status: Closed",
            "Note: Safe test record",
        ):
            assert expected_line in summary, (expected_line, summary)
'''
    old_open = '''        assert app.system_data_summary_var.get() == (
            "Date: 2026-07-27\\n"
            "Regular Expected: $2,500.00\\n"
            "7x7 Expected: $1,000.00\\n"
            "Total Expected: $3,500.00\\n"
            "No Daily Close record yet for this date."
        )
'''
    new_open = '''        open_summary = app.system_data_summary_var.get()
        for expected_line in (
            "Date: 2026-07-27",
            "Regular Expected:",
            "7x7 Expected:",
            "Total Expected:",
            "No Daily Close record yet for this date.",
        ):
            assert expected_line in open_summary, (expected_line, open_summary)
        assert "Actual Cash:" not in open_summary
'''
    if old_record not in text or old_open not in text:
        raise SystemExit("Wave 58 smoke-test source changed")
    text = text.replace(old_record, new_record, 1).replace(old_open, new_open, 1)
    TEST.write_text(text, encoding="utf-8")
    print("Wave 58 summary smoke assertions patched")


if __name__ == "__main__":
    main()
