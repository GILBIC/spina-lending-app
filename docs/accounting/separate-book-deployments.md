# Separate accounting book deployments

SPINA uses one immutable accounting book identity per database. The owner confirmed on 10 October 2026 that there are no existing accounting books. The immediate task is first-book setup from verified available records, without assuming a prior ledger or a separate existing business. If a separate legal entity is later established, its book requires an independent database running the same reviewed accounting code. Protected journals, periods, account keys, source keys and posting functions remain scoped by that database boundary.

## Starting the first book

Configure the verified entity identity and fiscal periods before recording new transactions. Identity setup posts no money and requires no old ledger or opening journal. Actual initial capital uses the protected initial-capital workflow. If prior cash, outstanding loans or obligations exist, review the available operational evidence and use the protected opening workbook only for supported balances at the selected cutover. Absence of old books is not evidence of zero balances. When no opening balances are needed, actual transactions may begin directly; an empty first period can close without an artificial zero journal.

Keep unknown amounts pending and visible. Reports should show that there is no prior comparison period rather than fabricate a preceding ledger. Record the basis of any opening amounts and distinguish them from current-period cash flows. See [the first-book runbook](first-book-setup.md).

## Current implementation boundary

Migration `0144_add_accounting_book_identity.sql` adds an initially empty `accounting.book_identity` singleton and private setup/context functions. It does not identify a real company, transfer historical rows, post opening balances, or activate Treasury accounting. Existing ledger operations are not globally blocked merely because identity is unconfigured. New Treasury accounting adapters must explicitly require the identity and matching context/account.

An active Management user with `accounting.journal.manage` may configure the identity through the backend. Management with `accounting.view` may read it. Setup stores the book UUID, kind, exact entity label, retained evidence reference and lowercase SHA-256 digest, authenticated actor and timestamp. A reference/digest is an attestation record: setup does not fetch a document or certify its truth, legal effect, or continued availability.

An exact retry from the same actor returns the same book UUID without changing its evidence or timestamp. Changed kind, label, evidence or actor conflicts. Setup requires READ COMMITTED transactions so the locked fresh-database check sees prior commits; the backend already uses that default. Identity rows reject update, delete and truncate. Correcting an erroneous configured identity requires a separately reviewed recovery/migration procedure; there is no relabel button or automatic reset.

Owner setup may explicitly adopt existing owner operations. Corporate or synthetic setup must occur before business data is entered. The function locks and checks independent roots: loans, journals, Treasury accounts, opening-balance workbooks, initial funding evidence, tax-rule evidence, imported historical credit datasets and cancelled-draft audit. Treasury accounts anchor Collector credits/openings and all Treasury movements through foreign keys. Existing seed chart accounts, users and open fiscal periods do not themselves block setup. Reviewed/closed periods and retained close preparations do block it, including zero-activity closes without a journal. This check does not replace fresh-database provisioning and inspection of any future independently added business tables.

## Independent company deployment

1. Provision a clean database with distinct database credentials and apply the repository's numbered migrations with its reviewed bootstrap process. Do not restore an owner database and change its label. Do not send a connection string or SQL schema from a browser or mobile request.
2. Configure independent authentication/authorization records, device registrations, private evidence storage and backup destinations. A future deployment switch must authenticate into the selected deployment and clear cached private state. Separate browser origins and explicit deployment/book labels prevent confusion.
3. Keep business entry disabled while an authorized manager verifies retained company identity evidence and creates the identity. The company kind is `corporate_legal`; a book for owner operations uses `owner_operations`; disposable verification is `synthetic`. These options do not establish that either real book already exists. Migration files must not seed any actual identity.
4. Set `GILBIC_EXPECTED_ACCOUNTING_BOOK_ID` to the retained book UUID after setup. Every backend connection checks it and rejects a mismatched or unconfigured database, then ends the read probe before business queries. Omit/unset this variable only during initial setup or an intentionally unconfigured legacy deployment; an explicit empty string is not a valid UUID. A legacy deployment must not be mistaken for a configured owner or company book.
5. Independently configure fiscal periods, private evidence retention, chart policies and supported opening figures. Any transfer between owner and company needs reviewed source evidence and distinct accounting on each side. Do not copy owner journals into the company's history or infer a shareholder loan as capital.
6. Independently test backup restore and restore identity verification, authorization denial, wrong-database configuration and the accounting lifecycle. Verify that each deployment's credentials cannot read the other's business rows. The code-only identity change does not provision or prove that infrastructure isolation.

The private table has RLS enabled with no client policies. PUBLIC, `anon`, `authenticated` and `service_role` receive no table/function access. Functions are SECURITY INVOKER with pinned search paths. The existing backend database-owner model continues to work. A deployment using a distinct least-privilege backend database role needs an explicitly reviewed role/grant/RLS configuration; do not grant browser roles access or add SECURITY DEFINER to bypass a deployment error. See [Supabase grants and RLS documentation](https://supabase.com/docs/guides/database/postgres/row-level-security).

## Backend contract

GET `/api/v1/management/financial-accounting/book` and the `/api/mobile/v1/...` alias return:

```json
{"success":true,"data":{"book":{"status":"unconfigured","book_id":null,"kind":null,"entity_label":null,"evidence_reference":null,"evidence_digest":null,"configured_by_user_id":null,"configured_at":null},"can_configure":true}}
```

POST the same path accepts only `kind`, `entity_label`, `evidence_reference`, `evidence_digest`, and `confirm: true`. The authenticated actor is supplied by the server. Whitespace is not silently trimmed from retained text, unknown fields are rejected, and confirmation must be a boolean. No endpoint accepts a database connection, book selector, or actor override.

`PostgresAccountingBookRepository.get_book_identity()` returns an identity or `None`. `read_book_identity(cursor)` uses a caller-owned dict-row cursor so statement reports can retain their existing consistent snapshot. `book_identity_payload()` distinguishes configured from unconfigured state.

Source adapters must call these private functions within the same transaction as preparation/posting:

- `accounting.require_book_treasury_context(context_id UUID) RETURNS UUID`: require configured identity and exact matching context kind; retain a share lock on the context through the transaction.
- `accounting.require_book_treasury_account(account_id UUID) RETURNS UUID`: also require an active account and compatible ownership; retain a share lock on the wallet. Company permits only `corporate`, owner permits `owner_personal`/`owner_business`, and synthetic permits only `synthetic`.

These functions are accounting compatibility guards, not user authorization. Source adapters must still require current actor/device/account permissions, bind exact source/mapping coordinates and preserve existing immutable posting controls. Migration 0137/0139 accounting admission blockers remain in place until exact protected adapters replace them.

## Verification handoff

`test_accounting_book_api.py` checks auth/role/permission boundaries, unconfigured output, retained setup evidence, confirmation and input restrictions, error responses and mobile parity. `test_accounting_book_postgres.py` checks real protected setup, exact retries, immutable history, current authority, private grants, context/account compatibility and the repository's existing-transaction adapters. `test_accounting_book_isolation_postgres.py` uses two synthetic databases and the actual connection/statement implementations to check wrong-UUID deployment rejection and distinct journals/report identities. It proves application binding; it does not prove production infrastructure credentials or storage ACLs.

PostgreSQL tests require `GILBIC_TEST_DATABASE_URL`, `SPINA_ALLOW_DISPOSABLE_DATABASE=1`, a loopback host and a task-owned database name matching `spina_treasury_validation_[a-f0-9]{24}`. Run them before suites that commit other synthetic business sources. They roll back each fixture; they do not connect to production or prove two deployed databases are independently permissioned.
