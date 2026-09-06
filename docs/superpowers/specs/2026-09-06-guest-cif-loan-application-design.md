# Pre-CIF Requirements Verification + CIF + Loan Application Design

**Status:** Approved product direction for GitHub #419; written spec updated with Management bypass and official Client-creation rules, awaiting final Management review before implementation resumes.

## Goal

A brand-new applicant must normally complete SPINA's minimum onboarding requirements before staff assists with the Client Information Form (CIF) or loan application. Management may make an auditable exception and bypass any or all of those pre-CIF requirements when Management chooses to accept the applicant anyway.

The pre-CIF gate prevents SPINA from spending time building a CIF or processing a loan request for an applicant who has not yet completed the required identity, residence, and field-verification checks, while preserving a controlled Management exception path.

## Product flow

Signed-out users keep three clear entry points:

1. **Sign in** — existing approved Client/Staff accounts only.
2. **Apply for a loan** — starts the new-applicant requirements-verification flow; it does **not** immediately create a CIF or loan application.
3. **Check application status** — reference plus verified one-time challenge before any status is returned.

The approved new-applicant flow is:

`New applicant -> Requirements verification -> Eligible for CIF -> create official inactive Client record -> Staff-assisted CIF + loan application preparation -> CIF Active -> activate Client record -> Management loan review -> approved borrower/account lifecycle`

The phrase **Apply for a loan** is the public entry point, but the first actual step is requirements verification. A financial loan application must not be submitted for final Management review until the pre-CIF eligibility decision has been made and the CIF is Active.

## Pre-CIF hard eligibility gate

The normal path requires all four requirements before SPINA marks the applicant **Eligible for CIF**:

1. **eGov-verified National ID**;
2. **eGov-verified TIN ID**;
3. **Meralco bill** accepted as the required residence/address evidence; and
4. **Collector residence visit** completed and passed.

These are the four onboarding requirements. The baseline face scan is **not** one of these four; it belongs to the CIF stage after eligibility.

Until the applicant is marked `eligible_for_cif` through the normal path or an approved Management bypass:

- do not create or assist with the full CIF;
- do not prepare/submit the loan application for processing;
- do not create a `lending.clients` row;
- do not create a `core.users` account or Client permissions;
- do not create a loan, schedule, journal, contract, disbursement, or release;
- show only a safe onboarding state such as requirements incomplete, under verification, or rejected.

## Verification roles and authority

The Collector is responsible only for the residence-visit part of the gate. The Collector may record the visit result, date, permitted notes/evidence reference, and their identity as the person who performed the visit.

The Collector **cannot** make the final **Eligible for CIF** decision and cannot bypass any requirement.

Authorized **Office Staff/Employee or Management** may make the normal eligibility decision only when all four individual requirements are verified as passed. SPINA must record who made the final eligibility decision and when.

Office Staff/Employee has **no bypass authority**.

## Management bypass

Management may bypass **any or all** of the four pre-CIF requirements and mark the applicant `eligible_for_cif` even when one or more requirements are missing, incomplete, rejected, or not yet verified.

A Management bypass is an auditable exception, not silent data editing. It must record at minimum:

- exactly which pre-CIF requirements were bypassed;
- a required non-empty Management reason;
- the Management user who authorized the bypass; and
- the authorization date/time.

The bypass should also create an immutable audit event in the existing audit trail.

The bypass applies **only** to the four pre-CIF requirements. It does **not** bypass:

- the CIF itself;
- the CIF baseline live face scan/liveness requirement;
- the five-year CIF lifecycle/re-verification rules;
- financial loan review/approval;
- contract/release controls; or
- Client-account credential controls.

## Lean pre-CIF record

Before CIF eligibility, SPINA keeps a small Applicant/Prospect verification record rather than an official Client account.

The record should contain only what is needed to manage the four checks and safely contact the applicant, including:

- application/reference number;
- applicant name and minimum contact information;
- controlled evidence reference/result for eGov National ID verification;
- controlled evidence reference/result for eGov TIN ID verification;
- controlled evidence reference/result for the Meralco bill;
- Collector visit status/result/date and Collector identity;
- final eligibility status, reviewer, and reviewed timestamp;
- Management-bypass metadata when a bypass is used; and
- the resulting `client_id` only after eligibility creates the official Client record.

Recommended lifecycle states remain deliberately small:

- `requirements_incomplete`
- `under_verification`
- `eligible_for_cif`
- `requirements_rejected`

No raw government-ID files, raw bill image, passwords, OTPs, phone contacts, or unnecessary identity values belong in the ordinary applicant row. Normal records keep only the minimum approved metadata/references; restricted evidence custody remains separately controlled.

## Official Client creation at eligibility

As soon as an applicant becomes `eligible_for_cif` — either because all four requirements passed or because Management used an approved bypass — SPINA creates exactly **one** official `lending.clients` row and links its `id` back to the pre-CIF record.

This promotion must be idempotent so the same applicant cannot create duplicate Client rows.

To fit the current `lending.clients` schema without inventing a new status solely for onboarding:

- create the Client with `status = 'inactive'`;
- keep `user_id = NULL`;
- generate the stable `client_code` once;
- copy only the minimum approved Client identity/contact fields needed for the CIF linkage; and
- do not grant Client permissions or create credentials.

The `client_id` then becomes the stable identity key for the CIF and subsequent loan application. Names are never used as identity keys.

When the CIF becomes Active, the Client row may transition from `inactive` to `active`. Client-account credentials still remain a separate downstream step.

## CIF boundary after eligibility

The full CIF is required only for a brand-new Client and can begin only after the applicant reaches **Eligible for CIF** and has the stable `client_id`.

Staff/Management assists the Client with the lean CIF. The CIF contains the approved stable/slow-changing Client information needed for onboarding, including:

- identity/contact information;
- present/permanent address information;
- basic employment/livelihood information;
- privacy/accuracy acknowledgements;
- Client signature and verifying-staff record; and
- **baseline live face selfie scan** that passes liveness checking.

On the normal path, the pre-CIF eGov National ID, eGov TIN ID, Meralco, and Collector-visit results are linked/reused as already-verified onboarding evidence rather than forcing the Client to submit the same requirements again inside the CIF.

On a Management-bypass path, the CIF must preserve the bypass record rather than pretending a missing requirement was verified. The bypass does not automatically create fake evidence or a false pass result.

The baseline face scan captured during the first CIF becomes the Client's identity baseline for later renewal face matching.

Do not revive the earlier overbuilt CIF or add unrelated personal data.

## CIF validity and re-verification

The approved CIF lifecycle remains:

- one Active CIF per Client;
- `expires_at = effective_at + five years`;
- status `Draft | Active | Expiring | Expired | Superseded`;
- Expiring begins 90 days before expiry;
- prior CIF versions remain immutable;
- material identity/address/contact change, ID/document expiry, discrepancy, suspicious activity, or another risk event may require earlier re-verification.

Authorized Office Staff/Employee or Management may perform scheduled/triggered CIF checking or re-verification, and SPINA records who checked it and when.

CIF expiry must not block collection or correction of an existing obligation. It does block final approval/contract/release of a new loan until the CIF is Active again.

## Loan application boundary

Once the applicant is `eligible_for_cif` and the official `client_id` exists, staff may assist with the CIF and prepare a loan-application draft.

To keep the workflow practical:

- a loan-application draft may be prepared while the CIF is being completed;
- the application must not proceed to final Management loan review/approval until the CIF is Active;
- requested amount/product/term/purpose and affordability information belong to the loan application, not the pre-CIF requirements record;
- CIF approval is not itself financial loan approval; and
- no loan, schedule, journal, contract, disbursement, or release is created merely because eligibility or CIF passed.

This separates the decisions cleanly:

1. **Requirements eligibility** — all four requirements pass, or Management records an audited bypass.
2. **Client identity creation** — exactly one inactive `lending.clients` row is created and linked.
3. **CIF validity** — required Client information and baseline identity enrollment become Active.
4. **Loan approval** — Management decides the actual requested loan under the separate loan-application workflow.

## Client-account boundary

The pre-CIF Applicant/Prospect record is not a `core.users` account and does not grant Client permissions.

Eligibility creates the official `lending.clients` identity row only. It does not create credentials.

Client username/password creation remains exclusively owned by the already-merged protected `/api/v1/management/client-accounts` lifecycle and must not be duplicated in #419. No public self-registration is restored.

## Renewal identity requirements

A normal renewal is **not another CIF** while the existing CIF remains Active.

The renewal identity requirements are only:

1. **Signature**; and
2. **Live face selfie scan**.

The renewal face scan must pass liveness and match the baseline face scan from the original CIF.

Do not require National ID, TIN ID, Meralco bill, Collector visit, or another full CIF merely because the Client renews. If the five-year CIF has expired or an early re-verification trigger exists, the separate CIF re-verification lifecycle applies first.

Management pre-CIF bypass does not automatically bypass future CIF expiry/re-verification requirements.

## Public status lookup

Public status lookup is never reference-only. A one-time verification challenge must be completed before SPINA returns safe status information.

Safe public states may include requirements incomplete, under verification, eligible for CIF, CIF processing, application under review, approved, or rejected as applicable. Public status must not disclose whether Management used an internal bypass unless Management explicitly defines applicant-safe wording later.

The response must never expose raw KYC evidence, government-ID values, Collector internal notes, Management bypass reasons, affordability inputs, reviewer internals, Client IDs, biometric matching data, or credentials.

Development continues to use a fake/disabled verification adapter until an approved live provider is separately authorized.

## UI scope

Implement only the smallest surfaces required for the approved flow:

- signed-out Web/Mobile entry;
- pre-CIF requirements checklist/status;
- Collector residence-visit recording surface;
- Staff/Management normal requirements-verification decision;
- Management-only bypass action with mandatory reason and selected bypassed requirements;
- staff-assisted CIF after eligibility;
- loan-application preparation only after eligibility, with final review gated on an Active CIF;
- safe public status check; and
- downstream handoff to existing Client-account creation after the official borrower lifecycle permits it.

Do not add a generic workflow engine, form-builder framework, separate authentication system, or live biometric/eGov integration merely to implement this flow.

## Testing and release boundary

Implementation must restart under strict RED -> GREEN TDD because the previous #419 tests encoded the now-superseded direct `Guest CIF + Loan Application` flow.

Required proof before merge will include:

- tests proving normal CIF/loan preparation cannot start before all four pre-CIF requirements pass;
- tests proving Management can bypass any/all four requirements and no other role can;
- tests proving a bypass requires a non-empty reason and records requirement set, actor, timestamp, and audit evidence;
- tests proving the Collector can record the residence visit but cannot grant final CIF eligibility or bypass;
- Staff/Management authorization tests for the normal eligibility decision;
- evidence-boundary tests for eGov National ID, eGov TIN ID, Meralco bill, and Collector visit;
- idempotent eligibility-promotion tests proving exactly one inactive `lending.clients` row is created with no `core.users`/credentials/loan side effects;
- CIF lifecycle tests including baseline face enrollment, five-year expiry, 90-day Expiring status, re-verification, and Active-CIF gate;
- safe status-verification tests;
- Management loan-review tests;
- Web/Mobile navigation/policy tests;
- disposable PostgreSQL validation; and
- full SPINA CI on the exact PR head.

The previously written implementation plan is superseded by this architecture and must not be executed further. After Management reviews this written spec, create a fresh implementation plan from this design before changing production code/tests.

This branch does not authorize production deployment, live applicant data, real eGov/ID/bill/face evidence upload, live residence evidence capture, live biometric/liveness/face-match provider calls, live OTP/email/SMS delivery, production database/Auth mutation, loan creation, contract execution, renewal execution, or release.