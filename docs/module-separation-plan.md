# SPINA module-separation planner

This document describes `tools/plan_module_separation.py`.

## Purpose

The SPINA desktop application is currently a single very large Python file. The planner creates a read-only map of the current code so future extraction work can be done in small, testable steps instead of moving thousands of lines at once.

The planner does not modify the application and does not approve any move automatically.

## What the report contains

- top-level classes and functions with line ranges and sizes
- very large definitions that need special handling
- coarse dependency signals for Tkinter, database, PDF, files, threads, spreadsheets, and images
- shared global reads and cross-definition calls
- suggested destination modules
- move-risk levels
- a small first-wave review list limited to low-risk utility/configuration candidates
- phased recommendations for later separation work

## Safety rules

- `selected_move_candidate_count` always remains `0`.
- No production source is edited.
- Business-critical areas are marked protected, including payments, balances, 7x7, interest, renewals, collectors, reports, backups, PostgreSQL, authentication, payroll, and transactions.
- Suggested modules are planning hints only and must be manually reviewed.
- Future extraction PRs must move one exact helper group at a time.

## Local use

After this PR is merged and `main` is pulled:

```bat
python tools\plan_module_separation.py --json module-separation-plan.json
```

Upload `module-separation-plan.json` for review before any production code is moved.

## Expected next process

1. Review `recommended_first_wave_review`.
2. Choose one cohesive low-risk helper group.
3. Add focused tests or before/after checks for that group.
4. Extract only that group in a separate guarded PR.
5. Repeat gradually.

## Proposed long-term layout

```text
spina_app/
  main.py
  config/
  database/
  services/
  ui/
  reports/
  utilities/
```

The final layout may change after dependency review. The planner intentionally avoids creating this package structure yet.
