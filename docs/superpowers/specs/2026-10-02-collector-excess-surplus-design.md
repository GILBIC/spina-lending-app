# Collector Excess and Surplus — Design and Acceptance

Date: 2 October 2026, Asia/Manila. **Planning-only, separate owner-started Codex handoff.**

## Intent, authority and dependency

The owner requested **“Plan everything and create a new pr”** after the Collector Excess review. Create a separate workstream; do not append implementation to, overwrite, merge or deploy Cash & GCash PR #490. The objective is truthful counted remittance, identification of extra money, Collector-specific amounts due back, and controlled settlement of those credits across Web, Android and the installed Windows portal.

Authorities:
- [Collector Surplus definition, 9 September](https://github.com/GILBIC/spina-lending-app/issues/296#issuecomment-5593951480).
- [Forgotten borrower payment after remittance](https://github.com/GILBIC/spina-lending-app/issues/296#issuecomment-5594006550) and [prior-day/current-day separation](https://github.com/GILBIC/spina-lending-app/issues/296#issuecomment-5594035959).
- [Excess review](https://github.com/GILBIC/spina-lending-app/pull/490#issuecomment-5946508416) and [published-head recheck](https://github.com/GILBIC/spina-lending-app/pull/490#issuecomment-5946568155).
- Live GitHub; [Notion Current State](https://www.notion.so/3cd5ade7bef48106b2c2ff97182001dd); Create State project `69a61c48-f842-44ac-aa11-e987ffec4a36`; frozen Master #296 and its later approved scope. Do not edit Master acceptance boxes.

Planning branch is based on main `41a13eb59c9cc1b65a0a6a51f3b73db4a0895013`. **Implementation depends on the reviewed Treasury foundation from #490**, inspected at `a24d72baab623dbcce69f1a1c2d7316d1431b34f`. These are evidence snapshots, not permanent latest heads. #485–#489 contain separate active role/native work. Re-read all relevant refs before implementation. This PR initially contains only this specification and its plan; it does not include #490's application diff.

Default integration: after the Treasury dependency is merged through a separately authorized process, bring current main into this branch and implement here. While #490 remains unmerged, author tests/contracts against its exact reviewed source in isolation and report the dependency; do not copy a second Treasury implementation or silently stack/publish its entire diff. An alternative stacked base needs explicit owner/integration-owner approval and clear dependency accounting. This planning request does not authorize merging #490 or discarding anyone's work.

Source recheck: #490's `RemittanceReviewBody` still has only `review_acknowledged`, with extra fields forbidden. `TreasuryService` already supplies strict commands, current account authorization, immutable events and durable outcomes; its borrower-linked receipts are not a Collector-credit ledger. Reuse that infrastructure. The current Desktop is `spina_pc` secure Edge/Chrome portal app mode, not a retired Tkinter application. The previous review ran only an isolated copied request-model probe; no new financial/native/browser acceptance is claimed here.

## Approach and boundaries

Add a bounded **Collector settlement and credit extension inside Treasury**, connecting existing remittance, custody, source-correction, evidence, payout and accounting controls. Do not build a second cashbook, payroll engine, wallet integration or loan allocator. A UI-only field would not enforce count or duplicate safety; a generic positive variance does not establish who owns the money. The selected approach separates observed cash, accepted custody, identification, credit and actual settlement.

No real balances, wallet accounts, opening credits or cash counts have been supplied. All examples and execution tests are synthetic. Production entry stays disabled/unconfigured. Authoring and applying additive migrations to an explicitly disposable database is future implementation work; production migrations, financial operations, signing, provider integration, live capture, deployment, mark-ready and merge are not authorized.

Preserve exact server money; Regular/7x7/combined/advance rules; source chronology; independent borrower and recipient controls; online-only financial writes; existing attendance policy; immutable history; private evidence; current permissions and `automatic_source_posting=false`. No automatic payroll deduction, borrower offset, shortage offset, interest/income plug, new tax policy or forced balance adjustment.

## S1 — Keep five different concepts separate

| Concept | Required treatment |
| --- | --- |
| Unposted cash still with Collector | Unresolved source/custody; not money owed back by the office. |
| Accepted Cash Over — Pending Identification | Extra physical cash held by the receiver, source unresolved; not yet Collector credit. |
| Collector Surplus | Confirmed excess over corrected remittance obligations, specifically recognized as due back to that Collector. |
| Borrower extra payment / Refund Due | Existing protected borrower allocation/refund, not Collector property. |
| Cash/GCash reconciliation difference | Account observation/ledger difference requiring investigation, not automatic surplus. |

Formula for candidate positive difference is `max(actual_accepted_cash - cash_required_for_this_reviewed_settlement, 0)`. **The formula identifies excess; it does not prove entitlement.** Source corrections and existing approved settlement funding must be reflected before genuine Collector Surplus is recognized. Money merely counted but not accepted creates no office cash or credit.

The requirement is the corrected amount for the exact settlement, including legitimate prior-day correction obligations and accepted cross-route custody as supported by their source records. Owner-received borrower GCash is excluded from physical Collector cash. Never infer funding or ownership from a note, display role or equal amount.

## S2 — Actual count, current snapshot and shortage rejection

Provide a protected settlement preview containing remittance ID, collector, designated receiver, source-item IDs/versions and custody states, original collection dates, refunds, gross obligation, any explicit authorized credit funding, current physical-cash requirement, receiving physical-cash account, and a server digest/version. Expected values are read-only. Full item/refund evidence remains accessible.

Receiver enters **Actual cash counted**, count time and retained evidence/attestation. Money is PHP decimal text using existing Treasury limits; zero is valid for a count, not a payment; negatives, binary floating-point amounts and extra precision are rejected. Missing is unavailable, not zero. Record `counted_at`, server `recorded_at`, and `accepted_at` separately.

A short count is retained as a rejected count attempt with its difference and reason. It does not accept the full remittance, clear the sender's obligation, create a negative credit or consume old credit automatically. Reject the offered handover and leave custody with the sender under existing rules. If physical money was nevertheless retained by someone during a dispute, record a separate custody exception with real holder/amount; do not pretend it was returned, accepted in full or vanished. That exception cannot silently authorize partial remittance settlement.

Count and acceptance are separate auditable facts but may be one deliberate UI action for a normal exact/over handover. Acceptance locks current source, count, account, remittance and any authorized funding; stale/changed source requires re-review. No success on a merely resolved HTTP request. Exact result must identify count, remittance, actors, account, physical amount, funding, disposition, Treasury event and durable request.

Update every receiving entry point, including notification acceptance and mobile aliases, so no boolean-only path bypasses the new contract when enabled. Older clients receive an explicit update/count-required response, not a silently inferred actual count. Plain rejection remains supported with current recipient/permission checks. Old accepted remittances keep their evidence as it was; do not fabricate historical counts.

## S3 — Receive money once and retain pending identification

The accepted actual cash amount increases the receiver's physical-cash register once. The ordinary expected portion and extra portion are linked classifications of that same receipt, not additional receipts. Reuse existing remittance/transfer source links for ordinary custody and Treasury for the extra; publish one authoritative full-receipt projection without duplicated movement lines, audit or GL cash.

The normal obligation may clear upon full valid acceptance while additional money is held in a linked **Cash Over — Pending Identification** case. Its record includes the originating count/settlement, physical cash event, collector attribution, holder/account/context, unresolved amount, evidence and versioned resolution history. It does not imply the Collector owns the extra or remains short. Unknown money is not disposable operating income.

A case may be resolved in evidenced portions: recognized Collector credit, protected missing borrower payment, another identified existing source, or an actual authorized return to its verified owner. Sum of resolutions never exceeds received excess. Unresolved remainder remains visible. Do not assign an arbitrary borrower or fabricate an income source to close the case. Matching an already recorded cash event only links it, without adding cash again.

## S4 — Genuine per-Collector credit and permissions

Only authorized recognition after source review creates a Collector-credit entry. Preserve count and identification evidence, corrected source snapshot, actual collector identity and reason. The receiver and recognizing authority cannot approve their own credit; configure an independent authorized actor or keep the action blocked. Management role alone does not expose all private wallet records.

Use existing active user/device, owner identity and per-account authorization plus bounded capabilities: `treasury.collector_surplus.receive`, `treasury.collector_surplus.resolve`, `treasury.collector_surplus.settle`, and `treasury.collector_surplus.view`. Receiving also needs existing remittance authority and the actual designated-recipient check. Settlement needs authority on the paying account and verified credit scope. Do not seed broad Employee/Collector grants. A Collector may read their own safe credit/history projection without being granted the office's account history, and may request/acknowledge a return but not recognize or approve their own credit.

Retain immutable credit entries for recognition, actual return, explicit application and evidenced reclassification; current versions/balances are projections. No direct editable balance. For each credit, expose original recognized, subsequently reclassified, actually returned, explicitly applied, outstanding, reserved/in-progress and available-to-settle amounts. Reservations are a subset of outstanding, not a second liability or cash debit. Never settle more than the unreserved outstanding amount. Original remittance/account remains traceable even when return uses a different eligible paying account in the same context.

## S5 — Cash/GCash returns and uncertain outcomes

An explicit return request/reservation states exact collector, credit, amount, paying account and destination. Approval alone changes neither actual money nor outstanding credit; a reservation prevents competing payment/application. Full and partial returns are supported. Cancellation releases reservation only after proving no actual debit/handout occurred and there is no uncertain attempt.

For physical cash: retain independent payout evidence and recipient acknowledgment through an authorized workflow. For GCash/bank: verify actual outgoing transaction, exact recipient/amount/reference/time, using the existing Treasury event and scoped evidence controls. Never ask for MPIN/OTP or perform a transfer. A generic borrower-refund path cannot be used by inventing a Client ID for the Collector.

Source type `collector_surplus_return` links the dedicated approved return to one actual event. Return40 from credit100 leaves60. A GCash return100 with separately evidenced fee15 reduces that wallet115 but settles credit100; the fee is not silently charged to the Collector. A cash return changes physical cash only; a wallet return changes that wallet only. The original received cash is not deducted again unless it is the actual paying account.

A verified debit with destination not confirmed stays visible as **Return debited — confirmation pending**, with credit capacity reserved. Do not silently mark paid, release the reservation or resend. Successful confirmation settles the credit once. Client-side timeout first recovers the same durable phase/request. Phase IDs, frozen amount/payee/evidence and current authorization survive appropriate same-actor refresh but never transfer to another account/device. Store and display actual event versus request uncertainty separately.

## S6 — Explicit future application, never automatic netting

The September decision permits an explicitly audited future application; it is not permission for automatic offset. Implement a separate opt-in, server-reviewed **Apply credit to my later remittance** workflow, limited to the same Collector and context. Require the Collector's recorded request/acknowledgment, independent Management approval, exact target settlement, credit reservation, current versions and funding preview. No application to payroll, another Collector, a borrower or an already recorded shortage through this feature. This capability remains disabled until separately configured for use.

Preview keeps the **gross custody obligation**, **authorized credit application** and **new physical cash required** visible. On acceptance, the credit is settled by retaining that approved portion in the Collector's hands as repayment of the existing liability; it is not new office cash or a new borrower payment. Cash held on behalf of the operation decreases by both actual remittance and this expressly authorized release-to-Collector component, with separate immutable custody evidence.

Synthetic example: gross obligation1000, approved credit application100, physical requirement900. Count/accept900 and apply100 atomically; actual office cash increases900, Collector credit decreases100, custody1000 is explained as900 remitted plus100 retained as authorized credit repayment. Never assert that1000 physical cash was received. Without that approved funding preview, count900 against requirement1000 is rejected as short. Count890 is still short even with the approved100 application.

Legacy receipt/history/GL paths must understand the split before enabling execution. Provide the explicit request/preview and a truthful blocker if a required custody adapter is unavailable; do not disguise a partial cash acceptance as a completed implementation. Preserve failed/cancelled application reservations and no-duplicate consumption. A credit cannot fund two remittances or simultaneously fund a return. No automatic application merely because a credit balance exists.

## S7 — Forgotten payments and later reclassification

Use the existing protected correction/allocator service with actual borrower/loan/source evidence. Retain original PASS and locked remittance snapshots; corrective records have their true effective cash-receipt date and later entry time. Never guess dates, erase history, create today's payment or change the loan using a second calculator. Recompute historical borrower effects through the established protected chronology/closed-period rules; if unsupported, preserve the case and expose the blocker instead of applying today.

If cash remains with the Collector, correction recognizes the additional source obligation and a later **prior-day correction remittance**. If the office already received it as pending excess, the new linked borrower application consumes that existing cash evidence and resolves excess without another office inflow or obligation to hand over the same cash again. A receipt returned by another actor must still identify the actual original collector and current holder independently.

A remittance can aggregate prior-day correction100 plus actual today payment100, displaying two dated sources. If today's payment did not occur, only the prior-day100 exists. If previously recognized surplus proves to be a borrower payment, an authorized reclassification reduces the Collector credit and uses protected source correction without changing the original receipt count.

If part has already been returned/applied, do not overdraw the remaining credit, delete the payout, offset wages or invent a recovery receivable. Record **Reclassification requires recovery decision**, show amount still held and amount already settled, freeze the conflicting capacity, and require an explicitly authorized recovery/source treatment outside any unsupported shortcut. Preserve known actual cash and borrower evidence; the exception is not a declaration that the borrower did not pay.

## S8 — Opening positions, legal context and accounting

Owner/pre-registration, corporate legal and synthetic contexts stay separate. Account mapping does not imply legal ownership or authority to operate. Existing September direction is liability/amount due back, not income; exact legal-book coordinates require configured protected mapping. Recognition, source reclassification, return and explicit application have separate source keys. Use explicit Management review/post/reversal only; unmapped sources return a blocker, not a generic manual journal or invented account code.

Received cash changes once; later credit recognition or GL posting has no additional cash movement. Returning money settles a liability, not an arbitrary operating expense. A journal reversal alone does not return physical cash or reverse a provider transfer. Reclassification after a closed period retains the original source and applies existing correction/period controls.

Opening setup can retain independently evidenced Collector credits and unresolved excess already included in the opening physical balance. This adds a classified obligation/history anchor, not another cash inflow. Require actual counter/holder/cutoff/evidence and overlap check against real prior settlements; no historical remittance invented to fit a count. Missing opening credit is unknown, not0. Reserve account/source IDs and contexts uniquely so imported anchors cannot be recognized again as new credit. Do not seed actual money, overwrite initial capital, or publish real balances, staff information or wallet identifiers.

## S9 — Versioned storage, transactional integrity and rollout

Extend Treasury with bounded settlement counts, accepted settlement/source links, excess cases/resolutions, Collector credit entries and pending settlement actions. Original facts and resolution/credit entries are append-only; lightweight current-state/version projections may use existing guarded update patterns. Reuse private evidence, durable `treasury.outcomes`, current actor/account checks, immutable audit and exact-money types. Do not overload borrower `treasury.receipts` with fake clients or introduce a second generic event/outcome framework.

All money/credit mutations require stable request UUID, strict action/target/account/payload, expected versions and server-generated source digest where needed. Same-key replay returns the original result only after current authority checks; changed payload conflicts. Also enforce global original-settlement/source/event uniqueness across different request IDs, devices and reviewers. Acquisition order must cover the current Treasury account locks and legacy remittance/source/credit locks without inversion; publish the actual order and test it with two database sessions. No HTTP-to-self, fake device sequence or nested independent commit for a financial phase.

Acceptance, actual movement linkage, custody clearing, case/credit changes, audit and durable result must commit together for a single accepted phase. Count attempts/rejections are persisted deliberately without committing an accepted receipt. A forced failure leaves no orphan movement, credit or cleared obligation. Separate external observation/verification from later business application honestly; do not roll back reality merely because an allocation fails.

New permission/command/migration work is allowed in later implementation, with no production grants. Reserve the next unoccupied migration prefix at execution after reading live #490 and all current migrations; never edit0136/0137 in place. Preserve backups/restore, source-aware disable/rollback and private file checks. A feature flag defaults false and requires Treasury readiness. Once surplus state exists, disabling new entry cannot erase credits, unlock uncertain returns or enable cash-only interpretation. The retained runtime compatibility guard must reject incompatible rollback when relevant.

## S10 — Screens and cross-platform consistency

Management/designated receiver: existing Remittances adds current snapshot, actual count, difference, exact physical/cross-funded settlement confirmation, pending identification and linked history. Cash & GCash Control adds **Collector Excess** with Pending identification, Credits, Returns/applications and History. Permission-filtered local views, not a new top-level redesign. Staff may count/receive or prepare returns only with assigned authority; credit recognition/payout approval is independent.

Collector: **My excess credit** shows only own unresolved-case status, confirmed outstanding/available/reserved, returned/applied amounts and safe history. It must not label unidentified overage as spendable credit. Links identify exact remittance and receipt. Client sees only resulting authorized borrower correction/receipt with safe reason; no Collector-credit, payroll, private wallet or investigation information.

Retain draft text and selected evidence through unrelated refresh without extending authority. Use scoped retries, exact returned result checks, stable uncertain request, meaningful keyboard focus, readable money/reference wrapping and clear failed/empty/pending states. Stop/invalidate existing sharing before sensitive panels open; no widened sharing regions. Native uses actual production theme and standard targets/text scaling. Windows uses the existing shared portal, not a resurrected local ledger. Reports expose original required, corrected/funding basis, actual accepted, unresolved, recognized, paid, applied and outstanding separately; server totals never come from a filtered visible list.

## S11 — Required examples and tests

All examples are synthetic:
1. Due10000/count10000 accepted once; no case or credit.
2. Due10000/count10100: actual cash10100, normal10000, pending extra100; recognition after source review creates credit100 with no cash delta.
3. Count10100 but missing borrower100 established: corrected due10100, surplus0, source linked without new cash.
4. Remitted10000 while forgotten100 remains with Collector: no credit, protected prior-date correction and later handover.
5. Due10000/count9900: rejected shortage100, no full acceptance or automatic credit use.
6. Collector cash3000 plus owner-received/applied GCash1200: required physical cash3000; neither false short nor surplus.
7. Credit100/actual cash return40: remaining60; later wallet return60 plus fee2: wallet debit62, credit0, no new expense equal to the principal return.
8. Gross later obligation1000/authorized application100/count900:900 physical plus100 separately authorized retained-cash settlement; no cash1000 assertion.
9. Partial credit already returned then evidence of missing borrower payment: explicit recovery exception, not negative credit or wage deduction.
10. Opening cash includes existing credit100: opening counted once, credit anchor once, later return changes only the paying account.

Test all above with actual disposable PostgreSQL, plus duplicate/different retry, stale source, simultaneous accept/recognize/return/application, aggregate amount ceilings, tiny cent values, fees, denied actor/device/private-file access, count evidence tampering, two dates and transferred custody, forced audit/result failures, uncertain payout, closed reconciliation supersession, retained rollback guard and restore.

## S12 — Completion and owner gates

Keep the new PR Draft/open/unmerged. Product completion requires all implemented tasks reconciled to S1–S12, focused red/green evidence, integrated database tests, Web/Android/Windows checks, private exports and exact-head existing CI. A docs-only Green, isolated arithmetic/schema test, screenshot filename or reported upstream test count is not financial/native acceptance.

Any unavailable safe historical correction, explicit application custody adapter or legal GL mapping is an explicit blocker with a reproducible test, not a fake implemented action. Do not mark end-to-end support for that path. Native/emulator/TalkBack, real Windows and production setup are separately reported. Preserve latest project history in GitHub/Notion/Create State with SHA, dependency status, tested/blocked items and next action.

No actual count is required to build/test the software. Owner later privately supplies observed cash and any evidenced outstanding credits; activation is separate from planning or software readiness. The owner starts Codex; no automatic agent invocation or deployment is part of this PR.

Implementation plan: [2026-10-02-collector-excess-surplus.md](../plans/2026-10-02-collector-excess-surplus.md).
