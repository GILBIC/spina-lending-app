from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PERMANENT_WORKFLOW = ROOT / ".github" / "workflows" / "backup-history-presentation-wave-68.yml"
TEMPORARY_PATHS = [
    ".github/workflows/wave68-backup-history-extractor.yml",
    ".github/workflows/wave68-candidate-planner.yml",
    ".github/workflows/wave68-target-inspector.yml",
    ".github/workflows/wave68-cleanup.yml",
    "docs/wave68-backup-history-meta.json",
    "docs/wave68-backup-history-source.txt",
    "docs/wave68-candidates.json",
    "tools/apply_wave68_backup_history_extraction.py",
    "tools/inspect_wave68_backup_history.py",
    "tools/plan_wave68_candidates.py",
    "tools/finalize_wave68.py",
]

WORKFLOW_TEXT = r'''name: Backup History Presentation Wave 68

on:
  pull_request:
    types: [opened, synchronize, reopened]
    paths:
      - "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
      - "spina_app/backup_history_presentation.py"
      - "tools/test_backup_history_presentation_wave_68.py"
      - "tools/test_backup_history_widget_smoke_wave_68.py"
      - "tools/test_long_task_presentation_wave_42.py"
      - "architecture-map.json"
      - "docs/architecture/**"
      - ".github/workflows/backup-history-presentation-wave-68.yml"
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: backup-history-presentation-wave-68-${{ github.event.pull_request.number || github.ref }}
  cancel-in-progress: true

jobs:
  validate:
    if: github.event_name != 'pull_request' || github.head_ref == 'agent/high-volume-wave-68'
    runs-on: [self-hosted, Windows, X64]
    timeout-minutes: 120
    steps:
      - name: Check out exact PR head
        uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.head.sha || github.sha }}
          fetch-depth: 0
          show-progress: false

      - name: Compile application, module, tests, and package
        shell: cmd
        run: |
          python -m py_compile OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py
          python -m py_compile spina_app\backup_history_presentation.py
          python -m py_compile tools\test_backup_history_presentation_wave_68.py
          python -m py_compile tools\test_backup_history_widget_smoke_wave_68.py
          python -m py_compile tools\test_long_task_presentation_wave_42.py
          python -m compileall -q spina_app

      - name: Run Wave 68 exact structural regression
        shell: cmd
        run: python -m tools.test_backup_history_presentation_wave_68

      - name: Run Wave 68 real Tkinter regression
        shell: cmd
        run: python -m tools.test_backup_history_widget_smoke_wave_68

      - name: Run protected long-task regression
        shell: cmd
        run: python tools\test_long_task_presentation_wave_42.py

      - name: Validate permanent architecture map
        uses: ./.github/actions/architecture-map-check

      - name: Run repository audits
        shell: cmd
        run: |
          if not exist artifacts mkdir artifacts
          python tools\redundancy_audit.py OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py --json artifacts\wave-68-redundancy.json
          python tools\spina_quality_audit.py OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py --json artifacts\wave-68-quality.json

      - name: Upload Wave 68 reports
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: backup-history-presentation-wave-68-reports
          path: artifacts/wave-68-*.json
          if-no-files-found: warn
'''


def main() -> None:
    for relative in TEMPORARY_PATHS:
        path = ROOT / relative
        if path.exists():
            path.unlink()
    PERMANENT_WORKFLOW.write_text(WORKFLOW_TEXT, encoding="utf-8")
    print("Wave 68 temporary files removed and permanent workflow written")


if __name__ == "__main__":
    main()
