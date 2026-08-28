# Protected 7x7 Extra Principal Bridge Design

**Date:** 2026-08-28  
**Repository:** `GILBIC/spina-lending-app`  
**Starting commit:** `6be0b0861a49aebaf5551162cbe66ea84d06b7dd`  
**Working branch:** `codex/7x7-extra-principal-bridge`  
**Parent:** Draft PR #370, based on `mobile/ca4-collector-ui`  
**Roadmap:** Master Issue #296

## Outcome

Add one protected, intent-aware bridge for a borrower's explicit 7x7 Extra
Principal payment. The bridge must create one official immutable receipt and,
inside the same PostgreSQL transaction, apply an interest-free principal
reduction, shorten only the untouched operational tail, preserve the signed
schedule, classify unusable Advance as Refund Due, retain accounting/audit
evidence, reconcile all affected views, and store an exactly replayable result.

The same protected Management collection-void workflow must reverse the latest
eligible receipt by preserving every original event and reconstructing the
operational amount overlay from signed schedule evidence plus all still-active
valid adjustments. A physical Refund Due release permanently blocks automatic
reversal and produces a durable, exactly retryable conflict record.

## Authoritative Decisions

- The only modern intent that activates this bridge is
  `extra_as_principal_reduction`.
- The legacy parseable intent `voluntary_extra` remains rejected. It is not a
  protected borrower allocation choice.
- Past Due Interest and Today Interest must both be zero immediately before the
  Extra Principal receipt is accepted.
- The accepted receipt contributes zero interest and exactly the approved amount
  to principal.
- The signed contract and signed installment rows are immutable. Only
  operational overlay rows may change.
- Extra Principal shortens the schedule from the future tail. It may remove full
  rows and reduce one boundary row, but it may not move the reduction into an
  earlier settled or touched row.
- Existing Advance retained on a surviving boundary row remains installment
  specific. Advance made unnecessary by removed/reduced operational amounts is
  classified as a separate Refund Due owed by SPINA to the borrower.
- Refund Due is never payment, interest, principal, income, another Advance, a
  cross-loan offset, or an automatic future application.
- Management approval and physical release are separate events. Approval does
  not change collector field cash. Physical release does.
- Accounting remains explicitly Management-posted with
  `automatic_source_posting=false`.
- A released Refund Due cannot be recreated, netted, or collected automatically
  during reversal. It requires a later reviewed Management correction workflow,
  which is not created in this slice.
- The unresolved rule for a new daily amount when every future row is already
  touched remains out of scope and fail-closed.

## Existing Protected Primitives

The implementation reuses these systems instead of introducing parallel ones:

- `spina_backend_mobile/src/spina_mobile_collections/postgres.py` owns the outer
  transaction, idempotency-key advisory lock, canonical request hash, exact
  duplicate response, and conflicting retry behavior.
- `spina_backend_mobile/src/spina_mobile_collections/contracts.py` owns
  `PaymentAllocationIntent`, the canonical collection payload, and the official
  response contract.
- `gilbic_backend/src/gilbic_backend/seven_by_seven_collection_posting.py` owns
  official 7x7 receipt creation, authoritative row locks, route/device checks,
  financial replay, official balance, source transaction, and audit insertion.
- `gilbic_backend/src/gilbic_backend/seven_by_seven_extra_principal.py` owns the
  monetary tail-shortening and boundary-row planner.
- Migration `0106_add_7x7_extra_principal_operational_evidence.sql` owns immutable
  forward adjustment/item evidence, operational amount overlays, Refund Due
  classification, and forward validators.
- Migration `0107_align_7x7_operational_readers.sql` owns the current operational
  schedule, DPD, and active-Advance reader alignment.
- `gilbic_backend/src/gilbic_backend/collection_void_repository.py` owns the
  Management-only unremitted void transaction, immutable void snapshot, loan
  state restoration, audit, and notifications.
- Migrations `0067` and `0068` own exact protected 7x7 accounting-journal reversal
  and the final fail-closed void guard.
- `gilbic_backend/src/gilbic_backend/seven_by_seven_no_collection_completion.py`
  demonstrates reconstruction from immutable signed schedule history instead of
  blindly reversing the last mutable overlay.
- Migration `0089` demonstrates protected idempotent evidence functions whose
  exact retries return the same identity and whose changed retries conflict.

## Persistence Gap and Migration Decision

Migration 0106 is sufficient for forward persistence but is fundamentally
incompatible with the complete reversal contract:

- it has no reversal identity or link to `collection_transaction_voids`;
- it has no reversal idempotency key or canonical payload fingerprint;
- its immutable adjustment has no separately derived active/reversed state;
- its operational-amount validator authorizes only the forward item's `new_*`
  values, so a signed-history reconstruction cannot restore an earlier state;
- every Refund Due classification is always subtracted from active Advance;
- it has no Management approval or physical-release evidence;
- it cannot prove or preserve a blocked reversal attempt after a released refund;
- it has no immutable reconstruction snapshot/digest.

Migration history must remain immutable, so 0106 will not be edited. The next
migration is:

`gilbic_backend/sql/0108_add_7x7_extra_principal_bridge.sql`

It is forward-only and additive. Existing 0106 rows remain valid and active
unless a new immutable 0108 reversal row says otherwise. No production rollback
is attempted by dropping historical evidence; application rollback is compatible
because old readers continue to see the original 0106 structures, while the
release/void paths must remain disabled until code and migration are deployed
together.

## New Protected Evidence

### Reversal requests

`lending.seven_by_seven_extra_principal_reversal_requests`

- `id uuid primary key`
- `idempotency_key uuid not null unique`
- `canonical_request_hash text not null`
- `transaction_id uuid not null`
- `adjustment_id uuid not null`
- `requested_by_user_id uuid not null`
- `reason text not null`
- `outcome text not null` constrained to `completed` or
  `blocked_refund_released`
- `collection_void_id uuid null unique`
- `released_refund_amount numeric(18,2) not null`
- `result_payload jsonb not null`
- `requested_at timestamptz not null`

Rows are terminal and immutable. A blocked request commits only this evidence and
no financial mutation. This is required because a PostgreSQL exception would
otherwise roll the attempted-reversal evidence back with the financial work.

### Successful reversals

`lending.seven_by_seven_extra_principal_reversals`

- one row per original adjustment, transaction, collection void, and completed
  reversal request;
- expected and resulting operational versions;
- original and reconstructed operational totals;
- restored active Advance and cancelled outstanding Refund Due totals;
- source-history and reconstructed-state SHA-256 digests;
- actor, reason, and timestamp copied from the immutable void/request evidence.

`lending.seven_by_seven_extra_principal_reversal_items`

- one row per signed installment needed to prove reconstruction;
- signed amount/principal/interest snapshot;
- current-before and reconstructed-after operational values;
- removed-state before/after;
- active Advance before/after;
- active Refund Due classification before/after;
- exact last active adjustment identity after reconstruction.

Both tables are append-only and writable only inside the controlled reversal
session established by the collection-void trigger.

### Refund Due lifecycle

`lending.loan_unused_advance_refund_due_approvals`

- exact-retry idempotency key and canonical request hash;
- borrower, loan, originating adjustment, approved amount, Management actor,
  reason/reference, and approval timestamp;
- approval never changes cash custody or the original classification.

`lending.loan_unused_advance_refund_due_approval_items`

- allocates each approval exactly across original 0106 Refund Due rows;
- makes partial approval across multiple installments unambiguous;
- provides the exact upper bound later release items must reference.

`lending.loan_unused_advance_refund_due_releases`

- exact-retry idempotency key and canonical request hash;
- approval, borrower, loan, assigned collector/releasing actor, amount,
  physical-release timestamp, evidence reference/digest, and result payload;
- a release requires prior approval, may not exceed approved/outstanding amounts,
  and is immutable.

`lending.loan_unused_advance_refund_due_release_items`

- allocates each release exactly to one or more previously approved 0106 Refund
  Due rows;
- ensures released totals cannot exceed classification totals;
- preserves `Unused Advance released`, `Cash returned to client`, and
  `Advance remaining` as separate values.

Derived views expose classified, approved, released, outstanding, reversed, and
reversal-blocking amounts without updating or deleting original rows. The active
Advance view subtracts only active Refund Due classifications. A successful
reversal deactivates an unreleased classification through the derived view; it
does not delete it.

## Forward Posting Flow

1. The existing collection executor takes the idempotency advisory lock and
   checks the stored canonical request hash.
2. The existing 7x7 bridge locks device sequence, loan/date, route, client, loan,
   loan state, active signed schedule/registration, operational version and rows,
   active Advance, active adjustments, and current allocation history.
3. A 7x7 Payment branches to Extra Principal only for
   `extra_as_principal_reduction`. Legacy `voluntary_extra` fails closed.
4. Protected financial replay proves Past Due Interest and Today Interest are
   both zero and that the pending event contributes zero interest.
5. The existing planner produces tail removals, at most one boundary reduction,
   retained Advance, and Refund Due classifications.
6. The existing official receipt/source transaction is inserted once with intent,
   route revision, state versions, source identity, planned adjustment identity,
   retained Advance, Refund Due, and reconciliation coordinates in `details`.
7. The 0106 adjustment/items, operational amount upserts, Refund Due rows, and
   operational version update are written under existing guards.
8. Existing contribution, receipt, audit, notification, accounting-readiness,
   and route-revision behavior completes.
9. A post-write reconciliation reloads all persisted rows and proves cash,
   receipt, zero interest, principal, balance, operational rows, Advance, Refund
   Due, adjustment, accounting readiness, and audit identities agree.
10. The existing executor writes the idempotency result in the same transaction.
    The stored response includes the adjustment identity and Refund Due result so
    an exact retry returns the same complete result.

Any error rolls back the receipt, adjustment, overlays, Refund Due, audit,
accounting readiness, notifications, route change, and idempotency row together.

## Reversal and Replay Flow

1. Extend the Management void request with an optional idempotency key. It is
   mandatory when the transaction owns an Extra Principal adjustment and remains
   optional for legacy non-Extra-Principal voids.
2. Lock the idempotency key, transaction, loan, signed schedule, operational
   state, adjustment history, Refund Due lifecycle, collection void state, and
   accounting posting/reversal state.
3. An existing request with the same canonical hash returns its stored terminal
   result. A changed retry conflicts.
4. If any related physical release exists, insert one immutable
   `blocked_refund_released` request, commit it without financial mutations, and
   return HTTP 409 with the same result on exact retry.
5. Otherwise create the existing collection-void snapshot, insert the completed
   reversal request, and update `collection_transactions.is_voided` in the same
   transaction.
6. A new trigger ordered after the void-evidence guard and before accounting
   reversal reconstructs every operational amount from signed installment
   evidence plus all non-voided active Extra Principal adjustments except the
   target. It verifies the current overlay matches replay before writing anything.
7. Insert immutable reversal header/items, update operational overlays using the
   controlled reconstruction guard, increment the operational version, and
   derive active Advance/Refund Due from immutable history.
8. Existing 0067 accounting reversal runs if an explicit protected journal was
   posted. An unposted source has no journal to reverse.
9. Final operational and accounting guards prove the exact reconstruction,
   collection void, immutable original evidence, and any journal reversal all
   agree before commit.
10. A standalone replay verifier performs the same signed-history reconstruction
    read-only and compares its digest and every row with persisted operational
    state.

Operational principal replay and Advance/Refund Due replay are deliberately
separate proofs. The operational amount overlay is reconstructed only from the
signed rows plus active, receipt-dated principal-reduction events. Each event may
alter only rows whose effective date was future to that receipt; due/past rows
remain untouched. Active Advance and Refund Due are then reconciled from their
own immutable allocation, classification, approval, release, and reversal
histories. This preserves interleaved Advance receipts instead of incorrectly
treating them as properties of a principal event.

## API and Response Compatibility

- Existing scheduled Payment, Advance, Pass, Regular, No Collection, Combined
  Pay, remittance, and accounting endpoints retain their existing wire shapes.
- `PostedCollection` gains optional immutable result metadata. Existing clients
  may ignore it.
- Collection duplicate lookup reads the stored result payload rather than
  rebuilding a smaller response, ensuring exact forward retry equivalence.
- Management collection void accepts `idempotency_key`; it is required only for
  Extra Principal reversals.
- Refund Due approval and physical release use dedicated protected endpoints and
  permissions because approval and release are distinct authorized actions.
- No mobile UI is added in this bridge branch, consistent with the authorized
  slice. The APIs are suitable for the later Management/Collector app workstream.

## Accounting and Custody Boundaries

- Receipt cash remains the immutable amount physically received.
- Extra Principal contributes zero interest and the approved amount to principal.
- Existing protected 7x7 source-event accounting preview/draft/posting remains the
  only journal subsystem.
- The bridge writes exact source evidence and readiness; it never posts a journal
  automatically.
- Existing 0067/0068 reversal remains the only journal reversal path.
- No new account or recognition rule is invented for Refund Due. Where an exact
  protected accounting treatment is not already ready, the readiness result is
  explicitly blocked for Management review.
- Approval does not change custody. A physical release is a separately itemized
  cash outflow and is included in the existing collector cash-accountability and
  remittance reconciliation calculations without altering the original receipt.

## Failure Semantics

Use existing domain error families and explicit codes. Required new protected
codes include:

- `seven_by_seven_extra_principal_intent_required`
- `seven_by_seven_extra_principal_interest_outstanding`
- `seven_by_seven_extra_principal_state_stale`
- `seven_by_seven_extra_principal_plan_mismatch`
- `seven_by_seven_extra_principal_reconciliation_failed`
- `seven_by_seven_extra_principal_reversal_idempotency_required`
- `seven_by_seven_extra_principal_reversal_idempotency_mismatch`
- `seven_by_seven_extra_principal_reversal_refund_released`
- `refund_due_approval_idempotency_mismatch`
- `refund_due_release_idempotency_mismatch`
- `refund_due_release_not_approved`
- `refund_due_release_exceeds_outstanding`

Database constraint/trigger failures are translated to the corresponding stable
API conflicts or rejections. Unexpected exceptions are not swallowed and cause a
complete rollback.

## Verification

The implementation must add persisted-state tests for all 36 required scenarios
from the work order, plus focused coverage for:

- the approved modern intent and rejection of the legacy intent;
- exact duplicate response metadata;
- immutable blocked-reversal attempt evidence;
- partial and complete Refund Due approval/release allocation;
- collector cash decreasing only on physical release;
- operational replay with multiple earlier active adjustments;
- trigger ordering with unposted and posted 7x7 accounting sources;
- migration upgrade from 0107 and clean bootstrap through 0108.

Validation runs in the work-order sequence: syntax, focused unit tests, planner,
posting/reversal integration, migration/bootstrap, disposable PostgreSQL,
accounting/reconciliation, idempotency/concurrency, 7x7 regressions, Regular
regressions, backend suite, lint, formatting, typing, financial controls, and
clean-tree verification.

After a relevant commit is pushed, create only a Draft PR to
`mobile/ca4-collector-ui`, reference Draft PR #370 and Master #296, and wait for
all five permanent CI lanes on the same exact head. Do not merge, mark Ready,
deploy, restart a protected backend, or apply migration 0108 to protected/live
data.
