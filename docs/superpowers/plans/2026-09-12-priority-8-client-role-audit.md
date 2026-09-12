# Priority #8 — Client Role Completion Audit and Execution Plan

Date: 2026-09-12
Baseline: `main` at `fd69d2f01c68c4193dc92aa1e45a7113190054b5`
Branch: `priority-8/client-authoritative-schedule`
Scope: Client / Borrower on Web + Android only

## Guardrails

- FastAPI/PostgreSQL remains authoritative.
- Client surfaces may only render server-authorized Client data and invoke protected Client actions.
- No Client-side lending, allocation, accounting, balance, schedule, approval, or permission authority.
- Regular and 7x7 remain distinct.
- Do not copy unfinished Priority #4, #6, or #7 implementations into Priority #8.
- Priority #3 credential lifecycle remains authoritative; final Client account creation/linking occurs only after the successful first-loan release boundary.
- Production online payments remain disabled until provider settlement verification/webhook/idempotency hardening is complete and Management explicitly enables live mode.

## Read-only audit

### Backend / PostgreSQL already present

- Protected Client loan portfolio: `GET /api/v1/client/loans` plus mobile alias.
- Protected authoritative Client schedule: `GET /api/v1/client/loans/{loan_id}/schedule` plus mobile alias.
  - Resolves the authenticated Client user to the linked borrower.
  - Rejects loans that do not belong to that borrower.
  - Reads the persisted operational schedule source instead of deriving a second schedule.
  - Returns server-owned contractual maturity, operational maturity, extension count, past-due amount/count, row dates, amounts, statuses, remaining amount, and notes.
- Protected official payment timeline: `GET /api/v1/client/payments` plus mobile alias.
  - Uses official posted collection transactions and receipt numbers.
  - Payment proof is explicitly not connected and cannot post a payment.
- Protected renewal request APIs and richer renewal-workflow APIs.
- Protected support APIs.
- User-scoped activity notifications.
- Protected GCash capability, payment-intent creation, and intent-status APIs.
  - Server validates loan ownership, active-loan state, amount vs official balance, and idempotency.
  - Live checkout is blocked if settlement verification is not ready.
  - Provider checkout completion does not itself become an official SPINA payment.
- Protected account/device overview.

### Web Client Portal already present

- My account / device overview.
- My loans with Regular and 7x7 visually separated.
- Official payment history and receipt metadata.
- Renewal request submission/status.
- Support request submission/history.
- GCash capability/instructions display.
- Activity notifications.

### Android Client role already present

- Client dashboard.
- My Loans.
- Payments / official receipt metadata timeline.
- Renewal request/status surfaces.
- Support.
- Notifications.
- Profile/security/account devices.
- A server-capability-driven GCash payment page and repository exist, including protected intent creation/status refresh, but the active Payments flow still shows an old placeholder and does not navigate to that page.

### Existing tests relevant to Priority #8

- Backend Client loan and cross-borrower schedule authorization tests.
- PostgreSQL operational-schedule repository tests.
- Backend Client payment tests.
- Renewal/support tests.
- Portal role/presenter/API tests.
- Android Client dashboard, loans, payments and related repository/widget tests.

## Gaps and inconsistencies

### Highest-value independent gap

The authoritative Client schedule endpoint already exists and is ownership-protected, but neither the Web Client Portal nor Android My Loans consumes it. This leaves both surfaces unable to show the persisted contractual/current operational schedule even though the server already owns that data.

A related backend robustness defect exists: `ClientLoanScheduleUnavailable` is raised when a verified contractual schedule is not available, but the Client schedule API does not currently translate that domain state into a controlled HTTP response.

### Backend capability not fully surfaced

- Authoritative schedule is not surfaced in Web or Android.
- Web only shows GCash capability text; it does not expose the existing protected payment-intent/status flow.
- Android has the GCash page but the current Payments screen still shows a stale “Coming soon through Xendit” placeholder.
- Richer renewal workflow/status capability is not consistently surfaced across Web and Android.

### Genuinely missing Client capability

- Protected Client payment-proof upload/re-upload/correction/status/history workflow.
- Download/view endpoint for an official generated receipt artifact; current Client payment APIs expose receipt metadata only.
- Borrower Statement of Account / downloadable authoritative statement endpoint and matching Web/Android experience.
- Protected historical finalized loan-document access (loan agreement, disclosure, approved consent/release artifacts).
- Server-owned Client dashboard obligation summary covering current required payment, next payment date, and current overdue obligation in a single borrower-readable contract.
- Controlled profile/contact-edit workflow for any fields Management approves for self-service.

### Stale / misleading Client workflow or copy

- Android Client dashboard says My Loans contains “schedules” and uses “Open schedule and details”, but the page currently has no schedule view.
- Android Client dashboard says Payments contains a “statement”, but no Client statement endpoint/screen was found on the current baseline.
- Android Payments still displays a static Xendit “coming soon” placeholder although a capability-driven GCash page already exists.
- Renewal/account UI still contains guarantor / surety / solidary co-maker language that must be reconciled with the latest approved borrower-only Client renewal rules before Priority #8 calls the Client renewal experience complete.

### Duplicated / risky Client-side financial interpretation

- Android computes a payment-progress percentage locally as `paid_amount / principal`. This is presentation logic, but it can become misleading if the authoritative loan treatment (especially 7x7) differs from that ratio. Prefer a server-owned progress/status field when Priority #6 settles the final 7x7 contract.
- Android GCash pre-fills a suggested amount using `min(daily_amount, remaining_balance)`. The server revalidates the amount, so this is not authority, but the suggestion can differ from the true current obligation after advances/extensions. Replace the suggestion with a server-owned payable/current-obligation value before live payments are enabled.
- Web groups loan types using presentation-side classification. It does not calculate balances/schedules, but server-canonical type/status fields should remain the long-term source of terminology.

### Security / ownership observations

- Client loan portfolio and schedule are bound to the authenticated `actor.user_id` and linked borrower record.
- The schedule repository requires both the linked Client id and requested loan id; another borrower's loan resolves as not found.
- Existing API tests cover cross-borrower schedule denial and Client-role enforcement.
- GCash intent creation also derives available loans from the authenticated Client portfolio and intent lookup is user-scoped.
- Activity notifications are queried by authenticated recipient user id.
- No Client document/download endpoints currently exist to audit for protected-file enumeration; those endpoints must include ownership checks when introduced.

## Cross-priority dependencies

- Priority #3 — Credential lifecycle: merged foundation. Priority #8 consumes it; do not recreate account-linking rules.
- Priority #4 — First-loan onboarding/release: final Client account creation/linking is triggered only after successful first-loan release. Priority #8 begins after that boundary and must not invent an earlier account lifecycle.
- Priority #6 — 7x7 contract/accounting alignment: Priority #8 may render the authoritative schedule returned by the server, but must not add Client-side 7x7 duration/payment calculations. New summary semantics that depend on 7x7 rules should wait for the finalized server contract.
- Priority #7 — Web operational completion: use the shared Web shell and protected APIs. Keep Priority #8 changes in Client-specific modules where possible and avoid competing Web architecture.

## Smallest safe execution plan

1. **P8-1 — Authoritative schedule visibility (start now)**
   - Add a controlled Client-schedule-unavailable API response and regression test.
   - Add Web on-demand “View schedule” using the existing protected endpoint.
   - Add Android on-demand schedule repository/model/page using the mobile alias.
   - Render server values only; no local schedule engine or maturity calculation.
2. **P8-2 — Client Home obligation summary**
   - Define one server response for required payment, next payment date, overdue/current obligation and progress after Priority #6 semantics are settled.
   - Consume the same fields in Web + Android.
3. **P8-3 — Receipts, statement and finalized documents**
   - Add ownership-protected server download/view contracts for official receipt/statement/finalized immutable documents.
   - Reuse generated authoritative artifacts; do not generate competing Client-side PDFs.
4. **P8-4 — Payment proof evidence workflow**
   - Implement upload/re-upload/correction/status/rejection reason/history as evidence only.
   - Never post a collection from an upload alone.
5. **P8-5 — Online payment parity**
   - Replace stale Android placeholder with existing capability-driven flow.
   - Add equivalent Web payment-intent/status UI.
   - Keep live mode blocked until verified provider settlement/webhook/idempotency integration and explicit Management approval.
6. **P8-6 — Renewal cleanup**
   - Remove stale Client-facing role/language and expose request → review → approval → signing → release status without bypassing Management.
7. **P8-7 — Notifications/profile/security parity and final acceptance**
   - Remove duplicate/noisy notices, preserve controlled identity corrections, add ownership/enumeration tests, and run Web + Android acceptance on one candidate head.

## Current task

P8-1 — authoritative Client schedule visibility.

No merge, deployment, production data/Auth mutation, or live payment enablement is authorized by this plan.
