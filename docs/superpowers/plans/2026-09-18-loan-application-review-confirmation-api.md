# Loan Application Review Confirmation API

This is a bounded Task 3 step in the approved office-only CIF/first-loan plan.
Reuse the accepted confirmation repository without introducing business policy.

## Accepted starting point

Head `197c15a32f26e927c1806ba320934f33b9dbe94e` passed SPINA CI2339,
Annex A59 and 7x7 PostgreSQL161. Backend executed 1894 passing cases with
447 skips and two warnings. Financial executed all 214 onboarding/CIF/application
database cases in 22.54s, created/dropped its disposable database and passed the
private-schema barrier. Read/create/append application APIs are accepted.
PR420 stays Draft, open and unmerged.

## HTTP boundary

`POST /api/v1/management/clients/{client_id}/loan-applications/{application_id}/review-confirmations`

- Reuse authenticated device context, `client_onboarding.requirement.review`
  permission and the explicit Employee or Management role requirement.
- Require exactly `application_version_id` and
  `applicant_confirmation_evidence_reference`. Validate the former as UUID and
  the latter as a stripped nonblank string. Reject missing, invalid or extra
  fields. The reference is an opaque acknowledgment evidence coordinate; this
  API does not authenticate the evidence or implement its upload/storage path.
- Delegate exactly once per request to existing `confirm_review`, passing the
  persisted authenticated actor, path Client/application, submitted exact version
  UUID and normalized evidence reference. Do not accept witness, CIF, timestamp,
  version contents or approval status from the request body.
- Preserve repository authority over source eligibility, complete stored request/
  repayment facts, existing CIF review confirmation, latest-version checks,
  immutable evidence, locking and exact/conflicting retries. The repository
  returns the original saved confirmation for an identical retry; do not add
  a second idempotency mechanism or reimplement these checks in the HTTP layer.
- Return HTTP201, including successful identical retries, with only the saved
  `review_confirmation_id`, `client_id`, `application_id`,
  `application_version_id`, `cif_version_id`, `witnessed_by_user_id`, UTC
  `confirmed_at` with a Z suffix, and
  `review_scope: loan_application_information_only`. Derive IDs, witness and time
  from the returned record, never generate or accept them in the API.
- Set `Cache-Control: no-store`. Exclude the evidence reference, other private
  evidence and confirmation-independent approval/release data. The response is
  information-review evidence, not loan approval, contract signing or release.
- Preserve auth/device/account denials; map repository AccessDenied to403 and
  Conflict to409, including incomplete facts, missing CIF confirmation, stale
  version/source and conflicting evidence/witness. Reject malformed path/body
  data with422 before repository use. No public or Client aliases.
- No credential, loan, schedule, receipt, cash or accounting effects.

## Tests-first sequence

New contract file:
`gilbic_backend/tests/test_loan_application_review_confirmation_api.py`.
Use synthetic dependency overrides against the registered application route.
Detect a missing POST using public OpenAPI paths and fail explicitly in test
bodies; no router-internals dependency, collection error or skipped contract.
Existing 214-case PostgreSQL coverage remains the persistence authority. HTTP
fakes prove delegation and serialization, not durable retries or atomicity.

1. Cover office access and denials, exact delegation and saved-record response,
   UTC conversion, retry delegation, repository conflicts, required/strict input,
   all path/body UUIDs, authoritative extras and absent aliases.
2. Independently review the contract; verify expected local missing-route Red
   and retained draft/review/CIF/application-value regressions.
3. Publish only this plan and the new test file as a non-force child of the
   accepted head, after rechecking the live branch.
4. Inspect new-head checks once, save GitHub/Notion/Create State/local handoff,
   then stop polling and await the user's Red/all-green signal.
5. Inspect actual matching logs. After verified missing-route Red, minimally
   extend the existing application API using existing authorization and repository
   code. Keep published tests, repository, SQL and financial behavior unchanged.
6. Accept only after focused checks and actual required CI evidence, including
   214 Financial database cases, cleanup and private-schema barrier.

Use the existing virtual environment and
`PYTHONPATH=gilbic_backend/src;spina_backend_mobile/src;.` on Windows.

## Local tests-only verification

All 35 new cases collect successfully and fail solely with
`Loan application review confirmation API is not implemented` in 74.08s, with
no collection errors or skips. All 244 retained append/draft/review/CIF/
application-value cases pass in 198.16s. Both focused runs report two existing
dependency deprecation warnings. Compilation, whitespace and independent
contract review pass. No production code, repository, SQL, runner, workflow,
dependencies or existing tests changed. No new database execution is claimed.

## Remaining dependencies and limits

The repository requires an existing CIF review confirmation. Its write API is
not yet implemented, so this slice does not provide the complete office flow;
that prerequisite must be completed before end-to-end office UI acceptance.
Full T01/privacy completeness, evidence authenticity and protected evidence
capture/retrieval remain open. Complete request/repayment facts alone are not
full application readiness. Later changes require their own review cycle.

Office UI, Management exact-term approval, bound documents/signing and actual
release remain unfinished. No main, frozen Master296, other-owner files, merge,
deployment or production operations are part of this change.
