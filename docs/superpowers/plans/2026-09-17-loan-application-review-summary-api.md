# Loan Application Review Summary API

This is a bounded implementation step within Task 3 of the approved
`2026-09-10-office-only-cif-first-loan.md` plan and paired design. It reuses the
accepted application repository; it does not change approved business policy.

## Accepted starting point

Commit `67b02b8bbf322e88c70fac61e189a33454e1c9de` passed SPINA CI2333,
Annex A53 and7x7 PostgreSQL155. Financial job105235065296 executed214 database
cases successfully in10.39s, dropped its disposable database and passed the
private-schema barrier. GitHub PR420 acceptance checkpoint5716279360 records
the evidence. PR420 remains Draft/open/unmerged.

## Smallest next boundary

Expose one saved application version for protected office review:

`GET /api/v1/management/clients/{client_id}/loan-applications/{application_id}/versions/{version_number}/review-summary`

- Reuse `authenticated_device_context`, the existing
  `client_onboarding.requirement.review` permission and explicit Employee or
  Management role requirement. Collector/Client are denied even with permission.
- Pass the authenticated actor, path Client/application IDs and positive version
  number to the existing `PostgresLoanApplicationRepository.get_version`.
  Never substitute a latest version or caller-supplied actor.
- Return only `client_id`, `application_id`, `application_version_id`,
  `application_reference`, `cif_version_id`, `version_number`, `information`,
  `missing_fields`, `recorded_at` and
  `review_scope: "loan_application_information_only"`.
- Serialize saved information using the existing model's JSON mode, preserving
  exact decimal strings. Report its missing request/repayment fields even for
  incomplete drafts; this is not full T01, confirmation or approval readiness.
- Use `Cache-Control: no-store`. Exclude private evidence references, recording
  actor identity, confirmation/approval state and financial effects.
- Preserve existing authentication/account/device denials. Map repository
  `LoanApplicationAccessDenied` to403 and `LoanApplicationConflict` to409.
- Reject malformed UUIDs and non-positive/non-integer versions with422 before
  accessing the repository. No mutation methods or public/Client alias.

## Tests-first publication

New file: `gilbic_backend/tests/test_loan_application_review_summary_api.py`.
Use synthetic auth/account/repository fakes like existing CIF summary tests;
real persistence remains covered by the accepted214-case database proof.

- [x] Write strict access, exact response, incomplete draft, error, path and
  method/alias contracts. Missing API must fail in test bodies, not skip or break
  collection. Verify the exact expected local Red.
- [x] Preserve existing tests, production code, SQL, runner and workflows.
  Run the existing CIF summary/correction and application value regressions.
- [ ] Review tests, recheck actual remote head, then publish only this plan and
  new test file as a non-force child of the accepted head.
- [ ] Read new-head CI once and synchronize GitHub, Notion and Create State.
  User may report only Red or all green; do not poll/manually rerun CI.
- [ ] On Red, inspect the exact failing CI log before implementation. Expected
  failure is the missing application review-summary API. Diagnose any other
  failure on its own evidence.
- [ ] Add minimal `loan_application_api.py`, repository dependency and router
  registration in `main.py`; keep published tests unchanged. Verify focused
  Green and all exact-head workflows before accepting this boundary.

Local evidence before publication:24 cases fail with the explicit missing-API
message; test discovery and compilation succeed. Existing CIF summary/correction
and application value regressions pass152 cases in39.09s (two dependency
deprecations and one local pytest cache-access warning). Use the existing CI
source paths locally: `PYTHONPATH=gilbic_backend/src;spina_backend_mobile/src;.`
on Windows. Omitting the sibling path initially caused import failures; no
dependency or code change was needed. Synthetic complete/incomplete fixtures and
exact decimal serialization were checked independently. An independent review
approved both new files; success uses version7 so hardcoded version1 cannot pass.

Create, append and confirmation HTTP writes remain later independent slices.
Full T01/privacy/evidence authenticity, Management approval, final documents,
signing and office release remain separate unfinished gates. No new workflow,
loan, financial or Auth engine; no main/frozen Master296/other-owner changes,
merge, deployment or production DB/Auth/customer/cash/provider operations.
