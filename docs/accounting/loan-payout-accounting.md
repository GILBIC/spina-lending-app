# Loan payout accounting

The 0154 adapter connects an actual protected Treasury loan payout to the ledger in two stages. Operational preparation and recipient acknowledgment do not independently create cash or a loan receivable. Accounting review and posting remain explicit Management actions.

| Stage | Source facts | Journal |
| --- | --- | --- |
| Actual debit | Verified original payout funding event, exact principal/fee movement lines, private evidence, source link, configured book and wallet mapping | Debit1050 loan disbursement transit for principal; debit5240 for actual separate fee; credit mapped cash for principal plus fee |
| Borrower completion | Completed immutable payout, exact first-loan release/borrower receipt and authoritative disbursement event, original protected loan coordinates, prior exact debit posting | Debit the exact loan carrying accounts from the approved lending coordinates; credit1050 instead of cash for the amount already disbursed |

A transfer to a Collector is not proof that the borrower has received the loan. Receipt by an intermediary leaves1050 outstanding until protected borrower completion. A valid unmatched debit remains a separately reconciled transit asset. It must not become loan income, a second cash payment, or a fictitious borrower receipt.

The first completion case is the existing supported pure new Regular loan: principal equals net proceeds, with no deductions or settlement components. Preserve the original lending measurement authority. Renewal,7x7, modified and deducted releases must use their own measured coordinates before their source blockers can clear; this document does not claim that those adapters already exist.

## Required controls

Both stages retain exact source IDs, dates, event movement/evidence, mapping and account definitions. Debit proof excludes future mutable payout-stage/version fields so later legitimate completion does not erase the historical debit. Original event corrections remain visible. A completion requires the exact prior debit audit and cannot predate it. Each stage posts at its own actual business date into an open period.

The 0154 writer uses the native `treasury_loan_payout` source family and leaves the 0139 legacy guard unchanged. Its own immutable prepared coordinates admit that new source. Legacy release journals remain blocked for Treasury payouts to prevent duplicate cash credit. A user-supplied session flag, source key or manually balanced journal is insufficient authority. Source inventory removes only the specifically matched Treasury debit and authoritative loan-release obligation. All other source/assessment/tax blockers remain.

Current actor, Management accounting permission, live device, private wallet permission, actual evidence bytes, book identity, expected digest and confirmation token are rechecked. Exact retry returns the original stage journal; changed coordinates conflict. Public responses project only the selected stage and reviewed journal lines. New private tables/functions revoke client access. Audit and journal commit atomically; manual reversal cannot sever the retained payout proof.

## Behavioral verification

Use an actual approved first-loan packet, operational payout preparation, private evidence, actual debit and independent borrower completion in a disposable database. Verify no accounting from preparation, debit1000 plus fee2 gives cash−1002/transit1000/expense2, Collector receipt alone leaves transit1000, borrower completion moves transit1000 to loan receivable1000 without another cash effect, and retry leaves all balances unchanged. Verify missing evidence, revoked authority, stale source/mapping/chart, unsupported deductions, cross-period dates, duplicate legacy journals, audit rollback and a reconciled outstanding transit balance.

## Integration contract

`loan_payout_coordinates(payout_id, stage)` derives the review, `prepare_loan_payout_accounting(payout_id, stage, source_digest, request_id, actor_id)` retains it, and `post_loan_payout_accounting(preparation_id, source_digest, confirmation_token, actor_id)` atomically posts the existing journal engine and immutable audit. Stages are `debit` and `completion`. An exact retry returns the retained journal even if a later source correction now needs review; it never rewrites the money.

`loan_payout_accounting_posting_status` exposes payout, stage, event, authoritative disbursement, wallet, book, loan, client, preparation and journal IDs; actual posting date, principal, fee, digest, exact posted proof and correction status. `loan_payout_transit_reconciliation(cutoff)` reconciles each payout's dated native debit/completion principal with its 1050 lines. Positive transit is valid. Unsupported unregistered 1050 journals remain blockers even when offsetting lines net to zero.

The web and mobile `/management/financial-accounting/treasury` routes provide `GET /payouts/{id}/review?stage=…`, `POST /payouts/{id}/prepare`, `GET /payout-preparations/{id}`, and explicit-confirmation `POST /payout-preparations/{id}/post`. Request bodies carry identities, retained digest/token and confirmation, never money or an actor supplied by the client. Public JSON excludes signed packet, source snapshots, evidence metadata and file locations. Completion verifies original debit bytes, borrower Treasury receipt bytes and the office receipt bytes keyed by its immutable request ID.

Completion remains blocked for renewal, 7x7, deductions, offsets, modified loans, source corrections and borrower acknowledgment on a different business date from the authoritative release. A dedicated protected correction/reversal adapter is required before any payout journal can be reversed. No existing operational action posts a journal automatically. This adapter does not complete the period-assessment, tax or comprehensive-source-coverage work.
