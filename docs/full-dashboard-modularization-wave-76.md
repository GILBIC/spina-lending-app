# Full Dashboard modularization Wave 76

Wave 76 completes the extraction of Dashboard implementation from the large desktop entry file.

## Final architecture

- `spina_app/tabs/dashboard.py` — Tkinter presentation, filters, cards, table, and refresh views
- `spina_app/dashboard_chart_presentation.py` — Dashboard charts
- `spina_app/repositories/dashboard.py` — clients, renewals, and transaction reads
- `spina_app/services/loan_cycles.py` — release timing, due dates, balances, 7x7 allocation, status, and sorting
- `spina_app/features/dashboard.py` — one idempotent runtime installer for the desktop `App`

The desktop entry file keeps one installer call and a small compatibility import bridge for helpers still used by Cash Control, statements, and older fallback paths.

## Removed from the monolithic file

- the `_spina_dashboard_fetch_rows` implementation
- Dashboard-only Wave 74 and Wave 75 calculation imports
- Dashboard utility imports used only by the old row loader
- Wave 28 Dashboard method wiring
- v17 modern Dashboard runtime patch
- v18 Dashboard contrast runtime patch
- v19 all-active runtime patch
- v20 final chart/runtime patch
- the late chart callback bridge

## Compatibility bridge retained

The main file imports, but does not implement, the following shared helpers because non-Dashboard features still reference them:

- 7x7 payment allocation, thousand tiers, and daily interest aliases
- Dashboard money and date formatting helpers
- the rounded-rectangle presentation helper used by Cash Control
- `fetch_dashboard_rows` under the legacy `_spina_dashboard_fetch_rows` fallback name

Regression checks protect these aliases from being accidentally removed in later waves.

## Preserved behavior

- only active clients appear
- payments before the current release or renewal cycle are excluded
- Regular legacy totals normalize to principal plus fixed interest
- 7x7 interest stays fixed from the recorded principal for the loan cycle
- 7x7 payments cover interest first and principal second
- renewal due dates preserve the original cycle length
- final v20 refresh and table population remain active
- final v19 all-active filtering remains active
- role visibility, theme refresh, and mode-switch behavior remain installed

## Validation

- compile every Dashboard layer and the desktop application
- apply the guarded extraction twice to prove idempotence
- run an in-memory database integration test
- verify Regular, renewed, and fixed-interest 7x7 rows
- verify the feature installer is idempotent
- verify shared compatibility imports used outside Dashboard
- run Wave 75 service compatibility
- run Wave 74 calculation compatibility
- run Wave 28 presentation compatibility
- run Wave 51 chart compatibility
- run `git diff --check`

## Merge order

Wave 76 is stacked on Wave 75. Merge PR #187 first, then retarget or merge the Wave 76 pull request into `main`.