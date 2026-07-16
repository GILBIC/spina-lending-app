# SPINA redundancy audit

Reviewed file: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py`

This review intentionally does **not** delete application code yet. SPINA is a large, patch-based single-file program, and several later definitions replace earlier implementations at runtime. Removing a definition merely because its name appears more than once could change login, dashboard, client, report, or collector-route behavior.

## Current findings

The source contains approximately 49,118 lines and 381 top-level function definitions representing 374 unique names.

### Repeated top-level definitions

The audit found these names defined more than once:

- `_collectors_areas_drag_motion`
- `_on_collectors_multi_toggle`
- `_on_collectors_select`
- `_on_collectors_tree_click`
- `_on_collectors_tree_wheel`
- `_spina__client_due_meta`
- `_spina_route_adv_marker_for`

Only the final top-level definition with a given name remains available after module loading, unless an earlier function object was saved elsewhere before replacement.

### Duplicate methods declared inside `App`

- `App._get_selected_report_client` is declared three times.
- `App._auto_load_report_note` is declared twice.

Inside one class body, later declarations replace earlier declarations. These are strong cleanup candidates, but their bodies should be compared and the final behavior tested before removal.

### Repeated monkey-patch targets

The application repeatedly replaces methods after class creation. The largest hotspots include:

- `App.__init__`
- `App.apply_role_access`
- `App._apply_ui_theme`
- `App._build_clients_tab`
- `App._build_collectors_tab`
- `App.refresh_clients`
- `App.refresh_collectors`
- `App.refresh_dashboard`
- `App._populate_dashboard_tree`
- `App.refresh_data_grid`

These patches explain much of the startup call stack and make the effective implementation difficult to trace. They should be consolidated feature-by-feature, not removed in bulk.

### Exact duplicate helper bodies

The audit found helper groups with identical AST bodies, including:

- `_spina_archive_row_to_dict` and `_spina_restore_row_to_dict`
- three compact money-formatting helpers
- two rounded-rectangle drawing helpers
- repeated theme/color palette helpers

These are lower-risk consolidation candidates because shared helpers can replace identical implementations without changing output, provided all call sites are preserved.

## Recommended cleanup order

1. Add automated syntax and redundancy checks.
2. Consolidate exact duplicate pure helpers.
3. Remove shadowed methods inside the original `App` class after comparing the final implementation.
4. Consolidate collector UI patches into one implementation.
5. Consolidate dashboard refresh patches.
6. Flatten the five `App.__init__` wrappers into one explicit initialization sequence.
7. Split the application into modules only after behavior is covered by tests.

## Validation required before merging behavioral cleanup

Test at minimum:

- Owner and staff account login
- Client add, edit, renewal, search, and Excel import
- Data Bank loading and payment entry
- ADV and PASS detection
- Regular and 7x7 balances
- Full Daily Ledger and Collector Route PDFs
- Dashboard, reports, client information logs, and cash control
- PostgreSQL backup, verification, and restore test

## Audit command

```bash
python tools/redundancy_audit.py OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py
```

The tool is read-only and can also produce JSON:

```bash
python tools/redundancy_audit.py OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py --json redundancy-report.json
```
