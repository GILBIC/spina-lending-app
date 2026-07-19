# Logger fallback pass-only cleanup tool

This document describes `tools/cleanup_logger_fallback_pass_only.py`.

## Purpose

The tool targets only the two exact logger fallback pass-only handlers found by `tools/plan_logger_fallback_pass_only.py`:

1. `_log_exc` final stderr fallback
2. `_log_suppressed_once` final stderr fallback

These are last-resort logger failure paths. The cleanup must not call `_log_exc`, `_log_suppressed_once`, or any other logger from inside these handlers, because that could create recursive logging.

## Safety rules

The tool fails closed unless each target is either:

- an exact safe candidate with `except Exception:` followed by `pass`, or
- already clean with `except Exception:` followed by `return`

The replacement is intentionally minimal:

```python
except Exception:
    return
```

This keeps behavior functionally unchanged: if even the final stderr fallback fails, the logger helper simply exits.

## What it does not touch

The tool does not touch:

- reports or PDFs
- payments, balances, 7x7, renewals, ledgers, collectors, or cash-control
- database, PostgreSQL, migrations, backups, or restore logic
- role/access logic
- login/auth logic
- general pass-only handlers outside these two logger fallback sites

## Dry-run

```bat
python tools\cleanup_logger_fallback_pass_only.py --json logger-fallback-cleanup-dry-run.json
```

Upload the JSON before applying.

## Apply

Apply only after the dry-run shows `safe: true` and `unsafe_count: 0`.

```bat
python tools\cleanup_logger_fallback_pass_only.py --apply --json logger-fallback-cleanup-after.json
```

## Verify

```bat
python tools\cleanup_logger_fallback_pass_only.py --json logger-fallback-cleanup-after-dry-run.json
python tools\plan_logger_fallback_pass_only.py --json logger-fallback-pass-only-plan-after.json
python tools\audit_pass_only_exceptions.py --json pass-only-exception-after-logger-fallback-cleanup.json
```

Then smoke-test app startup and normal logging behavior.
