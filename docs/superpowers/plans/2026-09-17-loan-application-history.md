# Loan Application History Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove the database foundation for a stable application identity and append-only versions without replacing reusable CIF or existing loan/renewal authorities.

**Architecture:** Two private `lending` tables store an application header and numbered request/repayment versions. Composite foreign keys protect the same-Client links. Existing Pydantic validation and the existing guarded onboarding PostgreSQL runner are reused.

**Tech Stack:** PostgreSQL, psycopg, pytest, existing Pydantic models; no new dependency or workflow.

**Spec:** This scoped design records Management's explicit 2026-09-17 approval of the proposal in PR420 checkpoint5710110034. It extends Task3 of `docs/superpowers/plans/2026-09-10-office-only-cif-first-loan.md` and its paired `docs/superpowers/specs/2026-09-10-office-only-cif-first-loan-design.md`; it does not supersede those authorities.

## Global constraints

- Remain on `feat/guest-cif-loan-application`, PR420 Draft/open/unmerged; no production database, main merge or other-owner changes.
- Reuse valid Client/CIF/account identities. A new application does not require new CIF registration or reuse another loan's signature/approval evidence.
- Draft storage may reference an inactive Client/draft CIF. Active, unexpired, non-blocked CIF remains an approval prerequisite, not a newly imposed draft prerequisite.
- Preserve all107 accepted application value tests, existing96 onboarding/CIF PostgreSQL cases, original forms and all financial/calendar rules.
- Schema constraints are NOT authenticated actor checks, eligibility/credit approval, atomic saves, safe retries or complete T01 confirmation.
- Ordinary backend database skips are not acceptance. Run real SQL only in the existing guarded `spina_onboarding_[0-9a-f]{12}` loopback disposable database.

## Approved storage design

`lending.loan_applications` contains exactly `id`, `application_reference`, `client_id`, `created_by_user_id`, `created_at`. Its UUID and timestamp have database defaults, the reference is nonblank and unique, and Client/actor references are non-null foreign keys. Add a unique `(id, client_id)` target for version ownership.

`lending.loan_application_versions` contains exactly `id`, `application_id`, `client_id`, `cif_version_id`, `version_number`, `information`, `recorded_by_user_id`, `recorded_at`. UUID/time have database defaults. All columns are non-null; version numbers are positive and unique within the application. Composite references bind `(application_id, client_id)` to the header and `(cif_version_id, client_id)` to existing CIF identity. Use `ON DELETE RESTRICT` to preserve sources.

The JSON object has exactly `request` and `repayment` object sections. Empty/incomplete draft sections are allowed, not interpreted as approved or complete. Database checks protect this outer shape only; do not duplicate the accepted nested Pydantic rules in SQL.

Both tables are append-only. One shared trigger function rejects UPDATE, DELETE and TRUNCATE with SQLSTATE23514 and `Loan application history is immutable`. Preserve existing0109 private-schema/default-privilege behavior; do not grant access to PUBLIC or Supabase client roles, change owners, or disable triggers to clean up tests. No approval/release/status columns, mutable latest pointer, new loan, schedule or Auth account.

## Task 1: Real PostgreSQL foundation tests and minimal migration

**Files:**
- New tests: `gilbic_backend/tests/test_loan_application_history_postgres.py`.
- Existing runner: `tools/run_client_onboarding_disposable_postgres_validation.py`.
- After verified Red, new migration: `gilbic_backend/sql/0120_add_loan_application_history.sql`.

**Interfaces:** Existing `_seed_case`, `_insert`, `_read`, `_unrelated_counts`, `connection` and `runtime_url` from the CIF-confirmation tests supply synthetic identities, historical evidence and the disposable guard. The new file owns only `_header`, `_version`, `_read` and `_require_schema` SQL test helpers. Payloads come from `LoanApplicationInformation.model_dump(mode="json")`, not guessed client facts.

- [x] Record approval and inspect live main/PR420/other open owner changes. At this review0120 is absent from the inspected main SQL tree, PR420 owns0119, and PR424 changes no SQL. Plan0120 for this slice; recheck allocation before publishing the migration. This is not a reservation on every stale branch.
- [x] Write the40-case schema tests: draft defaults/no side effects; multiple applications/versions with unchanged profile confirmation; duplicate keys; missing and cross-borrower references; null/invalid metadata/JSON; all three mutations on both tables; private grants; committed migration reruns.
- [x] Add only the new test path to the runner's presence check and same pytest invocation. Do not apply an absent migration or change existing bootstrap, safety guards or selected tests in the tests-first commit.
- [ ] Execute the existing Financial/disposable PostgreSQL CI lane at the exact published head. Expected new failures: `Application-history schema is not implemented`, reached from each test body. Existing96 cases remain selected. Investigate a different failure instead of assuming expected Red.

Example behavior exercised by the real SQL helpers:
```python
header = _header(connection, case)
first = _version(connection, case, header)
second = _version(connection, case, header, version_number=2)
assert _read(connection, "loan_application_versions", first["id"]) == first
assert second["version_number"] == 2
```

- [ ] After actual Red, create the two-table migration described above. Reuse the existing `lending_client_cif_versions_identity_uidx` from0119. Follow0119's transaction, idempotent creation, immutable-trigger and revoke patterns; never modify0119 or other-owner financial migrations.
- [ ] Register the migration in the existing runner after0119 and update only its accurate success description:
```python
CIF_MIGRATIONS = (
    ROOT / "gilbic_backend" / "sql" / "0114_add_client_cif_first_loan_foundation.sql",
    ROOT / "gilbic_backend" / "sql" / "0119_add_client_cif_review_confirmation.sql",
    ROOT / "gilbic_backend" / "sql" / "0120_add_loan_application_history.sql",
)
```
- [ ] Run the same guarded disposable proof. Expected:136 selected database cases pass (96 retained plus40 new); verify real execution and cleanup, not only backend skips. Check migration reruns keep data and guards. Verify the other exact-head CI lanes remain successful.
- [ ] Compare against the tests-only parent; leave40 tests and all prior assertions unchanged. Record exact revision/results in GitHub, existing Notion page and Create State. Do not mark the entire application workflow complete.

## Next independent acceptance boundary: protected save/retry logic

The approved design also requires transactionally safe creation/append and exact-version reads. Schema uniqueness merely rejects duplicates; it does NOT implement a successful retry. Before adding a repository, write real PostgreSQL tests for atomic header+first-version creation, same-reference/same-Client identical retry, conflicting reference reuse, current-version identical save, stale expected-version conflict, concurrent appends, rollback on version failure, and authorized same-Client/CIF/actor selection. Retain original versions even after later changes; returning an old retry must not replace the latest version. This is a separate reviewable task after the schema foundation is Green, not functionality claimed by this publication.

Later applicant confirmation must bind the exact saved version plus actual acknowledgment, Staff witness and server time. Do not overwrite0119's one-per-CIF confirmation or force repeat enrollment. Full applicable identity/privacy completeness and final approval revalidation remain required. Existing renewal, loan, schedule, accounting, tax and release engines remain authoritative; saving information alone has no financial effect.
