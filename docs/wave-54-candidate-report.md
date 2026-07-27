# Wave 54 high-volume candidate report

Scanned `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py` with a minimum size of 90 lines.

The planner is intentionally conservative. `protected` candidates are excluded from Wave 54 even when their architecture-map risk looks UI-heavy.

| Rank | Candidate | Lines | Class | Refs | Bindings | UI evidence | Review flags |
|---:|---|---:|---|---:|---:|---|---|

## Protected large functions

| Candidate | Lines | Protected evidence |
|---|---:|---|
| `print_full_daily_ledger` | 3223 | 7x7, adv, advance, balance, execute, full_daily_ledger, pass, payment, pdf, postgres |
| `_on_collectors_select` | 3005 | 7x7, adv, advance, balance, collector_route_daily_ledger, execute, full_daily_ledger, interest, pass, payment |
| `_maybe_suggest_link_clients` | 1988 | 7x7, backup, balance, commit, due_date, execute, interest, offset, pass, payment |
| `generate_client_pdf` | 1185 | 7x7, adv, balance, due_date, interest, offset, pass, payment, pdf, principal |
| `LoanDB._create_tables` | 901 | 7x7, backup, balance, commit, connect_db, day_close, due_date, execute, executemany, interest |
| `App.open_databank_close_dialog` | 651 | 7x7, balance, close_day, day_close, pass, password, reopen, report, role |
| `_spina_v23_client_form` | 457 | 7x7, balance, interest, offset, pass, payment, principal, renew |
| `App._import_encoder_batch` | 420 | 7x7, adv, advance, pass, payment, pdf, transaction |
| `App._import_from_excel_entry_worker` | 397 | pass, payment, report, transaction |
| `_build_collectors_tab` | 347 | collector_route_daily_ledger, pass |
| `App._build_reports_tab` | 338 | pass, payment, pdf, principal, report |
| `LoanDB.update_client` | 299 | 7x7, commit, due_date, execute, interest, offset, pass, payment, principal, transaction |
| `App.open_settings_dialog` | 288 | close_day, pass, pdf, report, statement |
| `_spina_save_closed_collector_route_copy` | 281 | 7x7, day_close, pass, payment, pdf, report, restore |
| `App.refresh_data_grid` | 271 | pass, payment, transaction |
| `refresh_clients` | 263 | 7x7, due_date, interest, offset, pass, payment, principal, reloan, renew, report |
| `_spina_dashboard_fetch_rows` | 262 | 7x7, due_date, execute, interest, offset, pass, payment, principal, renew, sqlite |
| `RenewDialog._compute_stats` | 259 | 7x7, adv, balance, interest, offset, pass, payment, principal, renew, report |
| `App.generate_pdf_selected` | 258 | offset, pass, payment, pdf, renew, report, statement |
| `LoanDB.delete_transactions_for_day` | 243 | 7x7, backup, balance, commit, day_close, execute, pass, payment, rollback, transaction |
| `App.print_databank_close_report` | 235 | 7x7, balance, day_close, execute, pass, pdf, reopen, report, transaction |
| `LoanDB.renew_client` | 228 | 7x7, commit, due_date, execute, interest, offset, pass, payment, principal, reloan |
| `_spina_pg_renew_client_direct` | 226 | 7x7, commit, due_date, execute, interest, offset, pass, payment, postgres, principal |
| `App.open_databank_close_records_dialog` | 224 | 7x7, balance, day_close, report |
| `_spina_perf_refresh_data_grid` | 205 | 7x7, pass, payment, transaction |
