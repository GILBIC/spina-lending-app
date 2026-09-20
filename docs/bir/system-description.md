# System description — engineering preparation notes

This describes the repository's canonical accounting path. It is a field-preparation aid for a reviewed system summary, not a completed official Annex C-1, sworn statement or filing. Taxpayer identity, branch scope, production infrastructure and maintainer facts must come from the private approved profile/evidence.

## Product and authority

Spina supports lending, collections, employee operations and protected accounting. The canonical backend is Python/FastAPI with PostgreSQL and Supabase authentication integration. The web portal and Flutter client use server-authorized APIs. Native V1 acceptance covers Windows and Android; repository iOS targets do not prove iOS release acceptance. A legacy Python/Tkinter desktop path also exists; assess its actual installed use and any interface separately rather than claiming every historical desktop table is the canonical ledger.

Record the exact source SHA/tree and actual deployed package versions, using [backend metadata](../../gilbic_backend/pyproject.toml), [Flutter metadata](../../gilbic_mobile/pubspec.yaml) and the retained release manifest. A package version alone is insufficient to identify a submitted build. Hosting/provider/account ownership remains declared evidence, not a fact inferred from deployment scripts.

## Financial data and process

| Stage | Actual source/control | Preparation boundary |
| --- | --- | --- |
| Identity and access | [request_auth.py](../../gilbic_backend/src/gilbic_backend/request_auth.py) derives authenticated account/device context; accounting routes require Management and the relevant permission. | Actual staff assignments, authenticator policy, revocation administration and service-account access need review. |
| Lending and collections | Registered API routers in [main.py](../../gilbic_backend/src/gilbic_backend/main.py); shared collection contracts in [spina_backend_mobile](../../spina_backend_mobile/src/spina_mobile_collections). | A collection record is operational evidence, not automatic authority for every accounting or tax posting. |
| Accounting | [0021 foundation](../../gilbic_backend/sql/0021_add_accounting_foundation.sql) and [0024 General Journal](../../gilbic_backend/sql/0024_add_manual_general_journal_and_trial_balance.sql) define accounts, periods, balanced posting, source identity, immutable posted records, reversal relationships and cancelled-draft audit. Later modules use this protected ledger. | Explicit authorized preparation/posting and evidence prerequisites remain. No second ledger is introduced by the export. |
| Statements and tax workflows | [financial_statements_repository.py](../../gilbic_backend/src/gilbic_backend/financial_statements_repository.py) reads posted activity; [tax policy](../accounting/v1-tax-accounting-policy.md) describes protected evidence-based tax workflows. | Software calculations do not establish taxpayer classification, return filing or payment of actual tax. |
| Review export | [accounting_export_repository.py](../../gilbic_backend/src/gilbic_backend/accounting_export_repository.py) reads the ledger; [accounting_export.py](../../gilbic_backend/src/gilbic_backend/accounting_export.py) prepares the bounded review bundle. | Export completion and sample review require evidence for the exact candidate and chosen period. |
| Retention and recovery | [private evidence storage](../../gilbic_backend/src/gilbic_backend/office_review_evidence_storage.py), [privacy manifest controls](../../gilbic_backend/src/gilbic_backend/privacy_record_repository.py), [backup/restore drill](../release/backup-restore-drill.md). | Synthetic recovery does not prove production backups, retention, physical safeguards or a tested production recovery owner. |

The operational flow is: authenticated request → role/permission/device checks → canonical business records → explicit protected accounting action → posted ledger → read-only review export. Corrections/reversals retain their history. The registration-package builder only reads local source/evidence files; it is outside the posting and government-submission paths.

## Accounting export scope

`GET /api/v1/management/financial-accounting/export` takes inclusive `start_date` and `end_date` in ISO date form, up to 366 days. Existing Management, `accounting.view` and approved-device controls apply. The implementation contract uses a PostgreSQL repeatable-read, read-only snapshot, bounded query execution, exact Decimal amounts, deterministic ordering and explicit oversized-output rejection rather than truncation. Limits are 100,000 rows per dataset and 64 MiB of uncompressed exported content. Authentication can update device last-seen separately; the accounting snapshot does not write financial records.

The ZIP inventory is `manifest.json`, `README.md`, `general-journal.csv`, `general-ledger.csv`, `trial-balance.csv`, `chart-of-accounts.csv`, `accounting-audit.csv`, `cancelled-drafts.json` and `print-view.html`. Books include posted entries and reversals, pre-range opening balances and closing balances; unposted/cancelled drafts are excluded from posted money. Retired-account history remains relevant. The audit scope is `accounting.journal_events` for entries whose posting date is in range, plus cancelled-draft evidence selected by its original posting date. Event timestamps do not define that scope. It is not a complete application/security log. Text is escaped for print output and protected against spreadsheet formula interpretation; accounting money remains exact.

Review the manifest's period/timezone, generating identity/time, version, row counts, file hashes and scope. Missing taxpayer/report identity must remain explicit. The existing capped journal/audit screens are not the complete-books export. The current print view contains the Trial Balance and posted General Journal; review any additionally required ledger/audit printouts separately. These outputs are internal review data; invoice and SAF applicability remain pending.

Current [client document rendering](../../gilbic_backend/src/gilbic_backend/client_document_rendering.py) expressly identifies downloads as copies of server records, not original receipts or tax invoices. Do not use them as an invoice capability demonstration without a separate approved implementation and evidence.

## System-summary preparation field list

Collect actual legal name/address/TIN/branch/RDO; approved CAS/CBA/component classification; taxpayer/VAT category; system and build identity; installed sites and interfaces; modules and financial effects; data/role/process diagrams; database and retained evidence locations; access/backup/retention owners; sample books/documents; supplier or in-house maintenance arrangement; and owner/accountant review references. Reconcile these notes to the current official form once retrieved. No form layout, certification text, signature, QR code or notarization is generated here.
