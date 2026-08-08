# Stage 5E.2 — Historical loan dataset reconstruction

Status: **historical evidence import and outcome-labeling readiness**.

Stage 5E.2 uses a legacy SPINA SQLite backup as an accounting-only historical source. It reconstructs loan episodes from `client_history` start events (`SNAPSHOT`, `ADD`, `RENEW`) and allocates final-state `transactions` to each episode by release-date interval.

## Safety boundary

The legacy database is never imported into operational `lending.loans`, borrower balances, current collection state, remittances, the protected opening workbook, or the General Ledger. The historical tables live only under `accounting`.

Names, contact numbers, addresses and client photos are not required for ECL calibration and are not stored in the historical episode table. Borrowers are represented by a SHA-256 key derived from the legacy `person_uid` when available, otherwise `client_uid`.

## Reconstructed evidence

For each episode the importer preserves:

- loan type, release/due dates, principal, contractual total and interest rate;
- observed positive cash and zero-payment observations during that episode;
- renewal rollover evidence where the next episode is a renewal;
- operational end evidence: `renewed`, `archived`, `archived_at_snapshot`, `deleted`, or `open_at_snapshot`;
- structural source-quality blockers such as missing dates or non-positive principal.

Those operational events are **not** automatically mapped to paid, defaulted, written off, cured, or recovered outcomes.

## Why Stage 5E.2 still does not calculate ECL

A renewal can refinance a remaining balance rather than indicate a credit loss. An archive can represent several business reasons. A deletion is an audit/data event, not a credit outcome. Therefore SPINA requires explicit reviewed labels before these records can be used to estimate default frequency or loss severity.

Until explicit outcome, loss/recovery and forward-looking methodology are approved:

- `explicit_default_label` remains NULL;
- `explicit_loss_amount` remains NULL;
- `explicit_recovery_amount` remains NULL;
- account `1190` remains unquantified;
- `ecl_amount` remains NULL;
- `ecl_included = false`;
- `ready_to_post = false`.

## Reconstruction command

From an environment where the backend package is installed:

```text
python tools/reconstruct_ecl_history.py <legacy.db> --output ecl-history.json
```

The output includes the source SHA-256 digest, source inventory and reconstructed episodes so the exact backup used for calibration can be audited.
