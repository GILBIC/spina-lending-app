# Remove Data Bank export controls

This document describes the safe removal path for the Data Bank export strip shown as:

- Exports
- Date Range Template
- JSONL Month
- Daily Excel Template

## Purpose

These controls are legacy export tools inside the Data Bank screen. Removing them simplifies the desktop-aligned Data Bank view.

## Safety rule

This PR does not directly delete thousands of lines from the main SPINA source. It adds a manual injector that removes the visible Data Bank export controls and disables known old callback entry points.

It does not change:

- notes storage
- note rendering logic
- Collector Route Daily Ledger
- Client Statement PDF
- loan balances
- 7x7 logic
- interest logic
- payment allocation
- report formulas or math
- database writes

## Local command after merge

Use GitHub Desktop to discard local app-file changes and pull main first. Then run this from the repository folder:

```bat
python tools\remove_databank_export_controls.py
python -m py_compile "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
python "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
```

Then check:

1. In Data Bank, these controls should be gone: Exports, Date Range Template, JSONL Month, Daily Excel Template.
2. Data Bank grid should still load.
3. Client notes should still work.
4. Collector Route Daily Ledger should still work.
5. Client Statement PDF should still work.

## Undo local injected change

Use GitHub Desktop because some PCs do not recognize `git` in Command Prompt:

1. Close SPINA.
2. Open GitHub Desktop.
3. Go to Changes.
4. Right-click the changed app file and choose Discard changes.
5. Pull origin again before rerunning the injector.
