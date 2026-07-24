# SPINA Risk and Modularization Map

Generated from commit `f15b4145a9a262b3e1f61cab271db2ebc75091bf`.

Scanned **131 Python files**, **70,799 lines**, and **2,147 symbols**.

> This is a static architecture map. Runtime callbacks and dynamic monkey patches can still require desktop testing.

## Risk groups

### Authentication

**98 symbols · 32,804 lines**

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8817 — Represents App for the authentication feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3931 — Represents LoanDB for the payments feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.print_full_daily_ledger` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:31444 — Print a 3-column DAILY COLLECTION LEDGER with a small UI to change: - Ledger Date - Paper size and orientation - Areas order (arrange ALL areas)
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:20982 — Populate the right-side details panel for the selected collector.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select.print_full_daily_ledger` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:21622 — Print a 3-column DAILY COLLECTION LEDGER with a small UI to change: - Ledger Date - Paper size and orientation - Areas order (arrange ALL areas)
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:24347 — Auto-suggest linking when a matching client exists in the other loan type. - YES links both rows (same person_uid). - NO sets link_opt_out=1 for BOTH rows so you won't be asked again from either side, unless you manually link later.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.generate_client_pdf` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:27327 — Override: Client SOA PDF that expands ADV ranges to daily 'Adv' markers in the Payment column, and prints other reasons as text in Payment. Never prints long notes in the Date column. Layout: 3 columns per page, 11 rows per column.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_databank_close_dialog` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:10607 — Handles open databank close dialog for the authentication feature. Main detected dependency: _apply_mode.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v32_prompt_login` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:44493 — Modern account-based login dialog. Returns (username, internal_access_profile).
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_backup_history_window` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:15672 — Show backup files and provide verify/restore-test actions.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_route_adv_marker_for` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:40627 — Collector Route ADV lookup with stronger PostgreSQL migration fallback. This version does not rely only on the printed route name. It finds the client_uid/person_uid from clients first, then checks every matching transaction name/uid for the selected loan type. This fixes migrated data where a linke
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._build_header` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:16258 — Modern top header: app identity + fast Regular/7x7 switch + app actions.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.__init__` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:14199 — Handles init for the authentication feature. Main detected dependency: LoanDB.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_delete_day_dialog` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:13702 — Delete all Data Bank entries for one selected date, with backup + password confirmation.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.apply_role_access` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:9633 — Apply role-based UI restrictions.
- `tools.cleanup_pure_login_dialog_ui_pass_only.build_report` — tools/cleanup_pure_login_dialog_ui_pass_only.py:173 — Builds build report for the authentication feature. Main detected dependency: abs.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._prompt_login` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:9346 — Login dialog: returns (username, role) or (None, None) if cancelled.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._force_change_password_dialog` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:9051 — Modal dialog that forces a password change. Returns True if changed.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.add_or_update_transaction_by_uid` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8199 — Insert or update a transaction using client_uid as the stable key. Key: (client_uid, loan_type, date) - Automatically pulls the current client name from clients table. - Updates the stored `name` in transactions if the client was renamed. - Writes append-only audit rows into transaction_history.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._rebuild_side_nav` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:15905 — Rebuild the modern left-side navigation from the currently visible notebook tabs.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.add_or_update_transaction` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7743 — Insert or update a transaction (Data Bank) row. Key: prefer (client_uid, loan_type, date); fallback to legacy (name, loan_type, date) - Populates `client_uid` when possible so linked profiles can see the same Data Bank rows. - Writes an append-only audit row into `transaction_history`.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._edit_selected_collector` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:13038 — Handles edit selected collector for the collectors feature. Main detected dependency: IOError.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._create_postgres_backup_file` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:15354 — Create a full PostgreSQL backup using pg_dump custom format. The backup includes clients, payments, JSON rows, PDFs, and pictures because those are now stored in spina_db. Password is passed through PGPASSWORD, not printed on screen.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._prompt_user_role` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:9474 — Simple role selector shown at startup.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select._edit_collector_dialog` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:21271 — Legacy dialog-based edit; now edits the main collectors.json dict schema.
- `tools.plan_module_separation.build_report` — tools/plan_module_separation.py:211 — Builds build report for the authentication feature. Main detected dependency: Counter.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._load_users_db` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:9194 — Load users database from data/users.json. If missing, create defaults. Default accounts (created only if missing): - admin / admin123 -> Admin - encoder / encoder123 -> Encoder - viewer / viewer123 -> Viewer - system / system123 -> System
- `tools.test_login_palette_wave_25.main` — tools/test_login_palette_wave_25.py:23 — Handles main for the authentication feature. Main detected dependency: Dummy.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.backup_postgres_database` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:15439 — UI handler for the Backup button.
- `tools.plan_pure_login_dialog_ui_pass_only.HandlerVisitor` — tools/plan_pure_login_dialog_ui_pass_only.py:71 — Represents HandlerVisitor for the authentication feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._delete_selected_collector` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:12833 — Removes delete selected collector for the collectors feature. Main detected dependency: IOError.
- `tools.plan_login_dialog_pass_only.PassOnlyVisitor` — tools/plan_login_dialog_pass_only.py:130 — Represents PassOnlyVisitor for the authentication feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select._delete_collector` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:21348 — Legacy delete; now deletes from the main collectors.json dict schema.
- `tools.audit_dynamic_sql_context.audit` — tools/audit_dynamic_sql_context.py:148 — Handles audit for the utilities feature. Main detected dependency: ast.parse.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_databank_close_dialog._close_day` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:11084 — Handles close day for the authentication feature. Main detected dependency: _default_workflow.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v32_switch_account` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:44745 — Handles spina v32 switch account for the authentication feature. Main detected dependency: _log_exc.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.delete_transaction` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7846 — Removes delete transaction for the authentication feature. Main detected dependency: ValueError.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v32_make_users_account_based` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:44436 — Add account display metadata while preserving existing usernames/passwords/access.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._add_collector` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:13131 — Handles add collector for the authentication feature. Main detected dependency: IOError.
- `tools.plan_pure_login_dialog_ui_pass_only.build_report` — tools/plan_pure_login_dialog_ui_pass_only.py:172 — Builds build report for the authentication feature. Main detected dependency: HandlerVisitor.
- …and 58 more.

### Backup

**33 symbols · 848 lines**

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app_refresh_client_picture_panel` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:35365 — Handles app refresh client picture panel for the clients feature. Main detected dependency: Image.open.
- `tools.cleanup_neutral_appclass_init_patch._find_neutral_block` — tools/cleanup_neutral_appclass_init_patch.py:49 — Retrieves find neutral block for the backup feature. Main detected dependency: DEF_RE.match.
- `tools.audit_pg_backup_action_flow.Visitor` — tools/audit_pg_backup_action_flow.py:93 — Represents Visitor for the backup feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._load_client_notes._safe_load_one` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:2517 — Handles safe load one for the backup feature. Main detected dependency: Exception.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_fixed_open_archived_clients_dialog.restore_selected` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:36421 — Handles restore selected for the clients feature. Main detected dependency: len.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._find_postgres_exe` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:15304 — Find pg_dump.exe / pg_restore.exe without requiring PostgreSQL bin in PATH.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._restore_backup_to_test_database` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:15635 — Restore selected backup into spina_restore_test only; never overwrites live spina_db.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_fixed_open_archived_clients_dialog_rowid.restore_selected` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:36687 — Handles restore selected for the clients feature. Main detected dependency: _rowid_from_iid.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._verify_postgres_backup_file` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:15571 — Verify a PostgreSQL custom backup by reading its table of contents.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.print_full_daily_ledger._draw_closed_route_payment_summary_page._draw_summary_row` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:34563 — Handles draw summary row for the dashboard feature. Main detected dependency: _area_txt.rstrip.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app_clear_selected_client_picture` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:35478 — Handles app clear selected client picture for the clients feature. Main detected dependency: _app__selected_client_name_and_lt.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app_open_archived_clients_dialog.restore_selected` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:31066 — Handles restore selected for the clients feature. Main detected dependency: _log_suppressed_once.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._list_postgres_backup_files` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:15547 — Return backup files from the app backups folder, newest first.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.generate_client_pdf._draw_also_footer` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:27957 — Draw small footer note (subtle) on the current page.
- `tools.audit_pg_backup_action_flow.Visitor._visit_function` — tools/audit_pg_backup_action_flow.py:111 — Handles visit function for the backup feature. Main detected dependency: any.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._restore_main_tabs` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:9574 — Handles restore main tabs for the clients feature. Main detected dependency: _log_suppressed_once.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina__resolve_app_path` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:35187 — Handles spina resolve app path for the clients feature. Main detected dependency: _spina_pg_restore_client_picture_to_cache.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.backup_postgres_database._success` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:15463 — Handles success for the payments feature. Main detected dependency: _open_path.
- `tools.inject_silent_ui_logging.print_report` — tools/inject_silent_ui_logging.py:333 — Generates print report for the dashboard feature. Main detected dependency: item.get.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_save_closed_collector_route_copy._draw_table_header` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:39921 — Handles draw table header for the clients feature. Main detected dependency: _colors.HexColor.
- `spina_app.area_hierarchy_ui.open_area_manager.close` — spina_app/area_hierarchy_ui.py:707 — Handles close for the payments feature. Main detected dependency: _refresh_app_area_views.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.backup_postgres_database._error` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:15481 — Handles error for the payments feature. Main detected dependency: _log_exc.
- `tools.cleanup_neutral_appclass_init_patch.print_report` — tools/cleanup_neutral_appclass_init_patch.py:164 — Generates print report for the reports feature. Main detected dependency: candidate.get.
- `tools.audit_patch_chains._classify_rhs` — tools/audit_patch_chains.py:77 — Handles classify rhs for the backup feature. Main detected dependency: _lower.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_archive_row_to_dict` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:36231 — Handles spina archive row to dict for the backup feature. Main detected dependency: _row.keys.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._db_get_client_picture` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:35262 — Handles db get client picture for the clients feature. Main detected dependency: _spina__ensure_client_picture_column.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._postgres_backup_dir` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:15344 — Return/create the app backup folder.
- `spina_app.area_hierarchy_ui._restore_parent_grab` — spina_app/area_hierarchy_ui.py:44 — Return modal control to the form that opened the Area window.
- `tools.cleanup_neutral_appclass_init_patch.main` — tools/cleanup_neutral_appclass_init_patch.py:180 — Handles main for the reports feature. Main detected dependency: Path.
- `spina_app.area_hierarchy_ui.select_area_node.close` — spina_app/area_hierarchy_ui.py:259 — Handles close for the payments feature. Main detected dependency: _restore_parent_grab.
- `spina_app.area_hierarchy_ui._select_parent_area.close` — spina_app/area_hierarchy_ui.py:431 — Handles close for the payments feature. Main detected dependency: _restore_parent_grab.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._restore_backup_to_test_database._check_cancel` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:15657 — Handles check cancel for the payments feature. Main detected dependency: RuntimeError.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._PgCompatConnection.backup` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:882 — Handles backup for the backup feature.

### Database Read

**253 symbols · 5,109 lines**

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.export_range_template` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:26343 — Export an Excel template for payments over a chosen date range. Presets: This Month / This Year / Custom (YYYY-MM-DD).
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._setup_style` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:14779 — Centralized ttk styling. Goals: - cleaner spacing / typography - readable Treeviews - consistent Notebook tabs - best-effort HiDPI handling on Windows
- `tools.extract_pure_helper_batch.inspect` — tools/extract_pure_helper_batch.py:81 — Handles inspect for the utilities feature. Main detected dependency: Path.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.parse_advance_ranges` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3649 — Parse one or more ADV date ranges from a transaction description. Supported tags (whitespace/case-tolerant): - [ADV:YYYY-MM-DD..YYYY-MM-DD] (single range) - [ADV:YYYY-MM-DD,YYYY-MM-DD,YYYY-MM-DD] (explicit days) - [ADV:range;range;...] where range is either: * YYYY-MM-DD..YYYY-MM-DD * YYYY-MM-DD (si
- `tools.cleanup_logger_fallback_pass_only._locate_target` — tools/cleanup_logger_fallback_pass_only.py:57 — Handles locate target for the payments feature. Main detected dependency: _find_top_level_function.
- `spina_app.area_hierarchy_ops._planned_subtree` — spina_app/area_hierarchy_ops.py:158 — Handles planned subtree for the utilities feature. Main detected dependency: ValueError.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._parse_reason_color_token_meta` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:26758 — Extract [RC:...] token plus optional window meta from the description. Supported token payloads (inside the brackets): - '#RRGGBB' - 'red' / 'green' / etc - '#RRGGBB;D:3' -> days=3 (inclusive, starting from the reason's date) - '#RRGGBB;UNTIL:YYYY-MM-DD' -> until (inclusive) - 'red;D:3' / 'red;UNTIL
- `tools.extract_display_formatters.build_plan` — tools/extract_display_formatters.py:133 — Builds build plan for the utilities feature. Main detected dependency: RuntimeError.
- `tools.extract_date_display_helpers.build_plan` — tools/extract_date_display_helpers.py:141 — Builds build plan for the utilities feature. Main detected dependency: RuntimeError.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:38243 — Populate the right-side details panel for the selected collector.
- `tools.plan_modern_ui_pass_only_cleanup.PassOnlyVisitor` — tools/plan_modern_ui_pass_only_cleanup.py:99 — Represents PassOnlyVisitor for the payments feature.
- `tools.plan_queue_empty_pass_only.PassOnlyVisitor` — tools/plan_queue_empty_pass_only.py:79 — Represents PassOnlyVisitor for the payments feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app_install_clients_picture_ui` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:35506 — Handles app install clients picture ui for the clients feature. Main detected dependency: box.pack.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.export_monthly_template` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:24659 — Export an Excel template for the current visible month (view-only data entry). Columns: Client Name + one column per date (YYYY-MM-DD). Users will fill payments in Excel and use 'Import from Excel' to load into the app.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._area_picker_dialog.add_new_area` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:11977 — Handles add new area for the authentication feature. Main detected dependency: _add_to_right.
- `tools.extract_numeric_parsers.build_plan` — tools/extract_numeric_parsers.py:143 — Builds build plan for the utilities feature. Main detected dependency: RuntimeError.
- `tools.plan_app_lifecycle_window_pass_only.PassOnlyVisitor` — tools/plan_app_lifecycle_window_pass_only.py:106 — Represents PassOnlyVisitor for the payments feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.get_client_note` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:2670 — Fetch a note for a client. scope: - 'shared' (default): shared notes (prefer person_uid/client_uid; legacy name fallback) - 'type': loan-type specific notes (prefer person_uid+loan_type or client_uid; legacy fallback) - 'effective': prefer type-specific if present, otherwise shared
- `tools.plan_logger_fallback_pass_only.PassOnlyVisitor` — tools/plan_logger_fallback_pass_only.py:84 — Represents PassOnlyVisitor for the payments feature.
- `tools.extract_cilog_diff_pairs.apply_extraction` — tools/extract_cilog_diff_pairs.py:138 — Handles apply extraction for the dashboard feature. Main detected dependency: APP_PATH.read_text.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._theme_palette` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:14994 — Handles theme palette for the settings feature. Main detected dependency: getattr.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_route_notice_for_client` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:39167 — Handles spina route notice for client for the clients feature. Main detected dependency: _spina_route_notice_key.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.pick_date_range` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1929 — Handles pick date range for the authentication feature. Main detected dependency: _CalendarRangePopup.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.NoteEditorDialog._collect_items` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3260 — Handles collect items for the clients feature. Main detected dependency: _load_client_notes.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._patch_messagebox_threadsafe` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:14461 — Make tkinter.messagebox safe to call from worker threads.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._collectors_name_from_values` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:20476 — Return the collector name from a Treeview row values tuple. Backwards compatible with older layouts: - Old layout: first value is the collector name. - New layout: first value is a select marker (radio/checkbox/bullet), second is the collector name.
- `spina_app.area_hierarchy_ui.build_area_selector_field` — spina_app/area_hierarchy_ui.py:335 — Build the modern client form's labeled, read-only Area selector.
- `tools.extract_fmt_currency_module.build_plan` — tools/extract_fmt_currency_module.py:112 — Builds build plan for the utilities feature. Main detected dependency: RuntimeError.
- `tools.plan_module_separation._record_definition` — tools/plan_module_separation.py:167 — Handles record definition for the other feature. Main detected dependency: _called_names.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._start_ui_queue_pump` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:14355 — Process UI-call requests from worker threads. This keeps Tk operations on the main thread. Any unexpected errors in the pump are logged (instead of silently swallowed) to avoid "stuck UI" mysteries.
- `tools.extract_log_serialization_helper.build_plan` — tools/extract_log_serialization_helper.py:62 — Builds build plan for the utilities feature. Main detected dependency: RuntimeError.
- `tools.test_cash_control_ui_controls_batch_09.capture_batch` — tools/test_cash_control_ui_controls_batch_09.py:216 — Handles capture batch for the dashboard feature. Main detected dependency: RuntimeError.
- `tools.test_display_ui_helper_batch_04.capture_batch` — tools/test_display_ui_helper_batch_04.py:178 — Handles capture batch for the utilities feature. Main detected dependency: RuntimeError.
- `tools.extract_date_helpers_module._required_import_nodes` — tools/extract_date_helpers_module.py:110 — Handles required import nodes for the utilities feature. Main detected dependency: RuntimeError.
- `tools.extract_text_normalizers._required_import_nodes` — tools/extract_text_normalizers.py:105 — Handles required import nodes for the utilities feature. Main detected dependency: RuntimeError.
- `tools.test_client_route_tree_style_batch_12.capture_batch` — tools/test_client_route_tree_style_batch_12.py:166 — Handles capture batch for the clients feature. Main detected dependency: RuntimeError.
- `tools.apply_hierarchical_area_ui_phase2.inspect` — tools/apply_hierarchical_area_ui_phase2.py:33 — Handles inspect for the other feature. Main detected dependency: RuntimeError.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_tree_wheel` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:34875 — Mouse wheel scroll for Collector Route list (Treeview).
- `spina_app.area_hierarchy.build_area_tree` — spina_app/area_hierarchy.py:267 — Build a nested tree from a flat list without imposing a depth limit.
- `tools.plan_queue_empty_pass_only.PassOnlyVisitor.visit_ExceptHandler` — tools/plan_queue_empty_pass_only.py:104 — Handles visit ExceptHandler for the payments feature. Main detected dependency: _contains_protected_word.
- …and 213 more.

### Database Write

**312 symbols · 16,043 lines**

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._area_picker_dialog` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:11630 — Route area picker (Main/Sub Tree + ordered selection). What you get: - Left: Tree of Main Areas with Sub Areas underneath - Right: Selected Route (ordered) as MAIN or MAIN - SUB entries - MAIN entry covers all its Sub Areas when printing/validating routes.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.attach_direct_integration` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:25673 — Minimal integration after removing undo/redo/backups. - Ensures a DB is attached - Wraps Excel import with a safe error dialog (if present) - Triggers initial UI refreshes (if methods exist)
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._import_from_excel_entry_worker` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:18398 — Worker for _import_from_excel_entry (runs off the Tk main thread).
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._build_collectors_tab` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:20126 — Collector's Route UI (organized + obvious selection + inline edit). Adds: - Obvious selection column (radio in single-select, checkbox in multi-select) - Per-row Actions column (View / Edit / Delete) - Multi-select bulk bar (Delete / Export / Clear) - Inline edit in the right-side panel (name + area
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v25_build_collectors_tab` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:43087 — Handles spina v25 build collectors tab for the clients feature. Main detected dependency: _log_exc.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._show_import_log_window` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:18796 — Organized import log viewer (tabs + search + save/copy). Tabs: - All (chronological) - Inserted / Updated - Skipped Duplicates / Skipped Unknown / Skipped - Errors - Header/Info / Other
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v27_build_collectors_tab` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:43561 — Handles spina v27 build collectors tab for the clients feature. Main detected dependency: _log_exc.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_settings_dialog` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:16487 — App settings (local-only).
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._run_long_task` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:14506 — Run work_fn() in a background thread with a simple modal 'Please wait' dialog. Improvements: - Optional Cancel button (signals a cancel_event to work_fn if it supports it) - Optional timeout (prevents UI from hanging forever on stuck tasks) - Cleanup is guarded so it can't run twice
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.refresh_data_grid` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:16994 — Refreshes refresh data grid for the clients feature. Main detected dependency: _log_ignored.
- `spina_app.area_hierarchy_ui.open_area_manager` — spina_app/area_hierarchy_ui.py:459 — Open the folder-style unlimited hierarchical Area manager.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._CalendarRangePopup` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1732 — Represents CalendarRangePopup for the payments feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_save_closed_collector_route_copy_same_format` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:40153 — Save final closed Collector Route copy using the SAME Collector Route PDF layout. Difference from normal print: the payment columns are filled with the actual amount paid on the closed date, and the PDF is saved silently under data/Closed_Collector_Routes.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_crc_fetch_close_rows` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:39539 — Build route rows with amount paid on the close date.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._import_from_excel_core` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:19555 — Auto-detect payments and reasons from Excel. Rules: " First row = headers. Must include 'Client Name' and at least one date column. " A date column can be an Excel date/datetime or a string 'YYYY-MM-DD'. " If a cell under a date column is numeric (or numeric-looking text): that's the amount. " If a 
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_areas_manager` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:19909 — Open the Areas manager window (create/rename/delete areas).
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._load_client_notes` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:2476 — Load client notes safely (cached). - Primary: <APP_DIR>/data/client_notes.json - Fallback (legacy): <CWD>/data/client_notes.json - Shallow-merge (primary wins on conflicts) - Cached in-memory to avoid frequent disk reads. - Logs problems to data/spina_app.log and shows a one-time warning if unreadab
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._apply_ui_theme` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:15041 — Handles apply ui theme for the payments feature. Main detected dependency: _log_suppressed_once.
- `tools.spina_quality_audit.audit` — tools/spina_quality_audit.py:116 — Handles audit for the payments feature. Main detected dependency: Visitor.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.import_from_excel_with_reasons` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:26527 — Import the Excel 'range template' where columns are: Client Name | 2025-10-01 | 2025-10-01 Reason | 2025-10-02 | 2025-10-02 Reason | ... Saves both Amount and Reason for each date.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._PgCompatCursor` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:698 — Represents PgCompatCursor for the utilities feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._pick_missed_reason` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:11484 — Modal checkbox dialog to choose one or more missed-payment reasons, plus optional 'Other' note. If 'Advance' is selected, you can enter a date range. Returns a single string (joined reasons + optional [ADV:s..e] tag) or None if cancelled.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._begin_cell_edit` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:13289 — Create an Entry over the clicked (or remembered) day cell and save back to DB.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_record_report_generation` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:27182 — Increment and return the daily Generate Report counter. Stored in: - data/report_generation_counts.json (summary counts) - data/report_generation_logs.csv (Excel-friendly full log) - data/report_generation_logs.jsonl (append-only full log) Counts: - total: all reports generated today - per client+lo
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._collector_editor_dialog` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:12901 — Unified editor for Collector name + route areas + notes.
- `tools.test_hierarchical_area_ui_phase2.main` — tools/test_hierarchical_area_ui_phase2.py:49 — Handles main for the clients feature. Main detected dependency: AssertionError.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._CalendarPopup` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1601 — Represents CalendarPopup for the payments feature.
- `spina_app.area_hierarchy_ui.select_area_node` — spina_app/area_hierarchy_ui.py:163 — Open a modal folder browser and return the selected active Area node.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._is_client_new` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:9771 — Return True if client is NEW. Rules: - If 'new_until' is explicitly set in the DB: * If it's an empty string or unparsable -> treat as explicit OFF (return False). * If it's a valid date -> return (ledger_date <= new_until). No fallback. - Otherwise (no explicit 'new_until' value present): * If 'day
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.export_range_template` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:25548 — Export an Excel template for payments over a chosen date range. Presets: This Month / This Year / Custom (YYYY-MM-DD).
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app_link_selected_client` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:30029 — Handles app link selected client for the clients feature. Main detected dependency: _app__get_selected_client_name.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._collectors_save_inline_edit` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:20771 — Save inline edits to collectors.json (atomic), then refresh UI.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_tree_click` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:34911 — Handle click in Sel / Actions columns without breaking row selection.
- `tools.cleanup_stale_databank_generated_blocks.main` — tools/cleanup_stale_databank_generated_blocks.py:337 — Handles main for the data bank feature. Main detected dependency: APP_FILE.exists.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select._populate_collector_details` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:21040 — Update the right panel: selected name, stats, areas tree, notes.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._populate_collector_details` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:38146 — Update the right panel: selected name, stats, areas tree, notes.
- `spina_app.tabs.client_info_logs._spina_v24_cilog_draw_charts` — spina_app/tabs/client_info_logs.py:81 — Handles spina v24 cilog draw charts for the clients feature. Main detected dependency: _log_exc.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_tree_click` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:20565 — Handle clicks in Sel + Actions columns.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._sum_paid_per_day` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8658 — Sum payments per date in a way that matches the app's Data Bank behavior. - Data Bank updates are keyed by (name, loan_type, date) so normally there's only 1 row per date. - If legacy/duplicate rows exist, we treat the **last non-zero** payment as the effective payment. - We do NOT let later 0.00 "r
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.delete_selected_cell` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:13538 — Removes delete selected cell for the clients feature. Main detected dependency: _date.
- …and 272 more.

### Filesystem

**141 symbols · 2,997 lines**

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._import_from_excel_entry_worker._parse_sheet` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:18572 — Handles parse sheet for the clients feature. Main detected dependency: HEADER_A.items.
- `tools.cleanup_databank_export_callbacks.main` — tools/cleanup_databank_export_callbacks.py:154 — Handles main for the data bank feature. Main detected dependency: APP_FILE.exists.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.generate_pdf_selected._work` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:18064 — Handles work for the clients feature. Main detected dependency: _json.dumps.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_save_closed_collector_route_copy_same_format._generate_one` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:40194 — Generates generate one for the collectors feature. Main detected dependency: _dt.now.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._collectors_export_selected` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:20711 — Handles collectors export selected for the collectors feature. Main detected dependency: _log_exc.
- `tools.cleanup_logger_fallback_pass_only.build_report` — tools/cleanup_logger_fallback_pass_only.py:136 — Builds build report for the payments feature. Main detected dependency: RuntimeError.
- `tools.extract_pure_helper_batch.apply` — tools/extract_pure_helper_batch.py:200 — Handles apply for the reports feature. Main detected dependency: Path.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._open_path` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1192 — Safely open a generated file/folder. v29 fix: Python 3.14 on Windows can crash hard with os.startfile() in some Tk/PDF workflows. Use subprocess instead so PDF generation does not close the app.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.link_selected_client.do_link` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:24502 — Handles do link for the clients feature. Main detected dependency: _log_suppressed_once.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app_link_selected_client.do_link` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:30097 — Handles do link for the clients feature. Main detected dependency: _log_suppressed_once.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_crc_load_collectors` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:39434 — Load collector route definitions from data/collectors.json in any supported schema.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._safe_filename_component` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1352 — Return a filesystem-safe single path component (no dirs).
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._load_collectors_route_map` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:10186 — Loads load collectors route map for the collectors feature. Main detected dependency: cur_areas.append.
- `tools.test_base_theme_palette_batch_11.main` — tools/test_base_theme_palette_batch_11.py:151 — Handles main for the reports feature. Main detected dependency: RuntimeError.
- `tools.test_legacy_dashboard_palette_batch_14.main` — tools/test_legacy_dashboard_palette_batch_14.py:151 — Handles main for the dashboard feature. Main detected dependency: RuntimeError.
- `tools.test_theme_palette_helper_batch_05.main` — tools/test_theme_palette_helper_batch_05.py:152 — Handles main for the reports feature. Main detected dependency: RuntimeError.
- `tools.test_ui_card_constructor_batch_08.main` — tools/test_ui_card_constructor_batch_08.py:203 — Handles main for the reports feature. Main detected dependency: RuntimeError.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina__store_client_picture_file` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:35207 — Handles spina store client picture file for the clients feature. Main detected dependency: _spina__client_pictures_dir.
- `tools.test_client_route_tree_style_batch_12.main` — tools/test_client_route_tree_style_batch_12.py:204 — Handles main for the clients feature. Main detected dependency: RuntimeError.
- `tools.test_legacy_dashboard_controls_batch_15.main` — tools/test_legacy_dashboard_controls_batch_15.py:267 — Handles main for the dashboard feature. Main detected dependency: RuntimeError.
- `tools.test_cash_control_ui_controls_batch_09.main` — tools/test_cash_control_ui_controls_batch_09.py:259 — Handles main for the dashboard feature. Main detected dependency: RuntimeError.
- `tools.test_cilog_ui_controls_batch_10.main` — tools/test_cilog_ui_controls_batch_10.py:246 — Handles main for the clients feature. Main detected dependency: RuntimeError.
- `tools.test_display_data_helper_batch.main` — tools/test_display_data_helper_batch.py:196 — Handles main for the reports feature. Main detected dependency: RuntimeError.
- `tools.test_pure_helper_batch.main` — tools/test_pure_helper_batch.py:170 — Handles main for the reports feature. Main detected dependency: RuntimeError.
- `tools.test_ui_display_helper_batch.main` — tools/test_ui_display_helper_batch.py:248 — Handles main for the reports feature. Main detected dependency: RuntimeError.
- `tools.test_display_ui_helper_batch_04.main` — tools/test_display_ui_helper_batch_04.py:220 — Handles main for the reports feature. Main detected dependency: RuntimeError.
- `tools.test_payment_schedule_normalizer_batch_06.main` — tools/test_payment_schedule_normalizer_batch_06.py:159 — Handles main for the payments feature. Main detected dependency: RuntimeError.
- `tools.test_legacy_dashboard_card_batch_16.main` — tools/test_legacy_dashboard_card_batch_16.py:202 — Handles main for the dashboard feature. Main detected dependency: RuntimeError.
- `tools.test_collector_route_card_batch_13.main` — tools/test_collector_route_card_batch_13.py:183 — Handles main for the collectors feature. Main detected dependency: RuntimeError.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_crc_copy_existing_route_pdfs` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:39733 — Handles spina crc copy existing route pdfs for the clients feature. Main detected dependency: _glob.glob.
- `tools.test_ci_acceleration.main` — tools/test_ci_acceleration.py:20 — Handles main for the payments feature. Main detected dependency: WORKFLOWS.glob.
- `tools.test_cilog_action_label_extraction._original` — tools/test_cilog_action_label_extraction.py:92 — Handles original for the utilities feature. Main detected dependency: Path.
- `tools.test_date_display_helper_extraction._test_original_state` — tools/test_date_display_helper_extraction.py:148 — Handles test original state for the utilities feature. Main detected dependency: Path.
- `tools.test_date_helpers_extraction._test_original_state` — tools/test_date_helpers_extraction.py:142 — Handles test original state for the utilities feature. Main detected dependency: Path.
- `tools.test_text_normalizer_extraction._test_original_state` — tools/test_text_normalizer_extraction.py:133 — Handles test original state for the utilities feature. Main detected dependency: Path.
- `tools.test_cilog_value_formatter_extraction._test_original` — tools/test_cilog_value_formatter_extraction.py:120 — Handles test original for the utilities feature. Main detected dependency: Path.
- `tools.test_numeric_parser_extraction._test_original_state` — tools/test_numeric_parser_extraction.py:129 — Handles test original state for the utilities feature. Main detected dependency: Path.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v23_client_form._load_pic_preview` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:42476 — Loads load pic preview for the payments feature. Main detected dependency: Image.open.
- `tools.test_display_formatter_extraction._test_original` — tools/test_display_formatter_extraction.py:128 — Handles test original for the utilities feature. Main detected dependency: Path.
- `tools.extract_fmt_currency_module.main` — tools/extract_fmt_currency_module.py:177 — Handles main for the reports feature. Main detected dependency: Path.
- …and 101 more.

### Financial Calculation

**179 symbols · 18,680 lines**

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._create_tables` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:4016 — Builds create tables for the clients feature. Main detected dependency: _ensure_column.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app__client_form` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:28563 — Handles app client form for the clients feature. Main detected dependency: _anchor.strftime.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.NoteEditorDialog` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:2949 — Improved per-client notes editor. Features: - Dated and undated notes - Scope: Shared (both Regular/7x7) or This loan type - Left panel: list of existing notes (with search) - Autosave (debounced) + unsaved indicator - Safe switching between notes (prompts if needed) Notes storage is handled by get_
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.refresh_collectors` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:12142 — Refresh the Collector's Route table (enhanced). - Supports older collectors.json schemas (dict/list/strings) and normalizes to: {name: {areas: [...], notes: "..."}} - Computes: * unassigned areas (master areas not in any route) * unknown route areas (route areas not found in master areas) * conflict
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.RenewDialog` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:30393 — Renew (reloan) dialog. Auto-computes **Released Cash** using: released_cash = max(0, new_principal - remaining_due) remaining_due is based on the current cycle: Regular: remaining_due = max(0, total_to_pay - paid_total) 7x7: remaining_due = remaining_principal + unpaid_interest_arrears You can still
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app_open_client_history_dialog` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:29513 — Handles app open client history dialog for the clients feature. Main detected dependency: _app__get_selected_client_name.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v23_client_form` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:42368 — Handles spina v23 client form for the clients feature. Main detected dependency: Image.open.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._import_encoder_batch` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:19134 — Import One-Day Encoder exports (.jsonl or .csv) into the DB. - Dedupe by record_id (preferred) or a content hash fallback - Unknown clients are skipped (no auto-create) - Advances are stored via description tag: [ADV:s..e; s..e; ...] (supports multiple ranges)
- `spina_app.tabs.reports._spina_v22_build_reports_tab` — spina_app/tabs/reports.py:105 — Handles spina v22 build reports tab for the dashboard feature. Main detected dependency: _anchor.get.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v27_collector_editor_dialog` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:43890 — Modern route editor: Available Areas vs Assigned Route Order.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._build_reports_tab` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:17415 — Builds build reports tab for the reports feature. Main detected dependency: _anchor.get.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.import_clients_from_excel` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:24714 — Import ONLY client details from an Excel file into the Clients DB. Multi-loan-type safe: - If the sheet has a "Loan Type" column, it imports per-row (Regular / 7x7). - Otherwise, it imports into the CURRENT view mode (top selector).
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.update_client` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5133 — Update a client (append-only history is written to client_history).
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.get_all_clients` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5878 — Return client names (optionally filtered by loan_type) with optional search. search_by: - 'all' / 'both' : match across common client fields (default) - 'client' : match in client name only - 'area' : match in area only - 'principal' : match in principal (as text) - 'released' : match in date_releas
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_save_closed_collector_route_copy` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:39768 — Save an audit copy of the Collector Route after Daily Close. The PDF contains the closed total/actual cash for the day and the amount paid by each client on that date. It is separate from Generate Report and from editable Data Bank rows.
- `spina_app.tabs.cash_control._spina_v21_cash_build_tab` — spina_app/tabs/cash_control.py:37 — Handles spina v21 cash build tab for the dashboard feature. Main detected dependency: _log_exc.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.refresh_clients` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:24079 — Refresh the Clients tab table from the database, honoring the search box.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_dashboard_fetch_rows` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:36786 — Return active client completion rows using payments from latest released date only. Latest released date = max(clients.date_released, latest renewals.renew_date). Payment start = latest released date + clients.pay_start_offset_days (normalized to 0/1 day).
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.RenewDialog._compute_stats` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:30439 — Return dict with paid/remaining/suggested released cash (best-effort). Regular: remaining_due = max(0, total_to_pay - paid_total) 7x7: remaining_due = remaining_principal + unpaid_interest_arrears (arrears must be cleared first). Uses the same rule as the SOA: - Daily interest = ceil(remaining_princ
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.generate_pdf_selected` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:17888 — Generate a client statement PDF without freezing the UI.
- `spina_app.tabs.client_info_logs._spina_v24_build_client_info_logs_tab` — spina_app/tabs/client_info_logs.py:202 — Handles spina v24 build client info logs tab for the clients feature. Main detected dependency: _log_exc.
- `spina_app.tabs.dashboard._spina_v17_build_dashboard_tab` — spina_app/tabs/dashboard.py:80 — Handles spina v17 build dashboard tab for the dashboard feature. Main detected dependency: _log_exc.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.delete_transactions_for_day` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7903 — Delete ALL Data Bank transaction rows for one calendar date. Safety behavior: - Validates YYYY-MM-DD. - Creates a JSON backup in data/day_delete_backups BEFORE deleting. - Deletes both Regular and 7x7 transactions for that date. - Clears the Data Bank close/collector-close lock rows for that date so
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.print_databank_close_report` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:10371 — Generates print databank close report for the data bank feature. Main detected dependency: _cv.Canvas.
- `spina_app.tabs.clients._spina_v23_build_clients_tab` — spina_app/tabs/clients.py:155 — Handles spina v23 build clients tab for the dashboard feature. Main detected dependency: _anchors.get.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.renew_client` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5436 — Renew a client (reloan). Updates the client row to a new cycle and records an event. - released_cash: cash actually released to the client for this renew (for display in reports). - new_principal: the new loan principal. If None/blank, defaults to released_cash.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_renew_client_direct` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:40387 — PostgreSQL-safe renew/reloan implementation for the TEST build.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_databank_close_records_dialog` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:11259 — Handles open databank close records dialog for the data bank feature. Main detected dependency: ValueError.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select.print_collector_route_daily_ledger` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:21410 — Print the SELECTED collector's route using the same 3-column Daily Collection Ledger layout as `print_full_daily_ledger`, but ONLY for that collector's areas (no 'arrange all areas' step). - Uses selection() first (more reliable than focus()). - Reads collectors.json in multiple historical schemas. 
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_perf_refresh_data_grid` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:36005 — Fast Data Bank month grid refresh using bulk month transaction query.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.print_collector_route_daily_ledger` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:31243 — Print the SELECTED collector's route using the same 3-column Daily Collection Ledger layout as `print_full_daily_ledger`, but ONLY for that collector's areas (no 'arrange all areas' step). - Uses selection() first (more reliable than focus()). - Reads collectors.json in multiple historical schemas. 
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.print_full_daily_ledger._draw_closed_route_payment_summary_page` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:34444 — Append closed-route payment summaries on a separate page. This keeps the route pages in the normal collector format while still saving a complete area-by-area payment summary plus grand total.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_route_balance_like_generate_report` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:39217 — Return the same Balance basis used by Generate Report PDF. Regular: total_to_pay (corrected to principal + interest when needed) minus effective current-cycle payments. 7x7: remaining principal after the Generate Report interest-first payment split. This intentionally matches the report header Balan
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.add_client` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:4949 — Handles add client for the authentication feature. Main detected dependency: _log_suppressed_once.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v21_cash_refresh` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:42047 — Handles spina v21 cash refresh for the dashboard feature. Main detected dependency: _log_exc.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_perf_clients_rows` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:35673 — Bulk load rows for Clients tab in one/few queries, avoiding per-row get_client_info().
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._build_clients_tab` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:19722 — Builds build clients tab for the clients feature. Main detected dependency: _anchors.get.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app_refresh_clients` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:29216 — Handles app refresh clients for the clients feature. Main detected dependency: _app__norm_lt_value.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_fixed_open_archived_clients_dialog_rowid` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:36601 — Archived clients restore dialog that restores by clients.id first.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_fixed_open_archived_clients_dialog` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:36343 — Archived clients restore dialog with UID fallback and refresh after restore.
- …and 139 more.

### Network

**1 symbols · 6 lines**

- `tools.spina_startup_diagnostics.check_tcp` — tools/spina_startup_diagnostics.py:54 — Handles check tcp for the other feature. Main detected dependency: CheckResult.

### Reports

**87 symbols · 1,880 lines**

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._collect_day_flags_for_month` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:27027 — txns: iterable of dicts/rows having keys: 'date'|'d', 'payment'|'amt', 'description'|'desc' Returns dict: day(date)-> {'adv':bool, 'adv_paid_on':set(str), 'reason':str or None, 'paid':float} Reporting rules: - ADV is marked ONLY on the COVERED days (NOT on the payment date). - Covered days also stor
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._register_unicode_fonts` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:2219 — Try to register a Unicode TTF so ReportLab can encode non-ASCII safely. Falls back to built-ins if none found.
- `tools.inspect_stale_databank_protected_context.main` — tools/inspect_stale_databank_protected_context.py:36 — Handles main for the data bank feature. Main detected dependency: _load_cleanup_tool.
- `tools.plan_ui_compatibility_pass_only.build_report` — tools/plan_ui_compatibility_pass_only.py:196 — Builds build report for the payments feature. Main detected dependency: Counter.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._build_reports_tab._toggle_reports_notes_panel` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:17645 — Handles toggle reports notes panel for the payments feature. Main detected dependency: _log_suppressed_once.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.resolve_area_order_from_prefs` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:2021 — NO-UI resolver: - Reads order from data/ledger_prefs.json["areas_order"] - Case/whitespace-insensitive matching - Appends new areas (not in prefs) alphabetically Returns arranged list.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select.print_full_daily_ledger._draw_global_header` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:22901 — Handles draw global header for the clients feature. Main detected dependency: _log_suppressed_once.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.print_full_daily_ledger._draw_global_header` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:32791 — Handles draw global header for the clients feature. Main detected dependency: _log_suppressed_once.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._import_from_excel_entry` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:18355 — Import payments from Excel. Supports: 1) Date-grid templates (first row has 'Client Name' + date columns like YYYY-MM-DD) via _import_from_excel_core() 2) One-day Daily Collection templates (Client | Payment | Reason), optionally grouped by [AREA] rows Notes: - Unknown clients are skipped (to avoid 
- `spina_app.theme_palettes._spina_v22_reports_colors` — spina_app/theme_palettes.py:148 — Handles spina v22 reports colors for the reports feature. Main detected dependency: getattr.
- `tools.test_reports_notes_dialog_wiring.main` — tools/test_reports_notes_dialog_wiring.py:13 — Handles main for the clients feature. Main detected dependency: APP_PATH.read_text.
- `tools.test_hierarchical_area_ui_phase2_source.main` — tools/test_hierarchical_area_ui_phase2_source.py:13 — Handles main for the clients feature. Main detected dependency: APP.read_text.
- `tools.ui_action_inventory.print_summary` — tools/ui_action_inventory.py:265 — Generates print summary for the dashboard feature. Main detected dependency: hit.get.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.safe_excel_import` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:26191 — import_fn should accept a file path and return a list of dicts or raise an error.
- `tools.audit_legacy_callback_usage.print_summary` — tools/audit_legacy_callback_usage.py:180 — Generates print summary for the dashboard feature. Main detected dependency: definitions_by_name.get.
- `tools.cleanup_stale_databank_generated_blocks._safety_check_range` — tools/cleanup_stale_databank_generated_blocks.py:301 — Handles safety check range for the data bank feature. Main detected dependency: _format_terms.
- `tools.spina_quality_audit.print_report` — tools/spina_quality_audit.py:271 — Generates print report for the payments feature. Main detected dependency: list.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._side_nav_items` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:15857 — Return visible main tabs as (tab_widget, title, icon).
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._auto_load_report_note` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:18234 — Handles auto load report note for the clients feature. Main detected dependency: _log_exc.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._load_report_note_for_client` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:18319 — Loads load report note for client for the clients feature. Main detected dependency: _log_exc.
- `spina_app.tabs.reports._spina_v22_button` — spina_app/tabs/reports.py:62 — Handles spina v22 button for the reports feature. Main detected dependency: _spina_v22_reports_colors.
- `tools.redundancy_audit.print_report` — tools/redundancy_audit.py:108 — Generates print report for the reports feature. Main detected dependency: isinstance.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select.print_full_daily_ledger._wrap_text_to_width` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:22848 — Handles wrap text to width for the reports feature. Main detected dependency: _fits.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.print_full_daily_ledger._wrap_text_to_width` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:32738 — Handles wrap text to width for the reports feature. Main detected dependency: _fits.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._open_note_dialog` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:9898 — Handles open note dialog for the clients feature. Main detected dependency: NoteEditorDialog.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.safe_excel_import.wrapper` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:26196 — Handles wrapper for the reports feature. Main detected dependency: ValueError.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._build_reports_tab._apply_report_range_from_fields` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:17460 — Handles apply report range from fields for the payments feature. Main detected dependency: _dt.strptime.
- `tools.audit_silent_ui_errors.print_summary` — tools/audit_silent_ui_errors.py:209 — Generates print summary for the dashboard feature. Main detected dependency: hit.get.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._on_mode_change` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8830 — Refresh visible tables when the mode selector changes.
- `spina_app.tabs.reports._spina_v22_style_reports_tree` — spina_app/tabs/reports.py:38 — Handles spina v22 style reports tree for the payments feature. Main detected dependency: _spina_v22_reports_colors.
- `tools.audit_bare_except_context.build_report` — tools/audit_bare_except_context.py:90 — Builds build report for the payments feature. Main detected dependency: Visitor.
- `tools.test_reports_feature_wave_18._assert_structure` — tools/test_reports_feature_wave_18.py:43 — Handles assert structure for the reports feature. Main detected dependency: EXPECTED_HASHES.items.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._build_reports_tab._sync_reports_range` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:17438 — Handles sync reports range for the reports feature. Main detected dependency: _dt.strptime.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.add_pdf_header` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3995 — Reusable header for PDFs with logo, title, and current date.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.print_full_daily_ledger.ensure_space` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:32891 — Handles ensure space for the collectors feature. Main detected dependency: _draw_page_number.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select.print_full_daily_ledger.ensure_space` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:23001 — Handles ensure space for the collectors feature. Main detected dependency: _draw_page_number.
- `tools.cleanup_databank_export_ui_source.is_confirmed_databank_export_ui_line` — tools/cleanup_databank_export_ui_source.py:95 — Handles is confirmed databank export ui line for the clients feature. Main detected dependency: _has_any.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._log_exc` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1269 — Log exceptions to data/spina_app.log (best-effort).
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._log_suppressed_once` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1294 — Log a suppressed exception only once per key (to avoid log spam).
- `tools.plan_module_separation._suggest_module` — tools/plan_module_separation.py:108 — Handles suggest module for the reports feature. Main detected dependency: any.
- …and 47 more.

### Support

**984 symbols · 10,126 lines**

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina__parse_flexible_due_rule` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:38895 — Return (label, due_today_bool) for optional flex_due_rule. Supported examples: - salary 15/30 window 2 -> due from 13-17 and last-day-2 through last-day+2 if valid - weekly Monday Thursday -> due every Monday and Thursday - 2nd Saturday -> due every 2nd Saturday of the month - days 13,14,15,29,30,31
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._resize_databank_columns` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:16904 — Resize Data Bank columns responsively. Supports 'freeze panes' layout: - name_tree shows Client + Area (fixed, no horizontal scroll) - days_tree shows day columns with horizontal scroll
- `tools.redundancy_audit.audit` — tools/redundancy_audit.py:33 — Handles audit for the utilities feature. Main detected dependency: assignments.append.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._collectors_areas_drag_end` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:20914 — Handles collectors areas drag end for the collectors feature. Main detected dependency: getattr.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._resolve_note_key_scoped` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:2374 — Resolve a notes_dict key for a client. Preferred (stable) keys: - shared scope: PID|<person_uid> (or CID|<client_uid> fallback) - type scope: PT|<person_uid>|<loan_type> (or CID|<client_uid> fallback) Legacy fallback keys remain supported: - shared: name - type: '<loan_type>::<name>' Uses candidate 
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina__client_due_meta` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:24013 — Return (day_due_label, due_today_bool) using stored schedule fields when present.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app__maybe_suggest_link_clients` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:30175 — Handles app maybe suggest link clients for the clients feature. Main detected dependency: _app__norm_lt_value.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app__client_form._flex_due_options` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:28626 — Handles flex due options for the clients feature. Main detected dependency: enumerate.
- `tools.audit_silent_ui_errors.audit` — tools/audit_silent_ui_errors.py:151 — Handles audit for the other feature. Main detected dependency: EXCEPT_RE.match.
- `tools.extract_cilog_action_label.build_plan` — tools/extract_cilog_action_label.py:56 — Builds build plan for the utilities feature. Main detected dependency: RuntimeError.
- `tools.extract_cilog_value_formatter.build_plan` — tools/extract_cilog_value_formatter.py:63 — Builds build plan for the utilities feature. Main detected dependency: RuntimeError.
- `spina_app.theme_palettes._spina_v21_cash_colors` — spina_app/theme_palettes.py:44 — Handles spina v21 cash colors for the settings feature. Main detected dependency: getattr.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.draw_notes_aligned` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8762 — Draws: Note: YYYY-MM-DD wrapped note text (blank) continuation lines aligned under text column Returns the new y after drawing.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.generate_client_pdf._draw_month_block` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:28267 — Handles draw month block for the payments feature. Main detected dependency: _math.ceil.
- `spina_app.theme_palettes._spina_v24_cilog_colors` — spina_app/theme_palettes.py:98 — Handles spina v24 cilog colors for the settings feature. Main detected dependency: getattr.
- `spina_app.theme_palettes._spina_v18_dashboard_palette` — spina_app/theme_palettes.py:279 — Handles spina v18 dashboard palette for the dashboard feature. Main detected dependency: getattr.
- `tools.audit_blocking_ui_calls.BlockingCallVisitor` — tools/audit_blocking_ui_calls.py:88 — Represents BlockingCallVisitor for the other feature.
- `tools.test_legacy_dashboard_card_batch_16._capture` — tools/test_legacy_dashboard_card_batch_16.py:133 — Handles capture for the dashboard feature. Main detected dependency: FakeWidget.
- `tools.audit_bare_except_context.Visitor` — tools/audit_bare_except_context.py:41 — Represents Visitor for the payments feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._run_long_task._finish` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:14554 — Handles finish for the payments feature. Main detected dependency: _cleanup_dialog.
- `tools.inspect_blocking_ui_context.BlockingContextVisitor` — tools/inspect_blocking_ui_context.py:86 — Represents BlockingContextVisitor for the other feature.
- `tools.test_ui_display_helper_batch._capture_card` — tools/test_ui_display_helper_batch.py:166 — Handles capture card for the utilities feature. Main detected dependency: FakeLabel.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._header_palette` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:16069 — Compact color palette for the modern top header.
- `spina_app.theme_palettes._spina_v17_dash_colors` — spina_app/theme_palettes.py:234 — Dashboard-specific modern colors that work in light and dark mode.
- `spina_app.theme_palettes._spina_v25_collector_colors` — spina_app/theme_palettes.py:190 — Handles spina v25 collector colors for the collectors feature. Main detected dependency: getattr.
- `tools.cleanup_stale_databank_generated_blocks._candidate_range_for_reference` — tools/cleanup_stale_databank_generated_blocks.py:231 — Return 0-based [start, end) candidate range for a stale generated block.
- `tools.plan_remaining_pass_only_groups.PassOnlyVisitor` — tools/plan_remaining_pass_only_groups.py:108 — Represents PassOnlyVisitor for the payments feature.
- `tools.test_display_ui_helper_batch_04._capture_card` — tools/test_display_ui_helper_batch_04.py:134 — Handles capture card for the utilities feature. Main detected dependency: FakeLabel.
- `tools.cleanup_modern_ui_pass_only.inspect_target` — tools/cleanup_modern_ui_pass_only.py:60 — Handles inspect target for the payments feature. Main detected dependency: context.
- `spina_app.theme_palettes._spina_v20_dash_palette` — spina_app/theme_palettes.py:4 — Handles spina v20 dash palette for the settings feature. Main detected dependency: getattr.
- `tools.audit_dynamic_sql_context.enclosing_stack` — tools/audit_dynamic_sql_context.py:72 — Handles enclosing stack for the other feature. Main detected dependency: Visitor.
- `tools.cleanup_databank_export_callbacks._find_function_ranges` — tools/cleanup_databank_export_callbacks.py:53 — Return 0-based inclusive/exclusive ranges for a function definition. Each result is (start_index, end_index, indent).
- `tools.test_cilog_money_formatter_extraction.main` — tools/test_cilog_money_formatter_extraction.py:106 — Handles main for the utilities feature. Main detected dependency: AssertionError.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._run_long_task._watchdog` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:14627 — Handles watchdog for the payments feature. Main detected dependency: TimeoutError.
- `tools.audit_legacy_callback_usage.collect_references` — tools/audit_legacy_callback_usage.py:97 — Handles collect references for the other feature. Main detected dependency: ASSIGN_OR_DEF_RE.search.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._looks_like_data_grid` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:13193 — Heuristic: columns contain 'client' + 'area' and many day columns (d1..d31 or numeric headings).
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v20_populate_dashboard_tree` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:41937 — Handles spina v20 populate dashboard tree for the dashboard feature. Main detected dependency: _log_exc.
- `tools.audit_pass_only_exceptions.audit.walk` — tools/audit_pass_only_exceptions.py:65 — Handles walk for the payments feature. Main detected dependency: _handler_name.
- `tools.test_collector_route_card_batch_13._capture` — tools/test_collector_route_card_batch_13.py:127 — Handles capture for the dashboard feature. Main detected dependency: FakeWidget.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.split_area_main_sub` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:2074 — Split a single Area string into (main_area, sub_area). Backwards compatible: - If no separator is found, main_area = original, sub_area = "" - Supports separators like: 'Main - Sub', 'Main / Sub', 'Main | Sub', 'Main: Sub'
- …and 944 more.

### Ui Only

**59 symbols · 908 lines**

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_configure_dashboard_tree_theme` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:37078 — Keep Dashboard Treeview text readable in both Light and Dark mode. The Dashboard uses colored status tags. In Dark Mode, the app-level Treeview foreground is light; if the tag background is also light pastel, the text becomes hard to read. This function sets both background AND foreground for every 
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._refresh_header_theme` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:16211 — Apply the current theme colors to the modern top header.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._CalendarRangePopup._build_ui` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1780 — Builds build ui for the other feature. Main detected dependency: b.pack.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._CalendarPopup._build_ui` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1635 — Builds build ui for the other feature. Main detected dependency: b.pack.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._configure_tree_stripes` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:15197 — Configure zebra striping tags on a ttk.Treeview based on current theme. Important: tag backgrounds override ttk style colors. Without this, Dark Mode can end up with light (white) row backgrounds + light foreground, which is hard to read.
- `spina_app.tabs.collectors._collectors_toggle_sections` — spina_app/tabs/collectors.py:125 — Handles collectors toggle sections for the collectors feature. Main detected dependency: bool.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._locate_data_tree` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:13229 — Find and memoize the actual Treeview used by the Data grid.
- `spina_app.tabs.dashboard._spina_v17_visible_dashboard_rows` — spina_app/tabs/dashboard.py:52 — Handles spina v17 visible dashboard rows for the dashboard feature. Main detected dependency: getattr.
- `tools.test_cash_control_ui_controls_batch_09._capture_style` — tools/test_cash_control_ui_controls_batch_09.py:188 — Handles capture style for the dashboard feature. Main detected dependency: _reset_runtime.
- `tools.test_cilog_ui_controls_batch_10._capture_style` — tools/test_cilog_ui_controls_batch_10.py:176 — Handles capture style for the other feature. Main detected dependency: _reset_runtime.
- `tools.test_client_route_tree_style_batch_12._capture_style` — tools/test_client_route_tree_style_batch_12.py:138 — Handles capture style for the clients feature. Main detected dependency: _reset_runtime.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._run_long_task._request_cancel` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:14601 — Handles request cancel for the payments feature. Main detected dependency: _cleanup_dialog.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._show_import_log_window._make_tab` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:18901 — Handles make tab for the payments feature. Main detected dependency: groups.get.
- `tools.test_legacy_dashboard_controls_batch_15._capture_style` — tools/test_legacy_dashboard_controls_batch_15.py:196 — Handles capture style for the dashboard feature. Main detected dependency: _reset_runtime.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app__client_form._toggle_due_widgets` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:28925 — Handles toggle due widgets for the payments feature. Main detected dependency: _prime_due_defaults.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_tree_wheel` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:34674 — Ensure mousewheel scroll works on Collector Route list (Treeview).
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v18_patch_dashboard_chart_cards` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:41497 — Make chart cards consistent: light outer panel, dark readable chart area.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._CalendarPopup._render` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1672 — Handles render for the other feature. Main detected dependency: b.configure.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.export_range_template._apply_preset_fields` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:26387 — Handles apply preset fields for the other feature. Main detected dependency: _cal2.monthrange.
- `spina_app.tabs.dashboard._spina_dashboard_visible_rows` — spina_app/tabs/dashboard.py:525 — Handles spina dashboard visible rows for the dashboard feature. Main detected dependency: getattr.
- `spina_app.ui_cards._spina_v17_make_card` — spina_app/ui_cards.py:54 — Handles spina v17 make card for the other feature. Main detected dependency: _spina_v17_dash_colors.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app__client_form._toggle_paymode_other` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:28947 — Handles toggle paymode other for the payments feature. Main detected dependency: paymode_other_var.set.
- `tools.disable_full_daily_ledger._looks_like_legacy_button_line` — tools/disable_full_daily_ledger.py:376 — Handles looks like legacy button line for the reports feature. Main detected dependency: _contains_legacy_label.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._tk_button_hover` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:16113 — Small hover helper for plain tk buttons/labels.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app_open_client_history_dialog._mk_ro_text` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:29744 — Handles mk ro text for the other feature. Main detected dependency: frm.grid_columnconfigure.
- `tools.remove_databank_export_controls._looks_like_ui_line` — tools/remove_databank_export_controls.py:380 — Handles looks like ui line for the data bank feature. Main detected dependency: any.
- `tools.test_legacy_dashboard_controls_batch_15._reset_runtime` — tools/test_legacy_dashboard_controls_batch_15.py:100 — Handles reset runtime for the dashboard feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.main` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:31145 — Handles main for the payments feature. Main detected dependency: App.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v23_client_form.section` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:42546 — Handles section for the other feature. Main detected dependency: f.pack.
- `spina_app.tabs.clients._spina_v23_card` — spina_app/tabs/clients.py:67 — Handles spina v23 card for the clients feature. Main detected dependency: _spina_v23_clients_colors.
- `spina_app.tabs.collectors._spina_v25_collector_card` — spina_app/tabs/collectors.py:16 — Handles spina v25 collector card for the collectors feature. Main detected dependency: _spina_v25_collector_colors.
- `spina_app.ui_cards._spina_v21_cash_card` — spina_app/ui_cards.py:15 — Handles spina v21 cash card for the other feature. Main detected dependency: _spina_v21_cash_colors.
- `spina_app.ui_cards._spina_v24_cilog_card` — spina_app/ui_cards.py:28 — Handles spina v24 cilog card for the other feature. Main detected dependency: _spina_v24_cilog_colors.
- `spina_app.ui_cards._spina_v27_route_card` — spina_app/ui_cards.py:41 — Handles spina v27 route card for the collectors feature. Main detected dependency: _spina_v27_route_colors.
- `tools.test_client_route_tree_style_batch_12._reset_runtime` — tools/test_client_route_tree_style_batch_12.py:80 — Handles reset runtime for the clients feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app__client_form._toggle_new_until` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:28914 — Handles toggle new until for the payments feature. Main detected dependency: _log_suppressed_once.
- `spina_app.tabs.clients._spina_v23_entry` — spina_app/tabs/clients.py:389 — Handles spina v23 entry for the clients feature. Main detected dependency: _spina_v23_clients_colors.
- `tools.test_legacy_dashboard_controls_batch_15.FakeTk` — tools/test_legacy_dashboard_controls_batch_15.py:42 — Represents FakeTk for the dashboard feature.
- `spina_app.ui_helpers._spina_v17_set_card` — spina_app/ui_helpers.py:43 — Handles spina v17 set card for the payments feature. Main detected dependency: get.
- `spina_app.ui_helpers._spina_v24_cilog_set_card` — spina_app/ui_helpers.py:54 — Handles spina v24 cilog set card for the payments feature. Main detected dependency: get.
- …and 19 more.

## Suggested larger modularization batches

### Batch 1: Clients (607 lines)

Risk mix: `database_read`, `support`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._note_type_key` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:2356 — Type-scoped key stable across name changes. If person_uid exists (linked), store type notes under: PT|<person_uid>|<loan_type_norm> This lets us retrieve the other loan type's notes without needing that row's client_uid.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._resolve_note_key_scoped` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:2374 — Resolve a notes_dict key for a client. Preferred (stable) keys: - shared scope: PID|<person_uid> (or CID|<client_uid> fallback) - type scope: PT|<person_uid>|<loan_type> (or CID|<client_uid> fallback) Legacy fallback keys remain supported: - shared: name - type: '<loan_type>::<name>' Uses candidate 
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._ensure_notes_dir` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:2469 — Handles ensure notes dir for the clients feature. Main detected dependency: _log_suppressed_once.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.get_client_note` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:2670 — Fetch a note for a client. scope: - 'shared' (default): shared notes (prefer person_uid/client_uid; legacy name fallback) - 'type': loan-type specific notes (prefer person_uid+loan_type or client_uid; legacy fallback) - 'effective': prefer type-specific if present, otherwise shared
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.NoteEditorDialog._title_text` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3100 — Handles title text for the clients feature. Main detected dependency: getattr.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.NoteEditorDialog._collect_items` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3260 — Handles collect items for the clients feature. Main detected dependency: _load_client_notes.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.NoteEditorDialog._open_notes_file` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3401 — Handles open notes file for the clients feature. Main detected dependency: _log_suppressed_once.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._looks_like_data_grid` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:13193 — Heuristic: columns contain 'client' + 'area' and many day columns (d1..d31 or numeric headings).
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._resize_databank_columns` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:16904 — Resize Data Bank columns responsively. Supports 'freeze panes' layout: - name_tree shows Client + Area (fixed, no horizontal scroll) - days_tree shows day columns with horizontal scroll
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina__client_due_meta` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:24013 — Return (day_due_label, due_today_bool) using stored schedule fields when present.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app__get_selected_client_name` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:28551 — Handles app get selected client name for the clients feature. Main detected dependency: self.clients_tree.item.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app_schedule_refresh_clients` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:29367 — Debounce Clients search so refresh doesn't run on every keystroke.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app__maybe_suggest_link_clients` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:30175 — Handles app maybe suggest link clients for the clients feature. Main detected dependency: _app__norm_lt_value.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app_import_missing` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:30379 — Handles app import missing for the clients feature. Main detected dependency: _log_suppressed_once.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina__client_pictures_dir` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:35175 — Handles spina client pictures dir for the clients feature. Main detected dependency: data_path.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app__selected_client_name_and_lt` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:35340 — Handles app selected client name and lt for the clients feature. Main detected dependency: _app__norm_lt_value.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app_set_selected_client_picture` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:35452 — Handles app set selected client picture for the clients feature. Main detected dependency: _app__selected_client_name_and_lt.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app_install_clients_picture_ui` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:35506 — Handles app install clients picture ui for the clients feature. Main detected dependency: box.pack.

### Batch 2: Collectors (500 lines)

Risk mix: `database_read`, `support`, `ui_only`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.get_databank_day_collector_totals` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7176 — Retrieves get databank day collector totals for the collectors feature. Main detected dependency: abs.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._show_conflicts` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:12751 — Show areas assigned to multiple collectors.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._collectors_name_from_values` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:20476 — Return the collector name from a Treeview row values tuple. Backwards compatible with older layouts: - Old layout: first value is the collector name. - New layout: first value is a select marker (radio/checkbox/bullet), second is the collector name.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_multi_toggle` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:20539 — Handles on collectors multi toggle for the collectors feature. Main detected dependency: bool.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._collectors_areas_drag_start` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:20888 — Handles collectors areas drag start for the collectors feature. Main detected dependency: self.collector_route_areas_lb.nearest.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._collectors_areas_drag_end` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:20914 — Handles collectors areas drag end for the collectors feature. Main detected dependency: getattr.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._schedule_collectors_refresh` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:31194 — Debounce refresh_collectors while typing in Search.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._clear_collectors_search_filters` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:31214 — Clear search + quick filters for Collector's Route UI.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_tree_wheel` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:34674 — Ensure mousewheel scroll works on Collector Route list (Treeview).
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_multi_toggle` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:34853 — Toggle multi-select mode for Collector Route list (checkbox Sel column).
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_tree_wheel` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:34875 — Mouse wheel scroll for Collector Route list (Treeview).
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._edit_selected_collector` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:35047 — Safe edit action for the context menu ('Full Editor…').
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:38243 — Populate the right-side details panel for the selected collector.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v25_collector_button` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:43042 — Handles spina v25 collector button for the collectors feature. Main detected dependency: _spina_v25_collector_colors.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v27_route_button` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:43510 — Handles spina v27 route button for the collectors feature. Main detected dependency: _spina_v27_route_colors.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v27_get_route_master_areas` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:43856 — Handles spina v27 get route master areas for the collectors feature. Main detected dependency: cleaned.append.
- `spina_app.tabs.collector_route.configure_collector_route_dependencies` — spina_app/tabs/collector_route.py:19 — Bind the desktop-owned Collector Route palette helper.
- `spina_app.tabs.collectors._spina_v25_collector_card` — spina_app/tabs/collectors.py:16 — Handles spina v25 collector card for the collectors feature. Main detected dependency: _spina_v25_collector_colors.

### Batch 3: Clients (494 lines)

Risk mix: `database_read`, `support`, `ui_only`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_refresh_client_info_logs` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:38623 — Handles spina refresh client info logs for the clients feature. Main detected dependency: _log_exc.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina__parse_flexible_due_rule` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:38895 — Return (label, due_today_bool) for optional flex_due_rule. Supported examples: - salary 15/30 window 2 -> due from 13-17 and last-day-2 through last-day+2 if valid - weekly Monday Thursday -> due every Monday and Thursday - 2nd Saturday -> due every 2nd Saturday of the month - days 13,14,15,29,30,31
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina__client_due_meta` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:39066 — Handles spina client due meta for the clients feature. Main detected dependency: _spina__client_due_meta_base.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_route_notice_key` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:39100 — Handles spina route notice key for the clients feature. Main detected dependency: _spina_route_notice_norm_lt.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_route_notice_for_client` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:39167 — Handles spina route notice for client for the clients feature. Main detected dependency: _spina_route_notice_key.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_crc_route_area_matches` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:39494 — Match route area to client area, including MAIN-only collector routes covering subareas.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_crc_collector_for_area` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:39521 — Handles spina crc collector for area for the clients feature. Main detected dependency: _spina_crc_route_area_matches.
- `spina_app.area_hierarchy_ops.count_clients_for_area_node` — spina_app/area_hierarchy_ops.py:142 — Count clients assigned directly to a node or its whole subtree.
- `spina_app.area_hierarchy_ui._refresh_app_area_views` — spina_app/area_hierarchy_ui.py:29 — Refresh legacy Area consumers only after the manager actually changed data.
- `spina_app.area_hierarchy_ui.build_simple_area_selector` — spina_app/area_hierarchy_ui.py:308 — Return a compact read-only selector row for legacy client forms.
- `spina_app.area_hierarchy_ui.build_area_selector_field` — spina_app/area_hierarchy_ui.py:335 — Build the modern client form's labeled, read-only Area selector.
- `spina_app.tabs.client_info_logs.configure_client_info_logs_dependencies` — spina_app/tabs/client_info_logs.py:26 — Bind application-owned callbacks used by the CILog presentation module.
- `spina_app.tabs.client_info_logs._spina_v24_cilog_stats` — spina_app/tabs/client_info_logs.py:56 — Handles spina v24 cilog stats for the clients feature. Main detected dependency: _spina_v24_cilog_parse_day.
- `spina_app.tabs.client_info_logs._spina_v24_refresh_client_info_logs` — spina_app/tabs/client_info_logs.py:537 — Handles spina v24 refresh client info logs for the clients feature. Main detected dependency: _log_exc.
- `spina_app.tabs.clients.configure_clients_dependencies` — spina_app/tabs/clients.py:25 — Bind application-owned callbacks used by the Clients presentation module.
- `spina_app.tabs.clients._spina_v23_button` — spina_app/tabs/clients.py:37 — Handles spina v23 button for the clients feature. Main detected dependency: _spina_v23_clients_colors.
- `spina_app.tabs.clients._spina_v23_card` — spina_app/tabs/clients.py:67 — Handles spina v23 card for the clients feature. Main detected dependency: _spina_v23_clients_colors.
- `spina_app.tabs.clients._spina_v23_selected_name_lt` — spina_app/tabs/clients.py:79 — Handles spina v23 selected name lt for the clients feature. Main detected dependency: _app__norm_lt_value.

### Batch 4: Payments (487 lines)

Risk mix: `database_read`, `support`, `ui_only`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._vscroll` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:16848 — Handles vscroll for the payments feature. Main detected dependency: _log_suppressed_once.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._on_mousewheel_sync` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:16873 — Mouse wheel scroll should move both name_tree (left) and days_tree (right) together.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._refresh_area_dropdowns` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:19891 — Refresh any area dropdowns (best-effort).
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.export_range_template` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:26343 — Export an Excel template for payments over a chosen date range. Presets: This Month / This Year / Custom (YYYY-MM-DD).
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._parse_reason_color_token_meta` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:26758 — Extract [RC:...] token plus optional window meta from the description. Supported token payloads (inside the brackets): - '#RRGGBB' - 'red' / 'green' / etc - '#RRGGBB;D:3' -> days=3 (inclusive, starting from the reason's date) - '#RRGGBB;UNTIL:YYYY-MM-DD' -> until (inclusive) - 'red;D:3' / 'red;UNTIL
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._extract_reason_and_color_from_desc` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:26845 — Return (reason_text, color_hex) from a transaction description. - Removes [ADV:...] tags - Extracts and removes [RC:...] token (optional ';D:n' / ';UNTIL:YYYY-MM-DD') - Returns trimmed reason text (may be empty)
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._extract_reason_color_meta_from_desc` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:26859 — Return (reason_text, color_hex, meta) from a transaction description. meta = {'days': int|None, 'until': date|None}
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._hex_to_rgb01` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:26871 — '#RRGGBB' -> (r,g,b) floats 0..1
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.RenewDialog._set_manual_rc` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:30699 — Updates set manual rc for the payments feature. Main detected dependency: _log_suppressed_once.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.RenewDialog._set_auto_rc` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:30707 — Updates set auto rc for the payments feature. Main detected dependency: _log_suppressed_once.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.main` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:31145 — Handles main for the payments feature. Main detected dependency: App.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_schedule_auto_daily_close` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:38850 — Run auto close now and then check periodically while the app is open.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_crc_clean_reason` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:39418 — Handles spina crc clean reason for the payments feature. Main detected dependency: re.sub.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_crc_split_area` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:39479 — Handles spina crc split area for the payments feature. Main detected dependency: a.split.
- `spina_app.area_hierarchy._row_value` — spina_app/area_hierarchy.py:62 — Handles row value for the payments feature. Main detected dependency: hasattr.
- `spina_app.area_hierarchy_ui._remember_open_folders` — spina_app/area_hierarchy_ui.py:76 — Handles remember open folders for the payments feature. Main detected dependency: bool.
- `spina_app.ui_controls._spina_v21_style_cash_table` — spina_app/ui_controls.py:26 — Handles spina v21 style cash table for the payments feature. Main detected dependency: _spina_v21_cash_colors.
- `spina_app.ui_controls._spina_v24_cilog_style_tree` — spina_app/ui_controls.py:82 — Handles spina v24 cilog style tree for the payments feature. Main detected dependency: _spina_v24_cilog_colors.

### Batch 5: Dashboard (378 lines)

Risk mix: `database_read`, `support`, `ui_only`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._system_data_open_close` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:10093 — Handles system data open close for the dashboard feature. Main detected dependency: self._system_data_get_date.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._show_unassigned_areas` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:12777 — Show areas not assigned to any collector (plus any unknown route areas).
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_configure_dashboard_tree_theme` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:37078 — Keep Dashboard Treeview text readable in both Light and Dark mode. The Dashboard uses colored status tags. In Dark Mode, the app-level Treeview foreground is light; if the tag background is also light pastel, the text becomes hard to read. This function sets both background AND foreground for every 
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_refresh_dashboard` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:37313 — Handles spina refresh dashboard for the dashboard feature. Main detected dependency: _log_exc.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v18_patch_dashboard_chart_cards` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:41497 — Make chart cards consistent: light outer panel, dark readable chart area.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v18_populate_dashboard_tree` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:41637 — Handles spina v18 populate dashboard tree for the dashboard feature. Main detected dependency: _log_exc.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v18_refresh_dashboard` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:41657 — Handles spina v18 refresh dashboard for the dashboard feature. Main detected dependency: _log_exc.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v19_refresh_dashboard` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:41715 — Handles spina v19 refresh dashboard for the dashboard feature. Main detected dependency: _log_exc.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v20_populate_dashboard_tree` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:41937 — Handles spina v20 populate dashboard tree for the dashboard feature. Main detected dependency: _log_exc.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v20_refresh_dashboard` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:41974 — Handles spina v20 refresh dashboard for the dashboard feature. Main detected dependency: _log_exc.
- `spina_app.tabs.cash_control.configure_cash_control_dependencies` — spina_app/tabs/cash_control.py:25 — Bind application-owned display and logging helpers used by Cash Control.
- `spina_app.tabs.dashboard.configure_legacy_dashboard_feature` — spina_app/tabs/dashboard.py:31 — Attach main-module services without importing the large entry module.
- `spina_app.tabs.dashboard._spina_dashboard_fetch_rows` — spina_app/tabs/dashboard.py:40 — Handles spina dashboard fetch rows for the dashboard feature. Main detected dependency: _dashboard_fetch_rows.
- `spina_app.tabs.dashboard._log_exc` — spina_app/tabs/dashboard.py:46 — Handles log exc for the dashboard feature. Main detected dependency: _dashboard_log_exc.
- `spina_app.tabs.dashboard._spina_v17_visible_dashboard_rows` — spina_app/tabs/dashboard.py:52 — Handles spina v17 visible dashboard rows for the dashboard feature. Main detected dependency: getattr.
- `spina_app.tabs.dashboard._spina_v17_refresh_dashboard` — spina_app/tabs/dashboard.py:503 — Handles spina v17 refresh dashboard for the dashboard feature. Main detected dependency: _log_exc.
- `spina_app.tabs.dashboard._spina_dashboard_visible_rows` — spina_app/tabs/dashboard.py:525 — Handles spina dashboard visible rows for the dashboard feature. Main detected dependency: getattr.
- `spina_app.tabs.dashboard._spina_v19_visible_dashboard_rows` — spina_app/tabs/dashboard.py:545 — Dashboard should show all active clients by default, not only priority clients.

### Batch 6: Payments (376 lines)

Risk mix: `database_read`, `support`, `ui_only`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.NoteEditorDialog._close` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3578 — Handles close for the payments feature. Main detected dependency: _log_suppressed_once.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.parse_advance_ranges` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3649 — Parse one or more ADV date ranges from a transaction description. Supported tags (whitespace/case-tolerant): - [ADV:YYYY-MM-DD..YYYY-MM-DD] (single range) - [ADV:YYYY-MM-DD,YYYY-MM-DD,YYYY-MM-DD] (explicit days) - [ADV:range;range;...] where range is either: * YYYY-MM-DD..YYYY-MM-DD * YYYY-MM-DD (si
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.parse_advance_range` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3758 — Backward-compatible helper: return first (start,end) ADV range if present.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.set_default_loan_type` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3983 — Set the default loan_type context used when caller does not pass loan_type.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._show_system_data_tab` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:9985 — Handles show system data tab for the payments feature. Main detected dependency: _log_suppressed_once.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._hide_system_data_tab` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:9996 — Handles hide system data tab for the payments feature. Main detected dependency: _log_suppressed_once.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._show_audit_tab` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:13845 — Handles show audit tab for the payments feature. Main detected dependency: _log_suppressed_once.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._hide_audit_tab` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:13855 — Handles hide audit tab for the payments feature. Main detected dependency: _log_suppressed_once.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._audit_set_today` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:13901 — Handles audit set today for the payments feature. Main detected dependency: _date.today.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._audit_set_last7` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:13911 — Handles audit set last7 for the payments feature. Main detected dependency: _date.today.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._audit_set_all` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:13922 — Handles audit set all for the payments feature. Main detected dependency: self.audit_from_var.set.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._start_ui_queue_pump` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:14355 — Process UI-call requests from worker threads. This keeps Tk operations on the main thread. Any unexpected errors in the pump are logged (instead of silently swallowed) to avoid "stuck UI" mysteries.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._ui_async` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:14446 — Schedule a UI function to run on the Tk main thread (non-blocking).
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._patch_messagebox_threadsafe` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:14461 — Make tkinter.messagebox safe to call from worker threads.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._select_side_tab` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:15890 — Handles select side tab for the payments feature. Main detected dependency: _log_suppressed_once.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._refresh_modern_shell_theme` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:16046 — Apply theme colors to the modern sidebar shell and rebuild nav labels/buttons.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._tk_button_hover` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:16113 — Small hover helper for plain tk buttons/labels.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._refresh_header_theme` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:16211 — Apply the current theme colors to the modern top header.

### Batch 7: Settings (366 lines)

Risk mix: `database_read`, `support`, `ui_only`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._theme_toggle_text` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:14919 — Handles theme toggle text for the settings feature. Main detected dependency: getattr.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.toggle_theme` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:14926 — Handles toggle theme for the settings feature. Main detected dependency: getattr.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._theme_palette` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:14994 — Handles theme palette for the settings feature. Main detected dependency: getattr.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._configure_tree_stripes` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:15197 — Configure zebra striping tags on a ttk.Treeview based on current theme. Important: tag backgrounds override ttk style colors. Without this, Dark Mode can end up with light (white) row backgrounds + light foreground, which is hard to read.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._header_palette` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:16069 — Compact color palette for the modern top header.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_auto_close_after_days_value` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:38672 — Return the configured auto-close delay in days. 0 = disabled.
- `spina_app.theme_palettes._spina_v20_dash_palette` — spina_app/theme_palettes.py:4 — Handles spina v20 dash palette for the settings feature. Main detected dependency: getattr.
- `spina_app.theme_palettes._spina_v21_cash_colors` — spina_app/theme_palettes.py:44 — Handles spina v21 cash colors for the settings feature. Main detected dependency: getattr.
- `spina_app.theme_palettes._spina_v24_cilog_colors` — spina_app/theme_palettes.py:98 — Handles spina v24 cilog colors for the settings feature. Main detected dependency: getattr.
- `tools.test_base_theme_palette_batch_11.Holder.__init__` — tools/test_base_theme_palette_batch_11.py:31 — Handles init for the settings feature.
- `tools.test_base_theme_palette_batch_11.BadString.__str__` — tools/test_base_theme_palette_batch_11.py:37 — Handles str for the settings feature. Main detected dependency: RuntimeError.
- `tools.test_base_theme_palette_batch_11._stable` — tools/test_base_theme_palette_batch_11.py:41 — Handles stable for the settings feature. Main detected dependency: _stable.
- `tools.test_base_theme_palette_batch_11._type_name` — tools/test_base_theme_palette_batch_11.py:51 — Handles type name for the settings feature. Main detected dependency: type.
- `tools.test_base_theme_palette_batch_11._load_manifest` — tools/test_base_theme_palette_batch_11.py:56 — Loads load manifest for the settings feature. Main detected dependency: json.loads.
- `tools.test_base_theme_palette_batch_11._resolve_from_source` — tools/test_base_theme_palette_batch_11.py:60 — Handles resolve from source for the settings feature. Main detected dependency: RuntimeError.
- `tools.test_base_theme_palette_batch_11._resolve_function` — tools/test_base_theme_palette_batch_11.py:83 — Handles resolve function for the settings feature. Main detected dependency: RuntimeError.
- `tools.test_base_theme_palette_batch_11._cases` — tools/test_base_theme_palette_batch_11.py:96 — Handles cases for the settings feature. Main detected dependency: BadString.
- `tools.test_base_theme_palette_batch_11._capture_call` — tools/test_base_theme_palette_batch_11.py:112 — Handles capture call for the settings feature. Main detected dependency: _stable.

### Batch 8: Utilities (353 lines)

Risk mix: `database_read`, `support`

- `tools.extract_numeric_parsers._local_names` — tools/extract_numeric_parsers.py:49 — Handles local names for the utilities feature. Main detected dependency: ast.walk.
- `tools.extract_numeric_parsers._external_loaded_names` — tools/extract_numeric_parsers.py:72 — Handles external loaded names for the utilities feature. Main detected dependency: _local_names.
- `tools.extract_numeric_parsers._validate_function` — tools/extract_numeric_parsers.py:82 — Validates validate function for the utilities feature. Main detected dependency: RuntimeError.
- `tools.extract_numeric_parsers._module_source` — tools/extract_numeric_parsers.py:97 — Handles module source for the utilities feature. Main detected dependency: _line_source.
- `tools.extract_numeric_parsers._patched_source` — tools/extract_numeric_parsers.py:119 — Handles patched source for the utilities feature. Main detected dependency: functions.items.
- `tools.extract_numeric_parsers._state` — tools/extract_numeric_parsers.py:130 — Handles state for the utilities feature. Main detected dependency: IMPORT_LINES.items.
- `tools.extract_numeric_parsers.build_plan` — tools/extract_numeric_parsers.py:143 — Builds build plan for the utilities feature. Main detected dependency: RuntimeError.
- `tools.extract_numeric_parsers.apply_extraction` — tools/extract_numeric_parsers.py:209 — Handles apply extraction for the utilities feature. Main detected dependency: _atomic_write.
- `tools.extract_pure_helper_batch._load_manifest` — tools/extract_pure_helper_batch.py:22 — Loads load manifest for the utilities feature. Main detected dependency: RuntimeError.
- `tools.extract_pure_helper_batch._source_hash` — tools/extract_pure_helper_batch.py:31 — Handles source hash for the utilities feature. Main detected dependency: hashlib.sha256.
- `tools.extract_pure_helper_batch._external_names` — tools/extract_pure_helper_batch.py:35 — Handles external names for the utilities feature. Main detected dependency: ast.walk.
- `tools.extract_pure_helper_batch._matching_imports` — tools/extract_pure_helper_batch.py:59 — Handles matching imports for the utilities feature. Main detected dependency: isinstance.
- `tools.extract_pure_helper_batch._module_definitions` — tools/extract_pure_helper_batch.py:70 — Handles module definitions for the utilities feature. Main detected dependency: RuntimeError.
- `tools.extract_pure_helper_batch.inspect` — tools/extract_pure_helper_batch.py:81 — Handles inspect for the utilities feature. Main detected dependency: Path.
- `tools.extract_text_normalizers._line_source` — tools/extract_text_normalizers.py:34 — Handles line source for the utilities feature. Main detected dependency: getattr.
- `tools.extract_text_normalizers._top_level_functions` — tools/extract_text_normalizers.py:42 — Handles top level functions for the utilities feature. Main detected dependency: RuntimeError.
- `tools.extract_text_normalizers._local_names` — tools/extract_text_normalizers.py:52 — Handles local names for the utilities feature. Main detected dependency: ast.walk.
- `tools.extract_text_normalizers._external_loaded_names` — tools/extract_text_normalizers.py:75 — Handles external loaded names for the utilities feature. Main detected dependency: _local_names.

### Batch 9: Utilities (311 lines)

Risk mix: `database_read`, `support`

- `tools.extract_text_normalizers._import_bindings` — tools/extract_text_normalizers.py:85 — Handles import bindings for the utilities feature. Main detected dependency: alias.name.split.
- `tools.extract_text_normalizers._required_import_nodes` — tools/extract_text_normalizers.py:105 — Handles required import nodes for the utilities feature. Main detected dependency: RuntimeError.
- `tools.extract_text_normalizers._module_source` — tools/extract_text_normalizers.py:144 — Handles module source for the utilities feature. Main detected dependency: _line_source.
- `tools.extract_text_normalizers._patched_source` — tools/extract_text_normalizers.py:167 — Handles patched source for the utilities feature. Main detected dependency: functions.items.
- `tools.extract_text_normalizers._state` — tools/extract_text_normalizers.py:181 — Handles state for the utilities feature. Main detected dependency: IMPORT_LINES.items.
- `tools.extract_text_normalizers.apply_extraction` — tools/extract_text_normalizers.py:274 — Handles apply extraction for the utilities feature. Main detected dependency: _atomic_write.
- `tools.redundancy_audit.audit` — tools/redundancy_audit.py:33 — Handles audit for the utilities feature. Main detected dependency: assignments.append.
- `tools.spina_quality_audit._sql_literal` — tools/spina_quality_audit.py:83 — Handles sql literal for the utilities feature. Main detected dependency: isinstance.
- `tools.test_append_unique_text_extraction.load_helper` — tools/test_append_unique_text_extraction.py:36 — Loads load helper for the utilities feature. Main detected dependency: APP_PATH.read_text.
- `tools.test_cilog_action_label_extraction._load` — tools/test_cilog_action_label_extraction.py:60 — Handles load for the utilities feature. Main detected dependency: RuntimeError.
- `tools.test_cilog_action_label_extraction._source_state` — tools/test_cilog_action_label_extraction.py:69 — Handles source state for the utilities feature. Main detected dependency: any.
- `tools.test_cilog_action_label_extraction.main` — tools/test_cilog_action_label_extraction.py:139 — Handles main for the utilities feature. Main detected dependency: AssertionError.
- `tools.test_cilog_diff_pairs_extraction._load_target` — tools/test_cilog_diff_pairs_extraction.py:17 — Loads load target for the utilities feature. Main detected dependency: RuntimeError.
- `tools.test_cilog_money_formatter_extraction._cases` — tools/test_cilog_money_formatter_extraction.py:20 — Handles cases for the utilities feature.
- `tools.test_cilog_money_formatter_extraction._capture` — tools/test_cilog_money_formatter_extraction.py:37 — Handles capture for the utilities feature. Main detected dependency: function.
- `tools.test_cilog_money_formatter_extraction._behavior` — tools/test_cilog_money_formatter_extraction.py:53 — Handles behavior for the utilities feature. Main detected dependency: AssertionError.
- `tools.test_cilog_money_formatter_extraction._state` — tools/test_cilog_money_formatter_extraction.py:60 — Handles state for the utilities feature. Main detected dependency: AssertionError.
- `tools.test_cilog_money_formatter_extraction._legacy_function` — tools/test_cilog_money_formatter_extraction.py:72 — Handles legacy function for the utilities feature. Main detected dependency: compile.

### Batch 10: Dashboard (310 lines)

Risk mix: `database_read`, `support`

- `spina_app.tabs.dashboard._spina_v20_visible_rows` — spina_app/tabs/dashboard.py:577 — Handles spina v20 visible rows for the dashboard feature. Main detected dependency: _spina_v19_visible_dashboard_rows.
- `spina_app.theme_palettes._spina_v17_dash_colors` — spina_app/theme_palettes.py:234 — Dashboard-specific modern colors that work in light and dark mode.
- `spina_app.theme_palettes._spina_v18_dashboard_palette` — spina_app/theme_palettes.py:279 — Handles spina v18 dashboard palette for the dashboard feature. Main detected dependency: getattr.
- `spina_app.ui_controls._spina_v17_style_dashboard_table` — spina_app/ui_controls.py:170 — Handles spina v17 style dashboard table for the dashboard feature. Main detected dependency: _spina_v17_dash_colors.
- `spina_app.utilities.dashboard._spina_dash__status_for` — spina_app/utilities/dashboard.py:6 — Handles spina dash status for for the dashboard feature. Main detected dependency: float.
- `tools.extract_cilog_diff_pairs._caller_summary` — tools/extract_cilog_diff_pairs.py:86 — Handles caller summary for the dashboard feature. Main detected dependency: ast.walk.
- `tools.extract_cilog_diff_pairs.inspect_state` — tools/extract_cilog_diff_pairs.py:108 — Handles inspect state for the dashboard feature. Main detected dependency: APP_PATH.read_text.
- `tools.extract_cilog_diff_pairs.apply_extraction` — tools/extract_cilog_diff_pairs.py:138 — Handles apply extraction for the dashboard feature. Main detected dependency: APP_PATH.read_text.
- `tools.plan_ui_compatibility_pass_only.classify_ui_site` — tools/plan_ui_compatibility_pass_only.py:180 — Handles classify ui site for the dashboard feature. Main detected dependency: contains_any.
- `tools.test_cash_control_feature_wave_21.top_level_functions` — tools/test_cash_control_feature_wave_21.py:21 — Handles top level functions for the dashboard feature. Main detected dependency: ast.parse.
- `tools.test_cash_control_feature_wave_21.FakeCanvas.__init__` — tools/test_cash_control_feature_wave_21.py:31 — Handles init for the dashboard feature.
- `tools.test_cash_control_feature_wave_21.FakeCanvas.configure` — tools/test_cash_control_feature_wave_21.py:39 — Handles configure for the dashboard feature. Main detected dependency: self.operations.append.
- `tools.test_cash_control_feature_wave_21.FakeCanvas.winfo_width` — tools/test_cash_control_feature_wave_21.py:42 — Handles winfo width for the dashboard feature.
- `tools.test_cash_control_feature_wave_21.FakeCanvas.winfo_height` — tools/test_cash_control_feature_wave_21.py:45 — Handles winfo height for the dashboard feature.
- `tools.test_cash_control_feature_wave_21.FakeCanvas.create_text` — tools/test_cash_control_feature_wave_21.py:48 — Builds create text for the dashboard feature. Main detected dependency: len.
- `tools.test_cash_control_feature_wave_21.Dummy.__init__` — tools/test_cash_control_feature_wave_21.py:56 — Handles init for the dashboard feature. Main detected dependency: FakeCanvas.
- `tools.test_cash_control_input_normalizer_batch_07._load` — tools/test_cash_control_input_normalizer_batch_07.py:56 — Handles load for the dashboard feature. Main detected dependency: json.loads.
- `tools.test_cash_control_input_normalizer_batch_07._functions` — tools/test_cash_control_input_normalizer_batch_07.py:60 — Handles functions for the dashboard feature. Main detected dependency: RuntimeError.

### Batch 11: Utilities (309 lines)

Risk mix: `database_read`, `support`

- `tools.extract_date_helpers_module._top_level_functions` — tools/extract_date_helpers_module.py:44 — Handles top level functions for the utilities feature. Main detected dependency: RuntimeError.
- `tools.extract_date_helpers_module._local_names` — tools/extract_date_helpers_module.py:54 — Handles local names for the utilities feature. Main detected dependency: ast.walk.
- `tools.extract_date_helpers_module._external_loaded_names` — tools/extract_date_helpers_module.py:78 — Handles external loaded names for the utilities feature. Main detected dependency: _local_names.
- `tools.extract_date_helpers_module._import_bindings` — tools/extract_date_helpers_module.py:88 — Handles import bindings for the utilities feature. Main detected dependency: alias.name.split.
- `tools.extract_date_helpers_module._required_import_nodes` — tools/extract_date_helpers_module.py:110 — Handles required import nodes for the utilities feature. Main detected dependency: RuntimeError.
- `tools.extract_date_helpers_module._module_source` — tools/extract_date_helpers_module.py:149 — Handles module source for the utilities feature. Main detected dependency: _line_source.
- `tools.extract_date_helpers_module._patched_source` — tools/extract_date_helpers_module.py:172 — Handles patched source for the utilities feature. Main detected dependency: functions.items.
- `tools.extract_date_helpers_module._state` — tools/extract_date_helpers_module.py:183 — Handles state for the utilities feature. Main detected dependency: IMPORT_LINES.items.
- `tools.extract_date_helpers_module.apply_extraction` — tools/extract_date_helpers_module.py:269 — Handles apply extraction for the utilities feature. Main detected dependency: _atomic_write.
- `tools.extract_display_formatters._node_source` — tools/extract_display_formatters.py:31 — Handles node source for the utilities feature. Main detected dependency: getattr.
- `tools.extract_display_formatters._top_level_functions` — tools/extract_display_formatters.py:39 — Handles top level functions for the utilities feature. Main detected dependency: RuntimeError.
- `tools.extract_display_formatters._local_names` — tools/extract_display_formatters.py:49 — Handles local names for the utilities feature. Main detected dependency: ast.walk.
- `tools.extract_display_formatters._external_loaded_names` — tools/extract_display_formatters.py:72 — Handles external loaded names for the utilities feature. Main detected dependency: _local_names.
- `tools.extract_display_formatters._module_target_counts` — tools/extract_display_formatters.py:82 — Handles module target counts for the utilities feature. Main detected dependency: ast.parse.
- `tools.extract_display_formatters._state` — tools/extract_display_formatters.py:94 — Handles state for the utilities feature. Main detected dependency: IMPORT_LINES.items.
- `tools.extract_display_formatters._patched_source` — tools/extract_display_formatters.py:107 — Handles patched source for the utilities feature. Main detected dependency: functions.items.
- `tools.extract_display_formatters.build_plan` — tools/extract_display_formatters.py:133 — Builds build plan for the utilities feature. Main detected dependency: RuntimeError.
- `tools.extract_display_formatters.apply_extraction` — tools/extract_display_formatters.py:206 — Handles apply extraction for the utilities feature. Main detected dependency: _atomic_write.

### Batch 12: Utilities (280 lines)

Risk mix: `database_read`, `support`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._PgCompatRow.__init__` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:558 — Handles init for the utilities feature. Main detected dependency: _spina_pg_normalize_value.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._init_logger` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1251 — Handles init logger for the utilities feature. Main detected dependency: _logging.basicConfig.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._parse_ymd` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1589 — Handles parse ymd for the utilities feature. Main detected dependency: __spina_logger.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._parse_any_adv_range` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3590 — Handles parse any adv range for the utilities feature. Main detected dependency: _ADV_PLAIN_RE.search.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._audit_parse_json_payload` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6835 — Handles audit parse json payload for the utilities feature. Main detected dependency: dict.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._audit_parse_date_filters` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:13871 — Handles audit parse date filters for the utilities feature. Main detected dependency: _dt.strptime.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._format_bytes` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:15535 — Handles format bytes for the utilities feature. Main detected dependency: float.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._parse_adv_range_any` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:26689 — Handles parse adv range any for the utilities feature. Main detected dependency: _ADV_PLAIN_RE.search.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._parse_reason_color_token` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:26732 — Extract a [RC:...] token (hex or a color-name) from the description. Returns: (color_hex or "", desc_without_token)
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_cashctl__fmt_money` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:37424 — Handles spina cashctl fmt money for the utilities feature. Main detected dependency: _spina_dash__fmt_money.
- `spina_app.area_hierarchy.normalize_area_segment` — spina_app/area_hierarchy.py:29 — Return a trimmed single Area node name with internal spaces collapsed.
- `spina_app.area_hierarchy.normalize_area_path` — spina_app/area_hierarchy.py:38 — Normalize spacing without changing a legacy Area's visible wording.
- `spina_app.area_hierarchy.format_area_path` — spina_app/area_hierarchy.py:47 — Join any number of Area levels into one unambiguous display path.
- `spina_app.area_hierarchy._path_key` — spina_app/area_hierarchy.py:53 — Handles path key for the utilities feature. Main detected dependency: normalize_area_path.
- `spina_app.area_hierarchy_ops._key` — spina_app/area_hierarchy_ops.py:29 — Handles key for the utilities feature. Main detected dependency: normalize_area_path.
- `spina_app.area_hierarchy_ops._planned_subtree` — spina_app/area_hierarchy_ops.py:158 — Handles planned subtree for the utilities feature. Main detected dependency: ValueError.
- `spina_app.ui_helpers._spina_v20_round_rect` — spina_app/ui_helpers.py:6 — Handles spina v20 round rect for the utilities feature. Main detected dependency: cv.create_polygon.
- `spina_app.ui_helpers._spina_v24_cilog_round_rect` — spina_app/ui_helpers.py:18 — Handles spina v24 cilog round rect for the utilities feature. Main detected dependency: cv.create_polygon.

### Batch 13: Utilities (276 lines)

Risk mix: `database_read`, `support`

- `tools.extract_cilog_value_formatter._node_source` — tools/extract_cilog_value_formatter.py:21 — Handles node source for the utilities feature. Main detected dependency: join.
- `tools.extract_cilog_value_formatter._top_level_function` — tools/extract_cilog_value_formatter.py:27 — Handles top level function for the utilities feature. Main detected dependency: RuntimeError.
- `tools.extract_cilog_value_formatter._local_names` — tools/extract_cilog_value_formatter.py:34 — Handles local names for the utilities feature. Main detected dependency: ast.walk.
- `tools.extract_cilog_value_formatter._validate` — tools/extract_cilog_value_formatter.py:48 — Handles validate for the utilities feature. Main detected dependency: RuntimeError.
- `tools.extract_cilog_value_formatter.build_plan` — tools/extract_cilog_value_formatter.py:63 — Builds build plan for the utilities feature. Main detected dependency: RuntimeError.
- `tools.extract_cilog_value_formatter.apply_extraction` — tools/extract_cilog_value_formatter.py:130 — Handles apply extraction for the utilities feature. Main detected dependency: _atomic_write.
- `tools.extract_date_display_helpers._line_source` — tools/extract_date_display_helpers.py:32 — Handles line source for the utilities feature. Main detected dependency: getattr.
- `tools.extract_date_display_helpers._top_level_functions` — tools/extract_date_display_helpers.py:40 — Handles top level functions for the utilities feature. Main detected dependency: RuntimeError.
- `tools.extract_date_display_helpers._local_names` — tools/extract_date_display_helpers.py:50 — Handles local names for the utilities feature. Main detected dependency: ast.walk.
- `tools.extract_date_display_helpers._external_loaded_names` — tools/extract_date_display_helpers.py:71 — Handles external loaded names for the utilities feature. Main detected dependency: _local_names.
- `tools.extract_date_display_helpers._validate_signature` — tools/extract_date_display_helpers.py:81 — Validates validate signature for the utilities feature. Main detected dependency: RuntimeError.
- `tools.extract_date_display_helpers._validate_existing_module` — tools/extract_date_display_helpers.py:87 — Validates validate existing module for the utilities feature. Main detected dependency: RuntimeError.
- `tools.extract_date_display_helpers._append_module_source` — tools/extract_date_display_helpers.py:108 — Handles append module source for the utilities feature. Main detected dependency: _line_source.
- `tools.extract_date_display_helpers._patched_source` — tools/extract_date_display_helpers.py:117 — Handles patched source for the utilities feature. Main detected dependency: functions.items.
- `tools.extract_date_display_helpers._state` — tools/extract_date_display_helpers.py:128 — Handles state for the utilities feature. Main detected dependency: IMPORT_LINES.items.
- `tools.extract_date_display_helpers.build_plan` — tools/extract_date_display_helpers.py:141 — Builds build plan for the utilities feature. Main detected dependency: RuntimeError.
- `tools.extract_date_display_helpers.apply_extraction` — tools/extract_date_display_helpers.py:223 — Handles apply extraction for the utilities feature. Main detected dependency: _atomic_write.
- `tools.extract_date_helpers_module._line_source` — tools/extract_date_helpers_module.py:34 — Handles line source for the utilities feature. Main detected dependency: getattr.

### Batch 14: Authentication (273 lines)

Risk mix: `database_read`, `support`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.pick_date_range` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1929 — Handles pick date range for the authentication feature. Main detected dependency: _CalendarRangePopup.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._users_db_path` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8911 — Handles users db path for the authentication feature. Main detected dependency: os.makedirs.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._setup_style` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:14779 — Centralized ttk styling. Goals: - cleaner spacing / typography - readable Treeviews - consistent Notebook tabs - best-effort HiDPI handling on Windows
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v32_selected_label_for_user` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:44428 — Handles spina v32 selected label for user for the authentication feature. Main detected dependency: label_to_user.get.
- `tools.cleanup_pure_login_dialog_ui_pass_only.ParentSetter.visit` — tools/cleanup_pure_login_dialog_ui_pass_only.py:93 — Handles visit for the authentication feature. Main detected dependency: ast.iter_child_nodes.
- `tools.cleanup_pure_login_dialog_ui_pass_only.node_name` — tools/cleanup_pure_login_dialog_ui_pass_only.py:99 — Handles node name for the authentication feature. Main detected dependency: isinstance.
- `tools.cleanup_pure_login_dialog_ui_pass_only.scope_for` — tools/cleanup_pure_login_dialog_ui_pass_only.py:105 — Handles scope for for the authentication feature. Main detected dependency: getattr.
- `tools.cleanup_pure_login_dialog_ui_pass_only.is_exception_handler` — tools/cleanup_pure_login_dialog_ui_pass_only.py:117 — Handles is exception handler for the authentication feature. Main detected dependency: isinstance.
- `tools.cleanup_pure_login_dialog_ui_pass_only.is_pass_only_handler` — tools/cleanup_pure_login_dialog_ui_pass_only.py:127 — Handles is pass only handler for the authentication feature. Main detected dependency: is_exception_handler.
- `tools.cleanup_pure_login_dialog_ui_pass_only.get_context` — tools/cleanup_pure_login_dialog_ui_pass_only.py:135 — Retrieves get context for the authentication feature. Main detected dependency: join.
- `tools.cleanup_pure_login_dialog_ui_pass_only.find_handlers` — tools/cleanup_pure_login_dialog_ui_pass_only.py:141 — Retrieves find handlers for the authentication feature. Main detected dependency: ParentSetter.
- `tools.plan_login_dialog_pass_only._read_text` — tools/plan_login_dialog_pass_only.py:95 — Handles read text for the authentication feature. Main detected dependency: path.read_text.
- `tools.plan_login_dialog_pass_only._handler_name` — tools/plan_login_dialog_pass_only.py:99 — Handles handler name for the authentication feature. Main detected dependency: ast.unparse.
- `tools.plan_login_dialog_pass_only._is_pass_only` — tools/plan_login_dialog_pass_only.py:108 — Handles is pass only for the authentication feature. Main detected dependency: isinstance.
- `tools.plan_login_dialog_pass_only._line_window` — tools/plan_login_dialog_pass_only.py:112 — Handles line window for the authentication feature. Main detected dependency: len.
- `tools.plan_login_dialog_pass_only._context_text` — tools/plan_login_dialog_pass_only.py:121 — Handles context text for the authentication feature. Main detected dependency: item.get.
- `tools.plan_login_dialog_pass_only._has_any` — tools/plan_login_dialog_pass_only.py:125 — Handles has any for the authentication feature. Main detected dependency: any.
- `tools.plan_login_dialog_pass_only.PassOnlyVisitor.__init__` — tools/plan_login_dialog_pass_only.py:131 — Handles init for the authentication feature.

### Batch 15: Utilities (273 lines)

Risk mix: `database_read`, `support`

- `tools.extract_fmt_currency_module._module_source` — tools/extract_fmt_currency_module.py:84 — Handles module source for the utilities feature. Main detected dependency: function_source.lstrip.
- `tools.extract_fmt_currency_module.build_plan` — tools/extract_fmt_currency_module.py:112 — Builds build plan for the utilities feature. Main detected dependency: RuntimeError.
- `tools.extract_fmt_currency_module.apply_extraction` — tools/extract_fmt_currency_module.py:156 — Handles apply extraction for the utilities feature. Main detected dependency: _atomic_write.
- `tools.extract_log_serialization_helper._source` — tools/extract_log_serialization_helper.py:20 — Handles source for the utilities feature. Main detected dependency: join.
- `tools.extract_log_serialization_helper._function` — tools/extract_log_serialization_helper.py:26 — Handles function for the utilities feature. Main detected dependency: RuntimeError.
- `tools.extract_log_serialization_helper._local_names` — tools/extract_log_serialization_helper.py:33 — Handles local names for the utilities feature. Main detected dependency: ast.walk.
- `tools.extract_log_serialization_helper._validate` — tools/extract_log_serialization_helper.py:47 — Handles validate for the utilities feature. Main detected dependency: RuntimeError.
- `tools.extract_log_serialization_helper.build_plan` — tools/extract_log_serialization_helper.py:62 — Builds build plan for the utilities feature. Main detected dependency: RuntimeError.
- `tools.extract_log_serialization_helper.apply` — tools/extract_log_serialization_helper.py:117 — Handles apply for the utilities feature. Main detected dependency: _write.
- `tools.extract_merge_note_dict.top_level_functions` — tools/extract_merge_note_dict.py:34 — Handles top level functions for the utilities feature. Main detected dependency: ast.parse.
- `tools.extract_merge_note_dict.validate_plan` — tools/extract_merge_note_dict.py:97 — Validates validate plan for the utilities feature. Main detected dependency: RuntimeError.
- `tools.extract_merge_note_dict.apply_extraction` — tools/extract_merge_note_dict.py:110 — Handles apply extraction for the utilities feature. Main detected dependency: APP_PATH.read_text.
- `tools.extract_note_dict_helper.top_level_functions` — tools/extract_note_dict_helper.py:33 — Handles top level functions for the utilities feature. Main detected dependency: ast.parse.
- `tools.extract_note_dict_helper.external_names` — tools/extract_note_dict_helper.py:38 — Handles external names for the utilities feature. Main detected dependency: ast.walk.
- `tools.extract_note_dict_helper.validate_plan` — tools/extract_note_dict_helper.py:98 — Validates validate plan for the utilities feature. Main detected dependency: RuntimeError.
- `tools.extract_note_dict_helper.apply_extraction` — tools/extract_note_dict_helper.py:112 — Handles apply extraction for the utilities feature. Main detected dependency: APP_PATH.read_text.
- `tools.extract_numeric_parsers._line_source` — tools/extract_numeric_parsers.py:31 — Handles line source for the utilities feature. Main detected dependency: getattr.
- `tools.extract_numeric_parsers._top_level_functions` — tools/extract_numeric_parsers.py:39 — Handles top level functions for the utilities feature. Main detected dependency: RuntimeError.

### Batch 16: Collectors (259 lines)

Risk mix: `database_read`, `support`, `ui_only`

- `spina_app.tabs.collectors._spina_v25_style_collector_trees` — spina_app/tabs/collectors.py:29 — Handles spina v25 style collector trees for the collectors feature. Main detected dependency: _spina_v25_collector_colors.
- `spina_app.tabs.collectors._collectors_get_selected_name` — spina_app/tabs/collectors.py:110 — Handles collectors get selected name for the collectors feature. Main detected dependency: getattr.
- `spina_app.tabs.collectors._collectors_toggle_sections` — spina_app/tabs/collectors.py:125 — Handles collectors toggle sections for the collectors feature. Main detected dependency: bool.
- `spina_app.tabs.collectors._collectors_refresh_bulk_bar` — spina_app/tabs/collectors.py:192 — Handles collectors refresh bulk bar for the collectors feature. Main detected dependency: bar.pack.
- `spina_app.tabs.collectors._collectors_clear_checked` — spina_app/tabs/collectors.py:218 — Handles collectors clear checked for the collectors feature. Main detected dependency: self._collectors_apply_markers.
- `spina_app.theme_palettes._spina_v25_collector_colors` — spina_app/theme_palettes.py:190 — Handles spina v25 collector colors for the collectors feature. Main detected dependency: getattr.
- `spina_app.ui_cards._spina_v27_route_card` — spina_app/ui_cards.py:41 — Handles spina v27 route card for the collectors feature. Main detected dependency: _spina_v27_route_colors.
- `spina_app.ui_controls._spina_v27_style_route_trees` — spina_app/ui_controls.py:132 — Handles spina v27 style route trees for the collectors feature. Main detected dependency: _spina_v27_route_colors.
- `spina_app.utilities.text._spina_route_notice_norm_name` — spina_app/utilities/text.py:16 — Handles spina route notice norm name for the collectors feature. Main detected dependency: re.sub.
- `tools.test_collector_route_card_batch_13.FakeWidget.__init__` — tools/test_collector_route_card_batch_13.py:41 — Handles init for the collectors feature. Main detected dependency: dict.
- `tools.test_collector_route_card_batch_13.FakeWidget.pack` — tools/test_collector_route_card_batch_13.py:50 — Handles pack for the collectors feature. Main detected dependency: dict.
- `tools.test_collector_route_card_batch_13._WidgetFactory.__init__` — tools/test_collector_route_card_batch_13.py:55 — Handles init for the collectors feature.
- `tools.test_collector_route_card_batch_13._WidgetFactory.__call__` — tools/test_collector_route_card_batch_13.py:58 — Handles call for the collectors feature. Main detected dependency: FakeWidget.
- `tools.test_collector_route_card_batch_13._route_palette` — tools/test_collector_route_card_batch_13.py:70 — Handles route palette for the collectors feature. Main detected dependency: RuntimeError.
- `tools.test_collector_route_card_batch_13._load_manifest` — tools/test_collector_route_card_batch_13.py:76 — Loads load manifest for the collectors feature. Main detected dependency: json.loads.
- `tools.test_collector_route_card_batch_13._source_function` — tools/test_collector_route_card_batch_13.py:80 — Handles source function for the collectors feature. Main detected dependency: RuntimeError.
- `tools.test_collector_route_card_batch_13._resolve_function` — tools/test_collector_route_card_batch_13.py:102 — Handles resolve function for the collectors feature. Main detected dependency: RuntimeError.
- `tools.test_collector_route_card_batch_13.capture_batch` — tools/test_collector_route_card_batch_13.py:164 — Handles capture batch for the collectors feature. Main detected dependency: RuntimeError.

### Batch 17: Payments (255 lines)

Risk mix: `database_read`, `support`, `ui_only`

- `spina_app.ui_helpers._spina_v17_set_card` — spina_app/ui_helpers.py:43 — Handles spina v17 set card for the payments feature. Main detected dependency: get.
- `spina_app.ui_helpers._spina_v24_cilog_set_card` — spina_app/ui_helpers.py:54 — Handles spina v24 cilog set card for the payments feature. Main detected dependency: get.
- `spina_app.ui_helpers._spina_v21_cash_set_card` — spina_app/ui_helpers.py:65 — Handles spina v21 cash set card for the payments feature. Main detected dependency: get.
- `spina_app.utilities.formatting._spina_crc_fmt_money` — spina_app/utilities/formatting.py:96 — Handles spina crc fmt money for the payments feature. Main detected dependency: abs.
- `spina_app.utilities.formatting._spina_dash__fmt_money` — spina_app/utilities/formatting.py:111 — Handles spina dash fmt money for the payments feature. Main detected dependency: callable.
- `spina_app.utilities.records._spina_perf_dict_rows` — spina_app/utilities/records.py:6 — Handles spina perf dict rows for the payments feature. Main detected dependency: dict.
- `tools.audit_bare_except_context.Visitor.visit_ExceptHandler` — tools/audit_bare_except_context.py:61 — Handles visit ExceptHandler for the payments feature. Main detected dependency: _ctx.
- `tools.audit_pass_only_exceptions._segment` — tools/audit_pass_only_exceptions.py:23 — Handles segment for the payments feature. Main detected dependency: join.
- `tools.audit_pass_only_exceptions._scope_name` — tools/audit_pass_only_exceptions.py:27 — Handles scope name for the payments feature. Main detected dependency: isinstance.
- `tools.audit_pass_only_exceptions._handler_name` — tools/audit_pass_only_exceptions.py:37 — Handles handler name for the payments feature. Main detected dependency: ast.unparse.
- `tools.audit_pass_only_exceptions._is_pass_only` — tools/audit_pass_only_exceptions.py:46 — Handles is pass only for the payments feature. Main detected dependency: isinstance.
- `tools.audit_pass_only_exceptions._protected` — tools/audit_pass_only_exceptions.py:50 — Handles protected for the payments feature. Main detected dependency: any.
- `tools.cleanup_logger_fallback_pass_only._line_text` — tools/cleanup_logger_fallback_pass_only.py:33 — Handles line text for the payments feature. Main detected dependency: len.
- `tools.cleanup_logger_fallback_pass_only._find_top_level_function` — tools/cleanup_logger_fallback_pass_only.py:39 — Retrieves find top level function for the payments feature. Main detected dependency: _line_text.
- `tools.cleanup_logger_fallback_pass_only._locate_target` — tools/cleanup_logger_fallback_pass_only.py:57 — Handles locate target for the payments feature. Main detected dependency: _find_top_level_function.
- `tools.cleanup_modern_ui_pass_only.context` — tools/cleanup_modern_ui_pass_only.py:49 — Handles context for the payments feature. Main detected dependency: len.
- `tools.cleanup_modern_ui_pass_only.has_protected_context` — tools/cleanup_modern_ui_pass_only.py:55 — Handles has protected context for the payments feature. Main detected dependency: any.
- `tools.cleanup_modern_ui_pass_only.inspect_target` — tools/cleanup_modern_ui_pass_only.py:60 — Handles inspect target for the payments feature. Main detected dependency: context.

### Batch 18: Utilities (252 lines)

Risk mix: `database_read`, `support`

- `tools.test_merge_note_dict_extraction.load_helper` — tools/test_merge_note_dict_extraction.py:50 — Loads load helper for the utilities feature. Main detected dependency: APP_PATH.read_text.
- `tools.test_merge_note_dict_extraction.validate_input_isolation` — tools/test_merge_note_dict_extraction.py:108 — Validates validate input isolation for the utilities feature. Main detected dependency: AssertionError.
- `tools.test_note_dict_helper_extraction.load_helper` — tools/test_note_dict_helper_extraction.py:38 — Loads load helper for the utilities feature. Main detected dependency: APP_PATH.read_text.
- `tools.test_note_dict_helper_extraction.capture_behavior` — tools/test_note_dict_helper_extraction.py:64 — Handles capture behavior for the utilities feature. Main detected dependency: fn.
- `tools.test_note_dict_helper_extraction.validate_copy_semantics` — tools/test_note_dict_helper_extraction.py:87 — Validates validate copy semantics for the utilities feature. Main detected dependency: AssertionError.
- `tools.test_numeric_parser_extraction._cases` — tools/test_numeric_parser_extraction.py:27 — Handles cases for the utilities feature.
- `tools.test_numeric_parser_extraction._validate_signature` — tools/test_numeric_parser_extraction.py:45 — Validates validate signature for the utilities feature. Main detected dependency: AssertionError.
- `tools.test_numeric_parser_extraction._capture` — tools/test_numeric_parser_extraction.py:66 — Handles capture for the utilities feature. Main detected dependency: function.
- `tools.test_numeric_parser_extraction._behavior` — tools/test_numeric_parser_extraction.py:82 — Handles behavior for the utilities feature. Main detected dependency: _capture.
- `tools.test_numeric_parser_extraction._functions_from_module_source` — tools/test_numeric_parser_extraction.py:93 — Handles functions from module source for the utilities feature. Main detected dependency: compile.
- `tools.test_numeric_parser_extraction._load_generated_functions` — tools/test_numeric_parser_extraction.py:99 — Loads load generated functions for the utilities feature. Main detected dependency: RuntimeError.
- `tools.test_numeric_parser_extraction._source_state` — tools/test_numeric_parser_extraction.py:108 — Handles source state for the utilities feature. Main detected dependency: IMPORT_LINES.items.
- `tools.test_numeric_parser_extraction._test_applied_state` — tools/test_numeric_parser_extraction.py:160 — Handles test applied state for the utilities feature. Main detected dependency: _behavior.
- `tools.test_numeric_parser_extraction.main` — tools/test_numeric_parser_extraction.py:180 — Handles main for the utilities feature. Main detected dependency: AssertionError.
- `tools.test_pure_helper_batch._load_manifest` — tools/test_pure_helper_batch.py:88 — Loads load manifest for the utilities feature. Main detected dependency: json.loads.
- `tools.test_pure_helper_batch._resolve_from_source` — tools/test_pure_helper_batch.py:92 — Handles resolve from source for the utilities feature. Main detected dependency: RuntimeError.
- `tools.test_pure_helper_batch._resolve_function` — tools/test_pure_helper_batch.py:111 — Handles resolve function for the utilities feature. Main detected dependency: RuntimeError.
- `tools.test_pure_helper_batch._type_name` — tools/test_pure_helper_batch.py:124 — Handles type name for the utilities feature. Main detected dependency: type.

### Batch 19: Utilities (248 lines)

Risk mix: `database_read`, `support`

- `tools.test_pure_helper_batch._capture` — tools/test_pure_helper_batch.py:129 — Handles capture for the utilities feature. Main detected dependency: _type_name.
- `tools.test_pure_helper_batch.capture_batch` — tools/test_pure_helper_batch.py:145 — Handles capture batch for the utilities feature. Main detected dependency: RuntimeError.
- `tools.test_text_normalizer_extraction._cases` — tools/test_text_normalizer_extraction.py:27 — Handles cases for the utilities feature.
- `tools.test_text_normalizer_extraction._validate_signature` — tools/test_text_normalizer_extraction.py:44 — Validates validate signature for the utilities feature. Main detected dependency: AssertionError.
- `tools.test_text_normalizer_extraction._capture` — tools/test_text_normalizer_extraction.py:67 — Handles capture for the utilities feature. Main detected dependency: function.
- `tools.test_text_normalizer_extraction._behavior` — tools/test_text_normalizer_extraction.py:83 — Handles behavior for the utilities feature. Main detected dependency: _capture.
- `tools.test_text_normalizer_extraction._functions_from_module_source` — tools/test_text_normalizer_extraction.py:94 — Handles functions from module source for the utilities feature. Main detected dependency: compile.
- `tools.test_text_normalizer_extraction._load_generated_functions` — tools/test_text_normalizer_extraction.py:100 — Loads load generated functions for the utilities feature. Main detected dependency: RuntimeError.
- `tools.test_text_normalizer_extraction._source_state` — tools/test_text_normalizer_extraction.py:109 — Handles source state for the utilities feature. Main detected dependency: IMPORT_LINES.items.
- `tools.test_text_normalizer_extraction._test_applied_state` — tools/test_text_normalizer_extraction.py:165 — Handles test applied state for the utilities feature. Main detected dependency: _behavior.
- `tools.test_text_normalizer_extraction.main` — tools/test_text_normalizer_extraction.py:185 — Handles main for the utilities feature. Main detected dependency: AssertionError.
- `tools.test_ui_card_constructor_batch_08._source_function` — tools/test_ui_card_constructor_batch_08.py:93 — Handles source function for the utilities feature. Main detected dependency: RuntimeError.
- `tools.test_ui_card_constructor_batch_08._resolve_function` — tools/test_ui_card_constructor_batch_08.py:116 — Handles resolve function for the utilities feature. Main detected dependency: RuntimeError.
- `tools.test_ui_card_constructor_batch_08.capture_batch` — tools/test_ui_card_constructor_batch_08.py:178 — Handles capture batch for the utilities feature. Main detected dependency: RuntimeError.
- `tools.test_ui_display_helper_batch.FakeCanvas.__init__` — tools/test_ui_display_helper_batch.py:37 — Handles init for the utilities feature.
- `tools.test_ui_display_helper_batch.FakeCanvas.create_polygon` — tools/test_ui_display_helper_batch.py:41 — Builds create polygon for the utilities feature. Main detected dependency: RuntimeError.
- `tools.test_ui_display_helper_batch.FakeCanvas.create_rectangle` — tools/test_ui_display_helper_batch.py:51 — Builds create rectangle for the utilities feature. Main detected dependency: _stable.
- `tools.test_ui_display_helper_batch.FakeLabel.__init__` — tools/test_ui_display_helper_batch.py:61 — Handles init for the utilities feature.

### Batch 20: Utilities (231 lines)

Risk mix: `database_read`, `support`

- `spina_app.utilities.notes._append_unique_text` — spina_app/utilities/notes.py:15 — Handles append unique text for the utilities feature. Main detected dependency: strip.
- `spina_app.utilities.notes._merge_note_dict` — spina_app/utilities/notes.py:28 — Merge src into dst without losing data; if conflicts, append text uniquely.
- `spina_app.utilities.numbers._spina_v27_count_from_text` — spina_app/utilities/numbers.py:15 — Handles spina v27 count from text for the utilities feature. Main detected dependency: int.
- `spina_app.utilities.numbers._spina_v25_parse_count_from_var` — spina_app/utilities/numbers.py:23 — Handles spina v25 parse count from var for the utilities feature. Main detected dependency: m.group.
- `spina_app.utilities.numbers._spina_cashctl__int_range` — spina_app/utilities/numbers.py:40 — Handles spina cashctl int range for the utilities feature. Main detected dependency: _spina_cashctl__parse_amount.
- `spina_app.utilities.serialization._spina_cilog_safe_json` — spina_app/utilities/serialization.py:7 — Handles spina cilog safe json for the utilities feature. Main detected dependency: isinstance.
- `spina_app.utilities.text._oslp__norm_area_name` — spina_app/utilities/text.py:7 — Handles oslp norm area name for the utilities feature. Main detected dependency: join.
- `spina_app.utilities.text._spina_crc_norm_text` — spina_app/utilities/text.py:10 — Handles spina crc norm text for the utilities feature. Main detected dependency: re.sub.
- `tools.audit_dynamic_sql_context.safe_unparse` — tools/audit_dynamic_sql_context.py:51 — Handles safe unparse for the utilities feature. Main detected dependency: ast.unparse.
- `tools.audit_dynamic_sql_context.call_name` — tools/audit_dynamic_sql_context.py:64 — Handles call name for the utilities feature. Main detected dependency: isinstance.
- `tools.audit_dynamic_sql_context.classify_risk` — tools/audit_dynamic_sql_context.py:137 — Handles classify risk for the utilities feature. Main detected dependency: any.
- `tools.audit_legacy_callback_usage.function_ranges` — tools/audit_legacy_callback_usage.py:58 — Return {(class_name, function_name): (start_line, end_line)}.
- `tools.extract_append_unique_text.top_level_functions` — tools/extract_append_unique_text.py:33 — Handles top level functions for the utilities feature. Main detected dependency: ast.parse.
- `tools.extract_append_unique_text.validate_plan` — tools/extract_append_unique_text.py:87 — Validates validate plan for the utilities feature. Main detected dependency: RuntimeError.
- `tools.extract_append_unique_text.apply_extraction` — tools/extract_append_unique_text.py:101 — Handles apply extraction for the utilities feature. Main detected dependency: APP_PATH.read_text.
- `tools.extract_cilog_action_label.build_plan` — tools/extract_cilog_action_label.py:56 — Builds build plan for the utilities feature. Main detected dependency: RuntimeError.
- `tools.extract_cilog_diff_pairs._function_matches` — tools/extract_cilog_diff_pairs.py:33 — Handles function matches for the utilities feature. Main detected dependency: ast.parse.
- `tools.extract_cilog_diff_pairs._validate_node` — tools/extract_cilog_diff_pairs.py:59 — Validates validate node for the utilities feature. Main detected dependency: RuntimeError.

### Batch 21: Utilities (229 lines)

Risk mix: `database_read`, `support`

- `tools.test_cilog_money_formatter_extraction._module_function` — tools/test_cilog_money_formatter_extraction.py:80 — Handles module function for the utilities feature. Main detected dependency: RuntimeError.
- `tools.test_cilog_money_formatter_extraction.main` — tools/test_cilog_money_formatter_extraction.py:106 — Handles main for the utilities feature. Main detected dependency: AssertionError.
- `tools.test_cilog_ui_controls_batch_10._source_function` — tools/test_cilog_ui_controls_batch_10.py:103 — Handles source function for the utilities feature. Main detected dependency: RuntimeError.
- `tools.test_cilog_ui_controls_batch_10._resolve_function` — tools/test_cilog_ui_controls_batch_10.py:126 — Handles resolve function for the utilities feature. Main detected dependency: RuntimeError.
- `tools.test_cilog_value_formatter_extraction._capture` — tools/test_cilog_value_formatter_extraction.py:50 — Handles capture for the utilities feature. Main detected dependency: function.
- `tools.test_cilog_value_formatter_extraction._behavior` — tools/test_cilog_value_formatter_extraction.py:66 — Handles behavior for the utilities feature. Main detected dependency: AssertionError.
- `tools.test_cilog_value_formatter_extraction._load_module` — tools/test_cilog_value_formatter_extraction.py:76 — Loads load module for the utilities feature. Main detected dependency: RuntimeError.
- `tools.test_cilog_value_formatter_extraction._source_state` — tools/test_cilog_value_formatter_extraction.py:85 — Handles source state for the utilities feature. Main detected dependency: any.
- `tools.test_cilog_value_formatter_extraction._legacy_function` — tools/test_cilog_value_formatter_extraction.py:113 — Handles legacy function for the utilities feature. Main detected dependency: _load_module.
- `tools.test_cilog_value_formatter_extraction._test_applied` — tools/test_cilog_value_formatter_extraction.py:151 — Handles test applied for the utilities feature. Main detected dependency: _behavior.
- `tools.test_cilog_value_formatter_extraction.main` — tools/test_cilog_value_formatter_extraction.py:169 — Handles main for the utilities feature. Main detected dependency: AssertionError.
- `tools.test_date_display_helper_extraction._cases` — tools/test_date_display_helper_extraction.py:28 — Handles cases for the utilities feature. Main detected dependency: date.
- `tools.test_date_display_helper_extraction._validate_signature` — tools/test_date_display_helper_extraction.py:44 — Validates validate signature for the utilities feature. Main detected dependency: AssertionError.
- `tools.test_date_display_helper_extraction._capture` — tools/test_date_display_helper_extraction.py:60 — Handles capture for the utilities feature. Main detected dependency: function.
- `tools.test_date_display_helper_extraction._behavior` — tools/test_date_display_helper_extraction.py:76 — Handles behavior for the utilities feature. Main detected dependency: _capture.
- `tools.test_date_display_helper_extraction._load_dates_module` — tools/test_date_display_helper_extraction.py:87 — Loads load dates module for the utilities feature. Main detected dependency: RuntimeError.
- `tools.test_date_display_helper_extraction._legacy_functions` — tools/test_date_display_helper_extraction.py:96 — Handles legacy functions for the utilities feature. Main detected dependency: _load_dates_module.
- `tools.test_date_display_helper_extraction._generated_functions` — tools/test_date_display_helper_extraction.py:106 — Handles generated functions for the utilities feature. Main detected dependency: _load_dates_module.

### Batch 22: Utilities (228 lines)

Risk mix: `database_read`, `support`

- `tools.test_display_ui_helper_batch_04._stable` — tools/test_display_ui_helper_batch_04.py:66 — Handles stable for the utilities feature. Main detected dependency: _stable.
- `tools.test_display_ui_helper_batch_04._type_name` — tools/test_display_ui_helper_batch_04.py:76 — Handles type name for the utilities feature. Main detected dependency: type.
- `tools.test_display_ui_helper_batch_04._load_manifest` — tools/test_display_ui_helper_batch_04.py:81 — Loads load manifest for the utilities feature. Main detected dependency: json.loads.
- `tools.test_display_ui_helper_batch_04._source_namespace` — tools/test_display_ui_helper_batch_04.py:85 — Handles source namespace for the utilities feature. Main detected dependency: importlib.import_module.
- `tools.test_display_ui_helper_batch_04._resolve_from_source` — tools/test_display_ui_helper_batch_04.py:94 — Handles resolve from source for the utilities feature. Main detected dependency: RuntimeError.
- `tools.test_display_ui_helper_batch_04._resolve_function` — tools/test_display_ui_helper_batch_04.py:113 — Handles resolve function for the utilities feature. Main detected dependency: RuntimeError.
- `tools.test_display_ui_helper_batch_04._capture_call` — tools/test_display_ui_helper_batch_04.py:126 — Handles capture call for the utilities feature. Main detected dependency: _type_name.
- `tools.test_display_ui_helper_batch_04._capture_card` — tools/test_display_ui_helper_batch_04.py:134 — Handles capture card for the utilities feature. Main detected dependency: FakeLabel.
- `tools.test_display_ui_helper_batch_04.capture_batch` — tools/test_display_ui_helper_batch_04.py:178 — Handles capture batch for the utilities feature. Main detected dependency: RuntimeError.
- `tools.test_fmt_currency_extraction.main` — tools/test_fmt_currency_extraction.py:33 — Handles main for the utilities feature. Main detected dependency: _capture.
- `tools.test_log_serialization_helper_extraction._cases` — tools/test_log_serialization_helper_extraction.py:20 — Handles cases for the utilities feature.
- `tools.test_log_serialization_helper_extraction._capture` — tools/test_log_serialization_helper_extraction.py:36 — Handles capture for the utilities feature. Main detected dependency: function.
- `tools.test_log_serialization_helper_extraction._behavior` — tools/test_log_serialization_helper_extraction.py:52 — Handles behavior for the utilities feature. Main detected dependency: AssertionError.
- `tools.test_log_serialization_helper_extraction._load_module` — tools/test_log_serialization_helper_extraction.py:59 — Loads load module for the utilities feature. Main detected dependency: RuntimeError.
- `tools.test_log_serialization_helper_extraction._source_state` — tools/test_log_serialization_helper_extraction.py:68 — Handles source state for the utilities feature. Main detected dependency: any.
- `tools.test_log_serialization_helper_extraction._applied` — tools/test_log_serialization_helper_extraction.py:118 — Handles applied for the utilities feature. Main detected dependency: _behavior.
- `tools.test_log_serialization_helper_extraction.main` — tools/test_log_serialization_helper_extraction.py:132 — Handles main for the utilities feature. Main detected dependency: AssertionError.
- `tools.test_merge_note_dict_extraction.load_notes_module` — tools/test_merge_note_dict_extraction.py:41 — Loads load notes module for the utilities feature. Main detected dependency: RuntimeError.

### Batch 23: Payments (215 lines)

Risk mix: `database_read`, `support`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_normalize_value` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:544 — Convert PostgreSQL-returned values into SQLite-like values.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._PgCompatConnection.in_transaction` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:858 — Handles in transaction for the payments feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_raise_sqlite_like` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:887 — Raise sqlite3-style exceptions so existing catch blocks still work.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina__merge_payment_mode` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1172 — Handles spina merge payment mode for the payments feature. Main detected dependency: _spina__split_payment_mode.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._log_ignored` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1336 — Log an otherwise-ignored exception once per key (to avoid log spam).
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._CalendarPopup._close` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1723 — Handles close for the payments feature. Main detected dependency: _log_suppressed_once.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._CalendarRangePopup._render` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1822 — Handles render for the payments feature. Main detected dependency: _log_suppressed_once.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._CalendarRangePopup._close` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1921 — Handles close for the payments feature. Main detected dependency: _log_suppressed_once.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.pick_date` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1974 — Handles pick date for the payments feature. Main detected dependency: _CalendarPopup.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._candidate_note_keys` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:2296 — Handles candidate note keys for the payments feature. Main detected dependency: _log_suppressed_once.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._resolve_note_key` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:2313 — Return an existing key in notes_dict matching 'name' using _candidate_note_keys. If none found, default to the original name.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.NoteEditorDialog._set_dirty` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3104 — Updates set dirty for the payments feature. Main detected dependency: _log_suppressed_once.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.NoteEditorDialog._validate_date_or_warn` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3123 — Validates validate date or warn for the payments feature. Main detected dependency: _log_suppressed_once.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.NoteEditorDialog._auto_choose_scope` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3138 — Handles auto choose scope for the payments feature. Main detected dependency: _log_suppressed_once.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.NoteEditorDialog._focus_search` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3163 — Handles focus search for the payments feature. Main detected dependency: _log_suppressed_once.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.NoteEditorDialog._pick_date` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3360 — Handles pick date for the payments feature. Main detected dependency: _log_suppressed_once.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.NoteEditorDialog._jump_today` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3370 — Handles jump today for the payments feature. Main detected dependency: _log_suppressed_once.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.NoteEditorDialog._on_text_modified` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3530 — Handles on text modified for the payments feature. Main detected dependency: _log_suppressed_once.

### Batch 24: Utilities (211 lines)

Risk mix: `database_read`, `support`

- `tools.test_date_display_helper_extraction._source_state` — tools/test_date_display_helper_extraction.py:111 — Handles source state for the utilities feature. Main detected dependency: IMPORT_LINES.items.
- `tools.test_date_display_helper_extraction._test_applied_state` — tools/test_date_display_helper_extraction.py:180 — Handles test applied state for the utilities feature. Main detected dependency: _behavior.
- `tools.test_date_display_helper_extraction.main` — tools/test_date_display_helper_extraction.py:201 — Handles main for the utilities feature. Main detected dependency: AssertionError.
- `tools.test_date_helpers_extraction._cases` — tools/test_date_helpers_extraction.py:34 — Handles cases for the utilities feature. Main detected dependency: date.
- `tools.test_date_helpers_extraction._validate_signature` — tools/test_date_helpers_extraction.py:50 — Validates validate signature for the utilities feature. Main detected dependency: AssertionError.
- `tools.test_date_helpers_extraction._capture` — tools/test_date_helpers_extraction.py:73 — Handles capture for the utilities feature. Main detected dependency: date.today.
- `tools.test_date_helpers_extraction._behavior` — tools/test_date_helpers_extraction.py:92 — Handles behavior for the utilities feature. Main detected dependency: _capture.
- `tools.test_date_helpers_extraction._functions_from_module_source` — tools/test_date_helpers_extraction.py:103 — Handles functions from module source for the utilities feature. Main detected dependency: compile.
- `tools.test_date_helpers_extraction._load_generated_functions` — tools/test_date_helpers_extraction.py:109 — Loads load generated functions for the utilities feature. Main detected dependency: RuntimeError.
- `tools.test_date_helpers_extraction._source_state` — tools/test_date_helpers_extraction.py:118 — Handles source state for the utilities feature. Main detected dependency: IMPORT_LINES.items.
- `tools.test_date_helpers_extraction._test_applied_state` — tools/test_date_helpers_extraction.py:174 — Handles test applied state for the utilities feature. Main detected dependency: _behavior.
- `tools.test_date_helpers_extraction.main` — tools/test_date_helpers_extraction.py:201 — Handles main for the utilities feature. Main detected dependency: AssertionError.
- `tools.test_display_data_helper_batch.PairRow.__iter__` — tools/test_display_data_helper_batch.py:27 — Handles iter for the utilities feature. Main detected dependency: iter.
- `tools.test_display_data_helper_batch.FlakyKeysRow.__init__` — tools/test_display_data_helper_batch.py:32 — Handles init for the utilities feature.
- `tools.test_display_data_helper_batch.FlakyKeysRow.keys` — tools/test_display_data_helper_batch.py:36 — Handles keys for the utilities feature. Main detected dependency: RuntimeError.
- `tools.test_display_data_helper_batch.FlakyKeysRow.__getitem__` — tools/test_display_data_helper_batch.py:42 — Handles getitem for the utilities feature.
- `tools.test_display_data_helper_batch.BadRow.__iter__` — tools/test_display_data_helper_batch.py:47 — Handles iter for the utilities feature. Main detected dependency: RuntimeError.
- `tools.test_display_data_helper_batch.BadRow.keys` — tools/test_display_data_helper_batch.py:50 — Handles keys for the utilities feature. Main detected dependency: RuntimeError.

### Batch 25: Dashboard (206 lines)

Risk mix: `database_read`, `support`

- `tools.test_cash_control_ui_controls_batch_09.capture_batch` — tools/test_cash_control_ui_controls_batch_09.py:216 — Handles capture batch for the dashboard feature. Main detected dependency: RuntimeError.
- `tools.test_cilog_ui_controls_batch_10._widget_summary` — tools/test_cilog_ui_controls_batch_10.py:143 — Handles widget summary for the dashboard feature. Main detected dependency: _widget_summary.
- `tools.test_cilog_ui_controls_batch_10._capture_button` — tools/test_cilog_ui_controls_batch_10.py:151 — Handles capture button for the dashboard feature. Main detected dependency: FakeWidget.
- `tools.test_collector_route_card_batch_13._widget_summary` — tools/test_collector_route_card_batch_13.py:118 — Handles widget summary for the dashboard feature. Main detected dependency: _widget_summary.
- `tools.test_collector_route_card_batch_13._capture` — tools/test_collector_route_card_batch_13.py:127 — Handles capture for the dashboard feature. Main detected dependency: FakeWidget.
- `tools.test_collectors_summary_wave_22.source_for` — tools/test_collectors_summary_wave_22.py:19 — Handles source for for the dashboard feature. Main detected dependency: join.
- `tools.test_dashboard_feature_wave_17.Var.__init__` — tools/test_dashboard_feature_wave_17.py:23 — Handles init for the dashboard feature.
- `tools.test_dashboard_feature_wave_17.Var.get` — tools/test_dashboard_feature_wave_17.py:26 — Handles get for the dashboard feature.
- `tools.test_dashboard_feature_wave_17.Var.set` — tools/test_dashboard_feature_wave_17.py:29 — Handles set for the dashboard feature.
- `tools.test_dashboard_feature_wave_17._functions` — tools/test_dashboard_feature_wave_17.py:33 — Handles functions for the dashboard feature. Main detected dependency: ast.parse.
- `tools.test_dashboard_feature_wave_17.verify_static_extraction` — tools/test_dashboard_feature_wave_17.py:43 — Handles verify static extraction for the dashboard feature. Main detected dependency: MANIFEST.read_text.
- `tools.test_dashboard_feature_wave_17.verify_refresh_bridge` — tools/test_dashboard_feature_wave_17.py:100 — Handles verify refresh bridge for the dashboard feature. Main detected dependency: RuntimeError.
- `tools.test_dashboard_visibility_wave_24.source_for` — tools/test_dashboard_visibility_wave_24.py:17 — Handles source for for the dashboard feature. Main detected dependency: join.
- `tools.test_dashboard_visibility_wave_24.Var.__init__` — tools/test_dashboard_visibility_wave_24.py:22 — Handles init for the dashboard feature.
- `tools.test_dashboard_visibility_wave_24.Var.get` — tools/test_dashboard_visibility_wave_24.py:25 — Handles get for the dashboard feature.
- `tools.test_dashboard_visibility_wave_24.make_dummy` — tools/test_dashboard_visibility_wave_24.py:41 — Handles make dummy for the dashboard feature. Main detected dependency: Dummy.
- `tools.test_legacy_dashboard_card_batch_16.FakeWidget.__init__` — tools/test_legacy_dashboard_card_batch_16.py:41 — Handles init for the dashboard feature. Main detected dependency: dict.
- `tools.test_legacy_dashboard_card_batch_16.FakeWidget.pack` — tools/test_legacy_dashboard_card_batch_16.py:51 — Handles pack for the dashboard feature. Main detected dependency: dict.

### Batch 26: Other (206 lines)

Risk mix: `database_read`, `support`, `ui_only`

- `spina_app.area_hierarchy_ops.active_area_paths` — spina_app/area_hierarchy_ops.py:417 — Return active hierarchy paths in tree order for legacy dropdowns.
- `spina_app.area_hierarchy_ui._connection` — spina_app/area_hierarchy_ui.py:21 — Handles connection for the other feature. Main detected dependency: RuntimeError.
- `spina_app.area_hierarchy_ui._tree_visible_uids` — spina_app/area_hierarchy_ui.py:55 — Handles tree visible uids for the other feature. Main detected dependency: by_uid.get.
- `spina_app.area_hierarchy_ui._folder_text` — spina_app/area_hierarchy_ui.py:71 — Handles folder text for the other feature. Main detected dependency: str.
- `spina_app.area_hierarchy_ui._refresh_folder_icons` — spina_app/area_hierarchy_ui.py:92 — Refreshes refresh folder icons for the other feature. Main detected dependency: _folder_text.
- `spina_app.area_hierarchy_ui._set_all_folders` — spina_app/area_hierarchy_ui.py:104 — Updates set all folders for the other feature. Main detected dependency: str.
- `spina_app.area_hierarchy_ui.select_area_for_variable` — spina_app/area_hierarchy_ui.py:290 — Handles select area for variable for the other feature. Main detected dependency: node.get.
- `spina_app.ui_cards._spina_v21_cash_card` — spina_app/ui_cards.py:15 — Handles spina v21 cash card for the other feature. Main detected dependency: _spina_v21_cash_colors.
- `spina_app.ui_cards._spina_v24_cilog_card` — spina_app/ui_cards.py:28 — Handles spina v24 cilog card for the other feature. Main detected dependency: _spina_v24_cilog_colors.
- `spina_app.ui_cards._spina_v17_make_card` — spina_app/ui_cards.py:54 — Handles spina v17 make card for the other feature. Main detected dependency: _spina_v17_dash_colors.
- `spina_app.ui_controls._spina_v21_build_labeled_entry` — spina_app/ui_controls.py:17 — Handles spina v21 build labeled entry for the other feature. Main detected dependency: _spina_v21_cash_colors.
- `spina_app.ui_controls._spina_v24_cilog_button` — spina_app/ui_controls.py:51 — Handles spina v24 cilog button for the other feature. Main detected dependency: _spina_v24_cilog_colors.
- `tools.add_optional_performance_logs.remove_existing_block` — tools/add_optional_performance_logs.py:117 — Removes remove existing block for the other feature. Main detected dependency: SystemExit.
- `tools.apply_hierarchical_area_storage_phase1.inspect` — tools/apply_hierarchical_area_storage_phase1.py:45 — Handles inspect for the other feature. Main detected dependency: APP.read_text.
- `tools.apply_hierarchical_area_ui_phase2._between` — tools/apply_hierarchical_area_ui_phase2.py:23 — Handles between for the other feature. Main detected dependency: RuntimeError.
- `tools.apply_hierarchical_area_ui_phase2.inspect` — tools/apply_hierarchical_area_ui_phase2.py:33 — Handles inspect for the other feature. Main detected dependency: RuntimeError.
- `tools.audit_bare_except_context._lines` — tools/audit_bare_except_context.py:23 — Handles lines for the other feature. Main detected dependency: path.read_text.
- `tools.audit_bare_except_context._ctx` — tools/audit_bare_except_context.py:27 — Handles ctx for the other feature. Main detected dependency: len.

### Batch 27: Other (203 lines)

Risk mix: `database_read`, `support`

- `tools.plan_module_separation._dependency_signals` — tools/plan_module_separation.py:99 — Handles dependency signals for the other feature. Main detected dependency: DEPENDENCY_PATTERNS.items.
- `tools.plan_module_separation._is_protected` — tools/plan_module_separation.py:103 — Handles is protected for the other feature. Main detected dependency: any.
- `tools.plan_module_separation._top_level_assignments` — tools/plan_module_separation.py:142 — Handles top level assignments for the other feature. Main detected dependency: ast.walk.
- `tools.plan_module_separation._imports` — tools/plan_module_separation.py:157 — Handles imports for the other feature. Main detected dependency: isinstance.
- `tools.plan_module_separation._record_definition` — tools/plan_module_separation.py:167 — Handles record definition for the other feature. Main detected dependency: _called_names.
- `tools.spina_quality_audit._name` — tools/spina_quality_audit.py:60 — Handles name for the other feature. Main detected dependency: _name.
- `tools.spina_quality_audit._line_span` — tools/spina_quality_audit.py:73 — Handles line span for the other feature. Main detected dependency: getattr.
- `tools.spina_quality_audit._risk_area` — tools/spina_quality_audit.py:95 — Handles risk area for the other feature. Main detected dependency: RISK_AREA_KEYWORDS.items.
- `tools.spina_quality_audit._handler_has_visible_action` — tools/spina_quality_audit.py:103 — Handles handler has visible action for the other feature. Main detected dependency: _name.
- `tools.spina_startup_diagnostics._env` — tools/spina_startup_diagnostics.py:23 — Handles env for the other feature. Main detected dependency: os.environ.get.
- `tools.spina_startup_diagnostics.check_psycopg` — tools/spina_startup_diagnostics.py:46 — Handles check psycopg for the other feature. Main detected dependency: CheckResult.
- `tools.test_append_unique_text_extraction.capture_behavior` — tools/test_append_unique_text_extraction.py:62 — Handles capture behavior for the other feature. Main detected dependency: fn.
- `tools.test_ci_acceleration.exact_head_guard` — tools/test_ci_acceleration.py:13 — Handles exact head guard for the other feature. Main detected dependency: bool.
- `tools.test_cilog_action_label_extraction._capture` — tools/test_cilog_action_label_extraction.py:37 — Handles capture for the other feature. Main detected dependency: function.
- `tools.test_cilog_action_label_extraction._behavior` — tools/test_cilog_action_label_extraction.py:53 — Handles behavior for the other feature. Main detected dependency: AssertionError.
- `tools.test_cilog_action_label_extraction._applied` — tools/test_cilog_action_label_extraction.py:125 — Handles applied for the other feature. Main detected dependency: _behavior.
- `tools.test_cilog_diff_pairs_extraction._cases` — tools/test_cilog_diff_pairs_extraction.py:40 — Handles cases for the other feature.
- `tools.test_cilog_diff_pairs_extraction._capture` — tools/test_cilog_diff_pairs_extraction.py:59 — Handles capture for the other feature. Main detected dependency: _cases.

### Batch 28: Data Bank (198 lines)

Risk mix: `support`, `ui_only`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.is_databank_day_closed` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7070 — Handles is databank day closed for the data bank feature. Main detected dependency: bool.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._get_databank_focus_date` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:9961 — Retrieves get databank focus date for the data bank feature. Main detected dependency: __spina_logger.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._system_data_get_date` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:10003 — Handles system data get date for the data bank feature. Main detected dependency: _dt.strptime.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._system_data_use_focus_date` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:10023 — Handles system data use focus date for the data bank feature. Main detected dependency: _log_suppressed_once.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._system_data_open_history` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:10105 — Handles system data open history for the data bank feature. Main detected dependency: self._system_data_get_date.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._system_data_open_records` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:10111 — Handles system data open records for the data bank feature. Main detected dependency: self._system_data_get_date.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._locate_data_tree` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:13229 — Find and memoize the actual Treeview used by the Data grid.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.goto_current_month` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:16858 — Handles goto current month for the data bank feature. Main detected dependency: date.today.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.prev_month` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:16863 — Handles prev month for the data bank feature. Main detected dependency: self._month_label.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.next_month` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:16867 — Handles next month for the data bank feature. Main detected dependency: self._month_label.
- `tools.cleanup_databank_export_callbacks._line_indent` — tools/cleanup_databank_export_callbacks.py:45 — Handles line indent for the data bank feature. Main detected dependency: len.
- `tools.cleanup_databank_export_callbacks._is_decorator` — tools/cleanup_databank_export_callbacks.py:49 — Handles is decorator for the data bank feature. Main detected dependency: line.lstrip.
- `tools.cleanup_databank_export_callbacks._find_function_ranges` — tools/cleanup_databank_export_callbacks.py:53 — Return 0-based inclusive/exclusive ranges for a function definition. Each result is (start_index, end_index, indent).
- `tools.cleanup_databank_export_callbacks._inside_any` — tools/cleanup_databank_export_callbacks.py:93 — Handles inside any for the data bank feature. Main detected dependency: any.
- `tools.cleanup_databank_export_callbacks._looks_like_string_reference` — tools/cleanup_databank_export_callbacks.py:97 — Handles looks like string reference for the data bank feature. Main detected dependency: any.
- `tools.cleanup_databank_export_callbacks._is_stale_cleanup_reference` — tools/cleanup_databank_export_callbacks.py:111 — Return True only for harmless generated cleanup/hide-block references.
- `tools.cleanup_databank_export_callbacks._external_references` — tools/cleanup_databank_export_callbacks.py:122 — Handles external references for the data bank feature. Main detected dependency: _inside_any.
- `tools.cleanup_databank_export_callbacks._remove_ranges` — tools/cleanup_databank_export_callbacks.py:144 — Removes remove ranges for the data bank feature. Main detected dependency: enumerate.

### Batch 29: Other (198 lines)

Risk mix: `support`

- `tools.audit_pg_command_callers._function_record` — tools/audit_pg_command_callers.py:85 — Handles function record for the other feature. Main detected dependency: _contains_name.
- `tools.audit_shadowed_definitions._indent_width` — tools/audit_shadowed_definitions.py:52 — Handles indent width for the other feature. Main detected dependency: len.
- `tools.audit_shadowed_definitions._context` — tools/audit_shadowed_definitions.py:56 — Handles context for the other feature. Main detected dependency: join.
- `tools.audit_shadowed_definitions._has_protected_context` — tools/audit_shadowed_definitions.py:62 — Handles has protected context for the other feature. Main detected dependency: _context.
- `tools.audit_shadowed_definitions._entry` — tools/audit_shadowed_definitions.py:67 — Handles entry for the other feature. Main detected dependency: _has_protected_context.
- `tools.audit_silent_ui_errors._indent_width` — tools/audit_silent_ui_errors.py:71 — Handles indent width for the other feature. Main detected dependency: len.
- `tools.audit_silent_ui_errors._line_context` — tools/audit_silent_ui_errors.py:75 — Handles line context for the other feature. Main detected dependency: join.
- `tools.audit_silent_ui_errors._has_any` — tools/audit_silent_ui_errors.py:81 — Handles has any for the other feature. Main detected dependency: any.
- `tools.audit_silent_ui_errors._body_range` — tools/audit_silent_ui_errors.py:86 — Return 0-based [start, end) body range for an except block.
- `tools.audit_silent_ui_errors._body_is_silent` — tools/audit_silent_ui_errors.py:103 — Handles body is silent for the other feature. Main detected dependency: all.
- `tools.audit_silent_ui_errors._scan_def_context` — tools/audit_silent_ui_errors.py:122 — Build a simple per-line function/class context map.
- `tools.audit_silent_ui_errors.audit` — tools/audit_silent_ui_errors.py:151 — Handles audit for the other feature. Main detected dependency: EXCEPT_RE.match.
- `tools.cleanup_neutral_appclass_init_patch._indent_width` — tools/cleanup_neutral_appclass_init_patch.py:45 — Handles indent width for the other feature. Main detected dependency: len.
- `tools.cleanup_pg_json_read_dynamic_sql._line_number` — tools/cleanup_pg_json_read_dynamic_sql.py:40 — Handles line number for the other feature. Main detected dependency: enumerate.
- `tools.cleanup_pg_json_read_dynamic_sql._slice_context` — tools/cleanup_pg_json_read_dynamic_sql.py:47 — Handles slice context for the other feature. Main detected dependency: len.
- `tools.cleanup_pg_json_read_dynamic_sql._function_block` — tools/cleanup_pg_json_read_dynamic_sql.py:55 — Handles function block for the other feature. Main detected dependency: len.
- `tools.extract_append_unique_text.external_names` — tools/extract_append_unique_text.py:38 — Handles external names for the other feature. Main detected dependency: ast.walk.
- `tools.extract_cilog_action_label._local_names` — tools/extract_cilog_action_label.py:20 — Handles local names for the other feature. Main detected dependency: ast.walk.

### Batch 30: Utilities (198 lines)

Risk mix: `database_read`, `support`

- `tools.test_display_data_helper_batch.BadRow.__getitem__` — tools/test_display_data_helper_batch.py:53 — Handles getitem for the utilities feature. Main detected dependency: KeyError.
- `tools.test_display_data_helper_batch._load_manifest` — tools/test_display_data_helper_batch.py:114 — Loads load manifest for the utilities feature. Main detected dependency: json.loads.
- `tools.test_display_data_helper_batch._resolve_from_source` — tools/test_display_data_helper_batch.py:118 — Handles resolve from source for the utilities feature. Main detected dependency: RuntimeError.
- `tools.test_display_data_helper_batch._resolve_function` — tools/test_display_data_helper_batch.py:137 — Handles resolve function for the utilities feature. Main detected dependency: RuntimeError.
- `tools.test_display_data_helper_batch._type_name` — tools/test_display_data_helper_batch.py:150 — Handles type name for the utilities feature. Main detected dependency: type.
- `tools.test_display_data_helper_batch._capture` — tools/test_display_data_helper_batch.py:155 — Handles capture for the utilities feature. Main detected dependency: _type_name.
- `tools.test_display_data_helper_batch.capture_batch` — tools/test_display_data_helper_batch.py:171 — Handles capture batch for the utilities feature. Main detected dependency: RuntimeError.
- `tools.test_display_formatter_extraction._cases` — tools/test_display_formatter_extraction.py:27 — Handles cases for the utilities feature.
- `tools.test_display_formatter_extraction._validate_signature` — tools/test_display_formatter_extraction.py:43 — Validates validate signature for the utilities feature. Main detected dependency: AssertionError.
- `tools.test_display_formatter_extraction._capture` — tools/test_display_formatter_extraction.py:64 — Handles capture for the utilities feature. Main detected dependency: function.
- `tools.test_display_formatter_extraction._behavior` — tools/test_display_formatter_extraction.py:80 — Handles behavior for the utilities feature. Main detected dependency: _capture.
- `tools.test_display_formatter_extraction._functions_from_sources` — tools/test_display_formatter_extraction.py:91 — Handles functions from sources for the utilities feature. Main detected dependency: compile.
- `tools.test_display_formatter_extraction._load_module_functions` — tools/test_display_formatter_extraction.py:98 — Loads load module functions for the utilities feature. Main detected dependency: RuntimeError.
- `tools.test_display_formatter_extraction._source_state` — tools/test_display_formatter_extraction.py:107 — Handles source state for the utilities feature. Main detected dependency: IMPORT_LINES.items.
- `tools.test_display_formatter_extraction._test_applied` — tools/test_display_formatter_extraction.py:157 — Handles test applied for the utilities feature. Main detected dependency: _behavior.
- `tools.test_display_formatter_extraction.main` — tools/test_display_formatter_extraction.py:174 — Handles main for the utilities feature. Main detected dependency: AssertionError.
- `tools.test_display_ui_helper_batch_04.FakeLabel.__init__` — tools/test_display_ui_helper_batch_04.py:52 — Handles init for the utilities feature.
- `tools.test_display_ui_helper_batch_04.FakeLabel.configure` — tools/test_display_ui_helper_batch_04.py:56 — Handles configure for the utilities feature. Main detected dependency: RuntimeError.

### Batch 31: Other (197 lines)

Risk mix: `database_read`, `support`, `ui_only`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._PgCompatCursor.__getattr__` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:843 — Handles getattr for the other feature. Main detected dependency: getattr.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._PgCompatConnection.__init__` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:848 — Handles init for the other feature. Main detected dependency: RuntimeError.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._PgCompatConnection.cursor` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:862 — Handles cursor for the other feature. Main detected dependency: _PgCompatCursor.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._PgCompatConnection.close` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:879 — Handles close for the other feature. Main detected dependency: self._pg.close.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_connect_db` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:905 — Handles spina pg connect db for the other feature. Main detected dependency: _PgCompatConnection.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.data_path` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1050 — Handles data path for the other feature. Main detected dependency: os.path.join.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.run_write` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1089 — Retry wrapper for SQLite write operations.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._CalendarPopup._build_ui` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1635 — Builds build ui for the other feature. Main detected dependency: b.pack.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._CalendarPopup._render` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1672 — Handles render for the other feature. Main detected dependency: b.configure.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._CalendarPopup._pick` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1693 — Handles pick for the other feature. Main detected dependency: date.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._CalendarPopup._prev_month` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1700 — Handles prev month for the other feature. Main detected dependency: self._render.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._CalendarPopup._next_month` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1707 — Handles next month for the other feature. Main detected dependency: self._render.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._CalendarPopup._today` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1714 — Handles today for the other feature. Main detected dependency: date.today.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._CalendarPopup._clear` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1719 — Handles clear for the other feature. Main detected dependency: self._close.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._CalendarRangePopup._build_ui` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1780 — Builds build ui for the other feature. Main detected dependency: b.pack.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._CalendarRangePopup._refresh_info` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1853 — Refreshes refresh info for the other feature. Main detected dependency: self._info.configure.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._CalendarRangePopup._pick` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1861 — Handles pick for the other feature. Main detected dependency: date.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._CalendarRangePopup._apply` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1887 — Handles apply for the other feature. Main detected dependency: self._close.

### Batch 32: Dashboard (192 lines)

Risk mix: `database_read`, `support`, `ui_only`

- `tools.test_legacy_dashboard_controls_batch_15.FakeTtk.Style` — tools/test_legacy_dashboard_controls_batch_15.py:83 — Handles Style for the dashboard feature. Main detected dependency: FakeStyle.
- `tools.test_legacy_dashboard_controls_batch_15._palette` — tools/test_legacy_dashboard_controls_batch_15.py:94 — Handles palette for the dashboard feature. Main detected dependency: RuntimeError.
- `tools.test_legacy_dashboard_controls_batch_15._reset_runtime` — tools/test_legacy_dashboard_controls_batch_15.py:100 — Handles reset runtime for the dashboard feature.
- `tools.test_legacy_dashboard_controls_batch_15._load_manifest` — tools/test_legacy_dashboard_controls_batch_15.py:114 — Loads load manifest for the dashboard feature. Main detected dependency: json.loads.
- `tools.test_legacy_dashboard_controls_batch_15._source_function` — tools/test_legacy_dashboard_controls_batch_15.py:118 — Handles source function for the dashboard feature. Main detected dependency: RuntimeError.
- `tools.test_legacy_dashboard_controls_batch_15._resolve_function` — tools/test_legacy_dashboard_controls_batch_15.py:142 — Handles resolve function for the dashboard feature. Main detected dependency: RuntimeError.
- `tools.test_legacy_dashboard_controls_batch_15._capture_style` — tools/test_legacy_dashboard_controls_batch_15.py:196 — Handles capture style for the dashboard feature. Main detected dependency: _reset_runtime.
- `tools.test_legacy_dashboard_palette_batch_14.Holder.__init__` — tools/test_legacy_dashboard_palette_batch_14.py:31 — Handles init for the dashboard feature.
- `tools.test_legacy_dashboard_palette_batch_14.BadString.__str__` — tools/test_legacy_dashboard_palette_batch_14.py:37 — Handles str for the dashboard feature. Main detected dependency: RuntimeError.
- `tools.test_legacy_dashboard_palette_batch_14._stable` — tools/test_legacy_dashboard_palette_batch_14.py:41 — Handles stable for the dashboard feature. Main detected dependency: _stable.
- `tools.test_legacy_dashboard_palette_batch_14._type_name` — tools/test_legacy_dashboard_palette_batch_14.py:51 — Handles type name for the dashboard feature. Main detected dependency: type.
- `tools.test_legacy_dashboard_palette_batch_14._load_manifest` — tools/test_legacy_dashboard_palette_batch_14.py:56 — Loads load manifest for the dashboard feature. Main detected dependency: json.loads.
- `tools.test_legacy_dashboard_palette_batch_14._resolve_from_source` — tools/test_legacy_dashboard_palette_batch_14.py:60 — Handles resolve from source for the dashboard feature. Main detected dependency: RuntimeError.
- `tools.test_legacy_dashboard_palette_batch_14._resolve_function` — tools/test_legacy_dashboard_palette_batch_14.py:83 — Handles resolve function for the dashboard feature. Main detected dependency: RuntimeError.
- `tools.test_legacy_dashboard_palette_batch_14._cases` — tools/test_legacy_dashboard_palette_batch_14.py:96 — Handles cases for the dashboard feature. Main detected dependency: BadString.
- `tools.test_legacy_dashboard_palette_batch_14._capture_call` — tools/test_legacy_dashboard_palette_batch_14.py:112 — Handles capture call for the dashboard feature. Main detected dependency: _stable.
- `tools.test_legacy_dashboard_palette_batch_14.capture_batch` — tools/test_legacy_dashboard_palette_batch_14.py:128 — Handles capture batch for the dashboard feature. Main detected dependency: RuntimeError.
- `tools.test_ui_card_constructor_batch_08._widget_summary` — tools/test_ui_card_constructor_batch_08.py:133 — Handles widget summary for the dashboard feature. Main detected dependency: _widget_summary.

### Batch 33: Data Bank (187 lines)

Risk mix: `support`

- `tools.cleanup_databank_export_ui_source.remove_old_blocks` — tools/cleanup_databank_export_ui_source.py:74 — Removes remove old blocks for the data bank feature. Main detected dependency: SystemExit.
- `tools.cleanup_databank_export_ui_source._has_any` — tools/cleanup_databank_export_ui_source.py:90 — Handles has any for the data bank feature. Main detected dependency: any.
- `tools.cleanup_databank_export_ui_source.cleanup_source_lines` — tools/cleanup_databank_export_ui_source.py:115 — Handles cleanup source lines for the data bank feature. Main detected dependency: cleaned.append.
- `tools.cleanup_stale_databank_generated_blocks._line_indent` — tools/cleanup_stale_databank_generated_blocks.py:91 — Handles line indent for the data bank feature. Main detected dependency: len.
- `tools.cleanup_stale_databank_generated_blocks._find_callback_definitions` — tools/cleanup_stale_databank_generated_blocks.py:95 — Retrieves find callback definitions for the data bank feature. Main detected dependency: enumerate.
- `tools.cleanup_stale_databank_generated_blocks._target_reference_lines` — tools/cleanup_stale_databank_generated_blocks.py:104 — Handles target reference lines for the data bank feature. Main detected dependency: enumerate.
- `tools.cleanup_stale_databank_generated_blocks._has_marker` — tools/cleanup_stale_databank_generated_blocks.py:109 — Handles has marker for the data bank feature. Main detected dependency: any.
- `tools.cleanup_stale_databank_generated_blocks._has_expected_generated_code` — tools/cleanup_stale_databank_generated_blocks.py:114 — Handles has expected generated code for the data bank feature. Main detected dependency: any.
- `tools.cleanup_stale_databank_generated_blocks._protected_hits` — tools/cleanup_stale_databank_generated_blocks.py:119 — Handles protected hits for the data bank feature. Main detected dependency: term.lower.
- `tools.cleanup_stale_databank_generated_blocks._protected_hits_in_code` — tools/cleanup_stale_databank_generated_blocks.py:142 — Handles protected hits in code for the data bank feature. Main detected dependency: _protected_hits.
- `tools.cleanup_stale_databank_generated_blocks._protected_hits_in_comments` — tools/cleanup_stale_databank_generated_blocks.py:147 — Handles protected hits in comments for the data bank feature. Main detected dependency: _protected_hits.
- `tools.cleanup_stale_databank_generated_blocks._looks_like_generated_databank_cleanup_block` — tools/cleanup_stale_databank_generated_blocks.py:152 — Return True only for generated cleanup/hide block shapes.
- `tools.cleanup_stale_databank_generated_blocks._is_possible_block_start` — tools/cleanup_stale_databank_generated_blocks.py:183 — Handles is possible block start for the data bank feature. Main detected dependency: _line_indent.
- `tools.cleanup_stale_databank_generated_blocks._is_possible_block_boundary` — tools/cleanup_stale_databank_generated_blocks.py:203 — Handles is possible block boundary for the data bank feature. Main detected dependency: _line_indent.
- `tools.cleanup_stale_databank_generated_blocks._next_boundary_after` — tools/cleanup_stale_databank_generated_blocks.py:218 — Handles next boundary after for the data bank feature. Main detected dependency: _is_possible_block_boundary.
- `tools.cleanup_stale_databank_generated_blocks._candidate_range_for_reference` — tools/cleanup_stale_databank_generated_blocks.py:231 — Return 0-based [start, end) candidate range for a stale generated block.
- `tools.cleanup_stale_databank_generated_blocks._merge_ranges` — tools/cleanup_stale_databank_generated_blocks.py:275 — Handles merge ranges for the data bank feature. Main detected dependency: max.
- `tools.cleanup_stale_databank_generated_blocks._remove_ranges` — tools/cleanup_stale_databank_generated_blocks.py:289 — Removes remove ranges for the data bank feature. Main detected dependency: enumerate.

### Batch 34: Utilities (185 lines)

Risk mix: `database_read`, `support`

- `tools.test_ui_display_helper_batch.FakeLabel.configure` — tools/test_ui_display_helper_batch.py:65 — Handles configure for the utilities feature. Main detected dependency: RuntimeError.
- `tools.test_ui_display_helper_batch._stable` — tools/test_ui_display_helper_batch.py:75 — Handles stable for the utilities feature. Main detected dependency: _stable.
- `tools.test_ui_display_helper_batch._type_name` — tools/test_ui_display_helper_batch.py:85 — Handles type name for the utilities feature. Main detected dependency: type.
- `tools.test_ui_display_helper_batch._load_manifest` — tools/test_ui_display_helper_batch.py:90 — Loads load manifest for the utilities feature. Main detected dependency: json.loads.
- `tools.test_ui_display_helper_batch._resolve_from_source` — tools/test_ui_display_helper_batch.py:94 — Handles resolve from source for the utilities feature. Main detected dependency: RuntimeError.
- `tools.test_ui_display_helper_batch._resolve_function` — tools/test_ui_display_helper_batch.py:113 — Handles resolve function for the utilities feature. Main detected dependency: RuntimeError.
- `tools.test_ui_display_helper_batch._capture_round` — tools/test_ui_display_helper_batch.py:126 — Handles capture round for the utilities feature. Main detected dependency: FakeCanvas.
- `tools.test_ui_display_helper_batch._card_state` — tools/test_ui_display_helper_batch.py:159 — Handles card state for the utilities feature.
- `tools.test_ui_display_helper_batch._capture_card` — tools/test_ui_display_helper_batch.py:166 — Handles capture card for the utilities feature. Main detected dependency: FakeLabel.
- `tools.test_ui_display_helper_batch.capture_batch` — tools/test_ui_display_helper_batch.py:213 — Handles capture batch for the utilities feature. Main detected dependency: RuntimeError.
- `tools.ui_action_inventory.normalize` — tools/ui_action_inventory.py:103 — Handles normalize for the utilities feature. Main detected dependency: join.
- `tools.ui_action_inventory.collect_callback_candidates` — tools/ui_action_inventory.py:164 — Handles collect callback candidates for the utilities feature. Main detected dependency: CALLBACK_KEYWORDS.items.

### Batch 35: Other (179 lines)

Risk mix: `database_read`, `support`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._strip_adv_tags` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:26835 — Remove [ADV:...] tags from a description string.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.RenewDialog._valid_ymd` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:30429 — Handles valid ymd for the other feature. Main detected dependency: datetime.strptime.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_cashctl__ceil_thousand_units` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:37586 — Handles spina cashctl ceil thousand units for the other feature. Main detected dependency: float.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_crc_key` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:39532 — Handles spina crc key for the other feature. Main detected dependency: _spina_crc_norm_lt.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_crc_wrap` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:39708 — Handles spina crc wrap for the other feature. Main detected dependency: c.stringWidth.
- `spina_app.area_hierarchy._now_text` — spina_app/area_hierarchy.py:25 — Handles now text for the other feature. Main detected dependency: datetime.now.
- `spina_app.area_hierarchy._legacy_area_uid` — spina_app/area_hierarchy.py:57 — Return a stable ID so repeated migrations cannot duplicate a flat Area.
- `spina_app.area_hierarchy.ensure_area_hierarchy_ready` — spina_app/area_hierarchy.py:255 — Ensure hierarchy storage once for this live database connection.
- `spina_app.area_hierarchy.list_area_nodes` — spina_app/area_hierarchy.py:262 — Handles list area nodes for the other feature. Main detected dependency: _fetch_nodes.
- `spina_app.area_hierarchy.build_area_tree` — spina_app/area_hierarchy.py:267 — Build a nested tree from a flat list without imposing a depth limit.
- `spina_app.area_hierarchy._node_by_uid` — spina_app/area_hierarchy.py:303 — Handles node by uid for the other feature. Main detected dependency: _fetch_nodes.
- `spina_app.area_hierarchy_ops._now_text` — spina_app/area_hierarchy_ops.py:25 — Handles now text for the other feature. Main detected dependency: datetime.now.
- `spina_app.area_hierarchy_ops._node_map` — spina_app/area_hierarchy_ops.py:33 — Handles node map for the other feature. Main detected dependency: dict.
- `spina_app.area_hierarchy_ops.find_area_node_by_path` — spina_app/area_hierarchy_ops.py:41 — Return the node whose full path matches ``path`` case-insensitively.
- `spina_app.area_hierarchy_ops._subtree_uids` — spina_app/area_hierarchy_ops.py:97 — Handles subtree uids for the other feature. Main detected dependency: children.get.
- `spina_app.area_hierarchy_ops.move_area_node` — spina_app/area_hierarchy_ops.py:298 — Move a node to another parent or to the root, preserving its subtree.
- `spina_app.area_hierarchy_ops._require_active_ancestor_chain` — spina_app/area_hierarchy_ops.py:349 — Prevent an active Area from existing below an inactive ancestor.
- `spina_app.area_hierarchy_ops.add_child_area_node` — spina_app/area_hierarchy_ops.py:412 — Named wrapper used by the Area Manager for unlimited child levels.

### Batch 36: Other (175 lines)

Risk mix: `database_read`, `support`

- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._LockedConnection.__init__` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3850 — Handles init for the other feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._LockedConnection.cursor` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3854 — Handles cursor for the other feature. Main detected dependency: _LockedCursor.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._LockedConnection.close` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3917 — Handles close for the other feature. Main detected dependency: self._conn.close.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._LockedConnection.__getattr__` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3924 — Handles getattr for the other feature. Main detected dependency: getattr.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._set_last_error` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3965 — Updates set last error for the other feature. Main detected dependency: str.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.get_last_error` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3971 — Retrieves get last error for the other feature. Main detected dependency: getattr.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._dayclose_norm_workflow` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6983 — Handles dayclose norm workflow for the other feature. Main detected dependency: abs.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._getv` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8645 — Safe getter for dict / sqlite3.Row / objects.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._wrap_to_width` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8748 — Handles wrap to width for the other feature. Main detected dependency: lines.append.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.draw_notes_aligned` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8762 — Draws: Note: YYYY-MM-DD wrapped note text (blank) continuation lines aligned under text column Returns the new y after drawing.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._access_prefs_path` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8861 — Handles access prefs path for the other feature. Main detected dependency: data_path.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._make_salt` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8961 — Handles make salt for the other feature. Main detected dependency: join.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._clear_preview` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:9927 — Handles clear preview for the other feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._walk_widgets` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:13185 — Handles walk widgets for the other feature. Main detected dependency: self._walk_widgets.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._audit_money_text` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:13862 — Handles audit money text for the other feature. Main detected dependency: float.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._make_header_button` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:16126 — Create a flatter, modern top-bar button using tk.Button for better dark-mode control.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._month_label` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:16856 — Handles month label for the other feature.
- `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._daterange_inclusive` — OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:26708 — Handles daterange inclusive for the other feature. Main detected dependency: _td_soapatch.

### Batch 37: Other (167 lines)

Risk mix: `support`

- `tools.audit_dynamic_sql_context.context` — tools/audit_dynamic_sql_context.py:117 — Handles context for the other feature. Main detected dependency: len.
- `tools.audit_dynamic_sql_context.has_protected_context` — tools/audit_dynamic_sql_context.py:128 — Handles has protected context for the other feature. Main detected dependency: any.
- `tools.audit_legacy_callback_usage.line_context` — tools/audit_legacy_callback_usage.py:47 — Handles line context for the other feature. Main detected dependency: join.
- `tools.audit_legacy_callback_usage.has_protected_keyword` — tools/audit_legacy_callback_usage.py:53 — Handles has protected keyword for the other feature. Main detected dependency: any.
- `tools.audit_legacy_callback_usage.collect_definitions` — tools/audit_legacy_callback_usage.py:73 — Handles collect definitions for the other feature. Main detected dependency: defs.append.
- `tools.audit_legacy_callback_usage.line_inside_any_definition` — tools/audit_legacy_callback_usage.py:90 — Handles line inside any definition for the other feature. Main detected dependency: int.
- `tools.audit_legacy_callback_usage.collect_references` — tools/audit_legacy_callback_usage.py:97 — Handles collect references for the other feature. Main detected dependency: ASSIGN_OR_DEF_RE.search.
- `tools.audit_legacy_callback_usage.audit` — tools/audit_legacy_callback_usage.py:164 — Handles audit for the other feature. Main detected dependency: build_recommendations.
- `tools.audit_patch_chains._lower` — tools/audit_patch_chains.py:62 — Handles lower for the other feature. Main detected dependency: str.
- `tools.audit_patch_chains._context` — tools/audit_patch_chains.py:66 — Handles context for the other feature. Main detected dependency: join.
- `tools.audit_patch_chains._has_protected` — tools/audit_patch_chains.py:72 — Handles has protected for the other feature. Main detected dependency: _lower.
- `tools.audit_patch_chains._def_lines` — tools/audit_patch_chains.py:92 — Handles def lines for the other feature. Main detected dependency: DEF_RE.match.
- `tools.audit_patch_chains._find_patch_assignments` — tools/audit_patch_chains.py:101 — Retrieves find patch assignments for the other feature. Main detected dependency: DIRECT_ASSIGN_RE.match.
- `tools.audit_pg_command_callers._call_name` — tools/audit_pg_command_callers.py:44 — Handles call name for the other feature. Main detected dependency: _call_name.
- `tools.audit_pg_command_callers._short_call_name` — tools/audit_pg_command_callers.py:57 — Handles short call name for the other feature. Main detected dependency: name.rsplit.
- `tools.audit_pg_command_callers._contains_name` — tools/audit_pg_command_callers.py:61 — Handles contains name for the other feature. Main detected dependency: _call_name.
- `tools.audit_pg_command_callers._context` — tools/audit_pg_command_callers.py:71 — Handles context for the other feature. Main detected dependency: len.
- `tools.audit_pg_command_callers._protected_context` — tools/audit_pg_command_callers.py:80 — Handles protected context for the other feature. Main detected dependency: _context.

### Batch 38: Dashboard (166 lines)

Risk mix: `database_read`, `support`, `ui_only`

- `tools.test_cash_control_input_normalizer_batch_07._capture` — tools/test_cash_control_input_normalizer_batch_07.py:86 — Handles capture for the dashboard feature. Main detected dependency: function.
- `tools.test_cash_control_input_normalizer_batch_07.capture` — tools/test_cash_control_input_normalizer_batch_07.py:102 — Handles capture for the dashboard feature. Main detected dependency: PARSE_CASES.items.
- `tools.test_cash_control_ui_controls_batch_09.FakeWidget.__init__` — tools/test_cash_control_ui_controls_batch_09.py:35 — Handles init for the dashboard feature. Main detected dependency: dict.
- `tools.test_cash_control_ui_controls_batch_09.FakeWidget.pack` — tools/test_cash_control_ui_controls_batch_09.py:44 — Handles pack for the dashboard feature. Main detected dependency: dict.
- `tools.test_cash_control_ui_controls_batch_09._WidgetFactory.__init__` — tools/test_cash_control_ui_controls_batch_09.py:49 — Handles init for the dashboard feature.
- `tools.test_cash_control_ui_controls_batch_09._WidgetFactory.__call__` — tools/test_cash_control_ui_controls_batch_09.py:52 — Handles call for the dashboard feature. Main detected dependency: FakeWidget.
- `tools.test_cash_control_ui_controls_batch_09.FakeStyle.__init__` — tools/test_cash_control_ui_controls_batch_09.py:62 — Handles init for the dashboard feature.
- `tools.test_cash_control_ui_controls_batch_09.FakeStyle.configure` — tools/test_cash_control_ui_controls_batch_09.py:66 — Handles configure for the dashboard feature. Main detected dependency: dict.
- `tools.test_cash_control_ui_controls_batch_09.FakeStyle.map` — tools/test_cash_control_ui_controls_batch_09.py:69 — Handles map for the dashboard feature. Main detected dependency: dict.
- `tools.test_cash_control_ui_controls_batch_09.FakeTtk.Style` — tools/test_cash_control_ui_controls_batch_09.py:79 — Handles Style for the dashboard feature. Main detected dependency: FakeStyle.
- `tools.test_cash_control_ui_controls_batch_09._cash_palette` — tools/test_cash_control_ui_controls_batch_09.py:90 — Handles cash palette for the dashboard feature. Main detected dependency: RuntimeError.
- `tools.test_cash_control_ui_controls_batch_09._reset_runtime` — tools/test_cash_control_ui_controls_batch_09.py:96 — Handles reset runtime for the dashboard feature.
- `tools.test_cash_control_ui_controls_batch_09._load_manifest` — tools/test_cash_control_ui_controls_batch_09.py:103 — Loads load manifest for the dashboard feature. Main detected dependency: json.loads.
- `tools.test_cash_control_ui_controls_batch_09._source_function` — tools/test_cash_control_ui_controls_batch_09.py:107 — Handles source function for the dashboard feature. Main detected dependency: RuntimeError.
- `tools.test_cash_control_ui_controls_batch_09._resolve_function` — tools/test_cash_control_ui_controls_batch_09.py:130 — Handles resolve function for the dashboard feature. Main detected dependency: RuntimeError.
- `tools.test_cash_control_ui_controls_batch_09._widget_summary` — tools/test_cash_control_ui_controls_batch_09.py:147 — Handles widget summary for the dashboard feature. Main detected dependency: _widget_summary.
- `tools.test_cash_control_ui_controls_batch_09._capture_builder` — tools/test_cash_control_ui_controls_batch_09.py:156 — Handles capture builder for the dashboard feature. Main detected dependency: FakeWidget.
- `tools.test_cash_control_ui_controls_batch_09._capture_style` — tools/test_cash_control_ui_controls_batch_09.py:188 — Handles capture style for the dashboard feature. Main detected dependency: _reset_runtime.

### Batch 39: Utilities (162 lines)

Risk mix: `support`

- `spina_app.ui_helpers._spina_v18_draw_round_rect` — spina_app/ui_helpers.py:30 — Canvas rounded rectangle fallback using polygon smoothing.
- `spina_app.utilities.dates._spina_cashctl__valid_date` — spina_app/utilities/dates.py:7 — Handles spina cashctl valid date for the utilities feature. Main detected dependency: date.today.
- `spina_app.utilities.dates._spina__parse_day_ymd` — spina_app/utilities/dates.py:15 — Handles spina parse day ymd for the utilities feature. Main detected dependency: datetime.strptime.
- `spina_app.utilities.dates._spina_dash__parse_date` — spina_app/utilities/dates.py:24 — Handles spina dash parse date for the utilities feature. Main detected dependency: datetime.strptime.
- `spina_app.utilities.dates._spina_dash__date_text` — spina_app/utilities/dates.py:33 — Handles spina dash date text for the utilities feature. Main detected dependency: _spina_dash__parse_date.
- `spina_app.utilities.dates._spina_v24_cilog_parse_day` — spina_app/utilities/dates.py:40 — Handles spina v24 cilog parse day for the utilities feature. Main detected dependency: datetime.strptime.
- `spina_app.utilities.dates._spina__norm_weekday` — spina_app/utilities/dates.py:51 — Handles spina norm weekday for the utilities feature. Main detected dependency: _mp.get.
- `spina_app.utilities.dates._spina__norm_dom` — spina_app/utilities/dates.py:66 — Handles spina norm dom for the utilities feature. Main detected dependency: int.
- `spina_app.utilities.diffs._spina_cilog_diff_pairs` — spina_app/utilities/diffs.py:5 — Handles spina cilog diff pairs for the utilities feature. Main detected dependency: isinstance.
- `spina_app.utilities.formatting.fmt_currency` — spina_app/utilities/formatting.py:5 — Handles fmt currency for the utilities feature. Main detected dependency: float.
- `spina_app.utilities.formatting._spina_dash__fmt_pct` — spina_app/utilities/formatting.py:11 — Handles spina dash fmt pct for the utilities feature. Main detected dependency: float.
- `spina_app.utilities.formatting._spina_v23_money` — spina_app/utilities/formatting.py:16 — Handles spina v23 money for the utilities feature. Main detected dependency: float.
- `spina_app.utilities.formatting._spina_v23_percent` — spina_app/utilities/formatting.py:22 — Handles spina v23 percent for the utilities feature. Main detected dependency: float.
- `spina_app.utilities.formatting._spina_cilog_fmt_money` — spina_app/utilities/formatting.py:29 — Handles spina cilog fmt money for the utilities feature. Main detected dependency: float.
- `spina_app.utilities.formatting._spina_v17_fmt_short_money` — spina_app/utilities/formatting.py:68 — Handles spina v17 fmt short money for the utilities feature. Main detected dependency: abs.
- `spina_app.utilities.formatting._spina_v18_fmt_money_compact` — spina_app/utilities/formatting.py:81 — Handles spina v18 fmt money compact for the utilities feature. Main detected dependency: abs.
- `spina_app.utilities.formatting._spina_cashctl__fmt_pct` — spina_app/utilities/formatting.py:123 — Handles spina cashctl fmt pct for the utilities feature. Main detected dependency: _spina_dash__fmt_pct.
- `spina_app.utilities.notes._as_note_dict` — spina_app/utilities/notes.py:5 — Normalize a note entry to a dict with '__default__' and YYYY-MM-DD keys.

### Batch 40: Other (159 lines)

Risk mix: `database_read`, `support`

- `tools.extract_cilog_action_label._find` — tools/extract_cilog_action_label.py:34 — Handles find for the other feature. Main detected dependency: isinstance.
- `tools.extract_cilog_action_label._function_text` — tools/extract_cilog_action_label.py:38 — Handles function text for the other feature. Main detected dependency: join.
- `tools.extract_cilog_action_label.apply` — tools/extract_cilog_action_label.py:114 — Handles apply for the other feature. Main detected dependency: _atomic_write.
- `tools.extract_cilog_diff_pairs._local_names` — tools/extract_cilog_diff_pairs.py:42 — Handles local names for the other feature. Main detected dependency: ast.walk.
- `tools.extract_fmt_currency_module._find_top_level_function` — tools/extract_fmt_currency_module.py:27 — Retrieves find top level function for the other feature. Main detected dependency: RuntimeError.
- `tools.extract_fmt_currency_module._local_names` — tools/extract_fmt_currency_module.py:40 — Handles local names for the other feature. Main detected dependency: ast.walk.
- `tools.extract_fmt_currency_module._external_loaded_names` — tools/extract_fmt_currency_module.py:64 — Handles external loaded names for the other feature. Main detected dependency: _local_names.
- `tools.extract_fmt_currency_module._function_source` — tools/extract_fmt_currency_module.py:74 — Handles function source for the other feature. Main detected dependency: getattr.
- `tools.extract_fmt_currency_module._replace_definition` — tools/extract_fmt_currency_module.py:92 — Handles replace definition for the other feature. Main detected dependency: getattr.
- `tools.extract_merge_note_dict.external_names` — tools/extract_merge_note_dict.py:39 — Handles external names for the other feature. Main detected dependency: ast.walk.
- `tools.inject_critical_path_logging.remove_existing_block` — tools/inject_critical_path_logging.py:137 — Removes remove existing block for the other feature. Main detected dependency: SystemExit.
- `tools.inject_silent_ui_logging._lower` — tools/inject_silent_ui_logging.py:174 — Handles lower for the other feature. Main detected dependency: str.
- `tools.inject_silent_ui_logging._has_any` — tools/inject_silent_ui_logging.py:178 — Handles has any for the other feature. Main detected dependency: _lower.
- `tools.inject_silent_ui_logging._line_indent_width` — tools/inject_silent_ui_logging.py:183 — Handles line indent width for the other feature. Main detected dependency: len.
- `tools.inject_silent_ui_logging._context` — tools/inject_silent_ui_logging.py:187 — Handles context for the other feature. Main detected dependency: join.
- `tools.inject_silent_ui_logging._function_map` — tools/inject_silent_ui_logging.py:193 — Handles function map for the other feature. Main detected dependency: CLASS_RE.match.
- `tools.inject_silent_ui_logging._body_after_except` — tools/inject_silent_ui_logging.py:209 — Handles body after except for the other feature. Main detected dependency: _line_indent_width.
- `tools.inject_silent_ui_logging._is_silent_fallback_body` — tools/inject_silent_ui_logging.py:222 — Handles is silent fallback body for the other feature. Main detected dependency: _lower.

## Duplicate symbol names

- `BadString`: `tools/test_base_theme_palette_batch_11.py:36`, `tools/test_legacy_dashboard_palette_batch_14.py:36`, `tools/test_theme_palette_helper_batch_05.py:37`
- `Dummy`: `tools/test_cash_control_feature_wave_21.py:53`, `tools/test_collectors_editor_wave_26.py:125`, `tools/test_dashboard_visibility_wave_24.py:29`
- `FakeApp`: `tools/test_client_info_logs_feature_wave_20.py:33`, `tools/test_clients_feature_wave_19.py:62`
- `FakeCanvas`: `tools/test_cash_control_feature_wave_21.py:30`, `tools/test_ui_display_helper_batch.py:36`
- `FakeLabel`: `tools/test_clients_feature_wave_19.py:34`, `tools/test_display_ui_helper_batch_04.py:51`, `tools/test_ui_display_helper_batch.py:60`
- `FakeStyle`: `tools/test_cash_control_ui_controls_batch_09.py:61`, `tools/test_cilog_ui_controls_batch_10.py:58`, `tools/test_client_route_tree_style_batch_12.py:39`, `tools/test_legacy_dashboard_controls_batch_15.py:66`
- `FakeTk`: `tools/test_cash_control_ui_controls_batch_09.py:56`, `tools/test_cilog_ui_controls_batch_10.py:54`, `tools/test_collector_route_card_batch_13.py:62`, `tools/test_legacy_dashboard_card_batch_16.py:66`, `tools/test_legacy_dashboard_controls_batch_15.py:42`, `tools/test_ui_card_constructor_batch_08.py:76`
- `FakeTree`: `tools/test_clients_feature_wave_19.py:42`, `tools/test_collectors_editor_wave_26.py:65`
- `FakeTtk`: `tools/test_cash_control_ui_controls_batch_09.py:73`, `tools/test_cilog_ui_controls_batch_10.py:70`, `tools/test_client_route_tree_style_batch_12.py:51`, `tools/test_legacy_dashboard_controls_batch_15.py:78`
- `FakeVar`: `tools/test_client_info_logs_feature_wave_20.py:26`, `tools/test_clients_feature_wave_19.py:25`
- `FakeWidget`: `tools/test_cash_control_ui_controls_batch_09.py:34`, `tools/test_cilog_ui_controls_batch_10.py:36`, `tools/test_collector_route_card_batch_13.py:40`, `tools/test_legacy_dashboard_card_batch_16.py:40`, `tools/test_ui_card_constructor_batch_08.py:54`
- `Holder`: `tools/test_base_theme_palette_batch_11.py:30`, `tools/test_display_ui_helper_batch_04.py:62`, `tools/test_legacy_dashboard_palette_batch_14.py:30`, `tools/test_theme_palette_helper_batch_05.py:31`, `tools/test_ui_display_helper_batch.py:71`
- `PassOnlyVisitor`: `tools/plan_app_lifecycle_window_pass_only.py:106`, `tools/plan_logger_fallback_pass_only.py:84`, `tools/plan_login_dialog_pass_only.py:130`, `tools/plan_modern_ui_pass_only_cleanup.py:99`, `tools/plan_queue_empty_pass_only.py:79`, `tools/plan_remaining_pass_only_groups.py:108`, `tools/plan_ui_compatibility_pass_only.py:138`
- `Style`: `tools/test_cash_control_ui_controls_batch_09.py:79`, `tools/test_cilog_ui_controls_batch_10.py:75`, `tools/test_client_route_tree_style_batch_12.py:56`, `tools/test_legacy_dashboard_controls_batch_15.py:83`
- `Var`: `tools/test_collectors_editor_wave_26.py:36`, `tools/test_dashboard_feature_wave_17.py:22`, `tools/test_dashboard_visibility_wave_24.py:21`
- `Visitor`: `tools/audit_bare_except_context.py:41`, `tools/audit_pg_backup_action_flow.py:93`
- `_WidgetFactory`: `tools/test_cash_control_ui_controls_batch_09.py:48`, `tools/test_cilog_ui_controls_batch_10.py:46`, `tools/test_collector_route_card_batch_13.py:54`, `tools/test_legacy_dashboard_card_batch_16.py:58`, `tools/test_ui_card_constructor_batch_08.py:68`
- `__call__`: `tools/test_cash_control_ui_controls_batch_09.py:52`, `tools/test_cilog_ui_controls_batch_10.py:50`, `tools/test_collector_route_card_batch_13.py:58`, `tools/test_legacy_dashboard_card_batch_16.py:62`, `tools/test_ui_card_constructor_batch_08.py:72`
- `__getattr__`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:843`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3845`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3924`
- `__getitem__`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:564`, `tools/test_display_data_helper_batch.py:42`, `tools/test_display_data_helper_batch.py:53`
- `__init__`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:558`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:699`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:848`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1602`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1733`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:2961`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3770`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3850`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3932`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:14199`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:26157`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:30405`, `tools/audit_bare_except_context.py:42`, `tools/audit_blocking_ui_calls.py:89`, `tools/audit_pg_backup_action_flow.py:94`, `tools/inspect_blocking_ui_context.py:87`, `tools/plan_app_lifecycle_window_pass_only.py:107`, `tools/plan_logger_fallback_pass_only.py:85`, `tools/plan_login_dialog_pass_only.py:131`, `tools/plan_modern_ui_pass_only_cleanup.py:100`, `tools/plan_pure_login_dialog_ui_pass_only.py:72`, `tools/plan_queue_empty_pass_only.py:80`, `tools/plan_remaining_pass_only_groups.py:109`, `tools/plan_ui_compatibility_pass_only.py:139`, `tools/test_base_theme_palette_batch_11.py:31`, `tools/test_cash_control_feature_wave_21.py:31`, `tools/test_cash_control_feature_wave_21.py:56`, `tools/test_cash_control_ui_controls_batch_09.py:35`, `tools/test_cash_control_ui_controls_batch_09.py:49`, `tools/test_cash_control_ui_controls_batch_09.py:62`, `tools/test_cilog_ui_controls_batch_10.py:37`, `tools/test_cilog_ui_controls_batch_10.py:47`, `tools/test_cilog_ui_controls_batch_10.py:59`, `tools/test_client_info_logs_feature_wave_20.py:27`, `tools/test_client_info_logs_feature_wave_20.py:34`, `tools/test_client_route_tree_style_batch_12.py:40`, `tools/test_clients_feature_wave_19.py:26`, `tools/test_clients_feature_wave_19.py:35`, `tools/test_clients_feature_wave_19.py:43`, `tools/test_clients_feature_wave_19.py:63`, `tools/test_collector_route_card_batch_13.py:41`, `tools/test_collector_route_card_batch_13.py:55`, `tools/test_collectors_editor_wave_26.py:37`, `tools/test_collectors_editor_wave_26.py:46`, `tools/test_collectors_editor_wave_26.py:66`, `tools/test_collectors_editor_wave_26.py:89`, `tools/test_collectors_editor_wave_26.py:117`, `tools/test_dashboard_feature_wave_17.py:23`, `tools/test_dashboard_visibility_wave_24.py:22`, `tools/test_display_data_helper_batch.py:32`, `tools/test_display_ui_helper_batch_04.py:52`, `tools/test_legacy_dashboard_card_batch_16.py:41`, `tools/test_legacy_dashboard_card_batch_16.py:59`, `tools/test_legacy_dashboard_controls_batch_15.py:35`, `tools/test_legacy_dashboard_controls_batch_15.py:55`, `tools/test_legacy_dashboard_controls_batch_15.py:67`, `tools/test_legacy_dashboard_palette_batch_14.py:31`, `tools/test_theme_palette_helper_batch_05.py:32`, `tools/test_ui_card_constructor_batch_08.py:55`, `tools/test_ui_card_constructor_batch_08.py:69`, `tools/test_ui_display_helper_batch.py:37`, `tools/test_ui_display_helper_batch.py:61`
- `__iter__`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:569`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:840`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3841`, `tools/test_display_data_helper_batch.py:27`, `tools/test_display_data_helper_batch.py:47`
- `__str__`: `tools/test_base_theme_palette_batch_11.py:37`, `tools/test_legacy_dashboard_palette_batch_14.py:37`, `tools/test_payment_schedule_normalizer_batch_06.py:27`, `tools/test_payment_schedule_normalizer_batch_06.py:32`, `tools/test_theme_palette_helper_batch_05.py:38`
- `_applied`: `tools/test_cilog_action_label_extraction.py:125`, `tools/test_log_serialization_helper_extraction.py:118`
- `_arrange_areas_dialog`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:21766`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:31580`
- `_atomic_write`: `tools/extract_cilog_action_label.py:44`, `tools/extract_cilog_diff_pairs.py:21`, `tools/extract_cilog_value_formatter.py:118`, `tools/extract_date_display_helpers.py:211`, `tools/extract_date_helpers_module.py:257`, `tools/extract_display_formatters.py:121`, `tools/extract_fmt_currency_module.py:100`, `tools/extract_numeric_parsers.py:197`, `tools/extract_text_normalizers.py:262`
- `_behavior`: `tools/test_cilog_action_label_extraction.py:53`, `tools/test_cilog_money_formatter_extraction.py:53`, `tools/test_cilog_value_formatter_extraction.py:66`, `tools/test_date_display_helper_extraction.py:76`, `tools/test_date_helpers_extraction.py:92`, `tools/test_display_formatter_extraction.py:80`, `tools/test_log_serialization_helper_extraction.py:52`, `tools/test_numeric_parser_extraction.py:82`, `tools/test_text_normalizer_extraction.py:83`
- `_build_ui`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1635`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1780`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3172`
- `_call_name`: `tools/audit_blocking_ui_calls.py:55`, `tools/audit_pg_command_callers.py:44`, `tools/inspect_blocking_ui_context.py:38`
- `_cancel`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:9125`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:9429`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:9523`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:21744`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:21823`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:25592`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:31558`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:31637`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:44215`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:44657`
- `_capture`: `tools/test_cash_control_input_normalizer_batch_07.py:86`, `tools/test_cilog_action_label_extraction.py:37`, `tools/test_cilog_diff_pairs_extraction.py:59`, `tools/test_cilog_money_formatter_extraction.py:37`, `tools/test_cilog_value_formatter_extraction.py:50`, `tools/test_collector_route_card_batch_13.py:127`, `tools/test_date_display_helper_extraction.py:60`, `tools/test_date_helpers_extraction.py:73`, `tools/test_display_data_helper_batch.py:155`, `tools/test_display_formatter_extraction.py:64`, `tools/test_fmt_currency_extraction.py:22`, `tools/test_legacy_dashboard_card_batch_16.py:133`, `tools/test_log_serialization_helper_extraction.py:36`, `tools/test_numeric_parser_extraction.py:66`, `tools/test_payment_schedule_normalizer_batch_06.py:74`, `tools/test_pure_helper_batch.py:129`, `tools/test_text_normalizer_extraction.py:67`, `tools/test_ui_card_constructor_batch_08.py:142`
- `_capture_call`: `tools/test_base_theme_palette_batch_11.py:112`, `tools/test_display_ui_helper_batch_04.py:126`, `tools/test_legacy_dashboard_palette_batch_14.py:112`, `tools/test_theme_palette_helper_batch_05.py:113`
- `_capture_card`: `tools/test_display_ui_helper_batch_04.py:134`, `tools/test_ui_display_helper_batch.py:166`
- `_capture_style`: `tools/test_cash_control_ui_controls_batch_09.py:188`, `tools/test_cilog_ui_controls_batch_10.py:176`, `tools/test_client_route_tree_style_batch_12.py:138`, `tools/test_legacy_dashboard_controls_batch_15.py:196`
- `_cases`: `tools/test_base_theme_palette_batch_11.py:96`, `tools/test_cilog_action_label_extraction.py:20`, `tools/test_cilog_diff_pairs_extraction.py:40`, `tools/test_cilog_money_formatter_extraction.py:20`, `tools/test_cilog_value_formatter_extraction.py:28`, `tools/test_date_display_helper_extraction.py:28`, `tools/test_date_helpers_extraction.py:34`, `tools/test_display_formatter_extraction.py:27`, `tools/test_legacy_dashboard_palette_batch_14.py:96`, `tools/test_log_serialization_helper_extraction.py:20`, `tools/test_numeric_parser_extraction.py:27`, `tools/test_text_normalizer_extraction.py:27`, `tools/test_theme_palette_helper_batch_05.py:97`
- `_cash_palette`: `tools/test_cash_control_ui_controls_batch_09.py:90`, `tools/test_ui_card_constructor_batch_08.py:81`
- `_cilog_palette`: `tools/test_cilog_ui_controls_batch_10.py:86`, `tools/test_ui_card_constructor_batch_08.py:85`
- `_classify`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:18824`, `tools/plan_app_lifecycle_window_pass_only.py:80`
- `_clear`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1719`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1916`
- `_clear_collectors_search_filters`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:20955`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:31214`
- `_close`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1723`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1921`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3578`
- `_close_editor`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:17331`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:17403`
- `_collectors_areas_drag_motion`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:20894`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:35064`
- `_context`: `tools/audit_patch_chains.py:66`, `tools/audit_pg_command_callers.py:71`, `tools/audit_shadowed_definitions.py:56`, `tools/inject_silent_ui_logging.py:187`, `tools/inspect_blocking_ui_context.py:60`, `tools/plan_app_lifecycle_window_pass_only.py:66`, `tools/plan_logger_fallback_pass_only.py:71`, `tools/plan_modern_ui_pass_only_cleanup.py:88`, `tools/plan_pure_login_dialog_ui_pass_only.py:108`, `tools/plan_queue_empty_pass_only.py:65`
- `_context_text`: `tools/plan_app_lifecycle_window_pass_only.py:72`, `tools/plan_login_dialog_pass_only.py:121`
- `_delete_selected_collector`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:12833`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:35014`
- `_display_loan_type_label`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:17782`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:27346`
- `_draw_final_footer`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:22885`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:32775`
- `_draw_global_header`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:22901`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:32791`
- `_draw_page_number`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:22877`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:32767`
- `_edit_selected_collector`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:13038`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:35047`
- `_external_loaded_names`: `tools/extract_date_display_helpers.py:71`, `tools/extract_date_helpers_module.py:78`, `tools/extract_display_formatters.py:72`, `tools/extract_fmt_currency_module.py:64`, `tools/extract_numeric_parsers.py:72`, `tools/extract_text_normalizers.py:75`
- `_fetch_clients_for`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:21667`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:31481`
- `_find_top_level_function`: `tools/cleanup_logger_fallback_pass_only.py:39`, `tools/extract_fmt_currency_module.py:27`
- `_fits`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:22853`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:32743`
- `_fmt_amt`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:10037`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:11380`
- `_functions`: `tools/test_cash_control_input_normalizer_batch_07.py:60`, `tools/test_dashboard_feature_wave_17.py:33`
- `_functions_from_module_source`: `tools/test_date_helpers_extraction.py:103`, `tools/test_numeric_parser_extraction.py:93`, `tools/test_text_normalizer_extraction.py:94`
- `_gv`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:27036`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:27385`
- `_handler_name`: `tools/audit_pass_only_exceptions.py:37`, `tools/plan_logger_fallback_pass_only.py:54`, `tools/plan_login_dialog_pass_only.py:99`, `tools/plan_modern_ui_pass_only_cleanup.py:70`, `tools/plan_queue_empty_pass_only.py:48`
- `_has_any`: `tools/audit_silent_ui_errors.py:81`, `tools/cleanup_databank_export_ui_source.py:90`, `tools/inject_silent_ui_logging.py:178`, `tools/plan_login_dialog_pass_only.py:125`
- `_import_bindings`: `tools/extract_date_helpers_module.py:88`, `tools/extract_text_normalizers.py:85`
- `_indent_width`: `tools/audit_shadowed_definitions.py:52`, `tools/audit_silent_ui_errors.py:71`, `tools/cleanup_neutral_appclass_init_patch.py:45`
- `_is_date`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3691`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:19161`
- `_is_pass_only`: `tools/audit_pass_only_exceptions.py:46`, `tools/plan_app_lifecycle_window_pass_only.py:62`, `tools/plan_logger_fallback_pass_only.py:67`, `tools/plan_login_dialog_pass_only.py:108`, `tools/plan_modern_ui_pass_only_cleanup.py:66`, `tools/plan_queue_empty_pass_only.py:61`, `tools/spina_quality_audit.py:79`
- `_legacy_function`: `tools/test_cilog_money_formatter_extraction.py:72`, `tools/test_cilog_value_formatter_extraction.py:113`
- `_line_indent`: `tools/cleanup_databank_export_callbacks.py:45`, `tools/cleanup_stale_databank_generated_blocks.py:91`
- `_line_source`: `tools/extract_date_display_helpers.py:32`, `tools/extract_date_helpers_module.py:34`, `tools/extract_numeric_parsers.py:31`, `tools/extract_text_normalizers.py:34`
- `_line_span`: `tools/plan_module_separation.py:66`, `tools/spina_quality_audit.py:73`
- `_load`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:11018`, `tools/test_cash_control_input_normalizer_batch_07.py:56`, `tools/test_cilog_action_label_extraction.py:60`
- `_load_generated_functions`: `tools/test_date_helpers_extraction.py:109`, `tools/test_numeric_parser_extraction.py:99`, `tools/test_text_normalizer_extraction.py:100`
- `_load_manifest`: `tools/extract_pure_helper_batch.py:22`, `tools/test_base_theme_palette_batch_11.py:56`, `tools/test_cash_control_ui_controls_batch_09.py:103`, `tools/test_cilog_ui_controls_batch_10.py:99`, `tools/test_client_route_tree_style_batch_12.py:93`, `tools/test_collector_route_card_batch_13.py:76`, `tools/test_display_data_helper_batch.py:114`, `tools/test_display_ui_helper_batch_04.py:81`, `tools/test_legacy_dashboard_card_batch_16.py:80`, `tools/test_legacy_dashboard_controls_batch_15.py:114`, `tools/test_legacy_dashboard_palette_batch_14.py:56`, `tools/test_pure_helper_batch.py:88`, `tools/test_theme_palette_helper_batch_05.py:57`, `tools/test_ui_card_constructor_batch_08.py:89`, `tools/test_ui_display_helper_batch.py:90`
- `_load_module`: `tools/test_cilog_value_formatter_extraction.py:76`, `tools/test_log_serialization_helper_extraction.py:59`
- `_local_names`: `tools/extract_cilog_action_label.py:20`, `tools/extract_cilog_diff_pairs.py:42`, `tools/extract_cilog_value_formatter.py:34`, `tools/extract_date_display_helpers.py:50`, `tools/extract_date_helpers_module.py:54`, `tools/extract_display_formatters.py:49`, `tools/extract_fmt_currency_module.py:40`, `tools/extract_log_serialization_helper.py:33`, `tools/extract_numeric_parsers.py:49`, `tools/extract_text_normalizers.py:52`
- `_log_exc`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1269`, `spina_app/tabs/dashboard.py:46`
- `_lower`: `tools/audit_patch_chains.py:62`, `tools/inject_silent_ui_logging.py:174`
- `_mode_filter`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8820`, `tools/test_clients_feature_wave_19.py:70`
- `_module_source`: `tools/extract_date_helpers_module.py:149`, `tools/extract_fmt_currency_module.py:84`, `tools/extract_numeric_parsers.py:97`, `tools/extract_text_normalizers.py:144`
- `_move`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:21799`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:31613`
- `_name`: `tools/plan_app_lifecycle_window_pass_only.py:48`, `tools/spina_quality_audit.py:60`
- `_next_month`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1707`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1902`
- `_node_source`: `tools/extract_cilog_value_formatter.py:21`, `tools/extract_display_formatters.py:31`
- `_norm`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:11674`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:18457`
- `_norm_area`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:10228`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:12222`
- `_norm_dom`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5060`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5262`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:42697`
- `_norm_lt`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3977`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:24735`
- `_norm_term`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5016`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5208`
- `_norm_weekday`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5046`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:5248`
- `_now_text`: `spina_app/area_hierarchy.py:25`, `spina_app/area_hierarchy_ops.py:25`
- `_ok`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:9395`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:9511`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:21741`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:21821`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:25591`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:31555`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:31635`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:44617`
- `_on_collectors_multi_toggle`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:20539`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:34853`
- `_on_collectors_select`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:20982`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:38243`
- `_on_collectors_tree_click`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:20565`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:34911`
- `_on_collectors_tree_wheel`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:20919`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:34674`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:34875`
- `_on_enter`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:9138`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:9440`
- `_on_search`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:12116`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:20454`
- `_options_dialog`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:21702`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:31516`
- `_original`: `tools/test_cilog_action_label_extraction.py:92`, `tools/test_log_serialization_helper_extraction.py:92`
- `_patched_source`: `tools/extract_date_display_helpers.py:117`, `tools/extract_date_helpers_module.py:172`, `tools/extract_display_formatters.py:107`, `tools/extract_numeric_parsers.py:119`, `tools/extract_text_normalizers.py:167`
- `_pick`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1693`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1861`
- `_populate_collector_details`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:21040`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:38146`
- `_prev_month`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1700`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1894`
- `_protected`: `tools/audit_pass_only_exceptions.py:50`, `tools/plan_app_lifecycle_window_pass_only.py:76`
- `_protected_context`: `tools/audit_pg_command_callers.py:80`, `tools/plan_modern_ui_pass_only_cleanup.py:94`
- `_refresh`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:18959`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:19955`
- `_remove_ranges`: `tools/cleanup_databank_export_callbacks.py:144`, `tools/cleanup_stale_databank_generated_blocks.py:289`
- `_render`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1672`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1822`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:18930`
- `_required_import_nodes`: `tools/extract_date_helpers_module.py:110`, `tools/extract_text_normalizers.py:105`
- `_reset_runtime`: `tools/test_cash_control_ui_controls_batch_09.py:96`, `tools/test_cilog_ui_controls_batch_10.py:92`, `tools/test_client_route_tree_style_batch_12.py:80`, `tools/test_legacy_dashboard_controls_batch_15.py:100`
- `_resolve_from_source`: `tools/test_base_theme_palette_batch_11.py:60`, `tools/test_display_data_helper_batch.py:118`, `tools/test_display_ui_helper_batch_04.py:94`, `tools/test_legacy_dashboard_palette_batch_14.py:60`, `tools/test_pure_helper_batch.py:92`, `tools/test_theme_palette_helper_batch_05.py:61`, `tools/test_ui_display_helper_batch.py:94`
- `_resolve_function`: `tools/test_base_theme_palette_batch_11.py:83`, `tools/test_cash_control_ui_controls_batch_09.py:130`, `tools/test_cilog_ui_controls_batch_10.py:126`, `tools/test_client_route_tree_style_batch_12.py:121`, `tools/test_collector_route_card_batch_13.py:102`, `tools/test_display_data_helper_batch.py:137`, `tools/test_display_ui_helper_batch_04.py:113`, `tools/test_legacy_dashboard_card_batch_16.py:107`, `tools/test_legacy_dashboard_controls_batch_15.py:142`, `tools/test_legacy_dashboard_palette_batch_14.py:83`, `tools/test_payment_schedule_normalizer_batch_06.py:61`, `tools/test_pure_helper_batch.py:111`, `tools/test_theme_palette_helper_batch_05.py:84`, `tools/test_ui_card_constructor_batch_08.py:116`, `tools/test_ui_display_helper_batch.py:113`
- `_route_palette`: `tools/test_client_route_tree_style_batch_12.py:74`, `tools/test_collector_route_card_batch_13.py:70`
- `_s`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:21697`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:31511`
- `_safe_json`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6600`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6758`
- `_save`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:9095`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:16721`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:44185`
- `_save_collector_notes`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:21171`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:34696`
- `_save_selected_collector_notes`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:21141`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:34760`
- `_schedule_collectors_refresh`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:20936`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:31194`
- `_scope`: `tools/plan_app_lifecycle_window_pass_only.py:113`, `tools/plan_login_dialog_pass_only.py:137`, `tools/plan_modern_ui_pass_only_cleanup.py:107`, `tools/plan_pure_login_dialog_ui_pass_only.py:105`
- `_scope_name`: `tools/audit_blocking_ui_calls.py:73`, `tools/audit_pass_only_exceptions.py:27`, `tools/inspect_blocking_ui_context.py:93`, `tools/plan_logger_fallback_pass_only.py:80`, `tools/plan_queue_empty_pass_only.py:86`
- `_source_function`: `tools/test_cash_control_ui_controls_batch_09.py:107`, `tools/test_cilog_ui_controls_batch_10.py:103`, `tools/test_client_route_tree_style_batch_12.py:97`, `tools/test_collector_route_card_batch_13.py:80`, `tools/test_legacy_dashboard_card_batch_16.py:84`, `tools/test_legacy_dashboard_controls_batch_15.py:118`, `tools/test_ui_card_constructor_batch_08.py:93`
- `_source_state`: `tools/test_cilog_action_label_extraction.py:69`, `tools/test_cilog_value_formatter_extraction.py:85`, `tools/test_date_display_helper_extraction.py:111`, `tools/test_date_helpers_extraction.py:118`, `tools/test_display_formatter_extraction.py:107`, `tools/test_log_serialization_helper_extraction.py:68`, `tools/test_numeric_parser_extraction.py:108`, `tools/test_text_normalizer_extraction.py:109`
- `_spina__client_due_meta`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:24013`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:39066`
- `_spina_dashboard_fetch_rows`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:36786`, `spina_app/tabs/dashboard.py:40`
- `_spina_route_adv_marker_for`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:8554`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:40627`
- `_stable`: `tools/test_base_theme_palette_batch_11.py:41`, `tools/test_display_ui_helper_batch_04.py:66`, `tools/test_legacy_dashboard_palette_batch_14.py:41`, `tools/test_theme_palette_helper_batch_05.py:42`, `tools/test_ui_display_helper_batch.py:75`
- `_state`: `tools/apply_client_area_uid_sync_phase2.py:19`, `tools/extract_date_display_helpers.py:128`, `tools/extract_date_helpers_module.py:183`, `tools/extract_display_formatters.py:94`, `tools/extract_numeric_parsers.py:130`, `tools/extract_text_normalizers.py:181`, `tools/test_cilog_money_formatter_extraction.py:60`
- `_stdlib_roots`: `tools/extract_date_helpers_module.py:104`, `tools/extract_text_normalizers.py:99`
- `_sync_selection`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:17076`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:36068`
- `_table_cols`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:4022`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:36808`
- `_test_applied`: `tools/test_cilog_value_formatter_extraction.py:151`, `tools/test_display_formatter_extraction.py:157`
- `_test_applied_state`: `tools/test_date_display_helper_extraction.py:180`, `tools/test_date_helpers_extraction.py:174`, `tools/test_numeric_parser_extraction.py:160`, `tools/test_text_normalizer_extraction.py:165`
- `_test_original`: `tools/test_cilog_value_formatter_extraction.py:120`, `tools/test_display_formatter_extraction.py:128`
- `_test_original_state`: `tools/test_date_display_helper_extraction.py:148`, `tools/test_date_helpers_extraction.py:142`, `tools/test_numeric_parser_extraction.py:129`, `tools/test_text_normalizer_extraction.py:133`
- `_today`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1714`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:1910`
- `_top_level_functions`: `tools/extract_date_display_helpers.py:40`, `tools/extract_date_helpers_module.py:44`, `tools/extract_display_formatters.py:39`, `tools/extract_numeric_parsers.py:39`, `tools/extract_text_normalizers.py:42`
- `_type_name`: `tools/test_base_theme_palette_batch_11.py:51`, `tools/test_display_data_helper_batch.py:150`, `tools/test_display_ui_helper_batch_04.py:76`, `tools/test_legacy_dashboard_palette_batch_14.py:51`, `tools/test_payment_schedule_normalizer_batch_06.py:36`, `tools/test_pure_helper_batch.py:124`, `tools/test_theme_palette_helper_batch_05.py:52`, `tools/test_ui_display_helper_batch.py:85`
- `_validate`: `tools/extract_cilog_value_formatter.py:48`, `tools/extract_log_serialization_helper.py:47`
- `_validate_date`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:29011`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:42690`
- `_validate_signature`: `tools/extract_date_display_helpers.py:81`, `tools/test_date_display_helper_extraction.py:44`, `tools/test_date_helpers_extraction.py:50`, `tools/test_display_formatter_extraction.py:43`, `tools/test_numeric_parser_extraction.py:45`, `tools/test_text_normalizer_extraction.py:44`
- `_widget_summary`: `tools/test_cash_control_ui_controls_batch_09.py:147`, `tools/test_cilog_ui_controls_batch_10.py:143`, `tools/test_collector_route_card_batch_13.py:118`, `tools/test_legacy_dashboard_card_batch_16.py:123`, `tools/test_ui_card_constructor_batch_08.py:133`
- `_wrap_text_to_width`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:22848`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:32738`
- `_write`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:26608`, `tools/extract_log_serialization_helper.py:105`
- `_write_fixture`: `tools/test_cilog_action_label_extraction.py:75`, `tools/test_cilog_money_formatter_extraction.py:89`, `tools/test_cilog_value_formatter_extraction.py:95`, `tools/test_date_display_helper_extraction.py:122`, `tools/test_date_helpers_extraction.py:129`, `tools/test_display_formatter_extraction.py:118`, `tools/test_log_serialization_helper_extraction.py:75`, `tools/test_numeric_parser_extraction.py:119`, `tools/test_text_normalizer_extraction.py:120`
- `_yview`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:17051`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:36053`
- `accept`: `spina_app/area_hierarchy_ui.py:245`, `spina_app/area_hierarchy_ui.py:439`
- `add_area`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7626`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:19992`
- `apply`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:30883`, `tools/apply_client_area_uid_sync_phase2.py:44`, `tools/apply_hierarchical_area_storage_phase1.py:62`, `tools/apply_hierarchical_area_ui_phase2.py:70`, `tools/extract_cilog_action_label.py:114`, `tools/extract_log_serialization_helper.py:117`, `tools/extract_pure_helper_batch.py:200`
- `apply_extraction`: `tools/extract_append_unique_text.py:101`, `tools/extract_cilog_diff_pairs.py:138`, `tools/extract_cilog_value_formatter.py:130`, `tools/extract_date_display_helpers.py:223`, `tools/extract_date_helpers_module.py:269`, `tools/extract_display_formatters.py:206`, `tools/extract_fmt_currency_module.py:156`, `tools/extract_merge_note_dict.py:110`, `tools/extract_note_dict_helper.py:112`, `tools/extract_numeric_parsers.py:209`, `tools/extract_text_normalizers.py:274`
- `atomic_write`: `tools/extract_append_unique_text.py:21`, `tools/extract_merge_note_dict.py:22`, `tools/extract_note_dict_helper.py:21`
- `audit`: `tools/audit_dynamic_sql_context.py:148`, `tools/audit_legacy_callback_usage.py:164`, `tools/audit_pass_only_exceptions.py:55`, `tools/audit_pg_command_callers.py:98`, `tools/audit_silent_ui_errors.py:151`, `tools/redundancy_audit.py:33`, `tools/spina_quality_audit.py:116`, `tools/ui_action_inventory.py:246`
- `build_plan`: `tools/cleanup_pg_json_read_dynamic_sql.py:66`, `tools/extract_append_unique_text.py:54`, `tools/extract_cilog_action_label.py:56`, `tools/extract_cilog_value_formatter.py:63`, `tools/extract_date_display_helpers.py:141`, `tools/extract_date_helpers_module.py:196`, `tools/extract_display_formatters.py:133`, `tools/extract_fmt_currency_module.py:112`, `tools/extract_log_serialization_helper.py:62`, `tools/extract_merge_note_dict.py:58`, `tools/extract_note_dict_helper.py:57`, `tools/extract_numeric_parsers.py:143`, `tools/extract_text_normalizers.py:194`, `tools/plan_modern_ui_pass_only_cleanup.py:160`
- `build_recommendations`: `tools/audit_legacy_callback_usage.py:135`, `tools/ui_action_inventory.py:213`
- `build_report`: `tools/audit_bare_except_context.py:90`, `tools/audit_blocking_ui_calls.py:138`, `tools/audit_pg_backup_action_flow.py:172`, `tools/cleanup_logger_fallback_pass_only.py:136`, `tools/cleanup_modern_ui_pass_only.py:118`, `tools/cleanup_pure_login_dialog_ui_pass_only.py:173`, `tools/plan_app_lifecycle_window_pass_only.py:160`, `tools/plan_logger_fallback_pass_only.py:136`, `tools/plan_login_dialog_pass_only.py:195`, `tools/plan_module_separation.py:211`, `tools/plan_pure_login_dialog_ui_pass_only.py:172`, `tools/plan_queue_empty_pass_only.py:139`, `tools/plan_remaining_pass_only_groups.py:152`, `tools/plan_ui_compatibility_pass_only.py:196`
- `cancel`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:24548`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:29124`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:42800`
- `capture_batch`: `tools/test_base_theme_palette_batch_11.py:128`, `tools/test_cash_control_ui_controls_batch_09.py:216`, `tools/test_cilog_ui_controls_batch_10.py:204`, `tools/test_client_route_tree_style_batch_12.py:166`, `tools/test_collector_route_card_batch_13.py:164`, `tools/test_display_data_helper_batch.py:171`, `tools/test_display_ui_helper_batch_04.py:178`, `tools/test_legacy_dashboard_card_batch_16.py:183`, `tools/test_legacy_dashboard_controls_batch_15.py:223`, `tools/test_legacy_dashboard_palette_batch_14.py:128`, `tools/test_payment_schedule_normalizer_batch_06.py:134`, `tools/test_pure_helper_batch.py:145`, `tools/test_theme_palette_helper_batch_05.py:129`, `tools/test_ui_card_constructor_batch_08.py:178`, `tools/test_ui_display_helper_batch.py:213`
- `capture_behavior`: `tools/test_append_unique_text_extraction.py:62`, `tools/test_merge_note_dict_extraction.py:75`, `tools/test_note_dict_helper_extraction.py:64`
- `close`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:834`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:879`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3834`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3917`, `spina_app/area_hierarchy_ui.py:259`, `spina_app/area_hierarchy_ui.py:431`, `spina_app/area_hierarchy_ui.py:707`
- `commit`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:873`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3907`
- `configure`: `tools/test_cash_control_feature_wave_21.py:39`, `tools/test_cash_control_ui_controls_batch_09.py:66`, `tools/test_cilog_ui_controls_batch_10.py:63`, `tools/test_client_route_tree_style_batch_12.py:44`, `tools/test_clients_feature_wave_19.py:37`, `tools/test_collectors_editor_wave_26.py:61`, `tools/test_display_ui_helper_batch_04.py:56`, `tools/test_legacy_dashboard_controls_batch_15.py:60`, `tools/test_legacy_dashboard_controls_batch_15.py:71`, `tools/test_ui_display_helper_batch.py:65`
- `context`: `tools/audit_dynamic_sql_context.py:117`, `tools/audit_pg_backup_action_flow.py:82`, `tools/cleanup_modern_ui_pass_only.py:49`
- `cursor`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:862`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3854`
- `defs`: `tools/test_client_info_logs_feature_wave_20.py:15`, `tools/test_clients_feature_wave_19.py:14`
- `delete`: `tools/test_cash_control_feature_wave_21.py:36`, `tools/test_collectors_editor_wave_26.py:101`, `tools/test_collectors_editor_wave_26.py:119`
- `delete_area`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7703`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:20025`
- `do_link`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:24502`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:30097`
- `ensure_space`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:23001`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:32891`
- `execute`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:716`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:865`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3774`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3859`
- `executemany`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:786`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:869`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3798`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3883`
- `export_range_template`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:25548`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:26343`
- `external_names`: `tools/extract_append_unique_text.py:38`, `tools/extract_merge_note_dict.py:39`, `tools/extract_note_dict_helper.py:38`
- `fetchall`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:815`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3826`
- `fetchmany`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:824`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3830`
- `fetchone`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:802`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3822`
- `get`: `tools/test_clients_feature_wave_19.py:28`, `tools/test_collectors_editor_wave_26.py:39`, `tools/test_collectors_editor_wave_26.py:94`, `tools/test_dashboard_feature_wave_17.py:26`, `tools/test_dashboard_visibility_wave_24.py:25`, `tools/test_legacy_dashboard_controls_batch_15.py:38`
- `get_children`: `tools/test_clients_feature_wave_19.py:53`, `tools/test_collectors_editor_wave_26.py:78`
- `get_client_info`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:6251`, `tools/test_clients_feature_wave_19.py:58`
- `handler_name`: `tools/plan_remaining_pass_only_groups.py:50`, `tools/plan_ui_compatibility_pass_only.py:117`
- `has_protected_context`: `tools/audit_dynamic_sql_context.py:128`, `tools/cleanup_modern_ui_pass_only.py:55`, `tools/plan_remaining_pass_only_groups.py:81`
- `has_protected_keyword`: `tools/audit_legacy_callback_usage.py:53`, `tools/ui_action_inventory.py:118`
- `insert`: `spina_app/area_hierarchy_ui.py:413`, `tools/test_collectors_editor_wave_26.py:96`, `tools/test_collectors_editor_wave_26.py:121`
- `inspect`: `tools/apply_client_area_uid_sync_phase2.py:31`, `tools/apply_hierarchical_area_storage_phase1.py:45`, `tools/apply_hierarchical_area_ui_phase2.py:33`, `tools/extract_pure_helper_batch.py:81`
- `is_pass_only`: `tools/plan_remaining_pass_only_groups.py:71`, `tools/plan_ui_compatibility_pass_only.py:134`
- `item`: `tools/test_clients_feature_wave_19.py:47`, `tools/test_collectors_editor_wave_26.py:80`
- `keys`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:572`, `tools/test_display_data_helper_batch.py:36`, `tools/test_display_data_helper_batch.py:50`
- `line_context`: `tools/audit_legacy_callback_usage.py:47`, `tools/ui_action_inventory.py:107`
- `load_helper`: `tools/test_append_unique_text_extraction.py:36`, `tools/test_merge_note_dict_extraction.py:50`, `tools/test_note_dict_helper_extraction.py:38`
- `load_list`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:31046`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:36393`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:36657`
- `main`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:31145`, `tools/add_optional_performance_logs.py:128`, `tools/apply_client_area_uid_sync_phase2.py:60`, `tools/apply_hierarchical_area_storage_phase1.py:75`, `tools/apply_hierarchical_area_ui_phase2.py:88`, `tools/audit_bare_except_context.py:114`, `tools/audit_blocking_ui_calls.py:162`, `tools/audit_dynamic_sql_context.py:211`, `tools/audit_legacy_callback_usage.py:216`, `tools/audit_pass_only_exceptions.py:128`, `tools/audit_patch_chains.py:188`, `tools/audit_pg_backup_action_flow.py:210`, `tools/audit_pg_command_callers.py:182`, `tools/audit_shadowed_definitions.py:167`, `tools/audit_silent_ui_errors.py:235`, `tools/cleanup_databank_export_callbacks.py:154`, `tools/cleanup_databank_export_ui_source.py:129`, `tools/cleanup_logger_fallback_pass_only.py:184`, `tools/cleanup_modern_ui_pass_only.py:162`, `tools/cleanup_neutral_appclass_init_patch.py:180`, `tools/cleanup_pg_json_read_dynamic_sql.py:142`, `tools/cleanup_pure_login_dialog_ui_pass_only.py:304`, `tools/cleanup_stale_databank_generated_blocks.py:337`, `tools/disable_full_daily_ledger.py:403`, `tools/extract_append_unique_text.py:133`, `tools/extract_cilog_action_label.py:126`, `tools/extract_cilog_diff_pairs.py:187`, `tools/extract_cilog_value_formatter.py:143`, `tools/extract_date_display_helpers.py:236`, `tools/extract_date_helpers_module.py:292`, `tools/extract_display_formatters.py:219`, `tools/extract_fmt_currency_module.py:177`, `tools/extract_log_serialization_helper.py:129`, `tools/extract_merge_note_dict.py:143`, `tools/extract_note_dict_helper.py:144`, `tools/extract_numeric_parsers.py:221`, `tools/extract_pure_helper_batch.py:248`, `tools/extract_text_normalizers.py:286`, `tools/inject_critical_path_logging.py:148`, `tools/inject_reports_pdf_logging.py:149`, `tools/inject_silent_ui_logging.py:352`, `tools/inspect_blocking_ui_context.py:159`, `tools/inspect_stale_databank_protected_context.py:36`, `tools/plan_app_lifecycle_window_pass_only.py:201`, `tools/plan_logger_fallback_pass_only.py:175`, `tools/plan_login_dialog_pass_only.py:243`, `tools/plan_modern_ui_pass_only_cleanup.py:199`, `tools/plan_module_separation.py:289`, `tools/plan_pure_login_dialog_ui_pass_only.py:227`, `tools/plan_queue_empty_pass_only.py:183`, `tools/plan_remaining_pass_only_groups.py:196`, `tools/plan_ui_compatibility_pass_only.py:267`, `tools/redundancy_audit.py:140`, `tools/remove_databank_export_controls.py:405`, `tools/spina_quality_audit.py:306`, `tools/spina_startup_diagnostics.py:82`, `tools/test_append_unique_text_extraction.py:85`, `tools/test_architecture_map.py:19`, `tools/test_base_theme_palette_batch_11.py:151`, `tools/test_cash_control_feature_wave_21.py:62`, `tools/test_cash_control_input_normalizer_batch_07.py:119`, `tools/test_cash_control_ui_controls_batch_09.py:259`, `tools/test_ci_acceleration.py:20`, `tools/test_cilog_action_label_extraction.py:139`, `tools/test_cilog_diff_pairs_extraction.py:82`, `tools/test_cilog_money_formatter_extraction.py:106`, `tools/test_cilog_ui_controls_batch_10.py:246`, `tools/test_cilog_value_formatter_extraction.py:169`, `tools/test_client_area_uid_sync_phase2.py:9`, `tools/test_client_info_logs_feature_wave_20.py:43`, `tools/test_client_route_tree_style_batch_12.py:204`, `tools/test_clients_feature_wave_19.py:74`, `tools/test_collector_route_card_batch_13.py:183`, `tools/test_collector_route_presentation_wave_23.py:28`, `tools/test_collectors_editor_wave_26.py:248`, `tools/test_collectors_summary_wave_22.py:23`, `tools/test_dashboard_feature_wave_17.py:128`, `tools/test_dashboard_visibility_wave_24.py:50`, `tools/test_date_display_helper_extraction.py:201`, `tools/test_date_helpers_extraction.py:201`, `tools/test_display_data_helper_batch.py:196`, `tools/test_display_formatter_extraction.py:174`, `tools/test_display_ui_helper_batch_04.py:220`, `tools/test_fmt_currency_extraction.py:33`, `tools/test_hierarchical_area_storage_phase1.py:126`, `tools/test_hierarchical_area_ui_phase2.py:49`, `tools/test_hierarchical_area_ui_phase2_source.py:13`, `tools/test_legacy_dashboard_card_batch_16.py:202`, `tools/test_legacy_dashboard_controls_batch_15.py:267`, `tools/test_legacy_dashboard_palette_batch_14.py:151`, `tools/test_log_serialization_helper_extraction.py:132`, `tools/test_login_palette_wave_25.py:23`, `tools/test_merge_note_dict_extraction.py:122`, `tools/test_module_separation_planner.py:36`, `tools/test_note_dict_helper_extraction.py:102`, `tools/test_numeric_parser_extraction.py:180`, `tools/test_payment_schedule_normalizer_batch_06.py:159`, `tools/test_pure_helper_batch.py:170`, `tools/test_reports_feature_wave_18.py:118`, `tools/test_reports_notes_dialog_wiring.py:13`, `tools/test_text_normalizer_extraction.py:185`, `tools/test_theme_palette_helper_batch_05.py:152`, `tools/test_ui_card_constructor_batch_08.py:203`, `tools/test_ui_display_helper_batch.py:248`, `tools/ui_action_inventory.py:303`
- `make_db`: `tools/test_hierarchical_area_storage_phase1.py:24`, `tools/test_hierarchical_area_ui_phase2.py:17`
- `map`: `tools/test_cash_control_ui_controls_batch_09.py:69`, `tools/test_cilog_ui_controls_batch_10.py:66`, `tools/test_client_route_tree_style_batch_12.py:47`, `tools/test_legacy_dashboard_controls_batch_15.py:74`
- `new_page_headers`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:22965`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:32855`
- `on_cancel`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:11607`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:12097`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:13013`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:26430`
- `on_ok`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:11581`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:12084`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:12992`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:26414`
- `pack`: `tools/test_cash_control_ui_controls_batch_09.py:44`, `tools/test_collector_route_card_batch_13.py:50`, `tools/test_collectors_editor_wave_26.py:49`, `tools/test_legacy_dashboard_card_batch_16.py:51`, `tools/test_ui_card_constructor_batch_08.py:64`
- `print_collector_route_daily_ledger`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:21410`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:31243`
- `print_full_daily_ledger`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:21622`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:31444`
- `print_report`: `tools/audit_patch_chains.py:176`, `tools/audit_shadowed_definitions.py:156`, `tools/cleanup_neutral_appclass_init_patch.py:164`, `tools/inject_silent_ui_logging.py:333`, `tools/redundancy_audit.py:108`, `tools/spina_quality_audit.py:271`
- `print_summary`: `tools/audit_legacy_callback_usage.py:180`, `tools/audit_silent_ui_errors.py:209`, `tools/ui_action_inventory.py:265`
- `push`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:26153`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:26160`
- `qualname`: `tools/audit_dynamic_sql_context.py:112`, `tools/audit_pg_backup_action_flow.py:38`
- `read_lines`: `tools/audit_pg_backup_action_flow.py:34`, `tools/plan_ui_compatibility_pass_only.py:113`
- `remove_existing_block`: `tools/add_optional_performance_logs.py:117`, `tools/inject_critical_path_logging.py:137`, `tools/inject_reports_pdf_logging.py:138`, `tools/remove_databank_export_controls.py:363`
- `rename_area`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:7657`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:20004`
- `restore_selected`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:31066`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:36421`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:36687`
- `rollback`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:876`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:3913`
- `run`: `tools/audit_patch_chains.py:130`, `tools/audit_shadowed_definitions.py:146`, `tools/cleanup_neutral_appclass_init_patch.py:130`, `tools/inject_silent_ui_logging.py:302`
- `save`: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:17289`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:17363`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:29018`, `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py:42711`
- `selection`: `tools/test_clients_feature_wave_19.py:45`, `tools/test_collectors_editor_wave_26.py:74`
- `set`: `tools/test_client_info_logs_feature_wave_20.py:29`, `tools/test_clients_feature_wave_19.py:30`, `tools/test_collectors_editor_wave_26.py:41`, `tools/test_dashboard_feature_wave_17.py:29`
- `source_for`: `tools/test_collector_route_presentation_wave_23.py:24`, `tools/test_collectors_editor_wave_26.py:23`, `tools/test_collectors_summary_wave_22.py:19`, `tools/test_dashboard_visibility_wave_24.py:17`, `tools/test_login_palette_wave_25.py:19`
- `top_level_functions`: `tools/extract_append_unique_text.py:33`, `tools/extract_merge_note_dict.py:34`, `tools/extract_note_dict_helper.py:33`, `tools/test_cash_control_feature_wave_21.py:21`
- `validate_plan`: `tools/extract_append_unique_text.py:87`, `tools/extract_merge_note_dict.py:97`, `tools/extract_note_dict_helper.py:98`
- `visit_AsyncFunctionDef`: `tools/audit_bare_except_context.py:58`, `tools/audit_blocking_ui_calls.py:104`, `tools/audit_pg_backup_action_flow.py:108`, `tools/inspect_blocking_ui_context.py:106`, `tools/plan_app_lifecycle_window_pass_only.py:126`, `tools/plan_logger_fallback_pass_only.py:101`, `tools/plan_login_dialog_pass_only.py:145`, `tools/plan_modern_ui_pass_only_cleanup.py:124`, `tools/plan_pure_login_dialog_ui_pass_only.py:88`, `tools/plan_queue_empty_pass_only.py:99`, `tools/plan_remaining_pass_only_groups.py:127`, `tools/plan_ui_compatibility_pass_only.py:153`
- `visit_Call`: `tools/audit_blocking_ui_calls.py:109`, `tools/audit_pg_backup_action_flow.py:131`, `tools/inspect_blocking_ui_context.py:109`
- `visit_ClassDef`: `tools/audit_bare_except_context.py:48`, `tools/audit_blocking_ui_calls.py:94`, `tools/audit_pg_backup_action_flow.py:100`, `tools/inspect_blocking_ui_context.py:96`, `tools/plan_app_lifecycle_window_pass_only.py:116`, `tools/plan_logger_fallback_pass_only.py:91`, `tools/plan_login_dialog_pass_only.py:150`, `tools/plan_modern_ui_pass_only_cleanup.py:114`, `tools/plan_pure_login_dialog_ui_pass_only.py:78`, `tools/plan_queue_empty_pass_only.py:89`, `tools/plan_remaining_pass_only_groups.py:117`, `tools/plan_ui_compatibility_pass_only.py:143`
- `visit_ExceptHandler`: `tools/audit_bare_except_context.py:61`, `tools/plan_login_dialog_pass_only.py:155`, `tools/plan_pure_login_dialog_ui_pass_only.py:93`, `tools/plan_queue_empty_pass_only.py:104`, `tools/plan_remaining_pass_only_groups.py:130`, `tools/plan_ui_compatibility_pass_only.py:158`
- `visit_FunctionDef`: `tools/audit_bare_except_context.py:53`, `tools/audit_blocking_ui_calls.py:99`, `tools/audit_pg_backup_action_flow.py:105`, `tools/inspect_blocking_ui_context.py:101`, `tools/plan_app_lifecycle_window_pass_only.py:121`, `tools/plan_logger_fallback_pass_only.py:96`, `tools/plan_login_dialog_pass_only.py:140`, `tools/plan_modern_ui_pass_only_cleanup.py:119`, `tools/plan_pure_login_dialog_ui_pass_only.py:83`, `tools/plan_queue_empty_pass_only.py:94`, `tools/plan_remaining_pass_only_groups.py:122`, `tools/plan_ui_compatibility_pass_only.py:148`
- `visit_Try`: `tools/plan_app_lifecycle_window_pass_only.py:131`, `tools/plan_logger_fallback_pass_only.py:106`, `tools/plan_modern_ui_pass_only_cleanup.py:127`
- `walk`: `spina_app/area_hierarchy_ops.py:205`, `spina_app/area_hierarchy_ui.py:79`, `spina_app/area_hierarchy_ui.py:93`, `spina_app/area_hierarchy_ui.py:105`, `tools/audit_pass_only_exceptions.py:65`

## Static-analysis limitations

- Dynamic imports and runtime-generated attribute names may not resolve.
- Callback and monkey-patch detection is static and may include false positives.
- SQL assembled from many runtime fragments may not reveal every table.
- Possible orphan symbols may still be called by reflection, Tkinter, plugins, or external code.
- Desktop smoke testing remains required before merging modularization changes.
