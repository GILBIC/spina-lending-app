# Pre-CIF Requirements Verification + CIF + Loan Application Design

**Status:** Revised approved product direction for GitHub #419; written spec awaiting final Management review before implementation resumes.

## Goal

A brand-new applicant must first complete and pass SPINA's minimum onboarding requirements before staff assists with the Client Information Form (CIF) or loan application.

The pre-CIF gate prevents SPINA from spending time building a CIF or processing a loan request for an applicant who has not yet completed the required identity, residence, and field-verification checks.

## Product flow

Signed-out users keep three clear entry points:

1. **Sign in** — existing approved Client/Staff accounts only.
2. **Apply for a loan** — starts the new-applicant requirements-verification flow; it does **not** immediately create a CIF or loan application.
3. **Check application status** — reference plus verified one-time challenge before any status is returned.

The approved new-applicant flow is:

`New applicant -> Requirements verification -> Eligible for CIF -> Staff-assisted CIF + loan application preparation -> CIF active -> Loan application review -> approved borrower/account lifecycle`

The phrase **Apply for a loan** is the public entry point, but the first actual step is requirements verification. A financial loan application must not be submitted for review until the applicant has passed the pre-CIF gate and the required CIF gate described below.

## Pre-CIF hard eligibility gate

A new applicant must complete all four requirements before SPINA marks the applicant **Eligible for CIF**:

1. **eGov-verified National ID**;
2. **eGov-verified TIN ID**;
3. **Meralco bill** accepted as the required residence/address evidence; and
4. **Collector residence visit** completed and passed.

These are the four onboarding requirements. The baseline face scan is **not** one of these four; it belongs to the CIF stage after eligibility.

Until all four requirements pass:

- do not create or assist with the full CIF;
- do not submit a loan application for review;
- do not create a `core.users` account or Client permissions;
- do not create a loan, schedule, journal, contract, disbursement, or release;
- show only a safe onboarding state such as requirements incomplete or under verification.

## Verification roles and authority

The Collector is responsible only for the residence-visit part of the gate. The Collector may record the visit result, date, permitted notes/evidence reference, and their identity as the person who performed the visit.

The Collector **cannot** make the final **Eligible for CIF** decision.

Authorized **Office Staff/Employee or Management** performs the final requirements check. SPINA may mark the applicant `eligible_for_cif` only when all four individual requirements are verified as passed. The system must record who made the final eligibility decision and when.

This final eligibility decision is separate from later Management loan approval.

## Lean pre-CIF record

Before CIF eligibility, SPINA keeps a small Applicant/Prospect verification record rather than an official Client account.

The record should contain only what is needed to manage the four checks and safely contact the applicant, including:

- application/reference number;
- applicant name and minimum contact information;
- controlled evidence reference/result for eGov National ID verification;
- controlled evidence reference/result for eGov TIN ID verification;
- controlled evidence reference/result for the Meralco bill;
- Collector visit status/result/date and Collector identity;
- final eligibility status, reviewer, and reviewed timestamp.

Recommended lifecycle states are deliberately small:

- `requirements_incomplete`
- `under_verification`
- `eligible_for_cif`
- `requirements_rejected`

No raw government-ID files, raw bill image, passwords, OTPs, phone contacts, or unnecessary identity values belong in the ordinary applicant row. Normal records keep only the minimum approved metadata/references; restricted evidence custody remains separately controlled.

## CIF boundary after eligibility

The full CIF is required only for a brand-new Client and can begin only after the applicant reaches **Eligible for CIF**.

Staff/Management assists the applicant with the lean CIF. The CIF contains the approved stable/slow-changing Client information needed for onboarding, including:

- identity/contact information;
- present/permanent address information;
- basic employment/livelihood information;
- privacy/accuracy acknowledgements;
- Client signature and verifying-staff record; and
- **baseline live face selfie scan** that passes liveness checking.

The pre-CIF eGov National ID, eGov TIN ID, Meralco, and Collector-visit results should be linked/reused as the already-verified onboarding evidence rather than forcing the applicant to submit the same requirements a second time inside the CIF.

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

Passing the four pre-CIF requirements makes the applicant eligible for staff assistance with the CIF and loan application preparation.

To keep the workflow practical, a loan-application draft may be prepared after eligibility while the CIF is being completed. However:

- the application must not proceed to final Management loan review/approval until the CIF is Active;
- requested amount/product/term/purpose and affordability information belong to the loan application, not the pre-CIF requirements record;
- CIF approval is not itself financial loan approval;
- no loan, schedule, journal, contract, disbursement, or release is created merely because the four requirements or CIF passed.

This separates the three decisions cleanly:

1. **Requirements eligibility** — Staff/Management confirms the four pre-CIF requirements.
2. **CIF validity** — required Client information and baseline identity enrollment are complete/Active.
3. **Loan approval** — Management decides the actual requested loan under the separate loan-application workflow.

## Official Client/account boundary

The pre-CIF Applicant/Prospect record is not a `core.users` account and does not grant Client permissions.

Passing the four requirements alone does not create credentials. Client username/password creation remains exclusively owned by the already-merged protected `/api/v1/management/client-accounts` lifecycle and must not be duplicated in #419.

The downstream implementation plan must preserve a single, auditable promotion from the approved onboarding/CIF path into the official borrower record before Client credentials are created. No public self-registration is restored.

## Renewal identity requirements

A normal renewal is **not another CIF** while the existing CIF remains Active.

The renewal identity requirements are only:

1. **Signature**; and
2. **Live face selfie scan**.

The renewal face scan must pass liveness and match the baseline face scan from the original CIF.

Do not require National ID, TIN ID, Meralco bill, Collector visit, or another full CIF merely because the Client renews. If the five-year CIF has expired or an early re-verification trigger exists, the separate CIF re-verification lifecycle applies first.

## Public status lookup

Public status lookup is never reference-only. A one-time verification challenge must be completed before SPINA returns safe status information.

Safe public states may include requirements incomplete, under verification, eligible for CIF, CIF processing, application under review, approved, or rejected as applicable. The response must never expose raw KYC evidence, government-ID values, Collector internal notes, affordability inputs, reviewer internals, Client IDs, biometric matching data, or credentials.

Development continues to use a fake/disabled verification adapter until an approved live provider is separately authorized.

## UI scope

Implement only the smallest surfaces required for the approved flow:

- signed-out Web/Mobile entry;
- pre-CIF requirements checklist/status;
- Collector residence-visit recording surface;
- Staff/Management requirements-verification decision;
- staff-assisted CIF after eligibility;
- loan-application preparation only after eligibility, with final review gated on an Active CIF;
- safe public status check;
- downstream handoff to existing Client-account creation after the official borrower lifecycle permits it.

Do not add a generic workflow engine, form-builder framework, separate authentication system, or live biometric/eGov integration merely to implement this flow.

## Testing and release boundary

Implementation must restart under strict RED -> GREEN TDD because the previous #419 tests encoded the now-superseded direct `Guest CIF + Loan Application` flow.

Required proof before merge will include:

- tests proving CIF/loan submission cannot occur before all four pre-CIF requirements pass;
- tests proving the Collector can record the residence visit but cannot grant final CIF eligibility;
- Staff/Management authorization tests for the final eligibility decision;
- evidence-boundary tests for eGov National ID, eGov TIN ID, Meralco bill, and Collector visit;
- CIF lifecycle tests including five-year expiry and Active-CIF gate;
- baseline face-scan/liveness contract tests at CIF enrollment;
- submission tests proving no public Auth/Client/loan side effects;
- safe status-verification tests;
- Management loan-review tests;
- promotion/idempotency tests;
- Web/Mobile navigation/policy tests;
- disposable PostgreSQL validation;
- full SPINA CI on the exact PR head.

The currently written implementation plan is superseded by this architecture and must not be executed further. After Management reviews this written spec, create a fresh implementation plan from this design before changing production code/tests.

This branch does not authorize production deployment, live applicant data, real eGov/ID/bill/face evidence upload, live residence evidence capture, live biometric/liveness/face-match provider calls, live OTP/email/SMS delivery, production database/Auth mutation, loan creation, contract execution, renewal execution, or release.