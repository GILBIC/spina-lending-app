# SPINA Application Database and File Access Map

Generated from commit `2b12a179bdf4ccf95c842125a8acc6318189adba`.

Scanned **231 Python files**, **80,236 lines**, and **2,666 symbols**.

> This is a static architecture map. Runtime callbacks and dynamic monkey patches can still require desktop testing.

> SQL tables are detected only from strings used by `execute`/`executemany` or variables named like SQL/query statements. Ordinary prose is excluded.

## Detected application database tables

### `app_json_store`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_read_json` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:211 — risk `database_read`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_write_json` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:235 — risk `database_write`.

### `app_settings_store`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_read_json` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:211 — risk `database_read`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_write_json` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:235 — risk `database_write`.

### `area_nodes`

- `spina_app.area_hierarchy._ensure_area_nodes_table` — spina_app/area_hierarchy.py:116 — risk `database_write`.
- `spina_app.area_hierarchy._fetch_nodes` — spina_app/area_hierarchy.py:146 — risk `database_read`.
- `spina_app.area_hierarchy.migrate_flat_areas` — spina_app/area_hierarchy.py:174 — risk `database_write`.
- `spina_app.area_hierarchy.add_area_node` — spina_app/area_hierarchy.py:313 — risk `database_write`.
- `spina_app.area_hierarchy_ops._apply_planned_subtree` — spina_app/area_hierarchy_ops.py:235 — risk `database_write`.
- `spina_app.area_hierarchy_ops.move_area_node_order` — spina_app/area_hierarchy_ops.py:308 — risk `database_write`.
- `spina_app.area_hierarchy_ops.set_area_node_active` — spina_app/area_hierarchy_ops.py:369 — risk `database_write`.

### `areas`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._create_tables` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:2900 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.ensure_area_exists` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5863 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.rename_area` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5882 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.delete_area` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5928 — risk `database_write`.
- `spina_app.area_hierarchy._ensure_legacy_areas_table` — spina_app/area_hierarchy.py:105 — risk `database_write`.
- `spina_app.area_hierarchy.migrate_flat_areas` — spina_app/area_hierarchy.py:174 — risk `database_write`.
- `spina_app.area_hierarchy.add_area_node` — spina_app/area_hierarchy.py:313 — risk `database_write`.
- `spina_app.area_hierarchy_ops._apply_planned_subtree` — spina_app/area_hierarchy_ops.py:235 — risk `database_write`.
- `spina_app.area_hierarchy_ops.set_area_node_active` — spina_app/area_hierarchy_ops.py:369 — risk `database_write`.
- `spina_app.loan_context_queries.get_all_areas` — spina_app/loan_context_queries.py:109 — risk `database_read`.

### `client_history`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._create_tables` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:2900 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_cilog_fetch_rows` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:29923 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._log_client_history` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5120 — risk `database_write`.
- `spina_app.client_queries.get_client_history` — spina_app/client_queries.py:412 — risk `database_read`.

### `client_pictures`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_store_client_picture_to_db` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:377 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_restore_client_picture_to_cache` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:436 — risk `backup`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_delete_client_picture_token` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:474 — risk `database_write`.

### `clients`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._import_from_excel_core` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:12778 — risk `database_read`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._write_loan_type_migration_review` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1319 — risk `filesystem`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select.print_collector_route_daily_ledger` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:14577 — risk `filesystem`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select.print_full_daily_ledger` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:14789 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.import_from_excel` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:17763 — risk `database_read`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.import_clients_from_excel` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:17881 — risk `filesystem`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.attach_direct_integration` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:18840 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.print_collector_route_daily_ledger` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:23399 — risk `filesystem`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.print_full_daily_ledger` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:23600 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina__ensure_client_picture_column` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:27316 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._db_set_client_picture` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:27428 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._db_clear_client_picture` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:27462 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_fixed_archive_client` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:28068 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_fixed_restore_client` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:28100 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_fixed_restore_client_by_uid` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:28143 — risk `backup`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_fixed_restore_client_by_id` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:28384 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._create_tables` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:2900 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_crc_fetch_close_rows` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:30850 — risk `database_read`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_crc_active_filtered_areas_for_collector` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:31409 — risk `database_read`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_save_closed_collector_route_copy_same_format` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:31464 — risk `filesystem`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_route_adv_marker_for` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:31938 — risk `filesystem`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._active_client_name_exists` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3802 — risk `filesystem`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.add_client` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3833 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.update_client` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:4017 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.renew_client._do` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:4465 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.get_renewal_stats` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:4549 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.delete_client` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:4615 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._ensure_archive_columns` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:4639 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.archive_client` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:4658 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.restore_client` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:4682 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.restore_client_by_uid` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:4706 — risk `backup`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.fetch_all_clients` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:4814 — risk `filesystem`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.set_link_opt_out_by_uid` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:4855 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.link_client_uids` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:4873 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.unlink_person_uid` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:4965 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._sync_transactions_for_client_uid` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:4998 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.repair_transaction_identity_links` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5064 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.rename_area` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5882 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.delete_area` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5928 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.import_missing_clients_from_transactions` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6530 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._is_client_new` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8007 — risk `reports`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._build_databank_collector_defaults_for_date` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8301 — risk `database_read`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._show_no_area_clients` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:9321 — risk `database_read`.
- `spina_app.area_hierarchy.migrate_flat_areas` — spina_app/area_hierarchy.py:174 — risk `database_write`.
- `spina_app.area_hierarchy.set_client_area_node` — spina_app/area_hierarchy.py:363 — risk `database_write`.
- `spina_app.area_hierarchy._ensure_client_area_uid` — spina_app/area_hierarchy.py:93 — risk `database_write`.
- `spina_app.area_hierarchy_ops._client_count_for_nodes` — spina_app/area_hierarchy_ops.py:115 — risk `database_read`.
- `spina_app.area_hierarchy_ops._apply_planned_subtree` — spina_app/area_hierarchy_ops.py:235 — risk `database_write`.
- `spina_app.area_hierarchy_ops.sync_client_area_uid_from_path` — spina_app/area_hierarchy_ops.py:57 — risk `database_write`.
- `spina_app.area_picker_presentation._area_picker_dialog` — spina_app/area_picker_presentation.py:26 — risk `database_read`.
- `spina_app.client_queries.get_client_link_meta` — spina_app/client_queries.py:353 — risk `database_read`.
- `spina_app.client_queries.find_clients_by_person_uid` — spina_app/client_queries.py:374 — risk `database_read`.
- `spina_app.client_queries.get_client_uid` — spina_app/client_queries.py:386 — risk `database_read`.
- `spina_app.client_queries.get_client_by_uid` — spina_app/client_queries.py:401 — risk `database_read`.
- `spina_app.client_queries.get_person_uid_for_client_uid` — spina_app/client_queries.py:464 — risk `database_read`.
- `spina_app.client_queries.get_all_clients` — spina_app/client_queries.py:49 — risk `database_read`.
- `spina_app.collector_refresh_presentation.refresh_collectors` — spina_app/collector_refresh_presentation.py:26 — risk `filesystem`.
- `spina_app.linked_client_queries.get_transactions_for_client_uids` — spina_app/linked_client_queries.py:114 — risk `database_read`.
- `spina_app.linked_client_queries.count_clients_in_area` — spina_app/linked_client_queries.py:175 — risk `database_read`.
- `spina_app.linked_client_queries.get_client_by_person_uid_and_loan_type` — spina_app/linked_client_queries.py:202 — risk `database_read`.
- `spina_app.loan_context_queries.get_all_areas` — spina_app/loan_context_queries.py:109 — risk `database_read`.
- `spina_app.tabs.clients._spina_perf_clients_rows` — spina_app/tabs/clients.py:537 — risk `database_read`.

### `clients__tmp`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._create_tables` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:2900 — risk `database_write`.

### `databank_day_close`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._create_tables` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:2900 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._sync_transactions_for_client_uid` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:4998 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.get_databank_day_close` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5381 — risk `database_read`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.set_databank_day_close` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5639 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.reopen_databank_day` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5707 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.set_databank_day_workflow` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5751 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.delete_transactions_for_day` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6128 — risk `database_write`.

### `databank_day_close_history`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._create_tables` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:2900 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._append_databank_day_close_history` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5421 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.list_databank_day_close_history` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5458 — risk `database_read`.

### `databank_day_collector_close`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._create_tables` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:2900 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.list_databank_day_collectors` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5484 — risk `database_read`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.replace_databank_day_collectors` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5546 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.delete_transactions_for_day` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6128 — risk `database_write`.

### `information_schema`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg__table_has_column` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:31680 — risk `database_read`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._PgCompatCursor.execute` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:638 — risk `database_write`.

### `payments`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.import_from_excel_with_reasons._write` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:19775 — risk `database_write`.

### `public`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg__reset_id_sequence` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:31657 — risk `database_read`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_renew_client_direct` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:31698 — risk `financial_calculation`.

### `renewals`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._create_tables` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:2900 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.renew_client._ensure_renewals_table` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:4401 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.renew_client._do` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:4465 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.get_renewal_stats` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:4549 — risk `financial_calculation`.

### `sqlite_master`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_dashboard_fetch_rows._table_exists` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:28624 — risk `database_read`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._create_tables` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:2900 — risk `database_write`.

### `stored_files`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_store_file_to_db` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:306 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_store_client_picture_to_db` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:377 — risk `database_write`.

### `transaction_history`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._create_tables` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:2900 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._log_transaction_history` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5168 — risk `database_write`.
- `spina_app.linked_client_queries.get_transaction_history_for_client_uids` — spina_app/linked_client_queries.py:83 — risk `database_read`.

### `transactions`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select.print_full_daily_ledger` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:14789 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.attach_direct_integration` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:18840 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.import_from_excel_with_reasons._write` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:19775 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._get_reason_color_for_client_date` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:20077 — risk `filesystem`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.print_full_daily_ledger` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:23600 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_perf_month_transactions` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:27756 — risk `database_read`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._create_tables` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:2900 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_cashctl_get_collection_totals` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:29019 — risk `database_read`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_cashctl_get_average_collection` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:29076 — risk `database_read`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_cashctl_estimated_payoff_with_interest` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:29155 — risk `financial_calculation`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_auto_close_candidate_dates` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:30052 — risk `database_read`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_crc_fetch_close_rows` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:30850 — risk `database_read`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_crc_build_paid_cache_for_date` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:31374 — risk `database_read`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_route_adv_marker_for` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:31938 — risk `filesystem`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.update_client` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:4017 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.delete_client` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:4615 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._sync_transactions_for_client_uid` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:4998 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.repair_transaction_identity_links` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5064 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.get_databank_daily_total` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5348 — risk `database_read`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.add_or_update_transaction` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5968 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.delete_transaction` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6071 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.delete_transactions_for_day` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6128 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.get_transaction` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6373 — risk `database_read`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.get_transaction_by_uid` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6393 — risk `database_read`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.add_or_update_transaction_by_uid` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6410 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.import_missing_clients_from_transactions` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6530 — risk `database_write`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._is_advance_on` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6685 — risk `database_read`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._adv_paid_on_dates_covering` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6733 — risk `database_read`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_route_adv_marker_for` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6790 — risk `filesystem`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._build_databank_collector_defaults_for_date` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8301 — risk `database_read`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.print_databank_close_report` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8374 — risk `filesystem`.
- `spina_app.databank_delete_day.open_delete_day_dialog` — spina_app/databank_delete_day.py:111 — risk `authentication`.
- `spina_app.linked_client_queries.get_transactions_for_client_uids` — spina_app/linked_client_queries.py:114 — risk `database_read`.
- `spina_app.linked_client_queries.get_transactions_for_client` — spina_app/linked_client_queries.py:218 — risk `database_read`.

## Detected application file paths and file types

### `*.csv`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._collectors_export_selected` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:13878

### `*.json`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._collectors_export_selected` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:13878

### `*.jsonl;*.csv`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._import_from_excel_entry` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:11916

### `*.pdf`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_crc_copy_existing_route_pdfs` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:31044
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.print_databank_close_report` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8374

### `*.txt`

- `spina_app.import_log_presentation._show_import_log_window._save_visible_as` — spina_app/import_log_presentation.py:273
- `spina_app.import_log_presentation._show_import_log_window._save_all_as` — spina_app/import_log_presentation.py:293

### `*.xlsx`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.export_monthly_template` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:17826
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.export_clients_template` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:18679
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.export_range_template` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:18715
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.export_range_template` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:19510
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.import_from_excel_with_reasons` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:19694
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app_export_clients_template` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:22257
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app_import_clients_from_excel` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:22283

### `ClientStatement_{}_{}_{}_to_{}_{}.pdf`

- `spina_app.client_statement_generation.generate_pdf_selected` — spina_app/client_statement_generation.py:23

### `Clients_Template.xlsx`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.export_clients_template` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:18679

### `ClosedCollectorRoute_{}_MANIFEST.txt`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_save_closed_collector_route_copy_same_format` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:31464

### `ClosedCollectorRoute_{}_Paid_{}_{}.pdf`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_save_closed_collector_route_copy` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:31079

### `CollectorRoute_{}_{}.pdf`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select.print_full_daily_ledger` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:14789
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.print_full_daily_ledger` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:23600

### `Daily_Cash_Close_{}.pdf`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.print_databank_close_report` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8374

### `Failed to apply role-based UI restrictions.\n\nFor safety, restart the app as Admin or contact support.\nSee log: data/spina_app.log`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.__init__` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:9873

### `Failed to delete note.\n\n{}\n\nSee log: data/spina_app.log`

- `spina_app.note_editor_presentation.NoteEditorDialog._delete_note` — spina_app/note_editor_presentation.py:572

### `Failed to export. See data/spina_app.log`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._collectors_export_selected` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:13878

### `Failed to generate PDF for {}: {}\n\nSee log: data/spina_app.log`

- `spina_app.client_statement_generation.generate_pdf_selected._err` — spina_app/client_statement_generation.py:273

### `Failed to save collectors.json. See data/spina_app.log`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._collectors_delete_selected` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:13825
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._collectors_save_inline_edit` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:13938

### `Failed to save collectors.json.\n\nCheck permissions/disk space.\nSee log: data/spina_app.log`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select._add_collector_dialog` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:14392
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select._edit_collector_dialog` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:14438
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select._delete_collector` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:14515
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._delete_selected_collector` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:9348
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._edit_selected_collector` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:9553
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._add_collector` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:9646

### `Failed to save note.\n\n{}\n\nSee log: data/spina_app.log`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._save_dated_note_for_client` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:11753
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._save_report_note_for_client` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:11839

### `Failed to save notes.\\n\\nSee log: data/spina_app.log`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select._save_selected_collector_notes` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:14308

### `Failed to save notes.\n\nSee log: data/spina_app.log`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._save_selected_collector_notes` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:26916

### `Failed to save user accounts (data/users.json).\n\nCheck permissions/disk space.\nSee log: data/spina_app.log`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._save_users_db` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7407

### `Failed to update password.\nSee log: data/spina_app.log`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._set_user_password` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7259

### `FullDailyLedger_{}.pdf`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select.print_full_daily_ledger` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:14789
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.print_full_daily_ledger` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:23600

### `\n\nSee log: data/spina_app.log`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._save_dated_note_for_client` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:11753
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._save_report_note_for_client` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:11839
- `spina_app.client_statement_generation.generate_pdf_selected._err` — spina_app/client_statement_generation.py:273
- `spina_app.note_editor_presentation.NoteEditorDialog._delete_note` — spina_app/note_editor_presentation.py:572

### `_MANIFEST.txt`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_save_closed_collector_route_copy_same_format` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:31464

### `access_prefs.json`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_json_table_for_path` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:201
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._access_prefs_path` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7097

### `client_notes.json`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._load_client_notes` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:2007

### `clients_template.xlsx`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app_export_clients_template` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:22257

### `collectors.json`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._collectors_delete_selected` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:13825
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._collectors_export_selected` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:13878
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._collectors_save_inline_edit` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:13938
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select._save_collector_notes` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:14338
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select._add_collector_dialog` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:14392
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select._edit_collector_dialog` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:14438
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select._delete_collector` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:14515
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select.print_collector_route_daily_ledger` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:14577
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.print_collector_route_daily_ledger` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:23399
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._save_collector_notes` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:26852
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_crc_load_collectors` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:30745
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._load_collectors_route_map` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8260
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._delete_selected_collector` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:9348
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._edit_selected_collector` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:9553
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._add_collector` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:9646
- `spina_app.collector_refresh_presentation.refresh_collectors` — spina_app/collector_refresh_presentation.py:26

### `delete_day_{}_{}.json`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.delete_transactions_for_day` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6128

### `encoder_import_last.txt`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._import_encoder_batch` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:12357

### `encoder_import_log.json`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._import_encoder_batch` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:12357
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.delete_transactions_for_day` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6128
- `spina_app.databank_delete_day.open_delete_day_dialog` — spina_app/databank_delete_day.py:111

### `encoder_import_{}.txt`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._import_encoder_batch` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:12357

### `ledger_prefs.json`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.resolve_area_order_from_prefs` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1552
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_json_table_for_path` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:201

### `loans.db`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.attach_direct_integration` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:18840

### `logo.png`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.generate_client_pdf` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:20494

### `migration_review_loan_types_{}_{}.csv`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._write_loan_type_migration_review` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1319

### `settings.json`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_json_table_for_path` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:201

### `spina_app.log`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._init_logger` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1173
- `spina_app.settings_dialog_presentation.open_settings_dialog` — spina_app/settings_dialog_presentation.py:22

### `spina_settings.json`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_json_table_for_path` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:201

### `users.json`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._users_db_path` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7147
- `spina_app.settings_dialog_presentation.open_settings_dialog` — spina_app/settings_dialog_presentation.py:22
