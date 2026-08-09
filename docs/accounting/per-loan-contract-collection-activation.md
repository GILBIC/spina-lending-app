# Stage 5E.4.6B — Per-loan contractual collection activation

Stage 5E.4.6B replaces the broad loan-type contractual-allocation switch in the live collector path with the immutable per-loan activation state installed by migration 0036.

## Live switch

`lending.loan_contract_collection_activation_state` is the only activation switch used by the live contractual collection wrapper.

- No activation history: the loan remains on the established collection path.
- Latest event `activate`: contractual allocation may run only if every protected readiness check still passes.
- Latest event `deactivate`: mobile collection is blocked until Management explicitly reactivates the loan. It does not silently fall back to legacy date-based collection.
- Active event tied to an older schedule: collection is blocked until Management resolves the stale activation.

The older loan-type setting `mobile_contract_schedule_allocation_enabled` remains in legacy Stage 5E.4.4 code for compatibility but does not control the Stage 5E.4.6B live collection dependency.

## Activation readiness

Management activation requires the exact loan to be:

- active;
- mobile-collection enabled;
- using `direct_remaining_balance` mode;
- backed by a current signed-contract schedule registration;
- DPD data status `ready`;
- operational remaining balance equal to the unpaid contractual schedule;
- free from automatic Default, ECL amount/inclusion, or accounting posting readiness.

Activation and deactivation require `lending.contract_collection.activate`, an explicit confirmation, and a Management note. They append immutable audit events only.

## Collector behavior

For an active, current, ready per-loan activation, the existing Stage 5E.4.4 contractual rules apply:

- normal cash goes to the oldest unpaid contractual installment;
- ADV uses exact contractual due dates;
- ADV-covered day with no new cash is not PASS;
- partial payment leaves the installment unpaid until completed;
- PASS is permitted only when an installment is actually due and unpaid on that date;
- voided collection allocations no longer consume an installment;
- a wrong contract-controlled collection must be voided and reposted rather than edited in place.

The collector route receives the same per-loan activation state. Deactivated or stale-activation loans have mobile collection disabled rather than reverting to legacy handling.

## Management UI

Management receives a `Contract Collection` screen showing:

- active count;
- ready-to-activate count;
- contract verification and reference;
- DPD readiness;
- unpaid contractual amount;
- balance reconciliation;
- accounting safety;
- blockers;
- explicit `Activate for Collection` / `Deactivate` controls.

A note plus explicit confirmation is required before either state change.

## Safety boundary

Stage 5E.4.6B does not automatically activate any loan, create or infer a contract schedule, rewrite prior payments, classify Default/Non-default, calculate or post ECL, populate account 1190, change a loan balance/status merely because of activation, or post General Ledger entries.

Synthetic regression tests exercise contract frequencies, ADV/no-cash/PASS behavior, partials, void/repost, overpayment rejection, and per-loan independence before real borrower data is used for acceptance.
