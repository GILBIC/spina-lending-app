# Loan Application Draft Version API

This is a bounded Task 3 step in the approved office-only CIF/first-loan plan.
Reuse the accepted application repository; introduce no business-policy change.

## Accepted starting point

Head `f0f6c51c30c9f6141b2773b014aba070fb081e69` passed SPINA CI2337,
Annex A57 and 7x7 PostgreSQL159. Backend executed 1858 passing cases with
447 skips and two warnings. Financial executed all 214 onboarding/CIF/application
database cases in 21.95s, created/dropped its disposable database and passed the
private-schema barrier. Draft creation and review-summary APIs are accepted.
PR420 stays Draft, open and unmerged.

## HTTP boundary

`POST /api/v1/management/clients/{client_id}/loan-applications/{application_id}/draft-versions`

- Reuse authenticated device context, `client_onboarding.requirement.review`
  permission and the explicit Employee or Management role requirement.
- Require exactly `cif_version_id`, `expected_version_number` and `information`.
  Validate the CIF as UUID, expected version as a strict positive integer, and
  information through the existing `LoanApplicationInformation` model. Reject
  booleans, floats and numeric strings as expected versions. Supplied information
  may be incomplete, including `{}`; saving a draft does not demand confirmation
  or approval readiness. Reject extra fields and invalid supplied values.
- Delegate exactly once per request to the existing repository `append_draft`,
  with the authenticated persisted actor, path Client/application, submitted CIF,
  expected version and validated information. Never take actor or path identity
  from the body. Eligibility, immutable history, locking, exact retries and
  conflicting/stale writes remain in that repository.
- Return HTTP200 for the saved version, including a successful exact retry and
  unchanged save. Return the actual repository record: it can be the expected
  version for a no-op, or its saved successor. Do not increment the version,
  mint IDs/timestamps or introduce a second idempotency mechanism in the API.
- Return the same explicit saved-version information as the accepted review GET:
  Client/application/version/CIF IDs, reference, version number, JSON-mode
  information with exact decimal strings, request/repayment `missing_fields`, UTC
  `recorded_at`, and `review_scope: loan_application_information_only`.
- Set `Cache-Control: no-store`. Exclude private evidence, recording actor and
  confirmation/approval/release state. Missing-fields is not full T01 readiness.
- Preserve auth/device/account denials; map repository AccessDenied to403 and
  Conflict to409. Reject malformed path/body data with422 before repository use.
- No public or Client alias. Saving a correction only invokes existing immutable
  application-version persistence. It does not confirm the application, approve
  a loan, sign documents, issue credentials, release cash or create a schedule.

## Tests-first sequence

New contract file: `gilbic_backend/tests/test_loan_application_append_draft_api.py`.
Synthetic dependency overrides exercise the registered route. Use the public
OpenAPI paths to detect a missing POST and fail explicitly in test bodies; do not
depend on flattened router internals, fail collection, or skip missing behavior.
Existing 214-case PostgreSQL coverage remains the persistence authority; HTTP
fakes establish neither database retries nor atomicity.

1. Cover office access and denials, complete/incomplete input, exact delegation,
   saved response (expected7 -> saved8 and unchanged7), retry delegation, conflict
   mapping, strict validation and aliases. Independently review the contract.
2. Verify collection, expected local missing-route Red and retained regressions.
3. Publish only this plan and the new test file as a non-force child of the
   accepted head; recheck the live branch immediately before pushing.
4. Read new-head checks once, save GitHub/Notion/Create State and stop CI polling.
5. On the user's Red/all-green signal, inspect actual matching logs. After
   verified missing-route Red, minimally extend the existing application API;
   keep published tests, repository, SQL and financial behavior unchanged.
6. Accept only after focused checks and actual required CI evidence, including
   214 executed Financial database cases, cleanup and private-schema barrier.

Use the existing virtual environment and
`PYTHONPATH=gilbic_backend/src;spina_backend_mobile/src;.` on Windows.

## Local tests-only verification

All 36 new cases collect successfully and fail solely with
`Loan application draft version API is not implemented` in 79.67s; no collection
errors or skips. Both complete and literal-empty information fixtures validate
with the existing model. All 208 retained draft/review/CIF/application-value
cases pass in 133.67s. Both focused runs report two existing dependency
deprecation warnings. Python compilation and whitespace checks pass.

Independent contract review passed after adding an explicit malformed
application-ID case alongside Client and CIF IDs. No production, repository,
SQL, runner, workflow, dependencies or existing tests changed. No new database
execution is claimed by this HTTP-only test slice.

Applicant-confirmation HTTP exposure and office UI remain later Task 3 slices.
Full T01/privacy/evidence authenticity, Management exact-term approval, source-
bound documents/signing and actual office release remain unfinished. No main,
frozen Master296, other-owner files, merge, deployment or production operations.
