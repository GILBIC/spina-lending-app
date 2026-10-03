# Loan payouts: Collector and direct borrower

This change records manual bank/GCash payouts. Collector is the default. Direct payment to the named borrower requires an explicit selection. Neither screen sends provider funds.

Staff open **Cash and GCash Control / Loan payouts**, select an approved source and the specific funding account, review the derived net proceeds and actual recipient, then prepare the payout. In **Money movements**, select that prepared payout and record the exact observed debit with its provider reference and private evidence. Record recipient receipt separately. An unfunded preparation can be cancelled; a debit that failed to link remains an observed movement requiring investigation and cannot be erased by cancelling the plan.

For a first loan, Office separately witnesses the named borrower's actual receipt using its real method and private signed receipt. The existing source transaction retains Management authorization, signed packet/disclosure/CIF/application/private-file/date checks, schedule creation, disbursement evidence and credential intent. An app account is not required for this first-loan acknowledgment. The typed receipt stores received proceeds/method and leaves legacy cash-only fields empty. An active payout blocks a competing Office cash release or approval cancellation. Existing cash receipts keep their original meaning.

For renewal, the accepted approved source must have its actual authoritative bank/GCash execution, exact offset/net amount and all required verified signers. Collector receipt, Collector handover and the borrower's own acknowledgment remain distinct. Direct borrower payment uses the borrower's own acknowledgment. Management reviews the private receipt proof before activation, with the old loan settled. Legacy cash-only custody fields remain empty and cannot activate a bound payout. Every required acknowledgment's recorded actor/device must still be active and authorized.

Recipient screens show only their payout and receipt stage, without beneficiary references, balances or whole-wallet history. Their acknowledgment commands carry no account grant. Web and installed Windows share the portal workflow; Android uses the same typed endpoints and encrypted request journal. A lost response stays locked for exact-request recovery. Selected files and drafts survive read-only refresh; changing the selected payout clears unrelated evidence/review. Entry-disabled history remains readable. Cancelling a stale unfunded plan still requires current account and source-role authority.

## Deployment and recovery

Migration `0139_add_loan_payout_destinations.sql` is required even when Treasury entry is disabled. It adds private RLS/revoked payout storage, immutable reviewed identity, forward stages, one active source/loan, typed first-loan receipts and cash/activation/source-void/journal guards. The runtime manifest requires `loan_payout_schema >= 1`; the retained host guard rejects older cash-only readers. Deploying or rolling back requires the source-aware runtime and full database/private-file recovery. Never roll back only the table or relabel existing funding as Office cash.

The legacy `cash_bank_gcash` disbursement category describes the method; it is not a legal wallet/context GL mapping. Automatic posting of linked loan/renewal journal sources is blocked until that mapping is reviewed. Unresolved debits remain visible for controlled investigation; this feature does not invent a reversal or settlement policy.

The disposable recovery drill seeds real signed/approved first-loan payouts through the services for both destinations, backs up database and private files, restores them, and verifies exact row/schema hashes plus funding/source/schedule/credential/receipt and private-document relationships. Source-void and old cash-path guards also remain active after restore. Synthetic tests do not establish production backup readiness or native device/TalkBack/scanner acceptance.

## Verification

Run `tools/run_treasury_disposable_postgres_validation.py` with its explicit owned loopback opt-in, the onboarding disposable verifier, `tools/run_release_recovery_drill.py`, portal build/tests, Flutter analysis and native tests. New tests exercise strict source contracts, both destinations, actual debit preservation, separate receipts, duplicate/concurrent preparation, current actor/device/evidence, rollback on failed audit/outcome, stale-plan cancellation, own-view privacy and exact-response recovery. CI must pass on the published draft's exact head before release consideration.

No production migration, activation, transfer, merge, deployment, signing or device acceptance is part of this implementation handoff. Android PR496, Office planning PR497 and retained-cash PR498 remain separate.
