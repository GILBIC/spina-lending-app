# Pure login dialog UI pass-only cleanup tool

`tools/cleanup_pure_login_dialog_ui_pass_only.py` is a dry-run/apply cleanup tool for a very small reviewed login dialog UI-only subgroup.

## Scope

The tool targets only these exact pure login dialog UI pass-only handlers:

- login dialog `dlg.transient(self.root)` fallback
- account combo `account_var.trace_add("write", _refresh_account_info)` fallback
- Return-key binding fallback
- dialog `dlg.grab_set()` fallback
- dialog geometry/positioning fallback

The initial password focus handler is intentionally excluded.

## Safety

The tool fails closed unless every exact target is either safely patchable or already patched by this same tool.

It excludes password verification, password-change flow, role/access, account database save/load, account switching, account header refresh, reports, PDFs, payments, balances, 7x7 calculation logic, renewals, collectors, backups, PostgreSQL, database migrations, cash-control, and report math.

By default, the tool is dry-run only and does not edit the SPINA app.

## Dry-run

```bat
python tools\cleanup_pure_login_dialog_ui_pass_only.py --json pure-login-dialog-ui-cleanup-dry-run.json
```

Review the JSON first. Apply only if:

- `safe` is `true`
- `unsafe_count` is `0`
- the selected handlers are still the 5 exact pure login dialog UI handlers

## Apply

```bat
python tools\cleanup_pure_login_dialog_ui_pass_only.py --apply --json pure-login-dialog-ui-cleanup-after.json
```

## Verify after apply

```bat
python tools\cleanup_pure_login_dialog_ui_pass_only.py --json pure-login-dialog-ui-cleanup-after-dry-run.json
python tools\plan_pure_login_dialog_ui_pass_only.py --json pure-login-dialog-ui-pass-only-plan-after.json
python tools\audit_pass_only_exceptions.py --json pass-only-exception-after-pure-login-dialog-cleanup.json
```

## Smoke test after apply

Test these before committing the app source change:

- staff login
- account switching
- password-change-required flow
- Cancel button
- Return-key login
- login dialog positioning
