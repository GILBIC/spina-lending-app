# Full Dashboard modularization Wave 76

Wave 76 completes the extraction of Dashboard implementation from the large desktop entry file.

## Final architecture

- `spina_app/tabs/dashboard.py` — Tkinter presentation, filters, cards, table, and refresh views
- `spina_app/dashboard_chart_presentation.py` — Dashboard charts
- `spina_app/repositories/dashboard.py` — clients, renewals, and transaction reads
- `spina_app/services/loan_cycles.py` — release timing, due dates, balances, 7x7 allocation, status, and sorting
- `spina_app/features/dashboard.py` — one idempotent runtime installer for the desktop `App`

The desktop entry file keeps only one installer call.

## Removed from the monolithic file

- `_spina_dashboard_fetch_rows`
- Wave 74 and Wave 75 Dashboard calculation imports
- Dashboard utility imports used only by the old row loader
- Wave 28 Dashboard method wiring
- v17 modern Dashboard runtime patch
- v18 Dashboard contrast runtime patch
- v19 all-active runtime patch
- v20 final chart/runtime patch
- the late chart callback bridge

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
- run Wave 75 service compatibility
- run Wave 74 calculation compatibility
- run Wave 28 presentation compatibility
- run the Dashboard chart regression when available
- run `git diff --check`

## Merge order

Wave 76 is stacked on Wave 75. Merge PR #187 first, then retarget or merge the Wave 76 pull request into `main`.
