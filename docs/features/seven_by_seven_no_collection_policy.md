# 7x7 No Collection protected policy

Updated: 2026-08-27 PH

This document is the current product/source-of-truth checkpoint for approved 7x7 No Collection behavior. It records the business rule separately from implementation status so incomplete wiring cannot be mistaken for finished financial behavior.

## Approved allocation and schedule rules

1. Older 7x7 Past Due is always paid first. Collector cannot bypass it.
2. A Management No Collection declaration shifts the affected installment and later operational schedule. The original signed contractual schedule and the Management declaration remain immutable evidence.
3. The No Collection date is an interest holiday for that borrower unless the affected signed installment is fully completed voluntarily on the original No Collection date.
4. Ordinary Payment must not silently consume a shifted No Collection installment while that installment is still future.
5. Partial voluntary No Collection cash stays attached to the affected signed installment as deferred/prepayment evidence. The No Collection shift and interest holiday remain.
6. A partial voluntary No Collection payment does not create another borrower-caused extension at day close on the original No Collection date. The row is already shifted. Borrower-caused extension is evaluated only when that row reaches its new operational due date and remains incomplete at official close.
7. If a client made a valid partial payment before Management later declares No Collection, that payment remains valid evidence. The unpaid remainder of the same installment moves with the shifted row.
8. If a client already fully completed the scheduled installment before Management declares No Collection, that borrower must not receive a new borrower-level No Collection shift or interest holiday merely because the area/date is declared No Collection. The completed payment remains normal.
9. Full voluntary completion on the original No Collection date removes exactly that borrower’s affected No Collection shift while preserving the original Management declaration as historical fact. Existing prior prepayment plus current receipt must reconcile exactly to the signed installment amount.
10. Cash beyond older Past Due plus the affected No Collection installment is true extra. SPINA must not guess its destination; borrower direction is required.
11. Consecutive No Collection declarations stack. Removing one borrower-completed shift must preserve all other valid No Collection shifts.
12. After official day close, a normal retroactive No Collection declaration is not allowed. It requires a Management Correction with reason and full audit trail.
13. A stale/offline Collector schedule cannot be trusted after Management changes the schedule. Server posting must reject stale state and require refresh. Cash already physically received while offline is pending/unposted until server validation succeeds.
14. If a full voluntary No Collection completion receipt is later voided, the borrower’s No Collection shift and interest holiday must be restored while immutable receipt/void/completion history remains. Ambiguous downstream history fails closed for Management reconciliation.
15. Management cannot silently reverse an original No Collection declaration after voluntary completion. A reviewed Management Correction is required with reason, approver, audit evidence, and recalculation preview.

## Current implementation status

| Rule / capability | Status | Current protection |
| --- | --- | --- |
| Older Past Due before affected NC installment | Implemented in planner | `plan_seven_by_seven_no_collection_voluntary_payment` sorts and consumes Past Due first. |
| Partial NC payment keeps shift + interest holiday | Implemented in planner | Returns `partial_shifted_prepayment`, `keep_no_collection_shift=True`, `keep_interest_holiday=True`. |
| No second extension on original NC day | Implemented by operational-date day-close semantics; explicit regression added | Day close only evaluates rows whose `effective_due_date` is the closed date. A shifted row is not due on the original NC date. |
| Partial payment before later NC declaration stays valid | Supported by schedule planner; explicit regression added | Existing allocation remains attached to immutable installment id while operational due date shifts. |
| Full payment before later NC declaration receives no shift/holiday | Approved, not fully wired | Management borrower-eligibility filtering still needs explicit repository/API handling. Current generic shift planner alone must not be treated as sufficient. |
| Explicit NC voluntary wire intent | Implemented | `NO_COLLECTION_VOLUNTARY` is canonical/idempotent input. |
| Verified NC posting context | Implemented | Locks/proves active verified schedule, exact active Management NC source, affected signed installment, Past Due, and existing allocation evidence. |
| Atomic NC receipt/evidence write | Pending | Verified requests still fail closed at the write boundary. |
| Immutable full-completion evidence schema | Implemented | Separate `voluntary_completion` adjustment plus `loan_no_collection_voluntary_completions`; source Management NC remains immutable. |
| Restore one shift while preserving consecutive NC history | Planner implemented | Completion restoration replay removes exactly one source NC and fails closed on schedule drift. |
| Direct Management reversal after affected payment | Protected | Existing Management reversal path rejects affected installments that already received payment. Dedicated reviewed correction workflow after voluntary completion is still pending. |
| Retroactive NC after official close | Approved, pending dedicated correction gate | Must not be implemented as a normal declaration. |
| Offline stale schedule | Server stale-route protection exists; pending-cash UX/persistence incomplete | Route revision conflicts force refresh. Dedicated pending/unposted cash handling still needs wiring. |
| Void full NC completion restores shift/holiday | Approved, pending | Requires immutable restoration/reversal evidence and replay validation. |
| Borrower-directed true extra after NC obligations | Planner rejects ambiguous extra | Full destination choices/wiring continue in protected extra-allocation work. |

## Protected implementation order

1. Finish exact-head CI; fix real failures before adding more financial writes.
2. Complete the atomic 7x7 No Collection voluntary receipt/evidence transaction.
3. Add explicit Management borrower eligibility for declarations made after a same-day full/partial payment: full completion is excluded; partial evidence is preserved and only the unpaid remainder stays shifted.
4. Add after-close Management Correction workflow for retroactive No Collection.
5. Add offline pending/unposted cash state and reconnect validation UX.
6. Add void-restoration path for full voluntary NC completion, including fail-closed replay on ambiguity.
7. Add reviewed Management Correction path for reversing an NC declaration after voluntary completion.

## Safety boundary

This policy does not authorize merge, Ready transition, auto-merge, acceptance/production deployment, protected backend restart, or protected/live database changes. Those remain separate Management-authorized actions.
