# Treasury integration map — 2 October 2026

PR490 implementation follows the owner's explicit “Include #490 too” instruction.
Released baseline remains `41a13eb5`. Tests use synthetic data in a disposable
loopback PostgreSQL database. Nothing here authorizes real account setup or release.

## Ownership and migrations

The integration owner owns existing financial writers/readers and allocation adapter.
The backend implementer owns new treasury contracts, authorization, ledger, evidence,
reconciliation and API. Web and Android consume that same contract, without money
formulas. The six Draft PRs remain open and unmerged.

Verified open GitHub PR heads485–490 and numbered migrations through0135 on2October.
Reserved additive files:

- `0136_add_treasury_control.sql`: scoped accounts, grants, immutable events,
  openings, claims/versions, receipt capacity, outcomes and reconciliation.
- `0137_add_collection_funding_source.sql`: transaction funding identity and
  guards across existing custody/accounting sources. Never rewrite old migrations.

The owner identity is `configured_employee_owner_id()`; no display-role or first-user
inference. `SPINA_TREASURY_ENABLED` defaults false. Disabling new entry must retain
source classification, protected history and cash-custody exclusions.

## Actual source graph

| Boundary | Existing authority | Treasury obligation |
| --- | --- | --- |
| Authenticated identity | `request_auth.authenticated_device_context`, `core.users`, `core.devices`, roles/permissions | Recheck current user/device/permission/account grant inside each transaction, including replay. |
| Proof files | `client_payment_proof_repository`, `office_review_evidence_storage` | Versioned validated private bytes, exact own/assigned object access. Old proof approval remains evidence-only. |
| Ordinary receipt | `collection_api.collection_service_dependency` → `PostgresCollectionExecutor` → `ConcurrentReceiptSafeCollectionPostingBridge` | Reuse full bridge; recorder is the real authenticated reviewer, funding holder is a separate account. |
| Regular allocation | bridge → `VoluntaryExtraAwareCollectionPostingBridge` → per-loan contract gate → `plan_protected_regular_allocation` | Preserve due/catch-up/explicit-extra choices and complete authoritative checks. |
|7x7 allocation | same bridge → multi-receipt/verified Advance/extra-principal/penalty layers | Preserve actual installment allocations and current verified schedule/penalty state. |
| Combined receipt | `combined_collection_api._allocation_preview` and protected component posting | Derive seven-first/Regular-second amounts server-side; one transaction for all components. No client leg calculator. |
| Cash custody | `remittance_repository._eligible_items`, remittance SQL item guards | Wallet-funded rows never eligible for physical cash handover. |
| Cross-area custody | `cross_collection_status_repository`, `cross_remittance_repository`, SQL assignment/activity triggers | Attribution survives independently; no “hand over cash” notice for owner-wallet money. |
| Cash summaries | `collector_cash_accountability_api`, Management operations/dashboard, collector/delegated/cross-route readers | Keep official applied totals, but exclude wallet funding from cash due/shortage and remittance totals. |
| Correction/void | `collection_correction_repository`, `collection_void_repository` and controlled reversal SQL | Loan reversal does not refund wallet; preserve separate treasury application/reversal links and actual cash event evidence. |
| General ledger | `eir_cash_allocation_repository`, `regular_collection_journal_preview`, `source_event_accounting_repository` and protected journal SQL | Never silently debit Collector cash for wallet funding. Unmapped owner context blocks corporate posting. Automatic source posting stays false. |
| Actual outgoing money | employee payroll/expense, loan-disbursement evidence, refund-due release authorities | Approval is not payment. Require exact source/version/payee/capacity; explicitly block unsupported cash-only adapters. Actual unapproved debit remains visible unclassified evidence. |
| Backup/recovery | existing full PostgreSQL backup/recovery drill | Additive schema and all foreign-key links remain in full backup. Restore test checks receipt/event/application/close history. |

## Transaction order

Treasury commands serialize their account/receipt scope and unchanged request outcome,
then acquire existing device-sequence and sorted loan/date advisory locks before loan
rows. Legacy collection/remittance writers do not acquire treasury account locks.
No callback opens or commits another connection. Source funding is set before the
collection INSERT so assignment/activity/custody triggers see the correct identity.
Reconciliation takes the same account lock and freezes an exact movement watermark.
Failures roll back state, links, audit and command outcome together. Receipt verification
is a separate committed phase; failed loan application leaves received funds unapplied.

## Windows discovery

`spina_app/` does not exist at this baseline. The current installed Desktop design is
`spina_pc/README.md` and `install_spina_pc.ps1`: the HTTPS portal in Edge/Chrome app mode.
Task11 therefore verifies the shared portal treasury workflow in installed Windows Edge,
with the same authenticated backend and report values. It must not recreate the retired
Tkinter application or a second local financial database.

## Acceptance still required

This map is source evidence, not completed runtime acceptance. Dedicated PostgreSQL
tests must prove source classification before notifications, cash/GCash split totals,
concurrency/replay/rollback, protected allocator outcomes, scope isolation, opening cutoff,
transfer transit, exact reconciliation and restored links. Web/native consumers require
their final shared contract and synthetic browser/widget checks. Real owner amounts,
receiving accounts and cutoff are deliberately absent.
