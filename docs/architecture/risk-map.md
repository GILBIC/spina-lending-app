# SPINA Application Risk and Modularization Map

Generated from commit `ee7c0955bd432d0c3d98d0c8599ccf12d1adf821`.

Scanned **140 Python files**, **72,179 lines**, and **2,210 symbols**.

> This is a static architecture map. Runtime callbacks and dynamic monkey patches can still require desktop testing.

> Risk groups and batches below include only application functions and methods. Container classes are excluded from line totals so method lines are not counted twice.

## Application risk groups

### Authentication

**42 symbols · 2,336 function lines**

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_settings_dialog` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:15508 — App settings (local-only).
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v32_prompt_login` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:42426 — Modern account-based login dialog. Returns (username, internal_access_profile).
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._build_header` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:15279 — Modern top header: app identity + fast Regular/7x7 switch + app actions.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.__init__` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:13493 — Handles init for the other feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_delete_day_dialog` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:13011 — Delete all Data Bank entries for one selected date, with backup + password confirmation.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.apply_role_access` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:9063 — Apply role-based UI restrictions.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._prompt_login` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8776 — Login dialog: returns (username, role) or (None, None) if cancelled.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._force_change_password_dialog` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8481 — Modal dialog that forces a password change. Returns True if changed.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._prompt_user_role` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8904 — Simple role selector shown at startup.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._load_users_db` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8624 — Load users database from data/users.json. If missing, create defaults. Default accounts (created only if missing): - admin / admin123 -> Admin - encoder / encoder123 -> Encoder - viewer / viewer123 -> Viewer - system / system123 -> System
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_databank_close_dialog._close_day` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:10485 — Handles close day for the data bank feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v32_switch_account` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:42678 — Handles spina v32 switch account for the authentication feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v32_make_users_account_based` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:42369 — Add account display metadata while preserving existing usernames/passwords/access.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.switch_account` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:15461 — Handles switch account for the authentication feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._verify_login` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8696 — Handles verify login for the authentication feature.
- `spina_app.theme_palettes._spina_v32_login_colors` — spina_app/theme_palettes.py:330 — Handles spina v32 login colors for the authentication feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v32_prompt_login._ok` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:42550 — Handles ok for the authentication feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._hash_password` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8353 — Hash passwords using PBKDF2-HMAC-SHA256 by default. Legacy scheme supported for backward compatibility: - scheme: 'sha256_salt' (or 'legacy') uses SHA-256(salt + password) Stored records should include: - scheme: 'pbkdf2_sha256' (recommended) or 'sha256_salt' - iterations: integer (PBKDF2 only)
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._prompt_login._ok` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8825 — Handles ok for the authentication feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_databank_close_dialog._update_workflow` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:10575 — Updates update workflow for the data bank feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._save_user_role` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8310 — Saves save user role for the authentication feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._force_change_password_dialog._save` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8525 — Handles save for the payments feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v32_account_choices` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:42330 — Handles spina v32 account choices for the authentication feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_databank_close_dialog._reopen_day` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:10546 — Handles reopen day for the data bank feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v32_login_button` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:42250 — Handles spina v32 login button for the authentication feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._set_user_password` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8453 — Update password hash+salt for user and clear must_change_password.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._must_change_password` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8426 — Enforce password change if account is still using the known defaults.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_cashctl_apply_role` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:36395 — Handles spina cashctl apply role for the cash control feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._save_users_db` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8601 — Saves save users db for the authentication feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._is_default_password_rec` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8406 — True if this user's stored hash matches the known default password.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._prompt_current_password` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:9571 — Handles prompt current password for the payments feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v32_refresh_user_header` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:42662 — Handles spina v32 refresh user header for the other feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._load_user_role` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8296 — Best-effort load of last used role. Not security—just convenience.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v32_prompt_login._refresh_account_info` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:42537 — Refreshes refresh account info for the authentication feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._refresh_user_header` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:15449 — Refreshes refresh user header for the other feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v32_account_permission_text` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:42291 — Handles spina v32 account permission text for the authentication feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v32_account_display_name` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:42304 — Handles spina v32 account display name for the authentication feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v32_account_role` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:42317 — Handles spina v32 account role for the authentication feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._hash_password_legacy` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8345 — Handles hash password legacy for the payments feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._users_db_path` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8341 — Handles users db path for the authentication feature.
- …and 2 more.

### Backup

**35 symbols · 1,683 function lines**

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_save_closed_collector_route_copy` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:37859 — Save an audit copy of the Collector Route after Daily Close. The PDF contains the closed total/actual cash for the day and the amount paid by each client on that date. It is separate from Generate Report and from editable Data Bank rows.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_backup_history_window` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:14966 — Show backup files and provide verify/restore-test actions.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_fixed_open_archived_clients_dialog_rowid` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:35204 — Archived clients restore dialog that restores by clients.id first.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_fixed_open_archived_clients_dialog` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:34946 — Archived clients restore dialog with UID fallback and refresh after restore.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app_open_archived_clients_dialog` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:29933 — Handles app open archived clients dialog for the clients feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._create_postgres_backup_file` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:14648 — Create a full PostgreSQL backup using pg_dump custom format. The backup includes clients, payments, JSON rows, PDFs, and pictures because those are now stored in spina_db. Password is passed through PGPASSWORD, not printed on screen.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.backup_postgres_database` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:14733 — UI handler for the Backup button.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_fixed_get_archived_clients_with_id` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:35104 — List archived clients and include the internal row id for reliable restore.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.generate_client_pdf._draw_official_report_footer` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:27063 — Draw a small, subtle official-version label and daily Generate Report counter at the bottom. This footer is intentionally NOT styled like the big notes section. It is only a quiet authenticity/count marker near the bottom of the page.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_fixed_open_archived_clients_dialog.restore_selected` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:35024 — Handles restore selected for the backup feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_restore_client_picture_to_cache` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:457 — Handles spina pg restore client picture to cache for the clients feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._restore_backup_to_test_database` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:14929 — Restore selected backup into spina_restore_test only; never overwrites live spina_db.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_fixed_open_archived_clients_dialog_rowid.restore_selected` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:35290 — Handles restore selected for the backup feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._verify_postgres_backup_file` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:14865 — Verify a PostgreSQL custom backup by reading its table of contents.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.get_archived_clients` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5842 — List archived clients for restore UI.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.print_full_daily_ledger._draw_closed_route_payment_summary_page._draw_summary_row` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:33499 — Handles draw summary row for the collectors feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_fixed_open_archived_clients_dialog_rowid.load_list` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:35260 — Loads load list for the clients feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_fixed_open_archived_clients_dialog.load_list` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:34996 — Loads load list for the clients feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app_open_archived_clients_dialog.restore_selected` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:30002 — Handles restore selected for the backup feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._list_postgres_backup_files` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:14841 — Return backup files from the app backups folder, newest first.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.generate_client_pdf._draw_also_footer` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:26893 — Draw small footer note (subtle) on the current page.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app_delete_client_selected` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:28425 — Handles app delete client selected for the clients feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_fixed_restore_client_by_uid` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:34923 — Restore archived client by UID, with name/type fallback support.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.restore_client_by_uid` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5822 — Restore a previously archived client by client_uid.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app_open_archived_clients_dialog.load_list` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:29982 — Loads load list for the clients feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._restore_main_tabs` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:9004 — Handles restore main tabs for the backup feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina__resolve_app_path` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:34123 — Handles spina resolve app path for the other feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_save_closed_collector_route_copy._draw_table_header` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:38012 — Handles draw table header for the collectors feature.
- `spina_app.area_hierarchy_ui.open_area_manager.close` — spina_app/area_hierarchy_ui.py:707 — Handles close for the other feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_archive_row_to_dict` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:34834 — Handles spina archive row to dict for the backup feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._postgres_backup_dir` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:14638 — Return/create the app backup folder.
- `spina_app.area_hierarchy_ui._restore_parent_grab` — spina_app/area_hierarchy_ui.py:44 — Return modal control to the form that opened the Area window.
- `spina_app.area_hierarchy_ui.select_area_node.close` — spina_app/area_hierarchy_ui.py:259 — Handles close for the other feature.
- `spina_app.area_hierarchy_ui._select_parent_area.close` — spina_app/area_hierarchy_ui.py:431 — Handles close for the other feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._PgCompatConnection.backup` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:882 — Handles backup for the backup feature.

### Database Read

**64 symbols · 2,847 function lines**

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._area_picker_dialog` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:11031 — Route area picker (Main/Sub Tree + ordered selection). What you get: - Left: Tree of Main Areas with Sub Areas underneath - Right: Selected Route (ordered) as MAIN or MAIN - SUB entries - MAIN entry covers all its Sub Areas when printing/validating routes.
- `spina_app.client_queries.get_all_clients` — spina_app/client_queries.py:49 — Return client names (optionally filtered by loan_type) with optional search. search_by: - 'all' / 'both' : match across common client fields (default) - 'client' : match in client name only - 'area' : match in area only - 'principal' : match in principal (as text) - 'released' : match in date_releas
- `spina_app.tabs.clients._spina_perf_clients_rows` — spina_app/tabs/clients.py:537 — Bulk load rows for Clients tab in one/few queries, avoiding per-row get_client_info().
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_crc_fetch_close_rows` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:37630 — Build route rows with amount paid on the close date.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._import_from_excel_core` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:18447 — Auto-detect payments and reasons from Excel. Rules: " First row = headers. Must include 'Client Name' and at least one date column. " A date column can be an Excel date/datetime or a string 'YYYY-MM-DD'. " If a cell under a date column is numeric (or numeric-looking text): that's the amount. " If a 
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._build_databank_collector_defaults_for_date` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:9628 — Builds build databank collector defaults for date for the collectors feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_perf_month_transactions` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:34536 — Return {(row_key, yyyy-mm-dd): payment} for visible clients in the month using one range query.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.get_audit_new_loan_rows` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6379 — Return append-only ADD audit rows for new loans.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.import_from_excel` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:23532 — Handles import from excel for the data bank feature.
- `spina_app.linked_client_queries.get_transactions_for_client_uids` — spina_app/linked_client_queries.py:114 — Return transactions for a linked person (both Regular + 7x7), using client_uid when available. Includes best-effort fallback to legacy rows where client_uid is blank but (name, loan_type) matches.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_cashctl_get_average_collection` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:35856 — Average daily collection before the selected date. Uses the last N calendar days before the selected date, then averages only days that actually have collections. This is better for forecasting collection days than dividing by every calendar day, especially when there are no-collection days.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.list_databank_day_close_records` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6978 — Handles list databank day close records for the data bank feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._adv_paid_on_dates_covering` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7927 — Return sorted list of *payment dates* (YYYY-MM-DD) whose ADV tag covers `day_yyyy_mm_dd`. Rules: - We only look at transactions whose description contains an [ADV:...] tag. - We EXCLUDE the payment date itself (so ADV is shown only on the covered days, not on the payment day). - If multiple ADV paym
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_cashctl_get_collection_totals` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:35799 — Return combined collection totals for one day. Combined Collected = Regular + 7x7 + any transaction without a clean loan_type. This intentionally uses the Data Bank transactions total, not only one payment mode.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_crc_active_filtered_areas_for_collector` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:38189 — Match the Collector Route screen filtering so blank/archived-only areas are skipped.
- `spina_app.client_queries.get_client_history` — spina_app/client_queries.py:412 — Return audit history rows (most recent first). Prefer client_uid. Normalizes key names for UI: ts -> changed_at before_json -> old_json after_json -> new_json
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._is_advance_on` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7879 — Return True if any transaction for `name` has an [ADV:s..e] tag that covers day_yyyy_mm_dd. Falls back quietly to False if anything goes wrong.
- `spina_app.linked_client_queries.get_transactions_for_client` — spina_app/linked_client_queries.py:218 — Retrieves get transactions for client for the clients feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.get_all_areas` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7039 — Return area master list for UI dropdowns. Hides areas that are used only by archived clients, but keeps: - areas with at least one active client - areas with no clients yet (manually-added / still-unused)
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.connect_db` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1053 — Central DB connector. PostgreSQL TEST MODE: ignores the old SQLite file path and connects to spina_db using psycopg through a SQLite-compatibility wrapper.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.list_databank_day_collectors` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6662 — Handles list databank day collectors for the collectors feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_auto_close_candidate_dates` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:36832 — Return transaction dates up to cutoff that are not already closed.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_crc_build_paid_cache_for_date` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:38154 — Return {(lower_name, lower_loan_type): paid_amount} for the closed date.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.get_databank_daily_total` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6526 — Retrieves get databank daily total for the data bank feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.get_databank_day_close` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6559 — Retrieves get databank day close for the data bank feature.
- `spina_app.linked_client_queries.get_transaction_history_for_client_uids` — spina_app/linked_client_queries.py:83 — Return databank audit rows (most recent first) for a list of client_uids.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.__init__` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3932 — Handles init for the loans feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._sqlite_fetchall_in_chunks` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1122 — Fetch all rows for SQL that contains 'IN ({ph})' placeholder. - Splits `items` into batches to avoid SQLite 'too many SQL variables'. - `sql_template` must include '{ph}' placeholder for question marks. - `tail_params` are appended after the batch params (e.g. BETWEEN ? AND ? values).
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._create_tables._ensure_column` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:4034 — Add column only if missing. Returns True if we attempted and succeeded.
- `spina_app.area_hierarchy._fetch_nodes` — spina_app/area_hierarchy.py:146 — Loads fetch nodes for the other feature.
- `spina_app.linked_client_queries.count_clients_in_area` — spina_app/linked_client_queries.py:175 — Count ACTIVE clients in an area. Archived-only areas should not keep showing up as 'in use' in the UI.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.list_databank_day_close_history` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6636 — Handles list databank day close history for the data bank feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._show_no_area_clients` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:12207 — Show clients that still have blank area (needs assignment).
- `spina_app.area_hierarchy_ops._client_count_for_nodes` — spina_app/area_hierarchy_ops.py:115 — Count all matching clients in one query, including stale legacy paths.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._LockedCursor.execute` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3774 — Handles execute for the database feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._LockedConnection.execute` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3859 — Handles execute for the database feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_read_json` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:211 — Handles spina pg read json for the database feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg__reset_id_sequence` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:38437 — Move a PostgreSQL BIGSERIAL/SERIAL sequence after the current MAX(id).
- `spina_app.client_queries.get_client_link_meta` — spina_app/client_queries.py:353 — Return (client_uid, person_uid, link_opt_out) for a client.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.get_transaction` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7586 — Retrieves get transaction for the payments feature.
- …and 24 more.

### Database Write

**63 symbols · 4,339 function lines**

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._create_tables` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:4016 — Builds create tables for the loans feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.attach_direct_integration` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:24609 — Minimal integration after removing undo/redo/backups. - Ensures a DB is attached - Wraps Excel import with a safe error dialog (if present) - Triggers initial UI refreshes (if methods exist)
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.update_client` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5133 — Update a client (append-only history is written to client_history).
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.delete_transactions_for_day` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7341 — Delete ALL Data Bank transaction rows for one calendar date. Safety behavior: - Validates YYYY-MM-DD. - Creates a JSON backup in data/day_delete_backups BEFORE deleting. - Deletes both Regular and 7x7 transactions for that date. - Clears the Data Bank close/collector-close lock rows for that date so
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.add_client` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:4949 — Handles add client for the clients feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.add_or_update_transaction_by_uid` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7623 — Insert or update a transaction using client_uid as the stable key. Key: (client_uid, loan_type, date) - Automatically pulls the current client name from clients table. - Updates the stored `name` in transactions if the client was renamed. - Writes append-only audit rows into transaction_history.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.add_or_update_transaction` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7181 — Insert or update a transaction (Data Bank) row. Key: prefer (client_uid, loan_type, date); fallback to legacy (name, loan_type, date) - Populates `client_uid` when possible so linked profiles can see the same Data Bank rows. - Writes an append-only audit row into `transaction_history`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.replace_databank_day_collectors` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6724 — Handles replace databank day collectors for the collectors feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.link_client_uids` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5989 — Link two client rows (typically Regular + 7x7) by assigning the same person_uid. Safety rules: - Prevent linking the same row to itself. - Prevent linking two rows of the same loan_type (to avoid accidental merges). - Prevent merging two different existing person_uid groups (unlink first).
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.import_missing_clients_from_transactions` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7743 — Ensure every (name, loan_type) in transactions has a matching row in clients. Older versions only tracked names (no loan_type). This version is multi-loan-type safe. For 7x7 loans, we default interest_rate to 0.0.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._log_transaction_history` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6284 — Append-only audit entry for Data Bank transactions.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_store_file_to_db` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:327 — Handles spina pg store file to db for the database feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._PgCompatCursor.execute` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:716 — Handles execute for the database feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.import_from_excel_with_reasons._write` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:25544 — Handles write for the data bank feature.
- `spina_app.area_hierarchy.migrate_flat_areas` — spina_app/area_hierarchy.py:174 — Migrate existing flat Area text to root nodes without changing text. Existing values are deliberately kept as root nodes. Staff can later move them under another Area through the hierarchy manager. This avoids guessing whether a dash or slash in an old Area name was intended as a separator.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.set_databank_day_close` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6817 — Updates set databank day close for the data bank feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._sync_transactions_for_client_uid` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6114 — Best-effort repair for transaction rows tied to one client. Keeps `transactions.client_uid` and `transactions.name` aligned to the current client row. Returns the number of transaction rows updated.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_cilog_fetch_rows` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:36703 — Handles spina cilog fetch rows for the clients feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_store_client_picture_to_db` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:398 — Handles spina pg store client picture to db for the clients feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.delete_transaction` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7284 — Removes delete transaction for the payments feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.repair_transaction_identity_links` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6180 — Best-effort global repair for transaction/client identity drift. - backfills missing transaction.client_uid from exact current (name, loan_type) - normalizes transaction.name from the current clients.name when client_uid is present Returns a small stats dict.
- `spina_app.area_hierarchy_ops._apply_planned_subtree` — spina_app/area_hierarchy_ops.py:235 — Handles apply planned subtree for the other feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.set_databank_day_workflow` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6929 — Updates set databank day workflow for the data bank feature.
- `spina_app.area_hierarchy.add_area_node` — spina_app/area_hierarchy.py:313 — Add one Area node under any parent and return the saved node.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.reopen_databank_day` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6885 — Handles reopen databank day for the data bank feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.rename_area` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7095 — Rename an area and update all clients that use it (all loan types). Logs client history.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_perf_ensure_indexes` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:34470 — Create helpful indexes for large datasets. Safe/idempotent.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_fixed_restore_client` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:34880 — Restore a previously archived client by name + loan type. Important fix: the old code called get_client_info() without include_archived=True. Because archived rows are hidden by default, restore failed with "Client not found".
- `spina_app.area_hierarchy_ops.set_area_node_active` — spina_app/area_hierarchy_ops.py:369 — Activate or deactivate a whole subtree safely.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._log_client_history` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6236 — Append-only audit entry. old_row/new_row are dicts or None.
- `spina_app.area_hierarchy_ops.move_area_node_order` — spina_app/area_hierarchy_ops.py:308 — Move one Area up or down among siblings.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.renew_client._do` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5581 — Handles do for the clients feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_fixed_restore_client_by_id` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:35164 — Restore archived client by exact clients.id row.
- `spina_app.area_hierarchy_ops.sync_client_area_uid_from_path` — spina_app/area_hierarchy_ops.py:57 — Link one legacy client Area path to its stable Area node ID.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.delete_area` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7141 — Delete an area. If clear_clients True, clear that area from all clients (logs history).
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_write_json` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:235 — Handles spina pg write json for the database feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._append_databank_day_close_history` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6599 — Handles append databank day close history for the data bank feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._db_set_client_picture` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:34208 — Handles db set client picture for the clients feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._db_clear_client_picture` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:34242 — Handles db clear client picture for the clients feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_fixed_archive_client` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:34848 — Soft-delete: hide the client while keeping transactions/history. Fix: after archiving, fetch the new row with include_archived=True so history can still see the archived row instead of getting an empty new_row.
- …and 23 more.

### Filesystem

**101 symbols · 9,203 function lines**

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:23283 — Auto-suggest linking when a matching client exists in the other loan type. - YES links both rows (same person_uid). - NO sets link_opt_out=1 for BOTH rows so you won't be asked again from either side, unless you manually link later.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.refresh_collectors` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:11543 — Refresh the Collector's Route table (enhanced). - Supports older collectors.json schemas (dict/list/strings) and normalizes to: {name: {areas: [...], notes: "..."}} - Computes: * unassigned areas (master areas not in any route) * unknown route areas (route areas not found in master areas) * conflict
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._import_encoder_batch` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:18026 — Import One-Day Encoder exports (.jsonl or .csv) into the DB. - Dedupe by record_id (preferred) or a content hash fallback - Unknown clients are skipped (no auto-create) - Advances are stored via description tag: [ADV:s..e; s..e; ...] (supports multiple ranges)
- `spina_app.tabs.reports._spina_v22_build_reports_tab` — spina_app/tabs/reports.py:105 — Handles spina v22 build reports tab for the reports feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._build_reports_tab` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:16307 — Builds build reports tab for the reports feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._show_import_log_window` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:17688 — Organized import log viewer (tabs + search + save/copy). Tabs: - All (chronological) - Inserted / Updated - Skipped Duplicates / Skipped Unknown / Skipped - Errors - Header/Info / Other
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.import_clients_from_excel` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:23650 — Import ONLY client details from an Excel file into the Clients DB. Multi-loan-type safe: - If the sheet has a "Loan Type" column, it imports per-row (Regular / 7x7). - Otherwise, it imports into the CURRENT view mode (top selector).
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.refresh_clients` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:23015 — Refresh the Clients tab table from the database, honoring the search box.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.print_databank_close_report` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:9772 — Generates print databank close report for the data bank feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_databank_close_records_dialog` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:10660 — Handles open databank close records dialog for the data bank feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select.print_collector_route_daily_ledger` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:20346 — Print the SELECTED collector's route using the same 3-column Daily Collection Ledger layout as `print_full_daily_ledger`, but ONLY for that collector's areas (no 'arrange all areas' step). - Uses selection() first (more reliable than focus()). - Reads collectors.json in multiple historical schemas. 
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.print_collector_route_daily_ledger` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:30179 — Print the SELECTED collector's route using the same 3-column Daily Collection Ledger layout as `print_full_daily_ledger`, but ONLY for that collector's areas (no 'arrange all areas' step). - Uses selection() first (more reliable than focus()). - Reads collectors.json in multiple historical schemas. 
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_route_adv_marker_for` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:38718 — Collector Route ADV lookup with stronger PostgreSQL migration fallback. This version does not rely only on the printed route name. It finds the client_uid/person_uid from clients first, then checks every matching transaction name/uid for the selected loan type. This fixes migrated data where a linke
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_save_closed_collector_route_copy_same_format` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:38244 — Save final closed Collector Route copy using the SAME Collector Route PDF layout. Difference from normal print: the payment columns are filled with the actual amount paid on the closed date, and the PDF is saved silently under data/Closed_Collector_Routes.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._begin_cell_edit` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:12598 — Create an Entry over the clicked (or remembered) day cell and save back to DB.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_record_report_generation` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:26118 — Increment and return the daily Generate Report counter. Stored in: - data/report_generation_counts.json (summary counts) - data/report_generation_logs.csv (Excel-friendly full log) - data/report_generation_logs.jsonl (append-only full log) Counts: - total: all reports generated today - per client+lo
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._import_from_excel_entry_worker._parse_sheet` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:17464 — Handles parse sheet for the utilities feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._get_reason_color_for_client_date` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:25846 — Return the active reason color for this client on this day (Collector Route only). Behavior: - If the reason token has no window (no D/UNTIL), color applies ONLY on the reason's date. - If token has D:n, color applies for n days starting from the reason's date. - If token has UNTIL:YYYY-MM-DD, color
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v18_draw_dashboard_charts` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:39593 — Handles spina v18 draw dashboard charts for the dashboard feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._collectors_save_inline_edit` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:19707 — Save inline edits to collectors.json (atomic), then refresh UI.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._write_loan_type_migration_review` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1397 — Write a CSV report of potentially misclassified loan types after legacy upgrades. Returns the report file path, or None if nothing was written.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_tree_click` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:33847 — Handle click in Sel / Actions columns without breaking row selection.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._edit_selected_collector` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:12439 — Handles edit selected collector for the collectors feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_tree_click` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:19501 — Handle clicks in Sel + Actions columns.
- `spina_app.tabs.dashboard._spina_v17_draw_dashboard_charts` — spina_app/tabs/dashboard.py:355 — Handles spina v17 draw dashboard charts for the dashboard feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app_refresh_client_picture_panel` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:34276 — Handles app refresh client picture panel for the clients feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._save_cell_edit` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:12742 — Save an edited day-cell value into the DB (no undo/redo). - amount == 0 → prompt for reason (stored in description) - amount > 0 → clears description
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_route_adv_marker_for` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7984 — Robust Collector Route ADV lookup for PostgreSQL test builds. Returns (True, adv_end_date) when an ADV range covers the ledger day. It is intentionally case-insensitive on name and supports client_uid fallback. The actual payment date is included when the ADV range covers it, so collector route can 
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.on_day_double` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:16157 — Handles on day double for the other feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select._edit_collector_dialog` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:20207 — Legacy dialog-based edit; now edits the main collectors.json dict schema.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._mark_missed_for_selected` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:12938 — Right-click action in Data Bank: set selected day as MISSED (0.0) with a reason.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._start_edit` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:16234 — Handles start edit for the other feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_databank_close_records_dialog._load_records` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:10797 — Loads load records for the data bank feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._delete_selected_collector` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:12234 — Removes delete selected collector for the collectors feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.generate_pdf_selected._work` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:16956 — Handles work for the reports feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select._delete_collector` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:20284 — Legacy delete; now deletes from the main collectors.json dict schema.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._load_client_notes._safe_load_one` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:2517 — Handles safe load one for the clients feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_save_closed_collector_route_copy_same_format._generate_one` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:38285 — Generates generate one for the collectors feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._collectors_export_selected` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:19647 — Handles collectors export selected for the collectors feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._add_collector` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:12532 — Handles add collector for the collectors feature.
- …and 61 more.

### Financial Calculation

**30 symbols · 9,679 function lines**

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.print_full_daily_ledger` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:30380 — Print a 3-column DAILY COLLECTION LEDGER with a small UI to change: - Ledger Date - Paper size and orientation - Areas order (arrange ALL areas)
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select.print_full_daily_ledger` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:20558 — Print a 3-column DAILY COLLECTION LEDGER with a small UI to change: - Ledger Date - Paper size and orientation - Areas order (arrange ALL areas)
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.generate_client_pdf` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:26263 — Override: Client SOA PDF that expands ADV ranges to daily 'Adv' markers in the Payment column, and prints other reasons as text in Payment. Never prints long notes in the Date column. Layout: 3 columns per page, 11 rows per column.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_dashboard_fetch_rows` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:35389 — Return active client completion rows using payments from latest released date only. Latest released date = max(clients.date_released, latest renewals.renew_date). Payment start = latest released date + clients.pay_start_offset_days (normalized to 0/1 day).
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.RenewDialog._compute_stats` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:29375 — Return dict with paid/remaining/suggested released cash (best-effort). Regular: remaining_due = max(0, total_to_pay - paid_total) 7x7: remaining_due = remaining_principal + unpaid_interest_arrears (arrears must be cleared first). Uses the same rule as the SOA: - Daily interest = ceil(remaining_princ
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.renew_client` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5436 — Renew a client (reloan). Updates the client row to a new cycle and records an event. - released_cash: cash actually released to the client for this renew (for display in reports). - new_principal: the new loan principal. If None/blank, defaults to released_cash.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_renew_client_direct` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:38478 — PostgreSQL-safe renew/reloan implementation for the TEST build.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_route_balance_like_generate_report` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:37308 — Return the same Balance basis used by Generate Report PDF. Regular: total_to_pay (corrected to principal + interest when needed) minus effective current-cycle payments. 7x7: remaining principal after the Generate Report interest-first payment split. This intentionally matches the report header Balan
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v21_cash_refresh` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:39980 — Handles spina v21 cash refresh for the other feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app_refresh_clients` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:28152 — Handles app refresh clients for the clients feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v20_draw_dashboard_charts` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:39788 — Replace old progress/remaining charts with more useful active-client charts.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_cashctl_estimated_payoff_with_interest` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:35935 — Estimate payoff collection for renewal, including interest. Regular: uses the dashboard remaining balance, which is based on total_to_pay. total_to_pay is corrected to principal + interest_amount when needed. 7x7: splits current-cycle payments into interest first, then principal, and includes unpaid
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.refresh_audit_tab` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:13379 — Refreshes refresh audit tab for the data bank feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_cashctl_refresh` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:36280 — Handles spina cashctl refresh for the cash control feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app__client_form.save` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:27954 — Handles save for the clients feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_cashctl_reserve_rows` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:36056 — Rows to reserve cash for possible renewals. IMPORTANT: Cash Control now includes ALL active clients in the reserve list, not only near-completion clients. Near-completion / due-soon rules are used only as priority labels so the owner can see who is urgent first. Reserve basis is the current principa
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.RenewDialog.body` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:29685 — Handles body for the loans feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app_renew_client_selected` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:29849 — Renew (reloan) the selected client and update the client row + report stats.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._build_audit_tab` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:13242 — Builds build audit tab for the data bank feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.refresh_clients.renew_client_selected` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:23149 — Renew (reloan) the selected client and update the client row.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.get_renewal_stats` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5665 — Return (renew_count, last_released_cash, last_release_date). - renew_count counts renew events (not including the original loan release). - last_released_cash is the last recorded released cash; if none, returns None.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.renew_client._ensure_renewals_table` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5517 — Handles ensure renewals table for the loans feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.get_audit_renewal_rows` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6443 — Return append-only RENEW audit rows.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v23_client_loan_summary` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:40234 — Handles spina v23 client loan summary for the clients feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._audit_show_selected` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:13322 — Handles audit show selected for the other feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.get_unpaired_7x7_names` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5880 — Return 7x7 client names that have NO Regular record and are NOT linked. Used so 7x7-only clients can still be managed from the Regular view (appear at the bottom) and included in Collector Route prints. Rules: - loan_type must be '7x7' - there is no same-name Regular record - person_uid is blank/emp
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.RenewDialog.validate` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:29779 — Handles validate for the utilities feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.RenewDialog.apply` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:29819 — Handles apply for the loans feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app__client_form._compute_dates` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:27898 — Handles compute dates for the clients feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_cashctl__x7_daily_interest` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:35930 — 7x7 daily interest: 1..1000=7/day, 1001..2000=14/day, etc.

### Reports

**61 symbols · 2,676 function lines**

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_databank_close_dialog` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:10008 — Handles open databank close dialog for the data bank feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.generate_pdf_selected` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:16780 — Generate a client statement PDF without freezing the UI.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._is_client_new` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:9201 — Return True if client is NEW. Rules: - If 'new_until' is explicitly set in the DB: * If it's an empty string or unparsable -> treat as explicit OFF (return False). * If it's a valid date -> return (ledger_date <= new_until). No fallback. - Otherwise (no explicit 'new_until' value present): * If 'day
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app_import_clients_from_excel` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:29200 — Handles app import clients from excel for the clients feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.refresh_reports` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:16647 — Refreshes refresh reports for the reports feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select.print_full_daily_ledger._arrange_areas_dialog` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:20702 — Handles arrange areas dialog for the collectors feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.print_full_daily_ledger._arrange_areas_dialog` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:30516 — Handles arrange areas dialog for the reports feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._register_unicode_fonts` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:2219 — Try to register a Unicode TTF so ReportLab can encode non-ASCII safely. Falls back to built-ins if none found.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v23_on_client_edit` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:40812 — Handles spina v23 on client edit for the clients feature.
- `spina_app.tabs.reports._spina_v22_update_report_cards` — spina_app/tabs/reports.py:488 — Handles spina v22 update report cards for the reports feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._build_reports_tab._toggle_reports_notes_panel` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:16537 — Handles toggle reports notes panel for the reports feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.set_area_for_selected_clients` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:18956 — Set one area for all selected clients in the Clients tab (current mode only).
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app_on_client_edit` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:28374 — Handles app on client edit for the clients feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v23_add_client_dialog` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:40760 — Handles spina v23 add client dialog for the clients feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app_add_client_dialog` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:28329 — Handles app add client dialog for the clients feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._save_dated_note_for_client` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:17084 — Saves save dated note for client for the clients feature.
- `spina_app.theme_palettes._spina_v22_reports_colors` — spina_app/theme_palettes.py:148 — Handles spina v22 reports colors for the reports feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._save_report_note_for_client` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:17170 — Saves save report note for client for the clients feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_settings_dialog._save` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:15742 — Handles save for the settings feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.refresh_clients.delete_client_selected` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:23113 — Removes delete client selected for the clients feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._auto_load_report_note` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:17126 — Handles auto load report note for the reports feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._set_report_note_text` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:17053 — Updates set report note text for the reports feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._load_report_note_for_client` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:17211 — Loads load report note for client for the clients feature.
- `spina_app.tabs.reports._spina_v22_button` — spina_app/tabs/reports.py:62 — Handles spina v22 button for the reports feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._open_note_dialog` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:9328 — Handles open note dialog for the notes feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.refresh_clients.on_client_edit` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:23251 — Handles on client edit for the clients feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.safe_excel_import.wrapper` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:25132 — Handles wrapper for the clients feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._build_reports_tab._apply_report_range_from_fields` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:16352 — Handles apply report range from fields for the reports feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._on_mode_change` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8260 — Refresh visible tables when the mode selector changes.
- `spina_app.tabs.reports._spina_v22_style_reports_tree` — spina_app/tabs/reports.py:38 — Handles spina v22 style reports tree for the reports feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.attach_refresh_all.refresh_all` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:25102 — Refreshes refresh all for the clients feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.auto_attach_enhancements` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:25162 — Search module globals for an App-like object and attach enhancements. Call this function at the bottom of the file or from interactive session once the app is created.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_patch_reportlab_canvas_save` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:516 — Handles spina pg patch reportlab canvas save for the reports feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._build_reports_tab._sync_reports_range` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:16330 — Handles sync reports range for the reports feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.add_pdf_header` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3995 — Reusable header for PDFs with logo, title, and current date.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.refresh_clients.add_client_dialog` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:23231 — Handles add client dialog for the clients feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._log_exc` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1269 — Log exceptions to data/spina_app.log (best-effort).
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._log_suppressed_once` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1294 — Log a suppressed exception only once per key (to avoid log spam).
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._alert_user` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1313 — Best-effort UI alert. Safe even if Tk root isn't created yet.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_settings_dialog._test_reports` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:15727 — Handles test reports for the reports feature.
- …and 21 more.

### Support

**566 symbols · 10,096 function lines**

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._import_from_excel_entry_worker` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:17290 — Worker for _import_from_excel_entry (runs off the Tk main thread).
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.print_full_daily_ledger._draw_closed_route_payment_summary_page` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:33380 — Append closed-route payment summaries on a separate page. This keeps the route pages in the normal collector format while still saving a complete area-by-area payment summary plus grand total.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina__parse_flexible_due_rule` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:37038 — Return (label, due_today_bool) for optional flex_due_rule. Supported examples: - salary 15/30 window 2 -> due from 13-17 and last-day-2 through last-day+2 if valid - weekly Monday Thursday -> due every Monday and Thursday - 2nd Saturday -> due every 2nd Saturday of the month - days 13,14,15,29,30,31
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._load_client_notes` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:2476 — Load client notes safely (cached). - Primary: <APP_DIR>/data/client_notes.json - Fallback (legacy): <CWD>/data/client_notes.json - Shallow-merge (primary wins on conflicts) - Cached in-memory to avoid frequent disk reads. - Logs problems to data/spina_app.log and shows a one-time warning if unreadab
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.import_from_excel_with_reasons` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:25463 — Import the Excel 'range template' where columns are: Client Name | 2025-10-01 | 2025-10-01 Reason | 2025-10-02 | 2025-10-02 Reason | ... Saves both Amount and Reason for each date.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._collect_day_flags_for_month` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:25963 — txns: iterable of dicts/rows having keys: 'date'|'d', 'payment'|'amt', 'description'|'desc' Returns dict: day(date)-> {'adv':bool, 'adv_paid_on':set(str), 'reason':str or None, 'paid':float} Reporting rules: - ADV is marked ONLY on the COVERED days (NOT on the payment date). - Covered days also stor
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.parse_advance_ranges` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3649 — Parse one or more ADV date ranges from a transaction description. Supported tags (whitespace/case-tolerant): - [ADV:YYYY-MM-DD..YYYY-MM-DD] (single range) - [ADV:YYYY-MM-DD,YYYY-MM-DD,YYYY-MM-DD] (explicit days) - [ADV:range;range;...] where range is either: * YYYY-MM-DD..YYYY-MM-DD * YYYY-MM-DD (si
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select._populate_collector_details` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:19976 — Update the right panel: selected name, stats, areas tree, notes.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._populate_collector_details` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:36477 — Update the right panel: selected name, stats, areas tree, notes.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._sum_paid_per_day` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8088 — Sum payments per date in a way that matches the app's Data Bank behavior. - Data Bank updates are keyed by (name, loan_type, date) so normally there's only 1 row per date. - If legacy/duplicate rows exist, we treat the **last non-zero** payment as the effective payment. - We do NOT let later 0.00 "r
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.delete_selected_cell` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:12847 — Removes delete selected cell for the data bank feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v23_client_form.save` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:40644 — Handles save for the clients feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_run_auto_daily_close` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:36912 — Auto-close Data Bank dates that are older than the configured delay.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.get_client_notes_in_range` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:2784 — Return list of (date, text) notes for 'name' between s and e inclusive. - Includes default (undated) note(s) as ("", text) first when present. - When include_type=True, includes loan-type specific notes for the current mode. - If include_other_type=True, also includes the other loan type (prefixed).
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._migrate_legacy_notes_by_name` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:2870 — Migrate legacy name-based notes (old_name and '<loan_type>::old_name') into stable-id keys. Use this when a client's name changes to avoid orphaning notes that were stored under the old name. Returns True if any changes were saved.
- `spina_app.area_hierarchy_ops._planned_subtree` — spina_app/area_hierarchy_ops.py:158 — Handles planned subtree for the other feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._parse_reason_color_token_meta` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:25694 — Extract [RC:...] token plus optional window meta from the description. Supported token payloads (inside the brackets): - '#RRGGBB' - 'red' / 'green' / etc - '#RRGGBB;D:3' -> days=3 (inclusive, starting from the reason's date) - '#RRGGBB;UNTIL:YYYY-MM-DD' -> until (inclusive) - 'red;D:3' / 'red;UNTIL
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.NoteEditorDialog._migrate_legacy_notes_if_needed` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3029 — Move legacy name-based keys into stable-id keys for this client (best-effort). This prevents collisions if names repeat, and keeps notes attached even if a name changes. Runs only when we have a stable id (person_uid or client_uid).
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._collectors_areas_drag_end` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:19850 — Handles collectors areas drag end for the collectors feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._resolve_note_key_scoped` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:2374 — Resolve a notes_dict key for a client. Preferred (stable) keys: - shared scope: PID|<person_uid> (or CID|<client_uid> fallback) - type scope: PT|<person_uid>|<loan_type> (or CID|<client_uid> fallback) Legacy fallback keys remain supported: - shared: name - type: '<loan_type>::<name>' Uses candidate 
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_databank_close_dialog._load` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:10419 — Handles load for the data bank feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina__client_due_meta` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:22949 — Return (day_due_label, due_today_bool) using stored schedule fields when present.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._save_collector_notes` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:33632 — Update one collector's notes in collectors.json (atomic, normalized schema).
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app__maybe_suggest_link_clients` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:29111 — Handles app maybe suggest link clients for the clients feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._system_data_refresh_summary` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:9433 — Handles system data refresh summary for the data bank feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_sql` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:632 — Translate common SQLite SQL into PostgreSQL-compatible SQL.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.set_client_note` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:2723 — Persist note for client. scope: - 'shared' (default): shared notes (prefer person_uid/client_uid; legacy name fallback) - 'type': loan-type specific notes (prefer person_uid+loan_type or client_uid; legacy fallback)
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app__client_form._flex_due_options` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:27562 — Handles flex due options for the clients feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.export_monthly_template` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:23595 — Export an Excel template for the current visible month (view-only data entry). Columns: Client Name + one column per date (YYYY-MM-DD). Users will fill payments in Excel and use 'Import from Excel' to load into the app.
- `spina_app.tabs.dashboard._spina_populate_dashboard_tree` — spina_app/tabs/dashboard.py:812 — Handles spina populate dashboard tree for the dashboard feature.
- `spina_app.theme_palettes._spina_v21_cash_colors` — spina_app/theme_palettes.py:44 — Handles spina v21 cash colors for the settings feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.get_client_note` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:2670 — Fetch a note for a client. scope: - 'shared' (default): shared notes (prefer person_uid/client_uid; legacy name fallback) - 'type': loan-type specific notes (prefer person_uid+loan_type or client_uid; legacy fallback) - 'effective': prefer type-specific if present, otherwise shared
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.resolve_area_order_from_prefs` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:2021 — NO-UI resolver: - Reads order from data/ledger_prefs.json["areas_order"] - Case/whitespace-insensitive matching - Appends new areas (not in prefs) alphabetically Returns arranged list.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.draw_notes_aligned` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8192 — Draws: Note: YYYY-MM-DD wrapped note text (blank) continuation lines aligned under text column Returns the new y after drawing.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.generate_client_pdf._draw_month_block` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:27203 — Handles draw month block for the clients feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._ui_call` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:13691 — Call a UI function from any thread and wait for completion. - If called from the Tk main thread, runs immediately. - If called from a worker thread, marshals execution onto the Tk main thread. - Includes a timeout to avoid deadlocks when the UI is closing.
- `spina_app.area_hierarchy_ui._populate_area_tree` — spina_app/area_hierarchy_ui.py:113 — Render a true parent/child folder tree and return its UID lookup.
- `spina_app.theme_palettes._spina_v24_cilog_colors` — spina_app/theme_palettes.py:98 — Handles spina v24 cilog colors for the clients feature.
- `spina_app.theme_palettes._spina_v18_dashboard_palette` — spina_app/theme_palettes.py:279 — Handles spina v18 dashboard palette for the dashboard feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._run_long_task._finish` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:13848 — Handles finish for the other feature.
- …and 526 more.

### Ui Only

**186 symbols · 14,473 function lines**

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:19918 — Populate the right-side details panel for the selected collector.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app__client_form` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:27499 — Handles app client form for the clients feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app_open_client_history_dialog` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:28449 — Handles app open client history dialog for the clients feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v23_client_form` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:40301 — Handles spina v23 client form for the clients feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v27_collector_editor_dialog` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:41823 — Modern route editor: Available Areas vs Assigned Route Order.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._build_collectors_tab` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:19062 — Collector's Route UI (organized + obvious selection + inline edit). Adds: - Obvious selection column (radio in single-select, checkbox in multi-select) - Per-row Actions column (View / Edit / Delete) - Multi-select bulk bar (Delete / Export / Clear) - Inline edit in the right-side panel (name + area
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v25_build_collectors_tab` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:41020 — Handles spina v25 build collectors tab for the collectors feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v27_build_collectors_tab` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:41494 — Handles spina v27 build collectors tab for the collectors feature.
- `spina_app.tabs.cash_control._spina_v21_cash_build_tab` — spina_app/tabs/cash_control.py:37 — Handles spina v21 cash build tab for the cash control feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._run_long_task` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:13800 — Run work_fn() in a background thread with a simple modal 'Please wait' dialog. Improvements: - Optional Cancel button (signals a cancel_event to work_fn if it supports it) - Optional timeout (prevents UI from hanging forever on stuck tasks) - Cleanup is guarded so it can't run twice
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.refresh_data_grid` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:15886 — Refreshes refresh data grid for the data bank feature.
- `spina_app.area_hierarchy_ui.open_area_manager` — spina_app/area_hierarchy_ui.py:459 — Open the folder-style unlimited hierarchical Area manager.
- `spina_app.tabs.client_info_logs._spina_v24_build_client_info_logs_tab` — spina_app/tabs/client_info_logs.py:202 — Handles spina v24 build client info logs tab for the clients feature.
- `spina_app.tabs.dashboard._spina_v17_build_dashboard_tab` — spina_app/tabs/dashboard.py:106 — Handles spina v17 build dashboard tab for the dashboard feature.
- `spina_app.tabs.clients._spina_v23_build_clients_tab` — spina_app/tabs/clients.py:168 — Handles spina v23 build clients tab for the clients feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_perf_refresh_data_grid` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:34608 — Fast Data Bank month grid refresh using bulk month transaction query.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.export_range_template` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:25279 — Export an Excel template for payments over a chosen date range. Presets: This Month / This Year / Custom (YYYY-MM-DD).
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_areas_manager` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:18793 — Open the Areas manager window (create/rename/delete areas).
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._build_clients_tab` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:18614 — Builds build clients tab for the clients feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._apply_ui_theme` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:14335 — Handles apply ui theme for the settings feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._pick_missed_reason` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:10885 — Modal checkbox dialog to choose one or more missed-payment reasons, plus optional 'Other' note. If 'Advance' is selected, you can enter a date range. Returns a single string (joined reasons + optional [ADV:s..e] tag) or None if cancelled.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._setup_style` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:14073 — Centralized ttk styling. Goals: - cleaner spacing / typography - readable Treeviews - consistent Notebook tabs - best-effort HiDPI handling on Windows
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._collector_editor_dialog` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:12302 — Unified editor for Collector name + route areas + notes.
- `spina_app.tabs.client_info_logs._spina_build_client_info_logs_tab` — spina_app/tabs/client_info_logs.py:562 — Handles spina build client info logs tab for the clients feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_cashctl_build_tab` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:36153 — Handles spina cashctl build tab for the cash control feature.
- `spina_app.area_hierarchy_ui.select_area_node` — spina_app/area_hierarchy_ui.py:163 — Open a modal folder browser and return the selected active Area node.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.link_selected_client` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:23371 — Manually link the selected client to another loan type record.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.export_range_template` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:24484 — Export an Excel template for payments over a chosen date range. Presets: This Month / This Year / Custom (YYYY-MM-DD).
- `spina_app.tabs.cash_control._spina_v21_cash_draw_charts` — spina_app/tabs/cash_control.py:316 — Handles spina v21 cash draw charts for the cash control feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app_link_selected_client` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:28965 — Handles app link selected client for the clients feature.
- `spina_app.tabs.dashboard._spina_build_dashboard_tab` — spina_app/tabs/dashboard.py:705 — Handles spina build dashboard tab for the dashboard feature.
- `spina_app.navigation._rebuild_side_nav` — spina_app/navigation.py:94 — Rebuild the modern left-side navigation from the currently visible notebook tabs.
- `spina_app.tabs.client_info_logs._spina_v24_cilog_draw_charts` — spina_app/tabs/client_info_logs.py:81 — Handles spina v24 cilog draw charts for the clients feature.
- `spina_app.tabs.clients._spina_perf_refresh_clients` — spina_app/tabs/clients.py:706 — Fast Clients tab refresh for large datasets.
- `spina_app.tabs.data_bank_shell._resize_databank_columns` — spina_app/tabs/data_bank_shell.py:138 — Resize Data Bank columns responsively. Supports 'freeze panes' layout: - name_tree shows Client + Area (fixed, no horizontal scroll) - days_tree shows day columns with horizontal scroll
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.NoteEditorDialog._build_ui` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3172 — Builds build ui for the notes feature.
- `spina_app.tabs.client_info_logs._spina_v24_render_client_info_logs` — spina_app/tabs/client_info_logs.py:453 — Handles spina v24 render client info logs for the clients feature.
- `spina_app.tabs.dashboard._spina_v17_populate_dashboard_tree` — spina_app/tabs/dashboard.py:444 — Handles spina v17 populate dashboard tree for the dashboard feature.
- `spina_app.area_hierarchy_ui._select_parent_area` — spina_app/area_hierarchy_ui.py:379 — Select a new parent folder; an empty string means move to the root.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_databank_close_history_dialog` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:9699 — Handles open databank close history dialog for the data bank feature.
- …and 146 more.

## Suggested larger application modularization batches

### Batch 1: Clients (787 lines)

Source file: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py`

Risk mix: `database_read`, `support`, `ui_only`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._load_client_notes` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:2476 — Load client notes safely (cached). - Primary: <APP_DIR>/data/client_notes.json - Fallback (legacy): <CWD>/data/client_notes.json - Shallow-merge (primary wins on conflicts) - Cached in-memory to avoid frequent disk reads. - Logs problems to data/spina_app.log and shows a one-time warning if unreadab
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.get_client_note` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:2670 — Fetch a note for a client. scope: - 'shared' (default): shared notes (prefer person_uid/client_uid; legacy name fallback) - 'type': loan-type specific notes (prefer person_uid+loan_type or client_uid; legacy fallback) - 'effective': prefer type-specific if present, otherwise shared
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.set_client_note` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:2723 — Persist note for client. scope: - 'shared' (default): shared notes (prefer person_uid/client_uid; legacy name fallback) - 'type': loan-type specific notes (prefer person_uid+loan_type or client_uid; legacy fallback)
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.get_client_notes_in_range` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:2784 — Return list of (date, text) notes for 'name' between s and e inclusive. - Includes default (undated) note(s) as ("", text) first when present. - When include_type=True, includes loan-type specific notes for the current mode. - If include_other_type=True, also includes the other loan type (prefixed).
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._show_no_area_clients` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:12207 — Show clients that still have blank area (needs assignment).
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._build_clients_tab` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:18614 — Builds build clients tab for the clients feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina__client_schedule_anchor` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:22933 — Handles spina client schedule anchor for the clients feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina__client_due_meta` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:22949 — Return (day_due_label, due_today_bool) using stored schedule fields when present.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._normalize_client_name_for_lookup` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:25822 — Normalize a display name back to the DB name (Collector Route / PDFs). Some PDF layouts append markers like "(7x7)" to the displayed name to avoid duplicates. Those markers must be stripped before looking up transactions/reasons/ADV in SQLite. We also trim and normalize whitespace.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app__get_selected_client_name` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:27487 — Handles app get selected client name for the clients feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app_schedule_refresh_clients` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:28303 — Debounce Clients search so refresh doesn't run on every keystroke.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app_link_selected_client` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:28965 — Handles app link selected client for the clients feature.

### Batch 2: Data Bank (783 lines)

Source file: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py`

Risk mix: `database_read`, `support`, `ui_only`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.delete_selected_cell` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:12847 — Removes delete selected cell for the data bank feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._build_data_tab` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:15801 — Builds build data tab for the data bank feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.refresh_data_grid` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:15886 — Refreshes refresh data grid for the data bank feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._import_from_excel_entry` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:17247 — Import payments from Excel. Supports: 1) Date-grid templates (first row has 'Client Name' + date columns like YYYY-MM-DD) via _import_from_excel_core() 2) One-day Daily Collection templates (Client | Payment | Reason), optionally grouped by [AREA] rows Notes: - Unknown clients are skipped (to avoid 
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._import_from_excel_core` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:18447 — Auto-detect payments and reasons from Excel. Rules: " First row = headers. Must include 'Client Name' and at least one date column. " A date column can be an Excel date/datetime or a string 'YYYY-MM-DD'. " If a cell under a date column is numeric (or numeric-looking text): that's the amount. " If a 
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.import_from_excel_with_reasons` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:25463 — Import the Excel 'range template' where columns are: Client Name | 2025-10-01 | 2025-10-01 Reason | 2025-10-02 | 2025-10-02 Reason | ... Saves both Amount and Reason for each date.

### Batch 3: Collectors (772 lines)

Source file: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py`

Risk mix: `database_read`, `support`, `ui_only`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._delete_selected_collector` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:33950 — Safe delete action used by keybinds/buttons/menus.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._edit_selected_collector` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:33983 — Safe edit action for the context menu ('Full Editor…').
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._collectors_areas_drag_motion` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:34000 — Drag-to-reorder areas listbox (MOVE item) without index-shift bugs.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._populate_collector_details` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:36477 — Update the right panel: selected name, stats, areas tree, notes.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:36574 — Populate the right-side details panel for the selected collector.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_route_notice_key` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:37233 — Handles spina route notice key for the collectors feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_route_notice_save` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:37253 — Handles spina route notice save for the collectors feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_route_notice_upsert` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:37266 — Handles spina route notice upsert for the collectors feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_crc_route_area_matches` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:37585 — Match route area to client area, including MAIN-only collector routes covering subareas.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_crc_collector_for_area` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:37612 — Handles spina crc collector for area for the collectors feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_crc_active_filtered_areas_for_collector` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:38189 — Match the Collector Route screen filtering so blank/archived-only areas are skipped.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v25_collector_button` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:40975 — Handles spina v25 collector button for the collectors feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v27_route_button` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:41443 — Handles spina v27 route button for the collectors feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v27_build_collectors_tab` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:41494 — Handles spina v27 build collectors tab for the collectors feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v27_get_route_master_areas` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:41789 — Handles spina v27 get route master areas for the collectors feature.

### Batch 4: Clients (757 lines)

Source file: `spina_app/tabs/clients.py`

Risk mix: `database_read`, `support`, `ui_only`

- `spina_app.tabs.clients.configure_clients_dependencies` — spina_app/tabs/clients.py:38 — Bind application-owned callbacks used by the Clients presentation module.
- `spina_app.tabs.clients._spina_v23_button` — spina_app/tabs/clients.py:50 — Handles spina v23 button for the clients feature.
- `spina_app.tabs.clients._spina_v23_card` — spina_app/tabs/clients.py:80 — Handles spina v23 card for the clients feature.
- `spina_app.tabs.clients._spina_v23_selected_name_lt` — spina_app/tabs/clients.py:92 — Handles spina v23 selected name lt for the clients feature.
- `spina_app.tabs.clients._spina_v23_refresh_client_profile` — spina_app/tabs/clients.py:113 — Handles spina v23 refresh client profile for the clients feature.
- `spina_app.tabs.clients._spina_v23_build_clients_tab` — spina_app/tabs/clients.py:168 — Handles spina v23 build clients tab for the clients feature.
- `spina_app.tabs.clients._spina_v23_entry` — spina_app/tabs/clients.py:402 — Handles spina v23 entry for the clients feature.
- `spina_app.tabs.clients._spina_v23_update_client_cards` — spina_app/tabs/clients.py:413 — Handles spina v23 update client cards for the clients feature.
- `spina_app.tabs.clients._db_get_client_picture` — spina_app/tabs/clients.py:445 — Handles db get client picture for the clients feature.
- `spina_app.tabs.clients._app__selected_client_name_and_lt` — spina_app/tabs/clients.py:456 — Handles app selected client name and lt for the clients feature.
- `spina_app.tabs.clients._app_install_clients_picture_ui` — spina_app/tabs/clients.py:480 — Handles app install clients picture ui for the clients feature.
- `spina_app.tabs.clients._spina_perf_clients_rows` — spina_app/tabs/clients.py:537 — Bulk load rows for Clients tab in one/few queries, avoiding per-row get_client_info().
- `spina_app.tabs.clients._spina_perf_refresh_clients` — spina_app/tabs/clients.py:706 — Fast Clients tab refresh for large datasets.
- `spina_app.tabs.clients._spina__client_due_meta` — spina_app/tabs/clients.py:797 — Handles spina client due meta for the clients feature.

### Batch 5: Dashboard (753 lines)

Source file: `spina_app/tabs/dashboard.py`

Risk mix: `support`, `ui_only`

- `spina_app.tabs.dashboard.configure_legacy_dashboard_feature` — spina_app/tabs/dashboard.py:37 — Attach main-module services without importing the large entry module.
- `spina_app.tabs.dashboard._spina_dashboard_fetch_rows` — spina_app/tabs/dashboard.py:53 — Handles spina dashboard fetch rows for the dashboard feature.
- `spina_app.tabs.dashboard._log_exc` — spina_app/tabs/dashboard.py:59 — Handles log exc for the dashboard feature.
- `spina_app.tabs.dashboard._spina_v18_draw_dashboard_charts` — spina_app/tabs/dashboard.py:64 — Handles spina v18 draw dashboard charts for the dashboard feature.
- `spina_app.tabs.dashboard._spina_v20_draw_dashboard_charts` — spina_app/tabs/dashboard.py:70 — Handles spina v20 draw dashboard charts for the dashboard feature.
- `spina_app.tabs.dashboard._spina_v17_visible_dashboard_rows` — spina_app/tabs/dashboard.py:78 — Handles spina v17 visible dashboard rows for the dashboard feature.
- `spina_app.tabs.dashboard._spina_v17_build_dashboard_tab` — spina_app/tabs/dashboard.py:106 — Handles spina v17 build dashboard tab for the dashboard feature.
- `spina_app.tabs.dashboard._spina_v17_populate_dashboard_tree` — spina_app/tabs/dashboard.py:444 — Handles spina v17 populate dashboard tree for the dashboard feature.
- `spina_app.tabs.dashboard._spina_v17_refresh_dashboard` — spina_app/tabs/dashboard.py:529 — Handles spina v17 refresh dashboard for the dashboard feature.
- `spina_app.tabs.dashboard._spina_dashboard_visible_rows` — spina_app/tabs/dashboard.py:551 — Handles spina dashboard visible rows for the dashboard feature.
- `spina_app.tabs.dashboard._spina_v19_visible_dashboard_rows` — spina_app/tabs/dashboard.py:571 — Dashboard should show all active clients by default, not only priority clients.
- `spina_app.tabs.dashboard._spina_v20_visible_rows` — spina_app/tabs/dashboard.py:603 — Handles spina v20 visible rows for the dashboard feature.
- `spina_app.tabs.dashboard._spina_dashboard_summary_text` — spina_app/tabs/dashboard.py:615 — Handles spina dashboard summary text for the dashboard feature.
- `spina_app.tabs.dashboard._spina_configure_dashboard_tree_theme` — spina_app/tabs/dashboard.py:641 — Keep Dashboard Treeview text readable in both Light and Dark mode. The Dashboard uses colored status tags. In Dark Mode, the app-level Treeview foreground is light; if the tag background is also light pastel, the text becomes hard to read. This function sets both background AND foreground for every 
- `spina_app.tabs.dashboard._spina_build_dashboard_tab` — spina_app/tabs/dashboard.py:705 — Handles spina build dashboard tab for the dashboard feature.
- `spina_app.tabs.dashboard._spina_populate_dashboard_tree` — spina_app/tabs/dashboard.py:812 — Handles spina populate dashboard tree for the dashboard feature.
- `spina_app.tabs.dashboard._spina_refresh_dashboard` — spina_app/tabs/dashboard.py:866 — Handles spina refresh dashboard for the dashboard feature.
- `spina_app.tabs.dashboard._spina_apply_dashboard_role` — spina_app/tabs/dashboard.py:886 — Handles spina apply dashboard role for the dashboard feature.

### Batch 6: Clients (722 lines)

Source file: `spina_app/tabs/client_info_logs.py`

Risk mix: `support`, `ui_only`

- `spina_app.tabs.client_info_logs.configure_client_info_logs_dependencies` — spina_app/tabs/client_info_logs.py:26 — Bind application-owned callbacks used by the CILog presentation module.
- `spina_app.tabs.client_info_logs._spina_v24_cilog_action_color` — spina_app/tabs/client_info_logs.py:38 — Handles spina v24 cilog action color for the clients feature.
- `spina_app.tabs.client_info_logs._spina_v24_cilog_stats` — spina_app/tabs/client_info_logs.py:56 — Handles spina v24 cilog stats for the clients feature.
- `spina_app.tabs.client_info_logs._spina_v24_cilog_draw_charts` — spina_app/tabs/client_info_logs.py:81 — Handles spina v24 cilog draw charts for the clients feature.
- `spina_app.tabs.client_info_logs._spina_v24_cilog_update_cards` — spina_app/tabs/client_info_logs.py:176 — Handles spina v24 cilog update cards for the clients feature.
- `spina_app.tabs.client_info_logs._spina_v24_build_client_info_logs_tab` — spina_app/tabs/client_info_logs.py:202 — Handles spina v24 build client info logs tab for the clients feature.
- `spina_app.tabs.client_info_logs._spina_v24_render_client_info_logs` — spina_app/tabs/client_info_logs.py:453 — Handles spina v24 render client info logs for the clients feature.
- `spina_app.tabs.client_info_logs._spina_v24_refresh_client_info_logs` — spina_app/tabs/client_info_logs.py:537 — Handles spina v24 refresh client info logs for the clients feature.
- `spina_app.tabs.client_info_logs._spina_build_client_info_logs_tab` — spina_app/tabs/client_info_logs.py:562 — Handles spina build client info logs tab for the clients feature.
- `spina_app.tabs.client_info_logs._spina_render_client_info_logs` — spina_app/tabs/client_info_logs.py:695 — Handles spina render client info logs for the clients feature.
- `spina_app.tabs.client_info_logs._spina_refresh_client_info_logs` — spina_app/tabs/client_info_logs.py:749 — Handles spina refresh client info logs for the clients feature.

### Batch 7: Collectors (697 lines)

Source file: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py`

Risk mix: `database_read`, `support`, `ui_only`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.list_databank_day_collectors` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6662 — Handles list databank day collectors for the collectors feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.get_databank_day_collector_totals` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6698 — Retrieves get databank day collector totals for the collectors feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._build_databank_collector_defaults_for_date` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:9628 — Builds build databank collector defaults for date for the collectors feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._show_conflicts` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:12152 — Show areas assigned to multiple collectors.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._show_unassigned_areas` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:12178 — Show areas not assigned to any collector (plus any unknown route areas).
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._collector_editor_dialog` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:12302 — Unified editor for Collector name + route areas + notes.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._collectors_name_from_values` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:19412 — Return the collector name from a Treeview row values tuple. Backwards compatible with older layouts: - Old layout: first value is the collector name. - New layout: first value is a select marker (radio/checkbox/bullet), second is the collector name.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_multi_toggle` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:19475 — Handles on collectors multi toggle for the collectors feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._collectors_areas_drag_start` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:19824 — Handles collectors areas drag start for the collectors feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._collectors_areas_drag_motion` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:19830 — Handles collectors areas drag motion for the collectors feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._collectors_areas_drag_end` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:19850 — Handles collectors areas drag end for the collectors feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._schedule_collectors_refresh` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:30130 — Debounce refresh_collectors while typing in Search.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._clear_collectors_search_filters` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:30150 — Clear search + quick filters for Collector's Route UI.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_tree_wheel` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:33610 — Ensure mousewheel scroll works on Collector Route list (Treeview).
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._save_collector_notes` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:33632 — Update one collector's notes in collectors.json (atomic, normalized schema).
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._save_selected_collector_notes` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:33696 — Save Notes from the right panel to collectors.json (atomic).
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_multi_toggle` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:33789 — Toggle multi-select mode for Collector Route list (checkbox Sel column).
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_tree_wheel` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:33811 — Mouse wheel scroll for Collector Route list (Treeview).

### Batch 8: Payments (594 lines)

Source file: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py`

Risk mix: `database_read`, `support`, `ui_only`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._PgCompatConnection.in_transaction` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:858 — Handles in transaction for the payments feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina__merge_payment_mode` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1172 — Handles spina merge payment mode for the payments feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.parse_advance_ranges` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3649 — Parse one or more ADV date ranges from a transaction description. Supported tags (whitespace/case-tolerant): - [ADV:YYYY-MM-DD..YYYY-MM-DD] (single range) - [ADV:YYYY-MM-DD,YYYY-MM-DD,YYYY-MM-DD] (explicit days) - [ADV:range;range;...] where range is either: * YYYY-MM-DD..YYYY-MM-DD * YYYY-MM-DD (si
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.parse_advance_range` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3758 — Backward-compatible helper: return first (start,end) ADV range if present.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.get_transaction` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7586 — Retrieves get transaction for the payments feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.get_transaction_by_uid` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7606 — Fetch a transaction by (client_uid, loan_type, date).
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._is_advance_on` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7879 — Return True if any transaction for `name` has an [ADV:s..e] tag that covers day_yyyy_mm_dd. Falls back quietly to False if anything goes wrong.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._adv_paid_on_dates_covering` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7927 — Return sorted list of *payment dates* (YYYY-MM-DD) whose ADV tag covers `day_yyyy_mm_dd`. Rules: - We only look at transactions whose description contains an [ADV:...] tag. - We EXCLUDE the payment date itself (so ADV is shown only on the covered days, not on the payment day). - If multiple ADV paym
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._sum_paid_per_day` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8088 — Sum payments per date in a way that matches the app's Data Bank behavior. - Data Bank updates are keyed by (name, loan_type, date) so normally there's only 1 row per date. - If legacy/duplicate rows exist, we treat the **last non-zero** payment as the effective payment. - We do NOT let later 0.00 "r
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._pick_missed_reason` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:10885 — Modal checkbox dialog to choose one or more missed-payment reasons, plus optional 'Other' note. If 'Advance' is selected, you can enter a date range. Returns a single string (joined reasons + optional [ADV:s..e] tag) or None if cancelled.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_perf_month_transactions` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:34536 — Return {(row_key, yyyy-mm-dd): payment} for visible clients in the month using one range query.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_crc_build_paid_cache_for_date` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:38154 — Return {(lower_name, lower_loan_type): paid_amount} for the closed date.

### Batch 9: Utilities (503 lines)

Source file: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py`

Risk mix: `support`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._open_path` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1192 — Safely open a generated file/folder. v29 fix: Python 3.14 on Windows can crash hard with os.startfile() in some Tk/PDF workflows. Use subprocess instead so PDF generation does not close the app.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._parse_ymd` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1589 — Handles parse ymd for the utilities feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.pick_date_range` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1929 — Handles pick date range for the utilities feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.NoteEditorDialog._validate_date_or_warn` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3123 — Validates validate date or warn for the utilities feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._parse_any_adv_range` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3590 — Handles parse any adv range for the utilities feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._audit_parse_json_payload` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6357 — Handles audit parse json payload for the utilities feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._getv` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8075 — Safe getter for dict / sqlite3.Row / objects.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._wrap_to_width` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8178 — Handles wrap to width for the utilities feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._walk_widgets` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:12586 — Handles walk widgets for the utilities feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._audit_parse_date_filters` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:13165 — Handles audit parse date filters for the utilities feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._format_bytes` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:14829 — Handles format bytes for the utilities feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._parse_adv_range_any` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:25625 — Handles parse adv range any for the utilities feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._parse_reason_color_token` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:25668 — Extract a [RC:...] token (hex or a color-name) from the description. Returns: (color_hex or "", desc_without_token)
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._parse_reason_color_token_meta` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:25694 — Extract [RC:...] token plus optional window meta from the description. Supported token payloads (inside the brackets): - '#RRGGBB' - 'red' / 'green' / etc - '#RRGGBB;D:3' -> days=3 (inclusive, starting from the reason's date) - '#RRGGBB;UNTIL:YYYY-MM-DD' -> until (inclusive) - 'red;D:3' / 'red;UNTIL
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina__parse_flexible_due_rule` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:37038 — Return (label, due_today_bool) for optional flex_due_rule. Supported examples: - salary 15/30 window 2 -> due from 13-17 and last-day-2 through last-day+2 if valid - weekly Monday Thursday -> due every Monday and Thursday - 2nd Saturday -> due every 2nd Saturday of the month - days 13,14,15,29,30,31

### Batch 10: Notes (471 lines)

Source file: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py`

Risk mix: `support`, `ui_only`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._candidate_note_keys` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:2296 — Handles candidate note keys for the notes feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._resolve_note_key` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:2313 — Return an existing key in notes_dict matching 'name' using _candidate_note_keys. If none found, default to the original name.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._note_scoped_prefix` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:2336 — Handles note scoped prefix for the notes feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._note_id_key` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:2339 — Stable notes keys that do NOT depend on client name. kind: - 'CID' : client_uid (per record) - 'PID' : person_uid (shared across Regular/7x7 when linked) Uses '|' separators to avoid colliding with legacy '<loan_type>::<name>' keys.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._note_type_key` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:2356 — Type-scoped key stable across name changes. If person_uid exists (linked), store type notes under: PT|<person_uid>|<loan_type_norm> This lets us retrieve the other loan type's notes without needing that row's client_uid.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._resolve_note_key_scoped` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:2374 — Resolve a notes_dict key for a client. Preferred (stable) keys: - shared scope: PID|<person_uid> (or CID|<client_uid> fallback) - type scope: PT|<person_uid>|<loan_type> (or CID|<client_uid> fallback) Legacy fallback keys remain supported: - shared: name - type: '<loan_type>::<name>' Uses candidate 
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._ensure_notes_dir` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:2469 — Handles ensure notes dir for the notes feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._migrate_legacy_notes_by_name` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:2870 — Migrate legacy name-based notes (old_name and '<loan_type>::old_name') into stable-id keys. Use this when a client's name changes to avoid orphaning notes that were stored under the old name. Returns True if any changes were saved.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.NoteEditorDialog.__init__` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:2961 — Handles init for the notes feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.NoteEditorDialog._migrate_legacy_notes_if_needed` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3029 — Move legacy name-based keys into stable-id keys for this client (best-effort). This prevents collisions if names repeat, and keeps notes attached even if a name changes. Runs only when we have a stable id (person_uid or client_uid).
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.NoteEditorDialog._title_text` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3100 — Handles title text for the notes feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.NoteEditorDialog._set_dirty` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3104 — Updates set dirty for the notes feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.NoteEditorDialog._note_date_value` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3112 — Handles note date value for the notes feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.NoteEditorDialog._sig_for_text` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3116 — Handles sig for text for the notes feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.NoteEditorDialog._auto_choose_scope` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3138 — Handles auto choose scope for the notes feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.NoteEditorDialog._scope_label` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3149 — Handles scope label for the notes feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.NoteEditorDialog._focus_search` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3163 — Handles focus search for the notes feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.NoteEditorDialog._build_ui` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3172 — Builds build ui for the notes feature.

### Batch 11: Clients (431 lines)

Source file: `spina_app/client_queries.py`

Risk mix: `database_read`, `support`

- `spina_app.client_queries.configure_client_queries_dependencies` — spina_app/client_queries.py:27 — Bind application-owned globals required by the extracted LoanDB methods.
- `spina_app.client_queries.get_all_clients` — spina_app/client_queries.py:49 — Return client names (optionally filtered by loan_type) with optional search. search_by: - 'all' / 'both' : match across common client fields (default) - 'client' : match in client name only - 'area' : match in area only - 'principal' : match in principal (as text) - 'released' : match in date_releas
- `spina_app.client_queries.get_client_info` — spina_app/client_queries.py:337 — Retrieves get client info for the clients feature.
- `spina_app.client_queries.get_client_link_meta` — spina_app/client_queries.py:353 — Return (client_uid, person_uid, link_opt_out) for a client.
- `spina_app.client_queries.find_clients_by_person_uid` — spina_app/client_queries.py:374 — Return list of client rows linked to this person_uid.
- `spina_app.client_queries.get_client_uid` — spina_app/client_queries.py:386 — Return client_uid for (name, loan_type).
- `spina_app.client_queries.get_client_by_uid` — spina_app/client_queries.py:401 — Retrieves get client by uid for the clients feature.
- `spina_app.client_queries.get_client_history` — spina_app/client_queries.py:412 — Return audit history rows (most recent first). Prefer client_uid. Normalizes key names for UI: ts -> changed_at before_json -> old_json after_json -> new_json
- `spina_app.client_queries.get_person_uid_for_client_uid` — spina_app/client_queries.py:464 — Retrieves get person uid for client uid for the clients feature.

### Batch 12: Data Bank (420 lines)

Source file: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py`

Risk mix: `database_read`, `support`, `ui_only`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._databank_day_close_bucket` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6501 — Handles databank day close bucket for the data bank feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.get_databank_daily_total` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6526 — Retrieves get databank daily total for the data bank feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.get_databank_day_close` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6559 — Retrieves get databank day close for the data bank feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.is_databank_day_closed` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6592 — Handles is databank day closed for the data bank feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.list_databank_day_close_history` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6636 — Handles list databank day close history for the data bank feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.list_databank_day_close_records` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6978 — Handles list databank day close records for the data bank feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._clear_preview` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:9357 — Handles clear preview for the data bank feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._get_databank_focus_date` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:9362 — Retrieves get databank focus date for the data bank feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._show_system_data_tab` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:9386 — Handles show system data tab for the data bank feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._hide_system_data_tab` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:9397 — Handles hide system data tab for the data bank feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._system_data_get_date` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:9404 — Handles system data get date for the data bank feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._system_data_use_focus_date` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:9424 — Handles system data use focus date for the data bank feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._system_data_refresh_summary` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:9433 — Handles system data refresh summary for the data bank feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._system_data_open_close` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:9494 — Handles system data open close for the data bank feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._system_data_open_history` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:9506 — Handles system data open history for the data bank feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._system_data_open_records` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:9512 — Handles system data open records for the data bank feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._build_system_data_tab` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:9524 — Builds build system data tab for the data bank feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_databank_close_history_dialog` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:9699 — Handles open databank close history dialog for the data bank feature.

### Batch 13: Settings (419 lines)

Source file: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py`

Risk mix: `support`, `ui_only`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.load_settings` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:983 — Loads load settings for the settings feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.save_settings` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1017 — Saves save settings for the settings feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._theme_toggle_text` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:14213 — Handles theme toggle text for the settings feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.toggle_theme` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:14220 — Handles toggle theme for the settings feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.set_theme` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:14227 — Updates set theme for the settings feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._theme_palette` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:14288 — Handles theme palette for the settings feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._apply_ui_theme` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:14335 — Handles apply ui theme for the settings feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._apply_tk_theme_recursive` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:14537 — Handles apply tk theme recursive for the settings feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._refresh_modern_shell_theme` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:15169 — Apply theme colors to the modern sidebar shell and rebuild nav labels/buttons.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._refresh_header_theme` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:15232 — Apply the current theme colors to the modern top header.

### Batch 14: Cash Control (410 lines)

Source file: `spina_app/tabs/cash_control.py`

Risk mix: `support`, `ui_only`

- `spina_app.tabs.cash_control.configure_cash_control_dependencies` — spina_app/tabs/cash_control.py:25 — Bind application-owned display and logging helpers used by Cash Control.
- `spina_app.tabs.cash_control._spina_v21_cash_build_tab` — spina_app/tabs/cash_control.py:37 — Handles spina v21 cash build tab for the cash control feature.
- `spina_app.tabs.cash_control._spina_v21_cash_draw_charts` — spina_app/tabs/cash_control.py:316 — Handles spina v21 cash draw charts for the cash control feature.

### Batch 15: Collectors (407 lines)

Source file: `spina_app/tabs/collectors.py`

Risk mix: `support`, `ui_only`

- `spina_app.tabs.collectors._spina_v25_collector_card` — spina_app/tabs/collectors.py:16 — Handles spina v25 collector card for the collectors feature.
- `spina_app.tabs.collectors._spina_v25_style_collector_trees` — spina_app/tabs/collectors.py:29 — Handles spina v25 style collector trees for the collectors feature.
- `spina_app.tabs.collectors._spina_v25_update_collector_cards` — spina_app/tabs/collectors.py:54 — Handles spina v25 update collector cards for the collectors feature.
- `spina_app.tabs.collectors._collectors_get_selected_name` — spina_app/tabs/collectors.py:110 — Handles collectors get selected name for the collectors feature.
- `spina_app.tabs.collectors._collectors_toggle_sections` — spina_app/tabs/collectors.py:125 — Handles collectors toggle sections for the collectors feature.
- `spina_app.tabs.collectors._collectors_apply_markers` — spina_app/tabs/collectors.py:155 — Update the Sel column (radio/checkbox) based on current selection/multi checks.
- `spina_app.tabs.collectors._collectors_refresh_bulk_bar` — spina_app/tabs/collectors.py:192 — Handles collectors refresh bulk bar for the collectors feature.
- `spina_app.tabs.collectors._collectors_clear_checked` — spina_app/tabs/collectors.py:218 — Handles collectors clear checked for the collectors feature.
- `spina_app.tabs.collectors._collectors_start_inline_edit` — spina_app/tabs/collectors.py:232 — Start inline editing for the currently selected collector (right panel).
- `spina_app.tabs.collectors._collectors_load_inline_edit_fields` — spina_app/tabs/collectors.py:298 — Populate the right-side edit widgets from collectors.json cache.
- `spina_app.tabs.collectors._collectors_cancel_inline_edit` — spina_app/tabs/collectors.py:332 — Cancel inline editing and restore view widgets.
- `spina_app.tabs.collectors._collectors_choose_areas` — spina_app/tabs/collectors.py:375 — Pick areas via existing picker dialog, then load into listbox.
- `spina_app.tabs.collectors._collectors_add_area_text` — spina_app/tabs/collectors.py:393 — Handles collectors add area text for the collectors feature.
- `spina_app.tabs.collectors._collectors_remove_area` — spina_app/tabs/collectors.py:415 — Handles collectors remove area for the collectors feature.
- `spina_app.tabs.collectors._collectors_move_area` — spina_app/tabs/collectors.py:425 — Handles collectors move area for the collectors feature.

### Batch 16: Notes (359 lines)

Source file: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py`

Risk mix: `support`, `ui_only`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.NoteEditorDialog._collect_items` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3260 — Handles collect items for the notes feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.NoteEditorDialog._refresh_list` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3305 — Refreshes refresh list for the notes feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.NoteEditorDialog._on_list_select` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3331 — Handles on list select for the notes feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.NoteEditorDialog._pick_date` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3360 — Handles pick date for the notes feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.NoteEditorDialog._jump_today` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3370 — Handles jump today for the notes feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.NoteEditorDialog._jump_default` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3382 — Handles jump default for the notes feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.NoteEditorDialog._clear_text` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3390 — Handles clear text for the notes feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.NoteEditorDialog._open_notes_file` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3401 — Handles open notes file for the notes feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.NoteEditorDialog._load_note` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3412 — Loads load note for the notes feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.NoteEditorDialog._save_note` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3446 — Saves save note for the notes feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.NoteEditorDialog._delete_note` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3490 — Removes delete note for the notes feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.NoteEditorDialog._on_text_modified` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3530 — Handles on text modified for the notes feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.NoteEditorDialog._schedule_autosave` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3540 — Handles schedule autosave for the notes feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.NoteEditorDialog._confirm_before_switch` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3554 — Handles confirm before switch for the notes feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.NoteEditorDialog._save_and_close` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3574 — Saves save and close for the notes feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.NoteEditorDialog._close` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3578 — Handles close for the notes feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.draw_notes_aligned` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8192 — Draws: Note: YYYY-MM-DD wrapped note text (blank) continuation lines aligned under text column Returns the new y after drawing.

### Batch 17: Navigation (358 lines)

Source file: `spina_app/navigation.py`

Risk mix: `support`, `ui_only`

- `spina_app.navigation._noop_log` — spina_app/navigation.py:11 — Handles noop log for the navigation feature.
- `spina_app.navigation.fmt_currency` — spina_app/navigation.py:18 — Handles fmt currency for the navigation feature.
- `spina_app.navigation.configure_navigation_dependencies` — spina_app/navigation.py:22 — Bind application-owned logging and currency display helpers.
- `spina_app.navigation._update_data_toolbar` — spina_app/navigation.py:29 — Updates update data toolbar for the navigation feature.
- `spina_app.navigation._side_nav_items` — spina_app/navigation.py:60 — Return visible main tabs as (tab_widget, title, icon).
- `spina_app.navigation._rebuild_side_nav` — spina_app/navigation.py:94 — Rebuild the modern left-side navigation from the currently visible notebook tabs.
- `spina_app.navigation._refresh_side_nav_selection` — spina_app/navigation.py:201 — Update sidebar button colors to match the selected notebook tab.
- `spina_app.navigation._header_palette` — spina_app/navigation.py:237 — Compact color palette for the modern top header.
- `spina_app.navigation._make_header_button` — spina_app/navigation.py:282 — Create a flatter, modern top-bar button using tk.Button for better dark-mode control.
- `spina_app.navigation._refresh_mode_toggle` — spina_app/navigation.py:311 — Update the Regular/7x7 segmented buttons after a mode change or theme change.
- `spina_app.navigation._vscroll` — spina_app/navigation.py:345 — Handles vscroll for the navigation feature.
- `spina_app.navigation._month_label` — spina_app/navigation.py:354 — Handles month label for the navigation feature.
- `spina_app.navigation._on_mousewheel_sync` — spina_app/navigation.py:358 — Mouse wheel scroll should move both name_tree (left) and days_tree (right) together.
- `spina_app.navigation._update_toolbar_states` — spina_app/navigation.py:390 — Updates update toolbar states for the navigation feature.

### Batch 18: Cash Control (259 lines)

Source file: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py`

Risk mix: `database_read`, `support`, `ui_only`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_cashctl__fmt_money` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:35755 — Handles spina cashctl fmt money for the cash control feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_cashctl_get_collection_totals` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:35799 — Return combined collection totals for one day. Combined Collected = Regular + 7x7 + any transaction without a clean loan_type. This intentionally uses the Data Bank transactions total, not only one payment mode.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_cashctl_get_average_collection` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:35856 — Average daily collection before the selected date. Uses the last N calendar days before the selected date, then averages only days that actually have collections. This is better for forecasting collection days than dividing by every calendar day, especially when there are no-collection days.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_cashctl__ceil_thousand_units` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:35917 — Handles spina cashctl ceil thousand units for the cash control feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_cashctl_build_tab` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:36153 — Handles spina cashctl build tab for the cash control feature.

### Batch 19: Loans (235 lines)

Source file: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py`

Risk mix: `database_read`, `support`, `ui_only`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.__init__` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3932 — Handles init for the loans feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._set_last_error` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3965 — Updates set last error for the loans feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.get_last_error` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3971 — Retrieves get last error for the loans feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.set_default_loan_type` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3983 — Set the default loan_type context used when caller does not pass loan_type.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._effective_lt` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3990 — Handles effective lt for the loans feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.get_audit_new_loan_rows` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6379 — Return append-only ADD audit rows for new loans.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._dayclose_norm_workflow` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6505 — Handles dayclose norm workflow for the loans feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._dayclose_variance_status` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6517 — Handles dayclose variance status for the loans feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.get_all_areas` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7039 — Return area master list for UI dropdowns. Hides areas that are used only by archived clients, but keeps: - areas with at least one active client - areas with no clients yet (manually-added / still-unused)
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.add_area` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7089 — Add a new area. Returns True if inserted or already exists.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.RenewDialog.__init__` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:29341 — Handles init for the loans feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.RenewDialog._valid_ymd` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:29365 — Handles valid ymd for the loans feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.RenewDialog._set_manual_rc` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:29635 — Updates set manual rc for the loans feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.RenewDialog._set_auto_rc` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:29643 — Updates set auto rc for the loans feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.RenewDialog._recompute` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:29652 — Handles recompute for the loans feature.

### Batch 20: Database (232 lines)

Source file: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py`

Risk mix: `database_read`, `support`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_storage_enabled` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:142 — Handles spina pg storage enabled for the database feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_storage_conn` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:149 — Handles spina pg storage conn for the database feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_app_dir` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:183 — Handles spina pg app dir for the database feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_json_table_for_path` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:201 — Handles spina pg json table for path for the database feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_read_json` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:211 — Handles spina pg read json for the database feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_sha256` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:273 — Handles spina pg sha256 for the database feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_guess_file_type` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:278 — Handles spina pg guess file type for the database feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_normalize_value` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:544 — Convert PostgreSQL-returned values into SQLite-like values.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_replace_qmarks` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:576 — Replace SQLite ? parameters with psycopg %s outside quoted strings.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_escape_literal_percents` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:603 — Escape literal percent signs for psycopg while preserving %s/%b/%t placeholders. Old SQLite queries commonly contain LIKE '%ADV%' or LIKE '%[RC:%'. Psycopg uses %s-style placeholders, so a literal % in the SQL text must be doubled as %%. Without this, ADV/reason queries can fail silently inside the 
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_sql` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:632 — Translate common SQLite SQL into PostgreSQL-compatible SQL.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_table_name_from_pragma` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:693 — Handles spina pg table name from pragma for the database feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._PgCompatCursor.__init__` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:699 — Handles init for the database feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._PgCompatCursor.connection` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:708 — Handles connection for the database feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._PgCompatCursor._set_rows` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:711 — Updates set rows for the database feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._PgCompatCursor.fetchone` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:802 — Handles fetchone for the database feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._PgCompatCursor.fetchall` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:815 — Handles fetchall for the database feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._PgCompatCursor.fetchmany` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:824 — Handles fetchmany for the database feature.

### Batch 21: Clients (211 lines)

Source file: `spina_app/linked_client_queries.py`

Risk mix: `database_read`, `support`

- `spina_app.linked_client_queries.configure_linked_client_query_dependencies` — spina_app/linked_client_queries.py:27 — Bind application-owned globals required by the extracted LoanDB methods.
- `spina_app.linked_client_queries.get_linked_client_uids` — spina_app/linked_client_queries.py:47 — Return all client_uids linked to the same person_uid (includes self). If not linked, returns [client_uid].
- `spina_app.linked_client_queries.get_transaction_history_for_client_uids` — spina_app/linked_client_queries.py:83 — Return databank audit rows (most recent first) for a list of client_uids.
- `spina_app.linked_client_queries.get_transactions_for_client_uids` — spina_app/linked_client_queries.py:114 — Return transactions for a linked person (both Regular + 7x7), using client_uid when available. Includes best-effort fallback to legacy rows where client_uid is blank but (name, loan_type) matches.
- `spina_app.linked_client_queries.count_clients_in_area` — spina_app/linked_client_queries.py:175 — Count ACTIVE clients in an area. Archived-only areas should not keep showing up as 'in use' in the UI.
- `spina_app.linked_client_queries.get_client_by_person_uid_and_loan_type` — spina_app/linked_client_queries.py:202 — Return a single client row matching (person_uid, loan_type), or None.
- `spina_app.linked_client_queries.get_transactions_for_client` — spina_app/linked_client_queries.py:218 — Retrieves get transactions for client for the clients feature.

### Batch 22: Data Bank (205 lines)

Source file: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py`

Risk mix: `ui_only`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_perf_refresh_data_grid` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:34608 — Fast Data Bank month grid refresh using bulk month transaction query.

### Batch 23: Data Bank (204 lines)

Source file: `spina_app/tabs/data_bank_shell.py`

Risk mix: `support`, `ui_only`

- `spina_app.tabs.data_bank_shell._noop_log` — spina_app/tabs/data_bank_shell.py:6 — Handles noop log for the data bank feature.
- `spina_app.tabs.data_bank_shell.configure_data_bank_shell_dependencies` — spina_app/tabs/data_bank_shell.py:14 — Bind application-owned logging helpers used by Data Bank presentation code.
- `spina_app.tabs.data_bank_shell._looks_like_data_grid` — spina_app/tabs/data_bank_shell.py:21 — Heuristic: columns contain 'client' + 'area' and many day columns (d1..d31 or numeric headings).
- `spina_app.tabs.data_bank_shell._locate_data_tree` — spina_app/tabs/data_bank_shell.py:58 — Find and memoize the actual Treeview used by the Data grid.
- `spina_app.tabs.data_bank_shell._ensure_databank_edit_bindings` — spina_app/tabs/data_bank_shell.py:86 — Bind double-click/F2 editing for Data grid (auto-detected) only once per Treeview instance.
- `spina_app.tabs.data_bank_shell._show_audit_tab` — spina_app/tabs/data_bank_shell.py:119 — Handles show audit tab for the data bank feature.
- `spina_app.tabs.data_bank_shell._hide_audit_tab` — spina_app/tabs/data_bank_shell.py:130 — Handles hide audit tab for the data bank feature.
- `spina_app.tabs.data_bank_shell._resize_databank_columns` — spina_app/tabs/data_bank_shell.py:138 — Resize Data Bank columns responsively. Supports 'freeze panes' layout: - name_tree shows Client + Area (fixed, no horizontal scroll) - days_tree shows day columns with horizontal scroll

### Batch 24: Clients (169 lines)

Source file: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py`

Risk mix: `support`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app_unlink_selected_client` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:29088 — Handles app unlink selected client for the clients feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app__maybe_suggest_link_clients` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:29111 — Handles app maybe suggest link clients for the clients feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app_export_clients_template` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:29174 — Handles app export clients template for the clients feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina__client_pictures_dir` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:34111 — Handles spina client pictures dir for the clients feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app_set_selected_client_picture` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:34363 — Handles app set selected client picture for the clients feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app_clear_selected_client_picture` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:34389 — Handles app clear selected client picture for the clients feature.

### Batch 25: Dashboard (158 lines)

Source file: `spina_app/tabs/dashboard.py`

Risk mix: `support`, `ui_only`

- `spina_app.tabs.dashboard._spina_v18_patch_dashboard_chart_cards` — spina_app/tabs/dashboard.py:912 — Make chart cards consistent: light outer panel, dark readable chart area.
- `spina_app.tabs.dashboard._spina_v18_populate_dashboard_tree` — spina_app/tabs/dashboard.py:934 — Handles spina v18 populate dashboard tree for the dashboard feature.
- `spina_app.tabs.dashboard._spina_v18_refresh_dashboard` — spina_app/tabs/dashboard.py:953 — Handles spina v18 refresh dashboard for the dashboard feature.
- `spina_app.tabs.dashboard._spina_v19_populate_dashboard_tree` — spina_app/tabs/dashboard.py:973 — Handles spina v19 populate dashboard tree for the dashboard feature.
- `spina_app.tabs.dashboard._spina_v19_refresh_dashboard` — spina_app/tabs/dashboard.py:993 — Handles spina v19 refresh dashboard for the dashboard feature.
- `spina_app.tabs.dashboard._spina_v20_populate_dashboard_tree` — spina_app/tabs/dashboard.py:1021 — Handles spina v20 populate dashboard tree for the dashboard feature.
- `spina_app.tabs.dashboard._spina_v20_refresh_dashboard` — spina_app/tabs/dashboard.py:1057 — Handles spina v20 refresh dashboard for the dashboard feature.

## Duplicate application symbol names

- `__getattr__`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:843`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3845`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3924`
- `__init__`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:558`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:699`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:848`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1602`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1733`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:2961`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3770`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3850`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3932`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:13493`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:25093`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:29341`
- `__iter__`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:569`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:840`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3841`
- `_arrange_areas_dialog`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:20702`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:30516`
- `_build_ui`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1635`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1780`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3172`
- `_cancel`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8555`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8859`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8953`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:20680`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:20759`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:24528`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:30494`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:30573`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:42148`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:42590`
- `_clear`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1719`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1916`
- `_clear_collectors_search_filters`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:19891`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:30150`
- `_close`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1723`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1921`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3578`
- `_close_editor`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:16223`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:16295`
- `_collectors_areas_drag_motion`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:19830`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:34000`
- `_delete_selected_collector`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:12234`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:33950`
- `_display_loan_type_label`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:16674`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:26282`
- `_draw_final_footer`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:21821`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:31711`
- `_draw_global_header`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:21837`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:31727`
- `_draw_page_number`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:21813`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:31703`
- `_edit_selected_collector`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:12439`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:33983`
- `_fetch_clients_for`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:20603`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:30417`
- `_fits`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:21789`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:31679`
- `_fmt_amt`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:9438`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:10781`
- `_gv`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:25972`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:26321`
- `_is_date`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3691`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:18053`
- `_log_exc`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1269`, `spina_app/tabs/dashboard.py:59`
- `_move`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:20735`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:30549`
- `_next_month`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1707`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1902`
- `_noop_log`: `spina_app/navigation.py:11`, `spina_app/tabs/data_bank_shell.py:6`
- `_norm`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:11075`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:17349`
- `_norm_area`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:9629`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:11623`
- `_norm_dom`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5060`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5262`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:40630`
- `_norm_lt`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3977`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:23671`
- `_norm_term`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5016`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5208`
- `_norm_weekday`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5046`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5248`
- `_now_text`: `spina_app/area_hierarchy.py:25`, `spina_app/area_hierarchy_ops.py:25`
- `_ok`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8825`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8941`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:20677`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:20757`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:24527`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:30491`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:30571`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:42550`
- `_on_collectors_multi_toggle`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:19475`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:33789`
- `_on_collectors_select`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:19918`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:36574`
- `_on_collectors_tree_click`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:19501`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:33847`
- `_on_collectors_tree_wheel`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:19855`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:33610`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:33811`
- `_on_enter`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8568`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8870`
- `_on_search`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:11517`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:19390`
- `_options_dialog`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:20638`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:30452`
- `_pick`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1693`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1861`
- `_populate_collector_details`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:19976`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:36477`
- `_prev_month`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1700`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1894`
- `_refresh`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:17851`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:18839`
- `_render`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1672`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1822`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:17822`
- `_s`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:20633`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:30447`
- `_safe_json`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6249`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6309`
- `_save`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8525`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:15742`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:42118`
- `_save_collector_notes`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:20107`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:33632`
- `_save_selected_collector_notes`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:20077`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:33696`
- `_schedule_collectors_refresh`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:19872`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:30130`
- `_spina__client_due_meta`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:22949`, `spina_app/tabs/clients.py:797`
- `_spina_dashboard_fetch_rows`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:35389`, `spina_app/tabs/dashboard.py:53`
- `_spina_route_adv_marker_for`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7984`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:38718`
- `_spina_v18_draw_dashboard_charts`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:39593`, `spina_app/tabs/dashboard.py:64`
- `_spina_v20_draw_dashboard_charts`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:39788`, `spina_app/tabs/dashboard.py:70`
- `_sync_selection`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:15968`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:34671`
- `_table_cols`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:4022`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:35411`
- `_today`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1714`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1910`
- `_validate_date`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:27947`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:40623`
- `_wrap_text_to_width`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:21784`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:31674`
- `_yview`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:15943`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:34656`
- `accept`: `spina_app/area_hierarchy_ui.py:245`, `spina_app/area_hierarchy_ui.py:439`
- `add_area`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7089`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:18876`
- `cancel`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:23484`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:28060`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:40733`
- `close`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:834`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:879`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3834`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3917`, `spina_app/area_hierarchy_ui.py:259`, `spina_app/area_hierarchy_ui.py:431`, `spina_app/area_hierarchy_ui.py:707`
- `commit`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:873`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3907`
- `cursor`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:862`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3854`
- `delete_area`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7141`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:18909`
- `do_link`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:23438`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:29033`
- `ensure_space`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:21937`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:31827`
- `execute`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:716`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:865`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3774`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3859`
- `executemany`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:786`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:869`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3798`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3883`
- `export_range_template`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:24484`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:25279`
- `fetchall`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:815`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3826`
- `fetchmany`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:824`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3830`
- `fetchone`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:802`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3822`
- `fmt_currency`: `spina_app/navigation.py:18`, `spina_app/utilities/formatting.py:5`
- `load_list`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:29982`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:34996`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:35260`
- `new_page_headers`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:21901`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:31791`
- `on_cancel`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:11008`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:11498`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:12414`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:25366`
- `on_ok`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:10982`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:11485`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:12393`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:25350`
- `print_collector_route_daily_ledger`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:20346`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:30179`
- `print_full_daily_ledger`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:20558`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:30380`
- `push`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:25089`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:25096`
- `rename_area`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7095`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:18888`
- `restore_selected`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:30002`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:35024`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:35290`
- `rollback`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:876`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3913`
- `save`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:16181`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:16255`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:27954`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:40644`
- `walk`: `spina_app/area_hierarchy_ops.py:205`, `spina_app/area_hierarchy_ui.py:79`, `spina_app/area_hierarchy_ui.py:93`, `spina_app/area_hierarchy_ui.py:105`

## Static-analysis limitations

- Dynamic imports and runtime-generated attribute names may not resolve.
- Callback and monkey-patch detection is static and may include false positives.
- SQL assembled from runtime fragments may not reveal every table.
- Possible orphan symbols may still be called by reflection, Tkinter, plugins, or external code.
- Risk labels are conservative planning hints, not proof of runtime behavior.
- Desktop smoke testing remains required before merging modularization changes.
