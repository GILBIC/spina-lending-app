# Remove legacy Clients-tab action buttons

This document describes the safe removal path for the legacy Clients-tab action buttons shown as:

- From Transactions
- Full Ledger
- Export Template
- Import Excel

## Purpose

These actions are legacy controls in the Clients tab. They can confuse testing because the preferred flows are now the desktop-aligned Clients editor, Collector Route Daily Ledger, Reports/Statement Center, and controlled import tools.

## Safety rule

This PR does not directly delete thousands of lines from the main SPINA source. It updates the manual injector so it removes the exact legacy button creation statements when they are found and also adds a runtime fallback for dynamically-created widgets.

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

## Faster removal behavior

The injector now avoids the slow full Python AST scan that could make Command Prompt look frozen on the very large SPINA source file.

It prints progress immediately:

```text
Starting legacy Clients-tab action remover...
Reading SPINA app file...
Removing old injected blocks...
Scanning for exact legacy button lines...
Inserting runtime removal fallback...
Writing updated SPINA app file...
Done. Static legacy button lines removed: <number>
```

The tool still uses two layers:

1. Static source cleanup: it scans local app-file lines for UI statements containing the exact legacy labels and removes those button/menu creation lines.
2. Runtime fallback: it still hides/destroys any matching widget if the UI creates the buttons dynamically after startup.

## Local command after merge

Run this from the repository folder:

```bat
python tools\disable_full_daily_ledger.py
python -m py_compile "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
python "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
```

The first command prints how many static button lines were removed.

Then check:

1. In the Clients tab, these buttons should be gone: From Transactions, Full Ledger, Export Template, Import Excel.
2. Collector Route Daily Ledger should still work.
3. Notes should still appear in the collector route output.
4. Client Statement PDF should still work.
5. Normal client search/edit/renew should still work.

## Undo local injected change

Use GitHub Desktop because some PCs do not recognize `git` in Command Prompt:

1. Close SPINA.
2. Open GitHub Desktop.
3. Go to Changes.
4. Right-click the changed app file and choose Discard changes.
5. Pull origin again before rerunning the injector.

## Why not delete the huge old functions immediately?

Some old functions are very large and may still share helpers with other print/import flows. Removing the visible actions first is safer than deleting thousands of lines in one PR. After this is confirmed working, the next cleanup can remove unreachable code in smaller pieces.
