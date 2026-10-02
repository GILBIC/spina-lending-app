# Collector surplus verification — 2 October 2026

This receipt separates implemented behavior from release and execution limits.
PR491 depends on Treasury PR490 at08c31edd. It remains a Draft: these checks do
not authorize production migration, feature enablement, real money or account
grants. Source and exact-head CI must be reconciled before final acceptance.

## Financial and access checks

Backend implementation with review corrections passed 116 tests against a newly bootstrapped
disposable PostgreSQL database through migration0138. That run includes existing
Treasury acceptance and thirteen independent integration guards. It covers:

- Exact, over, short and zero-count handovers; current designated recipient and
  source evidence; one accepted receipt and separately identified credit.
- Partial cash return, different-wallet principal plus a separate fee, actual
  incoming reversal, retained-cash disputes and opening capacity/overlap.
- Current authorization on execution and recovery, own/staff scope, private-file
  loss, changed payload, independent approval and concurrent capacity checks.
- Full rollback after forced outcome failure, source-aware reconciliation review,
  preserved close snapshots and safe unpaid cancellation without money movement.
- A verified debit whose source link conflicts stays visible and unpaid. The
  reservation remains; cancellation and a different payout are blocked. An
  explicit current review can link that same event without another movement.
- Frozen credit cannot advance to a linked payout. Delayed receipt appends a new
  acknowledgment without altering history, and settlement requires the latest
  statement. Original phase evidence remains required during request recovery.
- Opposite cross-account recoveries acquire consistent locks. A frozen source
  stays unresolved in source summaries even when its outstanding amount is zero.

A populated synthetic backup-and-restore drill passed. All eleven new tables
contained records; restored paid-return, acknowledgment, event and remaining
credit relationships and private file bytes matched. Database/file corruption
checks and cleanup passed. This is a synthetic recovery proof, not proof that a
particular production backup contains the new schema.
The final drill took 28.672 seconds; its migration0138 SHA256 is
`93780a70bbb3bace4578c10a729f2af82a55564b569203855c26ee0e7d3e5d97`.

New backend modules passed scoped Ruff, Pyright and Bandit checks. Existing
repository scanner findings remain subject to the unchanged CI regression gates;
no baseline waiver was introduced. Both clients are tested against serialized
responses produced by the actual disposable backend services.

## Platform and final release evidence

Web tests passed 1,288/1,288 after independent review corrected financial phase
validation, recovery ownership and own-export privacy. Genuine failing probes preceded the corrections. A further
client test proves malformed submission and recovery responses retain the same
request until a valid GET result arrives, with only one POST. Syntax checks
cover 240 modules; the production build passed. Parent and child recovery/retry
both complete the original form exactly once; an unchanged recovered draft
cannot silently become a second submission. Own records and export envelopes
reject fields outside the server-defined safe projection.

Synthetic browser checks cover ten named views at three widths (30 samples),
two role destinations, keyboard access and private file/draft preservation.
Three installed Windows browser app-mode samples passed. The native layout
matrix covers 27 width/text configurations plus keyboard and unknown-outcome
cases. Android's full suite passed 1,224 tests with one skipped before the last
seven privacy-boundary regressions were added. The final source passed 189
focused tests and the analyzer with fatal informational findings enabled. The
full suite on the exact published source remains a required CI gate.

Native recovery now loads the submitted attempt's correct authorization and
retained mode when reopening through either Treasury entry. An unavailable
authorization read preserves the pending journal and files. Own records,
nested facts, declared result slots and raw export envelopes reject unexpected
private metadata before display or sharing.

Independent backend review resolved all five findings with current database
evidence. Independent client review resolved all five finding groups and checked
the final privacy guard with its exact regression. Exact-head CI is pending at
source publication and must be verified separately.
The PR check run and current completion handoff identify the published revision;
dependency CI alone does not establish this feature's acceptance.

Native widget captures use the production Android theme with Android's Roboto
font fallback loaded into the test renderer. They do not establish physical
phone, emulator, TalkBack, camera or real provider acceptance. Windows synthetic
checks use the installed browser's app mode, the runtime used by `spina_pc`.

## Explicit unavailable execution paths

Future credit application can retain own intent but cannot apply credit until
the protected custody split exists. Historical borrower correction, inclusion
of disputed cash in a later acceptance, and automatic liability GL posting are
also unavailable. These paths return explicit blockers or recovery states;
neither a saved request nor a balanced cash reconciliation makes them complete.

Actual operational opening figures, permissions, rollout and owner acceptance
are separate release inputs. The implementation seeds none of them.
