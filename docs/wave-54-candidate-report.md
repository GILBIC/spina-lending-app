# Wave 54 high-volume candidate report

Scanned `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py` with a minimum size of 90 lines.

Protection is based on actual calls, SQL-shaped strings, and financial arithmetic—not ordinary `pass` statements or visible UI labels.

| Rank | Candidate | Lines | Class | Refs | Bindings | UI evidence | Review flags |
|---:|---|---:|---|---:|---:|---|---|
| 1 | `_spina_v21_cash_refresh` | 169 | ui-candidate | 1 | 0 | StringVar, delete, insert | none |
| 2 | `_spina_perf_refresh_data_grid` | 205 | ui-candidate | 1 | 0 | Frame, Scrollbar, Treeview, bind, column, configure, destroy, focus | none |
| 3 | `_app_refresh_clients` | 150 | ui-candidate | 1 | 0 | StringVar, delete, insert | none |
| 4 | `_spina_cashctl_build_tab` | 125 | ui-candidate | 1 | 0 | Button, Entry, Frame, Label, Scrollbar, StringVar, Treeview, column | none |
| 5 | `App._force_change_password_dialog` | 119 | ui-candidate | 1 | 0 | Button, Entry, Frame, Label, StringVar, Toplevel, bind, destroy | none |
| 6 | `_spina_cashctl_refresh` | 113 | ui-candidate | 1 | 0 | StringVar, delete, insert | none |
| 7 | `App.refresh_audit_tab` | 113 | ui-candidate | 6 | 0 | delete, focus, insert | none |
| 8 | `App.refresh_data_grid` | 271 | ui-candidate | 37 | 2 | Frame, Scrollbar, Treeview, bind, column, configure, destroy, focus | none |
| 9 | `App.__init__` | 161 | ui-candidate | 10 | 5 | Frame, Label, Notebook, StringVar, bind, configure, pack | none |
| 10 | `App._build_clients_tab` | 156 | ui-candidate | 2 | 2 | Button, Combobox, Entry, Frame, Label, Scrollbar, StringVar, Treeview | none |
| 11 | `App._prompt_login` | 126 | ui-candidate | 3 | 1 | Button, Combobox, Entry, Frame, Label, StringVar, Toplevel, bind | none |
| 12 | `App.refresh_reports` | 107 | ui-candidate | 30 | 1 | StringVar, delete, insert | none |
| 13 | `RenewDialog.body` | 93 | ui-candidate | 7 | 2 | BooleanVar, Button, Checkbutton, Entry, Frame, Label, StringVar, Text | none |
| 14 | `App._import_from_excel_entry_worker` | 397 | filesystem-review | 1 | 0 | none | replace |
| 15 | `export_range_template` | 179 | filesystem-review | 1 | 0 | Button, Entry, Frame, Label, Radiobutton, StringVar, Toplevel, bind | asksaveasfilename |
| 16 | `_spina__parse_flexible_due_rule` | 164 | support-review | 0 | 0 | none | none |
| 17 | `_collect_day_flags_for_month` | 145 | support-review | 1 | 0 | none | none |
| 18 | `_spina_record_report_generation` | 142 | filesystem-review | 1 | 0 | none | makedirs, open, write |
| 19 | `_collectors_save_inline_edit` | 110 | filesystem-review | 1 | 0 | focus | open |
| 20 | `_on_collectors_tree_click` | 101 | filesystem-review | 1 | 0 | focus | remove |
| 21 | `_on_collectors_tree_click` | 92 | filesystem-review | 1 | 0 | focus | remove |
| 22 | `App._build_header` | 169 | filesystem-review | 1 | 1 | Button, Frame, Label, bind, grid, pack | copy, open |
| 23 | `_load_client_notes` | 160 | filesystem-review | 4 | 0 | none | open, replace |
| 24 | `App._begin_cell_edit` | 142 | filesystem-review | 2 | 0 | bind, destroy, heading, insert, place | replace |
| 25 | `parse_advance_ranges` | 108 | support-review | 9 | 0 | none | none |
| 26 | `_spina_cashctl_reserve_rows` | 95 | filesystem-review | 3 | 0 | StringVar | replace |
| 27 | `App.apply_role_access` | 137 | support-review | 3 | 4 | none | none |
| 28 | `App._setup_style` | 137 | support-review | 2 | 1 | configure | none |

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
