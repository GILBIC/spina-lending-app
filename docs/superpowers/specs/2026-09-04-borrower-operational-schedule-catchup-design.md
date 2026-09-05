# Borrower Operational Schedule + Catch-up Design

Date: 2026-09-04
Authority: Management direction + Master Issue #296 + current Notion/Create State checkpoint
Base revision: `ae01b75769836ecde5e30682c70505931bddb305`

## Scope

This slice fixes Priority #1 only: borrower-caused schedule movement, catch-up allocation, Past Due/Advance gating, and authoritative operational schedule reads. It does not implement the later one-tap UI, CIF, legal contract text, iOS, deployment hardening, backup/security hardening, or branch-governance work.

## Locked product rules

1. Signed/contractual installment identity, due dates, and contractual amounts remain immutable evidence.
2. If a scheduled installment is not fully satisfied when that collection date is finalized, the borrower-caused operational schedule extends by one cadence slot. The affected installment and every later active installment move forward one operational slot.
3. Repeated unresolved collection dates can extend the same unpaid installment repeatedly. Extension is therefore not equal to the number of currently unpaid installment rows.
4. A later normal payment above the current required amount is catch-up before it is Advance. A fully covered additional future installment can reduce one active borrower-caused extension slot. Multiple fully covered catch-up installments can reduce multiple slots.
5. Partial catch-up may allocate toward the next shifted installment, but it does not remove a full extension slot until the additional installment is fully covered.
6. Advance is unavailable while the borrower has Past Due / active borrower-caused schedule extension. The borrower cannot skip Past Due/catch-up and prepay farther future rows.
7. Only true excess after current due + catch-up is satisfied can use the existing explicit Advance / Principal Reduction (Regular) or Advance / Extra Principal (7x7) rules.
8. Management No Collection stays a distinct audited reason. Existing Advance remains attached to the same immutable installment when an operational date moves.
9. Normal reads must not invent a second schedule engine or mutate dates. Collector, Client Web, and Mobile must consume the same persisted operational dates.
10. Management previously rejected a formal daily Open/Close Business Day workflow. Schedule finalization therefore must be idempotent and server-authoritative without adding a new mandatory daily-close screen.

## Example

Contract: 120 x ₱100 = ₱12,000 total.

- Day 5 receives ₱0 -> after Day 5 is final, installment 5 moves to Day 6; installment 6 moves to Day 7; maturity moves from Day 120 to Day 121.
- Day 6 normal ₱100 -> pays the shifted current installment; one extension slot remains.
- Day 6 normal ₱150 -> ₱100 current + ₱50 catch-up toward the next shifted installment; the extension remains until that catch-up installment is fully covered.
- Day 6 normal ₱200 -> ₱100 current + ₱100 catch-up; the remaining schedule contracts by one slot toward the base schedule.
- If Past Due/active borrower extension exists, an Advance instruction is rejected.

## Architecture

### Pure schedule transformation

Add pure planners beside `rolling_schedule.py`:

- borrower shortfall forward shift: reuse the same structural rule as No Collection — the affected current row moves to the next row's current effective date, every later row takes the next row's date, and only the tail requires cadence arithmetic;
- borrower catch-up contraction: do not rewrite already-reached/settled historical rows. Once one or more additional future installments are fully covered as catch-up, move only the later remaining schedule backward by that many existing operational slots. This restores future maturity without rewriting cash/receipt history.

Pure planners preserve installment IDs, contractual dates, and allocation evidence.

### Persistent state

Generalize the existing audited operational schedule infrastructure instead of creating a second competing authoritative schedule:

- `loan_schedule_operational_state` tracks both operational version and active borrower extension slots;
- `loan_schedule_adjustments` gains a generic event date and borrower adjustment types;
- `loan_schedule_adjustment_items` remains immutable old/new effective-date evidence;
- `loan_installment_operational_dates` remains the current authoritative effective-date overlay;
- every borrower shortfall/catch-up change is transactional, versioned, audited, and invalidates stale route revisions just like Management No Collection.

The migration number must be chosen only after checking the repository's duplicate `0109_*` history; do not assume a numeric sequence silently.

### Catch-up allocation

Protected normal payment allocation changes from:

`Past Due / Due Today -> explicit extra`

to:

`current operational due -> borrower catch-up rows while active extension exists -> explicit true extra`

Catch-up gets a distinct allocation basis so Past Due/promise progress and audit can distinguish it from Advance. A catch-up row is chronological and cannot be skipped. When enough catch-up rows become fully covered, the same transaction persists the corresponding schedule contraction before commit.

### Finalization boundary

Do not add a mandatory daily close UI. Add an idempotent backend finalization service that can safely finalize elapsed collection dates from authoritative PostgreSQL state. It must never treat an in-progress same-day partial receipt as final. It must be callable from a server-owned operational boundary and safe to retry; no schedule mutation may happen merely because a client opens a schedule view.

The integration point must be proven before this slice is considered complete.

## Safety / acceptance

- Regular and 7x7 both follow the same structural shift/catch-up schedule rules while keeping their protected product allocation internals.
- No stale Past Due + original Due Today double-stacking after a finalized shift.
- Repeated misses extend repeatedly.
- Catch-up can reduce extension but cannot move the remaining schedule earlier than allowed by existing operational history.
- Management No Collection remains separate and auditable.
- Existing Advance stays on its immutable installment.
- Same-day multiple receipts remain valid; no premature shift before the date is finalized.
- Same finalization request is idempotent.
- All financial writes are transactional and fail closed on stale version/state.
