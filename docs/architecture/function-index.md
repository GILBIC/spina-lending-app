# SPINA Function and Class Index

Generated from commit `c09256778fb513c7841fae69843cb2613e02dac1`.

Scanned **194 Python files**, **77,290 lines**, and **2,462 symbols**.

> This is a static architecture map. Runtime callbacks and dynamic monkey patches can still require desktop testing.

## `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py`

- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_early_log** (function, lines 27–31, 5 lines, risk `reports`): Handles spina early log for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_storage_enabled** (function, lines 142–146, 5 lines, risk `support`): Handles spina pg storage enabled for the database feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_storage_conn** (function, lines 149–151, 3 lines, risk `support`): Handles spina pg storage conn for the database feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_storage_log** (function, lines 154–162, 9 lines, risk `reports`): Handles spina pg storage log for the database feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_ensure_storage_schema** (function, lines 165–180, 16 lines, risk `database_write`): Handles spina pg ensure storage schema for the database feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_app_dir** (function, lines 183–187, 5 lines, risk `support`): Handles spina pg app dir for the database feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_relpath** (function, lines 190–198, 9 lines, risk `filesystem`): Handles spina pg relpath for the database feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_json_table_for_path** (function, lines 201–208, 8 lines, risk `support`): Handles spina pg json table for path for the database feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_read_json** (function, lines 211–232, 22 lines, risk `database_read`): Handles spina pg read json for the database feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_write_json** (function, lines 235–270, 36 lines, risk `database_write`): Handles spina pg write json for the database feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_store_file_to_db** (function, lines 306–374, 69 lines, risk `database_write`): Handles spina pg store file to db for the database feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_store_client_picture_to_db** (function, lines 377–433, 57 lines, risk `database_write`): Handles spina pg store client picture to db for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_restore_client_picture_to_cache** (function, lines 436–471, 36 lines, risk `backup`): Handles spina pg restore client picture to cache for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_delete_client_picture_token** (function, lines 474–492, 19 lines, risk `database_write`): Handles spina pg delete client picture token for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_patch_reportlab_canvas_save** (function, lines 495–515, 21 lines, risk `reports`): Handles spina pg patch reportlab canvas save for the reports feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._PgCompatRow** (class, lines 526–545, 20 lines, risk `container`): SQLite Row-like object: supports row['name'], row[0], dict(row), row.get().
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._PgCompatRow.__init__** (method, lines 530–534, 5 lines, risk `support`): Handles init for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._PgCompatRow.__getitem__** (method, lines 536–539, 4 lines, risk `support`): Handles getitem for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._PgCompatRow.__iter__** (method, lines 541–542, 2 lines, risk `support`): Handles iter for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._PgCompatRow.keys** (method, lines 544–545, 2 lines, risk `support`): Handles keys for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_sql** (function, lines 554–612, 59 lines, risk `support`): Translate common SQLite SQL into PostgreSQL-compatible SQL.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_table_name_from_pragma** (function, lines 615–617, 3 lines, risk `support`): Handles spina pg table name from pragma for the database feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._PgCompatCursor** (class, lines 620–766, 147 lines, risk `container`): Groups PgCompatCursor for the database feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._PgCompatCursor.__init__** (method, lines 621–627, 7 lines, risk `database_read`): Handles init for the database feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._PgCompatCursor.connection** (method, lines 630–631, 2 lines, risk `support`): Handles connection for the database feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._PgCompatCursor._set_rows** (method, lines 633–636, 4 lines, risk `support`): Updates set rows for the database feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._PgCompatCursor.execute** (method, lines 638–706, 69 lines, risk `database_write`): Handles execute for the database feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._PgCompatCursor.executemany** (method, lines 708–722, 15 lines, risk `database_write`): Handles executemany for the database feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._PgCompatCursor.fetchone** (method, lines 724–735, 12 lines, risk `database_read`): Handles fetchone for the database feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._PgCompatCursor.fetchall** (method, lines 737–744, 8 lines, risk `database_read`): Handles fetchall for the database feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._PgCompatCursor.fetchmany** (method, lines 746–754, 9 lines, risk `database_read`): Handles fetchmany for the database feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._PgCompatCursor.close** (method, lines 756–760, 5 lines, risk `support`): Handles close for the database feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._PgCompatCursor.__iter__** (method, lines 762–763, 2 lines, risk `database_read`): Handles iter for the database feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._PgCompatCursor.__getattr__** (method, lines 765–766, 2 lines, risk `support`): Handles getattr for the database feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._PgCompatConnection** (class, lines 769–806, 38 lines, risk `container`): Groups PgCompatConnection for the database feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._PgCompatConnection.__init__** (method, lines 770–777, 8 lines, risk `support`): Handles init for the database feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._PgCompatConnection.in_transaction** (method, lines 780–782, 3 lines, risk `support`): Handles in transaction for the payments feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._PgCompatConnection.cursor** (method, lines 784–785, 2 lines, risk `support`): Handles cursor for the database feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._PgCompatConnection.execute** (method, lines 787–789, 3 lines, risk `database_read`): Handles execute for the database feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._PgCompatConnection.executemany** (method, lines 791–793, 3 lines, risk `database_write`): Handles executemany for the database feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._PgCompatConnection.commit** (method, lines 795–796, 2 lines, risk `database_write`): Handles commit for the database feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._PgCompatConnection.rollback** (method, lines 798–799, 2 lines, risk `database_write`): Handles rollback for the database feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._PgCompatConnection.close** (method, lines 801–802, 2 lines, risk `support`): Handles close for the database feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._PgCompatConnection.backup** (method, lines 804–806, 3 lines, risk `backup`): Handles backup for the backup feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_raise_sqlite_like** (function, lines 809–824, 16 lines, risk `support`): Raise sqlite3-style exceptions so existing catch blocks still work.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_connect_db** (function, lines 827–828, 2 lines, risk `support`): Handles spina pg connect db for the database feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._read_json_file** (function, lines 864–878, 15 lines, risk `filesystem`): Handles read json file for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._write_json_atomic** (function, lines 880–903, 24 lines, risk `filesystem`): Saves write json atomic for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.load_settings** (function, lines 905–937, 33 lines, risk `support`): Loads load settings for the settings feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.save_settings** (function, lines 939–945, 7 lines, risk `support`): Saves save settings for the settings feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._can_use_dir** (function, lines 947–961, 15 lines, risk `filesystem`): Best-effort check if a directory is writable (used for reports_root).
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.data_path** (function, lines 972–973, 2 lines, risk `support`): Handles data path for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.connect_db** (function, lines 975–1009, 35 lines, risk `database_read`): Central DB connector. PostgreSQL TEST MODE: ignores the old SQLite file path and connects to spina_db using psycopg through a SQLite-compatibility wrapper.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.run_write** (function, lines 1011–1029, 19 lines, risk `support`): Retry wrapper for SQLite write operations.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._is_write_sql** (function, lines 1031–1041, 11 lines, risk `support`): Handles is write sql for the database feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._sqlite_fetchall_in_chunks** (function, lines 1044–1070, 27 lines, risk `database_read`): Fetch all rows for SQL that contains 'IN ({ph})' placeholder. - Splits `items` into batches to avoid SQLite 'too many SQL variables'. - `sql_template` must include '{ph}' placeholder for question marks. - `tail_params` are appended after the batch params (e.g. BETWEEN ? AND ? values).
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina__split_payment_mode** (function, lines 1076–1092, 17 lines, risk `filesystem`): Handles spina split payment mode for the payments feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina__merge_payment_mode** (function, lines 1094–1103, 10 lines, risk `support`): Handles spina merge payment mode for the payments feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._open_path** (function, lines 1114–1158, 45 lines, risk `support`): Safely open a generated file/folder. v29 fix: Python 3.14 on Windows can crash hard with os.startfile() in some Tk/PDF workflows. Use subprocess instead so PDF generation does not close the app.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._init_logger** (function, lines 1173–1187, 15 lines, risk `support`): Handles init logger for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._log_exc** (function, lines 1191–1207, 17 lines, risk `reports`): Log exceptions to data/spina_app.log (best-effort).
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._log_suppressed_once** (function, lines 1216–1232, 17 lines, risk `reports`): Log a suppressed exception only once per key (to avoid log spam).
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._alert_user** (function, lines 1235–1250, 16 lines, risk `reports`): Best-effort UI alert. Safe even if Tk root isn't created yet.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._log_ignored** (function, lines 1258–1268, 11 lines, risk `support`): Log an otherwise-ignored exception once per key (to avoid log spam).
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._safe_filename_component** (function, lines 1274–1313, 40 lines, risk `filesystem`): Return a filesystem-safe single path component (no dirs).
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._write_loan_type_migration_review** (function, lines 1319–1424, 106 lines, risk `filesystem`): Write a CSV report of potentially misclassified loan types after legacy upgrades. Returns the report file path, or None if nothing was written.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._pick_writable_dir** (function, lines 1438–1457, 20 lines, risk `filesystem`): Return first directory we can create + write into (best-effort).
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._get_reports_root** (function, lines 1475–1483, 9 lines, risk `reports`): Return the configured reports folder, with a writable fallback.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._parse_ymd** (function, lines 1511–1521, 11 lines, risk `support`): Handles parse ymd for the utilities feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._oslp__load_prefs_json** (function, lines 1540–1550, 11 lines, risk `filesystem`): Handles oslp load prefs json for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.resolve_area_order_from_prefs** (function, lines 1552–1601, 50 lines, risk `support`): NO-UI resolver: - Reads order from data/ledger_prefs.json["areas_order"] - Case/whitespace-insensitive matching - Appends new areas (not in prefs) alphabetically Returns arranged list.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.split_area_main_sub** (function, lines 1605–1638, 34 lines, risk `support`): Split a single Area string into (main_area, sub_area). Backwards compatible: - If no separator is found, main_area = original, sub_area = "" - Supports separators like: 'Main - Sub', 'Main / Sub', 'Main | Sub', 'Main: Sub'
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.join_area_main_sub** (function, lines 1641–1659, 19 lines, risk `support`): Join main/sub into a single Area string using a consistent separator. - If sub_area is blank -> returns main_area - Else -> 'Main - Sub'
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._find_ttf** (function, lines 1744–1748, 5 lines, risk `support`): Retrieves find ttf for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._register_unicode_fonts** (function, lines 1750–1820, 71 lines, risk `reports`): Try to register a Unicode TTF so ReportLab can encode non-ASCII safely. Falls back to built-ins if none found.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._candidate_note_keys** (function, lines 1827–1840, 14 lines, risk `support`): Handles candidate note keys for the notes feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._resolve_note_key** (function, lines 1844–1855, 12 lines, risk `support`): Return an existing key in notes_dict matching 'name' using _candidate_note_keys. If none found, default to the original name.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._normalize_loan_type_value** (function, lines 1858–1865, 8 lines, risk `filesystem`): Handles normalize loan type value for the loans feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._note_scoped_prefix** (function, lines 1867–1868, 2 lines, risk `support`): Handles note scoped prefix for the notes feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._note_id_key** (function, lines 1870–1885, 16 lines, risk `support`): Stable notes keys that do NOT depend on client name. kind: - 'CID' : client_uid (per record) - 'PID' : person_uid (shared across Regular/7x7 when linked) Uses '|' separators to avoid colliding with legacy '<loan_type>::<name>' keys.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._note_type_key** (function, lines 1887–1902, 16 lines, risk `support`): Type-scoped key stable across name changes. If person_uid exists (linked), store type notes under: PT|<person_uid>|<loan_type_norm> This lets us retrieve the other loan type's notes without needing that row's client_uid.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._resolve_note_key_scoped** (function, lines 1905–1969, 65 lines, risk `support`): Resolve a notes_dict key for a client. Preferred (stable) keys: - shared scope: PID|<person_uid> (or CID|<client_uid> fallback) - type scope: PT|<person_uid>|<loan_type> (or CID|<client_uid> fallback) Legacy fallback keys remain supported: - shared: name - type: '<loan_type>::<name>' Uses candidate 
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._split_scoped_key** (function, lines 1973–1983, 11 lines, risk `support`): Return (loan_type_or_none, name) for keys that may be scoped like '7x7::Juan'
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._ensure_notes_dir** (function, lines 2000–2005, 6 lines, risk `support`): Handles ensure notes dir for the notes feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._load_client_notes** (function, lines 2007–2166, 160 lines, risk `support`): Load client notes safely (cached). - Primary: <APP_DIR>/data/client_notes.json - Fallback (legacy): <CWD>/data/client_notes.json - Shallow-merge (primary wins on conflicts) - Cached in-memory to avoid frequent disk reads. - Logs problems to data/spina_app.log and shows a one-time warning if unreadab
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._load_client_notes._warn_once** (nested_function, lines 2035–2046, 12 lines, risk `support`): Handles warn once for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._load_client_notes._safe_load_one** (nested_function, lines 2048–2106, 59 lines, risk `filesystem`): Handles safe load one for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._save_client_notes** (function, lines 2167–2200, 34 lines, risk `filesystem`): Save client notes atomically and refresh in-memory cache.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.get_client_note** (function, lines 2201–2251, 51 lines, risk `support`): Fetch a note for a client. scope: - 'shared' (default): shared notes (prefer person_uid/client_uid; legacy name fallback) - 'type': loan-type specific notes (prefer person_uid+loan_type or client_uid; legacy fallback) - 'effective': prefer type-specific if present, otherwise shared
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.set_client_note** (function, lines 2254–2312, 59 lines, risk `support`): Persist note for client. scope: - 'shared' (default): shared notes (prefer person_uid/client_uid; legacy name fallback) - 'type': loan-type specific notes (prefer person_uid+loan_type or client_uid; legacy fallback)
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.get_client_notes_in_range** (function, lines 2315–2390, 76 lines, risk `support`): Return list of (date, text) notes for 'name' between s and e inclusive. - Includes default (undated) note(s) as ("", text) first when present. - When include_type=True, includes loan-type specific notes for the current mode. - If include_other_type=True, also includes the other loan type (prefixed).
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._migrate_legacy_notes_by_name** (function, lines 2401–2476, 76 lines, risk `support`): Migrate legacy name-based notes (old_name and '<loan_type>::old_name') into stable-id keys. Use this when a client's name changes to avoid orphaning notes that were stored under the old name. Returns True if any changes were saved.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._parse_any_adv_range** (function, lines 2490–2507, 18 lines, risk `support`): Handles parse any adv range for the utilities feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._expand_range_inclusive** (function, lines 2509–2513, 5 lines, risk `support`): Handles expand range inclusive for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._safe_string** (function, lines 2517–2527, 11 lines, risk `support`): As a last resort, coerce to an encodable string for current font.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._load_ledger_prefs** (function, lines 2535–2540, 6 lines, risk `filesystem`): Loads load ledger prefs for the reports feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._save_ledger_prefs** (function, lines 2542–2548, 7 lines, risk `reports`): Saves save ledger prefs for the reports feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.parse_advance_ranges** (function, lines 2549–2656, 108 lines, risk `support`): Parse one or more ADV date ranges from a transaction description. Supported tags (whitespace/case-tolerant): - [ADV:YYYY-MM-DD..YYYY-MM-DD] (single range) - [ADV:YYYY-MM-DD,YYYY-MM-DD,YYYY-MM-DD] (explicit days) - [ADV:range;range;...] where range is either: * YYYY-MM-DD..YYYY-MM-DD * YYYY-MM-DD (si
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.parse_advance_ranges._is_date** (nested_function, lines 2591–2592, 2 lines, risk `support`): Handles is date for the payments feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.parse_advance_range** (function, lines 2658–2661, 4 lines, risk `support`): Backward-compatible helper: return first (start,end) ADV range if present.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._LockedCursor** (class, lines 2669–2746, 78 lines, risk `container`): Groups LockedCursor for the database feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._LockedCursor.__init__** (method, lines 2670–2672, 3 lines, risk `support`): Handles init for the database feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._LockedCursor.execute** (method, lines 2674–2696, 23 lines, risk `database_read`): Handles execute for the database feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._LockedCursor.executemany** (method, lines 2698–2720, 23 lines, risk `database_write`): Handles executemany for the database feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._LockedCursor.fetchone** (method, lines 2722–2724, 3 lines, risk `database_read`): Handles fetchone for the database feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._LockedCursor.fetchall** (method, lines 2726–2728, 3 lines, risk `database_read`): Handles fetchall for the database feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._LockedCursor.fetchmany** (method, lines 2730–2732, 3 lines, risk `database_read`): Handles fetchmany for the database feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._LockedCursor.close** (method, lines 2734–2739, 6 lines, risk `support`): Handles close for the database feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._LockedCursor.__iter__** (method, lines 2741–2743, 3 lines, risk `database_read`): Handles iter for the database feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._LockedCursor.__getattr__** (method, lines 2745–2746, 2 lines, risk `support`): Handles getattr for the database feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._LockedConnection** (class, lines 2749–2825, 77 lines, risk `container`): Groups LockedConnection for the database feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._LockedConnection.__init__** (method, lines 2750–2752, 3 lines, risk `support`): Handles init for the database feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._LockedConnection.cursor** (method, lines 2754–2757, 4 lines, risk `database_read`): Handles cursor for the database feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._LockedConnection.execute** (method, lines 2759–2781, 23 lines, risk `database_read`): Handles execute for the database feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._LockedConnection.executemany** (method, lines 2783–2805, 23 lines, risk `database_write`): Handles executemany for the database feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._LockedConnection.commit** (method, lines 2807–2811, 5 lines, risk `support`): Handles commit for the database feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._LockedConnection.commit._op** (nested_function, lines 2808–2810, 3 lines, risk `database_write`): Handles op for the database feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._LockedConnection.rollback** (method, lines 2813–2815, 3 lines, risk `database_write`): Handles rollback for the database feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._LockedConnection.close** (method, lines 2817–2822, 6 lines, risk `support`): Handles close for the database feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._LockedConnection.__getattr__** (method, lines 2824–2825, 2 lines, risk `support`): Handles getattr for the database feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB** (class, lines 2831–6616, 3786 lines, risk `container`): Groups LoanDB for the loans feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.__init__** (method, lines 2832–2859, 28 lines, risk `database_read`): Handles init for the loans feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._norm_lt** (method, lines 2869–2873, 5 lines, risk `filesystem`): Handles norm lt for the loans feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.add_pdf_header** (method, lines 2879–2898, 20 lines, risk `reports`): Reusable header for PDFs with logo, title, and current date.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._create_tables** (method, lines 2900–3800, 901 lines, risk `database_write`): Builds create tables for the loans feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._create_tables._table_cols** (nested_function, lines 2906–2916, 11 lines, risk `database_read`): Return set of column names for table _t (best-effort).
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._create_tables._ensure_column** (nested_function, lines 2918–2943, 26 lines, risk `database_read`): Add column only if missing. Returns True if we attempted and succeeded.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._create_tables._try_sql** (nested_function, lines 2945–2954, 10 lines, risk `database_read`): Execute SQL and log on failure.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._active_client_name_exists** (method, lines 3802–3831, 30 lines, risk `filesystem`): True if an active client already uses this exact visible name in the same loan type.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.add_client** (method, lines 3833–4013, 181 lines, risk `database_write`): Handles add client for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.add_client._norm_term** (nested_function, lines 3900–3918, 19 lines, risk `filesystem`): Handles norm term for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.add_client._norm_weekday** (nested_function, lines 3930–3942, 13 lines, risk `support`): Handles norm weekday for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.add_client._norm_dom** (nested_function, lines 3944–3951, 8 lines, risk `support`): Handles norm dom for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.update_client** (method, lines 4017–4315, 299 lines, risk `database_write`): Update a client (append-only history is written to client_history).
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.update_client._norm_term** (nested_function, lines 4092–4109, 18 lines, risk `filesystem`): Handles norm term for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.update_client._norm_weekday** (nested_function, lines 4132–4144, 13 lines, risk `support`): Handles norm weekday for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.update_client._norm_dom** (nested_function, lines 4146–4153, 8 lines, risk `support`): Handles norm dom for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.renew_client** (method, lines 4320–4547, 228 lines, risk `financial_calculation`): Renew a client (reloan). Updates the client row to a new cycle and records an event. - released_cash: cash actually released to the client for this renew (for display in reports). - new_principal: the new loan principal. If None/blank, defaults to released_cash.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.renew_client._ensure_renewals_table** (nested_function, lines 4401–4460, 60 lines, risk `financial_calculation`): Handles ensure renewals table for the loans feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.renew_client._do** (nested_function, lines 4465–4502, 38 lines, risk `database_write`): Handles do for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.get_renewal_stats** (method, lines 4549–4612, 64 lines, risk `financial_calculation`): Return (renew_count, last_released_cash, last_release_date). - renew_count counts renew events (not including the original loan release). - last_released_cash is the last recorded released cash; if none, returns None.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.delete_client** (method, lines 4615–4638, 24 lines, risk `database_write`): Delete a client and related transactions for the given loan_type (history is written).
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._ensure_archive_columns** (method, lines 4639–4656, 18 lines, risk `database_write`): Best-effort: ensure archive columns exist for older DBs.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.archive_client** (method, lines 4658–4680, 23 lines, risk `database_write`): Soft-delete: hide the client (keeps transactions/history).
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.restore_client** (method, lines 4682–4704, 23 lines, risk `database_write`): Restore a previously archived client by (name, loan_type).
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.restore_client_by_uid** (method, lines 4706–4724, 19 lines, risk `backup`): Restore a previously archived client by client_uid.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.get_archived_clients** (method, lines 4726–4756, 31 lines, risk `backup`): List archived clients for restore UI.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.get_unpaired_7x7_names** (method, lines 4764–4811, 48 lines, risk `financial_calculation`): Return 7x7 client names that have NO Regular record and are NOT linked. Used so 7x7-only clients can still be managed from the Regular view (appear at the bottom) and included in Collector Route prints. Rules: - loan_type must be '7x7' - there is no same-name Regular record - person_uid is blank/emp
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.fetch_all_clients** (method, lines 4814–4847, 34 lines, risk `filesystem`): Return list of dict rows for clients (optionally filtered by loan_type).
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.set_link_opt_out_by_uid** (method, lines 4855–4872, 18 lines, risk `database_write`): Persist opt-out flag so auto-link prompts can be declined.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.link_client_uids** (method, lines 4873–4959, 87 lines, risk `database_write`): Link two client rows (typically Regular + 7x7) by assigning the same person_uid. Safety rules: - Prevent linking the same row to itself. - Prevent linking two rows of the same loan_type (to avoid accidental merges). - Prevent merging two different existing person_uid groups (unlink first).
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.unlink_person_uid** (method, lines 4965–4990, 26 lines, risk `database_write`): Unlink all rows that share this person_uid (clears person_uid).
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._sync_transactions_for_client_uid** (method, lines 4998–5062, 65 lines, risk `database_write`): Best-effort repair for transaction rows tied to one client. Keeps `transactions.client_uid` and `transactions.name` aligned to the current client row. Returns the number of transaction rows updated.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.repair_transaction_identity_links** (method, lines 5064–5116, 53 lines, risk `database_write`): Best-effort global repair for transaction/client identity drift. - backfills missing transaction.client_uid from exact current (name, loan_type) - normalizes transaction.name from the current clients.name when client_uid is present Returns a small stats dict.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._log_client_history** (method, lines 5120–5158, 39 lines, risk `database_write`): Append-only audit entry. old_row/new_row are dicts or None.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._log_client_history._safe_json** (nested_function, lines 5133–5140, 8 lines, risk `support`): Handles safe json for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._log_transaction_history** (method, lines 5168–5237, 70 lines, risk `database_write`): Append-only audit entry for Data Bank transactions.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._log_transaction_history._safe_json** (nested_function, lines 5193–5200, 8 lines, risk `support`): Handles safe json for the payments feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._audit_parse_json_payload** (method, lines 5241–5261, 21 lines, risk `support`): Handles audit parse json payload for the utilities feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.get_audit_renewal_rows** (method, lines 5265–5321, 57 lines, risk `financial_calculation`): Return append-only RENEW audit rows.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._databank_day_close_bucket** (method, lines 5323–5325, 3 lines, risk `support`): Handles databank day close bucket for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._dayclose_norm_workflow** (method, lines 5327–5337, 11 lines, risk `support`): Handles dayclose norm workflow for the loans feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._dayclose_variance_status** (method, lines 5339–5346, 8 lines, risk `support`): Handles dayclose variance status for the loans feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.get_databank_daily_total** (method, lines 5348–5379, 32 lines, risk `database_read`): Retrieves get databank daily total for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.get_databank_day_close** (method, lines 5381–5412, 32 lines, risk `database_read`): Retrieves get databank day close for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.is_databank_day_closed** (method, lines 5414–5419, 6 lines, risk `support`): Handles is databank day closed for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB._append_databank_day_close_history** (method, lines 5421–5456, 36 lines, risk `database_write`): Handles append databank day close history for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.list_databank_day_close_history** (method, lines 5458–5482, 25 lines, risk `database_read`): Handles list databank day close history for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.list_databank_day_collectors** (method, lines 5484–5518, 35 lines, risk `database_read`): Handles list databank day collectors for the collectors feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.get_databank_day_collector_totals** (method, lines 5520–5544, 25 lines, risk `support`): Retrieves get databank day collector totals for the collectors feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.replace_databank_day_collectors** (method, lines 5546–5637, 92 lines, risk `database_write`): Handles replace databank day collectors for the collectors feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.set_databank_day_close** (method, lines 5639–5705, 67 lines, risk `database_write`): Updates set databank day close for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.reopen_databank_day** (method, lines 5707–5749, 43 lines, risk `database_write`): Handles reopen databank day for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.set_databank_day_workflow** (method, lines 5751–5798, 48 lines, risk `database_write`): Updates set databank day workflow for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.list_databank_day_close_records** (method, lines 5800–5854, 55 lines, risk `database_read`): Handles list databank day close records for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.ensure_area_exists** (method, lines 5863–5874, 12 lines, risk `database_write`): Insert area into master table if not present.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.add_area** (method, lines 5876–5878, 3 lines, risk `support`): Add a new area. Returns True if inserted or already exists.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.rename_area** (method, lines 5882–5924, 43 lines, risk `database_write`): Rename an area and update all clients that use it (all loan types). Logs client history.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.delete_area** (method, lines 5928–5964, 37 lines, risk `database_write`): Delete an area. If clear_clients True, clear that area from all clients (logs history).
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.add_or_update_transaction** (method, lines 5968–6069, 102 lines, risk `database_write`): Insert or update a transaction (Data Bank) row. Key: prefer (client_uid, loan_type, date); fallback to legacy (name, loan_type, date) - Populates `client_uid` when possible so linked profiles can see the same Data Bank rows. - Writes an append-only audit row into `transaction_history`.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.delete_transaction** (method, lines 6071–6125, 55 lines, risk `database_write`): Removes delete transaction for the payments feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.delete_transactions_for_day** (method, lines 6128–6370, 243 lines, risk `database_write`): Delete ALL Data Bank transaction rows for one calendar date. Safety behavior: - Validates YYYY-MM-DD. - Creates a JSON backup in data/day_delete_backups BEFORE deleting. - Deletes both Regular and 7x7 transactions for that date. - Clears the Data Bank close/collector-close lock rows for that date so
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.get_transaction** (method, lines 6373–6388, 16 lines, risk `database_read`): Retrieves get transaction for the payments feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.get_transaction_by_uid** (method, lines 6393–6408, 16 lines, risk `database_read`): Fetch a transaction by (client_uid, loan_type, date).
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.add_or_update_transaction_by_uid** (method, lines 6410–6525, 116 lines, risk `database_write`): Insert or update a transaction using client_uid as the stable key. Key: (client_uid, loan_type, date) - Automatically pulls the current client name from clients table. - Updates the stored `name` in transactions if the client was renamed. - Writes append-only audit rows into transaction_history.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.LoanDB.import_missing_clients_from_transactions** (method, lines 6530–6616, 87 lines, risk `database_write`): Ensure every (name, loan_type) in transactions has a matching row in clients. Older versions only tracked names (no loan_type). This version is multi-loan-type safe. For 7x7 loans, we default interest_rate to 0.0.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._is_advance_on** (function, lines 6685–6731, 47 lines, risk `database_read`): Return True if any transaction for `name` has an [ADV:s..e] tag that covers day_yyyy_mm_dd. Falls back quietly to False if anything goes wrong.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._adv_paid_on_dates_covering** (function, lines 6733–6787, 55 lines, risk `database_read`): Return sorted list of *payment dates* (YYYY-MM-DD) whose ADV tag covers `day_yyyy_mm_dd`. Rules: - We only look at transactions whose description contains an [ADV:...] tag. - We EXCLUDE the payment date itself (so ADV is shown only on the covered days, not on the payment day). - If multiple ADV paym
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_route_adv_marker_for** (function, lines 6790–6868, 79 lines, risk `filesystem`): Robust Collector Route ADV lookup for PostgreSQL test builds. Returns (True, adv_end_date) when an ADV range covers the ledger day. It is intentionally case-insensitive on name and supports client_uid fallback. The actual payment date is included when the ADV range covers it, so collector route can 
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._getv** (function, lines 6881–6890, 10 lines, risk `support`): Safe getter for dict / sqlite3.Row / objects.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._sum_paid_per_day** (function, lines 6894–6982, 89 lines, risk `support`): Sum payments per date in a way that matches the app's Data Bank behavior. - Data Bank updates are keyed by (name, loan_type, date) so normally there's only 1 row per date. - If legacy/duplicate rows exist, we treat the **last non-zero** payment as the effective payment. - We do NOT let later 0.00 "r
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._wrap_to_width** (function, lines 6984–6996, 13 lines, risk `support`): Handles wrap to width for the utilities feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.draw_notes_aligned** (function, lines 6998–7047, 50 lines, risk `support`): Draws: Note: YYYY-MM-DD wrapped note text (blank) continuation lines aligned under text column Returns the new y after drawing.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App** (class, lines 7053–15630, 8578 lines, risk `container`): Groups App for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._mode_filter** (method, lines 7056–7064, 9 lines, risk `filesystem`): Return loan_type filter value for DB queries (Regular / 7x7).
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._on_mode_change** (method, lines 7066–7088, 23 lines, risk `reports`): Refresh visible tables when the mode selector changes.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._access_prefs_path** (method, lines 7097–7100, 4 lines, risk `support`): Handles access prefs path for the authentication feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._load_user_role** (method, lines 7102–7114, 13 lines, risk `authentication`): Best-effort load of last used role. Not security—just convenience.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._save_user_role** (method, lines 7116–7144, 29 lines, risk `authentication`): Saves save user role for the authentication feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._users_db_path** (method, lines 7147–7150, 4 lines, risk `authentication`): Handles users db path for the authentication feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._hash_password_legacy** (method, lines 7151–7157, 7 lines, risk `authentication`): Handles hash password legacy for the payments feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._hash_password** (method, lines 7159–7195, 37 lines, risk `authentication`): Hash passwords using PBKDF2-HMAC-SHA256 by default. Legacy scheme supported for backward compatibility: - scheme: 'sha256_salt' (or 'legacy') uses SHA-256(salt + password) Stored records should include: - scheme: 'pbkdf2_sha256' (recommended) or 'sha256_salt' - iterations: integer (PBKDF2 only)
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._make_salt** (method, lines 7197–7206, 10 lines, risk `support`): Handles make salt for the authentication feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._default_password_for** (method, lines 7208–7210, 3 lines, risk `authentication`): Handles default password for for the payments feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._is_default_password_rec** (method, lines 7212–7230, 19 lines, risk `authentication`): True if this user's stored hash matches the known default password.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._must_change_password** (method, lines 7232–7257, 26 lines, risk `authentication`): Enforce password change if account is still using the known defaults.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._set_user_password** (method, lines 7259–7285, 27 lines, risk `authentication`): Update password hash+salt for user and clear must_change_password.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._force_change_password_dialog** (method, lines 7287–7405, 119 lines, risk `authentication`): Modal dialog that forces a password change. Returns True if changed.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._force_change_password_dialog._save** (nested_function, lines 7331–7359, 29 lines, risk `authentication`): Handles save for the payments feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._force_change_password_dialog._cancel** (nested_function, lines 7361–7369, 9 lines, risk `support`): Handles cancel for the payments feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._force_change_password_dialog._on_enter** (nested_function, lines 7374–7375, 2 lines, risk `support`): Handles on enter for the payments feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._save_users_db** (method, lines 7407–7428, 22 lines, risk `authentication`): Saves save users db for the authentication feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._load_users_db** (method, lines 7430–7500, 71 lines, risk `authentication`): Load users database from data/users.json. If missing, create defaults. Default accounts (created only if missing): - admin / admin123 -> Admin - encoder / encoder123 -> Encoder - viewer / viewer123 -> Viewer - system / system123 -> System
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._verify_login** (method, lines 7502–7541, 40 lines, risk `authentication`): Handles verify login for the authentication feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._load_last_user** (method, lines 7543–7550, 8 lines, risk `filesystem`): Loads load last user for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._save_last_user** (method, lines 7552–7580, 29 lines, risk `filesystem`): Saves save last user for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._prompt_login** (method, lines 7582–7707, 126 lines, risk `authentication`): Login dialog: returns (username, role) or (None, None) if cancelled.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._prompt_login._ok** (nested_function, lines 7631–7663, 33 lines, risk `authentication`): Handles ok for the authentication feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._prompt_login._cancel** (nested_function, lines 7665–7671, 7 lines, risk `support`): Handles cancel for the authentication feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._prompt_login._on_enter** (nested_function, lines 7676–7677, 2 lines, risk `support`): Handles on enter for the authentication feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._prompt_user_role** (method, lines 7710–7792, 83 lines, risk `authentication`): Simple role selector shown at startup.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._prompt_user_role._ok** (nested_function, lines 7747–7757, 11 lines, risk `support`): Handles ok for the authentication feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._prompt_user_role._cancel** (nested_function, lines 7759–7765, 7 lines, risk `support`): Handles cancel for the authentication feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._remove_role_overlays** (method, lines 7794–7807, 14 lines, risk `support`): Removes remove role overlays for the authentication feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._restore_main_tabs** (method, lines 7810–7827, 18 lines, risk `backup`): Handles restore main tabs for the backup feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._make_import_only_overlay** (method, lines 7829–7847, 19 lines, risk `ui_only`): Overlay that blocks tab interaction, leaving only an Import button.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._make_close_only_overlay** (method, lines 7849–7867, 19 lines, risk `ui_only`): Overlay that blocks tab interaction, leaving only Daily Close / Variance access.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.apply_role_access** (method, lines 7869–8005, 137 lines, risk `authentication`): Apply role-based UI restrictions.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._is_client_new** (method, lines 8007–8130, 124 lines, risk `reports`): Return True if client is NEW. Rules: - If 'new_until' is explicitly set in the DB: * If it's an empty string or unparsable -> treat as explicit OFF (return False). * If it's a valid date -> return (ledger_date <= new_until). No fallback. - Otherwise (no explicit 'new_until' value present): * If 'day
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._open_note_dialog** (method, lines 8134–8160, 27 lines, risk `reports`): Handles open note dialog for the notes feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._clear_preview** (method, lines 8163–8165, 3 lines, risk `support`): Handles clear preview for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._get_databank_focus_date** (method, lines 8168–8190, 23 lines, risk `support`): Retrieves get databank focus date for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._show_system_data_tab** (method, lines 8192–8201, 10 lines, risk `support`): Handles show system data tab for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._hide_system_data_tab** (method, lines 8203–8208, 6 lines, risk `support`): Handles hide system data tab for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._system_data_get_date** (method, lines 8210–8228, 19 lines, risk `support`): Handles system data get date for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._system_data_use_focus_date** (method, lines 8230–8237, 8 lines, risk `support`): Handles system data use focus date for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._system_data_refresh_summary** (method, lines 8239–8298, 60 lines, risk `support`): Handles system data refresh summary for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._system_data_refresh_summary._fmt_amt** (nested_function, lines 8244–8251, 8 lines, risk `support`): Handles fmt amt for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._system_data_open_close** (method, lines 8300–8310, 11 lines, risk `support`): Handles system data open close for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._system_data_open_history** (method, lines 8312–8316, 5 lines, risk `support`): Handles system data open history for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._system_data_open_records** (method, lines 8318–8322, 5 lines, risk `support`): Handles system data open records for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._system_data_print_report** (method, lines 8324–8328, 5 lines, risk `reports`): Handles system data print report for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._build_system_data_tab** (method, lines 8330–8375, 46 lines, risk `ui_only`): Builds build system data tab for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._prompt_current_password** (method, lines 8377–8390, 14 lines, risk `authentication`): Handles prompt current password for the payments feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._load_collectors_route_map** (method, lines 8393–8432, 40 lines, risk `filesystem`): Loads load collectors route map for the collectors feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._build_databank_collector_defaults_for_date** (method, lines 8434–8503, 70 lines, risk `database_read`): Builds build databank collector defaults for date for the collectors feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._build_databank_collector_defaults_for_date._norm_area** (nested_function, lines 8435–8439, 5 lines, risk `support`): Handles norm area for the collectors feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_databank_close_history_dialog** (method, lines 8505–8575, 71 lines, risk `ui_only`): Handles open databank close history dialog for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.print_databank_close_report** (method, lines 8578–8812, 235 lines, risk `filesystem`): Generates print databank close report for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_databank_close_dialog** (method, lines 8814–9464, 651 lines, risk `reports`): Handles open databank close dialog for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_databank_close_dialog._parse_amount** (nested_function, lines 8865–8870, 6 lines, risk `filesystem`): Handles parse amount for the utilities feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_databank_close_dialog._fmt_amount** (nested_function, lines 8872–8879, 8 lines, risk `support`): Handles fmt amount for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_databank_close_dialog._variance_status** (nested_function, lines 8881–8888, 8 lines, risk `support`): Handles variance status for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_databank_close_dialog._default_workflow** (nested_function, lines 8890–8895, 6 lines, risk `support`): Handles default workflow for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_databank_close_dialog._selected_split_index** (nested_function, lines 8992–8999, 8 lines, risk `support`): Handles selected split index for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_databank_close_dialog._clear_split_editor** (nested_function, lines 9001–9006, 6 lines, risk `support`): Handles clear split editor for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_databank_close_dialog._refresh_split_tree** (nested_function, lines 9008–9055, 48 lines, risk `ui_only`): Refreshes refresh split tree for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_databank_close_dialog._load_split_editor_from_selection** (nested_function, lines 9057–9069, 13 lines, risk `support`): Loads load split editor from selection for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_databank_close_dialog._upsert_split_row** (nested_function, lines 9071–9102, 32 lines, risk `support`): Handles upsert split row for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_databank_close_dialog._remove_split_row** (nested_function, lines 9104–9124, 21 lines, risk `support`): Removes remove split row for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_databank_close_dialog._load_route_collectors** (nested_function, lines 9126–9138, 13 lines, risk `support`): Loads load route collectors for the collectors feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_databank_close_dialog._save_split** (nested_function, lines 9140–9158, 19 lines, risk `support`): Saves save split for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_databank_close_dialog._apply_mode** (nested_function, lines 9160–9199, 40 lines, risk `ui_only`): Handles apply mode for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_databank_close_dialog._recalc** (nested_function, lines 9201–9223, 23 lines, risk `support`): Handles recalc for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_databank_close_dialog._load** (nested_function, lines 9225–9289, 65 lines, risk `support`): Handles load for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_databank_close_dialog._close_day** (nested_function, lines 9291–9350, 60 lines, risk `authentication`): Handles close day for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_databank_close_dialog._reopen_day** (nested_function, lines 9352–9379, 28 lines, risk `authentication`): Handles reopen day for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_databank_close_dialog._update_workflow** (nested_function, lines 9381–9410, 30 lines, risk `authentication`): Updates update workflow for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_databank_close_dialog._print_report** (nested_function, lines 9412–9419, 8 lines, risk `reports`): Generates print report for the reports feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_databank_close_dialog._save_route_copy_now** (nested_function, lines 9421–9444, 24 lines, risk `support`): Saves save route copy now for the collectors feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_databank_close_dialog._open_records_list** (nested_function, lines 9446–9447, 2 lines, risk `support`): Handles open records list for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_databank_close_records_dialog** (method, lines 9466–9689, 224 lines, risk `filesystem`): Handles open databank close records dialog for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_databank_close_records_dialog._coerce_date** (nested_function, lines 9471–9478, 8 lines, risk `support`): Handles coerce date for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_databank_close_records_dialog._fmt_amt** (nested_function, lines 9587–9594, 8 lines, risk `support`): Handles fmt amt for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_databank_close_records_dialog._selected_date** (nested_function, lines 9596–9601, 6 lines, risk `support`): Handles selected date for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_databank_close_records_dialog._load_records** (nested_function, lines 9603–9669, 67 lines, risk `filesystem`): Loads load records for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_databank_close_records_dialog._open_selected** (nested_function, lines 9671–9676, 6 lines, risk `support`): Handles open selected for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_databank_close_records_dialog._print_selected** (nested_function, lines 9678–9683, 6 lines, risk `reports`): Generates print selected for the reports feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._pick_missed_reason** (method, lines 9691–9835, 145 lines, risk `ui_only`): Modal checkbox dialog to choose one or more missed-payment reasons, plus optional 'Other' note. If 'Advance' is selected, you can enter a date range. Returns a single string (joined reasons + optional [ADV:s..e] tag) or None if cancelled.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._pick_missed_reason.set_enabled** (nested_function, lines 9742–9749, 8 lines, risk `ui_only`): Updates set enabled for the payments feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._pick_missed_reason.on_adv_toggle** (nested_function, lines 9751–9752, 2 lines, risk `support`): Handles on adv toggle for the payments feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._pick_missed_reason._parse_any_date** (nested_function, lines 9766–9786, 21 lines, risk `support`): Handles parse any date for the utilities feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._pick_missed_reason.on_ok** (nested_function, lines 9788–9812, 25 lines, risk `support`): Handles on ok for the payments feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._pick_missed_reason.on_cancel** (nested_function, lines 9814–9816, 3 lines, risk `support`): Handles on cancel for the payments feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._show_conflicts** (method, lines 9839–9863, 25 lines, risk `support`): Show areas assigned to multiple collectors.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._show_unassigned_areas** (method, lines 9865–9892, 28 lines, risk `support`): Show areas not assigned to any collector (plus any unknown route areas).
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._show_no_area_clients** (method, lines 9894–9918, 25 lines, risk `database_read`): Show clients that still have blank area (needs assignment).
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._delete_selected_collector** (method, lines 9921–9987, 67 lines, risk `filesystem`): Removes delete selected collector for the collectors feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._collector_editor_dialog** (method, lines 9989–10124, 136 lines, risk `ui_only`): Unified editor for Collector name + route areas + notes.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._collector_editor_dialog._summarize** (nested_function, lines 10042–10049, 8 lines, risk `support`): Handles summarize for the collectors feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._collector_editor_dialog.choose_areas** (nested_function, lines 10055–10060, 6 lines, risk `support`): Handles choose areas for the collectors feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._collector_editor_dialog.on_ok** (nested_function, lines 10080–10099, 20 lines, risk `support`): Handles on ok for the collectors feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._collector_editor_dialog.on_cancel** (nested_function, lines 10101–10108, 8 lines, risk `support`): Handles on cancel for the collectors feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._edit_selected_collector** (method, lines 10126–10217, 92 lines, risk `filesystem`): Handles edit selected collector for the collectors feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._add_collector** (method, lines 10219–10271, 53 lines, risk `filesystem`): Handles add collector for the collectors feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._walk_widgets** (method, lines 10273–10279, 7 lines, risk `support`): Handles walk widgets for the utilities feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._begin_cell_edit** (method, lines 10285–10426, 142 lines, risk `filesystem`): Create an Entry over the clicked (or remembered) day cell and save back to DB.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._begin_cell_edit._commit** (nested_function, lines 10420–10421, 2 lines, risk `support`): Handles commit for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._save_cell_edit** (method, lines 10429–10512, 84 lines, risk `filesystem`): Save an edited day-cell value into the DB (no undo/redo). - amount == 0 → prompt for reason (stored in description) - amount > 0 → clears description
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._remember_cell_click** (method, lines 10514–10532, 19 lines, risk `support`): Handles remember cell click for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.delete_selected_cell** (method, lines 10534–10621, 88 lines, risk `support`): Removes delete selected cell for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._mark_missed_for_selected** (method, lines 10625–10695, 71 lines, risk `filesystem`): Right-click action in Data Bank: set selected day as MISSED (0.0) with a reason.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_delete_day_dialog** (method, lines 10698–10838, 141 lines, risk `authentication`): Delete all Data Bank entries for one selected date, with backup + password confirmation.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._audit_money_text** (method, lines 10843–10850, 8 lines, risk `support`): Handles audit money text for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._audit_parse_date_filters** (method, lines 10852–10880, 29 lines, risk `support`): Handles audit parse date filters for the utilities feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._audit_set_today** (method, lines 10882–10890, 9 lines, risk `support`): Handles audit set today for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._audit_set_last7** (method, lines 10892–10901, 10 lines, risk `support`): Handles audit set last7 for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._audit_set_all** (method, lines 10903–10909, 7 lines, risk `support`): Handles audit set all for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._audit_tree_factory** (method, lines 10911–10927, 17 lines, risk `ui_only`): Handles audit tree factory for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._audit_set_detail_text** (method, lines 10930–10937, 8 lines, risk `ui_only`): Handles audit set detail text for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._audit_show_selected** (method, lines 10939–10994, 56 lines, risk `financial_calculation`): Handles audit show selected for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.__init__** (method, lines 10997–11157, 161 lines, risk `authentication`): Handles init for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._prepare_tk_shutdown** (method, lines 11161–11179, 19 lines, risk `support`): Cancel recurring Tk callbacks before the root interpreter is destroyed.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._destroy_root_safely** (method, lines 11181–11188, 8 lines, risk `support`): Finish pending ttk idle work, cancel timers, then destroy the root once.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._start_ui_queue_pump** (method, lines 11190–11230, 41 lines, risk `support`): Process UI-call requests from worker threads on the Tk main thread.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._start_ui_queue_pump._schedule_next** (nested_function, lines 11192–11203, 12 lines, risk `ui_only`): Handles schedule next for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._start_ui_queue_pump._pump** (nested_function, lines 11205–11228, 24 lines, risk `support`): Handles pump for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._ui_call** (method, lines 11232–11279, 48 lines, risk `support`): Call a UI function from any thread and wait for completion. - If called from the Tk main thread, runs immediately. - If called from a worker thread, marshals execution onto the Tk main thread. - Includes a timeout to avoid deadlocks when the UI is closing.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._ui_async** (method, lines 11281–11294, 14 lines, risk `ui_only`): Schedule a UI function to run on the Tk main thread (non-blocking).
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._patch_messagebox_threadsafe** (method, lines 11296–11339, 44 lines, risk `support`): Make tkinter.messagebox safe to call from worker threads.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._setup_style** (method, lines 11341–11477, 137 lines, risk `ui_only`): Centralized ttk styling. Goals: - cleaner spacing / typography - readable Treeviews - consistent Notebook tabs - best-effort HiDPI handling on Windows
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.toggle_theme** (method, lines 11483–11488, 6 lines, risk `support`): Handles toggle theme for the settings feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.set_theme** (method, lines 11490–11549, 60 lines, risk `ui_only`): Updates set theme for the settings feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._configure_tree_stripes** (method, lines 11555–11588, 34 lines, risk `ui_only`): Configure zebra striping tags on a ttk.Treeview based on current theme. Important: tag backgrounds override ttk style colors. Without this, Dark Mode can end up with light (white) row backgrounds + light foreground, which is hard to read.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._apply_tree_stripes_all** (method, lines 11590–11599, 10 lines, risk `ui_only`): Re-apply zebra striping for known Treeviews (called after theme switch).
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._mk_tk_entry** (method, lines 11603–11619, 17 lines, risk `ui_only`): Handles mk tk entry for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._find_postgres_exe** (method, lines 11624–11662, 39 lines, risk `filesystem`): Find pg_dump.exe / pg_restore.exe without requiring PostgreSQL bin in PATH.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._postgres_backup_dir** (method, lines 11664–11672, 9 lines, risk `backup`): Return/create the app backup folder.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._create_postgres_backup_file** (method, lines 11674–11757, 84 lines, risk `backup`): Create a full PostgreSQL backup using pg_dump custom format. The backup includes clients, payments, JSON rows, PDFs, and pictures because those are now stored in spina_db. Password is passed through PGPASSWORD, not printed on screen.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.backup_postgres_database** (method, lines 11759–11827, 69 lines, risk `backup`): UI handler for the Backup button.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.backup_postgres_database._success** (nested_function, lines 11783–11799, 17 lines, risk `support`): Handles success for the backup feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.backup_postgres_database._error** (nested_function, lines 11801–11815, 15 lines, risk `support`): Handles error for the backup feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._postgres_cfg** (method, lines 11831–11843, 13 lines, risk `support`): Return PostgreSQL connection settings used by this test build.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._pg_env** (method, lines 11845–11853, 9 lines, risk `filesystem`): Handles pg env for the database feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._format_bytes** (method, lines 11855–11865, 11 lines, risk `support`): Handles format bytes for the utilities feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._list_postgres_backup_files** (method, lines 11867–11889, 23 lines, risk `backup`): Return backup files from the app backups folder, newest first.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._verify_postgres_backup_file** (method, lines 11891–11924, 34 lines, risk `backup`): Verify a PostgreSQL custom backup by reading its table of contents.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._run_pg_command** (method, lines 11926–11953, 28 lines, risk `support`): Run PostgreSQL command-line tools with hidden password.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._restore_backup_to_test_database** (method, lines 11955–11990, 36 lines, risk `backup`): Restore selected backup into spina_restore_test only; never overwrites live spina_db.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._restore_backup_to_test_database._check_cancel** (nested_function, lines 11977–11982, 6 lines, risk `support`): Handles check cancel for the backup feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_backup_history_window** (method, lines 11992–12173, 182 lines, risk `backup`): Show backup files and provide verify/restore-test actions.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._select_side_tab** (method, lines 12178–12191, 14 lines, risk `support`): Handles select side tab for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._tk_button_hover** (method, lines 12199–12210, 12 lines, risk `ui_only`): Small hover helper for plain tk buttons/labels.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._set_mode** (method, lines 12213–12235, 23 lines, risk `filesystem`): Fast switch between Regular and 7x7 from the modern segmented control.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._build_header** (method, lines 12240–12408, 169 lines, risk `authentication`): Modern top header: app identity + fast Regular/7x7 switch + app actions.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._refresh_user_header** (method, lines 12410–12420, 11 lines, risk `authentication`): Refreshes refresh user header for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.switch_account** (method, lines 12422–12467, 46 lines, risk `authentication`): Handles switch account for the authentication feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_settings_dialog** (method, lines 12469–12756, 288 lines, risk `authentication`): App settings (local-only).
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_settings_dialog._browse_reports** (nested_function, lines 12535–12545, 11 lines, risk `reports`): Handles browse reports for the reports feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_settings_dialog._save_auto_close_setting_only** (nested_function, lines 12581–12598, 18 lines, risk `support`): Saves save auto close setting only for the settings feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_settings_dialog._run_auto_close_now** (nested_function, lines 12600–12613, 14 lines, risk `support`): Handles run auto close now for the settings feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_settings_dialog._open_target** (nested_function, lines 12662–12672, 11 lines, risk `support`): Handles open target for the settings feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_settings_dialog._test_reports** (nested_function, lines 12688–12701, 14 lines, risk `reports`): Handles test reports for the reports feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_settings_dialog._save** (nested_function, lines 12703–12738, 36 lines, risk `reports`): Handles save for the settings feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._build_data_tab** (method, lines 12762–12828, 67 lines, risk `ui_only`): Builds build data tab for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.goto_current_month** (method, lines 12831–12835, 5 lines, risk `support`): Handles goto current month for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.prev_month** (method, lines 12836–12839, 4 lines, risk `ui_only`): Handles prev month for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.next_month** (method, lines 12840–12843, 4 lines, risk `ui_only`): Handles next month for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.refresh_data_grid** (method, lines 12847–13117, 271 lines, risk `ui_only`): Refreshes refresh data grid for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.refresh_data_grid._yview** (nested_function, lines 12904–12914, 11 lines, risk `support`): Handles yview for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.refresh_data_grid._sync_selection** (nested_function, lines 12929–12943, 15 lines, risk `ui_only`): Handles sync selection for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.refresh_data_grid._on_sel_left** (nested_function, lines 12945–12946, 2 lines, risk `support`): Handles on sel left for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.refresh_data_grid._on_sel_right** (nested_function, lines 12948–12949, 2 lines, risk `support`): Handles on sel right for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.refresh_data_grid._focus_right_from_left** (nested_function, lines 12958–12966, 9 lines, risk `ui_only`): Handles focus right from left for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.refresh_data_grid._focus_left_from_right** (nested_function, lines 12968–12976, 9 lines, risk `ui_only`): Handles focus left from right for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.on_day_double** (method, lines 13118–13193, 76 lines, risk `filesystem`): Handles on day double for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.on_day_double.save** (nested_function, lines 13142–13181, 40 lines, risk `ui_only`): Handles save for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.on_day_double._close_editor** (nested_function, lines 13184–13189, 6 lines, risk `support`): Handles close editor for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._start_edit** (method, lines 13195–13265, 71 lines, risk `filesystem`): Handles start edit for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._start_edit.save** (nested_function, lines 13216–13254, 39 lines, risk `ui_only`): Handles save for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._start_edit._close_editor** (nested_function, lines 13256–13261, 6 lines, risk `support`): Handles close editor for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._build_reports_tab** (method, lines 13268–13605, 338 lines, risk `filesystem`): Builds build reports tab for the reports feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._build_reports_tab._sync_reports_range** (nested_function, lines 13291–13311, 21 lines, risk `reports`): Handles sync reports range for the reports feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._build_reports_tab._apply_report_range_from_fields** (nested_function, lines 13313–13338, 26 lines, risk `reports`): Handles apply report range from fields for the reports feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._build_reports_tab._pick_reports_range** (nested_function, lines 13340–13342, 3 lines, risk `reports`): Handles pick reports range for the reports feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._build_reports_tab._clear_reports_range** (nested_function, lines 13344–13351, 8 lines, risk `reports`): Handles clear reports range for the reports feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._build_reports_tab._save_reports_page_size** (nested_function, lines 13391–13398, 8 lines, risk `reports`): Saves save reports page size for the reports feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._build_reports_tab._toggle_reports_notes_panel** (nested_function, lines 13498–13550, 53 lines, risk `reports`): Handles toggle reports notes panel for the reports feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.refresh_reports** (method, lines 13608–13714, 107 lines, risk `reports`): Refreshes refresh reports for the reports feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.refresh_reports._display_loan_type_label** (nested_function, lines 13635–13642, 8 lines, risk `support`): Handles display loan type label for the loans feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_report_generation_log** (method, lines 13718–13739, 22 lines, risk `filesystem`): Open the global Generate Report log file/folder.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.generate_pdf_selected** (method, lines 13741–13998, 258 lines, risk `reports`): Generate a client statement PDF without freezing the UI.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.generate_pdf_selected._effective_cycle_start** (nested_function, lines 13753–13797, 45 lines, risk `filesystem`): Normalize the current cycle start the same way the client screen and report body do. This prevents renewed clients from inheriting a stale earlier report start range.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.generate_pdf_selected._work** (nested_function, lines 13917–13977, 61 lines, risk `filesystem`): Handles work for the reports feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.generate_pdf_selected._done** (nested_function, lines 13979–13989, 11 lines, risk `support`): Handles done for the reports feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.generate_pdf_selected._err** (nested_function, lines 13991–13996, 6 lines, risk `support`): Handles err for the reports feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._get_report_note_text** (method, lines 14001–14012, 12 lines, risk `reports`): Retrieves get report note text for the reports feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._set_report_note_text** (method, lines 14014–14043, 30 lines, risk `reports`): Updates set report note text for the reports feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._save_dated_note_for_client** (method, lines 14045–14084, 40 lines, risk `reports`): Saves save dated note for client for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._auto_load_report_note** (method, lines 14087–14117, 31 lines, risk `reports`): Handles auto load report note for the reports feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._get_selected_report_client** (method, lines 14121–14129, 9 lines, risk `reports`): Retrieves get selected report client for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._save_report_note_for_client** (method, lines 14131–14169, 39 lines, risk `reports`): Saves save report note for client for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._load_report_note_for_client** (method, lines 14172–14201, 30 lines, risk `reports`): Loads load report note for client for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._import_from_excel_entry** (method, lines 14208–14249, 42 lines, risk `support`): Import payments from Excel. Supports: 1) Date-grid templates (first row has 'Client Name' + date columns like YYYY-MM-DD) via _import_from_excel_core() 2) One-day Daily Collection templates (Client | Payment | Reason), optionally grouped by [AREA] rows Notes: - Unknown clients are skipped (to avoid 
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._import_from_excel_entry_worker** (method, lines 14251–14647, 397 lines, risk `support`): Worker for _import_from_excel_entry (runs off the Tk main thread).
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._import_from_excel_entry_worker._norm** (nested_function, lines 14310–14312, 3 lines, risk `filesystem`): Handles norm for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._import_from_excel_entry_worker._looks_like_date_header** (nested_function, lines 14314–14326, 13 lines, risk `support`): Handles looks like date header for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._import_from_excel_entry_worker._parse_sheet** (nested_function, lines 14425–14558, 134 lines, risk `filesystem`): Handles parse sheet for the utilities feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._import_encoder_batch** (method, lines 14649–15068, 420 lines, risk `filesystem`): Import One-Day Encoder exports (.jsonl or .csv) into the DB. - Dedupe by record_id (preferred) or a content hash fallback - Unknown clients are skipped (no auto-create) - Advances are stored via description tag: [ADV:s..e; s..e; ...] (supports multiple ranges)
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._import_encoder_batch._canon_lt** (nested_function, lines 14670–14674, 5 lines, risk `filesystem`): Handles canon lt for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._import_encoder_batch._is_date** (nested_function, lines 14676–14678, 3 lines, risk `support`): Handles is date for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._import_encoder_batch._adv_tag_from_ranges** (nested_function, lines 14680–14693, 14 lines, risk `support`): Handles adv tag from ranges for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._import_encoder_batch._ilog** (nested_function, lines 14742–14746, 5 lines, risk `support`): Handles ilog for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._import_from_excel_core** (method, lines 15070–15235, 166 lines, risk `database_read`): Auto-detect payments and reasons from Excel. Rules: " First row = headers. Must include 'Client Name' and at least one date column. " A date column can be an Excel date/datetime or a string 'YYYY-MM-DD'. " If a cell under a date column is numeric (or numeric-looking text): that's the amount. " If a 
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._import_from_excel_core._parse_date_header** (nested_function, lines 15089–15100, 12 lines, risk `support`): Handles parse date header for the utilities feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._import_from_excel_core._to_number** (nested_function, lines 15102–15118, 17 lines, risk `filesystem`): Handles to number for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._import_from_excel_core._is_text_reason** (nested_function, lines 15120–15127, 8 lines, risk `support`): Handles is text reason for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._build_clients_tab** (method, lines 15237–15392, 156 lines, risk `ui_only`): Builds build clients tab for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App._refresh_area_dropdowns** (method, lines 15398–15414, 17 lines, risk `ui_only`): Refresh any area dropdowns (best-effort).
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_areas_manager** (method, lines 15416–15577, 162 lines, risk `ui_only`): Open the Areas manager window (create/rename/delete areas).
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_areas_manager._refresh** (nested_function, lines 15462–15474, 13 lines, risk `support`): Handles refresh for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_areas_manager._selected** (nested_function, lines 15476–15483, 8 lines, risk `support`): Handles selected for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_areas_manager._on_select** (nested_function, lines 15485–15492, 8 lines, risk `support`): Handles on select for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_areas_manager.add_area** (nested_function, lines 15499–15509, 11 lines, risk `support`): Handles add area for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_areas_manager.rename_area** (nested_function, lines 15511–15530, 20 lines, risk `support`): Handles rename area for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_areas_manager.delete_area** (nested_function, lines 15532–15554, 23 lines, risk `support`): Removes delete area for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.open_areas_manager._on_close** (nested_function, lines 15563–15574, 12 lines, risk `support`): Handles on close for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.App.set_area_for_selected_clients** (method, lines 15579–15630, 52 lines, risk `reports`): Set one area for all selected clients in the Clients tab (current mode only).
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._build_collectors_tab** (function, lines 15741–16087, 347 lines, risk `ui_only`): Collector's Route UI (organized + obvious selection + inline edit). Adds: - Obvious selection column (radio in single-select, checkbox in multi-select) - Per-row Actions column (View / Edit / Delete) - Multi-select bulk bar (Delete / Export / Clear) - Inline edit in the right-side panel (name + area
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._build_collectors_tab._set_sort** (nested_function, lines 15865–15875, 11 lines, risk `support`): Updates set sort for the collectors feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._build_collectors_tab._popup** (nested_function, lines 15938–15953, 16 lines, risk `ui_only`): Handles popup for the collectors feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._build_collectors_tab._on_search** (nested_function, lines 16069–16073, 5 lines, risk `support`): Handles on search for the collectors feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._collectors_name_from_values** (function, lines 16091–16134, 44 lines, risk `ui_only`): Return the collector name from a Treeview row values tuple. Backwards compatible with older layouts: - Old layout: first value is the collector name. - New layout: first value is a select marker (radio/checkbox/bullet), second is the collector name.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_multi_toggle** (function, lines 16154–16176, 23 lines, risk `support`): Handles on collectors multi toggle for the collectors feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_tree_click** (function, lines 16180–16271, 92 lines, risk `filesystem`): Handle clicks in Sel + Actions columns.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._collectors_delete_selected** (function, lines 16273–16324, 52 lines, risk `filesystem`): Handles collectors delete selected for the collectors feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._collectors_export_selected** (function, lines 16326–16379, 54 lines, risk `filesystem`): Handles collectors export selected for the collectors feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._collectors_save_inline_edit** (function, lines 16386–16495, 110 lines, risk `filesystem`): Save inline edits to collectors.json (atomic), then refresh UI.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._collectors_areas_drag_start** (function, lines 16503–16507, 5 lines, risk `support`): Handles collectors areas drag start for the collectors feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._collectors_areas_drag_motion** (function, lines 16509–16527, 19 lines, risk `ui_only`): Handles collectors areas drag motion for the collectors feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._collectors_areas_drag_end** (function, lines 16529–16594, 66 lines, risk `support`): Handles collectors areas drag end for the collectors feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._collectors_areas_drag_end._on_collectors_tree_wheel** (nested_function, lines 16534–16549, 16 lines, risk `support`): Ensure mousewheel scroll works on Collector Route list.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._collectors_areas_drag_end._schedule_collectors_refresh** (nested_function, lines 16551–16568, 18 lines, risk `ui_only`): Debounce refresh_collectors while typing in Search.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._collectors_areas_drag_end._clear_collectors_search_filters** (nested_function, lines 16570–16594, 25 lines, risk `support`): Handles clear collectors search filters for the collectors feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select** (function, lines 16597–19601, 3005 lines, risk `ui_only`): Populate the right-side details panel for the selected collector.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select._populate_collector_details** (nested_function, lines 16655–16754, 100 lines, risk `support`): Update the right panel: selected name, stats, areas tree, notes.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select._save_selected_collector_notes** (nested_function, lines 16756–16784, 29 lines, risk `support`): Save Notes from the right panel to collectors.json (atomic).
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select._save_collector_notes** (nested_function, lines 16786–16830, 45 lines, risk `filesystem`): Internal: update one collector's notes in collectors.json.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select._refresh_collectors_table** (nested_function, lines 16832–16838, 7 lines, risk `support`): Backward-compatible alias for older code paths.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select._add_collector_dialog** (nested_function, lines 16840–16884, 45 lines, risk `filesystem`): Legacy dialog-based add; now writes the SAME dict schema as the main Collectors tab.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select._edit_collector_dialog** (nested_function, lines 16886–16961, 76 lines, risk `filesystem`): Legacy dialog-based edit; now edits the main collectors.json dict schema.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select._delete_collector** (nested_function, lines 16963–17023, 61 lines, risk `filesystem`): Legacy delete; now deletes from the main collectors.json dict schema.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select.print_collector_route_daily_ledger** (nested_function, lines 17025–17235, 211 lines, risk `filesystem`): Print the SELECTED collector's route using the same 3-column Daily Collection Ledger layout as `print_full_daily_ledger`, but ONLY for that collector's areas (no 'arrange all areas' step). - Uses selection() first (more reliable than focus()). - Reads collectors.json in multiple historical schemas. 
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select.print_full_daily_ledger** (nested_function, lines 17237–19601, 2365 lines, risk `financial_calculation`): Print a 3-column DAILY COLLECTION LEDGER with a small UI to change: - Ledger Date - Paper size and orientation - Areas order (arrange ALL areas)
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select.print_full_daily_ledger._fetch_clients_for** (nested_function, lines 17282–17289, 8 lines, risk `support`): Loads fetch clients for for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select.print_full_daily_ledger._s** (nested_function, lines 17312–17312, 1 lines, risk `support`): Handles s for the collectors feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select.print_full_daily_ledger._options_dialog** (nested_function, lines 17317–17378, 62 lines, risk `ui_only`): Handles options dialog for the collectors feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select.print_full_daily_ledger._options_dialog._ok** (nested_function, lines 17356–17358, 3 lines, risk `support`): Handles ok for the collectors feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select.print_full_daily_ledger._options_dialog._cancel** (nested_function, lines 17359–17361, 3 lines, risk `support`): Handles cancel for the collectors feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select.print_full_daily_ledger._arrange_areas_dialog** (nested_function, lines 17381–17454, 74 lines, risk `reports`): Handles arrange areas dialog for the collectors feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select.print_full_daily_ledger._arrange_areas_dialog._move** (nested_function, lines 17414–17427, 14 lines, risk `ui_only`): Handles move for the collectors feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select.print_full_daily_ledger._arrange_areas_dialog._ok** (nested_function, lines 17436–17437, 2 lines, risk `support`): Handles ok for the collectors feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select.print_full_daily_ledger._arrange_areas_dialog._cancel** (nested_function, lines 17438–17439, 2 lines, risk `support`): Handles cancel for the collectors feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select.print_full_daily_ledger._wrap_text_to_width** (nested_function, lines 18463–18490, 28 lines, risk `support`): Handles wrap text to width for the collectors feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select.print_full_daily_ledger._wrap_text_to_width._fits** (nested_function, lines 18468–18468, 1 lines, risk `support`): Handles fits for the collectors feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select.print_full_daily_ledger._draw_page_number** (nested_function, lines 18492–18498, 7 lines, risk `support`): Handles draw page number for the collectors feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select.print_full_daily_ledger._draw_final_footer** (nested_function, lines 18500–18515, 16 lines, risk `support`): Handles draw final footer for the collectors feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select.print_full_daily_ledger._draw_global_header** (nested_function, lines 18516–18561, 46 lines, risk `support`): Handles draw global header for the collectors feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select.print_full_daily_ledger.new_page_headers** (nested_function, lines 18580–18610, 31 lines, risk `support`): Handles new page headers for the collectors feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select.print_full_daily_ledger.ensure_space** (nested_function, lines 18616–18634, 19 lines, risk `support`): Handles ensure space for the collectors feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina__client_schedule_anchor** (function, lines 19612–19625, 14 lines, risk `support`): Handles spina client schedule anchor for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina__client_due_meta** (function, lines 19628–19692, 65 lines, risk `support`): Return (day_due_label, due_today_bool) using stored schedule fields when present.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.refresh_clients** (function, lines 19694–19956, 263 lines, risk `filesystem`): Refresh the Clients tab table from the database, honoring the search box.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.refresh_clients.delete_client_selected** (nested_function, lines 19792–19825, 34 lines, risk `reports`): Removes delete client selected for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.refresh_clients.renew_client_selected** (nested_function, lines 19828–19894, 67 lines, risk `financial_calculation`): Renew (reloan) the selected client and update the client row.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.refresh_clients.open_client_history_dialog** (nested_function, lines 19897–19907, 11 lines, risk `support`): Open the richer audit-style history dialog for the selected client.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.refresh_clients.add_client_dialog** (nested_function, lines 19910–19928, 19 lines, risk `reports`): Handles add client dialog for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.refresh_clients.on_client_edit** (nested_function, lines 19930–19956, 27 lines, risk `reports`): Handles on client edit for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients** (function, lines 19962–21949, 1988 lines, risk `filesystem`): Auto-suggest linking when a matching client exists in the other loan type. - YES links both rows (same person_uid). - NO sets link_opt_out=1 for BOTH rows so you won't be asked again from either side, unless you manually link later.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.link_selected_client** (nested_function, lines 20050–20173, 124 lines, risk `ui_only`): Manually link the selected client to another loan type record.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.link_selected_client.do_link** (nested_function, lines 20117–20161, 45 lines, risk `support`): Handles do link for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.link_selected_client.cancel** (nested_function, lines 20163–20164, 2 lines, risk `support`): Handles cancel for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.unlink_selected_client** (nested_function, lines 20175–20204, 30 lines, risk `support`): Unlink the selected client (clears person_uid for the whole link group).
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.import_missing** (nested_function, lines 20206–20209, 4 lines, risk `reports`): Handles import missing for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.import_from_excel** (nested_function, lines 20211–20272, 62 lines, risk `database_read`): Handles import from excel for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.export_monthly_template** (nested_function, lines 20274–20327, 54 lines, risk `support`): Export an Excel template for the current visible month (view-only data entry). Columns: Client Name + one column per date (YYYY-MM-DD). Users will fill payments in Excel and use 'Import from Excel' to load into the app.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.import_clients_from_excel** (nested_function, lines 20329–20643, 315 lines, risk `filesystem`): Import ONLY client details from an Excel file into the Clients DB. Multi-loan-type safe: - If the sheet has a "Loan Type" column, it imports per-row (Regular / 7x7). - Otherwise, it imports into the CURRENT view mode (top selector).
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.import_clients_from_excel._norm_lt** (nested_function, lines 20350–20358, 9 lines, risk `filesystem`): Handles norm lt for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.import_clients_from_excel.to_date** (nested_function, lines 20362–20377, 16 lines, risk `support`): Handles to date for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.import_clients_from_excel.to_float** (nested_function, lines 20379–20385, 7 lines, risk `filesystem`): Handles to float for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.export_clients_template** (nested_function, lines 21127–21161, 35 lines, risk `support`): Export a blank Excel template for importing client details. Columns: Client Name | Area | Principal | Date Released | Due Date
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.export_range_template** (nested_function, lines 21163–21286, 124 lines, risk `ui_only`): Export an Excel template for payments over a chosen date range. Presets: This Month / This Year / Custom (YYYY-MM-DD).
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.export_range_template.on_sel** (nested_function, lines 21198–21200, 3 lines, risk `ui_only`): Handles on sel for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.export_range_template._ok** (nested_function, lines 21206–21206, 1 lines, risk `support`): Handles ok for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.export_range_template._cancel** (nested_function, lines 21207–21207, 1 lines, risk `support`): Handles cancel for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.attach_direct_integration** (nested_function, lines 21288–21727, 440 lines, risk `database_write`): Minimal integration after removing undo/redo/backups. - Ensures a DB is attached - Wraps Excel import with a safe error dialog (if present) - Triggers initial UI refreshes (if methods exist)
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients._attempt_attach_on_run** (nested_function, lines 21730–21741, 12 lines, risk `reports`): Handles attempt attach on run for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.push** (nested_function, lines 21768–21777, 10 lines, risk `support`): Handles push for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.push.__init__** (nested_function, lines 21772–21773, 2 lines, risk `support`): Handles init for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.push.push** (nested_function, lines 21775–21777, 3 lines, risk `support`): Handles push for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.attach_refresh_all** (nested_function, lines 21779–21804, 26 lines, risk `support`): Attach a refresh_all method to app_obj that calls common updating hooks if they exist.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.attach_refresh_all.refresh_all** (nested_function, lines 21781–21802, 22 lines, risk `reports`): Refreshes refresh all for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.safe_excel_import** (nested_function, lines 21806–21839, 34 lines, risk `support`): import_fn should accept a file path and return a list of dicts or raise an error.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.safe_excel_import.wrapper** (nested_function, lines 21811–21837, 27 lines, risk `reports`): Handles wrapper for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._maybe_suggest_link_clients.auto_attach_enhancements** (nested_function, lines 21841–21862, 22 lines, risk `reports`): Search module globals for an App-like object and attach enhancements. Call this function at the bottom of the file or from interactive session once the app is created.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.export_range_template** (function, lines 21958–22136, 179 lines, risk `ui_only`): Export an Excel template for payments over a chosen date range. Presets: This Month / This Year / Custom (YYYY-MM-DD).
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.export_range_template._today_parts** (nested_function, lines 21998–22000, 3 lines, risk `support`): Handles today parts for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.export_range_template._apply_preset_fields** (nested_function, lines 22002–22021, 20 lines, risk `ui_only`): Handles apply preset fields for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.export_range_template.on_ok** (nested_function, lines 22029–22043, 15 lines, risk `support`): Handles on ok for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.export_range_template.on_cancel** (nested_function, lines 22045–22046, 2 lines, risk `support`): Handles on cancel for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.import_from_excel_with_reasons** (function, lines 22142–22290, 149 lines, risk `support`): Import the Excel 'range template' where columns are: Client Name | 2025-10-01 | 2025-10-01 Reason | 2025-10-02 | 2025-10-02 Reason | ... Saves both Amount and Reason for each date.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.import_from_excel_with_reasons._write** (nested_function, lines 22223–22290, 68 lines, risk `database_write`): Handles write for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._parse_adv_range_any** (function, lines 22304–22321, 18 lines, risk `support`): Handles parse adv range any for the utilities feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._daterange_inclusive** (function, lines 22323–22327, 5 lines, risk `support`): Handles daterange inclusive for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._parse_reason_color_token** (function, lines 22347–22370, 24 lines, risk `support`): Extract a [RC:...] token (hex or a color-name) from the description. Returns: (color_hex or "", desc_without_token)
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._parse_reason_color_token_meta** (function, lines 22373–22446, 74 lines, risk `support`): Extract [RC:...] token plus optional window meta from the description. Supported token payloads (inside the brackets): - '#RRGGBB' - 'red' / 'green' / etc - '#RRGGBB;D:3' -> days=3 (inclusive, starting from the reason's date) - '#RRGGBB;UNTIL:YYYY-MM-DD' -> until (inclusive) - 'red;D:3' / 'red;UNTIL
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._strip_adv_tags** (function, lines 22450–22458, 9 lines, risk `support`): Remove [ADV:...] tags from a description string.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._extract_reason_and_color_from_desc** (function, lines 22460–22472, 13 lines, risk `support`): Return (reason_text, color_hex) from a transaction description. - Removes [ADV:...] tags - Extracts and removes [RC:...] token (optional ';D:n' / ';UNTIL:YYYY-MM-DD') - Returns trimmed reason text (may be empty)
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._extract_reason_color_meta_from_desc** (function, lines 22474–22484, 11 lines, risk `support`): Return (reason_text, color_hex, meta) from a transaction description. meta = {'days': int|None, 'until': date|None}
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._hex_to_rgb01** (function, lines 22486–22498, 13 lines, risk `support`): '#RRGGBB' -> (r,g,b) floats 0..1
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._normalize_client_name_for_lookup** (function, lines 22501–22523, 23 lines, risk `support`): Normalize a display name back to the DB name (Collector Route / PDFs). Some PDF layouts append markers like "(7x7)" to the displayed name to avoid duplicates. Those markers must be stripped before looking up transactions/reasons/ADV in SQLite. We also trim and normalize whitespace.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._get_reason_color_for_client_date** (function, lines 22525–22638, 114 lines, risk `filesystem`): Return the active reason color for this client on this day (Collector Route only). Behavior: - If the reason token has no window (no D/UNTIL), color applies ONLY on the reason's date. - If token has D:n, color applies for n days starting from the reason's date. - If token has UNTIL:YYYY-MM-DD, color
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._collect_day_flags_for_month** (function, lines 22642–22786, 145 lines, risk `support`): txns: iterable of dicts/rows having keys: 'date'|'d', 'payment'|'amt', 'description'|'desc' Returns dict: day(date)-> {'adv':bool, 'adv_paid_on':set(str), 'reason':str or None, 'paid':float} Reporting rules: - ADV is marked ONLY on the COVERED days (NOT on the payment date). - Covered days also stor
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._collect_day_flags_for_month._gv** (nested_function, lines 22651–22662, 12 lines, risk `support`): Handles gv for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._collect_day_flags_for_month._row_date** (nested_function, lines 22664–22674, 11 lines, risk `support`): Handles row date for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._collect_day_flags_for_month._adv_ranges_from_desc** (nested_function, lines 22676–22707, 32 lines, risk `support`): Return list of (start_date, end_date) as date objects.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_record_report_generation** (function, lines 22797–22938, 142 lines, risk `filesystem`): Increment and return the daily Generate Report counter. Stored in: - data/report_generation_counts.json (summary counts) - data/report_generation_logs.csv (Excel-friendly full log) - data/report_generation_logs.jsonl (append-only full log) Counts: - total: all reports generated today - per client+lo
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.generate_client_pdf** (function, lines 22942–24126, 1185 lines, risk `financial_calculation`): Override: Client SOA PDF that expands ADV ranges to daily 'Adv' markers in the Payment column, and prints other reasons as text in Payment. Never prints long notes in the Date column. Layout: 3 columns per page, 11 rows per column.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.generate_client_pdf._display_loan_type_label** (nested_function, lines 22961–22968, 8 lines, risk `support`): Handles display loan type label for the loans feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.generate_client_pdf._gv** (nested_function, lines 23000–23007, 8 lines, risk `support`): Handles gv for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.generate_client_pdf._per_day_effective_payments** (nested_function, lines 23082–23114, 33 lines, risk `support`): Return ordered list of (date, effective_payment) using the same rule as totals: last non-zero wins; 0 does not overwrite a prior non-zero; ignore ADV-only marker rows.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.generate_client_pdf._safe** (nested_function, lines 23355–23378, 24 lines, risk `filesystem`): Handles safe for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.generate_client_pdf._hdr_php** (nested_function, lines 23436–23440, 5 lines, risk `support`): Handles hdr php for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.generate_client_pdf._draw_kv** (nested_function, lines 23491–23506, 16 lines, risk `support`): Handles draw kv for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.generate_client_pdf._draw_pair** (nested_function, lines 23508–23513, 6 lines, risk `support`): Handles draw pair for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.generate_client_pdf._draw_also_footer** (nested_function, lines 23572–23594, 23 lines, risk `backup`): Draw small footer note (subtle) on the current page.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.generate_client_pdf._php** (nested_function, lines 23604–23608, 5 lines, risk `support`): Handles php for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.generate_client_pdf._page_no_draw** (nested_function, lines 23736–23740, 5 lines, risk `support`): Handles page no draw for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.generate_client_pdf._draw_official_report_footer** (nested_function, lines 23742–23792, 51 lines, risk `backup`): Draw a small, subtle official-version label and daily Generate Report counter at the bottom. This footer is intentionally NOT styled like the big notes section. It is only a quiet authenticity/count marker near the bottom of the page.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.generate_client_pdf._payment_text_from_flag** (nested_function, lines 23821–23853, 33 lines, risk `support`): Handles payment text from flag for the payments feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.generate_client_pdf._build_month_entries** (nested_function, lines 23855–23880, 26 lines, risk `support`): Builds build month entries for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.generate_client_pdf._draw_month_block** (nested_function, lines 23882–23931, 50 lines, risk `support`): Handles draw month block for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.generate_client_pdf._estimate_note_block_h** (nested_function, lines 24026–24049, 24 lines, risk `support`): Handles estimate note block h for the notes feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._ensure_prefs_file** (function, lines 24133–24142, 10 lines, risk `reports`): Handles ensure prefs file for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app__norm_lt_value** (function, lines 24152–24160, 9 lines, risk `filesystem`): Handles app norm lt value for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app__other_lt** (function, lines 24162–24164, 3 lines, risk `support`): Handles app other lt for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app__get_selected_client_name** (function, lines 24166–24176, 11 lines, risk `support`): Handles app get selected client name for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app_refresh_clients** (function, lines 24189–24338, 150 lines, risk `financial_calculation`): Handles app refresh clients for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app_schedule_refresh_clients** (function, lines 24340–24364, 25 lines, risk `ui_only`): Debounce Clients search so refresh doesn't run on every keystroke.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app_add_client_dialog** (function, lines 24366–24409, 44 lines, risk `reports`): Handles app add client dialog for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app_on_client_edit** (function, lines 24411–24460, 50 lines, risk `reports`): Handles app on client edit for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app_delete_client_selected** (function, lines 24462–24484, 23 lines, risk `backup`): Handles app delete client selected for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app_link_selected_client** (function, lines 24496–24617, 122 lines, risk `ui_only`): Handles app link selected client for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app_link_selected_client.refresh_list** (nested_function, lines 24551–24556, 6 lines, risk `support`): Refreshes refresh list for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app_link_selected_client.do_link** (nested_function, lines 24564–24606, 43 lines, risk `support`): Handles do link for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app_unlink_selected_client** (function, lines 24619–24640, 22 lines, risk `support`): Handles app unlink selected client for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app__maybe_suggest_link_clients** (function, lines 24642–24703, 62 lines, risk `support`): Handles app maybe suggest link clients for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app_export_clients_template** (function, lines 24705–24729, 25 lines, risk `support`): Handles app export clients template for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app_import_clients_from_excel** (function, lines 24731–24844, 114 lines, risk `reports`): Handles app import clients from excel for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app_import_clients_from_excel.col_idx** (nested_function, lines 24760–24764, 5 lines, risk `support`): Handles col idx for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app_import_missing** (function, lines 24846–24857, 12 lines, risk `support`): Handles app import missing for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.RenewDialog** (class, lines 24860–25377, 518 lines, risk `container`): Renew (reloan) dialog. Auto-computes **Released Cash** using: released_cash = max(0, new_principal - remaining_due) remaining_due is based on the current cycle: Regular: remaining_due = max(0, total_to_pay - paid_total) 7x7: remaining_due = remaining_principal + unpaid_interest_arrears You can still
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.RenewDialog.__init__** (method, lines 24872–24881, 10 lines, risk `support`): Handles init for the loans feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.RenewDialog._parse_float** (method, lines 24883–24894, 12 lines, risk `filesystem`): Handles parse float for the utilities feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.RenewDialog._valid_ymd** (method, lines 24896–24904, 9 lines, risk `support`): Handles valid ymd for the loans feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.RenewDialog._compute_stats** (method, lines 24906–25164, 259 lines, risk `financial_calculation`): Return dict with paid/remaining/suggested released cash (best-effort). Regular: remaining_due = max(0, total_to_pay - paid_total) 7x7: remaining_due = remaining_principal + unpaid_interest_arrears (arrears must be cleared first). Uses the same rule as the SOA: - Daily interest = ceil(remaining_princ
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.RenewDialog._set_manual_rc** (method, lines 25166–25172, 7 lines, risk `ui_only`): Updates set manual rc for the loans feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.RenewDialog._set_auto_rc** (method, lines 25174–25181, 8 lines, risk `ui_only`): Updates set auto rc for the loans feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.RenewDialog._recompute** (method, lines 25183–25214, 32 lines, risk `ui_only`): Handles recompute for the loans feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.RenewDialog.body** (method, lines 25216–25308, 93 lines, risk `financial_calculation`): Handles body for the loans feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.RenewDialog.body._row** (nested_function, lines 25221–25224, 4 lines, risk `ui_only`): Handles row for the loans feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.RenewDialog.validate** (method, lines 25310–25348, 39 lines, risk `financial_calculation`): Handles validate for the utilities feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.RenewDialog.apply** (method, lines 25350–25377, 28 lines, risk `financial_calculation`): Handles apply for the loans feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app_renew_client_selected** (function, lines 25380–25461, 82 lines, risk `financial_calculation`): Renew (reloan) the selected client and update the client row + report stats.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app_open_archived_clients_dialog** (function, lines 25464–25580, 117 lines, risk `backup`): Handles app open archived clients dialog for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app_open_archived_clients_dialog.load_list** (nested_function, lines 25513–25531, 19 lines, risk `backup`): Loads load list for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app_open_archived_clients_dialog.restore_selected** (nested_function, lines 25533–25557, 25 lines, risk `backup`): Handles restore selected for the backup feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._SpinaStartupCancelled** (class, lines 25612–25614, 3 lines, risk `container`): Internal signal used to stop layered App initialization after login cancellation.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.main** (function, lines 25617–25630, 14 lines, risk `ui_only`): Handles main for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._schedule_collectors_refresh** (function, lines 25669–25686, 18 lines, risk `ui_only`): Debounce refresh_collectors while typing in Search.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._clear_collectors_search_filters** (function, lines 25689–25714, 26 lines, risk `support`): Clear search + quick filters for Collector's Route UI.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.print_collector_route_daily_ledger** (function, lines 25718–25915, 198 lines, risk `filesystem`): Print the SELECTED collector's route using the same 3-column Daily Collection Ledger layout as `print_full_daily_ledger`, but ONLY for that collector's areas (no 'arrange all areas' step). - Uses selection() first (more reliable than focus()). - Reads collectors.json in multiple historical schemas. 
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.print_full_daily_ledger** (function, lines 25919–29141, 3223 lines, risk `financial_calculation`): Print a 3-column DAILY COLLECTION LEDGER with a small UI to change: - Ledger Date - Paper size and orientation - Areas order (arrange ALL areas)
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.print_full_daily_ledger._fetch_clients_for** (nested_function, lines 25956–25963, 8 lines, risk `support`): Loads fetch clients for for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.print_full_daily_ledger._s** (nested_function, lines 25986–25986, 1 lines, risk `support`): Handles s for the reports feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.print_full_daily_ledger._options_dialog** (nested_function, lines 25991–26052, 62 lines, risk `ui_only`): Handles options dialog for the reports feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.print_full_daily_ledger._options_dialog._ok** (nested_function, lines 26030–26032, 3 lines, risk `support`): Handles ok for the reports feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.print_full_daily_ledger._options_dialog._cancel** (nested_function, lines 26033–26035, 3 lines, risk `support`): Handles cancel for the reports feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.print_full_daily_ledger._arrange_areas_dialog** (nested_function, lines 26055–26128, 74 lines, risk `reports`): Handles arrange areas dialog for the reports feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.print_full_daily_ledger._arrange_areas_dialog._move** (nested_function, lines 26088–26101, 14 lines, risk `ui_only`): Handles move for the reports feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.print_full_daily_ledger._arrange_areas_dialog._ok** (nested_function, lines 26110–26111, 2 lines, risk `support`): Handles ok for the reports feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.print_full_daily_ledger._arrange_areas_dialog._cancel** (nested_function, lines 26112–26113, 2 lines, risk `support`): Handles cancel for the reports feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.print_full_daily_ledger._wrap_text_to_width** (nested_function, lines 27213–27240, 28 lines, risk `support`): Handles wrap text to width for the reports feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.print_full_daily_ledger._wrap_text_to_width._fits** (nested_function, lines 27218–27218, 1 lines, risk `support`): Handles fits for the reports feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.print_full_daily_ledger._draw_page_number** (nested_function, lines 27242–27248, 7 lines, risk `support`): Handles draw page number for the reports feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.print_full_daily_ledger._draw_final_footer** (nested_function, lines 27250–27265, 16 lines, risk `support`): Handles draw final footer for the reports feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.print_full_daily_ledger._draw_global_header** (nested_function, lines 27266–27311, 46 lines, risk `support`): Handles draw global header for the reports feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.print_full_daily_ledger.new_page_headers** (nested_function, lines 27330–27360, 31 lines, risk `support`): Handles new page headers for the reports feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.print_full_daily_ledger.ensure_space** (nested_function, lines 27366–27385, 20 lines, risk `support`): Handles ensure space for the reports feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.print_full_daily_ledger._draw_closed_route_payment_summary_page** (nested_function, lines 28919–29106, 188 lines, risk `support`): Append closed-route payment summaries on a separate page. This keeps the route pages in the normal collector format while still saving a complete area-by-area payment summary plus grand total.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.print_full_daily_ledger._draw_closed_route_payment_summary_page._fmt_summary_money** (nested_function, lines 28932–28942, 11 lines, risk `support`): Handles fmt summary money for the collectors feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.print_full_daily_ledger._draw_closed_route_payment_summary_page._as_float** (nested_function, lines 28944–28948, 5 lines, risk `support`): Handles as float for the collectors feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.print_full_daily_ledger._draw_closed_route_payment_summary_page._draw_summary_header** (nested_function, lines 28994–29036, 43 lines, risk `support`): Handles draw summary header for the collectors feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.print_full_daily_ledger._draw_closed_route_payment_summary_page._draw_summary_row** (nested_function, lines 29038–29067, 30 lines, risk `backup`): Handles draw summary row for the collectors feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_tree_wheel** (function, lines 29149–29169, 21 lines, risk `ui_only`): Ensure mousewheel scroll works on Collector Route list (Treeview).
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._save_collector_notes** (function, lines 29171–29233, 63 lines, risk `support`): Update one collector's notes in collectors.json (atomic, normalized schema).
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._save_selected_collector_notes** (function, lines 29235–29273, 39 lines, risk `support`): Save Notes from the right panel to collectors.json (atomic).
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_multi_toggle** (function, lines 29328–29347, 20 lines, risk `support`): Toggle multi-select mode for Collector Route list (checkbox Sel column).
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_tree_wheel** (function, lines 29350–29383, 34 lines, risk `ui_only`): Mouse wheel scroll for Collector Route list (Treeview).
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_tree_click** (function, lines 29386–29486, 101 lines, risk `filesystem`): Handle click in Sel / Actions columns without breaking row selection.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._delete_selected_collector** (function, lines 29489–29519, 31 lines, risk `support`): Safe delete action used by keybinds/buttons/menus.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._edit_selected_collector** (function, lines 29522–29536, 15 lines, risk `support`): Safe edit action for the context menu ('Full Editor…').
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._collectors_areas_drag_motion** (function, lines 29539–29581, 43 lines, risk `ui_only`): Drag-to-reorder areas listbox (MOVE item) without index-shift bugs.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina__ensure_client_picture_column** (function, lines 29635–29647, 13 lines, risk `database_write`): Best-effort lazy migration for client_picture support.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina__client_pictures_dir** (function, lines 29650–29659, 10 lines, risk `support`): Handles spina client pictures dir for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina__resolve_app_path** (function, lines 29662–29679, 18 lines, risk `backup`): Handles spina resolve app path for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina__store_client_picture_file** (function, lines 29682–29719, 38 lines, risk `filesystem`): Handles spina store client picture file for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina__delete_client_picture_file** (function, lines 29722–29734, 13 lines, risk `filesystem`): Handles spina delete client picture file for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._db_set_client_picture** (function, lines 29747–29778, 32 lines, risk `database_write`): Handles db set client picture for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._db_clear_client_picture** (function, lines 29781–29810, 30 lines, risk `database_write`): Handles db clear client picture for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app_refresh_client_picture_panel** (function, lines 29815–29899, 85 lines, risk `filesystem`): Handles app refresh client picture panel for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app_set_selected_client_picture** (function, lines 29902–29925, 24 lines, risk `support`): Handles app set selected client picture for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._app_clear_selected_client_picture** (function, lines 29928–29953, 26 lines, risk `support`): Handles app clear selected client picture for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_perf_ensure_indexes** (function, lines 30009–30051, 43 lines, risk `database_write`): Create helpful indexes for large datasets. Safe/idempotent.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_perf_norm_lt** (function, lines 30054–30061, 8 lines, risk `filesystem`): Handles spina perf norm lt for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_perf_month_transactions** (function, lines 30075–30142, 68 lines, risk `database_read`): Return {(row_key, yyyy-mm-dd): payment} for visible clients in the month using one range query.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_perf_month_transactions._chunks** (nested_function, lines 30099–30101, 3 lines, risk `support`): Handles chunks for the payments feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_perf_refresh_data_grid** (function, lines 30147–30351, 205 lines, risk `ui_only`): Fast Data Bank month grid refresh using bulk month transaction query.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_perf_refresh_data_grid._yview** (nested_function, lines 30195–30199, 5 lines, risk `support`): Handles yview for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_perf_refresh_data_grid._sync_selection** (nested_function, lines 30210–30222, 13 lines, risk `ui_only`): Handles sync selection for the data bank feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_archive_row_to_dict** (function, lines 30373–30384, 12 lines, risk `backup`): Handles spina archive row to dict for the backup feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_fixed_archive_client** (function, lines 30387–30416, 30 lines, risk `database_write`): Soft-delete: hide the client while keeping transactions/history. Fix: after archiving, fetch the new row with include_archived=True so history can still see the archived row instead of getting an empty new_row.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_fixed_restore_client** (function, lines 30419–30459, 41 lines, risk `database_write`): Restore a previously archived client by name + loan type. Important fix: the old code called get_client_info() without include_archived=True. Because archived rows are hidden by default, restore failed with "Client not found".
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_fixed_restore_client_by_uid** (function, lines 30462–30482, 21 lines, risk `backup`): Restore archived client by UID, with name/type fallback support.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_fixed_open_archived_clients_dialog** (function, lines 30485–30620, 136 lines, risk `backup`): Archived clients restore dialog with UID fallback and refresh after restore.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_fixed_open_archived_clients_dialog.load_list** (nested_function, lines 30535–30561, 27 lines, risk `backup`): Loads load list for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_fixed_open_archived_clients_dialog.restore_selected** (nested_function, lines 30563–30603, 41 lines, risk `backup`): Handles restore selected for the backup feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_fixed_get_archived_clients_with_id** (function, lines 30643–30700, 58 lines, risk `backup`): List archived clients and include the internal row id for reliable restore.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_fixed_restore_client_by_id** (function, lines 30703–30740, 38 lines, risk `database_write`): Restore archived client by exact clients.id row.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_fixed_open_archived_clients_dialog_rowid** (function, lines 30743–30879, 137 lines, risk `backup`): Archived clients restore dialog that restores by clients.id first.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_fixed_open_archived_clients_dialog_rowid._rowid_from_iid** (nested_function, lines 30784–30797, 14 lines, risk `support`): Handles rowid from iid for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_fixed_open_archived_clients_dialog_rowid.load_list** (nested_function, lines 30799–30827, 29 lines, risk `backup`): Loads load list for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_fixed_open_archived_clients_dialog_rowid.restore_selected** (nested_function, lines 30829–30864, 36 lines, risk `backup`): Handles restore selected for the backup feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_dash__norm_lt** (function, lines 30902–30907, 6 lines, risk `filesystem`): Handles spina dash norm lt for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_dashboard_fetch_rows** (function, lines 30928–31189, 262 lines, risk `financial_calculation`): Return active client completion rows using payments from latest released date only. Latest released date = max(clients.date_released, latest renewals.renew_date). Payment start = latest released date + clients.pay_start_offset_days (normalized to 0/1 day).
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_dashboard_fetch_rows._table_exists** (nested_function, lines 30943–30948, 6 lines, risk `database_read`): Handles table exists for the dashboard feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_dashboard_fetch_rows._table_cols** (nested_function, lines 30950–30954, 5 lines, risk `database_read`): Handles table cols for the dashboard feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_dashboard_fetch_rows._c** (nested_function, lines 30962–30963, 2 lines, risk `support`): Handles c for the dashboard feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_dashboard_fetch_rows._rv** (nested_function, lines 31027–31034, 8 lines, risk `support`): Handles rv for the dashboard feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_cashctl__fmt_money** (function, lines 31294–31304, 11 lines, risk `support`): Handles spina cashctl fmt money for the cash control feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_cashctl__parse_percent** (function, lines 31313–31329, 17 lines, risk `filesystem`): Parse a percent input like '10', '10%', or '0.10'. Returns 0..100.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_cashctl_get_collection_totals** (function, lines 31338–31392, 55 lines, risk `database_read`): Return combined collection totals for one day. Combined Collected = Regular + 7x7 + any transaction without a clean loan_type. This intentionally uses the Data Bank transactions total, not only one payment mode.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_cashctl_get_average_collection** (function, lines 31395–31451, 57 lines, risk `database_read`): Average daily collection before the selected date. Uses the last N calendar days before the selected date, then averages only days that actually have collections. This is better for forecasting collection days than dividing by every calendar day, especially when there are no-collection days.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_cashctl__ceil_thousand_units** (function, lines 31456–31466, 11 lines, risk `support`): Handles spina cashctl ceil thousand units for the cash control feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_cashctl__x7_daily_interest** (function, lines 31469–31471, 3 lines, risk `financial_calculation`): 7x7 daily interest: 1..1000=7/day, 1001..2000=14/day, etc.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_cashctl_estimated_payoff_with_interest** (function, lines 31474–31592, 119 lines, risk `financial_calculation`): Estimate payoff collection for renewal, including interest. Regular: uses the dashboard remaining balance, which is based on total_to_pay. total_to_pay is corrected to principal + interest_amount when needed. 7x7: splits current-cycle payments into interest first, then principal, and includes unpaid
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_cashctl_reserve_rows** (function, lines 31595–31689, 95 lines, risk `financial_calculation`): Rows to reserve cash for possible renewals. IMPORTANT: Cash Control now includes ALL active clients in the reserve list, not only near-completion clients. Near-completion / due-soon rules are used only as priority labels so the owner can see who is urgent first. Reserve basis is the current principa
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_cashctl_build_tab** (function, lines 31692–31816, 125 lines, risk `ui_only`): Handles spina cashctl build tab for the cash control feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_cashctl_refresh** (function, lines 31819–31931, 113 lines, risk `financial_calculation`): Handles spina cashctl refresh for the cash control feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_cashctl_apply_role** (function, lines 31934–31958, 25 lines, risk `authentication`): Handles spina cashctl apply role for the cash control feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._populate_collector_details** (function, lines 32016–32110, 95 lines, risk `support`): Update the right panel: selected name, stats, areas tree, notes.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._on_collectors_select** (function, lines 32113–32178, 66 lines, risk `ui_only`): Populate the right-side details panel for the selected collector.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_cilog_field_label** (function, lines 32203–32233, 31 lines, risk `filesystem`): Handles spina cilog field label for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_cilog_fetch_rows** (function, lines 32242–32301, 60 lines, risk `database_write`): Handles spina cilog fetch rows for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_auto_close_after_days_value** (function, lines 32354–32368, 15 lines, risk `support`): Return the configured auto-close delay in days. 0 = disabled.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_auto_close_candidate_dates** (function, lines 32371–32403, 33 lines, risk `database_read`): Return transaction dates up to cutoff that are not already closed.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_auto_close_one_day** (function, lines 32406–32448, 43 lines, risk `support`): Close one Data Bank day using system expected totals as the safe automatic actual amount.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_run_auto_daily_close** (function, lines 32451–32529, 79 lines, risk `support`): Auto-close Data Bank dates that are older than the configured delay.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_schedule_auto_daily_close** (function, lines 32532–32549, 18 lines, risk `ui_only`): Run auto close now and then check periodically while the app is open.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina__parse_flexible_due_rule** (function, lines 32577–32740, 164 lines, risk `support`): Return (label, due_today_bool) for optional flex_due_rule. Supported examples: - salary 15/30 window 2 -> due from 13-17 and last-day-2 through last-day+2 if valid - weekly Monday Thursday -> due every Monday and Thursday - 2nd Saturday -> due every 2nd Saturday of the month - days 13,14,15,29,30,31
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_route_notice_norm_lt** (function, lines 32765–32770, 6 lines, risk `filesystem`): Handles spina route notice norm lt for the collectors feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_route_notice_key** (function, lines 32772–32777, 6 lines, risk `support`): Handles spina route notice key for the collectors feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_route_notice_load** (function, lines 32779–32790, 12 lines, risk `filesystem`): Handles spina route notice load for the collectors feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_route_notice_save** (function, lines 32792–32803, 12 lines, risk `support`): Handles spina route notice save for the collectors feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_route_notice_upsert** (function, lines 32805–32837, 33 lines, risk `support`): Handles spina route notice upsert for the collectors feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_route_balance_like_generate_report** (function, lines 32847–33029, 183 lines, risk `financial_calculation`): Return the same Balance basis used by Generate Report PDF. Regular: total_to_pay (corrected to principal + interest when needed) minus effective current-cycle payments. 7x7: remaining principal after the Generate Report interest-first payment split. This intentionally matches the report header Balan
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_crc_norm_lt** (function, lines 33037–33042, 6 lines, risk `filesystem`): Handles spina crc norm lt for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_crc_clean_reason** (function, lines 33048–33061, 14 lines, risk `support`): Handles spina crc clean reason for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_crc_load_collectors** (function, lines 33064–33106, 43 lines, risk `filesystem`): Load collector route definitions from data/collectors.json in any supported schema.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_crc_split_area** (function, lines 33109–33121, 13 lines, risk `support`): Handles spina crc split area for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_crc_route_area_matches** (function, lines 33124–33148, 25 lines, risk `support`): Match route area to client area, including MAIN-only collector routes covering subareas.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_crc_collector_for_area** (function, lines 33151–33159, 9 lines, risk `support`): Handles spina crc collector for area for the collectors feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_crc_key** (function, lines 33162–33166, 5 lines, risk `support`): Handles spina crc key for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_crc_fetch_close_rows** (function, lines 33169–33335, 167 lines, risk `database_read`): Build route rows with amount paid on the close date.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_crc_fetch_close_rows._add_pay** (nested_function, lines 33215–33224, 10 lines, risk `support`): Handles add pay for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_crc_wrap** (function, lines 33338–33360, 23 lines, risk `support`): Handles spina crc wrap for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_crc_copy_existing_route_pdfs** (function, lines 33363–33395, 33 lines, risk `filesystem`): Handles spina crc copy existing route pdfs for the collectors feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_save_closed_collector_route_copy** (function, lines 33398–33678, 281 lines, risk `backup`): Save an audit copy of the Collector Route after Daily Close. The PDF contains the closed total/actual cash for the day and the amount paid by each client on that date. It is separate from Generate Report and from editable Data Bank rows.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_save_closed_collector_route_copy._rec_get** (nested_function, lines 33427–33434, 8 lines, risk `support`): Handles rec get for the collectors feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_save_closed_collector_route_copy._new_page** (nested_function, lines 33509–33513, 5 lines, risk `support`): Handles new page for the collectors feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_save_closed_collector_route_copy._ensure** (nested_function, lines 33515–33517, 3 lines, risk `support`): Handles ensure for the collectors feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_save_closed_collector_route_copy._draw_header** (nested_function, lines 33519–33549, 31 lines, risk `support`): Handles draw header for the collectors feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_save_closed_collector_route_copy._draw_table_header** (nested_function, lines 33551–33566, 16 lines, risk `backup`): Handles draw table header for the collectors feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_crc_build_paid_cache_for_date** (function, lines 33693–33725, 33 lines, risk `database_read`): Return {(lower_name, lower_loan_type): paid_amount} for the closed date.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_crc_active_filtered_areas_for_collector** (function, lines 33728–33780, 53 lines, risk `database_read`): Match the Collector Route screen filtering so blank/archived-only areas are skipped.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_save_closed_collector_route_copy_same_format** (function, lines 33783–33952, 170 lines, risk `filesystem`): Save final closed Collector Route copy using the SAME Collector Route PDF layout. Difference from normal print: the payment columns are filled with the actual amount paid on the closed date, and the PDF is saved silently under data/Closed_Collector_Routes.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_save_closed_collector_route_copy_same_format._safe_tag** (nested_function, lines 33818–33822, 5 lines, risk `filesystem`): Handles safe tag for the collectors feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_save_closed_collector_route_copy_same_format._generate_one** (nested_function, lines 33824–33882, 59 lines, risk `filesystem`): Generates generate one for the collectors feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg__reset_id_sequence** (function, lines 33976–33996, 21 lines, risk `database_read`): Move a PostgreSQL BIGSERIAL/SERIAL sequence after the current MAX(id).
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg__table_has_column** (function, lines 33999–34014, 16 lines, risk `database_read`): Handles spina pg table has column for the database feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_pg_renew_client_direct** (function, lines 34017–34242, 226 lines, risk `financial_calculation`): PostgreSQL-safe renew/reloan implementation for the TEST build.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_route_adv_marker_for** (function, lines 34257–34429, 173 lines, risk `filesystem`): Collector Route ADV lookup with stronger PostgreSQL migration fallback. This version does not rely only on the printed route name. It finds the client_uid/person_uid from clients first, then checks every matching transaction name/uid for the selected loan type. This fixes migrated data where a linke
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v21_cash_refresh** (function, lines 34789–34957, 169 lines, risk `financial_calculation`): Handles spina v21 cash refresh for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v23_client_loan_summary** (function, lines 35043–35099, 57 lines, risk `financial_calculation`): Handles spina v23 client loan summary for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v23_client_form** (function, lines 35110–35566, 457 lines, risk `ui_only`): Handles spina v23 client form for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v23_client_form.norm_lt** (nested_function, lines 35114–35119, 6 lines, risk `filesystem`): Handles norm lt for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v23_client_form._on_content_config** (nested_function, lines 35190–35195, 6 lines, risk `ui_only`): Handles on content config for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v23_client_form._load_pic_preview** (nested_function, lines 35218–35245, 28 lines, risk `filesystem`): Loads load pic preview for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v23_client_form._choose_picture** (nested_function, lines 35247–35258, 12 lines, risk `ui_only`): Handles choose picture for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v23_client_form._clear_picture** (nested_function, lines 35260–35266, 7 lines, risk `ui_only`): Handles clear picture for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v23_client_form.section** (nested_function, lines 35288–35298, 11 lines, risk `ui_only`): Handles section for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v23_client_form.calc_row** (nested_function, lines 35360–35364, 5 lines, risk `ui_only`): Handles calc row for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v23_client_form._parse_float_var** (nested_function, lines 35372–35377, 6 lines, risk `filesystem`): Handles parse float var for the utilities feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v23_client_form._sync_dates_and_calc** (nested_function, lines 35379–35417, 39 lines, risk `support`): Handles sync dates and calc for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v23_client_form._validate_date** (nested_function, lines 35432–35437, 6 lines, risk `support`): Validates validate date for the utilities feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v23_client_form._norm_dom** (nested_function, lines 35439–35451, 13 lines, risk `support`): Handles norm dom for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v23_client_form.save** (nested_function, lines 35453–35540, 88 lines, risk `support`): Handles save for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v23_client_form.cancel** (nested_function, lines 35542–35546, 5 lines, risk `support`): Handles cancel for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v23_add_client_dialog** (function, lines 35569–35618, 50 lines, risk `reports`): Handles spina v23 add client dialog for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v23_on_client_edit** (function, lines 35621–35687, 67 lines, risk `reports`): Handles spina v23 on client edit for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v27_get_route_master_areas** (function, lines 35907–35938, 32 lines, risk `support`): Handles spina v27 get route master areas for the collectors feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v32_account_default_name** (function, lines 36026–36034, 9 lines, risk `support`): Handles spina v32 account default name for the authentication feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v32_account_display_name** (function, lines 36043–36053, 11 lines, risk `authentication`): Handles spina v32 account display name for the authentication feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v32_account_role** (function, lines 36056–36066, 11 lines, risk `authentication`): Handles spina v32 account role for the authentication feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v32_account_choices** (function, lines 36069–36097, 29 lines, risk `authentication`): Handles spina v32 account choices for the authentication feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v32_selected_label_for_user** (function, lines 36100–36105, 6 lines, risk `support`): Handles spina v32 selected label for user for the other feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v32_make_users_account_based** (function, lines 36108–36162, 55 lines, risk `authentication`): Add account display metadata while preserving existing usernames/passwords/access.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v32_switch_account** (function, lines 36182–36239, 58 lines, risk `authentication`): Handles spina v32 switch account for the authentication feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_v32_prompt_user_role** (function, lines 36242–36245, 4 lines, risk `authentication`): Handles spina v32 prompt user role for the authentication feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_legacy_client_action_removed_message** (function, lines 36277–36288, 12 lines, risk `reports`): Handles spina legacy client action removed message for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_make_removed_legacy_client_action** (function, lines 36291–36296, 6 lines, risk `filesystem`): Handles spina make removed legacy client action for the clients feature.
- **OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed._spina_make_removed_legacy_client_action._spina_removed_action** (nested_function, lines 36292–36294, 3 lines, risk `support`): Handles spina removed action for the clients feature.

## `spina_app/account_header_presentation.py`

- **spina_app.account_header_presentation.configure_account_header_dependencies** (function, lines 16–21, 6 lines, risk `support`): Handles configure account header dependencies for the authentication feature.
- **spina_app.account_header_presentation._spina_v32_refresh_user_header** (function, lines 31–44, 14 lines, risk `authentication`): Handles spina v32 refresh user header for the authentication feature.
- **spina_app.account_header_presentation._spina_v32_build_header** (function, lines 46–57, 12 lines, risk `authentication`): Handles spina v32 build header for the navigation feature.

## `spina_app/account_permission_presentation.py`

- **spina_app.account_permission_presentation._spina_v32_account_permission_text** (function, lines 10–20, 11 lines, risk `authentication`): Handles spina v32 account permission text for the authentication feature.

## `spina_app/area_hierarchy.py`

- **spina_app.area_hierarchy._now_text** (function, lines 25–26, 2 lines, risk `support`): Handles now text for the other feature.
- **spina_app.area_hierarchy.normalize_area_segment** (function, lines 29–35, 7 lines, risk `support`): Return a trimmed single Area node name with internal spaces collapsed.
- **spina_app.area_hierarchy.normalize_area_path** (function, lines 38–44, 7 lines, risk `support`): Normalize spacing without changing a legacy Area's visible wording.
- **spina_app.area_hierarchy.format_area_path** (function, lines 47–50, 4 lines, risk `support`): Join any number of Area levels into one unambiguous display path.
- **spina_app.area_hierarchy._path_key** (function, lines 53–54, 2 lines, risk `support`): Handles path key for the other feature.
- **spina_app.area_hierarchy._legacy_area_uid** (function, lines 57–59, 3 lines, risk `support`): Return a stable ID so repeated migrations cannot duplicate a flat Area.
- **spina_app.area_hierarchy._row_value** (function, lines 62–73, 12 lines, risk `support`): Handles row value for the other feature.
- **spina_app.area_hierarchy._table_columns** (function, lines 76–90, 15 lines, risk `database_read`): Handles table columns for the other feature.
- **spina_app.area_hierarchy._ensure_client_area_uid** (function, lines 93–102, 10 lines, risk `database_write`): Handles ensure client area uid for the clients feature.
- **spina_app.area_hierarchy._ensure_legacy_areas_table** (function, lines 105–113, 9 lines, risk `database_write`): Handles ensure legacy areas table for the other feature.
- **spina_app.area_hierarchy._ensure_area_nodes_table** (function, lines 116–143, 28 lines, risk `database_write`): Handles ensure area nodes table for the other feature.
- **spina_app.area_hierarchy._fetch_nodes** (function, lines 146–171, 26 lines, risk `database_read`): Loads fetch nodes for the other feature.
- **spina_app.area_hierarchy.migrate_flat_areas** (function, lines 174–241, 68 lines, risk `database_write`): Migrate existing flat Area text to root nodes without changing text. Existing values are deliberately kept as root nodes. Staff can later move them under another Area through the hierarchy manager. This avoids guessing whether a dash or slash in an old Area name was intended as a separator.
- **spina_app.area_hierarchy.ensure_area_hierarchy_schema** (function, lines 244–252, 9 lines, risk `database_write`): Create hierarchy storage and explicitly rescan legacy values.
- **spina_app.area_hierarchy.ensure_area_hierarchy_ready** (function, lines 255–259, 5 lines, risk `support`): Ensure hierarchy storage once for this live database connection.
- **spina_app.area_hierarchy.list_area_nodes** (function, lines 262–264, 3 lines, risk `support`): Handles list area nodes for the other feature.
- **spina_app.area_hierarchy.build_area_tree** (function, lines 267–300, 34 lines, risk `support`): Build a nested tree from a flat list without imposing a depth limit.
- **spina_app.area_hierarchy.build_area_tree.sort_branch** (nested_function, lines 289–297, 9 lines, risk `support`): Handles sort branch for the other feature.
- **spina_app.area_hierarchy._node_by_uid** (function, lines 303–310, 8 lines, risk `support`): Handles node by uid for the other feature.
- **spina_app.area_hierarchy.add_area_node** (function, lines 313–360, 48 lines, risk `database_write`): Add one Area node under any parent and return the saved node.
- **spina_app.area_hierarchy.set_client_area_node** (function, lines 363–378, 16 lines, risk `database_write`): Assign a client to a node while synchronizing the legacy Area path text.

## `spina_app/area_hierarchy_ops.py`

- **spina_app.area_hierarchy_ops._now_text** (function, lines 25–26, 2 lines, risk `support`): Handles now text for the other feature.
- **spina_app.area_hierarchy_ops._key** (function, lines 29–30, 2 lines, risk `support`): Handles key for the other feature.
- **spina_app.area_hierarchy_ops._node_map** (function, lines 33–38, 6 lines, risk `support`): Handles node map for the other feature.
- **spina_app.area_hierarchy_ops.find_area_node_by_path** (function, lines 41–54, 14 lines, risk `support`): Return the node whose full path matches ``path`` case-insensitively.
- **spina_app.area_hierarchy_ops.sync_client_area_uid_from_path** (function, lines 57–94, 38 lines, risk `database_write`): Link one legacy client Area path to its stable Area node ID.
- **spina_app.area_hierarchy_ops._subtree_uids** (function, lines 97–112, 16 lines, risk `support`): Handles subtree uids for the other feature.
- **spina_app.area_hierarchy_ops._client_count_for_nodes** (function, lines 115–139, 25 lines, risk `database_read`): Count all matching clients in one query, including stale legacy paths.
- **spina_app.area_hierarchy_ops.count_clients_for_area_node** (function, lines 142–155, 14 lines, risk `support`): Count clients assigned directly to a node or its whole subtree.
- **spina_app.area_hierarchy_ops._planned_subtree** (function, lines 158–232, 75 lines, risk `support`): Handles planned subtree for the other feature.
- **spina_app.area_hierarchy_ops._planned_subtree.walk** (nested_function, lines 205–217, 13 lines, risk `support`): Handles walk for the other feature.
- **spina_app.area_hierarchy_ops._apply_planned_subtree** (function, lines 235–286, 52 lines, risk `database_write`): Handles apply planned subtree for the other feature.
- **spina_app.area_hierarchy_ops.rename_area_node** (function, lines 289–295, 7 lines, risk `support`): Rename one node and cascade full paths through all descendants and clients.
- **spina_app.area_hierarchy_ops.move_area_node** (function, lines 298–305, 8 lines, risk `support`): Move a node to another parent or to the root, preserving its subtree.
- **spina_app.area_hierarchy_ops.move_area_node_order** (function, lines 308–346, 39 lines, risk `database_write`): Move one Area up or down among siblings.
- **spina_app.area_hierarchy_ops._require_active_ancestor_chain** (function, lines 349–366, 18 lines, risk `support`): Prevent an active Area from existing below an inactive ancestor.
- **spina_app.area_hierarchy_ops.set_area_node_active** (function, lines 369–409, 41 lines, risk `database_write`): Activate or deactivate a whole subtree safely.
- **spina_app.area_hierarchy_ops.add_child_area_node** (function, lines 412–414, 3 lines, risk `support`): Named wrapper used by the Area Manager for unlimited child levels.
- **spina_app.area_hierarchy_ops.active_area_paths** (function, lines 417–420, 4 lines, risk `support`): Return active hierarchy paths in tree order for legacy dropdowns.

## `spina_app/area_hierarchy_ui.py`

- **spina_app.area_hierarchy_ui._connection** (function, lines 21–26, 6 lines, risk `support`): Handles connection for the database feature.
- **spina_app.area_hierarchy_ui._refresh_app_area_views** (function, lines 29–41, 13 lines, risk `support`): Refresh legacy Area consumers only after the manager actually changed data.
- **spina_app.area_hierarchy_ui._restore_parent_grab** (function, lines 44–52, 9 lines, risk `backup`): Return modal control to the form that opened the Area window.
- **spina_app.area_hierarchy_ui._tree_visible_uids** (function, lines 55–68, 14 lines, risk `support`): Handles tree visible uids for the other feature.
- **spina_app.area_hierarchy_ui._folder_text** (function, lines 71–73, 3 lines, risk `support`): Handles folder text for the other feature.
- **spina_app.area_hierarchy_ui._remember_open_folders** (function, lines 76–89, 14 lines, risk `support`): Handles remember open folders for the other feature.
- **spina_app.area_hierarchy_ui._remember_open_folders.walk** (nested_function, lines 79–86, 8 lines, risk `support`): Handles walk for the other feature.
- **spina_app.area_hierarchy_ui._refresh_folder_icons** (function, lines 92–101, 10 lines, risk `support`): Refreshes refresh folder icons for the other feature.
- **spina_app.area_hierarchy_ui._refresh_folder_icons.walk** (nested_function, lines 93–99, 7 lines, risk `support`): Handles walk for the other feature.
- **spina_app.area_hierarchy_ui._set_all_folders** (function, lines 104–110, 7 lines, risk `support`): Updates set all folders for the other feature.
- **spina_app.area_hierarchy_ui._set_all_folders.walk** (nested_function, lines 105–108, 4 lines, risk `support`): Handles walk for the other feature.
- **spina_app.area_hierarchy_ui._populate_area_tree** (function, lines 113–160, 48 lines, risk `support`): Render a true parent/child folder tree and return its UID lookup.
- **spina_app.area_hierarchy_ui._populate_area_tree.insert_branch** (nested_function, lines 134–157, 24 lines, risk `support`): Handles insert branch for the other feature.
- **spina_app.area_hierarchy_ui.select_area_node** (function, lines 163–287, 125 lines, risk `ui_only`): Open a modal folder browser and return the selected active Area node.
- **spina_app.area_hierarchy_ui.select_area_node.refresh** (nested_function, lines 230–243, 14 lines, risk `ui_only`): Handles refresh for the other feature.
- **spina_app.area_hierarchy_ui.select_area_node.accept** (nested_function, lines 245–253, 9 lines, risk `support`): Handles accept for the other feature.
- **spina_app.area_hierarchy_ui.select_area_node.clear** (nested_function, lines 255–257, 3 lines, risk `support`): Handles clear for the other feature.
- **spina_app.area_hierarchy_ui.select_area_node.close** (nested_function, lines 259–265, 7 lines, risk `backup`): Handles close for the other feature.
- **spina_app.area_hierarchy_ui.select_area_for_variable** (function, lines 290–305, 16 lines, risk `support`): Handles select area for variable for the other feature.
- **spina_app.area_hierarchy_ui.build_simple_area_selector** (function, lines 308–332, 25 lines, risk `ui_only`): Return a compact read-only selector row for legacy client forms.
- **spina_app.area_hierarchy_ui.build_area_selector_field** (function, lines 335–376, 42 lines, risk `ui_only`): Build the modern client form's labeled, read-only Area selector.
- **spina_app.area_hierarchy_ui._select_parent_area** (function, lines 379–456, 78 lines, risk `ui_only`): Select a new parent folder; an empty string means move to the root.
- **spina_app.area_hierarchy_ui._select_parent_area.insert** (nested_function, lines 413–426, 14 lines, risk `support`): Handles insert for the other feature.
- **spina_app.area_hierarchy_ui._select_parent_area.close** (nested_function, lines 431–437, 7 lines, risk `backup`): Handles close for the other feature.
- **spina_app.area_hierarchy_ui._select_parent_area.accept** (nested_function, lines 439–447, 9 lines, risk `support`): Handles accept for the other feature.
- **spina_app.area_hierarchy_ui.open_area_manager** (function, lines 459–729, 271 lines, risk `ui_only`): Open the folder-style unlimited hierarchical Area manager.
- **spina_app.area_hierarchy_ui.open_area_manager.selected_uid** (nested_function, lines 541–543, 3 lines, risk `support`): Handles selected uid for the other feature.
- **spina_app.area_hierarchy_ui.open_area_manager.selected_node** (nested_function, lines 545–546, 2 lines, risk `support`): Handles selected node for the other feature.
- **spina_app.area_hierarchy_ui.open_area_manager.render** (nested_function, lines 548–564, 17 lines, risk `ui_only`): Handles render for the other feature.
- **spina_app.area_hierarchy_ui.open_area_manager.reload_tree** (nested_function, lines 566–568, 3 lines, risk `support`): Handles reload tree for the other feature.
- **spina_app.area_hierarchy_ui.open_area_manager.mark_changed** (nested_function, lines 570–571, 2 lines, risk `support`): Handles mark changed for the other feature.
- **spina_app.area_hierarchy_ui.open_area_manager.add_main** (nested_function, lines 573–582, 10 lines, risk `support`): Handles add main for the other feature.
- **spina_app.area_hierarchy_ui.open_area_manager.add_child** (nested_function, lines 584–604, 21 lines, risk `support`): Handles add child for the other feature.
- **spina_app.area_hierarchy_ui.open_area_manager.rename_selected** (nested_function, lines 606–624, 19 lines, risk `support`): Handles rename selected for the other feature.
- **spina_app.area_hierarchy_ui.open_area_manager.move_selected** (nested_function, lines 626–639, 14 lines, risk `support`): Handles move selected for the other feature.
- **spina_app.area_hierarchy_ui.open_area_manager.reorder** (nested_function, lines 641–650, 10 lines, risk `support`): Handles reorder for the other feature.
- **spina_app.area_hierarchy_ui.open_area_manager.toggle_active** (nested_function, lines 652–682, 31 lines, risk `support`): Handles toggle active for the other feature.
- **spina_app.area_hierarchy_ui.open_area_manager.close** (nested_function, lines 707–722, 16 lines, risk `backup`): Handles close for the other feature.

## `spina_app/area_picker_presentation.py`

- **spina_app.area_picker_presentation.configure_area_picker_dependencies** (function, lines 14–19, 6 lines, risk `support`): Handles configure area picker dependencies for the other feature.
- **spina_app.area_picker_presentation._area_picker_dialog** (function, lines 26–536, 511 lines, risk `database_read`): Route area picker (Main/Sub Tree + ordered selection). What you get: - Left: Tree of Main Areas with Sub Areas underneath - Right: Selected Route (ordered) as MAIN or MAIN - SUB entries - MAIN entry covers all its Sub Areas when printing/validating routes.
- **spina_app.area_picker_presentation._area_picker_dialog._norm** (nested_function, lines 70–77, 8 lines, risk `support`): Handles norm for the other feature.
- **spina_app.area_picker_presentation._area_picker_dialog._set_info** (nested_function, lines 185–190, 6 lines, risk `support`): Updates set info for the other feature.
- **spina_app.area_picker_presentation._area_picker_dialog._current_selected_values** (nested_function, lines 192–196, 5 lines, risk `support`): Handles current selected values for the other feature.
- **spina_app.area_picker_presentation._area_picker_dialog._has_main_selected** (nested_function, lines 198–204, 7 lines, risk `support`): Handles has main selected for the other feature.
- **spina_app.area_picker_presentation._area_picker_dialog._remove_subs_of_main** (nested_function, lines 206–215, 10 lines, risk `support`): Removes remove subs of main for the other feature.
- **spina_app.area_picker_presentation._area_picker_dialog._replace_right** (nested_function, lines 217–226, 10 lines, risk `support`): Handles replace right for the other feature.
- **spina_app.area_picker_presentation._area_picker_dialog._add_to_right** (nested_function, lines 228–251, 24 lines, risk `support`): Handles add to right for the other feature.
- **spina_app.area_picker_presentation._area_picker_dialog._get_tree_selection_route_values** (nested_function, lines 253–268, 16 lines, risk `support`): Retrieves get tree selection route values for the collectors feature.
- **spina_app.area_picker_presentation._area_picker_dialog.add_sel** (nested_function, lines 270–274, 5 lines, risk `support`): Handles add sel for the other feature.
- **spina_app.area_picker_presentation._area_picker_dialog.remove_sel** (nested_function, lines 276–282, 7 lines, risk `support`): Removes remove sel for the other feature.
- **spina_app.area_picker_presentation._area_picker_dialog.move_up** (nested_function, lines 284–299, 16 lines, risk `ui_only`): Handles move up for the other feature.
- **spina_app.area_picker_presentation._area_picker_dialog.move_down** (nested_function, lines 301–316, 16 lines, risk `ui_only`): Handles move down for the other feature.
- **spina_app.area_picker_presentation._area_picker_dialog._selected_main_from_tree** (nested_function, lines 318–340, 23 lines, risk `ui_only`): Try to infer the current Main area from the left tree selection.
- **spina_app.area_picker_presentation._area_picker_dialog._on_tree_select_fill** (nested_function, lines 342–371, 30 lines, risk `ui_only`): Clicking a Main fills the Main entry, so you can add Sub areas quickly.
- **spina_app.area_picker_presentation._area_picker_dialog.add_new_area** (nested_function, lines 373–424, 52 lines, risk `ui_only`): Handles add new area for the other feature.
- **spina_app.area_picker_presentation._area_picker_dialog._expand_all** (nested_function, lines 426–432, 7 lines, risk `support`): Handles expand all for the other feature.
- **spina_app.area_picker_presentation._area_picker_dialog._refresh_tree** (nested_function, lines 434–464, 31 lines, risk `support`): Refreshes refresh tree for the other feature.
- **spina_app.area_picker_presentation._area_picker_dialog.on_ok** (nested_function, lines 480–491, 12 lines, risk `support`): Handles on ok for the other feature.
- **spina_app.area_picker_presentation._area_picker_dialog.on_cancel** (nested_function, lines 493–500, 8 lines, risk `support`): Handles on cancel for the other feature.
- **spina_app.area_picker_presentation._area_picker_dialog._on_search** (nested_function, lines 512–513, 2 lines, risk `support`): Handles on search for the other feature.

## `spina_app/audit_presentation.py`

- **spina_app.audit_presentation.configure_audit_presentation_dependencies** (function, lines 7–12, 6 lines, risk `support`): Handles configure audit presentation dependencies for the other feature.
- **spina_app.audit_presentation._build_audit_tab** (function, lines 21–90, 70 lines, risk `financial_calculation`): Builds build audit tab for the data bank feature.
- **spina_app.audit_presentation.refresh_audit_tab** (function, lines 92–204, 113 lines, risk `financial_calculation`): Refreshes refresh audit tab for the data bank feature.

## `spina_app/calendar_presentation.py`

- **spina_app.calendar_presentation.configure_calendar_dependencies** (function, lines 20–25, 6 lines, risk `support`): Handles configure calendar dependencies for the other feature.
- **spina_app.calendar_presentation._CalendarPopup** (class, lines 33–161, 129 lines, risk `container`): Groups CalendarPopup for the other feature.
- **spina_app.calendar_presentation._CalendarPopup.__init__** (method, lines 34–65, 32 lines, risk `ui_only`): Handles init for the other feature.
- **spina_app.calendar_presentation._CalendarPopup._build_ui** (method, lines 67–102, 36 lines, risk `ui_only`): Builds build ui for the other feature.
- **spina_app.calendar_presentation._CalendarPopup._render** (method, lines 104–123, 20 lines, risk `ui_only`): Handles render for the other feature.
- **spina_app.calendar_presentation._CalendarPopup._pick** (method, lines 125–130, 6 lines, risk `support`): Handles pick for the other feature.
- **spina_app.calendar_presentation._CalendarPopup._prev_month** (method, lines 132–137, 6 lines, risk `support`): Handles prev month for the other feature.
- **spina_app.calendar_presentation._CalendarPopup._next_month** (method, lines 139–144, 6 lines, risk `support`): Handles next month for the other feature.
- **spina_app.calendar_presentation._CalendarPopup._today** (method, lines 146–149, 4 lines, risk `support`): Handles today for the other feature.
- **spina_app.calendar_presentation._CalendarPopup._clear** (method, lines 151–153, 3 lines, risk `support`): Handles clear for the other feature.
- **spina_app.calendar_presentation._CalendarPopup._close** (method, lines 155–161, 7 lines, risk `support`): Handles close for the other feature.
- **spina_app.calendar_presentation._CalendarRangePopup** (class, lines 164–359, 196 lines, risk `container`): Groups CalendarRangePopup for the other feature.
- **spina_app.calendar_presentation._CalendarRangePopup.__init__** (method, lines 165–210, 46 lines, risk `ui_only`): Handles init for the other feature.
- **spina_app.calendar_presentation._CalendarRangePopup._build_ui** (method, lines 212–252, 41 lines, risk `ui_only`): Builds build ui for the other feature.
- **spina_app.calendar_presentation._CalendarRangePopup._render** (method, lines 254–283, 30 lines, risk `ui_only`): Handles render for the other feature.
- **spina_app.calendar_presentation._CalendarRangePopup._refresh_info** (method, lines 285–291, 7 lines, risk `ui_only`): Refreshes refresh info for the other feature.
- **spina_app.calendar_presentation._CalendarRangePopup._pick** (method, lines 293–317, 25 lines, risk `support`): Handles pick for the other feature.
- **spina_app.calendar_presentation._CalendarRangePopup._apply** (method, lines 319–324, 6 lines, risk `support`): Handles apply for the other feature.
- **spina_app.calendar_presentation._CalendarRangePopup._prev_month** (method, lines 326–332, 7 lines, risk `support`): Handles prev month for the other feature.
- **spina_app.calendar_presentation._CalendarRangePopup._next_month** (method, lines 334–340, 7 lines, risk `support`): Handles next month for the other feature.
- **spina_app.calendar_presentation._CalendarRangePopup._today** (method, lines 342–346, 5 lines, risk `support`): Handles today for the other feature.
- **spina_app.calendar_presentation._CalendarRangePopup._clear** (method, lines 348–351, 4 lines, risk `support`): Handles clear for the other feature.
- **spina_app.calendar_presentation._CalendarRangePopup._close** (method, lines 353–359, 7 lines, risk `support`): Handles close for the other feature.
- **spina_app.calendar_presentation.pick_date_range** (function, lines 361–404, 44 lines, risk `support`): Handles pick date range for the utilities feature.
- **spina_app.calendar_presentation.pick_date** (function, lines 406–435, 30 lines, risk `support`): Handles pick date for the other feature.

## `spina_app/client_form_presentation.py`

- **spina_app.client_form_presentation.configure_client_form_dependencies** (function, lines 13–18, 6 lines, risk `support`): Handles configure client form dependencies for the clients feature.
- **spina_app.client_form_presentation._app__client_form** (function, lines 24–672, 649 lines, risk `ui_only`): Handles app client form for the clients feature.
- **spina_app.client_form_presentation._app__client_form._flex_due_options** (nested_function, lines 87–144, 58 lines, risk `support`): Handles flex due options for the clients feature.
- **spina_app.client_form_presentation._app__client_form._flex_due_label_from_code** (nested_function, lines 153–162, 10 lines, risk `support`): Handles flex due label from code for the clients feature.
- **spina_app.client_form_presentation._app__client_form._flex_due_code_from_choice** (nested_function, lines 170–183, 14 lines, risk `support`): Handles flex due code from choice for the clients feature.
- **spina_app.client_form_presentation._app__client_form._current_anchor_for_form** (nested_function, lines 197–205, 9 lines, risk `support`): Handles current anchor for form for the clients feature.
- **spina_app.client_form_presentation._app__client_form._prime_due_defaults** (nested_function, lines 207–226, 20 lines, risk `support`): Handles prime due defaults for the clients feature.
- **spina_app.client_form_presentation._app__client_form.row** (nested_function, lines 235–237, 3 lines, risk `ui_only`): Handles row for the clients feature.
- **spina_app.client_form_presentation._app__client_form._dom_seed_date** (nested_function, lines 269–284, 16 lines, risk `support`): Handles dom seed date for the clients feature.
- **spina_app.client_form_presentation._app__client_form._pick_dom** (nested_function, lines 286–298, 13 lines, risk `support`): Handles pick dom for the clients feature.
- **spina_app.client_form_presentation._app__client_form._toggle_new_until** (nested_function, lines 375–384, 10 lines, risk `ui_only`): Handles toggle new until for the clients feature.
- **spina_app.client_form_presentation._app__client_form._toggle_due_widgets** (nested_function, lines 386–406, 21 lines, risk `ui_only`): Handles toggle due widgets for the clients feature.
- **spina_app.client_form_presentation._app__client_form._toggle_paymode_other** (nested_function, lines 408–421, 14 lines, risk `ui_only`): Handles toggle paymode other for the clients feature.
- **spina_app.client_form_presentation._app__client_form._compute_dates** (nested_function, lines 423–448, 26 lines, risk `financial_calculation`): Handles compute dates for the clients feature.
- **spina_app.client_form_presentation._app__client_form._validate_date** (nested_function, lines 472–477, 6 lines, risk `support`): Validates validate date for the utilities feature.
- **spina_app.client_form_presentation._app__client_form.save** (nested_function, lines 479–583, 105 lines, risk `financial_calculation`): Handles save for the clients feature.
- **spina_app.client_form_presentation._app__client_form.cancel** (nested_function, lines 585–590, 6 lines, risk `support`): Handles cancel for the clients feature.

## `spina_app/client_history_presentation.py`

- **spina_app.client_history_presentation.configure_client_history_dependencies** (function, lines 13–18, 6 lines, risk `support`): Handles configure client history dependencies for the clients feature.
- **spina_app.client_history_presentation._app_open_client_history_dialog** (function, lines 24–537, 514 lines, risk `ui_only`): Handles app open client history dialog for the clients feature.
- **spina_app.client_history_presentation._app_open_client_history_dialog._coerce_rows** (nested_function, lines 49–59, 11 lines, risk `support`): Handles coerce rows for the clients feature.
- **spina_app.client_history_presentation._app_open_client_history_dialog._ts_key** (nested_function, lines 61–62, 2 lines, risk `support`): Handles ts key for the clients feature.
- **spina_app.client_history_presentation._app_open_client_history_dialog._safe_json_load** (nested_function, lines 64–70, 7 lines, risk `support`): Handles safe json load for the clients feature.
- **spina_app.client_history_presentation._app_open_client_history_dialog._pretty** (nested_function, lines 72–87, 16 lines, risk `support`): Handles pretty for the clients feature.
- **spina_app.client_history_presentation._app_open_client_history_dialog._fmt_scalar** (nested_function, lines 89–96, 8 lines, risk `filesystem`): Handles fmt scalar for the clients feature.
- **spina_app.client_history_presentation._app_open_client_history_dialog._diff_pairs** (nested_function, lines 98–117, 20 lines, risk `support`): Handles diff pairs for the clients feature.
- **spina_app.client_history_presentation._app_open_client_history_dialog._diff_summary** (nested_function, lines 119–129, 11 lines, risk `support`): Handles diff summary for the clients feature.
- **spina_app.client_history_presentation._app_open_client_history_dialog._mk_ro_text** (nested_function, lines 255–266, 12 lines, risk `ui_only`): Handles mk ro text for the clients feature.
- **spina_app.client_history_presentation._app_open_client_history_dialog._set_ro** (nested_function, lines 277–281, 5 lines, risk `ui_only`): Updates set ro for the clients feature.
- **spina_app.client_history_presentation._app_open_client_history_dialog._render_tab1** (nested_function, lines 283–322, 40 lines, risk `ui_only`): Handles render tab1 for the clients feature.
- **spina_app.client_history_presentation._app_open_client_history_dialog._on_sel1** (nested_function, lines 324–341, 18 lines, risk `support`): Handles on sel1 for the clients feature.
- **spina_app.client_history_presentation._app_open_client_history_dialog._in_date_range** (nested_function, lines 390–400, 11 lines, risk `support`): Handles in date range for the utilities feature.
- **spina_app.client_history_presentation._app_open_client_history_dialog._render_tab2** (nested_function, lines 402–428, 27 lines, risk `ui_only`): Handles render tab2 for the clients feature.
- **spina_app.client_history_presentation._app_open_client_history_dialog._render_tab3** (nested_function, lines 490–522, 33 lines, risk `ui_only`): Handles render tab3 for the clients feature.
- **spina_app.client_history_presentation._app_open_client_history_dialog._on_sel3** (nested_function, lines 524–533, 10 lines, risk `support`): Handles on sel3 for the clients feature.

## `spina_app/client_queries.py`

- **spina_app.client_queries.configure_client_queries_dependencies** (function, lines 27–34, 8 lines, risk `support`): Bind application-owned globals required by the extracted LoanDB methods.
- **spina_app.client_queries.get_all_clients** (function, lines 49–335, 287 lines, risk `database_read`): Return client names (optionally filtered by loan_type) with optional search. search_by: - 'all' / 'both' : match across common client fields (default) - 'client' : match in client name only - 'area' : match in area only - 'principal' : match in principal (as text) - 'released' : match in date_releas
- **spina_app.client_queries.get_all_clients._start_date_expr** (nested_function, lines 119–127, 9 lines, risk `support`): Handles start date expr for the clients feature.
- **spina_app.client_queries.get_client_info** (function, lines 337–351, 15 lines, risk `database_read`): Retrieves get client info for the clients feature.
- **spina_app.client_queries.get_client_link_meta** (function, lines 353–372, 20 lines, risk `database_read`): Return (client_uid, person_uid, link_opt_out) for a client.
- **spina_app.client_queries.find_clients_by_person_uid** (function, lines 374–384, 11 lines, risk `database_read`): Return list of client rows linked to this person_uid.
- **spina_app.client_queries.get_client_uid** (function, lines 386–399, 14 lines, risk `database_read`): Return client_uid for (name, loan_type).
- **spina_app.client_queries.get_client_by_uid** (function, lines 401–410, 10 lines, risk `database_read`): Retrieves get client by uid for the clients feature.
- **spina_app.client_queries.get_client_history** (function, lines 412–462, 51 lines, risk `database_read`): Return audit history rows (most recent first). Prefer client_uid. Normalizes key names for UI: ts -> changed_at before_json -> old_json after_json -> new_json
- **spina_app.client_queries.get_person_uid_for_client_uid** (function, lines 464–478, 15 lines, risk `database_read`): Retrieves get person uid for client uid for the clients feature.

## `spina_app/collector_dialog_presentation.py`

- **spina_app.collector_dialog_presentation.configure_collector_dialog_dependencies** (function, lines 21–26, 6 lines, risk `support`): Handles configure collector dialog dependencies for the collectors feature.
- **spina_app.collector_dialog_presentation._spina_v27_collector_editor_dialog** (function, lines 36–385, 350 lines, risk `ui_only`): Modern route editor: Available Areas vs Assigned Route Order.
- **spina_app.collector_dialog_presentation._spina_v27_collector_editor_dialog._panel** (nested_function, lines 105–109, 5 lines, risk `ui_only`): Handles panel for the collectors feature.
- **spina_app.collector_dialog_presentation._spina_v27_collector_editor_dialog._assigned_keys** (nested_function, lines 147–148, 2 lines, risk `support`): Handles assigned keys for the collectors feature.
- **spina_app.collector_dialog_presentation._spina_v27_collector_editor_dialog._refresh_lists** (nested_function, lines 150–189, 40 lines, risk `ui_only`): Refreshes refresh lists for the collectors feature.
- **spina_app.collector_dialog_presentation._spina_v27_collector_editor_dialog._clean_assigned_display** (nested_function, lines 191–196, 6 lines, risk `support`): Handles clean assigned display for the collectors feature.
- **spina_app.collector_dialog_presentation._spina_v27_collector_editor_dialog._add_selected** (nested_function, lines 198–214, 17 lines, risk `support`): Handles add selected for the collectors feature.
- **spina_app.collector_dialog_presentation._spina_v27_collector_editor_dialog._remove_selected** (nested_function, lines 216–227, 12 lines, risk `support`): Removes remove selected for the collectors feature.
- **spina_app.collector_dialog_presentation._spina_v27_collector_editor_dialog._move_selected** (nested_function, lines 229–247, 19 lines, risk `support`): Handles move selected for the collectors feature.
- **spina_app.collector_dialog_presentation._spina_v27_collector_editor_dialog._move_top** (nested_function, lines 249–260, 12 lines, risk `support`): Handles move top for the collectors feature.
- **spina_app.collector_dialog_presentation._spina_v27_collector_editor_dialog._move_bottom** (nested_function, lines 262–273, 12 lines, risk `support`): Handles move bottom for the collectors feature.
- **spina_app.collector_dialog_presentation._spina_v27_collector_editor_dialog._add_all_visible** (nested_function, lines 275–283, 9 lines, risk `support`): Handles add all visible for the collectors feature.
- **spina_app.collector_dialog_presentation._spina_v27_collector_editor_dialog._clear_assigned** (nested_function, lines 285–294, 10 lines, risk `support`): Handles clear assigned for the collectors feature.
- **spina_app.collector_dialog_presentation._spina_v27_collector_editor_dialog._save** (nested_function, lines 331–359, 29 lines, risk `support`): Handles save for the collectors feature.
- **spina_app.collector_dialog_presentation._spina_v27_collector_editor_dialog._cancel** (nested_function, lines 361–367, 7 lines, risk `support`): Handles cancel for the collectors feature.

## `spina_app/collector_refresh_presentation.py`

- **spina_app.collector_refresh_presentation.configure_collector_refresh_dependencies** (function, lines 14–19, 6 lines, risk `support`): Handles configure collector refresh dependencies for the collectors feature.
- **spina_app.collector_refresh_presentation.refresh_collectors** (function, lines 26–633, 608 lines, risk `filesystem`): Refresh the Collector's Route table (enhanced). - Supports older collectors.json schemas (dict/list/strings) and normalizes to: {name: {areas: [...], notes: "..."}} - Computes: * unassigned areas (master areas not in any route) * unknown route areas (route areas not found in master areas) * conflict
- **spina_app.collector_refresh_presentation.refresh_collectors._norm_area** (nested_function, lines 106–110, 5 lines, risk `support`): Handles norm area for the collectors feature.
- **spina_app.collector_refresh_presentation.refresh_collectors._lt_key** (nested_function, lines 112–116, 5 lines, risk `filesystem`): Handles lt key for the collectors feature.
- **spina_app.collector_refresh_presentation.refresh_collectors._expand_route_area_to_master_norms** (nested_function, lines 217–250, 34 lines, risk `support`): Return list of master area norms covered by this route entry. Rules: - If route entry has sub: match exact (main, sub) in master areas (separator-insensitive). - If route entry is MAIN-only: cover ALL master areas that share that main. - Legacy: if the full string matches a master area exactly, acce
- **spina_app.collector_refresh_presentation.refresh_collectors._sort_key** (nested_function, lines 533–549, 17 lines, risk `support`): Handles sort key for the collectors feature.

## `spina_app/collector_tab_presentation.py`

- **spina_app.collector_tab_presentation.configure_collector_tab_dependencies** (function, lines 20–25, 6 lines, risk `support`): Handles configure collector tab dependencies for the collectors feature.
- **spina_app.collector_tab_presentation._spina_v27_build_collectors_tab** (function, lines 35–327, 293 lines, risk `ui_only`): Handles spina v27 build collectors tab for the collectors feature.

## `spina_app/dashboard_chart_presentation.py`

- **spina_app.dashboard_chart_presentation.configure_dashboard_chart_dependencies** (function, lines 23–35, 13 lines, risk `support`): Handles configure dashboard chart dependencies for the dashboard feature.
- **spina_app.dashboard_chart_presentation._spina_v18_draw_dashboard_charts** (function, lines 38–149, 112 lines, risk `filesystem`): Handles spina v18 draw dashboard charts for the dashboard feature.
- **spina_app.dashboard_chart_presentation._spina_v20_fix_chart_titles** (function, lines 152–179, 28 lines, risk `ui_only`): Rename the chart labels without rebuilding the whole tab.
- **spina_app.dashboard_chart_presentation._spina_v20_draw_dashboard_charts** (function, lines 182–315, 134 lines, risk `financial_calculation`): Replace old progress/remaining charts with more useful active-client charts.

## `spina_app/databank_presentation.py`

- **spina_app.databank_presentation.configure_databank_presentation_dependencies** (function, lines 25–30, 6 lines, risk `support`): Handles configure databank presentation dependencies for the data bank feature.
- **spina_app.databank_presentation._spina_v15_palette** (function, lines 39–55, 17 lines, risk `support`): Handles spina v15 palette for the data bank feature.
- **spina_app.databank_presentation._spina_v15_setup_databank_styles** (function, lines 57–104, 48 lines, risk `ui_only`): Handles spina v15 setup databank styles for the data bank feature.
- **spina_app.databank_presentation._spina_v15_stat_card** (function, lines 106–110, 5 lines, risk `ui_only`): Handles spina v15 stat card for the data bank feature.
- **spina_app.databank_presentation._spina_v15_build_data_tab** (function, lines 112–247, 136 lines, risk `ui_only`): Modern Data Bank page: card header, fast search, summary cards, grouped actions, same grid logic.
- **spina_app.databank_presentation._spina_v15_update_databank_cards** (function, lines 249–287, 39 lines, risk `support`): Handles spina v15 update databank cards for the data bank feature.
- **spina_app.databank_presentation._spina_v15_refresh_data_grid** (function, lines 289–306, 18 lines, risk `ui_only`): Handles spina v15 refresh data grid for the data bank feature.
- **spina_app.databank_presentation._spina_v15_update_data_toolbar** (function, lines 308–314, 7 lines, risk `support`): Handles spina v15 update data toolbar for the navigation feature.
- **spina_app.databank_presentation._spina_v15_apply_ui_theme** (function, lines 316–326, 11 lines, risk `support`): Handles spina v15 apply ui theme for the settings feature.
- **spina_app.databank_presentation._spina_v16_apply_bigger_payment_grid** (function, lines 328–348, 21 lines, risk `ui_only`): Make the Data Bank payment grid easier to read: bigger rows, wider client/area/day columns.
- **spina_app.databank_presentation._spina_v16_refresh_data_grid** (function, lines 350–356, 7 lines, risk `support`): Handles spina v16 refresh data grid for the data bank feature.
- **spina_app.databank_presentation._spina_v53_widget_text** (function, lines 364–368, 5 lines, risk `support`): Handles spina v53 widget text for the data bank feature.
- **spina_app.databank_presentation._spina_v53_walk_widgets** (function, lines 371–378, 8 lines, risk `support`): Handles spina v53 walk widgets for the utilities feature.
- **spina_app.databank_presentation._spina_v53_restore_databank_import_control** (function, lines 381–420, 40 lines, risk `backup`): Handles spina v53 restore databank import control for the data bank feature.
- **spina_app.databank_presentation._spina_v53_build_data_tab_with_import_control** (function, lines 423–426, 4 lines, risk `backup`): Handles spina v53 build data tab with import control for the data bank feature.

## `spina_app/import_log_presentation.py`

- **spina_app.import_log_presentation.configure_import_log_dependencies** (function, lines 17–21, 5 lines, risk `support`): Handles configure import log dependencies for the other feature.
- **spina_app.import_log_presentation._show_import_log_window** (function, lines 24–360, 337 lines, risk `filesystem`): Organized import log viewer (tabs + search + save/copy). Tabs: - All (chronological) - Inserted / Updated - Skipped Duplicates / Skipped Unknown / Skipped - Errors - Header/Info / Other
- **spina_app.import_log_presentation._show_import_log_window._classify** (nested_function, lines 52–69, 18 lines, risk `support`): Handles classify for the other feature.
- **spina_app.import_log_presentation._show_import_log_window._make_tab** (nested_function, lines 129–153, 25 lines, risk `ui_only`): Handles make tab for the other feature.
- **spina_app.import_log_presentation._show_import_log_window._render** (nested_function, lines 158–178, 21 lines, risk `ui_only`): Handles render for the other feature.
- **spina_app.import_log_presentation._show_import_log_window._current_cat** (nested_function, lines 180–185, 6 lines, risk `support`): Handles current cat for the other feature.
- **spina_app.import_log_presentation._show_import_log_window._refresh** (nested_function, lines 187–200, 14 lines, risk `support`): Handles refresh for the other feature.
- **spina_app.import_log_presentation._show_import_log_window._build_save_text** (nested_function, lines 203–231, 29 lines, risk `support`): Builds build save text for the other feature.
- **spina_app.import_log_presentation._show_import_log_window._write_to** (nested_function, lines 233–244, 12 lines, risk `filesystem`): Saves write to for the other feature.
- **spina_app.import_log_presentation._show_import_log_window._copy_visible** (nested_function, lines 256–263, 8 lines, risk `support`): Handles copy visible for the other feature.
- **spina_app.import_log_presentation._show_import_log_window._copy_all** (nested_function, lines 265–271, 7 lines, risk `support`): Handles copy all for the other feature.
- **spina_app.import_log_presentation._show_import_log_window._save_visible_as** (nested_function, lines 273–291, 19 lines, risk `ui_only`): Saves save visible as for the other feature.
- **spina_app.import_log_presentation._show_import_log_window._save_all_as** (nested_function, lines 293–310, 18 lines, risk `ui_only`): Saves save all as for the other feature.
- **spina_app.import_log_presentation._show_import_log_window._open_saved** (nested_function, lines 312–318, 7 lines, risk `support`): Handles open saved for the other feature.
- **spina_app.import_log_presentation._show_import_log_window._open_data_folder** (nested_function, lines 320–324, 5 lines, risk `support`): Handles open data folder for the other feature.

## `spina_app/linked_client_queries.py`

- **spina_app.linked_client_queries.configure_linked_client_query_dependencies** (function, lines 27–34, 8 lines, risk `support`): Bind application-owned globals required by the extracted LoanDB methods.
- **spina_app.linked_client_queries.get_linked_client_uids** (function, lines 47–81, 35 lines, risk `support`): Return all client_uids linked to the same person_uid (includes self). If not linked, returns [client_uid].
- **spina_app.linked_client_queries.get_transaction_history_for_client_uids** (function, lines 83–112, 30 lines, risk `database_read`): Return databank audit rows (most recent first) for a list of client_uids.
- **spina_app.linked_client_queries.get_transactions_for_client_uids** (function, lines 114–173, 60 lines, risk `database_read`): Return transactions for a linked person (both Regular + 7x7), using client_uid when available. Includes best-effort fallback to legacy rows where client_uid is blank but (name, loan_type) matches.
- **spina_app.linked_client_queries.count_clients_in_area** (function, lines 175–200, 26 lines, risk `database_read`): Count ACTIVE clients in an area. Archived-only areas should not keep showing up as 'in use' in the UI.
- **spina_app.linked_client_queries.get_client_by_person_uid_and_loan_type** (function, lines 202–216, 15 lines, risk `database_read`): Return a single client row matching (person_uid, loan_type), or None.
- **spina_app.linked_client_queries.get_transactions_for_client** (function, lines 218–254, 37 lines, risk `database_read`): Retrieves get transactions for client for the clients feature.

## `spina_app/loan_context_queries.py`

- **spina_app.loan_context_queries.configure_loan_context_dependencies** (function, lines 5–10, 6 lines, risk `support`): Handles configure loan context dependencies for the loans feature.
- **spina_app.loan_context_queries._set_last_error** (function, lines 21–25, 5 lines, risk `support`): Updates set last error for the loans feature.
- **spina_app.loan_context_queries.get_last_error** (function, lines 27–31, 5 lines, risk `support`): Retrieves get last error for the loans feature.
- **spina_app.loan_context_queries.set_default_loan_type** (function, lines 33–38, 6 lines, risk `support`): Set the default loan_type context used when caller does not pass loan_type.
- **spina_app.loan_context_queries._effective_lt** (function, lines 40–43, 4 lines, risk `support`): Handles effective lt for the loans feature.
- **spina_app.loan_context_queries.get_audit_new_loan_rows** (function, lines 45–107, 63 lines, risk `database_read`): Return append-only ADD audit rows for new loans.
- **spina_app.loan_context_queries.get_all_areas** (function, lines 109–144, 36 lines, risk `database_read`): Return area master list for UI dropdowns. Hides areas that are used only by archived clients, but keeps: - areas with at least one active client - areas with no clients yet (manually-added / still-unused)

## `spina_app/login_dialog_presentation.py`

- **spina_app.login_dialog_presentation.configure_login_dialog_dependencies** (function, lines 10–15, 6 lines, risk `authentication`): Handles configure login dialog dependencies for the authentication feature.
- **spina_app.login_dialog_presentation._spina_v32_prompt_login** (function, lines 24–257, 234 lines, risk `authentication`): Modern account-based login dialog. Returns (username, internal_access_profile).
- **spina_app.login_dialog_presentation._spina_v32_prompt_login._toggle_show** (nested_function, lines 117–121, 5 lines, risk `ui_only`): Handles toggle show for the authentication feature.
- **spina_app.login_dialog_presentation._spina_v32_prompt_login._refresh_account_info** (nested_function, lines 135–146, 12 lines, risk `authentication`): Refreshes refresh account info for the authentication feature.
- **spina_app.login_dialog_presentation._spina_v32_prompt_login._ok** (nested_function, lines 148–186, 39 lines, risk `authentication`): Handles ok for the authentication feature.
- **spina_app.login_dialog_presentation._spina_v32_prompt_login._cancel** (nested_function, lines 188–193, 6 lines, risk `support`): Handles cancel for the authentication feature.
- **spina_app.login_dialog_presentation._spina_v32_prompt_login._enter** (nested_function, lines 216–217, 2 lines, risk `support`): Handles enter for the authentication feature.

## `spina_app/long_task_presentation.py`

- **spina_app.long_task_presentation.configure_long_task_dependencies** (function, lines 21–26, 6 lines, risk `support`): Handles configure long task dependencies for the other feature.
- **spina_app.long_task_presentation._run_long_task** (function, lines 36–308, 273 lines, risk `ui_only`): Run work_fn() in a background thread with a simple modal 'Please wait' dialog. Improvements: - Optional Cancel button (signals a cancel_event to work_fn if it supports it) - Optional timeout (prevents UI from hanging forever on stuck tasks) - Cleanup is guarded so it can't run twice
- **spina_app.long_task_presentation._run_long_task._cleanup_dialog** (nested_function, lines 61–82, 22 lines, risk `support`): Handles cleanup dialog for the other feature.
- **spina_app.long_task_presentation._run_long_task._finish** (nested_function, lines 84–129, 46 lines, risk `support`): Handles finish for the other feature.
- **spina_app.long_task_presentation._run_long_task._request_cancel** (nested_function, lines 131–155, 25 lines, risk `ui_only`): Handles request cancel for the other feature.
- **spina_app.long_task_presentation._run_long_task._watchdog** (nested_function, lines 157–192, 36 lines, risk `ui_only`): Handles watchdog for the other feature.
- **spina_app.long_task_presentation._run_long_task._call_work_fn** (nested_function, lines 255–277, 23 lines, risk `support`): Call work_fn, optionally passing cancel_event if supported.
- **spina_app.long_task_presentation._run_long_task._worker** (nested_function, lines 279–306, 28 lines, risk `ui_only`): Handles worker for the other feature.

## `spina_app/navigation.py`

- **spina_app.navigation._noop_log** (function, lines 11–12, 2 lines, risk `support`): Handles noop log for the navigation feature.
- **spina_app.navigation.fmt_currency** (function, lines 18–19, 2 lines, risk `support`): Handles fmt currency for the navigation feature.
- **spina_app.navigation.configure_navigation_dependencies** (function, lines 22–26, 5 lines, risk `support`): Bind application-owned logging and currency display helpers.
- **spina_app.navigation._update_data_toolbar** (function, lines 29–57, 29 lines, risk `support`): Updates update data toolbar for the navigation feature.
- **spina_app.navigation._side_nav_items** (function, lines 60–91, 32 lines, risk `support`): Return visible main tabs as (tab_widget, title, icon).
- **spina_app.navigation._rebuild_side_nav** (function, lines 94–198, 105 lines, risk `ui_only`): Rebuild the modern left-side navigation from the currently visible notebook tabs.
- **spina_app.navigation._refresh_side_nav_selection** (function, lines 201–234, 34 lines, risk `ui_only`): Update sidebar button colors to match the selected notebook tab.
- **spina_app.navigation._header_palette** (function, lines 237–279, 43 lines, risk `support`): Compact color palette for the modern top header.
- **spina_app.navigation._make_header_button** (function, lines 282–308, 27 lines, risk `ui_only`): Create a flatter, modern top-bar button using tk.Button for better dark-mode control.
- **spina_app.navigation._refresh_mode_toggle** (function, lines 311–342, 32 lines, risk `ui_only`): Update the Regular/7x7 segmented buttons after a mode change or theme change.
- **spina_app.navigation._vscroll** (function, lines 345–351, 7 lines, risk `support`): Handles vscroll for the navigation feature.
- **spina_app.navigation._month_label** (function, lines 354–355, 2 lines, risk `support`): Handles month label for the navigation feature.
- **spina_app.navigation._on_mousewheel_sync** (function, lines 358–387, 30 lines, risk `support`): Mouse wheel scroll should move both name_tree (left) and days_tree (right) together.
- **spina_app.navigation._update_toolbar_states** (function, lines 390–397, 8 lines, risk `ui_only`): Updates update toolbar states for the navigation feature.

## `spina_app/note_editor_presentation.py`

- **spina_app.note_editor_presentation.configure_note_editor_dependencies** (function, lines 17–22, 6 lines, risk `support`): Handles configure note editor dependencies for the notes feature.
- **spina_app.note_editor_presentation.NoteEditorDialog** (class, lines 31–668, 638 lines, risk `container`): Improved per-client notes editor. Features: - Dated and undated notes - Scope: Shared (both Regular/7x7) or This loan type - Left panel: list of existing notes (with search) - Autosave (debounced) + unsaved indicator - Safe switching between notes (prompts if needed) Notes storage is handled by get_
- **spina_app.note_editor_presentation.NoteEditorDialog.__init__** (method, lines 43–108, 66 lines, risk `ui_only`): Handles init for the notes feature.
- **spina_app.note_editor_presentation.NoteEditorDialog._migrate_legacy_notes_if_needed** (method, lines 111–180, 70 lines, risk `support`): Move legacy name-based keys into stable-id keys for this client (best-effort). This prevents collisions if names repeat, and keeps notes attached even if a name changes. Runs only when we have a stable id (person_uid or client_uid).
- **spina_app.note_editor_presentation.NoteEditorDialog._title_text** (method, lines 182–184, 3 lines, risk `support`): Handles title text for the notes feature.
- **spina_app.note_editor_presentation.NoteEditorDialog._set_dirty** (method, lines 186–192, 7 lines, risk `support`): Updates set dirty for the notes feature.
- **spina_app.note_editor_presentation.NoteEditorDialog._note_date_value** (method, lines 194–196, 3 lines, risk `support`): Handles note date value for the notes feature.
- **spina_app.note_editor_presentation.NoteEditorDialog._sig_for_text** (method, lines 198–203, 6 lines, risk `support`): Handles sig for text for the notes feature.
- **spina_app.note_editor_presentation.NoteEditorDialog._validate_date_or_warn** (method, lines 205–218, 14 lines, risk `support`): Validates validate date or warn for the utilities feature.
- **spina_app.note_editor_presentation.NoteEditorDialog._auto_choose_scope** (method, lines 220–229, 10 lines, risk `support`): Handles auto choose scope for the notes feature.
- **spina_app.note_editor_presentation.NoteEditorDialog._scope_label** (method, lines 231–236, 6 lines, risk `support`): Handles scope label for the notes feature.
- **spina_app.note_editor_presentation.NoteEditorDialog._format_list_item** (method, lines 238–243, 6 lines, risk `filesystem`): Handles format list item for the utilities feature.
- **spina_app.note_editor_presentation.NoteEditorDialog._focus_search** (method, lines 245–251, 7 lines, risk `ui_only`): Handles focus search for the notes feature.
- **spina_app.note_editor_presentation.NoteEditorDialog._build_ui** (method, lines 254–339, 86 lines, risk `ui_only`): Builds build ui for the notes feature.
- **spina_app.note_editor_presentation.NoteEditorDialog._collect_items** (method, lines 342–385, 44 lines, risk `support`): Handles collect items for the notes feature.
- **spina_app.note_editor_presentation.NoteEditorDialog._collect_items.add_scope** (nested_function, lines 345–371, 27 lines, risk `support`): Handles add scope for the notes feature.
- **spina_app.note_editor_presentation.NoteEditorDialog._refresh_list** (method, lines 387–411, 25 lines, risk `ui_only`): Refreshes refresh list for the notes feature.
- **spina_app.note_editor_presentation.NoteEditorDialog._on_list_select** (method, lines 413–439, 27 lines, risk `support`): Handles on list select for the notes feature.
- **spina_app.note_editor_presentation.NoteEditorDialog._pick_date** (method, lines 442–450, 9 lines, risk `support`): Handles pick date for the notes feature.
- **spina_app.note_editor_presentation.NoteEditorDialog._jump_today** (method, lines 452–462, 11 lines, risk `support`): Handles jump today for the notes feature.
- **spina_app.note_editor_presentation.NoteEditorDialog._jump_default** (method, lines 464–470, 7 lines, risk `support`): Handles jump default for the notes feature.
- **spina_app.note_editor_presentation.NoteEditorDialog._clear_text** (method, lines 472–481, 10 lines, risk `support`): Handles clear text for the notes feature.
- **spina_app.note_editor_presentation.NoteEditorDialog._open_notes_file** (method, lines 483–491, 9 lines, risk `support`): Handles open notes file for the notes feature.
- **spina_app.note_editor_presentation.NoteEditorDialog._load_note** (method, lines 494–526, 33 lines, risk `support`): Loads load note for the notes feature.
- **spina_app.note_editor_presentation.NoteEditorDialog._save_note** (method, lines 528–570, 43 lines, risk `support`): Saves save note for the notes feature.
- **spina_app.note_editor_presentation.NoteEditorDialog._delete_note** (method, lines 572–609, 38 lines, risk `support`): Removes delete note for the notes feature.
- **spina_app.note_editor_presentation.NoteEditorDialog._on_text_modified** (method, lines 612–620, 9 lines, risk `support`): Handles on text modified for the notes feature.
- **spina_app.note_editor_presentation.NoteEditorDialog._schedule_autosave** (method, lines 622–634, 13 lines, risk `ui_only`): Handles schedule autosave for the notes feature.
- **spina_app.note_editor_presentation.NoteEditorDialog._confirm_before_switch** (method, lines 636–654, 19 lines, risk `support`): Handles confirm before switch for the notes feature.
- **spina_app.note_editor_presentation.NoteEditorDialog._save_and_close** (method, lines 656–658, 3 lines, risk `support`): Saves save and close for the notes feature.
- **spina_app.note_editor_presentation.NoteEditorDialog._close** (method, lines 660–668, 9 lines, risk `support`): Handles close for the notes feature.

## `spina_app/postgres_compat.py`

- **spina_app.postgres_compat.configure_postgres_compat_dependencies** (function, lines 13–18, 6 lines, risk `support`): Handles configure postgres compat dependencies for the database feature.
- **spina_app.postgres_compat._spina_pg_sha256** (function, lines 31–33, 3 lines, risk `support`): Handles spina pg sha256 for the database feature.
- **spina_app.postgres_compat._spina_pg_guess_file_type** (function, lines 35–56, 22 lines, risk `support`): Handles spina pg guess file type for the database feature.
- **spina_app.postgres_compat._spina_pg_guess_report_date** (function, lines 58–68, 11 lines, risk `reports`): Handles spina pg guess report date for the reports feature.
- **spina_app.postgres_compat._spina_pg_guess_collector** (function, lines 70–79, 10 lines, risk `filesystem`): Handles spina pg guess collector for the collectors feature.
- **spina_app.postgres_compat._spina_pg_normalize_value** (function, lines 81–88, 8 lines, risk `support`): Convert PostgreSQL-returned values into SQLite-like values.
- **spina_app.postgres_compat._spina_pg_replace_qmarks** (function, lines 90–114, 25 lines, risk `support`): Replace SQLite ? parameters with psycopg %s outside quoted strings.
- **spina_app.postgres_compat._spina_pg_escape_literal_percents** (function, lines 116–142, 27 lines, risk `support`): Escape literal percent signs for psycopg while preserving %s/%b/%t placeholders. Old SQLite queries commonly contain LIKE '%ADV%' or LIKE '%[RC:%'. Psycopg uses %s-style placeholders, so a literal % in the SQL text must be doubled as %%. Without this, ADV/reason queries can fail silently inside the 

## `spina_app/side_navigation_presentation.py`

- **spina_app.side_navigation_presentation.configure_side_navigation_dependencies** (function, lines 22–27, 6 lines, risk `support`): Handles configure side navigation dependencies for the navigation feature.
- **spina_app.side_navigation_presentation._spina_v13_hide_main_notebook_tabs** (function, lines 36–63, 28 lines, risk `ui_only`): Handles spina v13 hide main notebook tabs for the notes feature.
- **spina_app.side_navigation_presentation._spina_v13_side_nav_items** (function, lines 65–96, 32 lines, risk `support`): Return every visible main notebook pane as a sidebar item.
- **spina_app.side_navigation_presentation._spina_v13_rebuild_side_nav** (function, lines 98–196, 99 lines, risk `ui_only`): Modern sidebar rebuild: all visible tabs live here, no top tab row.
- **spina_app.side_navigation_presentation._spina_v13_refresh_side_nav_selection** (function, lines 198–227, 30 lines, risk `ui_only`): Handles spina v13 refresh side nav selection for the navigation feature.
- **spina_app.side_navigation_presentation._spina_v13_setup_style** (function, lines 229–235, 7 lines, risk `support`): Handles spina v13 setup style for the navigation feature.
- **spina_app.side_navigation_presentation._spina_v13_apply_ui_theme** (function, lines 237–244, 8 lines, risk `support`): Handles spina v13 apply ui theme for the settings feature.

## `spina_app/tabs/cash_control.py`

- **spina_app.tabs.cash_control.configure_cash_control_dependencies** (function, lines 25–34, 10 lines, risk `support`): Bind application-owned display and logging helpers used by Cash Control.
- **spina_app.tabs.cash_control._spina_v21_cash_build_tab** (function, lines 37–313, 277 lines, risk `ui_only`): Handles spina v21 cash build tab for the cash control feature.
- **spina_app.tabs.cash_control._spina_v21_cash_draw_charts** (function, lines 316–438, 123 lines, risk `ui_only`): Handles spina v21 cash draw charts for the cash control feature.

## `spina_app/tabs/client_info_logs.py`

- **spina_app.tabs.client_info_logs.configure_client_info_logs_dependencies** (function, lines 26–35, 10 lines, risk `support`): Bind application-owned callbacks used by the CILog presentation module.
- **spina_app.tabs.client_info_logs._spina_v24_cilog_action_color** (function, lines 38–54, 17 lines, risk `support`): Handles spina v24 cilog action color for the clients feature.
- **spina_app.tabs.client_info_logs._spina_v24_cilog_stats** (function, lines 56–79, 24 lines, risk `support`): Handles spina v24 cilog stats for the clients feature.
- **spina_app.tabs.client_info_logs._spina_v24_cilog_draw_charts** (function, lines 81–174, 94 lines, risk `ui_only`): Handles spina v24 cilog draw charts for the clients feature.
- **spina_app.tabs.client_info_logs._spina_v24_cilog_update_cards** (function, lines 176–200, 25 lines, risk `support`): Handles spina v24 cilog update cards for the clients feature.
- **spina_app.tabs.client_info_logs._spina_v24_build_client_info_logs_tab** (function, lines 202–451, 250 lines, risk `ui_only`): Handles spina v24 build client info logs tab for the clients feature.
- **spina_app.tabs.client_info_logs._spina_v24_render_client_info_logs** (function, lines 453–535, 83 lines, risk `ui_only`): Handles spina v24 render client info logs for the clients feature.
- **spina_app.tabs.client_info_logs._spina_v24_refresh_client_info_logs** (function, lines 537–559, 23 lines, risk `support`): Handles spina v24 refresh client info logs for the clients feature.
- **spina_app.tabs.client_info_logs._spina_build_client_info_logs_tab** (function, lines 562–693, 132 lines, risk `ui_only`): Handles spina build client info logs tab for the clients feature.
- **spina_app.tabs.client_info_logs._spina_render_client_info_logs** (function, lines 695–747, 53 lines, risk `ui_only`): Handles spina render client info logs for the clients feature.
- **spina_app.tabs.client_info_logs._spina_refresh_client_info_logs** (function, lines 749–759, 11 lines, risk `support`): Handles spina refresh client info logs for the clients feature.

## `spina_app/tabs/clients.py`

- **spina_app.tabs.clients.configure_clients_dependencies** (function, lines 38–47, 10 lines, risk `support`): Bind application-owned callbacks used by the Clients presentation module.
- **spina_app.tabs.clients._spina_v23_button** (function, lines 50–78, 29 lines, risk `ui_only`): Handles spina v23 button for the clients feature.
- **spina_app.tabs.clients._spina_v23_card** (function, lines 80–90, 11 lines, risk `ui_only`): Handles spina v23 card for the clients feature.
- **spina_app.tabs.clients._spina_v23_selected_name_lt** (function, lines 92–111, 20 lines, risk `support`): Handles spina v23 selected name lt for the clients feature.
- **spina_app.tabs.clients._spina_v23_refresh_client_profile** (function, lines 113–166, 54 lines, risk `ui_only`): Handles spina v23 refresh client profile for the clients feature.
- **spina_app.tabs.clients._spina_v23_build_clients_tab** (function, lines 168–400, 233 lines, risk `ui_only`): Handles spina v23 build clients tab for the clients feature.
- **spina_app.tabs.clients._spina_v23_entry** (function, lines 402–411, 10 lines, risk `ui_only`): Handles spina v23 entry for the clients feature.
- **spina_app.tabs.clients._spina_v23_update_client_cards** (function, lines 413–442, 30 lines, risk `ui_only`): Handles spina v23 update client cards for the clients feature.
- **spina_app.tabs.clients._db_get_client_picture** (function, lines 445–454, 10 lines, risk `support`): Handles db get client picture for the clients feature.
- **spina_app.tabs.clients._app__selected_client_name_and_lt** (function, lines 456–478, 23 lines, risk `support`): Handles app selected client name and lt for the clients feature.
- **spina_app.tabs.clients._app_install_clients_picture_ui** (function, lines 480–535, 56 lines, risk `ui_only`): Handles app install clients picture ui for the clients feature.
- **spina_app.tabs.clients._spina_perf_clients_rows** (function, lines 537–704, 168 lines, risk `database_read`): Bulk load rows for Clients tab in one/few queries, avoiding per-row get_client_info().
- **spina_app.tabs.clients._spina_perf_refresh_clients** (function, lines 706–795, 90 lines, risk `ui_only`): Fast Clients tab refresh for large datasets.
- **spina_app.tabs.clients._spina__client_due_meta** (function, lines 797–809, 13 lines, risk `support`): Handles spina client due meta for the clients feature.
- **spina_app.tabs.clients._spina_route_notice_for_client** (function, lines 811–855, 45 lines, risk `support`): Handles spina route notice for client for the clients feature.

## `spina_app/tabs/collector_route.py`

- **spina_app.tabs.collector_route.configure_collector_route_dependencies** (function, lines 19–28, 10 lines, risk `support`): Bind the desktop-owned Collector Route palette helper.
- **spina_app.tabs.collector_route._spina_v27_update_route_cards** (function, lines 30–87, 58 lines, risk `ui_only`): Handles spina v27 update route cards for the collectors feature.
- **spina_app.tabs.collector_route._spina_v27_hidden_collector_widgets** (function, lines 90–126, 37 lines, risk `ui_only`): Keep hidden compatibility widgets for legacy helper functions.

## `spina_app/tabs/collectors.py`

- **spina_app.tabs.collectors._spina_v25_collector_card** (function, lines 16–26, 11 lines, risk `ui_only`): Handles spina v25 collector card for the collectors feature.
- **spina_app.tabs.collectors._spina_v25_style_collector_trees** (function, lines 29–51, 23 lines, risk `ui_only`): Handles spina v25 style collector trees for the collectors feature.
- **spina_app.tabs.collectors._spina_v25_update_collector_cards** (function, lines 54–106, 53 lines, risk `ui_only`): Handles spina v25 update collector cards for the collectors feature.
- **spina_app.tabs.collectors._collectors_get_selected_name** (function, lines 110–123, 14 lines, risk `ui_only`): Handles collectors get selected name for the collectors feature.
- **spina_app.tabs.collectors._collectors_toggle_sections** (function, lines 125–153, 29 lines, risk `ui_only`): Handles collectors toggle sections for the collectors feature.
- **spina_app.tabs.collectors._collectors_apply_markers** (function, lines 155–190, 36 lines, risk `support`): Update the Sel column (radio/checkbox) based on current selection/multi checks.
- **spina_app.tabs.collectors._collectors_refresh_bulk_bar** (function, lines 192–216, 25 lines, risk `ui_only`): Handles collectors refresh bulk bar for the collectors feature.
- **spina_app.tabs.collectors._collectors_clear_checked** (function, lines 218–230, 13 lines, risk `support`): Handles collectors clear checked for the collectors feature.
- **spina_app.tabs.collectors._collectors_start_inline_edit** (function, lines 232–296, 65 lines, risk `ui_only`): Start inline editing for the currently selected collector (right panel).
- **spina_app.tabs.collectors._collectors_load_inline_edit_fields** (function, lines 298–330, 33 lines, risk `support`): Populate the right-side edit widgets from collectors.json cache.
- **spina_app.tabs.collectors._collectors_cancel_inline_edit** (function, lines 332–373, 42 lines, risk `ui_only`): Cancel inline editing and restore view widgets.
- **spina_app.tabs.collectors._collectors_choose_areas** (function, lines 375–391, 17 lines, risk `support`): Pick areas via existing picker dialog, then load into listbox.
- **spina_app.tabs.collectors._collectors_add_area_text** (function, lines 393–413, 21 lines, risk `support`): Handles collectors add area text for the collectors feature.
- **spina_app.tabs.collectors._collectors_remove_area** (function, lines 415–423, 9 lines, risk `support`): Handles collectors remove area for the collectors feature.
- **spina_app.tabs.collectors._collectors_move_area** (function, lines 425–440, 16 lines, risk `ui_only`): Handles collectors move area for the collectors feature.

## `spina_app/tabs/dashboard.py`

- **spina_app.tabs.dashboard.configure_legacy_dashboard_feature** (function, lines 37–50, 14 lines, risk `support`): Attach main-module services without importing the large entry module.
- **spina_app.tabs.dashboard._spina_dashboard_fetch_rows** (function, lines 53–56, 4 lines, risk `support`): Handles spina dashboard fetch rows for the dashboard feature.
- **spina_app.tabs.dashboard._log_exc** (function, lines 59–62, 4 lines, risk `support`): Handles log exc for the dashboard feature.
- **spina_app.tabs.dashboard._spina_v18_draw_dashboard_charts** (function, lines 64–67, 4 lines, risk `support`): Handles spina v18 draw dashboard charts for the dashboard feature.
- **spina_app.tabs.dashboard._spina_v20_draw_dashboard_charts** (function, lines 70–73, 4 lines, risk `support`): Handles spina v20 draw dashboard charts for the dashboard feature.
- **spina_app.tabs.dashboard._spina_v17_visible_dashboard_rows** (function, lines 78–103, 26 lines, risk `ui_only`): Handles spina v17 visible dashboard rows for the dashboard feature.
- **spina_app.tabs.dashboard._spina_v17_build_dashboard_tab** (function, lines 106–352, 247 lines, risk `ui_only`): Handles spina v17 build dashboard tab for the dashboard feature.
- **spina_app.tabs.dashboard._spina_v17_draw_dashboard_charts** (function, lines 355–441, 87 lines, risk `filesystem`): Handles spina v17 draw dashboard charts for the dashboard feature.
- **spina_app.tabs.dashboard._spina_v17_populate_dashboard_tree** (function, lines 444–526, 83 lines, risk `ui_only`): Handles spina v17 populate dashboard tree for the dashboard feature.
- **spina_app.tabs.dashboard._spina_v17_refresh_dashboard** (function, lines 529–547, 19 lines, risk `support`): Handles spina v17 refresh dashboard for the dashboard feature.
- **spina_app.tabs.dashboard._spina_dashboard_visible_rows** (function, lines 551–568, 18 lines, risk `ui_only`): Handles spina dashboard visible rows for the dashboard feature.
- **spina_app.tabs.dashboard._spina_v19_visible_dashboard_rows** (function, lines 571–600, 30 lines, risk `ui_only`): Dashboard should show all active clients by default, not only priority clients.
- **spina_app.tabs.dashboard._spina_v20_visible_rows** (function, lines 603–611, 9 lines, risk `support`): Handles spina v20 visible rows for the dashboard feature.
- **spina_app.tabs.dashboard._spina_dashboard_summary_text** (function, lines 615–639, 25 lines, risk `support`): Handles spina dashboard summary text for the dashboard feature.
- **spina_app.tabs.dashboard._spina_configure_dashboard_tree_theme** (function, lines 641–703, 63 lines, risk `ui_only`): Keep Dashboard Treeview text readable in both Light and Dark mode. The Dashboard uses colored status tags. In Dark Mode, the app-level Treeview foreground is light; if the tag background is also light pastel, the text becomes hard to read. This function sets both background AND foreground for every 
- **spina_app.tabs.dashboard._spina_build_dashboard_tab** (function, lines 705–810, 106 lines, risk `ui_only`): Handles spina build dashboard tab for the dashboard feature.
- **spina_app.tabs.dashboard._spina_populate_dashboard_tree** (function, lines 812–864, 53 lines, risk `support`): Handles spina populate dashboard tree for the dashboard feature.
- **spina_app.tabs.dashboard._spina_refresh_dashboard** (function, lines 866–884, 19 lines, risk `support`): Handles spina refresh dashboard for the dashboard feature.
- **spina_app.tabs.dashboard._spina_apply_dashboard_role** (function, lines 886–910, 25 lines, risk `support`): Handles spina apply dashboard role for the dashboard feature.
- **spina_app.tabs.dashboard._spina_v18_patch_dashboard_chart_cards** (function, lines 912–932, 21 lines, risk `ui_only`): Make chart cards consistent: light outer panel, dark readable chart area.
- **spina_app.tabs.dashboard._spina_v18_populate_dashboard_tree** (function, lines 934–951, 18 lines, risk `ui_only`): Handles spina v18 populate dashboard tree for the dashboard feature.
- **spina_app.tabs.dashboard._spina_v18_refresh_dashboard** (function, lines 953–971, 19 lines, risk `support`): Handles spina v18 refresh dashboard for the dashboard feature.
- **spina_app.tabs.dashboard._spina_v19_populate_dashboard_tree** (function, lines 973–991, 19 lines, risk `ui_only`): Handles spina v19 populate dashboard tree for the dashboard feature.
- **spina_app.tabs.dashboard._spina_v19_refresh_dashboard** (function, lines 993–1019, 27 lines, risk `support`): Handles spina v19 refresh dashboard for the dashboard feature.
- **spina_app.tabs.dashboard._spina_v20_populate_dashboard_tree** (function, lines 1021–1055, 35 lines, risk `ui_only`): Handles spina v20 populate dashboard tree for the dashboard feature.
- **spina_app.tabs.dashboard._spina_v20_refresh_dashboard** (function, lines 1057–1075, 19 lines, risk `support`): Handles spina v20 refresh dashboard for the dashboard feature.

## `spina_app/tabs/data_bank_shell.py`

- **spina_app.tabs.data_bank_shell._noop_log** (function, lines 6–7, 2 lines, risk `support`): Handles noop log for the data bank feature.
- **spina_app.tabs.data_bank_shell.configure_data_bank_shell_dependencies** (function, lines 14–18, 5 lines, risk `support`): Bind application-owned logging helpers used by Data Bank presentation code.
- **spina_app.tabs.data_bank_shell._looks_like_data_grid** (function, lines 21–55, 35 lines, risk `ui_only`): Heuristic: columns contain 'client' + 'area' and many day columns (d1..d31 or numeric headings).
- **spina_app.tabs.data_bank_shell._locate_data_tree** (function, lines 58–83, 26 lines, risk `ui_only`): Find and memoize the actual Treeview used by the Data grid.
- **spina_app.tabs.data_bank_shell._ensure_databank_edit_bindings** (function, lines 86–116, 31 lines, risk `ui_only`): Bind double-click/F2 editing for Data grid (auto-detected) only once per Treeview instance.
- **spina_app.tabs.data_bank_shell._show_audit_tab** (function, lines 119–127, 9 lines, risk `support`): Handles show audit tab for the data bank feature.
- **spina_app.tabs.data_bank_shell._hide_audit_tab** (function, lines 130–135, 6 lines, risk `support`): Handles hide audit tab for the data bank feature.
- **spina_app.tabs.data_bank_shell._resize_databank_columns** (function, lines 138–227, 90 lines, risk `ui_only`): Resize Data Bank columns responsively. Supports 'freeze panes' layout: - name_tree shows Client + Area (fixed, no horizontal scroll) - days_tree shows day columns with horizontal scroll

## `spina_app/tabs/reports.py`

- **spina_app.tabs.reports.configure_reports_dependencies** (function, lines 26–35, 10 lines, risk `reports`): Bind application-owned callbacks used by the Reports presentation module.
- **spina_app.tabs.reports._spina_v22_style_reports_tree** (function, lines 38–60, 23 lines, risk `reports`): Handles spina v22 style reports tree for the reports feature.
- **spina_app.tabs.reports._spina_v22_button** (function, lines 62–91, 30 lines, risk `reports`): Handles spina v22 button for the reports feature.
- **spina_app.tabs.reports._spina_v22_report_card** (function, lines 93–103, 11 lines, risk `reports`): Handles spina v22 report card for the reports feature.
- **spina_app.tabs.reports._spina_v22_build_reports_tab** (function, lines 105–475, 371 lines, risk `filesystem`): Handles spina v22 build reports tab for the reports feature.
- **spina_app.tabs.reports._spina_v22_reports_selection_status** (function, lines 477–486, 10 lines, risk `reports`): Handles spina v22 reports selection status for the reports feature.
- **spina_app.tabs.reports._spina_v22_update_report_cards** (function, lines 488–542, 55 lines, risk `reports`): Handles spina v22 update report cards for the reports feature.

## `spina_app/theme_palettes.py`

- **spina_app.theme_palettes._spina_v20_dash_palette** (function, lines 4–41, 38 lines, risk `support`): Handles spina v20 dash palette for the settings feature.
- **spina_app.theme_palettes._spina_v21_cash_colors** (function, lines 44–95, 52 lines, risk `support`): Handles spina v21 cash colors for the settings feature.
- **spina_app.theme_palettes._spina_v24_cilog_colors** (function, lines 98–145, 48 lines, risk `support`): Handles spina v24 cilog colors for the clients feature.
- **spina_app.theme_palettes._spina_v22_reports_colors** (function, lines 148–187, 40 lines, risk `reports`): Handles spina v22 reports colors for the reports feature.
- **spina_app.theme_palettes._spina_v25_collector_colors** (function, lines 190–231, 42 lines, risk `support`): Handles spina v25 collector colors for the collectors feature.
- **spina_app.theme_palettes._spina_v17_dash_colors** (function, lines 234–276, 43 lines, risk `support`): Dashboard-specific modern colors that work in light and dark mode.
- **spina_app.theme_palettes._spina_v18_dashboard_palette** (function, lines 279–326, 48 lines, risk `support`): Handles spina v18 dashboard palette for the dashboard feature.
- **spina_app.theme_palettes._spina_v32_login_colors** (function, lines 330–369, 40 lines, risk `authentication`): Handles spina v32 login colors for the authentication feature.

## `spina_app/theme_presentation.py`

- **spina_app.theme_presentation.configure_theme_presentation_dependencies** (function, lines 13–18, 6 lines, risk `support`): Handles configure theme presentation dependencies for the settings feature.
- **spina_app.theme_presentation._theme_toggle_text** (function, lines 31–36, 6 lines, risk `support`): Handles theme toggle text for the settings feature.
- **spina_app.theme_presentation._theme_palette** (function, lines 38–83, 46 lines, risk `support`): Handles theme palette for the settings feature.
- **spina_app.theme_presentation._apply_ui_theme** (function, lines 85–239, 155 lines, risk `ui_only`): Handles apply ui theme for the settings feature.
- **spina_app.theme_presentation._apply_tk_theme_recursive** (function, lines 241–279, 39 lines, risk `ui_only`): Handles apply tk theme recursive for the settings feature.
- **spina_app.theme_presentation._refresh_modern_shell_theme** (function, lines 281–301, 21 lines, risk `ui_only`): Apply theme colors to the modern sidebar shell and rebuild nav labels/buttons.
- **spina_app.theme_presentation._refresh_header_theme** (function, lines 303–348, 46 lines, risk `ui_only`): Apply the current theme colors to the modern top header.

## `spina_app/ui_cards.py`

- **spina_app.ui_cards._spina_v21_cash_card** (function, lines 15–25, 11 lines, risk `ui_only`): Handles spina v21 cash card for the other feature.
- **spina_app.ui_cards._spina_v24_cilog_card** (function, lines 28–38, 11 lines, risk `ui_only`): Handles spina v24 cilog card for the clients feature.
- **spina_app.ui_cards._spina_v27_route_card** (function, lines 41–51, 11 lines, risk `ui_only`): Handles spina v27 route card for the collectors feature.
- **spina_app.ui_cards._spina_v17_make_card** (function, lines 54–68, 15 lines, risk `ui_only`): Handles spina v17 make card for the other feature.

## `spina_app/ui_controls.py`

- **spina_app.ui_controls._spina_v21_build_labeled_entry** (function, lines 18–24, 7 lines, risk `ui_only`): Handles spina v21 build labeled entry for the other feature.
- **spina_app.ui_controls._spina_v21_style_cash_table** (function, lines 27–49, 23 lines, risk `ui_only`): Handles spina v21 style cash table for the other feature.
- **spina_app.ui_controls._spina_v24_cilog_button** (function, lines 52–80, 29 lines, risk `ui_only`): Handles spina v24 cilog button for the clients feature.
- **spina_app.ui_controls._spina_v24_cilog_style_tree** (function, lines 83–105, 23 lines, risk `ui_only`): Handles spina v24 cilog style tree for the clients feature.
- **spina_app.ui_controls._spina_v23_style_clients_tree** (function, lines 108–130, 23 lines, risk `ui_only`): Handles spina v23 style clients tree for the clients feature.
- **spina_app.ui_controls._spina_v27_style_route_trees** (function, lines 133–155, 23 lines, risk `ui_only`): Handles spina v27 style route trees for the collectors feature.
- **spina_app.ui_controls._spina_v17_update_filter_buttons** (function, lines 158–168, 11 lines, risk `ui_only`): Handles spina v17 update filter buttons for the other feature.
- **spina_app.ui_controls._spina_v17_style_dashboard_table** (function, lines 171–194, 24 lines, risk `ui_only`): Handles spina v17 style dashboard table for the dashboard feature.
- **spina_app.ui_controls._spina_v27_route_button** (function, lines 197–226, 30 lines, risk `ui_only`): Handles spina v27 route button for the collectors feature.
- **spina_app.ui_controls._spina_v32_login_button** (function, lines 228–255, 28 lines, risk `authentication`): Handles spina v32 login button for the authentication feature.

## `spina_app/ui_helpers.py`

- **spina_app.ui_helpers._spina_v20_round_rect** (function, lines 6–15, 10 lines, risk `support`): Handles spina v20 round rect for the utilities feature.
- **spina_app.ui_helpers._spina_v24_cilog_round_rect** (function, lines 18–27, 10 lines, risk `support`): Handles spina v24 cilog round rect for the clients feature.
- **spina_app.ui_helpers._spina_v18_draw_round_rect** (function, lines 30–40, 11 lines, risk `support`): Canvas rounded rectangle fallback using polygon smoothing.
- **spina_app.ui_helpers._spina_v17_set_card** (function, lines 43–51, 9 lines, risk `ui_only`): Handles spina v17 set card for the utilities feature.
- **spina_app.ui_helpers._spina_v24_cilog_set_card** (function, lines 54–62, 9 lines, risk `ui_only`): Handles spina v24 cilog set card for the clients feature.
- **spina_app.ui_helpers._spina_v21_cash_set_card** (function, lines 65–73, 9 lines, risk `ui_only`): Handles spina v21 cash set card for the utilities feature.

## `spina_app/utilities/dashboard.py`

- **spina_app.utilities.dashboard._spina_dash__status_for** (function, lines 6–32, 27 lines, risk `support`): Handles spina dash status for for the dashboard feature.

## `spina_app/utilities/dates.py`

- **spina_app.utilities.dates._spina_cashctl__valid_date** (function, lines 7–13, 7 lines, risk `support`): Handles spina cashctl valid date for the cash control feature.
- **spina_app.utilities.dates._spina__parse_day_ymd** (function, lines 15–22, 8 lines, risk `support`): Handles spina parse day ymd for the utilities feature.
- **spina_app.utilities.dates._spina_dash__parse_date** (function, lines 24–31, 8 lines, risk `support`): Handles spina dash parse date for the utilities feature.
- **spina_app.utilities.dates._spina_dash__date_text** (function, lines 33–38, 6 lines, risk `support`): Handles spina dash date text for the utilities feature.
- **spina_app.utilities.dates._spina_v24_cilog_parse_day** (function, lines 40–48, 9 lines, risk `support`): Handles spina v24 cilog parse day for the clients feature.
- **spina_app.utilities.dates._spina__norm_weekday** (function, lines 51–63, 13 lines, risk `support`): Handles spina norm weekday for the utilities feature.
- **spina_app.utilities.dates._spina__norm_dom** (function, lines 66–73, 8 lines, risk `support`): Handles spina norm dom for the utilities feature.

## `spina_app/utilities/diffs.py`

- **spina_app.utilities.diffs._spina_cilog_diff_pairs** (function, lines 5–24, 20 lines, risk `support`): Handles spina cilog diff pairs for the clients feature.

## `spina_app/utilities/formatting.py`

- **spina_app.utilities.formatting.fmt_currency** (function, lines 5–9, 5 lines, risk `support`): Handles fmt currency for the utilities feature.
- **spina_app.utilities.formatting._spina_dash__fmt_pct** (function, lines 11–15, 5 lines, risk `support`): Handles spina dash fmt pct for the utilities feature.
- **spina_app.utilities.formatting._spina_v23_money** (function, lines 16–21, 6 lines, risk `support`): Handles spina v23 money for the utilities feature.
- **spina_app.utilities.formatting._spina_v23_percent** (function, lines 22–27, 6 lines, risk `support`): Handles spina v23 percent for the utilities feature.
- **spina_app.utilities.formatting._spina_cilog_fmt_money** (function, lines 29–38, 10 lines, risk `support`): Handles spina cilog fmt money for the clients feature.
- **spina_app.utilities.formatting._spina_cilog_fmt_value** (function, lines 40–55, 16 lines, risk `filesystem`): Handles spina cilog fmt value for the clients feature.
- **spina_app.utilities.formatting._spina__fmt_client_money** (function, lines 58–65, 8 lines, risk `support`): Handles spina fmt client money for the clients feature.
- **spina_app.utilities.formatting._spina_v17_fmt_short_money** (function, lines 68–78, 11 lines, risk `support`): Handles spina v17 fmt short money for the utilities feature.
- **spina_app.utilities.formatting._spina_v18_fmt_money_compact** (function, lines 81–93, 13 lines, risk `support`): Handles spina v18 fmt money compact for the utilities feature.
- **spina_app.utilities.formatting._spina_crc_fmt_money** (function, lines 96–108, 13 lines, risk `support`): Handles spina crc fmt money for the utilities feature.
- **spina_app.utilities.formatting._spina_dash__fmt_money** (function, lines 111–120, 10 lines, risk `support`): Handles spina dash fmt money for the utilities feature.
- **spina_app.utilities.formatting._spina_cashctl__fmt_pct** (function, lines 123–130, 8 lines, risk `support`): Handles spina cashctl fmt pct for the cash control feature.

## `spina_app/utilities/notes.py`

- **spina_app.utilities.notes._as_note_dict** (function, lines 5–12, 8 lines, risk `support`): Normalize a note entry to a dict with '__default__' and YYYY-MM-DD keys.
- **spina_app.utilities.notes._append_unique_text** (function, lines 15–25, 11 lines, risk `support`): Handles append unique text for the notes feature.
- **spina_app.utilities.notes._merge_note_dict** (function, lines 28–40, 13 lines, risk `support`): Merge src into dst without losing data; if conflicts, append text uniquely.

## `spina_app/utilities/numbers.py`

- **spina_app.utilities.numbers._spina_dash__float** (function, lines 7–13, 7 lines, risk `filesystem`): Handles spina dash float for the utilities feature.
- **spina_app.utilities.numbers._spina_v27_count_from_text** (function, lines 15–20, 6 lines, risk `support`): Handles spina v27 count from text for the utilities feature.
- **spina_app.utilities.numbers._spina_v25_parse_count_from_var** (function, lines 23–29, 7 lines, risk `support`): Handles spina v25 parse count from var for the utilities feature.
- **spina_app.utilities.numbers._spina_cashctl__parse_amount** (function, lines 32–37, 6 lines, risk `filesystem`): Handles spina cashctl parse amount for the cash control feature.
- **spina_app.utilities.numbers._spina_cashctl__int_range** (function, lines 40–49, 10 lines, risk `support`): Handles spina cashctl int range for the cash control feature.

## `spina_app/utilities/records.py`

- **spina_app.utilities.records._spina_perf_dict_rows** (function, lines 6–16, 11 lines, risk `support`): Handles spina perf dict rows for the utilities feature.

## `spina_app/utilities/serialization.py`

- **spina_app.utilities.serialization._spina_cilog_safe_json** (function, lines 7–15, 9 lines, risk `support`): Handles spina cilog safe json for the clients feature.

## `spina_app/utilities/text.py`

- **spina_app.utilities.text._oslp__norm_area_name** (function, lines 7–8, 2 lines, risk `support`): Handles oslp norm area name for the utilities feature.
- **spina_app.utilities.text._spina_crc_norm_text** (function, lines 10–14, 5 lines, risk `support`): Handles spina crc norm text for the utilities feature.
- **spina_app.utilities.text._spina_route_notice_norm_name** (function, lines 16–23, 8 lines, risk `support`): Handles spina route notice norm name for the collectors feature.
- **spina_app.utilities.text._spina_cilog_action_label** (function, lines 25–36, 12 lines, risk `support`): Handles spina cilog action label for the clients feature.

## `tools/add_optional_performance_logs.py`

- **tools.add_optional_performance_logs.remove_existing_block** (function, lines 117–125, 9 lines, risk `support`): Removes remove existing block for the other feature.
- **tools.add_optional_performance_logs.main** (function, lines 128–151, 24 lines, risk `filesystem`): Handles main for the other feature.

## `tools/apply_client_area_uid_sync_phase2.py`

- **tools.apply_client_area_uid_sync_phase2._state** (function, lines 19–28, 10 lines, risk `support`): Handles state for the other feature.
- **tools.apply_client_area_uid_sync_phase2.inspect** (function, lines 31–41, 11 lines, risk `filesystem`): Handles inspect for the other feature.
- **tools.apply_client_area_uid_sync_phase2.apply** (function, lines 44–57, 14 lines, risk `filesystem`): Handles apply for the other feature.
- **tools.apply_client_area_uid_sync_phase2.main** (function, lines 60–71, 12 lines, risk `reports`): Handles main for the other feature.

## `tools/apply_hierarchical_area_storage_phase1.py`

- **tools.apply_hierarchical_area_storage_phase1.inspect** (function, lines 45–59, 15 lines, risk `filesystem`): Handles inspect for the other feature.
- **tools.apply_hierarchical_area_storage_phase1.apply** (function, lines 62–72, 11 lines, risk `filesystem`): Handles apply for the other feature.
- **tools.apply_hierarchical_area_storage_phase1.main** (function, lines 75–81, 7 lines, risk `reports`): Handles main for the other feature.

## `tools/apply_hierarchical_area_ui_phase2.py`

- **tools.apply_hierarchical_area_ui_phase2._between** (function, lines 23–30, 8 lines, risk `support`): Handles between for the other feature.
- **tools.apply_hierarchical_area_ui_phase2.inspect** (function, lines 33–67, 35 lines, risk `support`): Handles inspect for the other feature.
- **tools.apply_hierarchical_area_ui_phase2.apply** (function, lines 70–85, 16 lines, risk `filesystem`): Handles apply for the other feature.
- **tools.apply_hierarchical_area_ui_phase2.main** (function, lines 88–101, 14 lines, risk `filesystem`): Handles main for the other feature.

## `tools/audit_bare_except_context.py`

- **tools.audit_bare_except_context._lines** (function, lines 23–24, 2 lines, risk `filesystem`): Handles lines for the other feature.
- **tools.audit_bare_except_context._ctx** (function, lines 27–30, 4 lines, risk `support`): Handles ctx for the other feature.
- **tools.audit_bare_except_context._count_by** (function, lines 33–38, 6 lines, risk `support`): Handles count by for the other feature.
- **tools.audit_bare_except_context.Visitor** (class, lines 41–87, 47 lines, risk `container`): Groups Visitor for the other feature.
- **tools.audit_bare_except_context.Visitor.__init__** (method, lines 42–46, 5 lines, risk `support`): Handles init for the other feature.
- **tools.audit_bare_except_context.Visitor.visit_ClassDef** (method, lines 48–51, 4 lines, risk `support`): Handles visit ClassDef for the other feature.
- **tools.audit_bare_except_context.Visitor.visit_FunctionDef** (method, lines 53–56, 4 lines, risk `support`): Handles visit FunctionDef for the other feature.
- **tools.audit_bare_except_context.Visitor.visit_AsyncFunctionDef** (method, lines 58–59, 2 lines, risk `support`): Handles visit AsyncFunctionDef for the other feature.
- **tools.audit_bare_except_context.Visitor.visit_ExceptHandler** (method, lines 61–87, 27 lines, risk `support`): Handles visit ExceptHandler for the other feature.
- **tools.audit_bare_except_context.build_report** (function, lines 90–111, 22 lines, risk `reports`): Builds build report for the reports feature.
- **tools.audit_bare_except_context.main** (function, lines 114–126, 13 lines, risk `filesystem`): Handles main for the other feature.

## `tools/audit_blocking_ui_calls.py`

- **tools.audit_blocking_ui_calls._call_name** (function, lines 55–63, 9 lines, risk `support`): Handles call name for the other feature.
- **tools.audit_blocking_ui_calls._nearest_scope** (function, lines 66–70, 5 lines, risk `support`): Handles nearest scope for the other feature.
- **tools.audit_blocking_ui_calls._scope_name** (function, lines 73–80, 8 lines, risk `support`): Handles scope name for the other feature.
- **tools.audit_blocking_ui_calls._has_hint** (function, lines 83–85, 3 lines, risk `support`): Handles has hint for the other feature.
- **tools.audit_blocking_ui_calls.BlockingCallVisitor** (class, lines 88–135, 48 lines, risk `container`): Groups BlockingCallVisitor for the other feature.
- **tools.audit_blocking_ui_calls.BlockingCallVisitor.__init__** (method, lines 89–92, 4 lines, risk `support`): Handles init for the other feature.
- **tools.audit_blocking_ui_calls.BlockingCallVisitor.visit_ClassDef** (method, lines 94–97, 4 lines, risk `support`): Handles visit ClassDef for the other feature.
- **tools.audit_blocking_ui_calls.BlockingCallVisitor.visit_FunctionDef** (method, lines 99–102, 4 lines, risk `support`): Handles visit FunctionDef for the other feature.
- **tools.audit_blocking_ui_calls.BlockingCallVisitor.visit_AsyncFunctionDef** (method, lines 104–107, 4 lines, risk `support`): Handles visit AsyncFunctionDef for the other feature.
- **tools.audit_blocking_ui_calls.BlockingCallVisitor.visit_Call** (method, lines 109–135, 27 lines, risk `support`): Handles visit Call for the other feature.
- **tools.audit_blocking_ui_calls.build_report** (function, lines 138–159, 22 lines, risk `filesystem`): Builds build report for the reports feature.
- **tools.audit_blocking_ui_calls.main** (function, lines 162–175, 14 lines, risk `filesystem`): Handles main for the other feature.

## `tools/audit_dynamic_sql_context.py`

- **tools.audit_dynamic_sql_context.node_kind** (function, lines 31–48, 18 lines, risk `support`): Handles node kind for the other feature.
- **tools.audit_dynamic_sql_context.safe_unparse** (function, lines 51–57, 7 lines, risk `support`): Handles safe unparse for the utilities feature.
- **tools.audit_dynamic_sql_context.is_plain_sql_literal** (function, lines 60–61, 2 lines, risk `support`): Handles is plain sql literal for the database feature.
- **tools.audit_dynamic_sql_context.call_name** (function, lines 64–69, 6 lines, risk `support`): Handles call name for the other feature.
- **tools.audit_dynamic_sql_context.enclosing_stack** (function, lines 72–109, 38 lines, risk `support`): Handles enclosing stack for the other feature.
- **tools.audit_dynamic_sql_context.qualname** (function, lines 112–114, 3 lines, risk `support`): Handles qualname for the other feature.
- **tools.audit_dynamic_sql_context.context** (function, lines 117–125, 9 lines, risk `support`): Handles context for the other feature.
- **tools.audit_dynamic_sql_context.has_protected_context** (function, lines 128–134, 7 lines, risk `support`): Handles has protected context for the other feature.
- **tools.audit_dynamic_sql_context.classify_risk** (function, lines 137–145, 9 lines, risk `support`): Handles classify risk for the other feature.
- **tools.audit_dynamic_sql_context.audit** (function, lines 148–208, 61 lines, risk `filesystem`): Handles audit for the other feature.
- **tools.audit_dynamic_sql_context.main** (function, lines 211–230, 20 lines, risk `filesystem`): Handles main for the other feature.

## `tools/audit_legacy_callback_usage.py`

- **tools.audit_legacy_callback_usage.line_context** (function, lines 47–50, 4 lines, risk `support`): Handles line context for the other feature.
- **tools.audit_legacy_callback_usage.has_protected_keyword** (function, lines 53–55, 3 lines, risk `support`): Handles has protected keyword for the other feature.
- **tools.audit_legacy_callback_usage.function_ranges** (function, lines 58–70, 13 lines, risk `support`): Return {(class_name, function_name): (start_line, end_line)}.
- **tools.audit_legacy_callback_usage.collect_definitions** (function, lines 73–87, 15 lines, risk `support`): Handles collect definitions for the other feature.
- **tools.audit_legacy_callback_usage.line_inside_any_definition** (function, lines 90–94, 5 lines, risk `support`): Handles line inside any definition for the other feature.
- **tools.audit_legacy_callback_usage.collect_references** (function, lines 97–132, 36 lines, risk `support`): Handles collect references for the other feature.
- **tools.audit_legacy_callback_usage.build_recommendations** (function, lines 135–161, 27 lines, risk `support`): Builds build recommendations for the other feature.
- **tools.audit_legacy_callback_usage.audit** (function, lines 164–177, 14 lines, risk `filesystem`): Handles audit for the other feature.
- **tools.audit_legacy_callback_usage.print_summary** (function, lines 180–213, 34 lines, risk `reports`): Generates print summary for the reports feature.
- **tools.audit_legacy_callback_usage.main** (function, lines 216–231, 16 lines, risk `filesystem`): Handles main for the other feature.

## `tools/audit_pass_only_exceptions.py`

- **tools.audit_pass_only_exceptions._segment** (function, lines 23–24, 2 lines, risk `support`): Handles segment for the other feature.
- **tools.audit_pass_only_exceptions._scope_name** (function, lines 27–34, 8 lines, risk `support`): Handles scope name for the other feature.
- **tools.audit_pass_only_exceptions._handler_name** (function, lines 37–43, 7 lines, risk `support`): Handles handler name for the other feature.
- **tools.audit_pass_only_exceptions._is_pass_only** (function, lines 46–47, 2 lines, risk `support`): Handles is pass only for the payments feature.
- **tools.audit_pass_only_exceptions._protected** (function, lines 50–52, 3 lines, risk `support`): Handles protected for the other feature.
- **tools.audit_pass_only_exceptions.audit** (function, lines 55–125, 71 lines, risk `filesystem`): Handles audit for the other feature.
- **tools.audit_pass_only_exceptions.audit.walk** (nested_function, lines 65–99, 35 lines, risk `support`): Handles walk for the other feature.
- **tools.audit_pass_only_exceptions.main** (function, lines 128–142, 15 lines, risk `filesystem`): Handles main for the other feature.

## `tools/audit_patch_chains.py`

- **tools.audit_patch_chains._lower** (function, lines 62–63, 2 lines, risk `support`): Handles lower for the other feature.
- **tools.audit_patch_chains._context** (function, lines 66–69, 4 lines, risk `support`): Handles context for the other feature.
- **tools.audit_patch_chains._has_protected** (function, lines 72–74, 3 lines, risk `support`): Handles has protected for the other feature.
- **tools.audit_patch_chains._classify_rhs** (function, lines 77–89, 13 lines, risk `support`): Handles classify rhs for the other feature.
- **tools.audit_patch_chains._def_lines** (function, lines 92–98, 7 lines, risk `support`): Handles def lines for the other feature.
- **tools.audit_patch_chains._find_patch_assignments** (function, lines 101–127, 27 lines, risk `support`): Retrieves find patch assignments for the other feature.
- **tools.audit_patch_chains.run** (function, lines 130–173, 44 lines, risk `filesystem`): Handles run for the other feature.
- **tools.audit_patch_chains.print_report** (function, lines 176–185, 10 lines, risk `reports`): Generates print report for the reports feature.
- **tools.audit_patch_chains.main** (function, lines 188–198, 11 lines, risk `reports`): Handles main for the other feature.

## `tools/audit_pg_backup_action_flow.py`

- **tools.audit_pg_backup_action_flow.read_lines** (function, lines 34–35, 2 lines, risk `filesystem`): Handles read lines for the other feature.
- **tools.audit_pg_backup_action_flow.qualname** (function, lines 38–47, 10 lines, risk `support`): Handles qualname for the other feature.
- **tools.audit_pg_backup_action_flow.func_name_from_call** (function, lines 50–56, 7 lines, risk `support`): Handles func name from call for the other feature.
- **tools.audit_pg_backup_action_flow.call_text** (function, lines 59–64, 6 lines, risk `support`): Handles call text for the other feature.
- **tools.audit_pg_backup_action_flow.text_range** (function, lines 67–70, 4 lines, risk `support`): Handles text range for the other feature.
- **tools.audit_pg_backup_action_flow.has_call** (function, lines 73–79, 7 lines, risk `support`): Handles has call for the other feature.
- **tools.audit_pg_backup_action_flow.context** (function, lines 82–85, 4 lines, risk `support`): Handles context for the other feature.
- **tools.audit_pg_backup_action_flow.protected_context** (function, lines 88–90, 3 lines, risk `support`): Handles protected context for the other feature.
- **tools.audit_pg_backup_action_flow.Visitor** (class, lines 93–169, 77 lines, risk `container`): Groups Visitor for the other feature.
- **tools.audit_pg_backup_action_flow.Visitor.__init__** (method, lines 94–98, 5 lines, risk `support`): Handles init for the other feature.
- **tools.audit_pg_backup_action_flow.Visitor.visit_ClassDef** (method, lines 100–103, 4 lines, risk `support`): Handles visit ClassDef for the other feature.
- **tools.audit_pg_backup_action_flow.Visitor.visit_FunctionDef** (method, lines 105–106, 2 lines, risk `support`): Handles visit FunctionDef for the other feature.
- **tools.audit_pg_backup_action_flow.Visitor.visit_AsyncFunctionDef** (method, lines 108–109, 2 lines, risk `support`): Handles visit AsyncFunctionDef for the other feature.
- **tools.audit_pg_backup_action_flow.Visitor._visit_function** (method, lines 111–129, 19 lines, risk `support`): Handles visit function for the other feature.
- **tools.audit_pg_backup_action_flow.Visitor.visit_Call** (method, lines 131–161, 31 lines, risk `support`): Handles visit Call for the other feature.
- **tools.audit_pg_backup_action_flow.Visitor._is_inside_run_long_task_argument** (method, lines 163–169, 7 lines, risk `support`): Handles is inside run long task argument for the other feature.
- **tools.audit_pg_backup_action_flow.build_report** (function, lines 172–207, 36 lines, risk `reports`): Builds build report for the reports feature.
- **tools.audit_pg_backup_action_flow.main** (function, lines 210–222, 13 lines, risk `filesystem`): Handles main for the other feature.

## `tools/audit_pg_command_callers.py`

- **tools.audit_pg_command_callers._call_name** (function, lines 44–54, 11 lines, risk `support`): Handles call name for the other feature.
- **tools.audit_pg_command_callers._short_call_name** (function, lines 57–58, 2 lines, risk `support`): Handles short call name for the other feature.
- **tools.audit_pg_command_callers._contains_name** (function, lines 61–68, 8 lines, risk `support`): Handles contains name for the other feature.
- **tools.audit_pg_command_callers._context** (function, lines 71–77, 7 lines, risk `support`): Handles context for the other feature.
- **tools.audit_pg_command_callers._protected_context** (function, lines 80–82, 3 lines, risk `support`): Handles protected context for the other feature.
- **tools.audit_pg_command_callers._function_record** (function, lines 85–95, 11 lines, risk `support`): Handles function record for the other feature.
- **tools.audit_pg_command_callers.audit** (function, lines 98–179, 82 lines, risk `filesystem`): Handles audit for the other feature.
- **tools.audit_pg_command_callers.main** (function, lines 182–194, 13 lines, risk `filesystem`): Handles main for the other feature.

## `tools/audit_shadowed_definitions.py`

- **tools.audit_shadowed_definitions._indent_width** (function, lines 52–53, 2 lines, risk `support`): Handles indent width for the other feature.
- **tools.audit_shadowed_definitions._context** (function, lines 56–59, 4 lines, risk `support`): Handles context for the other feature.
- **tools.audit_shadowed_definitions._has_protected_context** (function, lines 62–64, 3 lines, risk `support`): Handles has protected context for the other feature.
- **tools.audit_shadowed_definitions._entry** (function, lines 67–72, 6 lines, risk `support`): Handles entry for the other feature.
- **tools.audit_shadowed_definitions.collect** (function, lines 75–143, 69 lines, risk `support`): Handles collect for the other feature.
- **tools.audit_shadowed_definitions.run** (function, lines 146–153, 8 lines, risk `filesystem`): Handles run for the other feature.
- **tools.audit_shadowed_definitions.print_report** (function, lines 156–164, 9 lines, risk `reports`): Generates print report for the reports feature.
- **tools.audit_shadowed_definitions.main** (function, lines 167–177, 11 lines, risk `reports`): Handles main for the other feature.

## `tools/audit_silent_ui_errors.py`

- **tools.audit_silent_ui_errors._indent_width** (function, lines 71–72, 2 lines, risk `support`): Handles indent width for the other feature.
- **tools.audit_silent_ui_errors._line_context** (function, lines 75–78, 4 lines, risk `support`): Handles line context for the other feature.
- **tools.audit_silent_ui_errors._has_any** (function, lines 81–83, 3 lines, risk `support`): Handles has any for the other feature.
- **tools.audit_silent_ui_errors._body_range** (function, lines 86–100, 15 lines, risk `support`): Return 0-based [start, end) body range for an except block.
- **tools.audit_silent_ui_errors._body_is_silent** (function, lines 103–119, 17 lines, risk `support`): Handles body is silent for the other feature.
- **tools.audit_silent_ui_errors._scan_def_context** (function, lines 122–148, 27 lines, risk `support`): Build a simple per-line function/class context map.
- **tools.audit_silent_ui_errors.audit** (function, lines 151–206, 56 lines, risk `filesystem`): Handles audit for the other feature.
- **tools.audit_silent_ui_errors.print_summary** (function, lines 209–232, 24 lines, risk `reports`): Generates print summary for the reports feature.
- **tools.audit_silent_ui_errors.main** (function, lines 235–250, 16 lines, risk `filesystem`): Handles main for the other feature.

## `tools/cleanup_databank_export_callbacks.py`

- **tools.cleanup_databank_export_callbacks._line_indent** (function, lines 45–46, 2 lines, risk `support`): Handles line indent for the other feature.
- **tools.cleanup_databank_export_callbacks._is_decorator** (function, lines 49–50, 2 lines, risk `support`): Handles is decorator for the other feature.
- **tools.cleanup_databank_export_callbacks._find_function_ranges** (function, lines 53–90, 38 lines, risk `support`): Return 0-based inclusive/exclusive ranges for a function definition. Each result is (start_index, end_index, indent).
- **tools.cleanup_databank_export_callbacks._inside_any** (function, lines 93–94, 2 lines, risk `support`): Handles inside any for the other feature.
- **tools.cleanup_databank_export_callbacks._looks_like_string_reference** (function, lines 97–108, 12 lines, risk `support`): Handles looks like string reference for the other feature.
- **tools.cleanup_databank_export_callbacks._is_stale_cleanup_reference** (function, lines 111–119, 9 lines, risk `support`): Return True only for harmless generated cleanup/hide-block references.
- **tools.cleanup_databank_export_callbacks._external_references** (function, lines 122–141, 20 lines, risk `support`): Handles external references for the other feature.
- **tools.cleanup_databank_export_callbacks._remove_ranges** (function, lines 144–151, 8 lines, risk `support`): Removes remove ranges for the other feature.
- **tools.cleanup_databank_export_callbacks.main** (function, lines 154–215, 62 lines, risk `filesystem`): Handles main for the other feature.

## `tools/cleanup_databank_export_ui_source.py`

- **tools.cleanup_databank_export_ui_source.remove_old_blocks** (function, lines 74–87, 14 lines, risk `support`): Removes remove old blocks for the other feature.
- **tools.cleanup_databank_export_ui_source._has_any** (function, lines 90–92, 3 lines, risk `support`): Handles has any for the other feature.
- **tools.cleanup_databank_export_ui_source.is_confirmed_databank_export_ui_line** (function, lines 95–112, 18 lines, risk `support`): Handles is confirmed databank export ui line for the data bank feature.
- **tools.cleanup_databank_export_ui_source.cleanup_source_lines** (function, lines 115–126, 12 lines, risk `support`): Handles cleanup source lines for the other feature.
- **tools.cleanup_databank_export_ui_source.main** (function, lines 129–147, 19 lines, risk `filesystem`): Handles main for the other feature.

## `tools/cleanup_logger_fallback_pass_only.py`

- **tools.cleanup_logger_fallback_pass_only._line_text** (function, lines 33–36, 4 lines, risk `support`): Handles line text for the other feature.
- **tools.cleanup_logger_fallback_pass_only._find_top_level_function** (function, lines 39–54, 16 lines, risk `support`): Retrieves find top level function for the other feature.
- **tools.cleanup_logger_fallback_pass_only._locate_target** (function, lines 57–133, 77 lines, risk `support`): Handles locate target for the other feature.
- **tools.cleanup_logger_fallback_pass_only.build_report** (function, lines 136–181, 46 lines, risk `filesystem`): Builds build report for the reports feature.
- **tools.cleanup_logger_fallback_pass_only.main** (function, lines 184–195, 12 lines, risk `filesystem`): Handles main for the other feature.

## `tools/cleanup_modern_ui_pass_only.py`

- **tools.cleanup_modern_ui_pass_only.context** (function, lines 49–52, 4 lines, risk `support`): Handles context for the other feature.
- **tools.cleanup_modern_ui_pass_only.has_protected_context** (function, lines 55–57, 3 lines, risk `support`): Handles has protected context for the other feature.
- **tools.cleanup_modern_ui_pass_only.inspect_target** (function, lines 60–100, 41 lines, risk `support`): Handles inspect target for the other feature.
- **tools.cleanup_modern_ui_pass_only.replacement_for** (function, lines 103–115, 13 lines, risk `support`): Handles replacement for for the other feature.
- **tools.cleanup_modern_ui_pass_only.build_report** (function, lines 118–159, 42 lines, risk `filesystem`): Builds build report for the reports feature.
- **tools.cleanup_modern_ui_pass_only.main** (function, lines 162–175, 14 lines, risk `filesystem`): Handles main for the other feature.

## `tools/cleanup_neutral_appclass_init_patch.py`

- **tools.cleanup_neutral_appclass_init_patch._indent_width** (function, lines 45–46, 2 lines, risk `support`): Handles indent width for the other feature.
- **tools.cleanup_neutral_appclass_init_patch._find_neutral_block** (function, lines 49–127, 79 lines, risk `support`): Retrieves find neutral block for the other feature.
- **tools.cleanup_neutral_appclass_init_patch.run** (function, lines 130–161, 32 lines, risk `filesystem`): Handles run for the other feature.
- **tools.cleanup_neutral_appclass_init_patch.print_report** (function, lines 164–177, 14 lines, risk `reports`): Generates print report for the reports feature.
- **tools.cleanup_neutral_appclass_init_patch.main** (function, lines 180–188, 9 lines, risk `reports`): Handles main for the other feature.

## `tools/cleanup_pg_json_read_dynamic_sql.py`

- **tools.cleanup_pg_json_read_dynamic_sql._line_number** (function, lines 40–44, 5 lines, risk `support`): Handles line number for the other feature.
- **tools.cleanup_pg_json_read_dynamic_sql._slice_context** (function, lines 47–52, 6 lines, risk `support`): Handles slice context for the other feature.
- **tools.cleanup_pg_json_read_dynamic_sql._function_block** (function, lines 55–63, 9 lines, risk `support`): Handles function block for the other feature.
- **tools.cleanup_pg_json_read_dynamic_sql.build_plan** (function, lines 66–139, 74 lines, risk `filesystem`): Builds build plan for the other feature.
- **tools.cleanup_pg_json_read_dynamic_sql.main** (function, lines 142–158, 17 lines, risk `filesystem`): Handles main for the other feature.

## `tools/cleanup_pure_login_dialog_ui_pass_only.py`

- **tools.cleanup_pure_login_dialog_ui_pass_only.Target** (class, lines 22–28, 7 lines, risk `container`): Groups Target for the other feature.
- **tools.cleanup_pure_login_dialog_ui_pass_only.ParentSetter** (class, lines 92–96, 5 lines, risk `container`): Groups ParentSetter for the other feature.
- **tools.cleanup_pure_login_dialog_ui_pass_only.ParentSetter.visit** (method, lines 93–96, 4 lines, risk `support`): Handles visit for the other feature.
- **tools.cleanup_pure_login_dialog_ui_pass_only.node_name** (function, lines 99–102, 4 lines, risk `support`): Handles node name for the other feature.
- **tools.cleanup_pure_login_dialog_ui_pass_only.scope_for** (function, lines 105–114, 10 lines, risk `support`): Handles scope for for the other feature.
- **tools.cleanup_pure_login_dialog_ui_pass_only.is_exception_handler** (function, lines 117–124, 8 lines, risk `support`): Handles is exception handler for the other feature.
- **tools.cleanup_pure_login_dialog_ui_pass_only.is_pass_only_handler** (function, lines 127–132, 6 lines, risk `support`): Handles is pass only handler for the payments feature.
- **tools.cleanup_pure_login_dialog_ui_pass_only.get_context** (function, lines 135–138, 4 lines, risk `support`): Retrieves get context for the other feature.
- **tools.cleanup_pure_login_dialog_ui_pass_only.find_handlers** (function, lines 141–158, 18 lines, risk `support`): Retrieves find handlers for the other feature.
- **tools.cleanup_pure_login_dialog_ui_pass_only.replacement_lines** (function, lines 161–170, 10 lines, risk `support`): Handles replacement lines for the other feature.
- **tools.cleanup_pure_login_dialog_ui_pass_only.build_report** (function, lines 173–301, 129 lines, risk `filesystem`): Builds build report for the reports feature.
- **tools.cleanup_pure_login_dialog_ui_pass_only.main** (function, lines 304–320, 17 lines, risk `filesystem`): Handles main for the other feature.

## `tools/cleanup_stale_databank_generated_blocks.py`

- **tools.cleanup_stale_databank_generated_blocks._line_indent** (function, lines 91–92, 2 lines, risk `support`): Handles line indent for the other feature.
- **tools.cleanup_stale_databank_generated_blocks._find_callback_definitions** (function, lines 95–101, 7 lines, risk `support`): Retrieves find callback definitions for the other feature.
- **tools.cleanup_stale_databank_generated_blocks._target_reference_lines** (function, lines 104–106, 3 lines, risk `support`): Handles target reference lines for the other feature.
- **tools.cleanup_stale_databank_generated_blocks._has_marker** (function, lines 109–111, 3 lines, risk `support`): Handles has marker for the other feature.
- **tools.cleanup_stale_databank_generated_blocks._has_expected_generated_code** (function, lines 114–116, 3 lines, risk `support`): Handles has expected generated code for the other feature.
- **tools.cleanup_stale_databank_generated_blocks._protected_hits** (function, lines 119–121, 3 lines, risk `support`): Handles protected hits for the other feature.
- **tools.cleanup_stale_databank_generated_blocks._split_comment_and_code_lines** (function, lines 124–139, 16 lines, risk `support`): Split Python source lines into comment-only lines and everything else. Protected terms in comments are safety notes, not executable lending/report logic. Protected terms in strings or executable code still count as code and keep the cleanup blocked.
- **tools.cleanup_stale_databank_generated_blocks._protected_hits_in_code** (function, lines 142–144, 3 lines, risk `support`): Handles protected hits in code for the other feature.
- **tools.cleanup_stale_databank_generated_blocks._protected_hits_in_comments** (function, lines 147–149, 3 lines, risk `support`): Handles protected hits in comments for the other feature.
- **tools.cleanup_stale_databank_generated_blocks._looks_like_generated_databank_cleanup_block** (function, lines 152–180, 29 lines, risk `support`): Return True only for generated cleanup/hide block shapes.
- **tools.cleanup_stale_databank_generated_blocks._is_possible_block_start** (function, lines 183–200, 18 lines, risk `support`): Handles is possible block start for the other feature.
- **tools.cleanup_stale_databank_generated_blocks._is_possible_block_boundary** (function, lines 203–215, 13 lines, risk `support`): Handles is possible block boundary for the other feature.
- **tools.cleanup_stale_databank_generated_blocks._next_boundary_after** (function, lines 218–228, 11 lines, risk `support`): Handles next boundary after for the other feature.
- **tools.cleanup_stale_databank_generated_blocks._candidate_range_for_reference** (function, lines 231–272, 42 lines, risk `support`): Return 0-based [start, end) candidate range for a stale generated block.
- **tools.cleanup_stale_databank_generated_blocks._merge_ranges** (function, lines 275–286, 12 lines, risk `support`): Handles merge ranges for the other feature.
- **tools.cleanup_stale_databank_generated_blocks._remove_ranges** (function, lines 289–294, 6 lines, risk `support`): Removes remove ranges for the other feature.
- **tools.cleanup_stale_databank_generated_blocks._format_terms** (function, lines 297–298, 2 lines, risk `support`): Handles format terms for the utilities feature.
- **tools.cleanup_stale_databank_generated_blocks._safety_check_range** (function, lines 301–334, 34 lines, risk `support`): Handles safety check range for the other feature.
- **tools.cleanup_stale_databank_generated_blocks.main** (function, lines 337–437, 101 lines, risk `filesystem`): Handles main for the other feature.

## `tools/disable_full_daily_ledger.py`

- **tools.disable_full_daily_ledger._flush** (function, lines 349–350, 2 lines, risk `reports`): Handles flush for the other feature.
- **tools.disable_full_daily_ledger.remove_existing_blocks** (function, lines 353–368, 16 lines, risk `support`): Removes remove existing blocks for the other feature.
- **tools.disable_full_daily_ledger._contains_legacy_label** (function, lines 371–373, 3 lines, risk `support`): Handles contains legacy label for the other feature.
- **tools.disable_full_daily_ledger._looks_like_legacy_button_line** (function, lines 376–389, 14 lines, risk `ui_only`): Handles looks like legacy button line for the other feature.
- **tools.disable_full_daily_ledger.remove_static_legacy_button_lines** (function, lines 392–400, 9 lines, risk `support`): Removes remove static legacy button lines for the other feature.
- **tools.disable_full_daily_ledger.main** (function, lines 403–438, 36 lines, risk `filesystem`): Handles main for the other feature.

## `tools/extract_append_unique_text.py`

- **tools.extract_append_unique_text.atomic_write** (function, lines 21–30, 10 lines, risk `filesystem`): Handles atomic write for the other feature.
- **tools.extract_append_unique_text.top_level_functions** (function, lines 33–35, 3 lines, risk `support`): Handles top level functions for the other feature.
- **tools.extract_append_unique_text.external_names** (function, lines 38–51, 14 lines, risk `support`): Handles external names for the other feature.
- **tools.extract_append_unique_text.build_plan** (function, lines 54–84, 31 lines, risk `filesystem`): Builds build plan for the other feature.
- **tools.extract_append_unique_text.validate_plan** (function, lines 87–98, 12 lines, risk `support`): Validates validate plan for the utilities feature.
- **tools.extract_append_unique_text.apply_extraction** (function, lines 101–130, 30 lines, risk `filesystem`): Handles apply extraction for the other feature.
- **tools.extract_append_unique_text.main** (function, lines 133–145, 13 lines, risk `filesystem`): Handles main for the other feature.

## `tools/extract_cilog_action_label.py`

- **tools.extract_cilog_action_label._local_names** (function, lines 20–31, 12 lines, risk `support`): Handles local names for the other feature.
- **tools.extract_cilog_action_label._find** (function, lines 34–35, 2 lines, risk `support`): Handles find for the other feature.
- **tools.extract_cilog_action_label._function_text** (function, lines 38–41, 4 lines, risk `support`): Handles function text for the other feature.
- **tools.extract_cilog_action_label._atomic_write** (function, lines 44–53, 10 lines, risk `filesystem`): Handles atomic write for the other feature.
- **tools.extract_cilog_action_label.build_plan** (function, lines 56–111, 56 lines, risk `filesystem`): Builds build plan for the other feature.
- **tools.extract_cilog_action_label.apply** (function, lines 114–123, 10 lines, risk `support`): Handles apply for the other feature.
- **tools.extract_cilog_action_label.main** (function, lines 126–142, 17 lines, risk `filesystem`): Handles main for the other feature.

## `tools/extract_cilog_diff_pairs.py`

- **tools.extract_cilog_diff_pairs._atomic_write** (function, lines 21–30, 10 lines, risk `filesystem`): Handles atomic write for the other feature.
- **tools.extract_cilog_diff_pairs._function_matches** (function, lines 33–39, 7 lines, risk `support`): Handles function matches for the other feature.
- **tools.extract_cilog_diff_pairs._local_names** (function, lines 42–56, 15 lines, risk `support`): Handles local names for the other feature.
- **tools.extract_cilog_diff_pairs._validate_node** (function, lines 59–83, 25 lines, risk `support`): Validates validate node for the utilities feature.
- **tools.extract_cilog_diff_pairs._caller_summary** (function, lines 86–105, 20 lines, risk `support`): Handles caller summary for the other feature.
- **tools.extract_cilog_diff_pairs.inspect_state** (function, lines 108–135, 28 lines, risk `filesystem`): Handles inspect state for the other feature.
- **tools.extract_cilog_diff_pairs.apply_extraction** (function, lines 138–184, 47 lines, risk `filesystem`): Handles apply extraction for the other feature.
- **tools.extract_cilog_diff_pairs.main** (function, lines 187–203, 17 lines, risk `filesystem`): Handles main for the other feature.

## `tools/extract_cilog_value_formatter.py`

- **tools.extract_cilog_value_formatter._node_source** (function, lines 21–24, 4 lines, risk `support`): Handles node source for the other feature.
- **tools.extract_cilog_value_formatter._top_level_function** (function, lines 27–31, 5 lines, risk `support`): Handles top level function for the other feature.
- **tools.extract_cilog_value_formatter._local_names** (function, lines 34–45, 12 lines, risk `support`): Handles local names for the other feature.
- **tools.extract_cilog_value_formatter._validate** (function, lines 48–60, 13 lines, risk `support`): Handles validate for the utilities feature.
- **tools.extract_cilog_value_formatter.build_plan** (function, lines 63–115, 53 lines, risk `filesystem`): Builds build plan for the other feature.
- **tools.extract_cilog_value_formatter._atomic_write** (function, lines 118–127, 10 lines, risk `filesystem`): Handles atomic write for the other feature.
- **tools.extract_cilog_value_formatter.apply_extraction** (function, lines 130–140, 11 lines, risk `support`): Handles apply extraction for the other feature.
- **tools.extract_cilog_value_formatter.main** (function, lines 143–161, 19 lines, risk `filesystem`): Handles main for the other feature.

## `tools/extract_date_display_helpers.py`

- **tools.extract_date_display_helpers._line_source** (function, lines 32–37, 6 lines, risk `support`): Handles line source for the other feature.
- **tools.extract_date_display_helpers._top_level_functions** (function, lines 40–47, 8 lines, risk `support`): Handles top level functions for the other feature.
- **tools.extract_date_display_helpers._local_names** (function, lines 50–68, 19 lines, risk `support`): Handles local names for the other feature.
- **tools.extract_date_display_helpers._external_loaded_names** (function, lines 71–78, 8 lines, risk `support`): Handles external loaded names for the other feature.
- **tools.extract_date_display_helpers._validate_signature** (function, lines 81–84, 4 lines, risk `support`): Validates validate signature for the utilities feature.
- **tools.extract_date_display_helpers._validate_existing_module** (function, lines 87–105, 19 lines, risk `support`): Validates validate existing module for the utilities feature.
- **tools.extract_date_display_helpers._append_module_source** (function, lines 108–114, 7 lines, risk `support`): Handles append module source for the other feature.
- **tools.extract_date_display_helpers._patched_source** (function, lines 117–125, 9 lines, risk `support`): Handles patched source for the other feature.
- **tools.extract_date_display_helpers._state** (function, lines 128–138, 11 lines, risk `support`): Handles state for the other feature.
- **tools.extract_date_display_helpers.build_plan** (function, lines 141–208, 68 lines, risk `filesystem`): Builds build plan for the other feature.
- **tools.extract_date_display_helpers._atomic_write** (function, lines 211–220, 10 lines, risk `filesystem`): Handles atomic write for the other feature.
- **tools.extract_date_display_helpers.apply_extraction** (function, lines 223–233, 11 lines, risk `support`): Handles apply extraction for the other feature.
- **tools.extract_date_display_helpers.main** (function, lines 236–253, 18 lines, risk `filesystem`): Handles main for the other feature.

## `tools/extract_date_helpers_module.py`

- **tools.extract_date_helpers_module._line_source** (function, lines 34–41, 8 lines, risk `support`): Handles line source for the other feature.
- **tools.extract_date_helpers_module._top_level_functions** (function, lines 44–51, 8 lines, risk `support`): Handles top level functions for the other feature.
- **tools.extract_date_helpers_module._local_names** (function, lines 54–75, 22 lines, risk `support`): Handles local names for the other feature.
- **tools.extract_date_helpers_module._external_loaded_names** (function, lines 78–85, 8 lines, risk `support`): Handles external loaded names for the other feature.
- **tools.extract_date_helpers_module._import_bindings** (function, lines 88–101, 14 lines, risk `support`): Handles import bindings for the other feature.
- **tools.extract_date_helpers_module._stdlib_roots** (function, lines 104–107, 4 lines, risk `support`): Handles stdlib roots for the other feature.
- **tools.extract_date_helpers_module._required_import_nodes** (function, lines 110–146, 37 lines, risk `support`): Handles required import nodes for the other feature.
- **tools.extract_date_helpers_module._module_source** (function, lines 149–169, 21 lines, risk `support`): Handles module source for the other feature.
- **tools.extract_date_helpers_module._patched_source** (function, lines 172–180, 9 lines, risk `support`): Handles patched source for the other feature.
- **tools.extract_date_helpers_module._state** (function, lines 183–193, 11 lines, risk `support`): Handles state for the other feature.
- **tools.extract_date_helpers_module.build_plan** (function, lines 196–254, 59 lines, risk `filesystem`): Builds build plan for the other feature.
- **tools.extract_date_helpers_module._atomic_write** (function, lines 257–266, 10 lines, risk `filesystem`): Handles atomic write for the other feature.
- **tools.extract_date_helpers_module.apply_extraction** (function, lines 269–289, 21 lines, risk `support`): Handles apply extraction for the other feature.
- **tools.extract_date_helpers_module.main** (function, lines 292–310, 19 lines, risk `filesystem`): Handles main for the other feature.

## `tools/extract_display_formatters.py`

- **tools.extract_display_formatters._node_source** (function, lines 31–36, 6 lines, risk `support`): Handles node source for the other feature.
- **tools.extract_display_formatters._top_level_functions** (function, lines 39–46, 8 lines, risk `support`): Handles top level functions for the other feature.
- **tools.extract_display_formatters._local_names** (function, lines 49–69, 21 lines, risk `support`): Handles local names for the other feature.
- **tools.extract_display_formatters._external_loaded_names** (function, lines 72–79, 8 lines, risk `support`): Handles external loaded names for the other feature.
- **tools.extract_display_formatters._module_target_counts** (function, lines 82–91, 10 lines, risk `support`): Handles module target counts for the other feature.
- **tools.extract_display_formatters._state** (function, lines 94–104, 11 lines, risk `support`): Handles state for the other feature.
- **tools.extract_display_formatters._patched_source** (function, lines 107–118, 12 lines, risk `support`): Handles patched source for the other feature.
- **tools.extract_display_formatters._atomic_write** (function, lines 121–130, 10 lines, risk `filesystem`): Handles atomic write for the other feature.
- **tools.extract_display_formatters.build_plan** (function, lines 133–203, 71 lines, risk `filesystem`): Builds build plan for the other feature.
- **tools.extract_display_formatters.apply_extraction** (function, lines 206–216, 11 lines, risk `support`): Handles apply extraction for the other feature.
- **tools.extract_display_formatters.main** (function, lines 219–236, 18 lines, risk `filesystem`): Handles main for the other feature.

## `tools/extract_fmt_currency_module.py`

- **tools.extract_fmt_currency_module._find_top_level_function** (function, lines 27–37, 11 lines, risk `support`): Retrieves find top level function for the other feature.
- **tools.extract_fmt_currency_module._local_names** (function, lines 40–61, 22 lines, risk `support`): Handles local names for the other feature.
- **tools.extract_fmt_currency_module._external_loaded_names** (function, lines 64–71, 8 lines, risk `support`): Handles external loaded names for the other feature.
- **tools.extract_fmt_currency_module._function_source** (function, lines 74–81, 8 lines, risk `support`): Handles function source for the other feature.
- **tools.extract_fmt_currency_module._module_source** (function, lines 84–89, 6 lines, risk `support`): Handles module source for the other feature.
- **tools.extract_fmt_currency_module._replace_definition** (function, lines 92–97, 6 lines, risk `support`): Handles replace definition for the other feature.
- **tools.extract_fmt_currency_module._atomic_write** (function, lines 100–109, 10 lines, risk `filesystem`): Handles atomic write for the other feature.
- **tools.extract_fmt_currency_module.build_plan** (function, lines 112–153, 42 lines, risk `filesystem`): Builds build plan for the other feature.
- **tools.extract_fmt_currency_module.apply_extraction** (function, lines 156–174, 19 lines, risk `support`): Handles apply extraction for the other feature.
- **tools.extract_fmt_currency_module.main** (function, lines 177–201, 25 lines, risk `filesystem`): Handles main for the other feature.

## `tools/extract_log_serialization_helper.py`

- **tools.extract_log_serialization_helper._source** (function, lines 20–23, 4 lines, risk `support`): Handles source for the other feature.
- **tools.extract_log_serialization_helper._function** (function, lines 26–30, 5 lines, risk `support`): Handles function for the other feature.
- **tools.extract_log_serialization_helper._local_names** (function, lines 33–44, 12 lines, risk `support`): Handles local names for the other feature.
- **tools.extract_log_serialization_helper._validate** (function, lines 47–59, 13 lines, risk `support`): Handles validate for the utilities feature.
- **tools.extract_log_serialization_helper.build_plan** (function, lines 62–102, 41 lines, risk `filesystem`): Builds build plan for the other feature.
- **tools.extract_log_serialization_helper._write** (function, lines 105–114, 10 lines, risk `filesystem`): Handles write for the other feature.
- **tools.extract_log_serialization_helper.apply** (function, lines 117–126, 10 lines, risk `support`): Handles apply for the other feature.
- **tools.extract_log_serialization_helper.main** (function, lines 129–142, 14 lines, risk `filesystem`): Handles main for the other feature.

## `tools/extract_merge_note_dict.py`

- **tools.extract_merge_note_dict.atomic_write** (function, lines 22–31, 10 lines, risk `filesystem`): Handles atomic write for the other feature.
- **tools.extract_merge_note_dict.top_level_functions** (function, lines 34–36, 3 lines, risk `support`): Handles top level functions for the other feature.
- **tools.extract_merge_note_dict.external_names** (function, lines 39–55, 17 lines, risk `support`): Handles external names for the other feature.
- **tools.extract_merge_note_dict.build_plan** (function, lines 58–94, 37 lines, risk `filesystem`): Builds build plan for the other feature.
- **tools.extract_merge_note_dict.validate_plan** (function, lines 97–107, 11 lines, risk `support`): Validates validate plan for the utilities feature.
- **tools.extract_merge_note_dict.apply_extraction** (function, lines 110–140, 31 lines, risk `filesystem`): Handles apply extraction for the other feature.
- **tools.extract_merge_note_dict.main** (function, lines 143–156, 14 lines, risk `filesystem`): Handles main for the other feature.

## `tools/extract_note_dict_helper.py`

- **tools.extract_note_dict_helper.atomic_write** (function, lines 21–30, 10 lines, risk `filesystem`): Handles atomic write for the other feature.
- **tools.extract_note_dict_helper.top_level_functions** (function, lines 33–35, 3 lines, risk `support`): Handles top level functions for the other feature.
- **tools.extract_note_dict_helper.external_names** (function, lines 38–54, 17 lines, risk `support`): Handles external names for the other feature.
- **tools.extract_note_dict_helper.build_plan** (function, lines 57–95, 39 lines, risk `filesystem`): Builds build plan for the other feature.
- **tools.extract_note_dict_helper.validate_plan** (function, lines 98–109, 12 lines, risk `support`): Validates validate plan for the utilities feature.
- **tools.extract_note_dict_helper.apply_extraction** (function, lines 112–141, 30 lines, risk `filesystem`): Handles apply extraction for the other feature.
- **tools.extract_note_dict_helper.main** (function, lines 144–157, 14 lines, risk `filesystem`): Handles main for the other feature.

## `tools/extract_numeric_parsers.py`

- **tools.extract_numeric_parsers._line_source** (function, lines 31–36, 6 lines, risk `support`): Handles line source for the other feature.
- **tools.extract_numeric_parsers._top_level_functions** (function, lines 39–46, 8 lines, risk `support`): Handles top level functions for the other feature.
- **tools.extract_numeric_parsers._local_names** (function, lines 49–69, 21 lines, risk `support`): Handles local names for the other feature.
- **tools.extract_numeric_parsers._external_loaded_names** (function, lines 72–79, 8 lines, risk `support`): Handles external loaded names for the other feature.
- **tools.extract_numeric_parsers._validate_function** (function, lines 82–94, 13 lines, risk `support`): Validates validate function for the utilities feature.
- **tools.extract_numeric_parsers._module_source** (function, lines 97–116, 20 lines, risk `support`): Handles module source for the other feature.
- **tools.extract_numeric_parsers._patched_source** (function, lines 119–127, 9 lines, risk `support`): Handles patched source for the other feature.
- **tools.extract_numeric_parsers._state** (function, lines 130–140, 11 lines, risk `support`): Handles state for the other feature.
- **tools.extract_numeric_parsers.build_plan** (function, lines 143–194, 52 lines, risk `filesystem`): Builds build plan for the other feature.
- **tools.extract_numeric_parsers._atomic_write** (function, lines 197–206, 10 lines, risk `filesystem`): Handles atomic write for the other feature.
- **tools.extract_numeric_parsers.apply_extraction** (function, lines 209–218, 10 lines, risk `support`): Handles apply extraction for the other feature.
- **tools.extract_numeric_parsers.main** (function, lines 221–239, 19 lines, risk `filesystem`): Handles main for the other feature.

## `tools/extract_pure_helper_batch.py`

- **tools.extract_pure_helper_batch._load_manifest** (function, lines 22–28, 7 lines, risk `filesystem`): Loads load manifest for the other feature.
- **tools.extract_pure_helper_batch._source_hash** (function, lines 31–32, 2 lines, risk `support`): Handles source hash for the other feature.
- **tools.extract_pure_helper_batch._external_names** (function, lines 35–56, 22 lines, risk `support`): Handles external names for the other feature.
- **tools.extract_pure_helper_batch._matching_imports** (function, lines 59–67, 9 lines, risk `support`): Handles matching imports for the other feature.
- **tools.extract_pure_helper_batch._module_definitions** (function, lines 70–78, 9 lines, risk `filesystem`): Handles module definitions for the other feature.
- **tools.extract_pure_helper_batch.inspect** (function, lines 81–197, 117 lines, risk `filesystem`): Handles inspect for the other feature.
- **tools.extract_pure_helper_batch.apply** (function, lines 200–245, 46 lines, risk `filesystem`): Handles apply for the other feature.
- **tools.extract_pure_helper_batch.main** (function, lines 248–260, 13 lines, risk `filesystem`): Handles main for the other feature.

## `tools/extract_text_normalizers.py`

- **tools.extract_text_normalizers._line_source** (function, lines 34–39, 6 lines, risk `support`): Handles line source for the other feature.
- **tools.extract_text_normalizers._top_level_functions** (function, lines 42–49, 8 lines, risk `support`): Handles top level functions for the other feature.
- **tools.extract_text_normalizers._local_names** (function, lines 52–72, 21 lines, risk `support`): Handles local names for the other feature.
- **tools.extract_text_normalizers._external_loaded_names** (function, lines 75–82, 8 lines, risk `support`): Handles external loaded names for the other feature.
- **tools.extract_text_normalizers._import_bindings** (function, lines 85–96, 12 lines, risk `support`): Handles import bindings for the other feature.
- **tools.extract_text_normalizers._stdlib_roots** (function, lines 99–102, 4 lines, risk `support`): Handles stdlib roots for the other feature.
- **tools.extract_text_normalizers._required_import_nodes** (function, lines 105–141, 37 lines, risk `support`): Handles required import nodes for the other feature.
- **tools.extract_text_normalizers._module_source** (function, lines 144–164, 21 lines, risk `support`): Handles module source for the other feature.
- **tools.extract_text_normalizers._patched_source** (function, lines 167–178, 12 lines, risk `support`): Handles patched source for the other feature.
- **tools.extract_text_normalizers._state** (function, lines 181–191, 11 lines, risk `support`): Handles state for the other feature.
- **tools.extract_text_normalizers.build_plan** (function, lines 194–259, 66 lines, risk `filesystem`): Builds build plan for the other feature.
- **tools.extract_text_normalizers._atomic_write** (function, lines 262–271, 10 lines, risk `filesystem`): Handles atomic write for the other feature.
- **tools.extract_text_normalizers.apply_extraction** (function, lines 274–283, 10 lines, risk `support`): Handles apply extraction for the other feature.
- **tools.extract_text_normalizers.main** (function, lines 286–304, 19 lines, risk `filesystem`): Handles main for the other feature.

## `tools/inject_critical_path_logging.py`

- **tools.inject_critical_path_logging.remove_existing_block** (function, lines 137–145, 9 lines, risk `support`): Removes remove existing block for the other feature.
- **tools.inject_critical_path_logging.main** (function, lines 148–170, 23 lines, risk `filesystem`): Handles main for the other feature.

## `tools/inject_reports_pdf_logging.py`

- **tools.inject_reports_pdf_logging.remove_existing_block** (function, lines 138–146, 9 lines, risk `support`): Removes remove existing block for the other feature.
- **tools.inject_reports_pdf_logging.main** (function, lines 149–171, 23 lines, risk `filesystem`): Handles main for the other feature.

## `tools/inject_silent_ui_logging.py`

- **tools.inject_silent_ui_logging._lower** (function, lines 174–175, 2 lines, risk `support`): Handles lower for the other feature.
- **tools.inject_silent_ui_logging._has_any** (function, lines 178–180, 3 lines, risk `support`): Handles has any for the other feature.
- **tools.inject_silent_ui_logging._line_indent_width** (function, lines 183–184, 2 lines, risk `support`): Handles line indent width for the other feature.
- **tools.inject_silent_ui_logging._context** (function, lines 187–190, 4 lines, risk `support`): Handles context for the other feature.
- **tools.inject_silent_ui_logging._function_map** (function, lines 193–206, 14 lines, risk `support`): Handles function map for the other feature.
- **tools.inject_silent_ui_logging._body_after_except** (function, lines 209–219, 11 lines, risk `support`): Handles body after except for the other feature.
- **tools.inject_silent_ui_logging._is_silent_fallback_body** (function, lines 222–232, 11 lines, risk `support`): Handles is silent fallback body for the other feature.
- **tools.inject_silent_ui_logging._skip_reason** (function, lines 235–246, 12 lines, risk `support`): Handles skip reason for the other feature.
- **tools.inject_silent_ui_logging.find_candidates** (function, lines 249–276, 28 lines, risk `support`): Retrieves find candidates for the other feature.
- **tools.inject_silent_ui_logging._insert_logging** (function, lines 279–299, 21 lines, risk `support`): Handles insert logging for the other feature.
- **tools.inject_silent_ui_logging.run** (function, lines 302–330, 29 lines, risk `filesystem`): Handles run for the other feature.
- **tools.inject_silent_ui_logging.print_report** (function, lines 333–349, 17 lines, risk `reports`): Generates print report for the reports feature.
- **tools.inject_silent_ui_logging.main** (function, lines 352–364, 13 lines, risk `reports`): Handles main for the other feature.

## `tools/inspect_blocking_ui_context.py`

- **tools.inspect_blocking_ui_context._call_name** (function, lines 38–44, 7 lines, risk `support`): Handles call name for the other feature.
- **tools.inspect_blocking_ui_context._is_blocking_call** (function, lines 47–51, 5 lines, risk `support`): Handles is blocking call for the other feature.
- **tools.inspect_blocking_ui_context._span_for_node** (function, lines 54–57, 4 lines, risk `support`): Handles span for node for the other feature.
- **tools.inspect_blocking_ui_context._context** (function, lines 60–66, 7 lines, risk `support`): Handles context for the other feature.
- **tools.inspect_blocking_ui_context._contains_protected_text** (function, lines 69–71, 3 lines, risk `support`): Handles contains protected text for the other feature.
- **tools.inspect_blocking_ui_context._severity** (function, lines 74–83, 10 lines, risk `support`): Handles severity for the other feature.
- **tools.inspect_blocking_ui_context.BlockingContextVisitor** (class, lines 86–130, 45 lines, risk `container`): Groups BlockingContextVisitor for the other feature.
- **tools.inspect_blocking_ui_context.BlockingContextVisitor.__init__** (method, lines 87–91, 5 lines, risk `support`): Handles init for the other feature.
- **tools.inspect_blocking_ui_context.BlockingContextVisitor._scope_name** (method, lines 93–94, 2 lines, risk `support`): Handles scope name for the other feature.
- **tools.inspect_blocking_ui_context.BlockingContextVisitor.visit_ClassDef** (method, lines 96–99, 4 lines, risk `support`): Handles visit ClassDef for the other feature.
- **tools.inspect_blocking_ui_context.BlockingContextVisitor.visit_FunctionDef** (method, lines 101–104, 4 lines, risk `support`): Handles visit FunctionDef for the other feature.
- **tools.inspect_blocking_ui_context.BlockingContextVisitor.visit_AsyncFunctionDef** (method, lines 106–107, 2 lines, risk `support`): Handles visit AsyncFunctionDef for the other feature.
- **tools.inspect_blocking_ui_context.BlockingContextVisitor.visit_Call** (method, lines 109–130, 22 lines, risk `support`): Handles visit Call for the other feature.
- **tools.inspect_blocking_ui_context.inspect_source** (function, lines 133–156, 24 lines, risk `filesystem`): Handles inspect source for the other feature.
- **tools.inspect_blocking_ui_context.main** (function, lines 159–172, 14 lines, risk `filesystem`): Handles main for the other feature.

## `tools/inspect_stale_databank_protected_context.py`

- **tools.inspect_stale_databank_protected_context._load_cleanup_tool** (function, lines 22–28, 7 lines, risk `support`): Loads load cleanup tool for the other feature.
- **tools.inspect_stale_databank_protected_context._matching_terms** (function, lines 31–33, 3 lines, risk `support`): Handles matching terms for the other feature.
- **tools.inspect_stale_databank_protected_context.main** (function, lines 36–105, 70 lines, risk `filesystem`): Handles main for the other feature.

## `tools/plan_app_lifecycle_window_pass_only.py`

- **tools.plan_app_lifecycle_window_pass_only._name** (function, lines 48–59, 12 lines, risk `support`): Handles name for the other feature.
- **tools.plan_app_lifecycle_window_pass_only._is_pass_only** (function, lines 62–63, 2 lines, risk `support`): Handles is pass only for the payments feature.
- **tools.plan_app_lifecycle_window_pass_only._context** (function, lines 66–69, 4 lines, risk `support`): Handles context for the other feature.
- **tools.plan_app_lifecycle_window_pass_only._context_text** (function, lines 72–73, 2 lines, risk `support`): Handles context text for the other feature.
- **tools.plan_app_lifecycle_window_pass_only._protected** (function, lines 76–77, 2 lines, risk `support`): Handles protected for the other feature.
- **tools.plan_app_lifecycle_window_pass_only._classify** (function, lines 80–103, 24 lines, risk `support`): Handles classify for the other feature.
- **tools.plan_app_lifecycle_window_pass_only.PassOnlyVisitor** (class, lines 106–157, 52 lines, risk `container`): Groups PassOnlyVisitor for the payments feature.
- **tools.plan_app_lifecycle_window_pass_only.PassOnlyVisitor.__init__** (method, lines 107–111, 5 lines, risk `support`): Handles init for the payments feature.
- **tools.plan_app_lifecycle_window_pass_only.PassOnlyVisitor._scope** (method, lines 113–114, 2 lines, risk `support`): Handles scope for the payments feature.
- **tools.plan_app_lifecycle_window_pass_only.PassOnlyVisitor.visit_ClassDef** (method, lines 116–119, 4 lines, risk `support`): Handles visit ClassDef for the payments feature.
- **tools.plan_app_lifecycle_window_pass_only.PassOnlyVisitor.visit_FunctionDef** (method, lines 121–124, 4 lines, risk `support`): Handles visit FunctionDef for the payments feature.
- **tools.plan_app_lifecycle_window_pass_only.PassOnlyVisitor.visit_AsyncFunctionDef** (method, lines 126–129, 4 lines, risk `support`): Handles visit AsyncFunctionDef for the payments feature.
- **tools.plan_app_lifecycle_window_pass_only.PassOnlyVisitor.visit_Try** (method, lines 131–157, 27 lines, risk `support`): Handles visit Try for the payments feature.
- **tools.plan_app_lifecycle_window_pass_only.build_report** (function, lines 160–198, 39 lines, risk `filesystem`): Builds build report for the reports feature.
- **tools.plan_app_lifecycle_window_pass_only.main** (function, lines 201–215, 15 lines, risk `filesystem`): Handles main for the other feature.

## `tools/plan_logger_fallback_pass_only.py`

- **tools.plan_logger_fallback_pass_only._handler_name** (function, lines 54–64, 11 lines, risk `support`): Handles handler name for the other feature.
- **tools.plan_logger_fallback_pass_only._is_pass_only** (function, lines 67–68, 2 lines, risk `support`): Handles is pass only for the payments feature.
- **tools.plan_logger_fallback_pass_only._context** (function, lines 71–77, 7 lines, risk `support`): Handles context for the other feature.
- **tools.plan_logger_fallback_pass_only._scope_name** (function, lines 80–81, 2 lines, risk `support`): Handles scope name for the other feature.
- **tools.plan_logger_fallback_pass_only.PassOnlyVisitor** (class, lines 84–133, 50 lines, risk `container`): Groups PassOnlyVisitor for the payments feature.
- **tools.plan_logger_fallback_pass_only.PassOnlyVisitor.__init__** (method, lines 85–89, 5 lines, risk `support`): Handles init for the payments feature.
- **tools.plan_logger_fallback_pass_only.PassOnlyVisitor.visit_ClassDef** (method, lines 91–94, 4 lines, risk `support`): Handles visit ClassDef for the payments feature.
- **tools.plan_logger_fallback_pass_only.PassOnlyVisitor.visit_FunctionDef** (method, lines 96–99, 4 lines, risk `support`): Handles visit FunctionDef for the payments feature.
- **tools.plan_logger_fallback_pass_only.PassOnlyVisitor.visit_AsyncFunctionDef** (method, lines 101–104, 4 lines, risk `support`): Handles visit AsyncFunctionDef for the payments feature.
- **tools.plan_logger_fallback_pass_only.PassOnlyVisitor.visit_Try** (method, lines 106–133, 28 lines, risk `support`): Handles visit Try for the payments feature.
- **tools.plan_logger_fallback_pass_only.build_report** (function, lines 136–172, 37 lines, risk `filesystem`): Builds build report for the reports feature.
- **tools.plan_logger_fallback_pass_only.main** (function, lines 175–187, 13 lines, risk `filesystem`): Handles main for the other feature.

## `tools/plan_login_dialog_pass_only.py`

- **tools.plan_login_dialog_pass_only._read_text** (function, lines 95–96, 2 lines, risk `filesystem`): Handles read text for the other feature.
- **tools.plan_login_dialog_pass_only._handler_name** (function, lines 99–105, 7 lines, risk `support`): Handles handler name for the other feature.
- **tools.plan_login_dialog_pass_only._is_pass_only** (function, lines 108–109, 2 lines, risk `support`): Handles is pass only for the payments feature.
- **tools.plan_login_dialog_pass_only._line_window** (function, lines 112–118, 7 lines, risk `support`): Handles line window for the other feature.
- **tools.plan_login_dialog_pass_only._context_text** (function, lines 121–122, 2 lines, risk `support`): Handles context text for the other feature.
- **tools.plan_login_dialog_pass_only._has_any** (function, lines 125–127, 3 lines, risk `support`): Handles has any for the other feature.
- **tools.plan_login_dialog_pass_only.PassOnlyVisitor** (class, lines 130–192, 63 lines, risk `container`): Groups PassOnlyVisitor for the payments feature.
- **tools.plan_login_dialog_pass_only.PassOnlyVisitor.__init__** (method, lines 131–135, 5 lines, risk `support`): Handles init for the payments feature.
- **tools.plan_login_dialog_pass_only.PassOnlyVisitor._scope** (method, lines 137–138, 2 lines, risk `support`): Handles scope for the payments feature.
- **tools.plan_login_dialog_pass_only.PassOnlyVisitor.visit_FunctionDef** (method, lines 140–143, 4 lines, risk `support`): Handles visit FunctionDef for the payments feature.
- **tools.plan_login_dialog_pass_only.PassOnlyVisitor.visit_AsyncFunctionDef** (method, lines 145–148, 4 lines, risk `support`): Handles visit AsyncFunctionDef for the payments feature.
- **tools.plan_login_dialog_pass_only.PassOnlyVisitor.visit_ClassDef** (method, lines 150–153, 4 lines, risk `support`): Handles visit ClassDef for the payments feature.
- **tools.plan_login_dialog_pass_only.PassOnlyVisitor.visit_ExceptHandler** (method, lines 155–192, 38 lines, risk `support`): Handles visit ExceptHandler for the payments feature.
- **tools.plan_login_dialog_pass_only.build_report** (function, lines 195–240, 46 lines, risk `reports`): Builds build report for the reports feature.
- **tools.plan_login_dialog_pass_only.main** (function, lines 243–263, 21 lines, risk `filesystem`): Handles main for the other feature.

## `tools/plan_modern_ui_pass_only_cleanup.py`

- **tools.plan_modern_ui_pass_only_cleanup._is_pass_only** (function, lines 66–67, 2 lines, risk `support`): Handles is pass only for the payments feature.
- **tools.plan_modern_ui_pass_only_cleanup._handler_name** (function, lines 70–85, 16 lines, risk `support`): Handles handler name for the other feature.
- **tools.plan_modern_ui_pass_only_cleanup._context** (function, lines 88–91, 4 lines, risk `support`): Handles context for the other feature.
- **tools.plan_modern_ui_pass_only_cleanup._protected_context** (function, lines 94–96, 3 lines, risk `support`): Handles protected context for the other feature.
- **tools.plan_modern_ui_pass_only_cleanup.PassOnlyVisitor** (class, lines 99–157, 59 lines, risk `container`): Groups PassOnlyVisitor for the payments feature.
- **tools.plan_modern_ui_pass_only_cleanup.PassOnlyVisitor.__init__** (method, lines 100–105, 6 lines, risk `support`): Handles init for the payments feature.
- **tools.plan_modern_ui_pass_only_cleanup.PassOnlyVisitor._scope** (method, lines 107–112, 6 lines, risk `support`): Handles scope for the payments feature.
- **tools.plan_modern_ui_pass_only_cleanup.PassOnlyVisitor.visit_ClassDef** (method, lines 114–117, 4 lines, risk `support`): Handles visit ClassDef for the payments feature.
- **tools.plan_modern_ui_pass_only_cleanup.PassOnlyVisitor.visit_FunctionDef** (method, lines 119–122, 4 lines, risk `support`): Handles visit FunctionDef for the payments feature.
- **tools.plan_modern_ui_pass_only_cleanup.PassOnlyVisitor.visit_AsyncFunctionDef** (method, lines 124–125, 2 lines, risk `support`): Handles visit AsyncFunctionDef for the payments feature.
- **tools.plan_modern_ui_pass_only_cleanup.PassOnlyVisitor.visit_Try** (method, lines 127–157, 31 lines, risk `support`): Handles visit Try for the payments feature.
- **tools.plan_modern_ui_pass_only_cleanup.build_plan** (function, lines 160–196, 37 lines, risk `filesystem`): Builds build plan for the other feature.
- **tools.plan_modern_ui_pass_only_cleanup.main** (function, lines 199–211, 13 lines, risk `filesystem`): Handles main for the other feature.

## `tools/plan_module_separation.py`

- **tools.plan_module_separation._line_span** (function, lines 66–69, 4 lines, risk `support`): Handles line span for the other feature.
- **tools.plan_module_separation._source_text** (function, lines 72–76, 5 lines, risk `support`): Handles source text for the other feature.
- **tools.plan_module_separation._loaded_names** (function, lines 79–84, 6 lines, risk `support`): Handles loaded names for the other feature.
- **tools.plan_module_separation._called_names** (function, lines 87–96, 10 lines, risk `support`): Handles called names for the other feature.
- **tools.plan_module_separation._dependency_signals** (function, lines 99–100, 2 lines, risk `support`): Handles dependency signals for the other feature.
- **tools.plan_module_separation._is_protected** (function, lines 103–105, 3 lines, risk `support`): Handles is protected for the other feature.
- **tools.plan_module_separation._suggest_module** (function, lines 108–124, 17 lines, risk `support`): Handles suggest module for the other feature.
- **tools.plan_module_separation._risk_level** (function, lines 127–139, 13 lines, risk `support`): Handles risk level for the other feature.
- **tools.plan_module_separation._top_level_assignments** (function, lines 142–154, 13 lines, risk `support`): Handles top level assignments for the other feature.
- **tools.plan_module_separation._imports** (function, lines 157–164, 8 lines, risk `support`): Handles imports for the other feature.
- **tools.plan_module_separation._record_definition** (function, lines 167–208, 42 lines, risk `support`): Handles record definition for the other feature.
- **tools.plan_module_separation.build_report** (function, lines 211–286, 76 lines, risk `filesystem`): Builds build report for the reports feature.
- **tools.plan_module_separation.main** (function, lines 289–300, 12 lines, risk `filesystem`): Handles main for the other feature.

## `tools/plan_pure_login_dialog_ui_pass_only.py`

- **tools.plan_pure_login_dialog_ui_pass_only.HandlerVisitor** (class, lines 71–139, 69 lines, risk `container`): Groups HandlerVisitor for the other feature.
- **tools.plan_pure_login_dialog_ui_pass_only.HandlerVisitor.__init__** (method, lines 72–76, 5 lines, risk `support`): Handles init for the other feature.
- **tools.plan_pure_login_dialog_ui_pass_only.HandlerVisitor.visit_ClassDef** (method, lines 78–81, 4 lines, risk `support`): Handles visit ClassDef for the other feature.
- **tools.plan_pure_login_dialog_ui_pass_only.HandlerVisitor.visit_FunctionDef** (method, lines 83–86, 4 lines, risk `support`): Handles visit FunctionDef for the other feature.
- **tools.plan_pure_login_dialog_ui_pass_only.HandlerVisitor.visit_AsyncFunctionDef** (method, lines 88–91, 4 lines, risk `support`): Handles visit AsyncFunctionDef for the other feature.
- **tools.plan_pure_login_dialog_ui_pass_only.HandlerVisitor.visit_ExceptHandler** (method, lines 93–96, 4 lines, risk `support`): Handles visit ExceptHandler for the other feature.
- **tools.plan_pure_login_dialog_ui_pass_only.HandlerVisitor._is_exception_pass_only** (method, lines 98–103, 6 lines, risk `support`): Handles is exception pass only for the payments feature.
- **tools.plan_pure_login_dialog_ui_pass_only.HandlerVisitor._scope** (method, lines 105–106, 2 lines, risk `support`): Handles scope for the other feature.
- **tools.plan_pure_login_dialog_ui_pass_only.HandlerVisitor._context** (method, lines 108–114, 7 lines, risk `support`): Handles context for the other feature.
- **tools.plan_pure_login_dialog_ui_pass_only.HandlerVisitor._site** (method, lines 116–139, 24 lines, risk `authentication`): Handles site for the other feature.
- **tools.plan_pure_login_dialog_ui_pass_only._classify_pure_login_dialog_ui** (function, lines 142–157, 16 lines, risk `authentication`): Handles classify pure login dialog ui for the authentication feature.
- **tools.plan_pure_login_dialog_ui_pass_only._fallback_login_group** (function, lines 160–169, 10 lines, risk `authentication`): Handles fallback login group for the authentication feature.
- **tools.plan_pure_login_dialog_ui_pass_only.build_report** (function, lines 172–224, 53 lines, risk `filesystem`): Builds build report for the reports feature.
- **tools.plan_pure_login_dialog_ui_pass_only.main** (function, lines 227–240, 14 lines, risk `filesystem`): Handles main for the other feature.

## `tools/plan_queue_empty_pass_only.py`

- **tools.plan_queue_empty_pass_only._handler_name** (function, lines 48–58, 11 lines, risk `support`): Handles handler name for the other feature.
- **tools.plan_queue_empty_pass_only._is_pass_only** (function, lines 61–62, 2 lines, risk `support`): Handles is pass only for the payments feature.
- **tools.plan_queue_empty_pass_only._context** (function, lines 65–71, 7 lines, risk `support`): Handles context for the other feature.
- **tools.plan_queue_empty_pass_only._contains_protected_word** (function, lines 74–76, 3 lines, risk `support`): Handles contains protected word for the other feature.
- **tools.plan_queue_empty_pass_only.PassOnlyVisitor** (class, lines 79–136, 58 lines, risk `container`): Groups PassOnlyVisitor for the payments feature.
- **tools.plan_queue_empty_pass_only.PassOnlyVisitor.__init__** (method, lines 80–84, 5 lines, risk `support`): Handles init for the payments feature.
- **tools.plan_queue_empty_pass_only.PassOnlyVisitor._scope_name** (method, lines 86–87, 2 lines, risk `support`): Handles scope name for the payments feature.
- **tools.plan_queue_empty_pass_only.PassOnlyVisitor.visit_ClassDef** (method, lines 89–92, 4 lines, risk `support`): Handles visit ClassDef for the payments feature.
- **tools.plan_queue_empty_pass_only.PassOnlyVisitor.visit_FunctionDef** (method, lines 94–97, 4 lines, risk `support`): Handles visit FunctionDef for the payments feature.
- **tools.plan_queue_empty_pass_only.PassOnlyVisitor.visit_AsyncFunctionDef** (method, lines 99–102, 4 lines, risk `support`): Handles visit AsyncFunctionDef for the payments feature.
- **tools.plan_queue_empty_pass_only.PassOnlyVisitor.visit_ExceptHandler** (method, lines 104–136, 33 lines, risk `support`): Handles visit ExceptHandler for the payments feature.
- **tools.plan_queue_empty_pass_only.build_report** (function, lines 139–180, 42 lines, risk `filesystem`): Builds build report for the reports feature.
- **tools.plan_queue_empty_pass_only.main** (function, lines 183–196, 14 lines, risk `filesystem`): Handles main for the other feature.

## `tools/plan_remaining_pass_only_groups.py`

- **tools.plan_remaining_pass_only_groups.handler_name** (function, lines 50–68, 19 lines, risk `support`): Handles handler name for the other feature.
- **tools.plan_remaining_pass_only_groups.is_pass_only** (function, lines 71–72, 2 lines, risk `support`): Handles is pass only for the payments feature.
- **tools.plan_remaining_pass_only_groups.context_for** (function, lines 75–78, 4 lines, risk `support`): Handles context for for the other feature.
- **tools.plan_remaining_pass_only_groups.has_protected_context** (function, lines 81–83, 3 lines, risk `support`): Handles has protected context for the other feature.
- **tools.plan_remaining_pass_only_groups.classify** (function, lines 86–105, 20 lines, risk `ui_only`): Handles classify for the other feature.
- **tools.plan_remaining_pass_only_groups.PassOnlyVisitor** (class, lines 108–149, 42 lines, risk `container`): Groups PassOnlyVisitor for the payments feature.
- **tools.plan_remaining_pass_only_groups.PassOnlyVisitor.__init__** (method, lines 109–112, 4 lines, risk `support`): Handles init for the payments feature.
- **tools.plan_remaining_pass_only_groups.PassOnlyVisitor.current_scope** (method, lines 114–115, 2 lines, risk `support`): Handles current scope for the payments feature.
- **tools.plan_remaining_pass_only_groups.PassOnlyVisitor.visit_ClassDef** (method, lines 117–120, 4 lines, risk `support`): Handles visit ClassDef for the payments feature.
- **tools.plan_remaining_pass_only_groups.PassOnlyVisitor.visit_FunctionDef** (method, lines 122–125, 4 lines, risk `support`): Handles visit FunctionDef for the payments feature.
- **tools.plan_remaining_pass_only_groups.PassOnlyVisitor.visit_AsyncFunctionDef** (method, lines 127–128, 2 lines, risk `support`): Handles visit AsyncFunctionDef for the payments feature.
- **tools.plan_remaining_pass_only_groups.PassOnlyVisitor.visit_ExceptHandler** (method, lines 130–149, 20 lines, risk `support`): Handles visit ExceptHandler for the payments feature.
- **tools.plan_remaining_pass_only_groups.build_report** (function, lines 152–193, 42 lines, risk `filesystem`): Builds build report for the reports feature.
- **tools.plan_remaining_pass_only_groups.main** (function, lines 196–209, 14 lines, risk `filesystem`): Handles main for the other feature.

## `tools/plan_ui_compatibility_pass_only.py`

- **tools.plan_ui_compatibility_pass_only.read_lines** (function, lines 113–114, 2 lines, risk `filesystem`): Handles read lines for the other feature.
- **tools.plan_ui_compatibility_pass_only.handler_name** (function, lines 117–131, 15 lines, risk `support`): Handles handler name for the other feature.
- **tools.plan_ui_compatibility_pass_only.is_pass_only** (function, lines 134–135, 2 lines, risk `support`): Handles is pass only for the payments feature.
- **tools.plan_ui_compatibility_pass_only.PassOnlyVisitor** (class, lines 138–161, 24 lines, risk `container`): Groups PassOnlyVisitor for the payments feature.
- **tools.plan_ui_compatibility_pass_only.PassOnlyVisitor.__init__** (method, lines 139–141, 3 lines, risk `support`): Handles init for the payments feature.
- **tools.plan_ui_compatibility_pass_only.PassOnlyVisitor.visit_ClassDef** (method, lines 143–146, 4 lines, risk `support`): Handles visit ClassDef for the payments feature.
- **tools.plan_ui_compatibility_pass_only.PassOnlyVisitor.visit_FunctionDef** (method, lines 148–151, 4 lines, risk `support`): Handles visit FunctionDef for the payments feature.
- **tools.plan_ui_compatibility_pass_only.PassOnlyVisitor.visit_AsyncFunctionDef** (method, lines 153–156, 4 lines, risk `support`): Handles visit AsyncFunctionDef for the payments feature.
- **tools.plan_ui_compatibility_pass_only.PassOnlyVisitor.visit_ExceptHandler** (method, lines 158–161, 4 lines, risk `support`): Handles visit ExceptHandler for the payments feature.
- **tools.plan_ui_compatibility_pass_only.line_window** (function, lines 164–167, 4 lines, risk `support`): Handles line window for the other feature.
- **tools.plan_ui_compatibility_pass_only.text_window** (function, lines 170–173, 4 lines, risk `support`): Handles text window for the other feature.
- **tools.plan_ui_compatibility_pass_only.contains_any** (function, lines 176–177, 2 lines, risk `support`): Handles contains any for the other feature.
- **tools.plan_ui_compatibility_pass_only.classify_ui_site** (function, lines 180–193, 14 lines, risk `support`): Handles classify ui site for the other feature.
- **tools.plan_ui_compatibility_pass_only.build_report** (function, lines 196–264, 69 lines, risk `reports`): Builds build report for the reports feature.
- **tools.plan_ui_compatibility_pass_only.main** (function, lines 267–280, 14 lines, risk `filesystem`): Handles main for the other feature.

## `tools/redundancy_audit.py`

- **tools.redundancy_audit.body_hash** (function, lines 19–30, 12 lines, risk `support`): Handles body hash for the other feature.
- **tools.redundancy_audit.audit** (function, lines 33–105, 73 lines, risk `filesystem`): Handles audit for the other feature.
- **tools.redundancy_audit.print_report** (function, lines 108–137, 30 lines, risk `reports`): Generates print report for the reports feature.
- **tools.redundancy_audit.main** (function, lines 140–149, 10 lines, risk `filesystem`): Handles main for the other feature.

## `tools/remove_databank_export_controls.py`

- **tools.remove_databank_export_controls.remove_existing_block** (function, lines 363–372, 10 lines, risk `support`): Removes remove existing block for the other feature.
- **tools.remove_databank_export_controls._contains_static_label** (function, lines 375–377, 3 lines, risk `support`): Handles contains static label for the other feature.
- **tools.remove_databank_export_controls._looks_like_ui_line** (function, lines 380–391, 12 lines, risk `ui_only`): Handles looks like ui line for the other feature.
- **tools.remove_databank_export_controls.remove_static_export_lines** (function, lines 394–402, 9 lines, risk `support`): Removes remove static export lines for the other feature.
- **tools.remove_databank_export_controls.main** (function, lines 405–433, 29 lines, risk `filesystem`): Handles main for the other feature.

## `tools/spina_quality_audit.py`

- **tools.spina_quality_audit._name** (function, lines 60–70, 11 lines, risk `support`): Handles name for the other feature.
- **tools.spina_quality_audit._line_span** (function, lines 73–76, 4 lines, risk `support`): Handles line span for the other feature.
- **tools.spina_quality_audit._is_pass_only** (function, lines 79–80, 2 lines, risk `support`): Handles is pass only for the payments feature.
- **tools.spina_quality_audit._sql_literal** (function, lines 83–92, 10 lines, risk `support`): Handles sql literal for the database feature.
- **tools.spina_quality_audit._risk_area** (function, lines 95–100, 6 lines, risk `support`): Handles risk area for the other feature.
- **tools.spina_quality_audit._handler_has_visible_action** (function, lines 103–113, 11 lines, risk `support`): Handles handler has visible action for the other feature.
- **tools.spina_quality_audit.audit** (function, lines 116–268, 153 lines, risk `filesystem`): Handles audit for the other feature.
- **tools.spina_quality_audit.print_report** (function, lines 271–303, 33 lines, risk `reports`): Generates print report for the reports feature.
- **tools.spina_quality_audit.main** (function, lines 306–316, 11 lines, risk `filesystem`): Handles main for the other feature.

## `tools/spina_startup_diagnostics.py`

- **tools.spina_startup_diagnostics.CheckResult** (class, lines 17–20, 4 lines, risk `container`): Groups CheckResult for the other feature.
- **tools.spina_startup_diagnostics._env** (function, lines 23–24, 2 lines, risk `support`): Handles env for the other feature.
- **tools.spina_startup_diagnostics.check_python** (function, lines 27–32, 6 lines, risk `filesystem`): Handles check python for the other feature.
- **tools.spina_startup_diagnostics.check_password** (function, lines 35–43, 9 lines, risk `authentication`): Handles check password for the payments feature.
- **tools.spina_startup_diagnostics.check_psycopg** (function, lines 46–51, 6 lines, risk `support`): Handles check psycopg for the other feature.
- **tools.spina_startup_diagnostics.check_tcp** (function, lines 54–59, 6 lines, risk `network`): Handles check tcp for the other feature.
- **tools.spina_startup_diagnostics.check_login** (function, lines 62–79, 18 lines, risk `authentication`): Handles check login for the authentication feature.
- **tools.spina_startup_diagnostics.main** (function, lines 82–115, 34 lines, risk `authentication`): Handles main for the other feature.

## `tools/test_account_header_presentation_wave_46.py`

- **tools.test_account_header_presentation_wave_46.normalized** (function, lines 45–46, 2 lines, risk `support`): Handles normalized for the utilities feature.
- **tools.test_account_header_presentation_wave_46.dotted** (function, lines 49–55, 7 lines, risk `support`): Handles dotted for the other feature.
- **tools.test_account_header_presentation_wave_46.signature_text** (function, lines 58–72, 15 lines, risk `support`): Handles signature text for the other feature.
- **tools.test_account_header_presentation_wave_46.source_for** (function, lines 75–76, 2 lines, risk `support`): Handles source for for the other feature.
- **tools.test_account_header_presentation_wave_46.function_defs** (function, lines 79–80, 2 lines, risk `support`): Handles function defs for the other feature.
- **tools.test_account_header_presentation_wave_46.check_function** (function, lines 83–101, 19 lines, risk `support`): Handles check function for the other feature.
- **tools.test_account_header_presentation_wave_46.main** (function, lines 104–180, 77 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_account_header_widget_smoke_wave_46.py`

- **tools.test_account_header_widget_smoke_wave_46.Harness** (class, lines 14–15, 2 lines, risk `container`): Groups Harness for the other feature.
- **tools.test_account_header_widget_smoke_wave_46.main** (function, lines 18–59, 42 lines, risk `authentication`): Handles main for the other feature.

## `tools/test_account_permission_presentation_wave_47.py`

- **tools.test_account_permission_presentation_wave_47.normalized_hash** (function, lines 38–40, 3 lines, risk `support`): Handles normalized hash for the utilities feature.
- **tools.test_account_permission_presentation_wave_47.function_nodes** (function, lines 43–48, 6 lines, risk `support`): Handles function nodes for the other feature.
- **tools.test_account_permission_presentation_wave_47.main** (function, lines 51–122, 72 lines, risk `authentication`): Handles main for the other feature.

## `tools/test_append_unique_text_extraction.py`

- **tools.test_append_unique_text_extraction.load_helper** (function, lines 36–59, 24 lines, risk `filesystem`): Loads load helper for the utilities feature.
- **tools.test_append_unique_text_extraction.capture_behavior** (function, lines 62–82, 21 lines, risk `support`): Handles capture behavior for the other feature.
- **tools.test_append_unique_text_extraction.main** (function, lines 85–101, 17 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_architecture_map.py`

- **tools.test_architecture_map.is_app** (function, lines 25–26, 2 lines, risk `support`): Handles is app for the other feature.
- **tools.test_architecture_map.main** (function, lines 29–170, 142 lines, risk `filesystem`): Handles main for the other feature.
- **tools.test_architecture_map.main.feature_for_suffix** (nested_function, lines 106–111, 6 lines, risk `support`): Handles feature for suffix for the other feature.

## `tools/test_area_picker_presentation_wave_37.py`

- **tools.test_area_picker_presentation_wave_37.normalized** (function, lines 18–19, 2 lines, risk `support`): Handles normalized for the utilities feature.
- **tools.test_area_picker_presentation_wave_37.digest** (function, lines 22–23, 2 lines, risk `support`): Handles digest for the other feature.
- **tools.test_area_picker_presentation_wave_37.call_chain** (function, lines 26–33, 8 lines, risk `support`): Handles call chain for the other feature.
- **tools.test_area_picker_presentation_wave_37.main** (function, lines 36–101, 66 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_audit_presentation_wave_54.py`

- **tools.test_audit_presentation_wave_54.normalized** (function, lines 15–16, 2 lines, risk `support`): Handles normalized for the utilities feature.
- **tools.test_audit_presentation_wave_54.source_hash** (function, lines 19–20, 2 lines, risk `support`): Handles source hash for the other feature.
- **tools.test_audit_presentation_wave_54.dotted** (function, lines 23–29, 7 lines, risk `support`): Handles dotted for the other feature.
- **tools.test_audit_presentation_wave_54.functions** (function, lines 32–33, 2 lines, risk `support`): Handles functions for the other feature.
- **tools.test_audit_presentation_wave_54.main** (function, lines 36–97, 62 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_audit_widget_smoke_wave_54.py`

- **tools.test_audit_widget_smoke_wave_54.walk** (function, lines 15–18, 4 lines, risk `support`): Handles walk for the other feature.
- **tools.test_audit_widget_smoke_wave_54.widget_texts** (function, lines 21–30, 10 lines, risk `support`): Handles widget texts for the other feature.
- **tools.test_audit_widget_smoke_wave_54.FakeDB** (class, lines 33–84, 52 lines, risk `container`): Groups FakeDB for the other feature.
- **tools.test_audit_widget_smoke_wave_54.FakeDB.__init__** (method, lines 34–76, 43 lines, risk `support`): Handles init for the other feature.
- **tools.test_audit_widget_smoke_wave_54.FakeDB.get_audit_new_loan_rows** (method, lines 78–80, 3 lines, risk `support`): Retrieves get audit new loan rows for the loans feature.
- **tools.test_audit_widget_smoke_wave_54.FakeDB.get_audit_renewal_rows** (method, lines 82–84, 3 lines, risk `financial_calculation`): Retrieves get audit renewal rows for the loans feature.
- **tools.test_audit_widget_smoke_wave_54.DummyAuditApp** (class, lines 87–132, 46 lines, risk `container`): Groups DummyAuditApp for the other feature.
- **tools.test_audit_widget_smoke_wave_54.DummyAuditApp.__init__** (method, lines 88–95, 8 lines, risk `ui_only`): Handles init for the other feature.
- **tools.test_audit_widget_smoke_wave_54.DummyAuditApp._audit_tree_factory** (method, lines 97–108, 12 lines, risk `ui_only`): Handles audit tree factory for the other feature.
- **tools.test_audit_widget_smoke_wave_54.DummyAuditApp._audit_show_selected** (method, lines 110–111, 2 lines, risk `support`): Handles audit show selected for the other feature.
- **tools.test_audit_widget_smoke_wave_54.DummyAuditApp._audit_set_today** (method, lines 113–114, 2 lines, risk `support`): Handles audit set today for the other feature.
- **tools.test_audit_widget_smoke_wave_54.DummyAuditApp._audit_set_last7** (method, lines 116–117, 2 lines, risk `support`): Handles audit set last7 for the other feature.
- **tools.test_audit_widget_smoke_wave_54.DummyAuditApp._audit_set_all** (method, lines 119–120, 2 lines, risk `support`): Handles audit set all for the other feature.
- **tools.test_audit_widget_smoke_wave_54.DummyAuditApp._audit_parse_date_filters** (method, lines 122–123, 2 lines, risk `support`): Handles audit parse date filters for the utilities feature.
- **tools.test_audit_widget_smoke_wave_54.DummyAuditApp._audit_money_text** (method, lines 125–129, 5 lines, risk `support`): Handles audit money text for the other feature.
- **tools.test_audit_widget_smoke_wave_54.DummyAuditApp._audit_set_detail_text** (method, lines 131–132, 2 lines, risk `support`): Handles audit set detail text for the other feature.
- **tools.test_audit_widget_smoke_wave_54.button_by_text** (function, lines 135–143, 9 lines, risk `ui_only`): Handles button by text for the other feature.
- **tools.test_audit_widget_smoke_wave_54.main** (function, lines 146–217, 72 lines, risk `financial_calculation`): Handles main for the other feature.

## `tools/test_base_theme_palette_batch_11.py`

- **tools.test_base_theme_palette_batch_11.Holder** (class, lines 30–33, 4 lines, risk `container`): Groups Holder for the other feature.
- **tools.test_base_theme_palette_batch_11.Holder.__init__** (method, lines 31–33, 3 lines, risk `support`): Handles init for the other feature.
- **tools.test_base_theme_palette_batch_11.BadString** (class, lines 36–38, 3 lines, risk `container`): Groups BadString for the other feature.
- **tools.test_base_theme_palette_batch_11.BadString.__str__** (method, lines 37–38, 2 lines, risk `support`): Handles str for the other feature.
- **tools.test_base_theme_palette_batch_11._stable** (function, lines 41–48, 8 lines, risk `support`): Handles stable for the other feature.
- **tools.test_base_theme_palette_batch_11._type_name** (function, lines 51–53, 3 lines, risk `support`): Handles type name for the other feature.
- **tools.test_base_theme_palette_batch_11._load_manifest** (function, lines 56–57, 2 lines, risk `filesystem`): Loads load manifest for the other feature.
- **tools.test_base_theme_palette_batch_11._resolve_from_source** (function, lines 60–80, 21 lines, risk `filesystem`): Handles resolve from source for the other feature.
- **tools.test_base_theme_palette_batch_11._resolve_function** (function, lines 83–93, 11 lines, risk `support`): Handles resolve function for the other feature.
- **tools.test_base_theme_palette_batch_11._cases** (function, lines 96–109, 14 lines, risk `support`): Handles cases for the other feature.
- **tools.test_base_theme_palette_batch_11._capture_call** (function, lines 112–125, 14 lines, risk `support`): Handles capture call for the other feature.
- **tools.test_base_theme_palette_batch_11.capture_batch** (function, lines 128–148, 21 lines, risk `support`): Handles capture batch for the other feature.
- **tools.test_base_theme_palette_batch_11.main** (function, lines 151–190, 40 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_calendar_presentation_wave_41.py`

- **tools.test_calendar_presentation_wave_41.normalized** (function, lines 20–21, 2 lines, risk `support`): Handles normalized for the utilities feature.
- **tools.test_calendar_presentation_wave_41.call_chain** (function, lines 24–31, 8 lines, risk `support`): Handles call chain for the other feature.
- **tools.test_calendar_presentation_wave_41.main** (function, lines 34–91, 58 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_cash_control_feature_wave_21.py`

- **tools.test_cash_control_feature_wave_21.top_level_functions** (function, lines 21–27, 7 lines, risk `filesystem`): Handles top level functions for the other feature.
- **tools.test_cash_control_feature_wave_21.FakeCanvas** (class, lines 30–50, 21 lines, risk `container`): Groups FakeCanvas for the other feature.
- **tools.test_cash_control_feature_wave_21.FakeCanvas.__init__** (method, lines 31–34, 4 lines, risk `support`): Handles init for the other feature.
- **tools.test_cash_control_feature_wave_21.FakeCanvas.delete** (method, lines 36–37, 2 lines, risk `support`): Handles delete for the other feature.
- **tools.test_cash_control_feature_wave_21.FakeCanvas.configure** (method, lines 39–40, 2 lines, risk `support`): Handles configure for the other feature.
- **tools.test_cash_control_feature_wave_21.FakeCanvas.winfo_width** (method, lines 42–43, 2 lines, risk `support`): Handles winfo width for the other feature.
- **tools.test_cash_control_feature_wave_21.FakeCanvas.winfo_height** (method, lines 45–46, 2 lines, risk `support`): Handles winfo height for the other feature.
- **tools.test_cash_control_feature_wave_21.FakeCanvas.create_text** (method, lines 48–50, 3 lines, risk `support`): Builds create text for the other feature.
- **tools.test_cash_control_feature_wave_21.Dummy** (class, lines 53–59, 7 lines, risk `container`): Groups Dummy for the other feature.
- **tools.test_cash_control_feature_wave_21.Dummy.__init__** (method, lines 56–59, 4 lines, risk `support`): Handles init for the other feature.
- **tools.test_cash_control_feature_wave_21.main** (function, lines 62–117, 56 lines, risk `filesystem`): Handles main for the other feature.
- **tools.test_cash_control_feature_wave_21.main.log_exc** (nested_function, lines 77–78, 2 lines, risk `support`): Handles log exc for the other feature.
- **tools.test_cash_control_feature_wave_21.main.money_short** (nested_function, lines 80–81, 2 lines, risk `support`): Handles money short for the other feature.
- **tools.test_cash_control_feature_wave_21.main.round_rect** (nested_function, lines 83–85, 3 lines, risk `support`): Handles round rect for the other feature.

## `tools/test_cash_control_input_normalizer_batch_07.py`

- **tools.test_cash_control_input_normalizer_batch_07._load** (function, lines 56–57, 2 lines, risk `filesystem`): Handles load for the other feature.
- **tools.test_cash_control_input_normalizer_batch_07._functions** (function, lines 60–83, 24 lines, risk `filesystem`): Handles functions for the other feature.
- **tools.test_cash_control_input_normalizer_batch_07._capture** (function, lines 86–99, 14 lines, risk `support`): Handles capture for the other feature.
- **tools.test_cash_control_input_normalizer_batch_07.capture** (function, lines 102–116, 15 lines, risk `support`): Handles capture for the other feature.
- **tools.test_cash_control_input_normalizer_batch_07.main** (function, lines 119–136, 18 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_cash_control_ui_controls_batch_09.py`

- **tools.test_cash_control_ui_controls_batch_09.FakeWidget** (class, lines 34–45, 12 lines, risk `container`): Groups FakeWidget for the other feature.
- **tools.test_cash_control_ui_controls_batch_09.FakeWidget.__init__** (method, lines 35–42, 8 lines, risk `support`): Handles init for the other feature.
- **tools.test_cash_control_ui_controls_batch_09.FakeWidget.pack** (method, lines 44–45, 2 lines, risk `support`): Handles pack for the other feature.
- **tools.test_cash_control_ui_controls_batch_09._WidgetFactory** (class, lines 48–53, 6 lines, risk `container`): Groups WidgetFactory for the other feature.
- **tools.test_cash_control_ui_controls_batch_09._WidgetFactory.__init__** (method, lines 49–50, 2 lines, risk `support`): Handles init for the other feature.
- **tools.test_cash_control_ui_controls_batch_09._WidgetFactory.__call__** (method, lines 52–53, 2 lines, risk `support`): Handles call for the other feature.
- **tools.test_cash_control_ui_controls_batch_09.FakeTk** (class, lines 56–58, 3 lines, risk `container`): Groups FakeTk for the other feature.
- **tools.test_cash_control_ui_controls_batch_09.FakeStyle** (class, lines 61–70, 10 lines, risk `container`): Groups FakeStyle for the other feature.
- **tools.test_cash_control_ui_controls_batch_09.FakeStyle.__init__** (method, lines 62–64, 3 lines, risk `support`): Handles init for the other feature.
- **tools.test_cash_control_ui_controls_batch_09.FakeStyle.configure** (method, lines 66–67, 2 lines, risk `support`): Handles configure for the other feature.
- **tools.test_cash_control_ui_controls_batch_09.FakeStyle.map** (method, lines 69–70, 2 lines, risk `support`): Handles map for the other feature.
- **tools.test_cash_control_ui_controls_batch_09.FakeTtk** (class, lines 73–84, 12 lines, risk `container`): Groups FakeTtk for the other feature.
- **tools.test_cash_control_ui_controls_batch_09.FakeTtk.Style** (method, lines 79–84, 6 lines, risk `support`): Handles Style for the other feature.
- **tools.test_cash_control_ui_controls_batch_09._cash_palette** (function, lines 90–93, 4 lines, risk `support`): Handles cash palette for the other feature.
- **tools.test_cash_control_ui_controls_batch_09._reset_runtime** (function, lines 96–100, 5 lines, risk `ui_only`): Handles reset runtime for the other feature.
- **tools.test_cash_control_ui_controls_batch_09._load_manifest** (function, lines 103–104, 2 lines, risk `filesystem`): Loads load manifest for the other feature.
- **tools.test_cash_control_ui_controls_batch_09._source_function** (function, lines 107–127, 21 lines, risk `filesystem`): Handles source function for the other feature.
- **tools.test_cash_control_ui_controls_batch_09._resolve_function** (function, lines 130–144, 15 lines, risk `support`): Handles resolve function for the other feature.
- **tools.test_cash_control_ui_controls_batch_09._widget_summary** (function, lines 147–153, 7 lines, risk `support`): Handles widget summary for the other feature.
- **tools.test_cash_control_ui_controls_batch_09._capture_builder** (function, lines 156–185, 30 lines, risk `support`): Handles capture builder for the other feature.
- **tools.test_cash_control_ui_controls_batch_09._capture_style** (function, lines 188–213, 26 lines, risk `ui_only`): Handles capture style for the other feature.
- **tools.test_cash_control_ui_controls_batch_09.capture_batch** (function, lines 216–256, 41 lines, risk `support`): Handles capture batch for the other feature.
- **tools.test_cash_control_ui_controls_batch_09.main** (function, lines 259–295, 37 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_ci_acceleration.py`

- **tools.test_ci_acceleration.exact_head_guard** (function, lines 13–17, 5 lines, risk `support`): Handles exact head guard for the other feature.
- **tools.test_ci_acceleration.main** (function, lines 20–52, 33 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_cilog_action_label_extraction.py`

- **tools.test_cilog_action_label_extraction._cases** (function, lines 20–34, 15 lines, risk `support`): Handles cases for the other feature.
- **tools.test_cilog_action_label_extraction._capture** (function, lines 37–50, 14 lines, risk `support`): Handles capture for the other feature.
- **tools.test_cilog_action_label_extraction._behavior** (function, lines 53–57, 5 lines, risk `support`): Handles behavior for the other feature.
- **tools.test_cilog_action_label_extraction._load** (function, lines 60–66, 7 lines, risk `support`): Handles load for the other feature.
- **tools.test_cilog_action_label_extraction._source_state** (function, lines 69–72, 4 lines, risk `support`): Handles source state for the other feature.
- **tools.test_cilog_action_label_extraction._write_fixture** (function, lines 75–89, 15 lines, risk `filesystem`): Saves write fixture for the other feature.
- **tools.test_cilog_action_label_extraction._original** (function, lines 92–122, 31 lines, risk `filesystem`): Handles original for the other feature.
- **tools.test_cilog_action_label_extraction._applied** (function, lines 125–136, 12 lines, risk `filesystem`): Handles applied for the other feature.
- **tools.test_cilog_action_label_extraction.main** (function, lines 139–157, 19 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_cilog_diff_pairs_extraction.py`

- **tools.test_cilog_diff_pairs_extraction._load_target** (function, lines 17–37, 21 lines, risk `filesystem`): Loads load target for the other feature.
- **tools.test_cilog_diff_pairs_extraction._cases** (function, lines 40–56, 17 lines, risk `support`): Handles cases for the other feature.
- **tools.test_cilog_diff_pairs_extraction._capture** (function, lines 59–79, 21 lines, risk `support`): Handles capture for the other feature.
- **tools.test_cilog_diff_pairs_extraction.main** (function, lines 82–105, 24 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_cilog_money_formatter_extraction.py`

- **tools.test_cilog_money_formatter_extraction._cases** (function, lines 20–34, 15 lines, risk `support`): Handles cases for the other feature.
- **tools.test_cilog_money_formatter_extraction._capture** (function, lines 37–50, 14 lines, risk `support`): Handles capture for the other feature.
- **tools.test_cilog_money_formatter_extraction._behavior** (function, lines 53–57, 5 lines, risk `support`): Handles behavior for the other feature.
- **tools.test_cilog_money_formatter_extraction._state** (function, lines 60–69, 10 lines, risk `support`): Handles state for the other feature.
- **tools.test_cilog_money_formatter_extraction._legacy_function** (function, lines 72–77, 6 lines, risk `support`): Handles legacy function for the other feature.
- **tools.test_cilog_money_formatter_extraction._module_function** (function, lines 80–86, 7 lines, risk `support`): Handles module function for the other feature.
- **tools.test_cilog_money_formatter_extraction._write_fixture** (function, lines 89–103, 15 lines, risk `filesystem`): Saves write fixture for the other feature.
- **tools.test_cilog_money_formatter_extraction.main** (function, lines 106–142, 37 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_cilog_ui_controls_batch_10.py`

- **tools.test_cilog_ui_controls_batch_10.FakeWidget** (class, lines 36–43, 8 lines, risk `container`): Groups FakeWidget for the other feature.
- **tools.test_cilog_ui_controls_batch_10.FakeWidget.__init__** (method, lines 37–43, 7 lines, risk `support`): Handles init for the other feature.
- **tools.test_cilog_ui_controls_batch_10._WidgetFactory** (class, lines 46–51, 6 lines, risk `container`): Groups WidgetFactory for the other feature.
- **tools.test_cilog_ui_controls_batch_10._WidgetFactory.__init__** (method, lines 47–48, 2 lines, risk `support`): Handles init for the other feature.
- **tools.test_cilog_ui_controls_batch_10._WidgetFactory.__call__** (method, lines 50–51, 2 lines, risk `support`): Handles call for the other feature.
- **tools.test_cilog_ui_controls_batch_10.FakeTk** (class, lines 54–55, 2 lines, risk `container`): Groups FakeTk for the other feature.
- **tools.test_cilog_ui_controls_batch_10.FakeStyle** (class, lines 58–67, 10 lines, risk `container`): Groups FakeStyle for the other feature.
- **tools.test_cilog_ui_controls_batch_10.FakeStyle.__init__** (method, lines 59–61, 3 lines, risk `support`): Handles init for the other feature.
- **tools.test_cilog_ui_controls_batch_10.FakeStyle.configure** (method, lines 63–64, 2 lines, risk `support`): Handles configure for the other feature.
- **tools.test_cilog_ui_controls_batch_10.FakeStyle.map** (method, lines 66–67, 2 lines, risk `support`): Handles map for the other feature.
- **tools.test_cilog_ui_controls_batch_10.FakeTtk** (class, lines 70–80, 11 lines, risk `container`): Groups FakeTtk for the other feature.
- **tools.test_cilog_ui_controls_batch_10.FakeTtk.Style** (method, lines 75–80, 6 lines, risk `support`): Handles Style for the other feature.
- **tools.test_cilog_ui_controls_batch_10._cilog_palette** (function, lines 86–89, 4 lines, risk `support`): Handles cilog palette for the clients feature.
- **tools.test_cilog_ui_controls_batch_10._reset_runtime** (function, lines 92–96, 5 lines, risk `ui_only`): Handles reset runtime for the other feature.
- **tools.test_cilog_ui_controls_batch_10._load_manifest** (function, lines 99–100, 2 lines, risk `filesystem`): Loads load manifest for the other feature.
- **tools.test_cilog_ui_controls_batch_10._source_function** (function, lines 103–123, 21 lines, risk `filesystem`): Handles source function for the other feature.
- **tools.test_cilog_ui_controls_batch_10._resolve_function** (function, lines 126–140, 15 lines, risk `support`): Handles resolve function for the other feature.
- **tools.test_cilog_ui_controls_batch_10._widget_summary** (function, lines 143–148, 6 lines, risk `support`): Handles widget summary for the other feature.
- **tools.test_cilog_ui_controls_batch_10._capture_button** (function, lines 151–173, 23 lines, risk `support`): Handles capture button for the other feature.
- **tools.test_cilog_ui_controls_batch_10._capture_style** (function, lines 176–201, 26 lines, risk `ui_only`): Handles capture style for the other feature.
- **tools.test_cilog_ui_controls_batch_10.capture_batch** (function, lines 204–243, 40 lines, risk `support`): Handles capture batch for the other feature.
- **tools.test_cilog_ui_controls_batch_10.main** (function, lines 246–282, 37 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_cilog_value_formatter_extraction.py`

- **tools.test_cilog_value_formatter_extraction._cases** (function, lines 28–47, 20 lines, risk `support`): Handles cases for the other feature.
- **tools.test_cilog_value_formatter_extraction._capture** (function, lines 50–63, 14 lines, risk `support`): Handles capture for the other feature.
- **tools.test_cilog_value_formatter_extraction._behavior** (function, lines 66–73, 8 lines, risk `support`): Handles behavior for the other feature.
- **tools.test_cilog_value_formatter_extraction._load_module** (function, lines 76–82, 7 lines, risk `support`): Loads load module for the other feature.
- **tools.test_cilog_value_formatter_extraction._source_state** (function, lines 85–92, 8 lines, risk `support`): Handles source state for the other feature.
- **tools.test_cilog_value_formatter_extraction._write_fixture** (function, lines 95–110, 16 lines, risk `filesystem`): Saves write fixture for the other feature.
- **tools.test_cilog_value_formatter_extraction._legacy_function** (function, lines 113–117, 5 lines, risk `support`): Handles legacy function for the other feature.
- **tools.test_cilog_value_formatter_extraction._test_original** (function, lines 120–148, 29 lines, risk `filesystem`): Handles test original for the other feature.
- **tools.test_cilog_value_formatter_extraction._test_applied** (function, lines 151–166, 16 lines, risk `filesystem`): Handles test applied for the other feature.
- **tools.test_cilog_value_formatter_extraction.main** (function, lines 169–190, 22 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_client_area_uid_sync_phase2.py`

- **tools.test_client_area_uid_sync_phase2.main** (function, lines 9–78, 70 lines, risk `database_write`): Handles main for the other feature.

## `tools/test_client_form_presentation_wave_38.py`

- **tools.test_client_form_presentation_wave_38.normalized** (function, lines 18–19, 2 lines, risk `support`): Handles normalized for the utilities feature.
- **tools.test_client_form_presentation_wave_38.call_chain** (function, lines 22–29, 8 lines, risk `support`): Handles call chain for the other feature.
- **tools.test_client_form_presentation_wave_38.main** (function, lines 32–61, 30 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_client_history_presentation_wave_36.py`

- **tools.test_client_history_presentation_wave_36.normalized** (function, lines 19–20, 2 lines, risk `support`): Handles normalized for the utilities feature.
- **tools.test_client_history_presentation_wave_36.digest** (function, lines 23–24, 2 lines, risk `support`): Handles digest for the other feature.
- **tools.test_client_history_presentation_wave_36.call_chain** (function, lines 27–34, 8 lines, risk `support`): Handles call chain for the other feature.
- **tools.test_client_history_presentation_wave_36.main** (function, lines 37–91, 55 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_client_info_logs_feature_wave_20.py`

- **tools.test_client_info_logs_feature_wave_20.defs** (function, lines 15–23, 9 lines, risk `filesystem`): Handles defs for the other feature.
- **tools.test_client_info_logs_feature_wave_20.FakeVar** (class, lines 26–30, 5 lines, risk `container`): Groups FakeVar for the other feature.
- **tools.test_client_info_logs_feature_wave_20.FakeVar.__init__** (method, lines 27–28, 2 lines, risk `support`): Handles init for the other feature.
- **tools.test_client_info_logs_feature_wave_20.FakeVar.set** (method, lines 29–30, 2 lines, risk `support`): Handles set for the other feature.
- **tools.test_client_info_logs_feature_wave_20.FakeApp** (class, lines 33–40, 8 lines, risk `container`): Groups FakeApp for the other feature.
- **tools.test_client_info_logs_feature_wave_20.FakeApp.__init__** (method, lines 34–38, 5 lines, risk `support`): Handles init for the other feature.
- **tools.test_client_info_logs_feature_wave_20.FakeApp.render_client_info_logs** (method, lines 39–40, 2 lines, risk `support`): Handles render client info logs for the clients feature.
- **tools.test_client_info_logs_feature_wave_20.main** (function, lines 43–102, 60 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_client_read_queries_wave_31.py`

- **tools.test_client_read_queries_wave_31.normalized_source** (function, lines 16–17, 2 lines, risk `support`): Handles normalized source for the utilities feature.
- **tools.test_client_read_queries_wave_31.source_hash** (function, lines 20–21, 2 lines, risk `support`): Handles source hash for the other feature.
- **tools.test_client_read_queries_wave_31.direct_functions** (function, lines 24–29, 6 lines, risk `support`): Handles direct functions for the other feature.
- **tools.test_client_read_queries_wave_31.main** (function, lines 32–97, 66 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_client_route_tree_style_batch_12.py`

- **tools.test_client_route_tree_style_batch_12.FakeStyle** (class, lines 39–48, 10 lines, risk `container`): Groups FakeStyle for the other feature.
- **tools.test_client_route_tree_style_batch_12.FakeStyle.__init__** (method, lines 40–42, 3 lines, risk `support`): Handles init for the other feature.
- **tools.test_client_route_tree_style_batch_12.FakeStyle.configure** (method, lines 44–45, 2 lines, risk `support`): Handles configure for the other feature.
- **tools.test_client_route_tree_style_batch_12.FakeStyle.map** (method, lines 47–48, 2 lines, risk `support`): Handles map for the other feature.
- **tools.test_client_route_tree_style_batch_12.FakeTtk** (class, lines 51–61, 11 lines, risk `container`): Groups FakeTtk for the other feature.
- **tools.test_client_route_tree_style_batch_12.FakeTtk.Style** (method, lines 56–61, 6 lines, risk `support`): Handles Style for the other feature.
- **tools.test_client_route_tree_style_batch_12._clients_palette** (function, lines 68–71, 4 lines, risk `support`): Handles clients palette for the clients feature.
- **tools.test_client_route_tree_style_batch_12._route_palette** (function, lines 74–77, 4 lines, risk `support`): Handles route palette for the collectors feature.
- **tools.test_client_route_tree_style_batch_12._reset_runtime** (function, lines 80–90, 11 lines, risk `ui_only`): Handles reset runtime for the other feature.
- **tools.test_client_route_tree_style_batch_12._load_manifest** (function, lines 93–94, 2 lines, risk `filesystem`): Loads load manifest for the other feature.
- **tools.test_client_route_tree_style_batch_12._source_function** (function, lines 97–118, 22 lines, risk `filesystem`): Handles source function for the other feature.
- **tools.test_client_route_tree_style_batch_12._resolve_function** (function, lines 121–135, 15 lines, risk `support`): Handles resolve function for the other feature.
- **tools.test_client_route_tree_style_batch_12._capture_style** (function, lines 138–163, 26 lines, risk `ui_only`): Handles capture style for the other feature.
- **tools.test_client_route_tree_style_batch_12.capture_batch** (function, lines 166–201, 36 lines, risk `support`): Handles capture batch for the other feature.
- **tools.test_client_route_tree_style_batch_12.main** (function, lines 204–241, 38 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_clients_feature_wave_19.py`

- **tools.test_clients_feature_wave_19.defs** (function, lines 14–22, 9 lines, risk `filesystem`): Handles defs for the other feature.
- **tools.test_clients_feature_wave_19.FakeVar** (class, lines 25–31, 7 lines, risk `container`): Groups FakeVar for the other feature.
- **tools.test_clients_feature_wave_19.FakeVar.__init__** (method, lines 26–27, 2 lines, risk `support`): Handles init for the other feature.
- **tools.test_clients_feature_wave_19.FakeVar.get** (method, lines 28–29, 2 lines, risk `support`): Handles get for the other feature.
- **tools.test_clients_feature_wave_19.FakeVar.set** (method, lines 30–31, 2 lines, risk `support`): Handles set for the other feature.
- **tools.test_clients_feature_wave_19.FakeLabel** (class, lines 34–39, 6 lines, risk `container`): Groups FakeLabel for the other feature.
- **tools.test_clients_feature_wave_19.FakeLabel.__init__** (method, lines 35–36, 2 lines, risk `support`): Handles init for the other feature.
- **tools.test_clients_feature_wave_19.FakeLabel.configure** (method, lines 37–39, 3 lines, risk `support`): Handles configure for the other feature.
- **tools.test_clients_feature_wave_19.FakeTree** (class, lines 42–54, 13 lines, risk `container`): Groups FakeTree for the other feature.
- **tools.test_clients_feature_wave_19.FakeTree.__init__** (method, lines 43–44, 2 lines, risk `support`): Handles init for the other feature.
- **tools.test_clients_feature_wave_19.FakeTree.selection** (method, lines 45–46, 2 lines, risk `support`): Handles selection for the other feature.
- **tools.test_clients_feature_wave_19.FakeTree.item** (method, lines 47–52, 6 lines, risk `support`): Handles item for the other feature.
- **tools.test_clients_feature_wave_19.FakeTree.get_children** (method, lines 53–54, 2 lines, risk `support`): Retrieves get children for the other feature.
- **tools.test_clients_feature_wave_19.FakeDB** (class, lines 57–59, 3 lines, risk `container`): Groups FakeDB for the other feature.
- **tools.test_clients_feature_wave_19.FakeDB.get_client_info** (method, lines 58–59, 2 lines, risk `support`): Retrieves get client info for the clients feature.
- **tools.test_clients_feature_wave_19.FakeApp** (class, lines 62–71, 10 lines, risk `container`): Groups FakeApp for the other feature.
- **tools.test_clients_feature_wave_19.FakeApp.__init__** (method, lines 63–69, 7 lines, risk `support`): Handles init for the other feature.
- **tools.test_clients_feature_wave_19.FakeApp._mode_filter** (method, lines 70–71, 2 lines, risk `support`): Handles mode filter for the other feature.
- **tools.test_clients_feature_wave_19.main** (function, lines 74–125, 52 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_clients_read_presentation_wave_30.py`

- **tools.test_clients_read_presentation_wave_30.top_level_functions** (function, lines 34–43, 10 lines, risk `filesystem`): Handles top level functions for the other feature.
- **tools.test_clients_read_presentation_wave_30.source_hash** (function, lines 46–47, 2 lines, risk `support`): Handles source hash for the other feature.
- **tools.test_clients_read_presentation_wave_30.import_lines** (function, lines 50–59, 10 lines, risk `support`): Handles import lines for the other feature.
- **tools.test_clients_read_presentation_wave_30.runtime_reference_lines** (function, lines 62–76, 15 lines, risk `support`): Handles runtime reference lines for the other feature.
- **tools.test_clients_read_presentation_wave_30.assert_exact_extraction** (function, lines 79–108, 30 lines, risk `support`): Handles assert exact extraction for the other feature.
- **tools.test_clients_read_presentation_wave_30.assert_runtime_wiring_order** (function, lines 111–139, 29 lines, risk `filesystem`): Handles assert runtime wiring order for the other feature.
- **tools.test_clients_read_presentation_wave_30.assert_focused_behavior** (function, lines 142–194, 53 lines, risk `support`): Handles assert focused behavior for the other feature.
- **tools.test_clients_read_presentation_wave_30.main** (function, lines 197–201, 5 lines, risk `reports`): Handles main for the other feature.

## `tools/test_collector_dialog_presentation_wave_43.py`

- **tools.test_collector_dialog_presentation_wave_43.normalized** (function, lines 25–26, 2 lines, risk `support`): Handles normalized for the utilities feature.
- **tools.test_collector_dialog_presentation_wave_43.chain** (function, lines 29–36, 8 lines, risk `support`): Handles chain for the other feature.
- **tools.test_collector_dialog_presentation_wave_43.call_name** (function, lines 39–40, 2 lines, risk `support`): Handles call name for the other feature.
- **tools.test_collector_dialog_presentation_wave_43.source_for** (function, lines 43–44, 2 lines, risk `support`): Handles source for for the other feature.
- **tools.test_collector_dialog_presentation_wave_43.main** (function, lines 47–115, 69 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_collector_refresh_presentation_wave_39.py`

- **tools.test_collector_refresh_presentation_wave_39.normalized** (function, lines 21–22, 2 lines, risk `support`): Handles normalized for the utilities feature.
- **tools.test_collector_refresh_presentation_wave_39.call_chain** (function, lines 25–32, 8 lines, risk `support`): Handles call chain for the other feature.
- **tools.test_collector_refresh_presentation_wave_39.main** (function, lines 35–90, 56 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_collector_route_card_batch_13.py`

- **tools.test_collector_route_card_batch_13.FakeWidget** (class, lines 40–51, 12 lines, risk `container`): Groups FakeWidget for the other feature.
- **tools.test_collector_route_card_batch_13.FakeWidget.__init__** (method, lines 41–48, 8 lines, risk `support`): Handles init for the other feature.
- **tools.test_collector_route_card_batch_13.FakeWidget.pack** (method, lines 50–51, 2 lines, risk `support`): Handles pack for the other feature.
- **tools.test_collector_route_card_batch_13._WidgetFactory** (class, lines 54–59, 6 lines, risk `container`): Groups WidgetFactory for the other feature.
- **tools.test_collector_route_card_batch_13._WidgetFactory.__init__** (method, lines 55–56, 2 lines, risk `support`): Handles init for the other feature.
- **tools.test_collector_route_card_batch_13._WidgetFactory.__call__** (method, lines 58–59, 2 lines, risk `support`): Handles call for the other feature.
- **tools.test_collector_route_card_batch_13.FakeTk** (class, lines 62–64, 3 lines, risk `container`): Groups FakeTk for the other feature.
- **tools.test_collector_route_card_batch_13._route_palette** (function, lines 70–73, 4 lines, risk `support`): Handles route palette for the collectors feature.
- **tools.test_collector_route_card_batch_13._load_manifest** (function, lines 76–77, 2 lines, risk `filesystem`): Loads load manifest for the other feature.
- **tools.test_collector_route_card_batch_13._source_function** (function, lines 80–99, 20 lines, risk `filesystem`): Handles source function for the other feature.
- **tools.test_collector_route_card_batch_13._resolve_function** (function, lines 102–115, 14 lines, risk `support`): Handles resolve function for the other feature.
- **tools.test_collector_route_card_batch_13._widget_summary** (function, lines 118–124, 7 lines, risk `support`): Handles widget summary for the other feature.
- **tools.test_collector_route_card_batch_13._capture** (function, lines 127–161, 35 lines, risk `support`): Handles capture for the other feature.
- **tools.test_collector_route_card_batch_13.capture_batch** (function, lines 164–180, 17 lines, risk `support`): Handles capture batch for the other feature.
- **tools.test_collector_route_card_batch_13.main** (function, lines 183–216, 34 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_collector_route_presentation_wave_23.py`

- **tools.test_collector_route_presentation_wave_23.source_for** (function, lines 24–25, 2 lines, risk `support`): Handles source for for the other feature.
- **tools.test_collector_route_presentation_wave_23.main** (function, lines 28–80, 53 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_collector_tab_presentation_wave_44.py`

- **tools.test_collector_tab_presentation_wave_44.normalized** (function, lines 24–25, 2 lines, risk `support`): Handles normalized for the utilities feature.
- **tools.test_collector_tab_presentation_wave_44.dotted** (function, lines 28–34, 7 lines, risk `support`): Handles dotted for the other feature.
- **tools.test_collector_tab_presentation_wave_44.top_functions** (function, lines 37–38, 2 lines, risk `support`): Handles top functions for the other feature.
- **tools.test_collector_tab_presentation_wave_44.source_for** (function, lines 41–42, 2 lines, risk `support`): Handles source for for the other feature.
- **tools.test_collector_tab_presentation_wave_44.signature_text** (function, lines 45–51, 7 lines, risk `support`): Handles signature text for the other feature.
- **tools.test_collector_tab_presentation_wave_44.main** (function, lines 54–132, 79 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_collector_tab_widget_smoke_wave_44.py`

- **tools.test_collector_tab_widget_smoke_wave_44._route_colors** (function, lines 32–33, 2 lines, risk `support`): Handles route colors for the collectors feature.
- **tools.test_collector_tab_widget_smoke_wave_44._route_button** (function, lines 36–38, 3 lines, risk `ui_only`): Handles route button for the collectors feature.
- **tools.test_collector_tab_widget_smoke_wave_44._route_card** (function, lines 41–50, 10 lines, risk `ui_only`): Handles route card for the collectors feature.
- **tools.test_collector_tab_widget_smoke_wave_44._style_route_trees** (function, lines 53–55, 3 lines, risk `ui_only`): Handles style route trees for the collectors feature.
- **tools.test_collector_tab_widget_smoke_wave_44._hidden_widgets** (function, lines 58–61, 4 lines, risk `ui_only`): Handles hidden widgets for the other feature.
- **tools.test_collector_tab_widget_smoke_wave_44._update_cards** (function, lines 64–74, 11 lines, risk `ui_only`): Updates update cards for the other feature.
- **tools.test_collector_tab_widget_smoke_wave_44.FakeCollectorApp** (class, lines 77–130, 54 lines, risk `container`): Groups FakeCollectorApp for the collectors feature.
- **tools.test_collector_tab_widget_smoke_wave_44.FakeCollectorApp.__init__** (method, lines 78–82, 5 lines, risk `ui_only`): Handles init for the collectors feature.
- **tools.test_collector_tab_widget_smoke_wave_44.FakeCollectorApp._record** (method, lines 84–85, 2 lines, risk `support`): Handles record for the collectors feature.
- **tools.test_collector_tab_widget_smoke_wave_44.FakeCollectorApp.print_collector_route_daily_ledger** (method, lines 87–88, 2 lines, risk `reports`): Generates print collector route daily ledger for the collectors feature.
- **tools.test_collector_tab_widget_smoke_wave_44.FakeCollectorApp._edit_selected_collector** (method, lines 90–91, 2 lines, risk `support`): Handles edit selected collector for the collectors feature.
- **tools.test_collector_tab_widget_smoke_wave_44.FakeCollectorApp._add_collector** (method, lines 93–94, 2 lines, risk `support`): Handles add collector for the collectors feature.
- **tools.test_collector_tab_widget_smoke_wave_44.FakeCollectorApp._clear_collectors_search_filters** (method, lines 96–99, 4 lines, risk `support`): Handles clear collectors search filters for the collectors feature.
- **tools.test_collector_tab_widget_smoke_wave_44.FakeCollectorApp._show_unassigned_areas** (method, lines 101–102, 2 lines, risk `support`): Handles show unassigned areas for the collectors feature.
- **tools.test_collector_tab_widget_smoke_wave_44.FakeCollectorApp._show_no_area_clients** (method, lines 104–105, 2 lines, risk `support`): Handles show no area clients for the clients feature.
- **tools.test_collector_tab_widget_smoke_wave_44.FakeCollectorApp._show_conflicts** (method, lines 107–108, 2 lines, risk `support`): Handles show conflicts for the collectors feature.
- **tools.test_collector_tab_widget_smoke_wave_44.FakeCollectorApp._delete_selected_collector** (method, lines 110–111, 2 lines, risk `support`): Removes delete selected collector for the collectors feature.
- **tools.test_collector_tab_widget_smoke_wave_44.FakeCollectorApp._collectors_name_from_values** (method, lines 113–114, 2 lines, risk `support`): Handles collectors name from values for the collectors feature.
- **tools.test_collector_tab_widget_smoke_wave_44.FakeCollectorApp._schedule_collectors_refresh** (method, lines 116–117, 2 lines, risk `support`): Handles schedule collectors refresh for the collectors feature.
- **tools.test_collector_tab_widget_smoke_wave_44.FakeCollectorApp.refresh_collectors** (method, lines 119–130, 12 lines, risk `support`): Refreshes refresh collectors for the collectors feature.
- **tools.test_collector_tab_widget_smoke_wave_44.main** (function, lines 133–202, 70 lines, risk `reports`): Handles main for the other feature.

## `tools/test_collectors_editor_wave_26.py`

- **tools.test_collectors_editor_wave_26.sha256_text** (function, lines 19–20, 2 lines, risk `support`): Handles sha256 text for the other feature.
- **tools.test_collectors_editor_wave_26.source_for** (function, lines 23–24, 2 lines, risk `support`): Handles source for for the other feature.
- **tools.test_collectors_editor_wave_26.nodes** (function, lines 27–33, 7 lines, risk `support`): Handles nodes for the other feature.
- **tools.test_collectors_editor_wave_26.Var** (class, lines 36–42, 7 lines, risk `container`): Groups Var for the other feature.
- **tools.test_collectors_editor_wave_26.Var.__init__** (method, lines 37–38, 2 lines, risk `support`): Handles init for the other feature.
- **tools.test_collectors_editor_wave_26.Var.get** (method, lines 39–40, 2 lines, risk `support`): Handles get for the other feature.
- **tools.test_collectors_editor_wave_26.Var.set** (method, lines 41–42, 2 lines, risk `support`): Handles set for the other feature.
- **tools.test_collectors_editor_wave_26.Widget** (class, lines 45–62, 18 lines, risk `container`): Groups Widget for the other feature.
- **tools.test_collectors_editor_wave_26.Widget.__init__** (method, lines 46–48, 3 lines, risk `support`): Handles init for the other feature.
- **tools.test_collectors_editor_wave_26.Widget.pack** (method, lines 49–51, 3 lines, risk `support`): Handles pack for the other feature.
- **tools.test_collectors_editor_wave_26.Widget.pack_forget** (method, lines 52–53, 2 lines, risk `support`): Handles pack forget for the other feature.
- **tools.test_collectors_editor_wave_26.Widget.grid** (method, lines 54–56, 3 lines, risk `support`): Handles grid for the other feature.
- **tools.test_collectors_editor_wave_26.Widget.grid_remove** (method, lines 57–58, 2 lines, risk `support`): Handles grid remove for the other feature.
- **tools.test_collectors_editor_wave_26.Widget.winfo_ismapped** (method, lines 59–60, 2 lines, risk `support`): Handles winfo ismapped for the other feature.
- **tools.test_collectors_editor_wave_26.Widget.configure** (method, lines 61–62, 2 lines, risk `support`): Handles configure for the other feature.
- **tools.test_collectors_editor_wave_26.FakeTree** (class, lines 65–85, 21 lines, risk `container`): Groups FakeTree for the other feature.
- **tools.test_collectors_editor_wave_26.FakeTree.__init__** (method, lines 66–73, 8 lines, risk `support`): Handles init for the other feature.
- **tools.test_collectors_editor_wave_26.FakeTree.selection** (method, lines 74–75, 2 lines, risk `support`): Handles selection for the other feature.
- **tools.test_collectors_editor_wave_26.FakeTree.focus** (method, lines 76–77, 2 lines, risk `support`): Handles focus for the other feature.
- **tools.test_collectors_editor_wave_26.FakeTree.get_children** (method, lines 78–79, 2 lines, risk `support`): Retrieves get children for the other feature.
- **tools.test_collectors_editor_wave_26.FakeTree.item** (method, lines 80–85, 6 lines, risk `support`): Handles item for the other feature.
- **tools.test_collectors_editor_wave_26.FakeListbox** (class, lines 88–113, 26 lines, risk `container`): Groups FakeListbox for the other feature.
- **tools.test_collectors_editor_wave_26.FakeListbox.__init__** (method, lines 89–91, 3 lines, risk `support`): Handles init for the other feature.
- **tools.test_collectors_editor_wave_26.FakeListbox.size** (method, lines 92–93, 2 lines, risk `support`): Handles size for the other feature.
- **tools.test_collectors_editor_wave_26.FakeListbox.get** (method, lines 94–95, 2 lines, risk `support`): Handles get for the other feature.
- **tools.test_collectors_editor_wave_26.FakeListbox.insert** (method, lines 96–100, 5 lines, risk `support`): Handles insert for the other feature.
- **tools.test_collectors_editor_wave_26.FakeListbox.delete** (method, lines 101–107, 7 lines, risk `support`): Handles delete for the other feature.
- **tools.test_collectors_editor_wave_26.FakeListbox.curselection** (method, lines 108–109, 2 lines, risk `support`): Handles curselection for the other feature.
- **tools.test_collectors_editor_wave_26.FakeListbox.selection_clear** (method, lines 110–111, 2 lines, risk `support`): Handles selection clear for the other feature.
- **tools.test_collectors_editor_wave_26.FakeListbox.selection_set** (method, lines 112–113, 2 lines, risk `support`): Handles selection set for the other feature.
- **tools.test_collectors_editor_wave_26.FakeText** (class, lines 116–122, 7 lines, risk `container`): Groups FakeText for the other feature.
- **tools.test_collectors_editor_wave_26.FakeText.__init__** (method, lines 117–118, 2 lines, risk `support`): Handles init for the other feature.
- **tools.test_collectors_editor_wave_26.FakeText.delete** (method, lines 119–120, 2 lines, risk `support`): Handles delete for the other feature.
- **tools.test_collectors_editor_wave_26.FakeText.insert** (method, lines 121–122, 2 lines, risk `support`): Handles insert for the other feature.
- **tools.test_collectors_editor_wave_26.Dummy** (class, lines 125–126, 2 lines, risk `container`): Groups Dummy for the other feature.
- **tools.test_collectors_editor_wave_26.bind** (function, lines 129–135, 7 lines, risk `support`): Handles bind for the other feature.
- **tools.test_collectors_editor_wave_26.static_checks** (function, lines 138–166, 29 lines, risk `filesystem`): Handles static checks for the other feature.
- **tools.test_collectors_editor_wave_26.behavior_checks** (function, lines 169–245, 77 lines, risk `ui_only`): Handles behavior checks for the other feature.
- **tools.test_collectors_editor_wave_26.main** (function, lines 248–252, 5 lines, risk `reports`): Handles main for the other feature.

## `tools/test_collectors_summary_wave_22.py`

- **tools.test_collectors_summary_wave_22.source_for** (function, lines 19–20, 2 lines, risk `support`): Handles source for for the other feature.
- **tools.test_collectors_summary_wave_22.main** (function, lines 23–61, 39 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_dashboard_chart_presentation_wave_51.py`

- **tools.test_dashboard_chart_presentation_wave_51.normalized** (function, lines 72–73, 2 lines, risk `support`): Handles normalized for the utilities feature.
- **tools.test_dashboard_chart_presentation_wave_51.source_hash** (function, lines 76–77, 2 lines, risk `support`): Handles source hash for the other feature.
- **tools.test_dashboard_chart_presentation_wave_51.dotted** (function, lines 80–86, 7 lines, risk `support`): Handles dotted for the other feature.
- **tools.test_dashboard_chart_presentation_wave_51.top_functions** (function, lines 89–90, 2 lines, risk `support`): Handles top functions for the other feature.
- **tools.test_dashboard_chart_presentation_wave_51.source_for** (function, lines 93–96, 4 lines, risk `support`): Handles source for for the other feature.
- **tools.test_dashboard_chart_presentation_wave_51.calls_for** (function, lines 99–104, 6 lines, risk `support`): Handles calls for for the other feature.
- **tools.test_dashboard_chart_presentation_wave_51.verify_bridge_sources** (function, lines 107–114, 8 lines, risk `filesystem`): Handles verify bridge sources for the other feature.
- **tools.test_dashboard_chart_presentation_wave_51.main** (function, lines 117–197, 81 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_dashboard_chart_widget_smoke_wave_51.py`

- **tools.test_dashboard_chart_widget_smoke_wave_51.round_rect** (function, lines 27–29, 3 lines, risk `support`): Handles round rect for the other feature.
- **tools.test_dashboard_chart_widget_smoke_wave_51.FakeApp** (class, lines 32–33, 2 lines, risk `container`): Groups FakeApp for the other feature.
- **tools.test_dashboard_chart_widget_smoke_wave_51.chart_frame** (function, lines 36–43, 8 lines, risk `ui_only`): Handles chart frame for the other feature.
- **tools.test_dashboard_chart_widget_smoke_wave_51.main** (function, lines 46–129, 84 lines, risk `reports`): Handles main for the other feature.

## `tools/test_dashboard_feature_wave_17.py`

- **tools.test_dashboard_feature_wave_17.Var** (class, lines 22–30, 9 lines, risk `container`): Groups Var for the other feature.
- **tools.test_dashboard_feature_wave_17.Var.__init__** (method, lines 23–24, 2 lines, risk `support`): Handles init for the other feature.
- **tools.test_dashboard_feature_wave_17.Var.get** (method, lines 26–27, 2 lines, risk `support`): Handles get for the other feature.
- **tools.test_dashboard_feature_wave_17.Var.set** (method, lines 29–30, 2 lines, risk `support`): Handles set for the other feature.
- **tools.test_dashboard_feature_wave_17._functions** (function, lines 33–40, 8 lines, risk `filesystem`): Handles functions for the other feature.
- **tools.test_dashboard_feature_wave_17.verify_static_extraction** (function, lines 43–70, 28 lines, risk `filesystem`): Handles verify static extraction for the other feature.
- **tools.test_dashboard_feature_wave_17.verify_visible_rows** (function, lines 73–97, 25 lines, risk `ui_only`): Handles verify visible rows for the other feature.
- **tools.test_dashboard_feature_wave_17.verify_refresh_bridge** (function, lines 100–125, 26 lines, risk `support`): Handles verify refresh bridge for the other feature.
- **tools.test_dashboard_feature_wave_17.main** (function, lines 128–134, 7 lines, risk `reports`): Handles main for the other feature.

## `tools/test_dashboard_presentation_wave_28.py`

- **tools.test_dashboard_presentation_wave_28.functions** (function, lines 20–29, 10 lines, risk `filesystem`): Handles functions for the other feature.
- **tools.test_dashboard_presentation_wave_28.assert_dashboard_startup_wiring** (function, lines 33–62, 30 lines, risk `filesystem`): Handles assert dashboard startup wiring for the dashboard feature.
- **tools.test_dashboard_presentation_wave_28.FakeNotebook** (class, lines 65–87, 23 lines, risk `container`): Groups FakeNotebook for the notes feature.
- **tools.test_dashboard_presentation_wave_28.FakeNotebook.__init__** (method, lines 66–68, 3 lines, risk `support`): Handles init for the notes feature.
- **tools.test_dashboard_presentation_wave_28.FakeNotebook.tabs** (method, lines 70–71, 2 lines, risk `support`): Handles tabs for the notes feature.
- **tools.test_dashboard_presentation_wave_28.FakeNotebook.insert** (method, lines 73–76, 4 lines, risk `support`): Handles insert for the notes feature.
- **tools.test_dashboard_presentation_wave_28.FakeNotebook.add** (method, lines 78–81, 4 lines, risk `support`): Handles add for the notes feature.
- **tools.test_dashboard_presentation_wave_28.FakeNotebook.hide** (method, lines 83–87, 5 lines, risk `filesystem`): Handles hide for the notes feature.
- **tools.test_dashboard_presentation_wave_28.assert_dashboard_role_visibility** (function, lines 90–104, 15 lines, risk `support`): Handles assert dashboard role visibility for the dashboard feature.
- **tools.test_dashboard_presentation_wave_28.main** (function, lines 107–146, 40 lines, risk `reports`): Handles main for the other feature.

## `tools/test_dashboard_visibility_wave_24.py`

- **tools.test_dashboard_visibility_wave_24.source_for** (function, lines 17–18, 2 lines, risk `support`): Handles source for for the other feature.
- **tools.test_dashboard_visibility_wave_24.Var** (class, lines 21–26, 6 lines, risk `container`): Groups Var for the other feature.
- **tools.test_dashboard_visibility_wave_24.Var.__init__** (method, lines 22–23, 2 lines, risk `support`): Handles init for the other feature.
- **tools.test_dashboard_visibility_wave_24.Var.get** (method, lines 25–26, 2 lines, risk `support`): Handles get for the other feature.
- **tools.test_dashboard_visibility_wave_24.Dummy** (class, lines 29–30, 2 lines, risk `container`): Groups Dummy for the other feature.
- **tools.test_dashboard_visibility_wave_24.sample_rows** (function, lines 33–38, 6 lines, risk `support`): Handles sample rows for the other feature.
- **tools.test_dashboard_visibility_wave_24.make_dummy** (function, lines 41–47, 7 lines, risk `support`): Handles make dummy for the other feature.
- **tools.test_dashboard_visibility_wave_24.main** (function, lines 50–109, 60 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_databank_import_control_wave_53.py`

- **tools.test_databank_import_control_wave_53.walk** (function, lines 19–22, 4 lines, risk `support`): Handles walk for the other feature.
- **tools.test_databank_import_control_wave_53.buttons_with_text** (function, lines 25–33, 9 lines, risk `ui_only`): Handles buttons with text for the other feature.
- **tools.test_databank_import_control_wave_53.static_checks** (function, lines 36–76, 41 lines, risk `backup`): Handles static checks for the other feature.
- **tools.test_databank_import_control_wave_53.widget_checks** (function, lines 79–111, 33 lines, risk `reports`): Handles widget checks for the other feature.
- **tools.test_databank_import_control_wave_53.main** (function, lines 114–116, 3 lines, risk `support`): Handles main for the other feature.

## `tools/test_databank_presentation_wave_49.py`

- **tools.test_databank_presentation_wave_49.dotted** (function, lines 104–110, 7 lines, risk `support`): Handles dotted for the other feature.
- **tools.test_databank_presentation_wave_49.source_for** (function, lines 113–115, 3 lines, risk `support`): Handles source for for the other feature.
- **tools.test_databank_presentation_wave_49.normalized** (function, lines 118–119, 2 lines, risk `support`): Handles normalized for the utilities feature.
- **tools.test_databank_presentation_wave_49.source_hash** (function, lines 122–123, 2 lines, risk `support`): Handles source hash for the other feature.
- **tools.test_databank_presentation_wave_49.functions** (function, lines 126–127, 2 lines, risk `support`): Handles functions for the other feature.
- **tools.test_databank_presentation_wave_49.capture_node** (function, lines 130–149, 20 lines, risk `support`): Handles capture node for the other feature.
- **tools.test_databank_presentation_wave_49.binding_nodes** (function, lines 152–167, 16 lines, risk `support`): Handles binding nodes for the other feature.
- **tools.test_databank_presentation_wave_49.assert_presentation_only** (function, lines 170–179, 10 lines, risk `support`): Handles assert presentation only for the other feature.
- **tools.test_databank_presentation_wave_49.FakeVar** (class, lines 182–188, 7 lines, risk `container`): Groups FakeVar for the other feature.
- **tools.test_databank_presentation_wave_49.FakeVar.__init__** (method, lines 183–184, 2 lines, risk `support`): Handles init for the other feature.
- **tools.test_databank_presentation_wave_49.FakeVar.get** (method, lines 185–186, 2 lines, risk `support`): Handles get for the other feature.
- **tools.test_databank_presentation_wave_49.FakeVar.set** (method, lines 187–188, 2 lines, risk `support`): Handles set for the other feature.
- **tools.test_databank_presentation_wave_49.FakeTree** (class, lines 191–198, 8 lines, risk `container`): Groups FakeTree for the other feature.
- **tools.test_databank_presentation_wave_49.FakeTree.__init__** (method, lines 192–193, 2 lines, risk `support`): Handles init for the other feature.
- **tools.test_databank_presentation_wave_49.FakeTree.get_children** (method, lines 194–195, 2 lines, risk `support`): Retrieves get children for the other feature.
- **tools.test_databank_presentation_wave_49.FakeTree.item** (method, lines 196–198, 3 lines, risk `support`): Handles item for the other feature.
- **tools.test_databank_presentation_wave_49.main** (function, lines 201–365, 165 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_databank_widget_smoke_wave_49.py`

- **tools.test_databank_widget_smoke_wave_49.widget_texts** (function, lines 15–25, 11 lines, risk `support`): Handles widget texts for the other feature.
- **tools.test_databank_widget_smoke_wave_49.DummyApp** (class, lines 28–103, 76 lines, risk `container`): Groups DummyApp for the other feature.
- **tools.test_databank_widget_smoke_wave_49.DummyApp.__init__** (method, lines 29–44, 16 lines, risk `ui_only`): Handles init for the other feature.
- **tools.test_databank_widget_smoke_wave_49.DummyApp._theme_palette** (method, lines 46–47, 2 lines, risk `support`): Handles theme palette for the settings feature.
- **tools.test_databank_widget_smoke_wave_49.DummyApp._month_label** (method, lines 49–50, 2 lines, risk `support`): Handles month label for the navigation feature.
- **tools.test_databank_widget_smoke_wave_49.DummyApp._mode_filter** (method, lines 52–53, 2 lines, risk `support`): Handles mode filter for the other feature.
- **tools.test_databank_widget_smoke_wave_49.DummyApp.prev_month** (method, lines 55–56, 2 lines, risk `support`): Handles prev month for the other feature.
- **tools.test_databank_widget_smoke_wave_49.DummyApp.goto_current_month** (method, lines 58–59, 2 lines, risk `support`): Handles goto current month for the other feature.
- **tools.test_databank_widget_smoke_wave_49.DummyApp.next_month** (method, lines 61–62, 2 lines, risk `support`): Handles next month for the other feature.
- **tools.test_databank_widget_smoke_wave_49.DummyApp.open_databank_close_dialog** (method, lines 64–65, 2 lines, risk `support`): Handles open databank close dialog for the data bank feature.
- **tools.test_databank_widget_smoke_wave_49.DummyApp.open_delete_day_dialog** (method, lines 67–68, 2 lines, risk `support`): Handles open delete day dialog for the data bank feature.
- **tools.test_databank_widget_smoke_wave_49.DummyApp.open_databank_close_records_dialog** (method, lines 70–71, 2 lines, risk `support`): Handles open databank close records dialog for the data bank feature.
- **tools.test_databank_widget_smoke_wave_49.DummyApp.refresh_data_grid** (method, lines 73–100, 28 lines, risk `ui_only`): Refreshes refresh data grid for the data bank feature.
- **tools.test_databank_widget_smoke_wave_49.DummyApp._update_data_toolbar** (method, lines 102–103, 2 lines, risk `support`): Updates update data toolbar for the navigation feature.
- **tools.test_databank_widget_smoke_wave_49.main** (function, lines 106–177, 72 lines, risk `reports`): Handles main for the other feature.

## `tools/test_date_display_helper_extraction.py`

- **tools.test_date_display_helper_extraction._cases** (function, lines 28–41, 14 lines, risk `support`): Handles cases for the other feature.
- **tools.test_date_display_helper_extraction._validate_signature** (function, lines 44–57, 14 lines, risk `support`): Validates validate signature for the utilities feature.
- **tools.test_date_display_helper_extraction._capture** (function, lines 60–73, 14 lines, risk `support`): Handles capture for the other feature.
- **tools.test_date_display_helper_extraction._behavior** (function, lines 76–84, 9 lines, risk `support`): Handles behavior for the other feature.
- **tools.test_date_display_helper_extraction._load_dates_module** (function, lines 87–93, 7 lines, risk `support`): Loads load dates module for the other feature.
- **tools.test_date_display_helper_extraction._legacy_functions** (function, lines 96–103, 8 lines, risk `support`): Handles legacy functions for the other feature.
- **tools.test_date_display_helper_extraction._generated_functions** (function, lines 106–108, 3 lines, risk `support`): Handles generated functions for the other feature.
- **tools.test_date_display_helper_extraction._source_state** (function, lines 111–119, 9 lines, risk `support`): Handles source state for the other feature.
- **tools.test_date_display_helper_extraction._write_fixture** (function, lines 122–129, 8 lines, risk `filesystem`): Saves write fixture for the other feature.
- **tools.test_date_display_helper_extraction._copy_existing_package** (function, lines 132–145, 14 lines, risk `filesystem`): Handles copy existing package for the other feature.
- **tools.test_date_display_helper_extraction._test_original_state** (function, lines 148–177, 30 lines, risk `filesystem`): Handles test original state for the other feature.
- **tools.test_date_display_helper_extraction._test_applied_state** (function, lines 180–198, 19 lines, risk `filesystem`): Handles test applied state for the other feature.
- **tools.test_date_display_helper_extraction.main** (function, lines 201–228, 28 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_date_helpers_extraction.py`

- **tools.test_date_helpers_extraction._cases** (function, lines 34–47, 14 lines, risk `support`): Handles cases for the other feature.
- **tools.test_date_helpers_extraction._validate_signature** (function, lines 50–70, 21 lines, risk `support`): Validates validate signature for the utilities feature.
- **tools.test_date_helpers_extraction._capture** (function, lines 73–89, 17 lines, risk `support`): Handles capture for the other feature.
- **tools.test_date_helpers_extraction._behavior** (function, lines 92–100, 9 lines, risk `support`): Handles behavior for the other feature.
- **tools.test_date_helpers_extraction._functions_from_module_source** (function, lines 103–106, 4 lines, risk `support`): Handles functions from module source for the other feature.
- **tools.test_date_helpers_extraction._load_generated_functions** (function, lines 109–115, 7 lines, risk `support`): Loads load generated functions for the other feature.
- **tools.test_date_helpers_extraction._source_state** (function, lines 118–126, 9 lines, risk `support`): Handles source state for the other feature.
- **tools.test_date_helpers_extraction._write_fixture** (function, lines 129–139, 11 lines, risk `filesystem`): Saves write fixture for the other feature.
- **tools.test_date_helpers_extraction._test_original_state** (function, lines 142–171, 30 lines, risk `filesystem`): Handles test original state for the other feature.
- **tools.test_date_helpers_extraction._test_applied_state** (function, lines 174–198, 25 lines, risk `filesystem`): Handles test applied state for the other feature.
- **tools.test_date_helpers_extraction.main** (function, lines 201–233, 33 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_display_data_helper_batch.py`

- **tools.test_display_data_helper_batch.PairRow** (class, lines 26–28, 3 lines, risk `container`): Groups PairRow for the other feature.
- **tools.test_display_data_helper_batch.PairRow.__iter__** (method, lines 27–28, 2 lines, risk `support`): Handles iter for the other feature.
- **tools.test_display_data_helper_batch.FlakyKeysRow** (class, lines 31–43, 13 lines, risk `container`): Groups FlakyKeysRow for the other feature.
- **tools.test_display_data_helper_batch.FlakyKeysRow.__init__** (method, lines 32–34, 3 lines, risk `support`): Handles init for the other feature.
- **tools.test_display_data_helper_batch.FlakyKeysRow.keys** (method, lines 36–40, 5 lines, risk `support`): Handles keys for the other feature.
- **tools.test_display_data_helper_batch.FlakyKeysRow.__getitem__** (method, lines 42–43, 2 lines, risk `support`): Handles getitem for the other feature.
- **tools.test_display_data_helper_batch.BadRow** (class, lines 46–54, 9 lines, risk `container`): Groups BadRow for the other feature.
- **tools.test_display_data_helper_batch.BadRow.__iter__** (method, lines 47–48, 2 lines, risk `support`): Handles iter for the other feature.
- **tools.test_display_data_helper_batch.BadRow.keys** (method, lines 50–51, 2 lines, risk `support`): Handles keys for the other feature.
- **tools.test_display_data_helper_batch.BadRow.__getitem__** (method, lines 53–54, 2 lines, risk `support`): Handles getitem for the other feature.
- **tools.test_display_data_helper_batch._load_manifest** (function, lines 114–115, 2 lines, risk `filesystem`): Loads load manifest for the other feature.
- **tools.test_display_data_helper_batch._resolve_from_source** (function, lines 118–134, 17 lines, risk `filesystem`): Handles resolve from source for the other feature.
- **tools.test_display_data_helper_batch._resolve_function** (function, lines 137–147, 11 lines, risk `support`): Handles resolve function for the other feature.
- **tools.test_display_data_helper_batch._type_name** (function, lines 150–152, 3 lines, risk `support`): Handles type name for the other feature.
- **tools.test_display_data_helper_batch._capture** (function, lines 155–168, 14 lines, risk `support`): Handles capture for the other feature.
- **tools.test_display_data_helper_batch.capture_batch** (function, lines 171–193, 23 lines, risk `support`): Handles capture batch for the other feature.
- **tools.test_display_data_helper_batch.main** (function, lines 196–232, 37 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_display_formatter_extraction.py`

- **tools.test_display_formatter_extraction._cases** (function, lines 27–40, 14 lines, risk `support`): Handles cases for the other feature.
- **tools.test_display_formatter_extraction._validate_signature** (function, lines 43–61, 19 lines, risk `support`): Validates validate signature for the utilities feature.
- **tools.test_display_formatter_extraction._capture** (function, lines 64–77, 14 lines, risk `support`): Handles capture for the other feature.
- **tools.test_display_formatter_extraction._behavior** (function, lines 80–88, 9 lines, risk `support`): Handles behavior for the other feature.
- **tools.test_display_formatter_extraction._functions_from_sources** (function, lines 91–95, 5 lines, risk `support`): Handles functions from sources for the other feature.
- **tools.test_display_formatter_extraction._load_module_functions** (function, lines 98–104, 7 lines, risk `support`): Loads load module functions for the other feature.
- **tools.test_display_formatter_extraction._source_state** (function, lines 107–115, 9 lines, risk `support`): Handles source state for the other feature.
- **tools.test_display_formatter_extraction._write_fixture** (function, lines 118–125, 8 lines, risk `filesystem`): Saves write fixture for the other feature.
- **tools.test_display_formatter_extraction._test_original** (function, lines 128–154, 27 lines, risk `filesystem`): Handles test original for the other feature.
- **tools.test_display_formatter_extraction._test_applied** (function, lines 157–171, 15 lines, risk `filesystem`): Handles test applied for the other feature.
- **tools.test_display_formatter_extraction.main** (function, lines 174–200, 27 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_display_ui_helper_batch_04.py`

- **tools.test_display_ui_helper_batch_04.FakeLabel** (class, lines 51–59, 9 lines, risk `container`): Groups FakeLabel for the other feature.
- **tools.test_display_ui_helper_batch_04.FakeLabel.__init__** (method, lines 52–54, 3 lines, risk `support`): Handles init for the other feature.
- **tools.test_display_ui_helper_batch_04.FakeLabel.configure** (method, lines 56–59, 4 lines, risk `support`): Handles configure for the other feature.
- **tools.test_display_ui_helper_batch_04.Holder** (class, lines 62–63, 2 lines, risk `container`): Groups Holder for the other feature.
- **tools.test_display_ui_helper_batch_04._stable** (function, lines 66–73, 8 lines, risk `support`): Handles stable for the other feature.
- **tools.test_display_ui_helper_batch_04._type_name** (function, lines 76–78, 3 lines, risk `support`): Handles type name for the other feature.
- **tools.test_display_ui_helper_batch_04._load_manifest** (function, lines 81–82, 2 lines, risk `filesystem`): Loads load manifest for the other feature.
- **tools.test_display_ui_helper_batch_04._source_namespace** (function, lines 85–91, 7 lines, risk `support`): Handles source namespace for the other feature.
- **tools.test_display_ui_helper_batch_04._resolve_from_source** (function, lines 94–110, 17 lines, risk `filesystem`): Handles resolve from source for the other feature.
- **tools.test_display_ui_helper_batch_04._resolve_function** (function, lines 113–123, 11 lines, risk `support`): Handles resolve function for the other feature.
- **tools.test_display_ui_helper_batch_04._capture_call** (function, lines 126–131, 6 lines, risk `support`): Handles capture call for the other feature.
- **tools.test_display_ui_helper_batch_04._capture_card** (function, lines 134–175, 42 lines, risk `support`): Handles capture card for the other feature.
- **tools.test_display_ui_helper_batch_04.capture_batch** (function, lines 178–217, 40 lines, risk `support`): Handles capture batch for the other feature.
- **tools.test_display_ui_helper_batch_04.main** (function, lines 220–255, 36 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_fmt_currency_extraction.py`

- **tools.test_fmt_currency_extraction._capture** (function, lines 22–30, 9 lines, risk `support`): Handles capture for the other feature.
- **tools.test_fmt_currency_extraction.main** (function, lines 33–42, 10 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_hierarchical_area_storage_phase1.py`

- **tools.test_hierarchical_area_storage_phase1.make_db** (function, lines 24–58, 35 lines, risk `database_write`): Handles make db for the other feature.
- **tools.test_hierarchical_area_storage_phase1.assert_legacy_migration** (function, lines 61–85, 25 lines, risk `database_read`): Handles assert legacy migration for the other feature.
- **tools.test_hierarchical_area_storage_phase1.assert_unlimited_hierarchy** (function, lines 88–123, 36 lines, risk `database_read`): Handles assert unlimited hierarchy for the other feature.
- **tools.test_hierarchical_area_storage_phase1.main** (function, lines 126–131, 6 lines, risk `reports`): Handles main for the other feature.

## `tools/test_hierarchical_area_ui_phase2.py`

- **tools.test_hierarchical_area_ui_phase2.make_db** (function, lines 17–39, 23 lines, risk `support`): Handles make db for the other feature.
- **tools.test_hierarchical_area_ui_phase2.node_paths** (function, lines 42–46, 5 lines, risk `support`): Handles node paths for the other feature.
- **tools.test_hierarchical_area_ui_phase2.main** (function, lines 49–178, 130 lines, risk `database_write`): Handles main for the other feature.

## `tools/test_hierarchical_area_ui_phase2_source.py`

- **tools.test_hierarchical_area_ui_phase2_source.main** (function, lines 13–50, 38 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_import_log_presentation_wave_53.py`

- **tools.test_import_log_presentation_wave_53.normalized** (function, lines 37–38, 2 lines, risk `support`): Handles normalized for the utilities feature.
- **tools.test_import_log_presentation_wave_53.dotted** (function, lines 41–47, 7 lines, risk `support`): Handles dotted for the other feature.
- **tools.test_import_log_presentation_wave_53.desktop_callers** (function, lines 50–76, 27 lines, risk `support`): Handles desktop callers for the other feature.
- **tools.test_import_log_presentation_wave_53.main** (function, lines 79–169, 91 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_import_log_widget_smoke_wave_53.py`

- **tools.test_import_log_widget_smoke_wave_53.descendants** (function, lines 11–16, 6 lines, risk `support`): Handles descendants for the other feature.
- **tools.test_import_log_widget_smoke_wave_53.main** (function, lines 19–129, 111 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_legacy_collector_cleanup_wave_52.py`

- **tools.test_legacy_collector_cleanup_wave_52.normalized** (function, lines 31–32, 2 lines, risk `support`): Handles normalized for the utilities feature.
- **tools.test_legacy_collector_cleanup_wave_52.dotted** (function, lines 35–41, 7 lines, risk `support`): Handles dotted for the other feature.
- **tools.test_legacy_collector_cleanup_wave_52.top_functions** (function, lines 44–45, 2 lines, risk `support`): Handles top functions for the other feature.
- **tools.test_legacy_collector_cleanup_wave_52.build_bindings** (function, lines 48–63, 16 lines, risk `support`): Builds build bindings for the other feature.
- **tools.test_legacy_collector_cleanup_wave_52.main** (function, lines 66–136, 71 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_legacy_dashboard_card_batch_16.py`

- **tools.test_legacy_dashboard_card_batch_16.FakeWidget** (class, lines 40–55, 16 lines, risk `container`): Groups FakeWidget for the other feature.
- **tools.test_legacy_dashboard_card_batch_16.FakeWidget.__init__** (method, lines 41–49, 9 lines, risk `support`): Handles init for the other feature.
- **tools.test_legacy_dashboard_card_batch_16.FakeWidget.pack** (method, lines 51–52, 2 lines, risk `support`): Handles pack for the other feature.
- **tools.test_legacy_dashboard_card_batch_16.FakeWidget.grid_propagate** (method, lines 54–55, 2 lines, risk `support`): Handles grid propagate for the other feature.
- **tools.test_legacy_dashboard_card_batch_16._WidgetFactory** (class, lines 58–63, 6 lines, risk `container`): Groups WidgetFactory for the other feature.
- **tools.test_legacy_dashboard_card_batch_16._WidgetFactory.__init__** (method, lines 59–60, 2 lines, risk `support`): Handles init for the other feature.
- **tools.test_legacy_dashboard_card_batch_16._WidgetFactory.__call__** (method, lines 62–63, 2 lines, risk `support`): Handles call for the other feature.
- **tools.test_legacy_dashboard_card_batch_16.FakeTk** (class, lines 66–68, 3 lines, risk `container`): Groups FakeTk for the other feature.
- **tools.test_legacy_dashboard_card_batch_16._dashboard_palette** (function, lines 74–77, 4 lines, risk `support`): Handles dashboard palette for the dashboard feature.
- **tools.test_legacy_dashboard_card_batch_16._load_manifest** (function, lines 80–81, 2 lines, risk `filesystem`): Loads load manifest for the other feature.
- **tools.test_legacy_dashboard_card_batch_16._source_function** (function, lines 84–104, 21 lines, risk `filesystem`): Handles source function for the other feature.
- **tools.test_legacy_dashboard_card_batch_16._resolve_function** (function, lines 107–120, 14 lines, risk `support`): Handles resolve function for the other feature.
- **tools.test_legacy_dashboard_card_batch_16._widget_summary** (function, lines 123–130, 8 lines, risk `support`): Handles widget summary for the other feature.
- **tools.test_legacy_dashboard_card_batch_16._capture** (function, lines 133–180, 48 lines, risk `support`): Handles capture for the other feature.
- **tools.test_legacy_dashboard_card_batch_16.capture_batch** (function, lines 183–199, 17 lines, risk `support`): Handles capture batch for the other feature.
- **tools.test_legacy_dashboard_card_batch_16.main** (function, lines 202–236, 35 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_legacy_dashboard_controls_batch_15.py`

- **tools.test_legacy_dashboard_controls_batch_15.FakeStringVar** (class, lines 34–39, 6 lines, risk `container`): Groups FakeStringVar for the other feature.
- **tools.test_legacy_dashboard_controls_batch_15.FakeStringVar.__init__** (method, lines 35–36, 2 lines, risk `support`): Handles init for the other feature.
- **tools.test_legacy_dashboard_controls_batch_15.FakeStringVar.get** (method, lines 38–39, 2 lines, risk `support`): Handles get for the other feature.
- **tools.test_legacy_dashboard_controls_batch_15.FakeTk** (class, lines 42–51, 10 lines, risk `container`): Groups FakeTk for the other feature.
- **tools.test_legacy_dashboard_controls_batch_15.FakeTk.StringVar** (method, lines 47–51, 5 lines, risk `ui_only`): Handles StringVar for the other feature.
- **tools.test_legacy_dashboard_controls_batch_15.FakeButton** (class, lines 54–63, 10 lines, risk `container`): Groups FakeButton for the other feature.
- **tools.test_legacy_dashboard_controls_batch_15.FakeButton.__init__** (method, lines 55–58, 4 lines, risk `support`): Handles init for the other feature.
- **tools.test_legacy_dashboard_controls_batch_15.FakeButton.configure** (method, lines 60–63, 4 lines, risk `support`): Handles configure for the other feature.
- **tools.test_legacy_dashboard_controls_batch_15.FakeStyle** (class, lines 66–75, 10 lines, risk `container`): Groups FakeStyle for the other feature.
- **tools.test_legacy_dashboard_controls_batch_15.FakeStyle.__init__** (method, lines 67–69, 3 lines, risk `support`): Handles init for the other feature.
- **tools.test_legacy_dashboard_controls_batch_15.FakeStyle.configure** (method, lines 71–72, 2 lines, risk `support`): Handles configure for the other feature.
- **tools.test_legacy_dashboard_controls_batch_15.FakeStyle.map** (method, lines 74–75, 2 lines, risk `support`): Handles map for the other feature.
- **tools.test_legacy_dashboard_controls_batch_15.FakeTtk** (class, lines 78–88, 11 lines, risk `container`): Groups FakeTtk for the other feature.
- **tools.test_legacy_dashboard_controls_batch_15.FakeTtk.Style** (method, lines 83–88, 6 lines, risk `support`): Handles Style for the other feature.
- **tools.test_legacy_dashboard_controls_batch_15._palette** (function, lines 94–97, 4 lines, risk `support`): Handles palette for the other feature.
- **tools.test_legacy_dashboard_controls_batch_15._reset_runtime** (function, lines 100–111, 12 lines, risk `ui_only`): Handles reset runtime for the other feature.
- **tools.test_legacy_dashboard_controls_batch_15._load_manifest** (function, lines 114–115, 2 lines, risk `filesystem`): Loads load manifest for the other feature.
- **tools.test_legacy_dashboard_controls_batch_15._source_function** (function, lines 118–139, 22 lines, risk `filesystem`): Handles source function for the other feature.
- **tools.test_legacy_dashboard_controls_batch_15._resolve_function** (function, lines 142–156, 15 lines, risk `support`): Handles resolve function for the other feature.
- **tools.test_legacy_dashboard_controls_batch_15._capture_filter** (function, lines 159–193, 35 lines, risk `ui_only`): Handles capture filter for the other feature.
- **tools.test_legacy_dashboard_controls_batch_15._capture_style** (function, lines 196–220, 25 lines, risk `ui_only`): Handles capture style for the other feature.
- **tools.test_legacy_dashboard_controls_batch_15.capture_batch** (function, lines 223–264, 42 lines, risk `support`): Handles capture batch for the other feature.
- **tools.test_legacy_dashboard_controls_batch_15.main** (function, lines 267–304, 38 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_legacy_dashboard_palette_batch_14.py`

- **tools.test_legacy_dashboard_palette_batch_14.Holder** (class, lines 30–33, 4 lines, risk `container`): Groups Holder for the other feature.
- **tools.test_legacy_dashboard_palette_batch_14.Holder.__init__** (method, lines 31–33, 3 lines, risk `support`): Handles init for the other feature.
- **tools.test_legacy_dashboard_palette_batch_14.BadString** (class, lines 36–38, 3 lines, risk `container`): Groups BadString for the other feature.
- **tools.test_legacy_dashboard_palette_batch_14.BadString.__str__** (method, lines 37–38, 2 lines, risk `support`): Handles str for the other feature.
- **tools.test_legacy_dashboard_palette_batch_14._stable** (function, lines 41–48, 8 lines, risk `support`): Handles stable for the other feature.
- **tools.test_legacy_dashboard_palette_batch_14._type_name** (function, lines 51–53, 3 lines, risk `support`): Handles type name for the other feature.
- **tools.test_legacy_dashboard_palette_batch_14._load_manifest** (function, lines 56–57, 2 lines, risk `filesystem`): Loads load manifest for the other feature.
- **tools.test_legacy_dashboard_palette_batch_14._resolve_from_source** (function, lines 60–80, 21 lines, risk `filesystem`): Handles resolve from source for the other feature.
- **tools.test_legacy_dashboard_palette_batch_14._resolve_function** (function, lines 83–93, 11 lines, risk `support`): Handles resolve function for the other feature.
- **tools.test_legacy_dashboard_palette_batch_14._cases** (function, lines 96–109, 14 lines, risk `support`): Handles cases for the other feature.
- **tools.test_legacy_dashboard_palette_batch_14._capture_call** (function, lines 112–125, 14 lines, risk `support`): Handles capture call for the other feature.
- **tools.test_legacy_dashboard_palette_batch_14.capture_batch** (function, lines 128–148, 21 lines, risk `support`): Handles capture batch for the other feature.
- **tools.test_legacy_dashboard_palette_batch_14.main** (function, lines 151–190, 40 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_linked_client_queries_wave_32.py`

- **tools.test_linked_client_queries_wave_32.normalized_source** (function, lines 16–17, 2 lines, risk `support`): Handles normalized source for the utilities feature.
- **tools.test_linked_client_queries_wave_32.source_hash** (function, lines 20–21, 2 lines, risk `support`): Handles source hash for the other feature.
- **tools.test_linked_client_queries_wave_32.direct_functions** (function, lines 24–29, 6 lines, risk `support`): Handles direct functions for the other feature.
- **tools.test_linked_client_queries_wave_32.main** (function, lines 32–97, 66 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_loan_context_queries_wave_33.py`

- **tools.test_loan_context_queries_wave_33.main** (function, lines 8–19, 12 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_log_serialization_helper_extraction.py`

- **tools.test_log_serialization_helper_extraction._cases** (function, lines 20–33, 14 lines, risk `support`): Handles cases for the other feature.
- **tools.test_log_serialization_helper_extraction._capture** (function, lines 36–49, 14 lines, risk `support`): Handles capture for the other feature.
- **tools.test_log_serialization_helper_extraction._behavior** (function, lines 52–56, 5 lines, risk `support`): Handles behavior for the other feature.
- **tools.test_log_serialization_helper_extraction._load_module** (function, lines 59–65, 7 lines, risk `support`): Loads load module for the other feature.
- **tools.test_log_serialization_helper_extraction._source_state** (function, lines 68–72, 5 lines, risk `support`): Handles source state for the other feature.
- **tools.test_log_serialization_helper_extraction._write_fixture** (function, lines 75–89, 15 lines, risk `filesystem`): Saves write fixture for the other feature.
- **tools.test_log_serialization_helper_extraction._original** (function, lines 92–115, 24 lines, risk `filesystem`): Handles original for the other feature.
- **tools.test_log_serialization_helper_extraction._applied** (function, lines 118–129, 12 lines, risk `filesystem`): Handles applied for the other feature.
- **tools.test_log_serialization_helper_extraction.main** (function, lines 132–149, 18 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_login_cancel_startup_wave_46.py`

- **tools.test_login_cancel_startup_wave_46.dotted** (function, lines 12–18, 7 lines, risk `support`): Handles dotted for the other feature.
- **tools.test_login_cancel_startup_wave_46.normalized_hash** (function, lines 21–22, 2 lines, risk `support`): Handles normalized hash for the utilities feature.
- **tools.test_login_cancel_startup_wave_46.main** (function, lines 25–113, 89 lines, risk `authentication`): Handles main for the other feature.
- **tools.test_login_cancel_startup_wave_46.main.base_init** (nested_function, lines 95–97, 3 lines, risk `support`): Handles base init for the other feature.
- **tools.test_login_cancel_startup_wave_46.main.client_logs_wrapper** (nested_function, lines 99–101, 3 lines, risk `support`): Handles client logs wrapper for the clients feature.
- **tools.test_login_cancel_startup_wave_46.main.outer_wrapper** (nested_function, lines 103–105, 3 lines, risk `support`): Handles outer wrapper for the other feature.

## `tools/test_login_dialog_presentation_wave_45.py`

- **tools.test_login_dialog_presentation_wave_45.normalized** (function, lines 28–29, 2 lines, risk `support`): Handles normalized for the utilities feature.
- **tools.test_login_dialog_presentation_wave_45.dotted** (function, lines 32–38, 7 lines, risk `support`): Handles dotted for the other feature.
- **tools.test_login_dialog_presentation_wave_45.source_for** (function, lines 41–42, 2 lines, risk `support`): Handles source for for the other feature.
- **tools.test_login_dialog_presentation_wave_45.top_functions** (function, lines 45–46, 2 lines, risk `support`): Handles top functions for the other feature.
- **tools.test_login_dialog_presentation_wave_45.app_method** (function, lines 49–53, 5 lines, risk `support`): Handles app method for the other feature.
- **tools.test_login_dialog_presentation_wave_45.main** (function, lines 56–135, 80 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_login_dialog_widget_smoke_wave_45.py`

- **tools.test_login_dialog_widget_smoke_wave_45.descendants** (function, lines 16–19, 4 lines, risk `support`): Handles descendants for the other feature.
- **tools.test_login_dialog_widget_smoke_wave_45.top_level** (function, lines 22–25, 4 lines, risk `ui_only`): Handles top level for the other feature.
- **tools.test_login_dialog_widget_smoke_wave_45.find_button** (function, lines 28–34, 7 lines, risk `ui_only`): Retrieves find button for the other feature.
- **tools.test_login_dialog_widget_smoke_wave_45.DummyApp** (class, lines 37–64, 28 lines, risk `container`): Groups DummyApp for the other feature.
- **tools.test_login_dialog_widget_smoke_wave_45.DummyApp.__init__** (method, lines 38–41, 4 lines, risk `ui_only`): Handles init for the other feature.
- **tools.test_login_dialog_widget_smoke_wave_45.DummyApp._load_users_db** (method, lines 43–51, 9 lines, risk `authentication`): Loads load users db for the authentication feature.
- **tools.test_login_dialog_widget_smoke_wave_45.DummyApp._verify_login** (method, lines 53–57, 5 lines, risk `authentication`): Handles verify login for the authentication feature.
- **tools.test_login_dialog_widget_smoke_wave_45.DummyApp._must_change_password** (method, lines 59–60, 2 lines, risk `authentication`): Handles must change password for the payments feature.
- **tools.test_login_dialog_widget_smoke_wave_45.DummyApp._force_change_password_dialog** (method, lines 62–64, 3 lines, risk `authentication`): Handles force change password dialog for the payments feature.
- **tools.test_login_dialog_widget_smoke_wave_45.configure_dependencies** (function, lines 67–99, 33 lines, risk `authentication`): Handles configure dependencies for the other feature.
- **tools.test_login_dialog_widget_smoke_wave_45.configure_dependencies.account_choices** (nested_function, lines 80–82, 3 lines, risk `support`): Handles account choices for the authentication feature.
- **tools.test_login_dialog_widget_smoke_wave_45.configure_dependencies.login_button** (nested_function, lines 84–86, 3 lines, risk `authentication`): Handles login button for the authentication feature.
- **tools.test_login_dialog_widget_smoke_wave_45.run_sign_in** (function, lines 102–132, 31 lines, risk `authentication`): Handles run sign in for the other feature.
- **tools.test_login_dialog_widget_smoke_wave_45.run_sign_in.action** (nested_function, lines 105–125, 21 lines, risk `ui_only`): Handles action for the other feature.
- **tools.test_login_dialog_widget_smoke_wave_45.run_cancel** (function, lines 135–153, 19 lines, risk `authentication`): Handles run cancel for the other feature.
- **tools.test_login_dialog_widget_smoke_wave_45.run_cancel.action** (nested_function, lines 138–146, 9 lines, risk `ui_only`): Handles action for the other feature.
- **tools.test_login_dialog_widget_smoke_wave_45.main** (function, lines 156–166, 11 lines, risk `reports`): Handles main for the other feature.

## `tools/test_login_palette_wave_25.py`

- **tools.test_login_palette_wave_25.source_for** (function, lines 19–20, 2 lines, risk `support`): Handles source for for the other feature.
- **tools.test_login_palette_wave_25.main** (function, lines 23–92, 70 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_long_task_presentation_wave_42.py`

- **tools.test_long_task_presentation_wave_42.normalized** (function, lines 24–25, 2 lines, risk `support`): Handles normalized for the utilities feature.
- **tools.test_long_task_presentation_wave_42.call_chain** (function, lines 28–35, 8 lines, risk `support`): Handles call chain for the other feature.
- **tools.test_long_task_presentation_wave_42.main** (function, lines 38–93, 56 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_merge_note_dict_extraction.py`

- **tools.test_merge_note_dict_extraction.load_notes_module** (function, lines 41–47, 7 lines, risk `support`): Loads load notes module for the notes feature.
- **tools.test_merge_note_dict_extraction.load_helper** (function, lines 50–72, 23 lines, risk `filesystem`): Loads load helper for the utilities feature.
- **tools.test_merge_note_dict_extraction.capture_behavior** (function, lines 75–105, 31 lines, risk `support`): Handles capture behavior for the other feature.
- **tools.test_merge_note_dict_extraction.validate_input_isolation** (function, lines 108–119, 12 lines, risk `support`): Validates validate input isolation for the utilities feature.
- **tools.test_merge_note_dict_extraction.main** (function, lines 122–141, 20 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_module_separation_planner.py`

- **tools.test_module_separation_planner.main** (function, lines 36–53, 18 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_navigation_databank_shell_wave_29.py`

- **tools.test_navigation_databank_shell_wave_29.top_level_functions** (function, lines 45–53, 9 lines, risk `filesystem`): Handles top level functions for the other feature.
- **tools.test_navigation_databank_shell_wave_29.assert_exact_method_bodies** (function, lines 56–77, 22 lines, risk `filesystem`): Handles assert exact method bodies for the other feature.
- **tools.test_navigation_databank_shell_wave_29.assignment_rows** (function, lines 80–95, 16 lines, risk `support`): Handles assignment rows for the other feature.
- **tools.test_navigation_databank_shell_wave_29.assert_startup_wiring** (function, lines 98–132, 35 lines, risk `filesystem`): Handles assert startup wiring for the other feature.
- **tools.test_navigation_databank_shell_wave_29.FakeNotebook** (class, lines 135–157, 23 lines, risk `container`): Groups FakeNotebook for the notes feature.
- **tools.test_navigation_databank_shell_wave_29.FakeNotebook.__init__** (method, lines 136–139, 4 lines, risk `support`): Handles init for the notes feature.
- **tools.test_navigation_databank_shell_wave_29.FakeNotebook.tabs** (method, lines 141–142, 2 lines, risk `support`): Handles tabs for the notes feature.
- **tools.test_navigation_databank_shell_wave_29.FakeNotebook.tab** (method, lines 144–147, 4 lines, risk `support`): Handles tab for the notes feature.
- **tools.test_navigation_databank_shell_wave_29.FakeNotebook.add** (method, lines 149–152, 4 lines, risk `support`): Handles add for the notes feature.
- **tools.test_navigation_databank_shell_wave_29.FakeNotebook.hide** (method, lines 154–157, 4 lines, risk `filesystem`): Handles hide for the notes feature.
- **tools.test_navigation_databank_shell_wave_29.FakeTree** (class, lines 160–183, 24 lines, risk `container`): Groups FakeTree for the other feature.
- **tools.test_navigation_databank_shell_wave_29.FakeTree.__init__** (method, lines 161–165, 5 lines, risk `support`): Handles init for the other feature.
- **tools.test_navigation_databank_shell_wave_29.FakeTree.__getitem__** (method, lines 167–170, 4 lines, risk `support`): Handles getitem for the other feature.
- **tools.test_navigation_databank_shell_wave_29.FakeTree.heading** (method, lines 172–174, 3 lines, risk `support`): Handles heading for the other feature.
- **tools.test_navigation_databank_shell_wave_29.FakeTree.winfo_class** (method, lines 176–177, 2 lines, risk `ui_only`): Handles winfo class for the other feature.
- **tools.test_navigation_databank_shell_wave_29.FakeTree.bind** (method, lines 179–180, 2 lines, risk `support`): Handles bind for the other feature.
- **tools.test_navigation_databank_shell_wave_29.FakeTree.yview_scroll** (method, lines 182–183, 2 lines, risk `support`): Handles yview scroll for the other feature.
- **tools.test_navigation_databank_shell_wave_29.FakeVar** (class, lines 186–191, 6 lines, risk `container`): Groups FakeVar for the other feature.
- **tools.test_navigation_databank_shell_wave_29.FakeVar.__init__** (method, lines 187–188, 2 lines, risk `support`): Handles init for the other feature.
- **tools.test_navigation_databank_shell_wave_29.FakeVar.set** (method, lines 190–191, 2 lines, risk `support`): Handles set for the other feature.
- **tools.test_navigation_databank_shell_wave_29.FakeButton** (class, lines 194–201, 8 lines, risk `container`): Groups FakeButton for the other feature.
- **tools.test_navigation_databank_shell_wave_29.FakeButton.__init__** (method, lines 195–196, 2 lines, risk `support`): Handles init for the other feature.
- **tools.test_navigation_databank_shell_wave_29.FakeButton.config** (method, lines 198–199, 2 lines, risk `support`): Handles config for the other feature.
- **tools.test_navigation_databank_shell_wave_29.assert_navigation_behavior** (function, lines 204–263, 60 lines, risk `support`): Handles assert navigation behavior for the navigation feature.
- **tools.test_navigation_databank_shell_wave_29.assert_data_bank_shell_behavior** (function, lines 267–304, 38 lines, risk `support`): Handles assert data bank shell behavior for the data bank feature.
- **tools.test_navigation_databank_shell_wave_29.main** (function, lines 307–312, 6 lines, risk `reports`): Handles main for the other feature.

## `tools/test_note_dict_helper_extraction.py`

- **tools.test_note_dict_helper_extraction.load_helper** (function, lines 38–61, 24 lines, risk `filesystem`): Loads load helper for the utilities feature.
- **tools.test_note_dict_helper_extraction.capture_behavior** (function, lines 64–84, 21 lines, risk `support`): Handles capture behavior for the other feature.
- **tools.test_note_dict_helper_extraction.validate_copy_semantics** (function, lines 87–99, 13 lines, risk `support`): Validates validate copy semantics for the utilities feature.
- **tools.test_note_dict_helper_extraction.main** (function, lines 102–121, 20 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_note_editor_presentation_wave_40.py`

- **tools.test_note_editor_presentation_wave_40.normalized** (function, lines 20–21, 2 lines, risk `support`): Handles normalized for the utilities feature.
- **tools.test_note_editor_presentation_wave_40.call_chain** (function, lines 24–31, 8 lines, risk `support`): Handles call chain for the other feature.
- **tools.test_note_editor_presentation_wave_40.main** (function, lines 34–78, 45 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_numeric_parser_extraction.py`

- **tools.test_numeric_parser_extraction._cases** (function, lines 27–42, 16 lines, risk `support`): Handles cases for the other feature.
- **tools.test_numeric_parser_extraction._validate_signature** (function, lines 45–63, 19 lines, risk `support`): Validates validate signature for the utilities feature.
- **tools.test_numeric_parser_extraction._capture** (function, lines 66–79, 14 lines, risk `support`): Handles capture for the other feature.
- **tools.test_numeric_parser_extraction._behavior** (function, lines 82–90, 9 lines, risk `support`): Handles behavior for the other feature.
- **tools.test_numeric_parser_extraction._functions_from_module_source** (function, lines 93–96, 4 lines, risk `support`): Handles functions from module source for the other feature.
- **tools.test_numeric_parser_extraction._load_generated_functions** (function, lines 99–105, 7 lines, risk `support`): Loads load generated functions for the other feature.
- **tools.test_numeric_parser_extraction._source_state** (function, lines 108–116, 9 lines, risk `support`): Handles source state for the other feature.
- **tools.test_numeric_parser_extraction._write_fixture** (function, lines 119–126, 8 lines, risk `filesystem`): Saves write fixture for the other feature.
- **tools.test_numeric_parser_extraction._test_original_state** (function, lines 129–157, 29 lines, risk `filesystem`): Handles test original state for the other feature.
- **tools.test_numeric_parser_extraction._test_applied_state** (function, lines 160–177, 18 lines, risk `filesystem`): Handles test applied state for the other feature.
- **tools.test_numeric_parser_extraction.main** (function, lines 180–209, 30 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_payment_schedule_normalizer_batch_06.py`

- **tools.test_payment_schedule_normalizer_batch_06.BrokenText** (class, lines 26–28, 3 lines, risk `container`): Groups BrokenText for the other feature.
- **tools.test_payment_schedule_normalizer_batch_06.BrokenText.__str__** (method, lines 27–28, 2 lines, risk `support`): Handles str for the other feature.
- **tools.test_payment_schedule_normalizer_batch_06.MondayText** (class, lines 31–33, 3 lines, risk `container`): Groups MondayText for the other feature.
- **tools.test_payment_schedule_normalizer_batch_06.MondayText.__str__** (method, lines 32–33, 2 lines, risk `support`): Handles str for the other feature.
- **tools.test_payment_schedule_normalizer_batch_06._type_name** (function, lines 36–38, 3 lines, risk `support`): Handles type name for the other feature.
- **tools.test_payment_schedule_normalizer_batch_06._resolve_source_function** (function, lines 41–58, 18 lines, risk `filesystem`): Handles resolve source function for the other feature.
- **tools.test_payment_schedule_normalizer_batch_06._resolve_function** (function, lines 61–71, 11 lines, risk `support`): Handles resolve function for the other feature.
- **tools.test_payment_schedule_normalizer_batch_06._capture** (function, lines 74–87, 14 lines, risk `support`): Handles capture for the other feature.
- **tools.test_payment_schedule_normalizer_batch_06._weekday_cases** (function, lines 90–111, 22 lines, risk `support`): Handles weekday cases for the other feature.
- **tools.test_payment_schedule_normalizer_batch_06._day_of_month_cases** (function, lines 114–131, 18 lines, risk `support`): Handles day of month cases for the other feature.
- **tools.test_payment_schedule_normalizer_batch_06.capture_batch** (function, lines 134–156, 23 lines, risk `filesystem`): Handles capture batch for the other feature.
- **tools.test_payment_schedule_normalizer_batch_06.main** (function, lines 159–194, 36 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_postgres_compat_wave_34.py`

- **tools.test_postgres_compat_wave_34.normalized_source** (function, lines 16–17, 2 lines, risk `support`): Handles normalized source for the utilities feature.
- **tools.test_postgres_compat_wave_34.source_hash** (function, lines 20–21, 2 lines, risk `support`): Handles source hash for the other feature.
- **tools.test_postgres_compat_wave_34.main** (function, lines 24–80, 57 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_pure_helper_batch.py`

- **tools.test_pure_helper_batch._load_manifest** (function, lines 88–89, 2 lines, risk `filesystem`): Loads load manifest for the other feature.
- **tools.test_pure_helper_batch._resolve_from_source** (function, lines 92–108, 17 lines, risk `filesystem`): Handles resolve from source for the other feature.
- **tools.test_pure_helper_batch._resolve_function** (function, lines 111–121, 11 lines, risk `support`): Handles resolve function for the other feature.
- **tools.test_pure_helper_batch._type_name** (function, lines 124–126, 3 lines, risk `support`): Handles type name for the other feature.
- **tools.test_pure_helper_batch._capture** (function, lines 129–142, 14 lines, risk `support`): Handles capture for the other feature.
- **tools.test_pure_helper_batch.capture_batch** (function, lines 145–167, 23 lines, risk `support`): Handles capture batch for the other feature.
- **tools.test_pure_helper_batch.main** (function, lines 170–206, 37 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_reports_feature_wave_18.py`

- **tools.test_reports_feature_wave_18._sha** (function, lines 28–29, 2 lines, risk `support`): Handles sha for the other feature.
- **tools.test_reports_feature_wave_18._sources** (function, lines 32–40, 9 lines, risk `filesystem`): Handles sources for the other feature.
- **tools.test_reports_feature_wave_18._assert_structure** (function, lines 43–64, 22 lines, risk `filesystem`): Handles assert structure for the other feature.
- **tools.test_reports_feature_wave_18._assert_dependency_bridge** (function, lines 67–79, 13 lines, risk `reports`): Handles assert dependency bridge for the other feature.
- **tools.test_reports_feature_wave_18._assert_card_refresh_behavior** (function, lines 82–115, 34 lines, risk `reports`): Handles assert card refresh behavior for the other feature.
- **tools.test_reports_feature_wave_18.main** (function, lines 118–122, 5 lines, risk `reports`): Handles main for the other feature.

## `tools/test_reports_notes_dialog_wiring.py`

- **tools.test_reports_notes_dialog_wiring.main** (function, lines 13–52, 40 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_side_navigation_presentation_wave_48.py`

- **tools.test_side_navigation_presentation_wave_48.dotted** (function, lines 25–31, 7 lines, risk `support`): Handles dotted for the other feature.
- **tools.test_side_navigation_presentation_wave_48.normalized** (function, lines 34–35, 2 lines, risk `support`): Handles normalized for the utilities feature.
- **tools.test_side_navigation_presentation_wave_48.source_for** (function, lines 38–41, 4 lines, risk `support`): Handles source for for the other feature.
- **tools.test_side_navigation_presentation_wave_48.function_nodes** (function, lines 44–45, 2 lines, risk `support`): Handles function nodes for the other feature.
- **tools.test_side_navigation_presentation_wave_48.check_function** (function, lines 48–57, 10 lines, risk `support`): Handles check function for the other feature.
- **tools.test_side_navigation_presentation_wave_48.find_capture** (function, lines 60–71, 12 lines, risk `support`): Retrieves find capture for the other feature.
- **tools.test_side_navigation_presentation_wave_48.find_binding** (function, lines 74–88, 15 lines, risk `support`): Retrieves find binding for the other feature.
- **tools.test_side_navigation_presentation_wave_48.main** (function, lines 91–219, 129 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_side_navigation_widget_smoke_wave_48.py`

- **tools.test_side_navigation_widget_smoke_wave_48.main** (function, lines 16–89, 74 lines, risk `reports`): Handles main for the other feature.

## `tools/test_text_normalizer_extraction.py`

- **tools.test_text_normalizer_extraction._cases** (function, lines 27–41, 15 lines, risk `support`): Handles cases for the other feature.
- **tools.test_text_normalizer_extraction._validate_signature** (function, lines 44–64, 21 lines, risk `support`): Validates validate signature for the utilities feature.
- **tools.test_text_normalizer_extraction._capture** (function, lines 67–80, 14 lines, risk `support`): Handles capture for the other feature.
- **tools.test_text_normalizer_extraction._behavior** (function, lines 83–91, 9 lines, risk `support`): Handles behavior for the other feature.
- **tools.test_text_normalizer_extraction._functions_from_module_source** (function, lines 94–97, 4 lines, risk `support`): Handles functions from module source for the other feature.
- **tools.test_text_normalizer_extraction._load_generated_functions** (function, lines 100–106, 7 lines, risk `support`): Loads load generated functions for the other feature.
- **tools.test_text_normalizer_extraction._source_state** (function, lines 109–117, 9 lines, risk `support`): Handles source state for the other feature.
- **tools.test_text_normalizer_extraction._write_fixture** (function, lines 120–130, 11 lines, risk `filesystem`): Saves write fixture for the other feature.
- **tools.test_text_normalizer_extraction._test_original_state** (function, lines 133–162, 30 lines, risk `filesystem`): Handles test original state for the other feature.
- **tools.test_text_normalizer_extraction._test_applied_state** (function, lines 165–182, 18 lines, risk `filesystem`): Handles test applied state for the other feature.
- **tools.test_text_normalizer_extraction.main** (function, lines 185–217, 33 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_theme_palette_helper_batch_05.py`

- **tools.test_theme_palette_helper_batch_05.Holder** (class, lines 31–34, 4 lines, risk `container`): Groups Holder for the other feature.
- **tools.test_theme_palette_helper_batch_05.Holder.__init__** (method, lines 32–34, 3 lines, risk `support`): Handles init for the other feature.
- **tools.test_theme_palette_helper_batch_05.BadString** (class, lines 37–39, 3 lines, risk `container`): Groups BadString for the other feature.
- **tools.test_theme_palette_helper_batch_05.BadString.__str__** (method, lines 38–39, 2 lines, risk `support`): Handles str for the other feature.
- **tools.test_theme_palette_helper_batch_05._stable** (function, lines 42–49, 8 lines, risk `support`): Handles stable for the other feature.
- **tools.test_theme_palette_helper_batch_05._type_name** (function, lines 52–54, 3 lines, risk `support`): Handles type name for the other feature.
- **tools.test_theme_palette_helper_batch_05._load_manifest** (function, lines 57–58, 2 lines, risk `filesystem`): Loads load manifest for the other feature.
- **tools.test_theme_palette_helper_batch_05._resolve_from_source** (function, lines 61–81, 21 lines, risk `filesystem`): Handles resolve from source for the other feature.
- **tools.test_theme_palette_helper_batch_05._resolve_function** (function, lines 84–94, 11 lines, risk `support`): Handles resolve function for the other feature.
- **tools.test_theme_palette_helper_batch_05._cases** (function, lines 97–110, 14 lines, risk `support`): Handles cases for the other feature.
- **tools.test_theme_palette_helper_batch_05._capture_call** (function, lines 113–126, 14 lines, risk `support`): Handles capture call for the other feature.
- **tools.test_theme_palette_helper_batch_05.capture_batch** (function, lines 129–149, 21 lines, risk `support`): Handles capture batch for the other feature.
- **tools.test_theme_palette_helper_batch_05.main** (function, lines 152–190, 39 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_theme_presentation_wave_35.py`

- **tools.test_theme_presentation_wave_35.normalized** (function, lines 18–19, 2 lines, risk `support`): Handles normalized for the utilities feature.
- **tools.test_theme_presentation_wave_35.digest** (function, lines 22–23, 2 lines, risk `support`): Handles digest for the other feature.
- **tools.test_theme_presentation_wave_35.main** (function, lines 26–75, 50 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_tk_shutdown_wave_46.py`

- **tools.test_tk_shutdown_wave_46.load_methods** (function, lines 17–34, 18 lines, risk `filesystem`): Loads load methods for the other feature.
- **tools.test_tk_shutdown_wave_46.child** (function, lines 37–77, 41 lines, risk `reports`): Handles child for the other feature.
- **tools.test_tk_shutdown_wave_46.child.switch_theme_and_close** (nested_function, lines 65–70, 6 lines, risk `support`): Handles switch theme and close for the settings feature.
- **tools.test_tk_shutdown_wave_46.parent** (function, lines 80–104, 25 lines, risk `filesystem`): Handles parent for the other feature.

## `tools/test_ui_button_factories_wave_50.py`

- **tools.test_ui_button_factories_wave_50.dotted** (function, lines 55–61, 7 lines, risk `support`): Handles dotted for the other feature.
- **tools.test_ui_button_factories_wave_50.normalized** (function, lines 64–65, 2 lines, risk `support`): Handles normalized for the utilities feature.
- **tools.test_ui_button_factories_wave_50.source_hash** (function, lines 68–69, 2 lines, risk `support`): Handles source hash for the other feature.
- **tools.test_ui_button_factories_wave_50.top_function** (function, lines 72–75, 4 lines, risk `support`): Handles top function for the other feature.
- **tools.test_ui_button_factories_wave_50.source_for** (function, lines 78–81, 4 lines, risk `support`): Handles source for for the other feature.
- **tools.test_ui_button_factories_wave_50.calls_for** (function, lines 84–89, 6 lines, risk `support`): Handles calls for for the other feature.
- **tools.test_ui_button_factories_wave_50.verify_function** (function, lines 92–98, 7 lines, risk `filesystem`): Handles verify function for the other feature.
- **tools.test_ui_button_factories_wave_50.main** (function, lines 101–157, 57 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_ui_button_factories_widget_smoke_wave_50.py`

- **tools.test_ui_button_factories_widget_smoke_wave_50.expected** (function, lines 24–35, 12 lines, risk `support`): Handles expected for the other feature.
- **tools.test_ui_button_factories_widget_smoke_wave_50.verify_button** (function, lines 38–60, 23 lines, risk `ui_only`): Handles verify button for the other feature.
- **tools.test_ui_button_factories_widget_smoke_wave_50.main** (function, lines 63–84, 22 lines, risk `reports`): Handles main for the other feature.

## `tools/test_ui_card_constructor_batch_08.py`

- **tools.test_ui_card_constructor_batch_08.FakeWidget** (class, lines 54–65, 12 lines, risk `container`): Groups FakeWidget for the other feature.
- **tools.test_ui_card_constructor_batch_08.FakeWidget.__init__** (method, lines 55–62, 8 lines, risk `support`): Handles init for the other feature.
- **tools.test_ui_card_constructor_batch_08.FakeWidget.pack** (method, lines 64–65, 2 lines, risk `support`): Handles pack for the other feature.
- **tools.test_ui_card_constructor_batch_08._WidgetFactory** (class, lines 68–73, 6 lines, risk `container`): Groups WidgetFactory for the other feature.
- **tools.test_ui_card_constructor_batch_08._WidgetFactory.__init__** (method, lines 69–70, 2 lines, risk `support`): Handles init for the other feature.
- **tools.test_ui_card_constructor_batch_08._WidgetFactory.__call__** (method, lines 72–73, 2 lines, risk `support`): Handles call for the other feature.
- **tools.test_ui_card_constructor_batch_08.FakeTk** (class, lines 76–78, 3 lines, risk `container`): Groups FakeTk for the other feature.
- **tools.test_ui_card_constructor_batch_08._cash_palette** (function, lines 81–82, 2 lines, risk `support`): Handles cash palette for the other feature.
- **tools.test_ui_card_constructor_batch_08._cilog_palette** (function, lines 85–86, 2 lines, risk `support`): Handles cilog palette for the clients feature.
- **tools.test_ui_card_constructor_batch_08._load_manifest** (function, lines 89–90, 2 lines, risk `filesystem`): Loads load manifest for the other feature.
- **tools.test_ui_card_constructor_batch_08._source_function** (function, lines 93–113, 21 lines, risk `filesystem`): Handles source function for the other feature.
- **tools.test_ui_card_constructor_batch_08._resolve_function** (function, lines 116–130, 15 lines, risk `support`): Handles resolve function for the other feature.
- **tools.test_ui_card_constructor_batch_08._widget_summary** (function, lines 133–139, 7 lines, risk `support`): Handles widget summary for the other feature.
- **tools.test_ui_card_constructor_batch_08._capture** (function, lines 142–175, 34 lines, risk `support`): Handles capture for the other feature.
- **tools.test_ui_card_constructor_batch_08.capture_batch** (function, lines 178–200, 23 lines, risk `support`): Handles capture batch for the other feature.
- **tools.test_ui_card_constructor_batch_08.main** (function, lines 203–241, 39 lines, risk `filesystem`): Handles main for the other feature.

## `tools/test_ui_display_helper_batch.py`

- **tools.test_ui_display_helper_batch.FakeCanvas** (class, lines 36–57, 22 lines, risk `container`): Groups FakeCanvas for the other feature.
- **tools.test_ui_display_helper_batch.FakeCanvas.__init__** (method, lines 37–39, 3 lines, risk `support`): Handles init for the other feature.
- **tools.test_ui_display_helper_batch.FakeCanvas.create_polygon** (method, lines 41–49, 9 lines, risk `support`): Builds create polygon for the other feature.
- **tools.test_ui_display_helper_batch.FakeCanvas.create_rectangle** (method, lines 51–57, 7 lines, risk `support`): Builds create rectangle for the other feature.
- **tools.test_ui_display_helper_batch.FakeLabel** (class, lines 60–68, 9 lines, risk `container`): Groups FakeLabel for the other feature.
- **tools.test_ui_display_helper_batch.FakeLabel.__init__** (method, lines 61–63, 3 lines, risk `support`): Handles init for the other feature.
- **tools.test_ui_display_helper_batch.FakeLabel.configure** (method, lines 65–68, 4 lines, risk `support`): Handles configure for the other feature.
- **tools.test_ui_display_helper_batch.Holder** (class, lines 71–72, 2 lines, risk `container`): Groups Holder for the other feature.
- **tools.test_ui_display_helper_batch._stable** (function, lines 75–82, 8 lines, risk `support`): Handles stable for the other feature.
- **tools.test_ui_display_helper_batch._type_name** (function, lines 85–87, 3 lines, risk `support`): Handles type name for the other feature.
- **tools.test_ui_display_helper_batch._load_manifest** (function, lines 90–91, 2 lines, risk `filesystem`): Loads load manifest for the other feature.
- **tools.test_ui_display_helper_batch._resolve_from_source** (function, lines 94–110, 17 lines, risk `filesystem`): Handles resolve from source for the other feature.
- **tools.test_ui_display_helper_batch._resolve_function** (function, lines 113–123, 11 lines, risk `support`): Handles resolve function for the other feature.
- **tools.test_ui_display_helper_batch._capture_round** (function, lines 126–156, 31 lines, risk `support`): Handles capture round for the other feature.
- **tools.test_ui_display_helper_batch._card_state** (function, lines 159–163, 5 lines, risk `support`): Handles card state for the other feature.
- **tools.test_ui_display_helper_batch._capture_card** (function, lines 166–210, 45 lines, risk `support`): Handles capture card for the other feature.
- **tools.test_ui_display_helper_batch.capture_batch** (function, lines 213–245, 33 lines, risk `support`): Handles capture batch for the other feature.
- **tools.test_ui_display_helper_batch.main** (function, lines 248–284, 37 lines, risk `filesystem`): Handles main for the other feature.

## `tools/ui_action_inventory.py`

- **tools.ui_action_inventory.normalize** (function, lines 103–104, 2 lines, risk `support`): Handles normalize for the utilities feature.
- **tools.ui_action_inventory.line_context** (function, lines 107–110, 4 lines, risk `support`): Handles line context for the other feature.
- **tools.ui_action_inventory.looks_like_ui_context** (function, lines 113–115, 3 lines, risk `support`): Handles looks like ui context for the other feature.
- **tools.ui_action_inventory.has_protected_keyword** (function, lines 118–120, 3 lines, risk `support`): Handles has protected keyword for the other feature.
- **tools.ui_action_inventory.looks_like_label_literal** (function, lines 123–133, 11 lines, risk `support`): Return True when a line contains the exact UI label as display text. This intentionally does not match case-insensitive SQL fragments such as `FROM transactions` or option names such as `exportselection=False`.
- **tools.ui_action_inventory.should_ignore_label_hit** (function, lines 136–138, 3 lines, risk `support`): Handles should ignore label hit for the other feature.
- **tools.ui_action_inventory.collect_label_hits** (function, lines 141–161, 21 lines, risk `support`): Handles collect label hits for the other feature.
- **tools.ui_action_inventory.collect_callback_candidates** (function, lines 164–187, 24 lines, risk `support`): Handles collect callback candidates for the other feature.
- **tools.ui_action_inventory.collect_command_references** (function, lines 190–210, 21 lines, risk `support`): Handles collect command references for the other feature.
- **tools.ui_action_inventory.build_recommendations** (function, lines 213–243, 31 lines, risk `support`): Builds build recommendations for the other feature.
- **tools.ui_action_inventory.audit** (function, lines 246–262, 17 lines, risk `filesystem`): Handles audit for the other feature.
- **tools.ui_action_inventory.print_summary** (function, lines 265–300, 36 lines, risk `reports`): Generates print summary for the reports feature.
- **tools.ui_action_inventory.main** (function, lines 303–318, 16 lines, risk `filesystem`): Handles main for the other feature.
