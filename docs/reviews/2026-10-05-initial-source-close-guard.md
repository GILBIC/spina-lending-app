# Initial source close guard — migration 0141

This increment prevents formal review/preparation/close when authoritative Treasury or Collector accounting sources in that period have no supported GL adapter. It does not certify a complete accounting close. No mapping, legal book identity, journal, liability settlement or real opening figure is fabricated by the migration.

## Database interface

`accounting.period_source_blockers(period_id)` returns `source_type`, `source_id`, `effective_date`, `amount`, `reason`, and internal `account_id`. It reads original source tables even when no journal preparation exists. The API uses `account_id` to authorize Treasury account/private-history scope and must strip it from the response. `accounting.assert_period_source_complete(period_id)` raises SQLSTATE `23514` if a blocking row exists. Its public-facing error omits source IDs, dates and amounts: period-management permission does not grant private wallet history. The functions are private, invoker-authorized database interfaces; the API must enforce Management accounting authorization and existing Treasury account/private-history scope before revealing exact source rows. Redaction must not remove a blocker from the close assertion or its total count.

`accounting.period_source_close_state` returns period status, live blocker count, source status, `coverage_policy=treasury_collector_initial_v1`, and `comprehensive_source_coverage=false`. A clear result is named `initial_source_gate_clear`, deliberately not complete/ready/certified. A closed period with subsequently recorded evidence reads `closed_source_review_required`; immutable journal and close history stay unchanged.

The source rows are an inventory, **not an additive financial total**. Original cash, credit recognition and the associated entry can describe the same amount. Every row must remain identifiable in the UI; do not sum the inventory into a liability or cash balance.

## Covered sources and dates

- Treasury verified events, including their fees, use `effective_at`. All actual events block until a reviewed adapter exists, regardless of operational classification, application, source link or subsequent settlement. Correction movement lines use their own `effective_at` and remain separate even when their amount offsets the original cash.
- Nonzero active or superseded Treasury opening positions use their original `cutoff`. Draft or evidenced zero openings do not manufacture a financial journal requirement.
- Active Collector openings use their retained cutoff. Opening credit/entry rows also retain that cutoff rather than the date someone entered the historical record.
- Collector entries include recognition, opening, return and return reversal. Actual return/reversal event dates take precedence; an entry without a reviewed effective accounting date uses its immutable recording timestamp only as a conservative blocker. It does not authorize posting on that date.
- Collector original credit recognition, resolutions, accepted settlements and original excess cases are also inventoried independently of entry preparation. Settlement/case evidence uses accepted-at or the original opening cutoff as applicable. Recognition/resolution facts without a reviewed accounting-date policy use their retained recording timestamps as blockers.

All timestamp boundaries explicitly use `Asia/Manila`. Only source dates inside the selected fiscal period are included. The current status or nonzero balance of an earlier-period credit does not itself block a later period. This is not proof that every earlier-period control balance has been reconciled. A legitimate outstanding liability may remain unpaid; no zero-payables rule exists.

All Treasury contexts remain visible to this defensive gate. GL-to-context mapping is not implemented; silently excluding an owner/corporate context would misstate completeness. The separate book identity contract and future adapters must establish the correct legal context before any such source becomes clear.

## Enforcement and concurrency

Database triggers assert coverage before a fiscal-period transition into review/closed and before inserting a close preparation. A small wrapper preserves the existing preparation implementation and revalidates even when preparation is retried. Deferred constraint triggers recheck at transaction completion so a caller cannot normally insert a source later in its own closing transaction without detection. A failure rolls back the close journal, preparation/posting audit and period transition atomically. Exact replay of an already posted close remains governed by the existing protected replay contract; the live source status separately exposes later evidence.

The assertion takes `SHARE` locks on covered source tables in a fixed order and retains them to transaction end. A source writer that obtains its write lock first commits before the fresh inventory query; a close that obtains its locks first serializes subsequent recording until after the close commit. The latter event is retained and visibly requires historical review. No blanket source-recording trigger discards or rejects actual-money evidence merely because its effective date is already closed.

Close commands require `READ COMMITTED`. That allows the inventory query after a lock wait to see the source writer's committed row. A previously established repeatable-read snapshot cannot offer that guarantee and is rejected. Financial statement read transactions can still use repeatable read.

These relation locks are intentionally conservative and may briefly block unrelated Treasury/Collector writes during a close transaction. Keep close transactions short. Existing application write paths acquire multiple locks; a PostgreSQL deadlock victim must receive the existing failed-command response and retry, never be reported as recorded. The integration tests exercise the two direct writer/close orderings; they do not certify every multi-source operational workflow.

## Remaining work

No Treasury/Collector source is marked accounted merely because a journal has the same amount or an operational row says settled. Reviewed account/context adapters, exact immutable source-posting audit, date policy and control-account reconciliation are still required to clear these sources. This migration intentionally has no exception or waiver table.

Legacy collections/voids, releases/renewals, remittances, period-end EIR, current ECL measurement, tax obligations/amendments and initial capital remain outside this increment. Additional gaps include explicit cutover coverage, exact immutable source inventory digests, late-evidence remediation, comprehensive subledger reconciliation, and pending reviewed preparations that become blocked after late evidence. These are named follow-on work, not implied success when the initial source gate is clear.

## Verification

`gilbic_backend/tests/test_source_close_guard_postgres.py` is restricted to an explicitly opted-in loopback disposable database named `spina_treasury_validation_<24 hex>`. The root worker owns database startup and serial test execution; this slice never starts a PostgreSQL server or queries production.

The baseline regression is `test_review_rejects_unposted_actual_money` with test-only `SPINA_SOURCE_CLOSE_BASELINE=1`, which omits installing 0141 on a fresh baseline database. The expected baseline failure is `DID NOT RAISE`: the old review transition ignored the raw cash event. Unset that variable for the new behavior. Test installation is not an application bypass.

Focused command, with the root-provided disposable environment already configured:

```powershell
../.venv/Scripts/python.exe -m pytest gilbic_backend/tests/test_source_close_guard_postgres.py -q
```

The focused suite covers missing preparations, all three close gates and rollback, Manila boundaries, net-zero corrections, Collector entry/opening evidence, an earlier-period outstanding liability, preparation retry, deferred revalidation, successful empty close, late retained source status and two-connection serialization. A few tests intentionally retain committed synthetic fixtures in unique future periods so actual transaction boundaries can be proved without deleting immutable history.
