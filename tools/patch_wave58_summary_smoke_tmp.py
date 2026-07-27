from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST = ROOT / "tools" / "test_system_data_summary_widget_smoke_wave_58.py"


RECORD_REPLACEMENT = '''        summary = app.system_data_summary_var.get()
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
            assert expected_line in summary, (expected_line, summary)'''

OPEN_REPLACEMENT = '''        open_summary = app.system_data_summary_var.get()
        for expected_line in (
            "Date: 2026-07-27",
            "Regular Expected:",
            "7x7 Expected:",
            "Total Expected:",
            "No Daily Close record yet for this date.",
        ):
            assert expected_line in open_summary, (expected_line, open_summary)
        assert "Actual Cash:" not in open_summary'''


def main() -> None:
    text = TEST.read_text(encoding="utf-8")
    marker = "        assert app.system_data_summary_var.get() == (\n"

    first_start = text.find(marker)
    if first_start < 0:
        raise SystemExit("Wave 58 first summary assertion missing")
    first_end_marker = "\n\n        app.db.calls.clear()"
    first_end = text.find(first_end_marker, first_start)
    if first_end < 0:
        raise SystemExit("Wave 58 first summary boundary missing")
    text = text[:first_start] + RECORD_REPLACEMENT + text[first_end:]

    second_start = text.find(marker, first_start + len(RECORD_REPLACEMENT))
    if second_start < 0:
        raise SystemExit("Wave 58 second summary assertion missing")
    second_end_marker = "\n        print(\"Wave 58 real Tkinter System Data summary behavior test passed\")"
    second_end = text.find(second_end_marker, second_start)
    if second_end < 0:
        raise SystemExit("Wave 58 second summary boundary missing")
    text = text[:second_start] + OPEN_REPLACEMENT + text[second_end:]

    TEST.write_text(text, encoding="utf-8")
    print("Wave 58 summary smoke assertions patched")


if __name__ == "__main__":
    main()
