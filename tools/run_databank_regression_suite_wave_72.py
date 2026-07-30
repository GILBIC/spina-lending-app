from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
APP_PATH = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
SELF = Path(__file__).resolve()
EXCLUDED_PARTS = ("plan_", "inspect_", "extract_", "run_databank_regression_suite_wave_72")

# These files verify the old per-wave aliases in the desktop monolith. Wave 82
# replaces those aliases with one installer and checks the same ownership in
# test_data_bank_feature_wave_82.py. Behavior and real-Tkinter counterparts are
# deliberately not skipped.
WAVE82_REPLACED_LOCATION_TESTS = {
    "test_databank_cell_writes_wave_61.py",
    "test_databank_close_history_presentation_wave_57.py",
    "test_databank_close_records_presentation_wave_66.py",
    "test_databank_delete_day_wave_62.py",
    "test_databank_editor_presentation_wave_60.py",
    "test_databank_feature_wave_72.py",
    "test_databank_grid_presentation_wave_59.py",
    "test_databank_presentation_wave_49.py",
    "test_navigation_databank_shell_wave_29.py",
}


def main() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    wave82_active = "# --- BEGIN: Data Bank feature installer Wave 82 ---" in app_text

    candidates = set(TOOLS.glob("test_*databank*.py"))
    candidates.update(TOOLS.glob("test_data_bank*.py"))
    tests = []
    skipped = []
    for path in sorted(candidates):
        if path.resolve() == SELF:
            continue
        if any(part in path.name for part in EXCLUDED_PARTS):
            continue
        if wave82_active and path.name in WAVE82_REPLACED_LOCATION_TESTS:
            skipped.append(path)
            continue
        tests.append(path)

    assert len(tests) >= 10, [path.name for path in tests]
    if wave82_active:
        assert {path.name for path in skipped} == WAVE82_REPLACED_LOCATION_TESTS
        assert any(path.name == "test_data_bank_feature_wave_82.py" for path in tests)
        assert any(path.name == "test_data_bank_extraction_wave_82.py" for path in tests)

    failures = []
    print(f"Running {len(tests)} Data Bank regression files")
    if skipped:
        print("Wave 82 replaced source-location checks:")
        for path in skipped:
            print(f"- {path.name}")

    for path in tests:
        module = ".".join(path.relative_to(ROOT).with_suffix("").parts)
        print(f"\n=== {module} ===", flush=True)
        result = subprocess.run([sys.executable, "-m", module], cwd=ROOT, check=False)
        if result.returncode != 0:
            failures.append((path.name, result.returncode))

    print("\nExecuted:")
    for path in tests:
        print(f"- {path.name}")

    if failures:
        print("\nData Bank regression failures:")
        for name, returncode in failures:
            print(f"- {name} (exit {returncode})")
        raise SystemExit(1)

    print("\nAll applicable Data Bank regressions passed")


if __name__ == "__main__":
    main()
