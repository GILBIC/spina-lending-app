# Wave 54 high-volume candidate report

Scanned `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py` with a minimum size of 20 lines.

Protection is based on actual calls, SQL-shaped strings, and financial arithmetic—not ordinary `pass` statements or visible UI labels.

## Safe presentation groups

| Group | Functions | Total lines | Largest members |
|---|---:|---:|---|
| data-bank | 4 | 614 | `App.refresh_data_grid` (271), `_spina_perf_refresh_data_grid` (205), `App.open_databank_close_history_dialog` (71), `App._build_data_tab` (67) |
| cash-control | 3 | 407 | `_spina_v21_cash_refresh` (169), `_spina_cashctl_build_tab` (125), `_spina_cashctl_refresh` (113) |
| clients | 3 | 399 | `App._build_clients_tab` (156), `_app_refresh_clients` (150), `RenewDialog.body` (93) |
| authentication | 2 | 245 | `App._prompt_login` (126), `App._force_change_password_dialog` (119) |
| audit | 2 | 183 | `App.refresh_audit_tab` (113), `App._build_audit_tab` (70) |
| misc | 1 | 161 | `App.__init__` (161) |
| reports | 1 | 107 | `App.refresh_reports` (107) |

## Safe presentation candidates

| Candidate | Group | Lines | Refs | UI evidence |
|---|---|---:|---:|---|
| `App.refresh_audit_tab` | audit | 113 | 6 | delete, focus, insert |
| `App._build_audit_tab` | audit | 70 | 1 | Button, Entry, Frame, Label, Notebook, Scrollbar, StringVar, Text |
| `App._prompt_login` | authentication | 126 | 3 | Button, Combobox, Entry, Frame, Label, StringVar, Toplevel, bind |
| `App._force_change_password_dialog` | authentication | 119 | 1 | Button, Entry, Frame, Label, StringVar, Toplevel, bind, destroy |
| `_spina_v21_cash_refresh` | cash-control | 169 | 1 | StringVar, delete, insert |
| `_spina_cashctl_build_tab` | cash-control | 125 | 1 | Button, Entry, Frame, Label, Scrollbar, StringVar, Treeview, column |
| `_spina_cashctl_refresh` | cash-control | 113 | 1 | StringVar, delete, insert |
| `App._build_clients_tab` | clients | 156 | 2 | Button, Combobox, Entry, Frame, Label, Scrollbar, StringVar, Treeview |
| `_app_refresh_clients` | clients | 150 | 1 | StringVar, delete, insert |
| `RenewDialog.body` | clients | 93 | 7 | BooleanVar, Button, Checkbutton, Entry, Frame, Label, StringVar, Text |
| `App.refresh_data_grid` | data-bank | 271 | 37 | Frame, Scrollbar, Treeview, bind, column, configure, destroy, focus |
| `_spina_perf_refresh_data_grid` | data-bank | 205 | 1 | Frame, Scrollbar, Treeview, bind, column, configure, destroy, focus |
| `App.open_databank_close_history_dialog` | data-bank | 71 | 2 | Button, Frame, Label, Scrollbar, Toplevel, Treeview, column, configure |
| `App._build_data_tab` | data-bank | 67 | 1 | Button, Entry, Frame, Label, StringVar, bind, pack |
| `App.__init__` | misc | 161 | 10 | Frame, Label, Notebook, StringVar, bind, configure, pack |
| `App.refresh_reports` | reports | 107 | 30 | StringVar, delete, insert |

## Protected large functions

| Candidate | Lines | Protected evidence |
|---|---:|---|
| `print_full_daily_ledger` | 3223 | execute, SQL |
| `_on_collectors_select` | 3005 | execute, print_full_daily_ledger, SQL |
| `_maybe_suggest_link_clients` | 1988 | commit, execute, principal, SQL |
| `generate_client_pdf` | 1185 | interest, principal |
| `LoanDB._create_tables` | 901 | backup, commit, connect_db, execute, executemany, SQL |
| `App.open_databank_close_dialog` | 651 | print_databank_close_report, variance, SQL |
| `_spina_v23_client_form` | 457 | interest, principal, SQL |
| `App._import_encoder_batch` | 420 | SQL |
| `_build_collectors_tab` | 347 | SQL |
| `App._build_reports_tab` | 338 | SQL |
| `LoanDB.update_client` | 299 | commit, execute, payment_amount, principal, SQL |
| `App.open_settings_dialog` | 288 | SQL |
| `_spina_save_closed_collector_route_copy` | 281 | variance |
| `refresh_clients` | 263 | renew_client, SQL |
| `_spina_dashboard_fetch_rows` | 262 | execute, due_date, interest, principal, SQL |
| `RenewDialog._compute_stats` | 259 | principal |
| `App.generate_pdf_selected` | 258 | generate_client_pdf, SQL |
| `LoanDB.delete_transactions_for_day` | 243 | commit, execute, rollback, SQL |
| `App.print_databank_close_report` | 235 | execute, variance, SQL |
| `LoanDB.renew_client` | 228 | commit, execute, rollback, run_write, SQL |
| `_spina_pg_renew_client_direct` | 226 | commit, execute, rollback, SQL |
| `App.open_databank_close_records_dialog` | 224 | print_databank_close_report, variance, SQL |
| `print_collector_route_daily_ledger` | 198 | execute, print_full_daily_ledger, SQL |
| `_spina_route_balance_like_generate_report` | 183 | interest, principal |
| `App.open_backup_history_window` | 182 | SQL |
| `LoanDB.add_client` | 181 | commit, execute, payment_amount, SQL |
| `_spina_route_adv_marker_for` | 173 | execute, SQL |
| `_spina_save_closed_collector_route_copy_same_format` | 170 | execute, print_full_daily_ledger, SQL |
| `_spina_crc_fetch_close_rows` | 167 | execute, SQL |
| `App._import_from_excel_core` | 166 | execute, SQL |
| `App.open_areas_manager` | 162 | SQL |
| `import_from_excel_with_reasons` | 149 | commit, execute, SQL |
| `App._pick_missed_reason` | 145 | SQL |
| `App.open_delete_day_dialog` | 141 | delete_transactions_for_day, execute, SQL |
| `_spina_fixed_open_archived_clients_dialog_rowid` | 137 | SQL |
