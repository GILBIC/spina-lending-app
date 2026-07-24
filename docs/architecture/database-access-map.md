# SPINA Database and File Access Map

Generated from commit `f15b4145a9a262b3e1f61cab271db2ebc75091bf`.

Scanned **131 Python files**, **70,799 lines**, and **2,147 symbols**.

> This is a static architecture map. Runtime callbacks and dynamic monkey patches can still require desktop testing.

## Detected database tables

### `Client`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v23_on_client_edit` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:42879 — risk `financial_calculation`.

### `Data`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.print_databank_close_report` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:10371 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_delete_day_dialog` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:13702 — risk `authentication`.

### `Excel`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._build_data_tab` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:16780 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._import_from_excel_entry` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:18355 — risk `reports`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._import_from_excel_core` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:19555 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:24347 — risk `authentication`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.export_monthly_template` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:24659 — risk `database_read`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.export_clients_template` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:25512 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.export_range_template` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:25548 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.export_range_template` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:26343 — risk `database_read`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.import_from_excel_with_reasons` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:26527 — risk `database_write`.

### `Generate`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_save_closed_collector_route_copy` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:39768 — risk `financial_calculation`.

### `IF`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_cilog_fetch_rows` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:38372 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._create_tables` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:4016 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.renew_client` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5436 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.renew_client._ensure_renewals_table` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5517 — risk `financial_calculation`.
- `spina_app.area_hierarchy._ensure_legacy_areas_table` — spina_app/area_hierarchy.py:105 — risk `database_write`.
- `spina_app.area_hierarchy._ensure_area_nodes_table` — spina_app/area_hierarchy.py:116 — risk `database_write`.

### `PostgreSQL`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_sql` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:632 — risk `database_write`.

### `Reports`

- `tools.test_reports_feature_wave_18._assert_structure` — tools/test_reports_feature_wave_18.py:43 — risk `reports`.

### `Routes`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_databank_close_dialog` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:10607 — risk `authentication`.

### `Row`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_databank_close_dialog` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:10607 — risk `authentication`.

### `SET`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_write_json` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:235 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_store_file_to_db` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:327 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_store_client_picture_to_db` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:398 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.set_databank_day_close` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7295 — risk `database_write`.

### `SPINA`

- `tools.extract_cilog_diff_pairs.apply_extraction` — tools/extract_cilog_diff_pairs.py:138 — risk `database_read`.
- `tools.extract_date_helpers_module._module_source` — tools/extract_date_helpers_module.py:149 — risk `database_read`.
- `tools.extract_log_serialization_helper.build_plan` — tools/extract_log_serialization_helper.py:62 — risk `database_read`.
- `tools.extract_note_dict_helper.apply_extraction` — tools/extract_note_dict_helper.py:112 — risk `database_read`.
- `tools.extract_numeric_parsers._module_source` — tools/extract_numeric_parsers.py:97 — risk `database_read`.
- `tools.extract_text_normalizers._module_source` — tools/extract_text_normalizers.py:144 — risk `database_read`.

### `SQLite`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_normalize_value` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:544 — risk `database_read`.

### `Variance`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_databank_close_dialog` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:10607 — risk `authentication`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_databank_close_dialog._update_workflow` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:11174 — risk `authentication`.

### `Workflow`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_databank_close_dialog` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:10607 — risk `authentication`.

### `__future__`

- `tools.extract_cilog_diff_pairs.apply_extraction` — tools/extract_cilog_diff_pairs.py:138 — risk `database_read`.
- `tools.extract_date_helpers_module._module_source` — tools/extract_date_helpers_module.py:149 — risk `database_read`.
- `tools.extract_fmt_currency_module._module_source` — tools/extract_fmt_currency_module.py:84 — risk `database_read`.
- `tools.extract_log_serialization_helper.build_plan` — tools/extract_log_serialization_helper.py:62 — risk `database_read`.
- `tools.extract_note_dict_helper.apply_extraction` — tools/extract_note_dict_helper.py:112 — risk `database_read`.
- `tools.extract_numeric_parsers._module_source` — tools/extract_numeric_parsers.py:97 — risk `database_read`.
- `tools.extract_text_normalizers._module_source` — tools/extract_text_normalizers.py:144 — risk `database_read`.

### `_t`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._create_tables` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:4016 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._create_tables._table_cols` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:4022 — risk `database_write`.

### `a`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._ui_call` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:14397 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._collectors_name_from_values` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:20476 — risk `database_read`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.join_area_main_sub` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:2110 — risk `database_read`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._strip_adv_tags` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:26835 — risk `database_read`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._extract_reason_and_color_from_desc` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:26845 — risk `database_read`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._extract_reason_color_meta_from_desc` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:26859 — risk `database_read`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.parse_advance_ranges` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3649 — risk `database_read`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.update_client` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5133 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.add_or_update_transaction` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7743 — risk `authentication`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.add_or_update_transaction_by_uid` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8199 — risk `authentication`.
- `spina_app.area_hierarchy.build_area_tree` — spina_app/area_hierarchy.py:267 — risk `database_read`.

### `all`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.rename_area` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7657 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.delete_area` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7703 — risk `database_write`.

### `an`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:24347 — risk `authentication`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.import_clients_from_excel` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:24714 — risk `financial_calculation`.

### `any`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._ui_call` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:14397 — risk `database_write`.
- `spina_app.area_hierarchy.format_area_path` — spina_app/area_hierarchy.py:47 — risk `database_read`.

### `app_json_store`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_read_json` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:211 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_write_json` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:235 — risk `database_write`.
- `tools.cleanup_pg_json_read_dynamic_sql.build_plan` — tools/cleanup_pg_json_read_dynamic_sql.py:66 — risk `financial_calculation`.

### `app_settings_store`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_read_json` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:211 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_write_json` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:235 — risk `database_write`.
- `tools.cleanup_pg_json_read_dynamic_sql.build_plan` — tools/cleanup_pg_json_read_dynamic_sql.py:66 — risk `financial_calculation`.

### `area_nodes`

- `spina_app.area_hierarchy._fetch_nodes` — spina_app/area_hierarchy.py:146 — risk `database_write`.
- `spina_app.area_hierarchy.migrate_flat_areas` — spina_app/area_hierarchy.py:174 — risk `database_write`.
- `spina_app.area_hierarchy.add_area_node` — spina_app/area_hierarchy.py:313 — risk `database_write`.
- `spina_app.area_hierarchy_ops._apply_planned_subtree` — spina_app/area_hierarchy_ops.py:235 — risk `database_write`.
- `spina_app.area_hierarchy_ops.move_area_node_order` — spina_app/area_hierarchy_ops.py:308 — risk `database_write`.
- `spina_app.area_hierarchy_ops.set_area_node_active` — spina_app/area_hierarchy_ops.py:369 — risk `database_write`.

### `areas`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._create_tables` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:4016 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.get_all_areas` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7576 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.ensure_area_exists` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7613 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.rename_area` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7657 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.delete_area` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7703 — risk `database_write`.
- `spina_app.area_hierarchy.migrate_flat_areas` — spina_app/area_hierarchy.py:174 — risk `database_write`.
- `spina_app.area_hierarchy.add_area_node` — spina_app/area_hierarchy.py:313 — risk `database_write`.
- `spina_app.area_hierarchy_ops._apply_planned_subtree` — spina_app/area_hierarchy_ops.py:235 — risk `database_write`.
- `spina_app.area_hierarchy_ops.set_area_node_active` — spina_app/area_hierarchy_ops.py:369 — risk `database_write`.
- `tools.test_client_area_uid_sync_phase2.main` — tools/test_client_area_uid_sync_phase2.py:9 — risk `database_write`.
- `tools.test_hierarchical_area_storage_phase1.make_db` — tools/test_hierarchical_area_storage_phase1.py:24 — risk `database_write`.
- `tools.test_hierarchical_area_ui_phase2.make_db` — tools/test_hierarchical_area_ui_phase2.py:17 — risk `database_write`.
- `tools.test_hierarchical_area_ui_phase2.main` — tools/test_hierarchical_area_ui_phase2.py:49 — risk `database_write`.

### `batches`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._sqlite_fetchall_in_chunks` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1122 — risk `database_write`.

### `branch`

- `tools.cleanup_pg_json_read_dynamic_sql.build_plan` — tools/cleanup_pg_json_read_dynamic_sql.py:66 — risk `financial_calculation`.

### `clauses`

- `tools.ui_action_inventory.audit` — tools/ui_action_inventory.py:246 — risk `database_read`.

### `client_history`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_cilog_fetch_rows` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:38372 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._create_tables` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:4016 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._log_client_history` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6587 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.get_client_history` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6627 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.get_audit_new_loan_rows` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6857 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.get_audit_renewal_rows` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6921 — risk `financial_calculation`.

### `client_pictures`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_store_client_picture_to_db` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:398 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_restore_client_picture_to_cache` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:457 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_delete_client_picture_token` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:495 — risk `database_write`.

### `clients`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._build_databank_collector_defaults_for_date` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:10227 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._area_picker_dialog` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:11630 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.refresh_collectors` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:12142 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._show_no_area_clients` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:12806 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._write_loan_type_migration_review` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1397 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._import_from_excel_core` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:19555 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:20982 — risk `authentication`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select.print_collector_route_daily_ledger` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:21410 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select.print_full_daily_ledger` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:21622 — risk `authentication`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:24347 — risk `authentication`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.import_from_excel` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:24596 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.import_clients_from_excel` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:24714 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.attach_direct_integration` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:25673 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.print_collector_route_daily_ledger` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:31243 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.print_full_daily_ledger` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:31444 — risk `authentication`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina__ensure_client_picture_column` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:35160 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._db_set_client_picture` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:35274 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._db_clear_client_picture` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:35308 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_perf_clients_rows` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:35673 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_fixed_archive_client` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:36245 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_fixed_restore_client` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:36277 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_fixed_restore_client_by_uid` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:36320 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_fixed_get_archived_clients_with_id` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:36501 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_fixed_restore_client_by_id` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:36561 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_dashboard_fetch_rows` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:36786 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_crc_fetch_close_rows` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:39539 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_crc_active_filtered_areas_for_collector` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:40098 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_save_closed_collector_route_copy_same_format` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:40153 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._create_tables` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:4016 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_route_adv_marker_for` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:40627 — risk `authentication`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._active_client_name_exists` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:4918 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.add_client` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:4949 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.update_client` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5133 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.renew_client` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5436 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.renew_client._do` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5581 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.get_renewal_stats` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5665 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.delete_client` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5731 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._ensure_archive_columns` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5755 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.archive_client` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5774 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.restore_client` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5798 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.restore_client_by_uid` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5822 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.get_archived_clients` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5842 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.get_all_clients` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5878 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.fetch_all_clients` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6216 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.get_client_info` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6251 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.get_client_link_meta` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6269 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.set_link_opt_out_by_uid` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6290 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.link_client_uids` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6308 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.unlink_person_uid` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6400 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.find_clients_by_person_uid` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6427 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.get_client_uid` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6441 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._sync_transactions_for_client_uid` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6456 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.repair_transaction_identity_links` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6522 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.get_client_by_uid` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6576 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.get_person_uid_for_client_uid` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6681 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.get_transactions_for_client_uids` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7512 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.get_all_areas` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7576 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.count_clients_in_area` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7630 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.rename_area` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7657 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.delete_area` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7703 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.get_client_by_person_uid_and_loan_type` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8166 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.add_or_update_transaction_by_uid` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8199 — risk `authentication`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.import_missing_clients_from_transactions` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8355 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._is_client_new` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:9771 — risk `database_write`.
- `spina_app.area_hierarchy.migrate_flat_areas` — spina_app/area_hierarchy.py:174 — risk `database_write`.
- `spina_app.area_hierarchy.set_client_area_node` — spina_app/area_hierarchy.py:363 — risk `database_write`.
- `spina_app.area_hierarchy._ensure_client_area_uid` — spina_app/area_hierarchy.py:93 — risk `database_write`.
- `spina_app.area_hierarchy_ops._client_count_for_nodes` — spina_app/area_hierarchy_ops.py:115 — risk `database_write`.
- `spina_app.area_hierarchy_ops._apply_planned_subtree` — spina_app/area_hierarchy_ops.py:235 — risk `database_write`.
- `spina_app.area_hierarchy_ops.sync_client_area_uid_from_path` — spina_app/area_hierarchy_ops.py:57 — risk `database_write`.
- `tools.test_client_area_uid_sync_phase2.main` — tools/test_client_area_uid_sync_phase2.py:9 — risk `database_write`.
- `tools.test_hierarchical_area_storage_phase1.make_db` — tools/test_hierarchical_area_storage_phase1.py:24 — risk `database_write`.
- `tools.test_hierarchical_area_storage_phase1.assert_legacy_migration` — tools/test_hierarchical_area_storage_phase1.py:61 — risk `database_write`.
- `tools.test_hierarchical_area_storage_phase1.assert_unlimited_hierarchy` — tools/test_hierarchical_area_storage_phase1.py:88 — risk `database_write`.
- `tools.test_hierarchical_area_ui_phase2.make_db` — tools/test_hierarchical_area_ui_phase2.py:17 — risk `database_write`.
- `tools.test_hierarchical_area_ui_phase2.main` — tools/test_hierarchical_area_ui_phase2.py:49 — risk `database_write`.

### `clients__tmp`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._create_tables` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:4016 — risk `financial_calculation`.

### `collectors`

- `spina_app.tabs.collectors._collectors_load_inline_edit_fields` — spina_app/tabs/collectors.py:298 — risk `database_write`.

### `comment`

- `tools.cleanup_stale_databank_generated_blocks._split_comment_and_code_lines` — tools/cleanup_stale_databank_generated_blocks.py:124 — risk `reports`.

### `data`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.resolve_area_order_from_prefs` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:2021 — risk `reports`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_crc_load_collectors` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:39434 — risk `filesystem`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._load_users_db` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:9194 — risk `authentication`.

### `databank_day_close`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._create_tables` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:4016 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._sync_transactions_for_client_uid` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6456 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.get_databank_day_close` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7037 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.set_databank_day_close` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7295 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.reopen_databank_day` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7363 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.set_databank_day_workflow` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7407 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.list_databank_day_close_records` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7456 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.delete_transactions_for_day` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7903 — risk `financial_calculation`.

### `databank_day_close_history`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._append_databank_day_close_history` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7077 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.list_databank_day_close_history` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7114 — risk `database_write`.

### `databank_day_collector_close`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.list_databank_day_collectors` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7140 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.replace_databank_day_collectors` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7202 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.delete_transactions_for_day` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7903 — risk `financial_calculation`.

### `database`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._restore_backup_to_test_database` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:15635 — risk `backup`.

### `date`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_databank_close_records_dialog` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:11259 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_databank_close_records_dialog._load_records` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:11396 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._audit_parse_date_filters` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:13871 — risk `database_read`.

### `desktop`

- `tools.test_login_palette_wave_25.main` — tools/test_login_palette_wave_25.py:23 — risk `authentication`.
- `tools.test_reports_feature_wave_18._assert_structure` — tools/test_reports_feature_wave_18.py:43 — risk `reports`.

### `dst`

- `spina_app.utilities.notes._merge_note_dict` — spina_app/utilities/notes.py:28 — risk `database_read`.

### `editable`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_save_closed_collector_route_copy` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:39768 — risk `financial_calculation`.

### `either`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:24347 — risk `authentication`.

### `exact`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.repair_transaction_identity_links` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6522 — risk `database_write`.

### `existing`

- `spina_app.area_hierarchy_ops._require_active_ancestor_chain` — spina_app/area_hierarchy_ops.py:349 — risk `database_read`.

### `failed`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app_on_client_edit` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:29438 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v23_on_client_edit` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:42879 — risk `financial_calculation`.

### `from`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.refresh_clients` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:24079 — risk `financial_calculation`.

### `hanging`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._run_long_task` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:14506 — risk `database_write`.

### `helper`

- `tools.cleanup_pg_json_read_dynamic_sql.build_plan` — tools/cleanup_pg_json_read_dynamic_sql.py:66 — risk `financial_calculation`.

### `identifier`

- `tools.cleanup_pg_json_read_dynamic_sql.build_plan` — tools/cleanup_pg_json_read_dynamic_sql.py:66 — risk `financial_calculation`.

### `if`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.ensure_area_exists` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7613 — risk `database_write`.

### `information_schema`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg__table_has_column` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:40369 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._PgCompatCursor.execute` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:716 — risk `database_write`.

### `inheriting`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.generate_pdf_selected` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:17888 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.generate_pdf_selected._effective_cycle_start` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:17900 — risk `financial_calculation`.

### `interactive`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:24347 — risk `authentication`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.auto_attach_enhancements` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:26226 — risk `authentication`.

### `interest`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_cashctl_estimated_payoff_with_interest` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:37604 — risk `financial_calculation`.

### `latest`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_dashboard_fetch_rows` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:36786 — risk `financial_calculation`.

### `listbox`

- `spina_app.tabs.collectors._collectors_choose_areas` — spina_app/tabs/collectors.py:375 — risk `database_write`.

### `logger`

- `tools.cleanup_logger_fallback_pass_only._locate_target` — tools/cleanup_logger_fallback_pass_only.py:57 — risk `database_read`.

### `main`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.join_area_main_sub` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:2110 — risk `database_read`.

### `master`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.ensure_area_exists` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7613 — risk `database_write`.

### `non`

- `tools.extract_date_helpers_module._required_import_nodes` — tools/extract_date_helpers_module.py:110 — risk `database_read`.
- `tools.extract_text_normalizers._required_import_nodes` — tools/extract_text_normalizers.py:105 — risk `database_read`.

### `normal`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_save_closed_collector_route_copy_same_format` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:40153 — risk `database_write`.

### `not`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._delete_selected_collector` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:12833 — risk `authentication`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._edit_selected_collector` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:13038 — risk `authentication`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:20982 — risk `authentication`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select._edit_collector_dialog` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:21271 — risk `authentication`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select._delete_collector` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:21348 — risk `authentication`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select.print_collector_route_daily_ledger` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:21410 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.print_collector_route_daily_ledger` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:31243 — risk `financial_calculation`.

### `of`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._verify_postgres_backup_file` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:15571 — risk `backup`.

### `one`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:20982 — risk `authentication`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select._save_collector_notes` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:21171 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._save_collector_notes` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:34696 — risk `database_write`.
- `spina_app.area_hierarchy.format_area_path` — spina_app/area_hierarchy.py:47 — risk `database_read`.

### `or`

- `tools.audit_dynamic_sql_context.audit` — tools/audit_dynamic_sql_context.py:148 — risk `authentication`.

### `password`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._set_user_password` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:9023 — risk `authentication`.

### `payments`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.import_from_excel_with_reasons` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:26527 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.import_from_excel_with_reasons._write` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:26608 — risk `database_write`.

### `public`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg__reset_id_sequence` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:40346 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_renew_client_direct` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:40387 — risk `financial_calculation`.

### `reason`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._get_reason_color_for_client_date` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:26910 — risk `financial_calculation`.

### `renewals`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_dashboard_fetch_rows` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:36786 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._create_tables` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:4016 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.renew_client` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5436 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.renew_client._ensure_renewals_table` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5517 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.renew_client._do` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5581 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.get_renewal_stats` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5665 — risk `financial_calculation`.

### `replacement`

- `tools.cleanup_pg_json_read_dynamic_sql.build_plan` — tools/cleanup_pg_json_read_dynamic_sql.py:66 — risk `financial_calculation`.

### `sidebar`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._refresh_side_nav_selection` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:16011 — risk `database_write`.

### `spina_app`

- `tools.test_cash_control_feature_wave_21.main` — tools/test_cash_control_feature_wave_21.py:62 — risk `financial_calculation`.
- `tools.test_client_info_logs_feature_wave_20.main` — tools/test_client_info_logs_feature_wave_20.py:43 — risk `database_write`.
- `tools.test_clients_feature_wave_19.main` — tools/test_clients_feature_wave_19.py:74 — risk `financial_calculation`.
- `tools.test_dashboard_feature_wave_17.verify_static_extraction` — tools/test_dashboard_feature_wave_17.py:43 — risk `database_read`.

### `spina_restore_test`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._restore_backup_to_test_database` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:15635 — risk `backup`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_backup_history_window` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:15672 — risk `authentication`.

### `sqlite_master`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_dashboard_fetch_rows` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:36786 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_dashboard_fetch_rows._table_exists` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:36801 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._create_tables` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:4016 — risk `financial_calculation`.

### `stable`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._migrate_legacy_notes_by_name` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:2870 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.NoteEditorDialog._migrate_legacy_notes_if_needed` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3029 — risk `database_write`.

### `state`

- `tools.extract_pure_helper_batch.apply` — tools/extract_pure_helper_batch.py:200 — risk `filesystem`.

### `stored_files`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_store_file_to_db` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:327 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_store_client_picture_to_db` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:398 — risk `database_write`.

### `sync`

- `tools.apply_client_area_uid_sync_phase2.inspect` — tools/apply_client_area_uid_sync_phase2.py:31 — risk `database_write`.

### `that`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_save_closed_collector_route_copy` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:39768 — risk `financial_calculation`.

### `the`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._area_picker_dialog` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:11630 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._area_picker_dialog._selected_main_from_tree` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:11922 — risk `database_read`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._save_cell_edit` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:13433 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._ui_call` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:14397 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._list_postgres_backup_files` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:15547 — risk `backup`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._rebuild_side_nav` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:15905 — risk `authentication`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._set_mode` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:16154 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._refresh_mode_toggle` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:16178 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._import_encoder_batch` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:19134 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:20982 — risk `authentication`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select._populate_collector_details` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:21040 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select._save_selected_collector_notes` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:21141 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select._delete_collector` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:21348 — risk `authentication`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.refresh_clients` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:24079 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.refresh_clients.renew_client_selected` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:24213 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:24347 — risk `authentication`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.export_monthly_template` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:24659 — risk `database_read`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.import_clients_from_excel` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:24714 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._parse_reason_color_token` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:26732 — risk `database_read`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._parse_reason_color_token_meta` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:26758 — risk `database_read`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._get_reason_color_for_client_date` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:26910 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app_renew_client_selected` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:30913 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._save_selected_collector_notes` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:34760 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._populate_collector_details` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:38146 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_route_adv_marker_for` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:40627 — risk `authentication`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v32_prompt_login` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:44493 — risk `authentication`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_legacy_client_action_removed_message` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:44851 — risk `reports`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.get_unpaired_7x7_names` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6166 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.repair_transaction_identity_links` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6522 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._force_change_password_dialog` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:9051 — risk `authentication`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._force_change_password_dialog._save` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:9095 — risk `authentication`.
- `spina_app.tabs.collectors._collectors_apply_markers` — spina_app/tabs/collectors.py:155 — risk `database_write`.
- `tools.cleanup_modern_ui_pass_only.build_report` — tools/cleanup_modern_ui_pass_only.py:118 — risk `financial_calculation`.
- `tools.cleanup_neutral_appclass_init_patch.run` — tools/cleanup_neutral_appclass_init_patch.py:130 — risk `financial_calculation`.
- `tools.extract_fmt_currency_module._module_source` — tools/extract_fmt_currency_module.py:84 — risk `database_read`.
- `tools.test_dashboard_feature_wave_17.verify_static_extraction` — tools/test_dashboard_feature_wave_17.py:43 — risk `database_read`.

### `this`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_databank_close_records_dialog` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:11259 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v27_collector_editor_dialog` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:43890 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v27_collector_editor_dialog._clear_assigned` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:44139 — risk `database_read`.
- `tools.audit_blocking_ui_calls.build_report` — tools/audit_blocking_ui_calls.py:138 — risk `financial_calculation`.
- `tools.audit_dynamic_sql_context.audit` — tools/audit_dynamic_sql_context.py:148 — risk `authentication`.
- `tools.audit_pass_only_exceptions.audit` — tools/audit_pass_only_exceptions.py:55 — risk `financial_calculation`.
- `tools.audit_patch_chains.run` — tools/audit_patch_chains.py:130 — risk `financial_calculation`.
- `tools.audit_pg_backup_action_flow.build_report` — tools/audit_pg_backup_action_flow.py:172 — risk `financial_calculation`.
- `tools.audit_pg_command_callers.audit` — tools/audit_pg_command_callers.py:98 — risk `financial_calculation`.
- `tools.audit_shadowed_definitions.collect` — tools/audit_shadowed_definitions.py:75 — risk `financial_calculation`.
- `tools.cleanup_pg_json_read_dynamic_sql.build_plan` — tools/cleanup_pg_json_read_dynamic_sql.py:66 — risk `financial_calculation`.
- `tools.inspect_blocking_ui_context.inspect_source` — tools/inspect_blocking_ui_context.py:133 — risk `financial_calculation`.
- `tools.plan_app_lifecycle_window_pass_only.build_report` — tools/plan_app_lifecycle_window_pass_only.py:160 — risk `authentication`.
- `tools.plan_logger_fallback_pass_only.build_report` — tools/plan_logger_fallback_pass_only.py:136 — risk `authentication`.
- `tools.plan_login_dialog_pass_only.build_report` — tools/plan_login_dialog_pass_only.py:195 — risk `authentication`.
- `tools.plan_modern_ui_pass_only_cleanup.PassOnlyVisitor.visit_Try` — tools/plan_modern_ui_pass_only_cleanup.py:127 — risk `database_read`.
- `tools.plan_pure_login_dialog_ui_pass_only.build_report` — tools/plan_pure_login_dialog_ui_pass_only.py:172 — risk `authentication`.
- `tools.plan_queue_empty_pass_only.build_report` — tools/plan_queue_empty_pass_only.py:139 — risk `authentication`.
- `tools.plan_ui_compatibility_pass_only.build_report` — tools/plan_ui_compatibility_pass_only.py:196 — risk `reports`.

### `those`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_areas_manager` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:19909 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_areas_manager.delete_area` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:20025 — risk `database_write`.

### `transaction_history`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._log_transaction_history` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6733 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.get_transaction_history_for_client_uids` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6804 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.add_or_update_transaction` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7743 — risk `authentication`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.delete_transactions_for_day` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7903 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.add_or_update_transaction_by_uid` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8199 — risk `authentication`.

### `transactions`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._build_databank_collector_defaults_for_date` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:10227 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.print_databank_close_report` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:10371 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_delete_day_dialog` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:13702 — risk `authentication`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:20982 — risk `authentication`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select.print_full_daily_ledger` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:21622 — risk `authentication`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:24347 — risk `authentication`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.attach_direct_integration` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:25673 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.import_from_excel_with_reasons` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:26527 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.import_from_excel_with_reasons._write` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:26608 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._get_reason_color_for_client_date` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:26910 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app_import_missing` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:30379 — risk `database_read`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.print_full_daily_ledger` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:31444 — risk `authentication`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_perf_month_transactions` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:35843 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_dashboard_fetch_rows` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:36786 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_cashctl_get_collection_totals` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:37468 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_cashctl_get_average_collection` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:37525 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_cashctl_estimated_payoff_with_interest` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:37604 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_auto_close_candidate_dates` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:38689 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_crc_fetch_close_rows` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:39539 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_crc_build_paid_cache_for_date` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:40063 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._create_tables` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:4016 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_route_adv_marker_for` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:40627 — risk `authentication`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.update_client` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5133 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.delete_client` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5731 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._sync_transactions_for_client_uid` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6456 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.repair_transaction_identity_links` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6522 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.get_databank_daily_total` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7004 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.get_transactions_for_client_uids` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7512 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.add_or_update_transaction` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7743 — risk `authentication`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.delete_transaction` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7846 — risk `authentication`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.delete_transactions_for_day` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7903 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.get_transaction` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8148 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.get_transaction_by_uid` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8182 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.add_or_update_transaction_by_uid` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8199 — risk `authentication`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.get_transactions_for_client` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8317 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.import_missing_clients_from_transactions` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8355 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._is_advance_on` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8449 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._adv_paid_on_dates_covering` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8497 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_route_adv_marker_for` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8554 — risk `financial_calculation`.
- `tools.ui_action_inventory.looks_like_label_literal` — tools/ui_action_inventory.py:123 — risk `database_read`.

### `worker`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._start_ui_queue_pump` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:14355 — risk `database_read`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._ui_call` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:14397 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._patch_messagebox_threadsafe` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:14461 — risk `database_read`.

### `workflow`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_databank_close_dialog` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:10607 — risk `authentication`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_databank_close_dialog._update_workflow` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:11174 — risk `authentication`.

## Detected file paths and file types

### `*.csv`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._collectors_export_selected` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:20711

### `*.json`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._collectors_export_selected` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:20711

### `*.jsonl;*.csv`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._import_from_excel_entry` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:18355

### `*.pdf`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.print_databank_close_report` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:10371
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_crc_copy_existing_route_pdfs` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:39733

### `*.txt`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._show_import_log_window` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:18796
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._show_import_log_window._save_visible_as` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:19045
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._show_import_log_window._save_all_as` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:19065

### `*.xlsx`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:24347
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.export_monthly_template` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:24659
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.export_clients_template` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:25512
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.export_range_template` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:25548
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.export_range_template` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:26343
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.import_from_excel_with_reasons` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:26527
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app_export_clients_template` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:30238
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app_import_clients_from_excel` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:30264

### `*.yaml`

- `tools.test_ci_acceleration.main` — tools/test_ci_acceleration.py:20

### `*.yml`

- `tools.test_ci_acceleration.main` — tools/test_ci_acceleration.py:20

### `Clients_Template.xlsx`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:24347
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.export_clients_template` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:25512

### `Failed to apply role-based UI restrictions.\n\nFor safety, restart the app as Admin or contact support.\nSee log: data/spina_app.log`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.__init__` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:14199

### `Failed to export. See data/spina_app.log`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._collectors_export_selected` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:20711

### `Failed to save collectors.json. See data/spina_app.log`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._collectors_delete_selected` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:20658
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._collectors_save_inline_edit` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:20771

### `Failed to save collectors.json.\n\nCheck permissions/disk space.\nSee log: data/spina_app.log`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._delete_selected_collector` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:12833
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._edit_selected_collector` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:13038
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._add_collector` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:13131
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:20982
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select._add_collector_dialog` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:21225
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select._edit_collector_dialog` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:21271
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select._delete_collector` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:21348

### `Failed to save notes.\\n\\nSee log: data/spina_app.log`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:20982
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select._save_selected_collector_notes` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:21141

### `Failed to save notes.\n\nSee log: data/spina_app.log`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._save_selected_collector_notes` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:34760

### `Failed to save user accounts (data/users.json).\n\nCheck permissions/disk space.\nSee log: data/spina_app.log`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._save_users_db` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:9171

### `Failed to update password.\nSee log: data/spina_app.log`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._set_user_password` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:9023

### `\n\nSee log: data/spina_app.log`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.generate_pdf_selected` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:17888
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.generate_pdf_selected._err` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:18138
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._save_dated_note_for_client` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:18192
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._save_report_note_for_client` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:18278
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.NoteEditorDialog._delete_note` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3490

### `_MANIFEST.txt`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_save_closed_collector_route_copy_same_format` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:40153

### `access_prefs.json`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_json_table_for_path` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:201
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._access_prefs_path` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8861

### `client_notes.json`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._load_client_notes` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:2476

### `clients_template.xlsx`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app_export_clients_template` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:30238

### `collectors.json`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._load_collectors_route_map` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:10186
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.refresh_collectors` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:12142
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._delete_selected_collector` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:12833
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._edit_selected_collector` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:13038
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._add_collector` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:13131
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._collectors_delete_selected` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:20658
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._collectors_export_selected` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:20711
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._collectors_save_inline_edit` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:20771
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:20982
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select._save_collector_notes` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:21171
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select._add_collector_dialog` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:21225
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select._edit_collector_dialog` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:21271
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select._delete_collector` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:21348
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select.print_collector_route_daily_ledger` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:21410
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.print_collector_route_daily_ledger` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:31243
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._save_collector_notes` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:34696
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_crc_load_collectors` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:39434

### `encoder_import_last.txt`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._import_encoder_batch` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:19134

### `encoder_import_log.json`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_delete_day_dialog` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:13702
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._import_encoder_batch` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:19134
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.delete_transactions_for_day` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7903

### `ledger_prefs.json`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_json_table_for_path` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:201
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.resolve_area_order_from_prefs` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:2021

### `loans.db`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:24347
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.attach_direct_integration` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:25673

### `logger-fallback-cleanup-report.json`

- `tools.cleanup_logger_fallback_pass_only.main` — tools/cleanup_logger_fallback_pass_only.py:184

### `login-dialog-pass-only-plan.json`

- `tools.plan_login_dialog_pass_only.main` — tools/plan_login_dialog_pass_only.py:243

### `logo.png`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.generate_client_pdf` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:27327

### `settings.json`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_json_table_for_path` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:201

### `spina_app.log`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._init_logger` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1251
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_settings_dialog` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:16487

### `spina_settings.json`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_json_table_for_path` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:201

### `users.json`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_settings_dialog` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:16487
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._users_db_path` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8911
