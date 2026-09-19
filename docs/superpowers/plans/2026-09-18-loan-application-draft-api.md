# Loan Application Draft Creation API

This is a bounded Task 3 step in the approved office-only CIF/first-loan plan.
Reuse the accepted application repository; introduce no business-policy change.

## Accepted starting point

Head `a98c74124620de0e45a5133c64c058f77381f5a5` passed SPINA CI2335,
Annex A55 and 7x7 PostgreSQL157. Backend executed 1826 passing cases with
447 skips and two warnings. Financial executed all 214 onboarding/CIF/application
database cases in 23.40s, created/dropped its disposable database and passed the
private-schema barrier. The review-summary API is accepted. PR420 stays Draft,
open and unmerged.

## HTTP boundary

`POST /api/v1/management/clients/{client_id}/loan-applications/drafts`

- Reuse authenticated device context, `client_onboarding.requirement.review`
  permission and the explicit Employee or Management role requirement.
- Accept only `cif_version_id`, `application_reference` and `information`.
  Require a valid CIF UUID, a stripped nonblank string reference, and the existing
  `LoanApplicationInformation` model. Supplied information may be incomplete,
  including `{}`; draft creation must not demand applicant confirmation or loan
  approval readiness. Reject extra request fields and invalid supplied values.
- Delegate exactly once per request to the existing repository `create_draft`,
  with the authenticated persisted actor, path Client, submitted CIF, normalized
  reference and validated information. Never take actor or Client identity from
  the body. Source eligibility, immutable persistence, identical retries and
  conflicting reference reuse stay in the existing repository.
- Return HTTP201 for the saved draft, including a successful identical retry.
  The repository returns the original record on that retry; do not mint new
  identifiers, times or a second idempotency mechanism in the HTTP layer.
- Return the same explicit saved-version information as the accepted review GET:
  Client/application/version/CIF IDs, reference, version number, JSON-mode
  information with exact decimal strings, request/repayment `missing_fields`, UTC
  `recorded_at`, and `review_scope: loan_application_information_only`.
- Set `Cache-Control: no-store`. Exclude private evidence, recording actor and
  confirmation/approval/release state. Missing-fields is not full T01 readiness.
- Preserve auth/device/account denials; map repository AccessDenied to403 and
  Conflict to409. Reject malformed path/body data with422 before repository use.
- No public or Client alias. No append, review confirmation, approval, credential,
  loan, schedule, cash, receipt or accounting effects beyond existing draft save.

## Tests-first sequence

New contract file: `gilbic_backend/tests/test_loan_application_draft_api.py`.
Synthetic dependency overrides exercise the registered application route. An
explicit missing-route assertion must fail in test bodies rather than breaking
collection or skipping the contract. Existing 214-case PostgreSQL coverage remains
the persistence authority; HTTP fakes do not establish database retry/atomicity.

1. Cover office access and denials, complete/incomplete input, exact delegation
   and saved response, retries, conflict mapping, strict validation and aliases.
2. Verify collection, expected local missing-route Red and retained regressions.
   Independently review the contract before publication.
3. Publish only this plan and the new test file as a non-force child of the
   accepted head; recheck the live branch immediately before pushing.
4. Read new-head checks once, save GitHub/Notion/Create State and stop CI polling.
5. On the user's Red/all-green signal, inspect the actual matching logs. After
   verified missing-route Red, minimally extend the existing application API;
   keep published tests, repository, SQL and financial behavior unchanged.
6. Accept the slice only after focused checks and actual required CI evidence.

Use the existing local virtual environment and
`PYTHONPATH=gilbic_backend/src;spina_backend_mobile/src;.` on Windows.

## Local tests-only verification

The 32 new cases collect successfully and all fail solely with
`Loan application draft creation API is not implemented` in 23.51s: no collection
errors or skips. Literal empty-information fixtures validate with the existing
model. All 176 retained review/CIF/application-value cases pass in 68.49s.
Python compilation, whitespace checks and independent contract review pass.
The retained run reports two dependency deprecations and one local pytest-cache
warning; the new run reports four warnings. No dependency or cache cleanup is
part of this change. No new database execution is claimed by the HTTP tests.

Append-version and applicant-confirmation HTTP contracts remain later slices.
Full T01/privacy/evidence authenticity, Management exact-term approval, source-
bound documents/signing and actual office release remain unfinished. No main,
frozen Master296, other-owner files, merge, deployment or production operations.
