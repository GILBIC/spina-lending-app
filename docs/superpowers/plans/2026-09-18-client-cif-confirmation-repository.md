# Protected CIF Review Confirmation Repository

This is the next bounded Task 3 dependency in the approved office-only CIF/first-
loan plan. Reuse existing Client/CIF identity, four-field review/correction,
authorization conventions and immutable 0119 storage. No HTTP or UI in this step.

## Accepted starting point

Head `07306d963b3aa7aae7287019bfc0f5fbd8170871` passed CI2341,
Annex A61 and 7x7 PostgreSQL163. Backend: 1929 passed, 447 skipped, two warnings.
Financial: all 214 actual onboarding/CIF/application database cases passed in
22.53s, disposable database cleanup and private-schema barrier passed.
Application review/create/append/confirmation APIs are accepted within their
bounded contracts. Protected CIF-confirmation creation remains missing.
PR420 stays Draft, open and unmerged.

## Repository contract

Add `PostgresClientCifRepository.confirm_review` with keyword-only inputs:
`actor_user_id`, `client_id`, `cif_version_id`, `expected_information`, and
`applicant_confirmation_evidence_reference`.

Return a frozen `ClientCifReviewConfirmationRecord` mirroring the existing table:
`id`, `client_id`, `cif_version_id`, `review_cycle_number`, `review_snapshot`,
`applicant_confirmation_evidence_reference`, `witnessed_by_user_id`, `confirmed_at`.
Do not accept cycle numbers, witness identity or timestamps from the caller.

- Use existing `_cif_information_snapshot` to validate exactly `full_name`,
  `phone_number`, `email` and `present_address`, with strict existing text/null
  rules. Preserve expected values exactly. Reject malformed snapshots and
  non-string/blank evidence references with `ValueError`; strip the reference.
- Recheck persisted authorization inside the transaction, including retries:
  active `core.users`, Employee or Management role, and
  `client_onboarding.requirement.review` granted to that office role. Add a
  distinct `ClientCifAccessDenied` error. No new permission or production grant.
- Bind exact Client and CIF IDs. For a new confirmation require a current CIF
  linked to an `eligible_for_cif` applicant, with draft/inactive or active/active
  CIF/Client status respectively. Reject wrong identities, unavailable sources,
  blocked/closed Clients, superseded/noncurrent CIFs and ineligible applicants.
  Confirmation itself neither requires nor changes activation/liveness state.
- Serialize with existing draft correction by locking the same joined source
  rows using `FOR UPDATE OF cif, applicant, client`. Avoid a separate Client-first
  lock that could invert correction's lock order. Recheck after waiting, including
  an existing confirmation created by the winning transaction. A stale reviewed
  snapshot cannot be confirmed after correction; a winning confirmation prevents
  later in-place correction through the existing correction guard.
- For new evidence, compare every expected field to the locked stored CIF value.
  A mismatch is `ClientCifConflict` and requires refreshing the review. Validate
  stored completeness with existing `normalize_cif_information` rules but do not
  replace reviewed/stored values with its normalized output. Incomplete stored
  information conflicts. Email remains optional; no new T01/private-document,
  income, liveness or loan-approval requirement is invented.
- Save a four-field snapshot from the locked stored row, normalized evidence
  reference and authenticated witness. Let existing database defaults provide
  identity and time. Allocate `coalesce(max(review_cycle_number), 0) + 1` for the
  Client while the Client/source lock is held; CIF version number is not a cycle.
- An existing confirmation with the same exact Client/CIF, immutable snapshot,
  normalized evidence reference and witness returns the original record without
  writes or new cycle/time. Changed snapshot/reference/witness conflicts. An
  authenticated exact historical retry remains valid after supersession or a
  later source-state change; fresh eligibility applies to creating evidence.
  Compare retries against the immutable saved snapshot, not today's CIF row.
- The only new persisted evidence is the existing confirmation row. Preserve all
  Client/CIF/applicant fields, prior confirmations, audit history and financial/
  Auth records. Existing immutable confirmation evidence is the record of this
  action; do not add a parallel audit/financial engine or change schema guards.
  SQL failures roll back the whole write.

This confirms only the four fields exposed by the accepted CIF review API.
It does not claim full T01/privacy completeness, evidence authenticity, CIF
activation, loan approval, final contract signing, release, credentials or a
schedule. Later corrections need a new version/review cycle; this method does
not introduce a CIF renewal or version-creation workflow.

## Tests-first publication

New tests:
`gilbic_backend/tests/test_client_cif_review_confirmation_repository_postgres.py`.
Reuse the existing guarded loopback disposable fixtures and real SQL. Redirect
only connection acquisition. Missing method must fail explicitly in test bodies
with `CIF review confirmation repository is not implemented`, without collection
errors or resolving missing exception classes first.

Register this file in the existing
`tools/run_client_onboarding_disposable_postgres_validation.py` prerequisite list
and pytest invocation. This is test wiring: keep its database guard, migrations,
bootstrap cutoff, environment, timeout, cleanup and existing test selections
unchanged. Do not add a workflow, migration or second database engine.

Prove real persisted identity/snapshot/witness/server time and no unrelated
mutations; office authorization including retries; exact/conflicting and
historical retries; fresh eligibility, completeness and stale review rejection;
per-Client cycles independent of CIF version; SQL rollback; and correction versus
confirmation contention in both directions. Use bounded SQL timeouts and actual
PostgreSQL blocking evidence, not timing-only or fake concurrency acceptance.
Reuse existing schema immutability tests without duplicating them.

1. Independently review contract/tests/runner scope.
2. Run the guarded disposable validator against a dedicated local scratch server.
   Verify all 214 retained cases pass and new cases fail only for the missing
   method. Observe database creation/drop and leave the scratch server stopped.
   Backend database skips alone are not acceptance.
3. Publish only plan, new tests and runner registration as a non-force child of
   the accepted head after rechecking the live branch.
4. Inspect new-head CI once, save GitHub/Notion/Create State/local handoff and wait
   for the user's Red/all-green signal. No polling/manual rerun.
5. After verifying actual expected CI Red, minimally implement in the existing
   CIF repository, keeping published tests and 0119 unchanged. Accept only after
   all 258 database cases (214 retained + 44 new), private-schema barrier, cleanup
   and all required CI.

## Local tests-only verification

All 44 new cases collect. Final guarded PostgreSQL18 validation reported
**44 failed, 214 passed, two pytest cache-permission warnings in 52.72s**. Every
failure was exactly `CIF review confirmation repository is not implemented`;
there were no retained failures, setup errors or skipped database cases.
Disposable `spina_onboarding_408aff4904d7` was created and dropped. An explicit
administrative query confirmed no onboarding disposable databases remain, and
the dedicated scratch server was stopped. No separate local private-schema
barrier run is claimed; verified parent CI evidence remains authoritative until
new CI executes it.

The first run exposed one invalid account-status fixture alongside 43 intended
failures and 214 retained passes. Both occurrences were corrected to the existing
`inactive` status before the successful expected-Red rerun above.

Compilation, whitespace and independent review passed. Before publication, review
fixed schema-invalid fixtures, preserved other Clients' committed confirmations in
state comparisons, and added actual waiting correction plus identical/conflicting
confirmation races. Existing 214 tests, SQL, repositories and APIs are unchanged.

The protected CIF-confirmation HTTP boundary comes after repository acceptance;
office UI and complete evidence/privacy gates follow. No main/frozen Master296,
other-owner files, merge, deployment or production operations are in this scope.
