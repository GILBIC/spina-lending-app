# Office-Only New Borrower CIF + First-Loan Design

**Status:** Management-approved V1 product direction. This document supersedes the public new-applicant Apply/status portions of the 2026-09-06 onboarding design for all work after verified Plan 1.

## Goal

Keep new-borrower onboarding controlled, privacy-minimal, and operationally simple:

- a brand-new applicant starts and completes the first-loan application process at the SPINA office;
- Office Staff/Employee interviews and encodes the applicant/CIF information;
- the applicant reviews and confirms the encoded information in the office;
- the four approved pre-CIF requirements remain the normal eligibility gate, with Management-only audited bypass;
- the first-loan contract/disclosure is separate from the application/CIF confirmation and is signed only after Management approves the exact loan terms;
- actual first-loan cash release occurs at the SPINA office; and
- permanent Client credentials are created/linked only after a successful actual first-loan release.

The design must reuse existing SPINA account, Area, payment, schedule, audit, and financial authorities rather than introducing duplicate engines.

## Authoritative V1 flow

`Applicant arrives at SPINA office`

`-> Staff-assisted minimum applicant intake / requirements record`

`-> National ID + TIN ID + Meralco + Collector residence visit verification`

`-> Eligible for CIF (normal pass or Management-only audited bypass)`

`-> exactly one inactive lending.clients identity exists`

`-> Staff-assisted CIF + first-loan application preparation in office`

`-> applicant reviews and confirms CIF/application information`

`-> CIF becomes Active when its required checks and baseline live face enrollment pass`

`-> Management reviews and approves/rejects exact loan terms`

`-> locked disclosure/contract generated from approved terms`

`-> borrower signs locked contract at SPINA office`

`-> authorized Office Staff performs actual cash handoff after valid Management release authorization`

`-> borrower confirms exact cash received`

`-> SPINA records release actors/time + official receipt`

`-> loan becomes Released immediately`

`-> operational schedule starts from actual office release date`

`-> SPINA creates/links permanent Client credentials and delivers username/password under the existing managed credential lifecycle`

If the actual office release does not occur, the process remains **Approved / Pending Release**. No schedule activation, credential creation, partial release state, or fake financial state is created.

## Public and Client Web/Mobile boundary

New applicants do **not** self-start or continue a first-loan application outside the SPINA office.

Therefore V1 Client Web/Mobile must not expose:

- public `Apply for a loan` for brand-new applicants;
- public applicant self-entry forms;
- borrower-started first-loan application continuation from home;
- public reference/OTP application-status continuation for brand-new applicants; or
- public self-registration for Client credentials.

Client Web/Mobile remain focused on authenticated servicing after SPINA creates/links the permanent Client account.

Any earlier public new-applicant intake/status concept is superseded and must not be used as the authority for future implementation.

## Pre-CIF eligibility gate

The normal path still requires all four approved requirements before **Eligible for CIF**:

1. eGov-verified National ID;
2. eGov-verified TIN ID;
3. accepted Meralco bill for residence/address evidence; and
4. Collector residence visit completed and passed.

The baseline live face selfie/liveness check is **not** one of these four requirements; it belongs to the CIF stage after eligibility.

Until normal eligibility or an approved Management bypass:

- do not start the full CIF;
- do not prepare the first-loan application for processing;
- do not create credentials;
- do not create a loan, schedule, journal, contract, disbursement, or release.

## Roles and authority

### Office Staff / Employee

May:

- interview the applicant in the office;
- encode applicant, CIF, and first-loan application information;
- record/assist normal verification work allowed by existing permissions;
- present the read-only application/CIF summary for applicant review;
- correct data after the applicant identifies an error;
- witness the applicant's application/CIF confirmation;
- after Management approval and release authorization, physically hand first-loan cash to the named borrower if their role has the required release permission.

May not:

- bypass pre-CIF requirements;
- approve the loan;
- alter Management-approved amount/rate/term/schedule/fees at release;
- create a substitute contract; or
- create Client credentials before successful release.

### Collector

May:

- perform and record the approved residence visit;
- continue existing-Client renewal field duties under the separately approved renewal flow.

May not:

- own first-loan office application encoding;
- grant final CIF eligibility;
- use Management bypass;
- approve a first loan; or
- perform first-loan field cash release.

### Management

Owns:

- any pre-CIF bypass;
- final loan approval/rejection;
- exact approved loan terms;
- explicit release authorization; and
- Management-only exceptions already defined elsewhere.

Management approval does not itself create credentials or activate the schedule.

## Management pre-CIF bypass

Management may bypass any or all four pre-CIF requirements.

Every bypass must record:

- exact bypassed requirement set;
- mandatory non-empty reason;
- Management actor;
- server timestamp; and
- immutable audit evidence.

The original pending/failed requirement states remain truthful; bypass must not rewrite them into fake `passed` states.

Bypass grants only **Eligible for CIF**. It does not bypass CIF requirements, baseline face/liveness, loan approval, contract signing, release authorization, or credential controls.

## Stable Client identity boundary

Verified Plan 1 remains authoritative:

- normal eligibility and Management bypass create exactly one idempotent `lending.clients` row;
- the Client is initially `inactive`;
- `user_id = NULL`;
- Area may remain unassigned until authoritative Area Management assigns it;
- residence address is not silently reused as operational Collector Area/route;
- no Auth account, loan, schedule, journal, contract, disbursement, or release is created by eligibility alone.

The stable `client_id` is used by CIF and first-loan application work. Names are not identity keys.

## CIF content and lifecycle

Keep the CIF lean. Store only information materially needed for identity/KYC, contact/residence, loan decision/supporting facts, required acknowledgements, and approved evidence.

The first CIF includes the baseline live face selfie scan with liveness. That verified baseline becomes the comparison source for later renewal identity checks.

CIF lifecycle remains:

- one current Active CIF for operations;
- historical CIF versions preserved rather than destructively overwritten;
- five-year validity;
- Expiring begins 90 days before expiry;
- earlier re-verification may be triggered by material identity/address/contact change, document expiry, discrepancy, suspicious activity, or another approved risk event;
- routine `CIF Review Due` does not disable an Active Client's existing loans, collections, payments, or portal access;
- new loans/renewals are blocked while required CIF re-verification is unresolved.

Every approved/released loan preserves the relevant borrower/CIF snapshot used for that loan so later CIF changes do not rewrite historical contracts, disclosures, receipts, approvals, or evidence.

## Application/CIF confirmation boundary

Application/CIF confirmation and final loan contract signing are separate events.

After Staff finishes encoding:

1. applicant reviews a read-only summary in the office;
2. if anything is wrong, Staff corrects it;
3. once correct, applicant signs/acknowledges the application/CIF information;
4. SPINA records confirmation time and the Staff witness/actor.

This confirmation does **not** mean:

- loan approval;
- acceptance of final loan terms;
- contract execution;
- cash release; or
- credential creation.

## Loan approval and legal-document boundary

Management separately approves the exact financial terms.

After approval, SPINA generates a locked disclosure/contract from the approved authoritative terms. The borrower signs that exact locked version in the office before first-loan release.

Do not finalize lawyer-dependent legal wording in code. Maintain a safe template/integration boundary so counsel-approved wording can be substituted later without changing the financial authority or release state machine.

If the borrower asks to change terms, the document mismatches approval, approval is stale/revoked, or another final check fails, release stops and returns to Staff/Management handling.

## First-loan office release

First-loan signing and cash handoff are office-only.

Required release evidence is intentionally simple:

- named borrower signs the exact locked disclosure/contract;
- borrower explicitly confirms the exact cash amount actually received;
- SPINA records Management approver/release authorizer separately from the releasing Staff actor;
- SPINA records authoritative release date/time and witness/actor information; and
- SPINA generates and retains the official first-loan release receipt.

A face+money release photo is **not required** for first-loan office release.

The handoff is all-or-nothing for V1. No partial release state is created.

## Release effects

A successful actual first-loan office release is the authoritative transition that:

- marks the loan Released;
- records the actual release date/time;
- starts the operational schedule from the actual release date according to the existing authoritative schedule rules;
- produces the official receipt/evidence; and
- creates/links the permanent Client Auth account using the already-approved SPINA-managed credential lifecycle.

Management approval alone, contract signing alone, or a planned handoff does not create credentials.

If release is cancelled, declined, blocked, or never completed, no permanent Client Auth account is created from this first-loan flow.

## Credential boundary

Reuse the existing protected Client-account lifecycle. Do not create another authentication or password system.

After successful first-loan release:

- create/link the Client account once;
- generate/deliver username and password through the approved SPINA credential process;
- no public self-registration;
- no recoverable plaintext password storage;
- future Regular/7x7 loans and renewals reuse the same Client account.

## Existing-Client renewal boundary

This spec does not replace the separately approved renewal flow.

For an existing Client with an Active CIF, normal renewal identity evidence remains:

- signature; and
- live face selfie scan with liveness + match to the CIF baseline.

Approved renewal contract/cash handoff may occur through the Collector under the already-approved field-custody/witness/evidence rules. That field renewal behavior does **not** authorize first-loan field release.

## Client-facing post-release view

After successful release, authenticated Client Web/Mobile may show the authoritative:

- loan amount;
- actual release date;
- first payment date;
- required daily/payment amount; and
- updated payment schedule.

These values are read-only and come from released server state, not client-side calculation or draft terms.

## Testing boundary for the next implementation plan

The next implementation plan must use strict RED -> GREEN TDD and prove at minimum:

- no public brand-new applicant Apply/status continuation on Client Web/Mobile;
- Staff-assisted office encoding and applicant review/confirmation;
- four-requirement normal eligibility and existing Management-only bypass remain intact;
- Collector cannot own office encoding, final eligibility, bypass, first-loan approval, or first-loan release;
- one stable inactive Client identity is reused without duplicate Auth/loan creation;
- lean CIF + baseline liveness/face enrollment + five-year lifecycle and re-verification boundaries;
- application/CIF confirmation is separate from final contract signing;
- final Management approval gates the exact locked loan terms;
- valid Management release authorization is required before Staff cash handoff;
- successful actual release is atomic, creates no partial state, starts schedule on actual release date, and triggers Client credential creation/linking exactly once;
- failed/declined/cancelled release keeps Approved/Pending Release and creates no schedule/credentials;
- first-loan office release does not require face+money photo;
- historical CIF/loan snapshot integrity;
- disposable PostgreSQL proof and full exact-head SPINA CI.

## Explicit non-goals for this phase

Do not add:

- public new-applicant self-service;
- generic workflow/form-builder infrastructure;
- a second Area/routing, schedule, accounting, or authentication engine;
- live eGov, biometric, OTP, SMS, or payment-provider integration without separate approval;
- lawyer-dependent final legal wording;
- production deployment, production DB/Auth mutation, real applicant data, or real cash release.

## Integration rule

All work remains on Draft branches/PRs and must not be merged, marked ready, deployed, or released without explicit Management approval.