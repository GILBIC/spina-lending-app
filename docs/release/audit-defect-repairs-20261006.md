# Audit repair release — 6 October 2026

This candidate repairs the six findings in the SPINA code audit. It does not activate the separate-book accounting program or claim complete lending-company accounting.

## Behavior

- Receipt void requires provable prior state. Management cannot substitute zero missed payments or empty history when an older receipt has no such evidence.
- Accounting exception filters use bound patterns with the real PostgreSQL driver.
- Financial statements read period and cumulative balances from one read-only repeatable-read snapshot.
- Android private payment, loan, statement and schedule pages clear private state on access/update denials and discard late responses from the denied or previous session. Transport failures preserve only the permitted cached state.
- Remittance submission binds the current source facts to the preview the sender reviewed. A stale or absent review identity is rejected before receipts are locked.
- New migration 0141 makes initial Treasury/Collector source coverage a prerequisite for review, preparation and close. Existing unsupported source families remain explicit blockers; manual journals do not manufacture protected source proof.

## Migration and compatibility

Production already contains 0140 Office screen signatures. Apply the new `gilbic_backend/sql/0141_add_accounting_source_close_guard.sql` only after the installed 0001–0140 migrations. This is separate from the unshipped accounting branch, whose book-identity numbering must be reconciled before that branch can be integrated.

Before rollout, preserve a coordinated database/private-evidence backup, exercise the candidate migration and clients in staging, and run `tools/run_audit_defect_validation.py` against an explicitly disposable loopback admin database. The release preflight now checks all four enabled source-guard triggers, including deferred commit checks. The candidate must fail deployment preflight if 0141 is missing or a required trigger is disabled.

The migration creates no balances, tax evidence, journals or company identity. It does not reopen historical periods. A late real-money record remains recordable and causes the closed-period queue to show review required. When source writers are active, close immediately asks for a retry and releases partial locks; it must not deadlock an actual cash acceptance.

Install the server migration before the matching backend and client release. Update browser cached assets and Android installations together with the new remittance contract. An older sender cannot omit its reviewed digest and submit an unreviewed batch; it must refresh/update before preparing another remittance. Existing submitted receipts and accepted cash retain their original identities and recovery paths.

The close inventory is intentionally conservative: Treasury/Collector facts lacking supported GL adapters block close. An empty initial source gate does not certify full lending/EIR/ECL/tax or annual-report completeness. Prior-period unpaid liabilities are not required to become zero.

## Verification

Retained local evidence is in `../checkpoints/audit-fixes-20261006`. Local integration passed 205 checks on the complete schema through 0141 (zero skips), 101 Collector recovery checks, and 1,839 Portal tests. The legacy repair selection passed 161 checks on schema 0140; two controlled 7x7 tests passed on their intended schema 0066. These selections overlap and must not be summed. Full CI, Android results and independent review are recorded in the pull request before readiness is claimed.

The validator creates its own unique loopback PostgreSQL database, installs the full candidate schema through 0141, runs the audit regressions with zero skipped/failed tests allowed, and removes only its own database. Existing bounded financial validators remain distinct historical/current workflow checks.

Physical Android acceptance and a production-data restore rehearsal remain separate from automated software checks.

## Recovery

An uncertain financial response must be recovered using its original command/review identity. Never create a fresh payment or remittance to test whether the original succeeded.

If migration fails before commit, verify rollback and retain the error before retrying. If the candidate fails before any new accepted activity, use the reviewed release backout process. Once real activity is accepted, preserve its facts and use a forward repair; do not restore an older database over new events or delete immutable journals.

## Remaining accounting program

Separate owner/company deployments, real opening balances and entity/tax facts, broad source adapters and liability reconciliation, the complete reporting package and remaining loan/correction lifecycles are outside this focused repair release. Their prior work remains on the separate accounting branch, unactivated.

