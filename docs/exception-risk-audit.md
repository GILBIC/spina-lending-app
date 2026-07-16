# SPINA exception risk audit

This document explains the extra exception-risk fields added to `tools/spina_quality_audit.py`.

## Purpose

The SPINA desktop app still has many broad `except Exception` handlers. Some are harmless fallbacks, but some may hide bugs in sensitive areas like database connection, login, reports, Excel import, backup/restore, or payment/balance code.

This PR does not change app behavior. It only improves the read-only audit report so the next cleanup PR can target the safest area first.

## New report fields

The quality audit now reports:

- `silent_broad_except_count`
- `broad_except_by_risk_area`
- `silent_broad_except_by_risk_area`
- `silent_broad_except_examples`
- `high_risk_silent_except_examples`

A broad exception is treated as silent when the handler does not obviously log, show a message, or re-raise.

## Risk areas

The audit groups handlers by function name into these buckets:

- `startup/database`
- `login/accounts`
- `reports/pdf`
- `excel/import-export`
- `backup/restore`
- `payment/balance`
- `general`

This grouping is not a final bug verdict. It is a triage map.

## Local command

```bat
python tools\spina_quality_audit.py "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py" --json quality-report.json
```

Open `quality-report.json`, then check `high_risk_silent_except_examples` first.

## Cleanup rule

Do not fix all silent exceptions at once. Use one PR per area, for example:

1. reports/pdf only
2. excel/import-export only
3. backup/restore only
4. login/accounts only

Avoid changing loan calculations, balances, payment allocation, or report math in the same PR as logging cleanup.
