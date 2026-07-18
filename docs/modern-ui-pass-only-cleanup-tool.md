# Modern UI pass-only cleanup tool

This tool is a narrow cleanup helper for the modern UI chrome/sidebar/theme pass-only exception handlers identified by the planner.

## What it targets

Only the 19 selected modern UI handlers from `tools/plan_modern_ui_pass_only_cleanup.py`:

- `App.set_theme`
- `App._select_side_tab`
- `App._rebuild_side_nav`
- `App._refresh_side_nav_selection`
- `App._refresh_modern_shell_theme`
- `App._tk_button_hover`
- `App._set_mode`
- `App._refresh_mode_toggle`
- `App._refresh_header_theme`

## Safety rules

The tool fails closed unless each target still matches an exact pass-only handler:

```python
except Exception:
    pass
```

It also refuses to apply when protected business-context words appear near the target.

It does not target reports, PDFs, payments, balances, 7x7 calculation logic, renewals, collectors, backups, database migrations, cash-control, or report math.

## Dry run

Run this first:

```bat
python tools\cleanup_modern_ui_pass_only.py --json modern-ui-pass-only-cleanup-dry-run.json
```

Upload the JSON before applying.

## Apply

Apply only after the dry-run JSON shows:

- `safe: true`
- `unsafe_count: 0`
- expected candidate count

```bat
python tools\cleanup_modern_ui_pass_only.py --apply --json modern-ui-pass-only-cleanup-after.json
```

## After apply

Rerun:

```bat
python tools\audit_pass_only_exceptions.py --json pass-only-exception-after-modern-ui-cleanup.json
python tools\plan_modern_ui_pass_only_cleanup.py --json modern-ui-pass-only-cleanup-plan-after.json
```

Then smoke-test:

- app opens and logs in
- theme toggle works
- sidebar navigation works
- Regular / 7x7 mode switch still works
