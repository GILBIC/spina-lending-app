# Cash Control modularization Wave 77

## Purpose

Wave 77 begins the next safe SPINA modularization boundary after the completed Dashboard extraction. The target is the contiguous Cash Control block immediately following the Wave 76 Dashboard installer.

This planning stage is intentionally read-only. It adds inspection and validation only; it does not modify the desktop application, PostgreSQL behavior, lending rules, or Cash Control calculations.

## Confirmed current boundary

The inspector requires exactly one Cash Control start marker and one end marker in:

`OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py`

The block currently owns:

- combined Regular, 7x7, and unclassified daily collection reads
- active-day average collection history
- 7x7 renewal-payoff estimation with interest-first allocation
- all-active-client renewal reserve rows and priority labels
- current safe amount and forecasted safe amount calculations
- Cash Control Tkinter tab construction and refresh
- role visibility
- `App.__init__`, `apply_role_access`, and `_on_mode_change` runtime wrappers

## Why this is next

Wave 76 removed the Dashboard implementation but retained compatibility globals specifically because Cash Control still consumes Dashboard and Wave 74 helpers from the monolithic file. Extracting Cash Control next will:

- remove another runtime monkey-patch chain
- eliminate the remaining Cash Control dependency on Dashboard compatibility globals
- isolate read-only database queries from Tkinter presentation
- make safe-cash calculations independently testable
- preserve the existing Dashboard, Cash Control, statement, Regular, and 7x7 behavior

## Proposed module map

### `spina_app/repositories/cash_control.py`

Own read-only database access:

- daily collection totals by normalized loan type
- active collection-day totals for an averaging window
- current-cycle 7x7 payments for payoff estimation

No database writes, schema changes, or transaction-control changes belong here.

### `spina_app/services/cash_control.py`

Own pure and reusable rules:

- percent and numeric input normalization
- Regular payoff from remaining total-to-pay balance
- 7x7 interest-aware payoff using shared Wave 74 allocation rules
- reserve row classification and sorting
- safe-now and forecast-safe calculations

The existing rules must remain unchanged:

- current available cash = cash on hand + selected-day collection
- current emergency buffer is based on current available cash
- safe now excludes forecast collection
- forecast available adds average collection × forecast days
- forecast buffer is calculated separately from forecast available cash
- reserve includes all active clients
- reserve amount defaults to principal
- expected renewal payoff includes 7x7 accrued interest

### `spina_app/tabs/cash_control.py`

Own Tkinter presentation:

- tab construction
- input variables
- summary labels
- reserve Treeview
- refresh rendering
- System-role visibility

### `spina_app/features/cash_control.py`

Own one idempotent installer:

- final `App` method bindings
- initialization hook
- role hook
- Regular/7x7 mode-change refresh hook

## Protected behavior

Wave 77 must not change:

- principal, interest, balance, renewal, offset, ADV/PASS, or 7x7 rules
- Dashboard rows, status, sorting, filters, charts, or role behavior
- Data Bank transaction writes or Daily Close behavior
- PostgreSQL compatibility, connections, transactions, or schema
- authentication, permissions, passwords, backups, reports, or Collector Route
- Cash Control labels, reserve inclusion, sorting, or safe-amount formulas

## Planned validation

The extraction stage must include:

1. exact boundary and function inventory checks
2. application and new-module compilation
3. in-memory collection-total and average-collection tests
4. Regular and 7x7 payoff tests
5. safe-now versus forecast-safe tests
6. all-active-client reserve and sorting tests
7. real Tkinter Cash Control tab smoke test
8. Wave 76 Dashboard compatibility
9. Wave 75 and Wave 74 calculation compatibility
10. `git diff --check`
11. read-only owner-authored Windows workflow

## Current planning files

- `tools/inspect_cash_control_wave_77.py`
- `.github/workflows/inspect-cash-control-wave-77.yml`
- this document

No production source is changed in the planning stage.
