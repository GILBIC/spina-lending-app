# R1 Pre-release Disclosure Source — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans for inline execution, or superpowers:subagent-driven-development only when that method is selected and available. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the first protected R1 source-record, approval-packet and document-binding slice without fabricating financial events or claiming full positive-GRT/production readiness.

**Architecture:** Add one private append-only calculation register at the existing first-loan boundary. Reuse the existing authoritative schedule, exact document projection, private file store, Management/device checks and PostgreSQL transaction machinery. The register holds reviewed precomputed disclosure evidence; actual tax accounting remains in A6.2 after actual source events.

**Tech Stack:** Existing Python/FastAPI/Pydantic/psycopg/PostgreSQL, pytest, and current document tooling. No new dependency or separate financial engine.

**Spec:** `docs/superpowers/specs/2026-09-22-r1-pre-release-tax-disclosure-design.md`, approved by Management in this conversation on 22 September 2026 at commit `8f6659a788f94e5e84b28001b56495e02ac98f7f`.

**Status:** Written specification approved; this implementation plan is submitted for review. No implementation step or new regression test has been executed. PR #449 stays Draft. Execution recommendation: continue inline in the owning chat; no autonomous background workers or automatic merges.

## Global Constraints

- "Extend the existing first-loan approval workflow, not the loan engine or General Ledger."
- "This specification selects no tax rate, gross-up method, exemption, charge entitlement or new fee."
- "Store money as exact currency-cent decimals and transport it as decimal strings; use the existing 18-digit/2-decimal boundary."
- "A first-loan record requires renewal offset to be explicitly zero."
- "Company tax-rule evidence alone is insufficient" as borrower-charge authority.
- "Amount Financed is not inferred from net cash."
- "No SQL migration number is reserved here." The inspected SQL tree ends at 0128; 0129 below is a candidate filename, subject to the execution-time allocation check in Task 2.
- "Do not backfill historical zero taxes, rewrite hashes or regenerate old signed packets using new templates."
- "Production capability activation, migrations, template approval and deployment are separate authorized operations."
- R2/#450 owns renewal summaries; R6/#451 owns staff money serializers; R9/#452 owns mobile temporary images. Coordinate in #448 before touching their files. At this planning check their changed-file lists each contain only their own work brief.

## Review Focus

1. An Employee guesses a calculation/support ID: deny internal-file access even though that Employee can read the office's approved financial summary — Tasks 3 and 5.
2. A request crosses Manila midnight or an applicable rule is inserted concurrently: either accept the still-valid version at a defined transaction boundary or reject the new action without side effects — Tasks 3 and 7.
3. A review succeeds but its response is lost, then its source becomes stale: current authorized readback returns the committed review, but a new approval must reject stale evidence — Tasks 3, 4 and 7.
4. Equivalent decimal spelling, reordered object keys, and non-ASCII support notes: normalize money once and use one explicitly selected digest convention; do not substitute the evidence module's different JSON encoding — Task 1.
5. Private-file persistence succeeds but the database transaction rolls back: exact retry reuses only the same bytes; it never erases another review's evidence or claims that an unreferenced file is a committed record — Tasks 3 and 7.

---

## Delivery boundary and dependencies

This plan delivers **R1-A**, the source-and-binding foundation authorized by the specification's initial-slice boundary. It does not silently expand the existing principal/interest schedule into a new GRT allocator.

A positive borrower-DST deduction can be checked against the existing exact deduction/schedule representation with retained reviewed support. Positive scheduled GRT/other components remain `component_integration_required` until their owning schedule/allocation path is integrated. Recording their reviewed support must not enable approval, signing or release. A fully reconciled arithmetic example is not legal or accounting clearance.

The later requirements remain explicit gates, not discarded work: positive scheduled-GRT allocation and servicing; affected Web/Android/shared-Windows forms; actual product/deduction journal support; and complete document/platform acceptance. Task 8 records their precise handoff criteria. Do not close R1 or #448 on completion of this foundation.

## File ownership map

Paths below are proposed changes, not files claimed to exist already. `B` means `gilbic_backend/src/gilbic_backend`; `T` means `gilbic_backend/tests`. Commands use full paths.

| Path | Responsibility |
| --- | --- |
| New `B/first_loan_disclosure.py` | Strict component/support value contract, canonical digests, exact projection and safe public snapshot. No database or tax calculator. |
| New `B/first_loan_disclosure_repository.py` | Transaction-scoped review, readback, rule/source checks, consumption and support-file authorization. Caller owns the connection/transaction. |
| Modify `B/first_loan_repository.py` | Small delegating methods and approval/lifecycle binding; preserve existing source validation, credential and financial engines. |
| Modify `B/first_loan_api.py` | Protected context/review/readback/support routes and approval's saved ID/digest fields. Register fixed routes before `/{loan_id}`. |
| Modify `B/first_loan_documents.py` | Read saved financial values; require supported disclosure fields without changing historical originals. |
| Candidate `gilbic_backend/sql/0129_add_first_loan_disclosure_source.sql` | One append-only private register, source relationships, immutability/private-schema controls and schema-2 relationship guards. Forward migration only. |
| New `T/first_loan_disclosure_fixtures.py` | Synthetic input builders and explicit reuse of the existing first-loan PostgreSQL setup. |
| New `T/test_first_loan_disclosure.py` | Pure contract, money, projection and digest tests. |
| New `T/test_first_loan_disclosure_postgres.py` | Review/approval/private-storage and no-financial-side-effect tests. |
| New `T/test_first_loan_disclosure_api.py` | Protected HTTP contract, safe errors and public/private response separation. |
| New `T/test_first_loan_disclosure_concurrency_postgres.py` | Committed disposable fixtures and independent database sessions for races/replay. |
| New `T/test_first_loan_disclosure_documents.py` | Saved field mapping, new-template requirements and historical readback. |
| Modify `tools/run_client_onboarding_disposable_postgres_validation.py` | Add the allocated migration and PostgreSQL proofs to the existing guarded runner, not a second runner. |
| Modify `docs/operations/office-first-loan.md` | Current source-review workflow, unsupported cases, activation and recovery instructions. |

Existing `PrivateEvidenceStore`, tax-rule evidence, `FirstLoanTerms`, schedule generation, and `project_loan_document_tax_breakdown` are reused. The new register stores its own support-file metadata using `PrivateEvidenceStore`; **do not add calculation files to the generic office wet-sign evidence table**. Its existing download method permits office readers and must not accidentally become a route to Management-only calculation support [S3]. This choice avoids changing that shared repository or inventing another file store.

## Shared contract for the tasks

All new names here are planned interfaces. Implementation must keep the names consistent, rather than adding parallel adapters for each task.

### Review request and retained record

`DisclosureReviewRequest` uses `extra='forbid'`, the existing `FirstLoanTerms`, and these fields:

| Field | Type / exact rule |
| --- | --- |
| `request_id`, `application_version_id`, `cif_version_id` | UUID. Client and application IDs are resolved server-side; submitted CIF must match. |
| `terms` | Existing `FirstLoanTerms`; keep the same normalized complete terms used by approval. |
| `expected_context_digest` | Lowercase SHA-256 from the protected context route. Covers source versions, normalized terms/schedule/date and selected rule snapshots. |
| `dst_rule_id`, `grt_rule_id` | UUIDs resolving existing correct-type, effective, non-superseded rule evidence. No implicit rule creation. |
| `components` | Strict `DisclosureComponents`: principal, contractual_interest, dst_upfront, grt_in_repayments, renewal_offset, other_upfront_deductions, other_scheduled_charges, total_upfront_deductions, net_proceeds, total_scheduled_payable. All required exact money. |
| `charge_items` | At most 30 strict records: unique normalized `item_id`, `kind`, `timing`, exact `amount`, and nonblank support-section reference. Allowed kinds are `dst`, `grt_recovery`, `other_upfront`, `other_scheduled`; timings must match kind. Every aggregate must match its itemization, and every existing deduction code must map exactly once. |
| `disclosure_values` | Explicit optional values with their own support references: amount_financed, finance_charge_total, non_finance_charge_total, effective_interest_rate, rate_period, calculation_method. `None` means unavailable, never zero. No implicit rate/unit conversion. |
| `borrower_charge_basis` | Nonblank retained-support reference and specific review rationale; include separate reasons for zero/company-borne treatment. It is reviewed support, not proof inferred from a tax-rule row. |
| `calculation_method` | Exactly `reviewed_precomputed_v1` in this slice. No claim of automated tax calculation. |
| `review_rationale` | Nonblank, bounded to 2,000 characters. |
| `support_media_type`, `support_base64` | Existing supported PDF/PNG/JPEG types, decoded maximum 10 MiB. A required original support file, not a URL/path or a hash alone. |
| `supersedes_calculation_id` | UUID or explicit null; a newer review must name the current review in the same application chain. |

The server retains `id`, `version_number`, source IDs, normalized input and source snapshots, exact rule snapshots, review digest, support storage key/hash/type/size, reviewing actor/device and database timestamp. Caller input cannot set review actor, review time, ready status or final packet. Use a server-issued UUID for record identity. A deterministic support storage key derived with `uuid5(request_id, 'spina.r1.support.v1')` permits exact rollback/retry without storing files under a user-provided path; the input/actor binding and `PrivateEvidenceStore` byte checks remain mandatory.

Public readback exposes the calculation ID/digest, source version, `financial_snapshot`, `approval_ready`, ordered `blockers` and review time. It does not expose raw support, storage keys, internal rationale or private support references. Management support access is a separate protected route. Historical readback returns saved data; readiness is current metadata and never rewrites the saved snapshot.

### Planned internal interfaces

Use `dict[str, object]` for the existing repository-style envelopes. Strict nested value models validate the public contract; do not use unvalidated arbitrary dictionaries for financial inputs.

```python
# first_loan_disclosure.py
# parse_components(payload: dict) -> DisclosureComponents
# canonical_review_digest(payload: dict) -> str
# project_components(components: DisclosureComponents, *,
#                    references: dict[str, str]) -> dict[str, str]
# public_financial_snapshot(review_snapshot: dict) -> dict
# require_component_compatibility(terms: FirstLoanTerms, rows: tuple,
#                                 components: DisclosureComponents) -> None
# Raises FirstLoanConflict for unsupported or inconsistent usable bindings.

# first_loan_disclosure_repository.py — operate inside the caller's transaction
# review_context(cursor, *, application_version_id: UUID, cif_version_id: UUID,
#                terms: FirstLoanTerms, dst_rule_id: UUID, grt_rule_id: UUID) -> dict
# record_review(cursor, *, actor_user_id: UUID, registered_device_id: UUID,
#               request: DisclosureReviewRequest, support: bytes) -> dict
# read_review(cursor, *, calculation_id: UUID, application_version_id: UUID) -> dict
# require_for_approval(cursor, *, calculation_id: UUID, expected_digest: str,
#                      application_version_id: UUID, terms: FirstLoanTerms,
#                      rows: tuple) -> dict
# require_packet_source(cursor, *, approval_row: dict, action: str) -> None
# support_content(cursor, *, actor_user_id: UUID, registered_device_id: UUID,
#                 calculation_id: UUID, application_version_id: UUID) -> tuple[str, bytes]
```

`references` must supply exactly the four nonblank reference names required by the existing document projection: `loan_version_reference`, `tax_loan_version_reference`, `tax_rule_snapshot_reference`, and `tax_calculation_reference`. The two loan-version references must match. Repository callers construct these from the verified saved source; synthetic strings are allowed only in explicitly synthetic pure tests.

`require_packet_source` accepts only `generate`, `sign`, `authorize_release`, or `release`; it is never called to repeat an already committed financial transition. No new helper imports `first_loan_repository` at module initialization if that creates a cycle: pass source context from the owning repository, or use the existing method-local import style. Reuse `FirstLoanConflict` via a method-local import where required; do not refactor the entire existing repository for exceptions.

---

## Task 1 — Pin exact inputs, digests and component readiness

**Files:** new `B/first_loan_disclosure.py`, `T/first_loan_disclosure_fixtures.py`, `T/test_first_loan_disclosure.py`.
**Consumes:** existing term/schedule and document projection functions.
**Produces:** the pure interfaces above plus `DisclosureComponents` and `DisclosureReviewRequest`.

- [ ] Write the synthetic component builder and these actual-module tests first. During the initial RED commit use a test-body `import_module` and `pytest.fail` for the missing module; do not introduce collection errors, skipped new cases or production stubs.

```python
# first_loan_disclosure_fixtures.py

def component_values(**changes):
    result = dict(principal='1000.00', contractual_interest='200.00',
        dst_upfront='10.00', grt_in_repayments='0.00', renewal_offset='0.00',
        other_upfront_deductions='0.00', other_scheduled_charges='0.00',
        total_upfront_deductions='10.00', net_proceeds='990.00',
        total_scheduled_payable='1200.00')
    result.update(changes)
    return result
```

These values are arithmetic fixtures, **not a tax rate or supported live tax calculation**. Database acceptance fixtures separately retain applicable rule/calculation support.

```python
from copy import deepcopy
from importlib import import_module
import pytest
from first_loan_disclosure_fixtures import component_values

def subject():
    try:
        return import_module('gilbic_backend.first_loan_disclosure')
    except ModuleNotFoundError as error:
        if error.name != 'gilbic_backend.first_loan_disclosure':
            raise
        pytest.fail('R1 disclosure contract is not implemented', pytrace=False)

@pytest.mark.parametrize('bad', [True, 10.0, '10.001', '-1.00', 'NaN',
                                'Infinity', '10000000000000000.00'])
def test_money_rejects_inexact_or_out_of_range(bad):
    with pytest.raises(ValueError):
        subject().parse_components(component_values(dst_upfront=bad))

def test_exact_projection_never_mutates_inputs():
    original = component_values()
    before = deepcopy(original)
    references = dict(loan_version_reference='SYN-TERMS-1',
        tax_loan_version_reference='SYN-TERMS-1',
        tax_rule_snapshot_reference='SYN-RULES-1',
        tax_calculation_reference='SYN-CALC-1')
    result = subject().project_components(
        subject().parse_components(original), references=references)
    assert result['net_proceeds'] == '990.00'
    assert result['total_scheduled_payable'] == '1200.00'
    assert original == before

def test_missing_is_not_zero():
    values = component_values()
    del values['grt_in_repayments']
    with pytest.raises(ValueError):
        subject().parse_components(values)
```

- [ ] Run `python -m pytest -q gilbic_backend/tests/test_first_loan_disclosure.py`; record the precise RED failures, then implement strict parsing. Normalize accepted money to two-decimal strings before hashing. Reject fractional cents; never silently round inputs.
- [ ] Implement projection by calling `project_loan_document_tax_breakdown` with the reviewed record's validated references and expected totals. Do not put invented reference IDs inside persisted records. Test the helper with explicitly synthetic references only.
- [ ] Test required-zero versus missing, duplicate item IDs, DST appearing in generic deductions twice, GRT upstream deduction, overflow and exact sums. Use `localcontext` sufficient for 18-digit values and at most 30 items; reject out-of-range outputs instead of changing global Decimal precision.
- [ ] Pin digest behavior using the existing **first-loan** `snapshot_digest` convention over normalized JSON-safe values. Tests cover reordered keys, `10`/`10.0`/`10.00`, Unicode notes and a changed amount. Do not swap in the office-evidence digest, whose encoding differs [S3]. A digest proves consistency, not authority.
- [ ] `require_component_compatibility` compares principal/interest/deductions to the existing term and installment rows. Nonzero scheduled GRT/other components raise `component integration required`; even a balanced alternative split may not relabel existing interest.
- [ ] Run the new tests plus `test_first_loan_terms.py` and `test_loan_document_tax_breakdown.py`; commit only this tested contract slice with a descriptive `feat(r1)` message.

## Task 2 — Add the private append-only register and guarded database proof

**Files:** candidate `gilbic_backend/sql/0129_add_first_loan_disclosure_source.sql`; new `T/test_first_loan_disclosure_postgres.py`; existing guarded runner.
**Consumes:** Task 1 canonical input contract and existing private-schema/first-loan models.
**Produces:** `lending.first_loan_disclosure_calculations`, including source relationships, unique retries and immutable version history.

- [ ] Before reserving a migration number, read live main, every open PR's changed files and #448's latest allocation comments. At planning, the inspected SQL tree ends at 0128 and #450/#451/#452 contain no SQL. Reserve 0129 in #448 only if still unclaimed; if claimed, allocate the actual next unused ID and change this plan's filename references once before publication. Never rewrite existing migrations.
- [ ] Add a failing catalog/control test to the existing disposable runner. It must assert the table, FK/unique/immutability/private access controls exist; a missing migration is a RED result, not a skipped test. Preserve the runner's loopback-only `spina_onboarding_` database creation and `finally` cleanup.

```sql
-- Core relationships to include in the allocated forward migration.
-- Additional exact checks below are part of this task, not optional extensions.
CREATE TABLE lending.first_loan_disclosure_calculations (
  id uuid PRIMARY KEY,
  request_id uuid NOT NULL UNIQUE,
  application_id uuid NOT NULL REFERENCES lending.loan_applications(id),
  application_version_id uuid NOT NULL REFERENCES lending.loan_application_versions(id),
  client_id uuid NOT NULL REFERENCES lending.clients(id),
  cif_version_id uuid NOT NULL REFERENCES lending.client_cif_versions(id),
  version_number integer NOT NULL CHECK (version_number > 0),
  supersedes_calculation_id uuid UNIQUE REFERENCES lending.first_loan_disclosure_calculations(id),
  dst_rule_id uuid NOT NULL REFERENCES accounting.v1_tax_rule_evidence(id),
  grt_rule_id uuid NOT NULL REFERENCES accounting.v1_tax_rule_evidence(id),
  request_digest text NOT NULL CHECK (request_digest ~ '^[0-9a-f]{64}$'),
  review_digest text NOT NULL CHECK (review_digest ~ '^[0-9a-f]{64}$'),
  review_snapshot jsonb NOT NULL CHECK (jsonb_typeof(review_snapshot) = 'object'),
  support_storage_key uuid NOT NULL UNIQUE,
  support_sha256 text NOT NULL CHECK (support_sha256 ~ '^[0-9a-f]{64}$'),
  support_media_type text NOT NULL CHECK (support_media_type IN ('application/pdf','image/png','image/jpeg')),
  support_byte_count integer NOT NULL CHECK (support_byte_count BETWEEN 1 AND 10485760),
  reviewed_by_user_id uuid NOT NULL REFERENCES core.users(id),
  reviewed_device_id uuid NOT NULL REFERENCES core.devices(id),
  reviewed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  UNIQUE(application_id, version_number),
  CHECK(supersedes_calculation_id IS NULL OR supersedes_calculation_id <> id)
);
```

- [ ] Add cross-source checks against the existing application/version/client/CIF relationships; separate simple FKs do not prove they belong together. A successor must name the current review of the same application, use the next version, and never branch from an already superseded record. Add an index on `(application_version_id, version_number)` and verify request lookups use the unique key.
- [ ] Reject UPDATE/DELETE through a trigger; validate INSERT actor/device and source relationships through a narrow guard. Revoke PUBLIC/anon/authenticated table access using the existing private-schema pattern; no browser database grants. Preserve backend transaction access. Do not claim a custom session variable alone protects against a database owner.
- [ ] Extend schema-2 approval relationship checks in this forward migration without modifying historical SQL. The calculation ID/digest/source must match the packet when present; schema-1 historical originals remain readable. Do not seed reviewed calculations, rules, live facts or approvals.
- [ ] Register this migration and the new PostgreSQL test paths in `CIF_MIGRATIONS`/`FULL_FLOW_TESTS`. Run the guarded runner using the already configured **disposable local** credentials; no production URL or migration CLI is an acceptable substitute. Verify exact failures then GREEN, including a second installation attempt under the repository's migration contract; commit schema and proofs together.

## Task 3 — Record and read back one authorized review

**Files:** new `B/first_loan_disclosure_repository.py`; delegating methods in `B/first_loan_repository.py`; `T/first_loan_disclosure_fixtures.py`, `T/test_first_loan_disclosure_postgres.py`.
**Consumes:** Tasks 1–2, existing `_actor`, `_source`, `PrivateEvidenceStore`, approved tax-rule rows.
**Produces:** `review_context`, `record_review`, `read_review`, `support_content` and owning repository delegation.

- [ ] Reuse `test_first_loan_postgres.setup(connection, monkeypatch)` and its `private_fixture_configuration`, `connection` and `runtime_url` fixtures explicitly. Add a named `record_synthetic_review` fixture helper; it obtains source context and inserts test-only rules through `PostgresV1TaxEvidenceRepository.record_rule`, then calls the real new review method. Do not insert a ready flag or bypass production source checks in a fixture.
- [ ] First write a test that snapshots the selected client's actual-event tables before recording: loan/disbursement/collection/first-loan release/credential-intent/actual DST/actual percentage-tax/journal rows. Recording changes only its review, retained support metadata and scoped audit. Compare full relevant rows or stable row hashes, not just net money totals.
- [ ] Require canonical active Management, `lending.first_loan.approve` and its own persisted active device before parsing/storing private bytes. Source context is server-derived from current confirmed application/CIF, normalized terms and existing schedule. Resolve tax-rule types, date range, maturity restrictions and supersession; retain immutable snapshots. The initial method is a **human-reviewed precomputed** calculation, not an automated-tax certificate.
- [ ] Serialize by stable request key and application review chain. For the relatively infrequent tax-rule writes, use a bounded `SHARE` lock on `accounting.v1_tax_rule_evidence` before authoritative rule reads in a READ COMMITTED transaction. This conflicts with an INSERT's automatic ROW EXCLUSIVE lock; row-locking only an old rule would not prevent a newer-rule insert [P1–P2]. Use a short `SET LOCAL lock_timeout`; rollback and return an existing safe conflict response on timeout/deadlock. Do not hold these locks during PDF conversion or external calls.

```sql
SET LOCAL lock_timeout = '2s';
LOCK TABLE accounting.v1_tax_rule_evidence IN SHARE MODE;
-- Only now resolve applicable rule rows and latest version under READ COMMITTED.
-- The caller then uses existing source locks and holds this lock to transaction end.
```

- [ ] Persist `PrivateEvidenceStore.put` using the deterministic server-derived support key only after source/input checks. Retain original bytes and metadata in the same reviewed transaction; call `.read` to verify exact bytes before consuming. A rollback may leave a private unreferenced file, as in the existing storage contract; retain it for exact retry, do not delete arbitrary paths.
- [ ] Compute the immutable request digest from normalized payload and support content hash, excluding server-generated record identity/time. Identical authorized retries return the saved ID and digest even if current source readiness later changes. Different actor/payload/support with the same request UUID fails. No audit duplication on replay.
- [ ] Record missing required disclosure fields or unsupported positive scheduled components as explicit blockers on the reviewed record's readback; never make them approval-ready. Wrong source, invalid amounts, unbound/corrupt support or spoofed authority is rejected, not retained as approved evidence.
- [ ] Implement Management-only `support_content`; retain office access only to allowlisted financial summary/readiness. Test a guessed correct record ID using an Employee and another source application. Run the new PostgreSQL proof through the guarded runner; commit only after rollback, replay and file-integrity cases pass.

## Task 4 — Bind the saved review to approval and all new actions

**Files:** `B/first_loan_repository.py`, `B/first_loan_disclosure_repository.py`; `T/test_first_loan_disclosure_postgres.py` plus directly affected first-loan fixtures.
**Consumes:** Task 3 reviewed record; existing first-loan approval/signature/release functions.
**Produces:** `require_for_approval`, `require_packet_source`, packet schema 2 and singular historical readback.

- [ ] Add the failing exact-binding cases before changing approval. In the explicit new-review test fixture obtain the saved ID/digest, call the actual approval method, and assert the packet contains exactly that safe snapshot. Change terms, application, CIF, rule, digest and source date one at a time: approval must fail with no new loan/approval/financial rows.
- [ ] Extend approval with `disclosure_calculation_id`/`expected_disclosure_digest`; use the same transaction to revalidate and copy the allowlisted financial snapshot into `packet['tax_disclosure']`, set schema 2, then retain its relationship to the newly allocated loan/packet. Never accept a client-provided final packet. Keep current loan, schedule and credential sequencing.

```python
# Required integration order inside the already-authorized approval transaction:
# rows = generate_first_loan_schedule(terms)
# disclosure = require_for_approval(cursor,
#     calculation_id=disclosure_calculation_id,
#     expected_digest=expected_disclosure_digest,
#     application_version_id=application_version_id, terms=terms, rows=rows)
# packet['schema_version'] = 2
# packet['tax_disclosure'] = disclosure
# Existing save computes snapshot_digest(packet) and retains actor/device.
```

- [ ] Add saved source ID/digest to immutable approval retry comparison. Do not call current-source validation before returning an already committed identical approved result; return historical result plus current blockers. Authorization remains current even for readback.
- [ ] Call `require_packet_source` before registering generated documents, capturing new contract/cash evidence, authorizing release and committing a new release. Keep actual server business-date check, existing source locks and current packet/hash/evidence guards. A newly superseded source blocks a new action and requires controlled cancel/reapprove/re-sign; do not mutate the old packet.
- [ ] No bypass flag: activating this contract means new approvals require the source pair. Missing pairs produce the explicit source-required response. Existing released schema-1 originals and completed release retries remain readable/singular; previously approved but unreleased schema-1 packets cannot perform new issuance/release under the new contract. Do not automatically cancel or backfill them.
- [ ] Run affected first-loan tests with explicit schema-1 historical fixtures and explicit schema-2 review setup. Do not weaken assertions or silently manufacture review evidence in global fixtures. Commit the bound lifecycle once the new RED-to-GREEN cases pass.

## Task 5 — Expose protected context, review and readback contracts

**Files:** `B/first_loan_api.py`, `T/test_first_loan_disclosure_api.py`.
**Consumes:** Task 3 repository delegates and Task 4 approval arguments.
**Produces:** these routes under existing `/api/v1/management/first-loans`, placed before the generic loan ID route:

| Route | Permission and semantics |
| --- | --- |
| `POST /disclosure-context` | Management + approve permission + active device; accepts proposed source/terms/rule IDs; returns server context/digest, no financial event. |
| `POST /disclosure-calculations` | Same controls; strict review request and bounded support upload; returns saved review ID/digest and derived blockers. |
| `GET /disclosure-calculations/by-request/{request_id}` | Same Management controls and reviewing-actor ownership for lost-response recovery; no arbitrary cross-user request discovery. |
| `GET /disclosure-calculations/{calculation_id}?application_version_id=...` | Existing authorized office readers get financial summary/readiness only; verify exact application relationship. |
| `GET /disclosure-calculations/{calculation_id}/support?application_version_id=...` | Management + approve permission + active device only; verified bytes, correct content type, no-store, no static/private-path redirect. |
| Existing `POST /approve` | Add the saved source pair and preserve canonical Management approval; missing/partial pair cannot downgrade to old behavior. |

- [ ] Follow existing dependency-injected API tests; assert missing new routes in test bodies for the initial RED commit. Use fake auth/record repositories for API-boundary tests only; PostgreSQL proofs remain separate.
- [ ] Test unauthenticated, inactive/revoked device, wrong role, missing permission, forged server audit fields, invalid base64, over-limit content, guessed foreign IDs and cache headers. Normal invalid input stays 422; unauthorized access 403; stale/unsupported binding 409 with a safe explanation. A support-reference mismatch must not reveal another client's IDs or file metadata.
- [ ] Implement the routes using existing actor dependencies and `execute` error translation. Extend protected context metadata to advertise `disclosure_source_required`; no new public guest flow and no Supabase direct table access.
- [ ] Test exact decimal strings in JSON and absence of storage keys/internal rationale/support bytes in office responses, Client documents, standard first-loan readback and logs. Logging a whole review request is prohibited.
- [ ] Run the new API tests plus existing first-loan API and evidence tests. Commit the tested boundary; report UI integration as outstanding, not automatically implemented by OpenAPI routes.

## Task 6 — Render only the bound financial snapshot

**Files:** `B/first_loan_documents.py`, `T/test_first_loan_disclosure_documents.py`, `docs/operations/office-first-loan.md`.
**Consumes:** Task 4 schema-2 packet and Task 1 exact projection.
**Produces:** saved `dst_upfront`, `grt_in_repayments`, component totals and separately supported Amount Financed/EIR fields in new legal packets.

- [ ] Start with pure `packet_fields` tests using a synthetic schema-2 record. Assert exact values and identical repeats across document mappings; tampered packet hash, missing source, non-reconciling totals and unavailable mandatory disclosure values fail. Test that a correctly supported Amount Financed different from net cash remains different.
- [ ] Reuse the existing projection after source validation. Use the saved source values, not current tax-rule queries or another tax calculator inside rendering. Public financial fields contain no internal support paths, review rationale or borrower-charge-source document.
- [ ] Keep the existing common PDF field checks. For schema-2 disclosure templates require the named new mandatory disclosure fields as applicable to the approved template contract; missing fields block generation rather than being silently omitted. Do not mark or seed a template legally approved. Test the same semantics in disclosure/agreement and complete Annex without inventing an extra schedule.
- [ ] Test historical readback using retained released schema-1 bytes, not regeneration. Do not change their digest, fonts or metadata as part of this task. Preserve existing converter/font/integrity checks for new packets.
- [ ] Run new mapping tests, retained document tests and the existing real converter proof where available. Document any unavailable converter/device evidence rather than claiming it ran. Update operational instructions with source review, source-required responses, blocked GRT/component cases, and exact retry; commit the tested mapping and guide together.

## Task 7 — Prove races, rollback and restart-safe readback

**Files:** `T/test_first_loan_disclosure_concurrency_postgres.py`, `T/test_first_loan_disclosure_postgres.py`; only minimal fixes in the owning source modules.
**Consumes:** Tasks 2–6 with the actual PostgreSQL locks and immutable storage.
**Produces:** evidence for R1-11/12 and the five Review Focus conditions.

- [ ] Use independent connections in a newly created guarded disposable database, not two cursors on one connection or a mocked lock. Seed and commit synthetic source records before starting workers; retain original fixture names/owner assertions. No shared/live database or cleanup of company data.
- [ ] Race identical review UUIDs: one record, one audit, same stored content and result. Race different payloads using one UUID: one wins, the other conflicts. Race two successors of one calculation: at most one becomes its successor.
- [ ] Race an actual protected rule insertion against review/approval/new release. Synchronize at the real SQL boundary, not with arbitrary sleeps. Verify either the earlier valid action commits before the rule writer, or the new action sees the newer rule and fails. A row lock on only the old rule is not sufficient. Test timeout/deadlock paths leave no partial transition.
- [ ] Test source/CIF invalidation between context and review, review and approval, and authorization and release. Preserve existing CIF database guard behavior. A read-only replay must still return already committed outcomes subject to current access control.
- [ ] Inject failure after file persistence and after audit/record writes. A database rollback leaves no committed calculation/approval/journal. Repeating the identical request reuses the exact private support file; changed bytes fail, never overwrite. Missing/corrupt file after restart blocks a new action but does not delete historical records.
- [ ] Test near-midnight planned date versus the actual server business date. Never use device date as release authority. These are synthetic clock/date fixtures, not modified production timestamps.
- [ ] Run new race cases and retained onboarding/tax/first-loan proofs through the existing runner. Commit only if evidence establishes the failure before the fix and the expected behavior after it; report any unproven race as open.

## Task 8 — Acceptance, dependent handoff and activation barrier

**Files:** existing guarded runner, `docs/operations/office-first-loan.md`, this plan's checkboxes and PR #449/#448 evidence records. No broad CI rewrite.
**Consumes:** actual results from Tasks 1–7 and unchanged owning financial regression suites.
**Produces:** an R1-A acceptance record and explicit unmet R1 completion gates.

- [ ] Run the new pure/API/document tests, existing first-loan/document/tax suites and combined disposable proof once for the relevant integrated code head. Use the existing full SPINA CI, including the three current lanes, on the published candidate. Reuse unchanged prior evidence as history; never relabel it as newly executed on a changed source.
- [ ] Verify the changed-file boundary with `git diff --check` and the PR diff. Confirm no R2 renewal-summary edits, R6 money-model changes, R9 image cleanup, production fixtures, secrets, financial seed rows or historical migration rewrites.
- [ ] Record R1-A acceptance only when authorized source recording, exact review-to-packet binding, private support access, compatible document mapping, no-event recording, replay and races are proven. Keep PR Draft until the separately authorized integration decision.
- [ ] Track dependent **R1-B**: add authoritative positive-GRT component representation and servicing/allocation using an explicitly reviewed calculation policy. Acceptance must include a genuinely positive scheduled-GRT case with unchanged agreed repayments, component identity, early-payoff/adjustment behavior and no duplicate charges. This plan does not invent that policy or a residual-interest split.
- [ ] Track dependent **R1-C**: integrate the source selection/breakdown in the existing Web and Android first-loan forms, coordinate shared files with #451/#452, and verify the Windows shared-Web experience. Server endpoints alone do not satisfy R1-16. Existing clients must present a clear source-required/update-required result, not bypass the gate.
- [ ] Track dependent **R1-D**: demonstrate supported accounting for each intended positive deduction/product using the existing protected journal owner, exact release and actual collection sources. Preserve `automatic_source_posting=false`; actual tax liability, filing, payment and company activation remain separate. No calculated borrower deduction is proof of a posted liability.
- [ ] Keep actual production activation blocked until B/C/D plus current legal-template/operator and platform acceptance are complete. No migration application, signing secret change, live financial record, merge or deployment is part of plan approval.

### Coverage of the approved specification

| Spec tests | Foundation ownership and completion boundary |
| --- | --- |
| R1-01–03 | Tasks 2–5: source recording without financial events; exact source identity; canonical role/device checks. |
| R1-04–05 | Tasks 3, 5, 7: effective rules and retained evidence; public/private separation. |
| R1-06–08 | Tasks 1, 3, 6: explicit zero/missing/company-borne distinctions, exact money and itemization. |
| R1-09 | Tasks 1, 3, 4: positive unsupported splits explicitly blocked. Positive enablement is R1-B, not claimed by this foundation. |
| R1-10 | Tasks 1, 3, 6: mandatory independent Amount Financed/EIR support. No automatically calculated rate is introduced. |
| R1-11–12 | Tasks 3, 4, 7: same-request identity, supersession, audit rollback and actual independent-session races. |
| R1-13–14 | Tasks 4, 6, 7: new-action source guard; historical original preservation and singular committed-result replay. |
| R1-15 | Tasks 3/8 prove no premature actual-event posting and preserve existing A6.2 regressions; full supported positive lifecycle reconciliation remains R1-D. |
| R1-16 | Task 5 covers the API boundary only. Web/Android/Windows interaction and device/browser acceptance remain R1-C. |

## Verification record and next action

Plan self-review: checked the approved specification, task interfaces, exact file owners, money/input boundaries, actual-event timing, private evidence routing, old/new packet separation, lock behavior and the coverage table. No new executable product test was run while writing this plan. The container could not download the public source archive because GitHub DNS failed; connected GitHub reads succeeded. This is not a local checkout or full-suite verification claim.

**Next action:** Management reviews this plan and selects execution. Recommended method is inline execution in the PR #449 chat, with the existing GitHub checks and explicit review of each finished slice. The design direction and written specification are already approved and must not be asked again. Plan approval permits starting Task 1's real RED-to-GREEN work; it is not permission to merge, deploy or activate company transactions.

Do not request another permission round merely to run an already-approved task's test/fix cycle. Stop for an actual new business-rule decision, scope change, conflicting owner change, or operation outside this plan. Keep #448, Notion and Create State synchronized with exact source, executed evidence and the next unfinished task.

## Sources used for this plan

- **S1:** Approved specification at `8f6659a788f94e5e84b28001b56495e02ac98f7f`, linked above; source observations are also in PR #449 and coordination #448.
- **S2:** Existing `first_loan_api.py`, `first_loan_repository.py`, `first_loan_terms.py`, `first_loan_documents.py` and `loan_document_tax_breakdown.py` at that commit.
- **S3:** `office_review_evidence_repository.py`, especially `capture_evidence`, `require_evidence`, `snapshot_digest` and `get_content`; existing `PrivateEvidenceStore` contract.
- **S4:** `test_first_loan_postgres.py`, `test_first_loan_terms.py`, and `tools/run_client_onboarding_disposable_postgres_validation.py` at that commit; full SQL tree `48fae2a7232cd4a001bf7f404fb93dcc59816d86` through 0128.
- **P1:** PostgreSQL 18, Explicit Locking: https://www.postgresql.org/docs/18/explicit-locking.html (SHARE/ROW EXCLUSIVE conflicts, transaction lifetime and deadlock caution).
- **P2:** PostgreSQL 18, Transaction Isolation: https://www.postgresql.org/docs/18/transaction-iso.html (READ COMMITTED statement snapshots; do not substitute a previously established REPEATABLE READ snapshot).
