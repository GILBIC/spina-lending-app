# Guest CIF + Loan Application Design

**Status:** Approved product direction for GitHub #419.

## Goal

Allow a brand-new borrower to apply to SPINA before a Client account exists, while keeping the application outside `core.users`, outside official borrower identity, and outside loan/accounting records until Management approves it.

## Product flow

Signed-out users receive three clear choices:

1. **Sign in** — existing Client account flow.
2. **Apply for a loan** — new Guest CIF + Loan Application flow.
3. **Check application status** — reference plus verified one-time challenge before any status is returned.

The new-borrower flow is:

`Guest intake -> Submitted application -> Management review -> Approved borrower record -> existing SPINA-managed Client-account flow`

A rejected application never creates a Client account.

## New-client CIF boundary

The full CIF is required **only for a brand-new Client**. Existing Clients do not repeat the CIF on renewal.

The Guest CIF is a staging intake snapshot, not an official `lending.clients` row and not a `core.users` account. It stores only data materially needed to identify/contact the applicant, evaluate the request, and review required KYC evidence.

Minimum intake categories:

- full name and contact details;
- present and permanent address;
- basic employment/livelihood information;
- declared current income, essential expenses, and current debt payments needed for affordability review;
- requested loan product, amount, term, and purpose;
- evidence reference for an **eGov-verified National ID**;
- evidence reference for an **eGov-verified TIN ID**;
- **Meralco bill** evidence reference for address/location proof;
- **baseline face selfie scan** evidence reference from a live face scan that passes liveness checking;
- privacy/accuracy/consent acknowledgements.

The baseline face scan captured during the first CIF becomes the identity baseline used for later renewal face matching.

Do not revive the earlier overbuilt CIF. Do not collect extra personal data merely because a previous form contained it.

## Renewal identity requirements

A renewal is **not another CIF**.

The borrower renewal requirements are only:

1. **Signature**; and
2. **Face selfie scan**.

The renewal face selfie scan must:

- pass liveness checking; and
- match the baseline face scan enrolled from the Client's original new-client CIF.

Do not require the Client to submit the CIF, eGov-verified National ID, eGov-verified TIN ID, or Meralco bill again merely because the Client is renewing.

This design records the renewal rule now so later renewal work uses the same identity baseline. #419 remains focused on new-client intake and does not expand Task 2 into a renewal subsystem.

## Restricted evidence rule

Normal application rows store only controlled evidence references/metadata needed to connect the application to separately protected evidence. They do not store passwords, OTPs, MPINs, phone contacts, full unnecessary government-ID data, raw identity documents, raw face-scan media, or reusable biometric templates in the ordinary application row.

For the new-client face scan, the normal Guest Application row stores only `baseline_face_scan_evidence_reference`. The protected evidence service may later retain the minimum approved matching artifact needed for renewal verification, subject to the separate privacy/retention/access controls.

Real evidence upload/custody and live eGov/face-verification provider integration remain blocked until the restricted repository/privacy/retention/access controls are separately approved. Development tests use fake evidence references only.

## Persistence model

Create one additive pre-client table under the lending domain: `lending.guest_loan_applications`.

The table must have no foreign key to `core.users` and no foreign key to `lending.clients` at submission time. It owns a UUID primary key and a unique public application reference such as `APP-2026-000124`.

The first implementation keeps a deliberately small lifecycle:

- `submitted`
- `under_review`
- `approved`
- `rejected`

Review timestamps and the Management reviewer are recorded separately from applicant-supplied data. Approval may later record the promoted `lending.clients.id`; that link is nullable and can exist only after approval.

## Public submission

Expose a public FastAPI route dedicated to guest applications. It accepts only the approved lean fields, uses strict Pydantic input (`extra="forbid"`), normalizes obvious text/contact input, and persists one submitted application.

The required identity/address evidence inputs for a new applicant are references representing:

- eGov-verified National ID;
- eGov-verified TIN ID;
- Meralco bill; and
- baseline live face selfie scan.

Successful submission returns only:

- the application reference;
- `submitted` status;
- a short instruction to keep the reference for status checking.

Submission must not create:

- a Supabase Auth user;
- a `core.users` row;
- a Client role/permission;
- a `lending.clients` row;
- a loan, schedule, journal, contract, disbursement, or credential email.

## Status lookup

Public status lookup is never reference-only. The application reference first enters a one-time verification flow using an injectable verifier/OTP adapter. Development uses a fake adapter; no live SMS/email provider or real applicant communication is authorized by this feature branch.

After verification, the safe response contains only the reference, high-level status, submitted/reviewed timestamps, and a short safe Management note when appropriate. It must not expose KYC evidence, government-ID metadata, affordability inputs, reviewer internals, borrower/client IDs, biometric matching data, or credentials.

## Management review

Only authenticated Management on an approved device may review and decide guest applications in this first version. Existing Employee/Office Staff permissions are not broadened automatically.

Management can:

- list submitted/under-review applications;
- open the complete lean application for review;
- mark an application under review;
- approve or reject it with an auditable decision.

A rejection stores the decision and safe applicant-facing reason and creates no borrower/account.

An approval promotes the minimum stable borrower fields into one new active `lending.clients` record and records the new `client_id` back on the application. Promotion is idempotent: the same approved application cannot create two borrowers.

Client credentials remain owned by the already-merged Priority #3 pathway. After promotion, SPINA uses the existing protected `/api/v1/management/client-accounts` workflow for username/password creation and delivery. #419 must not duplicate or bypass that authentication logic.

## Loan boundary

Requested loan terms in the guest application are intake/request data only. Approval of the guest application is not approval of a financial loan and must not create `lending.loans` or any accounting/disbursement record.

The formal per-loan/per-renewal Loan Application and lawyer-approved contract/disclosure work remain separate. Renewal identity evidence is limited to signature + live face scan as defined above, but no legal wording is finalized here.

## UI scope

Implement the smallest complete surfaces needed for the approved new-client flow:

- signed-out Web/Mobile entry points;
- guest application form;
- status check entry;
- Management review queue/detail/decision;
- handoff from approved application to existing Client-account creation.

Reuse current SPINA components and API patterns. Do not add a new framework, workflow engine, generic form builder, separate authentication system, or renewal engine to #419.

## Testing and release boundary

Use strict RED -> GREEN TDD. The first RED slice proves the database separation before production migration code is added.

Required proof before merge includes:

- schema tests proving guest applications are separate from users/clients;
- new-client schema/API contracts for eGov National ID evidence, eGov TIN ID evidence, Meralco bill evidence, and baseline face-scan evidence reference;
- submission API tests proving no Auth/Client side effect;
- safe status-verification tests;
- Management-only review/decision tests;
- promotion idempotency tests;
- Web/Mobile entry and navigation tests;
- disposable PostgreSQL validation;
- full SPINA CI on the exact PR head.

This branch does not authorize production deployment, live applicant data, live identity/face upload, live eGov verification, live face-match provider calls, live OTP/email/SMS delivery, live database/Auth mutation, loan creation, contract execution, renewal execution, or release.
