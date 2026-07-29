# Reports modularization Wave 80

Wave 80 completes the active Reports feature boundary without changing report calculations or layout.

## Final module ownership

- `spina_app/repositories/reports.py` — read-only client, loan-type, and link metadata access
- `spina_app/services/reports.py` — loan labels, linked-type labels, report rows, and summary text
- `spina_app/report_controller.py` — list refresh, report notes, selected client, and report-log opening
- `spina_app/reports_tab_presentation.py` — active Reports tab construction from Wave 64
- `spina_app/client_statement_generation.py` — asynchronous statement generation orchestration from Wave 67
- `spina_app/report_engine.py` — SOA PDF rendering, ADV/reason parsing, report counters/logs, and fixed-principal 7x7 calculations
- `spina_app/features/reports.py` — one idempotent installer and compatibility binding point

## Preserved behavior

- three statement columns per page
- eleven payment rows per statement column
- manual Start/End date range
- current cycle fallback only when Start is blank
- Regular and legacy Emergency/7x7 labels
- shared/effective report notes using stable client/person IDs
- ADV coverage shown on covered dates, not the original payment date
- reason text and optional color tokens
- one effective payment per day
- report-generation JSON, JSONL, and CSV tracking
- fixed daily 7x7 interest based on the original principal
- interest-first allocation with gap-day accrual and arrears carry

## Guarded extraction

`tools/apply_reports_modularization_wave_80.py` removes the nine active Reports methods from `App`, moves the marked SOA engine block into `spina_app/report_engine.py`, removes the separate Wave 64 and Wave 67 runtime bindings, and inserts one Wave 80 installer. The transformation is applied twice in validation to prove idempotence.

## Validation

The Wave 80 workflow compiles the staged and generated architectures, runs Reports layer/installer/extraction regressions, reruns earlier Reports presentation and statement orchestration tests, protects Collector Route, and reruns Wave 75/Wave 74 plus fixed-principal 7x7 tests before publishing only the validated desktop file and report engine.
