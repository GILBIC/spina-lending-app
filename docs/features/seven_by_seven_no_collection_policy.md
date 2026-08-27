# 7x7 No Collection protected policy

Updated: 2026-08-27 PH

This document is the current product/source-of-truth checkpoint for approved 7x7 No Collection behavior. It records business rules separately from implementation status so incomplete wiring cannot be mistaken for finished financial behavior.

## Approved allocation and schedule rules

1. Older 7x7 Past Due is always paid first. Collector cannot bypass it.
2. A Management No Collection declaration shifts the affected installment and later operational schedule. The original signed contractual schedule and the Management declaration remain immutable evidence.
3. The No Collection date is an interest holiday for that borrower unless the affected signed installment is fully completed voluntarily on the original No Collection date.
4. Ordinary Payment must not silently consume a shifted No Collection installment while that installment is still future.
5. Partial voluntary No Collection cash stays attached to the affected signed installment as deferred/prepayment evidence. The No Collection shift and interest holiday remain.
6. A partial voluntary No Collection payment does not create another borrower-caused extension at day close on the original No Collection date. The row is already shifted. Borrower-caused extension is evaluated only when that row reaches its new operational due date and remains incomplete at official close.
7. If a client made a valid partial payment before Management later declares No Collection, that payment remains valid evidence. The unpaid remainder of the same installment moves with the shifted row.
8. A normal same-day payment that already fully completed the scheduled installment before Management declares No Collection remains a completed normal payment; that borrower must not receive a new borrower-level shift or interest holiday merely because the area/date is later declared No Collection.
9. **Advance follows the installment.** If the installment due on the Management No Collection date was already fully prepaid by Advance, the installment still moves with the No Collection schedule shift and the Advance remains attached to that same immutable installment. Do not detach, reassign, or convert the Advance merely because the operational due date moves.
10. Full voluntary completion on the original No Collection date removes exactly that borrower’s affected No Collection shift while preserving the original Management declaration as historical fact. Existing prior prepayment plus current receipt must reconcile exactly to the signed installment amount.
11. Cash beyond older Past Due plus the affected No Collection installment is true extra. SPINA must not guess its destination; borrower direction is required.
12. Consecutive No Collection declarations stack. Removing one borrower-completed shift must preserve all other valid No Collection shifts.
13. After official day close, a normal retroactive No Collection declaration is not allowed. It requires a Management Correction with reason and full audit trail.
14. A stale/offline Collector schedule cannot be trusted after Management changes the schedule. Server posting must reject stale state and require refresh. Cash already physically received while offline is pending/unposted until server validation succeeds.
15. If a full voluntary No Collection completion receipt is later voided, the borrower’s No Collection shift and interest holiday must be restored while immutable receipt/void/completion history remains. If the void occurs before official day close and an applicable Management No Collection declaration already exists, the No Collection shift/holiday is automatically reapplied. After official day close, use Management Correction.
16. Management cannot silently reverse an original No Collection declaration after voluntary completion. A reviewed Management Correction is required with reason, approver, audit evidence, and recalculation preview.

## Current implementation status

| Rule / capability | Status | Current protection |
| --- | --- | --- |
| Older Past Due before affected NC installment | Implemented | Protected planner consumes older Past Due first. |
| Partial NC payment keeps shift + interest holiday | Implemented | Partial affected cash remains deferred/prepayment evidence. |
| No second extension on original NC day | Implemented + regression | Day close only evaluates rows operationally due on that date. |
| Partial payment before later NC declaration stays valid | Implemented in schedule planner + regression | Existing allocation remains attached to immutable installment id while the operational due date shifts. |
| Normal full payment before later NC declaration receives no shift/holiday | Partially wired | Generic eligibility guard exists; Management repository/API still need source-aware final handling. |
| Fully prepaid Advance target still moves with NC | Approved; source-aware wiring pending | Current Management eligibility work must distinguish Advance evidence from normal same-day completion. |
| Explicit NC voluntary wire intent | Implemented | `NO_COLLECTION_VOLUNTARY` is canonical/idempotent input. |
| Verified NC posting context | Implemented | Locks/proves active verified schedule, exact active Management NC source, affected signed installment, Past Due, and existing allocation evidence. |
| Atomic NC receipt/evidence write | Implemented + real disposable PostgreSQL regression | Partial deferment, later same-day completion, immutable completion evidence, financial replay, rollback protection, and idempotent retry are proven. |
| Immutable full-completion evidence schema | Implemented | Separate `voluntary_completion` adjustment plus `loan_no_collection_voluntary_completions`; source Management NC remains immutable. |
| Restore one shift while preserving consecutive NC history | Implemented planner | Completion restoration replay removes exactly one source NC and fails closed on schedule drift. |
| Direct Management reversal after affected payment | Protected | Existing reversal path rejects unsafe affected-payment reversal; dedicated reviewed correction workflow remains pending. |
| Retroactive NC after official close | Approved, pending dedicated correction gate | Must not be implemented as a normal declaration. |
| Offline stale schedule | Server protection exists; pending-cash UX/persistence incomplete | Route revision conflicts force refresh. |
| Void full NC completion restores shift/holiday | Approved, pending full wiring | Before-close automatic reapplication and after-close Management Correction are the approved behavior. |
| Borrower-directed true extra after NC obligations | Planner rejects ambiguous extra | Full destination choices/wiring continue in protected extra-allocation work. |

## Protected implementation order

1. Finish the source-aware Management borrower eligibility distinction: normal same-day full completion is excluded, fully prepaid Advance still moves with its installment, and partial evidence remains attached while the unpaid remainder moves.
2. Add after-close Management Correction workflow for retroactive No Collection.
3. Add offline pending/unposted cash state and reconnect validation UX.
4. Add void-restoration path for full voluntary NC completion, including before-close automatic NC reapplication and fail-closed replay on ambiguity.
5. Add reviewed Management Correction path for reversing an NC declaration after voluntary completion.
6. Continue borrower-directed true-extra destination wiring and remaining protected 7x7 schedule work.

## Safety boundary

This policy does not authorize merge, Ready transition, auto-merge, acceptance/production deployment, protected backend restart, or protected/live database changes. Those remain separate Management-authorized actions.
