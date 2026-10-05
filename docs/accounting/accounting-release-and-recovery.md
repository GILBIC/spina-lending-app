# Accounting release and forward recovery

This runbook is a release procedure, not evidence that SPINA is already deployed or that a real company's books are complete. The execution ledger in `docs/reviews/2026-10-05-accounting-completion-progress.md` names the latest verified software boundaries and remaining work.

## Before release

1. Freeze the proposed code and numbered migrations. Preserve the commit, schema version, test outputs and independent review findings with the release record. Run the disposable verifiers for that exact version; a successful earlier bounded verifier does not prove a later migration.
2. Restore a recent production backup and matching private evidence into a separately credentialed staging deployment. Preserve original evidence identifiers and bytes. Confirm the restored book identity against the intended deployment. Use no live notifications or payment connections during the rehearsal.
3. Apply migrations in order to staging. Investigate a chart collision using the actual existing account definition and balances. Do not overwrite the account, delete migration checks or add a balancing journal simply to make installation pass.
4. Reconcile source inventories, every cash wallet/custody account, lending carrying balances, unapplied funds, payables and transit to the posted ledger. Inspect unsupported, corrected and unregistered sources, including offsetting lines whose net balance is zero. Close requires exact source support, not zero liabilities.
5. Exercise current-role/device/wallet denials, changed-source rejection, unchanged-request recovery, review/prepare/confirmation and concurrent source changes. Verify the final statement pack and an independently reconciled parallel period close using real retained evidence.
6. Record the release decision and rollback boundary before scheduling the production maintenance window. Production activation is a separate action from this implementation work.

Owner and corporate deployments must follow `separate-book-deployments.md`. Each requires its own credentials, authorization records, private files, backups and pinned `GILBIC_EXPECTED_ACCOUNTING_BOOK_ID`. Copying the owner database into the corporate deployment is not company opening accounting.

## Applying an approved release

Pause accounting preparation/posting and period-close writes during migration and smoke checks. Coordinate operational entry so actual-money evidence is retained throughout the maintenance window; do not discard or invent an event to work around a closed period. Back up the database, private evidence and deployment configuration together immediately before migration.

Apply each reviewed migration through the established migration process. Deploy compatible backend and clients together, then verify configured book identity, read permissions, explicit preparation/confirmation and retained statement/review evidence. Reconcile pre/post migration balances; these schema changes must not themselves create company amounts.

Enable supported workflows only after those checks pass. Keep unsupported source families visible as blockers. The software's partial-source and annual-package labels must continue to describe the implemented and verified scope truthfully.

## Recovery after a failure

- **Uncertain request response:** recover the original request/preparation and confirmation identity. Do not create a new request or operational movement to test whether the first succeeded. Compare the returned immutable posting audit and journal.
- **Migration failure before commit:** preserve the error and release record, verify transaction rollback and inspect schema/version state before retrying. An idempotent replay may recover the same migration; it must not reinterpret retained evidence.
- **Failure after schema commit, before new postings:** keep writes paused. Prefer a reviewed forward fix. Restore the coordinated database/files/configuration backup only after confirming no accepted operational or accounting evidence would be lost.
- **Failure after accepted activity:** do not restore an older database over newer facts or delete protected journals. Preserve events and audits, isolate the affected workflow, and implement a reviewed forward correction with exact links to the original accounting. Source observation changes, money returned and journal reversals are distinct facts.
- **Late evidence affecting a closed period:** retain the actual event and its real date, inspect the closed-period warning and use the supported correction process. Do not reopen or silently rewrite immutable history.
- **Missing or changed private evidence:** restore the exact retained bytes from verified storage and recheck their digest. A different file with the same display name is not equivalent evidence. Preparation must remain blocked while required evidence is unavailable.

After any recovery, repeat the relevant reconciliation and backup-restore checks and retain their results with the incident. No recovery step may waive an unexplained control balance, bypass current authorization or manufacture external approval.
