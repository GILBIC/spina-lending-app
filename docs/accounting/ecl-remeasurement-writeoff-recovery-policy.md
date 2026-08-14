# Controlled ECL remeasurement, write-off and recovery — SPINA V1 A5

## Purpose

A5 extends the protected A4 allowance boundary without weakening it. Every action remains an explicit Management-confirmed accounting action. Prior A3 measurements, A4 postings and A5 postings are immutable; a changed estimate is represented by a new approved A3 measurement and a new journal/audit record.

`automatic_source_posting=false` remains mandatory.

## Remeasurement

A5 adjusts the protected per-loan account `1190 Allowance for Expected Credit Loss` balance to the exact amount of a new current authoritative A3 measurement.

The current protected allowance is the posted per-loan net credit balance of account 1190. The target is the new measurement's exact authoritative ECL amount.

- Increase: debit `5000 Credit Loss Expense`, credit `1190 Allowance for Expected Credit Loss` for the exact positive delta.
- Decrease: debit `1190`, credit `5000` for the exact decrease.
- Full allowance reversal: when the new authoritative ECL is zero, debit `1190`, credit `5000` for the full prior protected allowance.

The function revalidates the current A3 measurement identity/digest, open period, protected 5000/1190 identities, prior allowance balance, delta and resulting allowance inside the posting transaction. A measurement already consumed by an A4/A5 allowance posting cannot create another adjustment. Exact retry is idempotent only when every immutable confirmation coordinate is unchanged; a different retry is rejected.

This treatment follows the IFRS 9 impairment requirement that the impairment gain or loss is the amount needed to adjust the loss allowance to the required reporting-date amount. A5 does not create a PD/LGD shortcut or any quantitative assumption.

## Write-off

A write-off is a separate derecognition action, not a credit-risk label side effect. A5 V1 supports a **full accounting write-off only** because the existing protected write-off-support review records the conclusion that there is no reasonable expectation of recovery but does not carry an authoritative partial-write-off amount. SPINA must not invent a partial amount.

A full write-off is allowed only when all of these are simultaneously true:

- the current protected review is current/non-stale, Stage 3, reviewed default and `supported_no_reasonable_expectation_of_recovery`, with its retained evidence reference and rationale;
- a current authoritative A3 measurement exists and its ECL equals the exact protected current gross carrying amount;
- the protected per-loan 1190 allowance equals that same gross carrying amount;
- the exact posted General Ledger gross carrying components are positive and reconcile to the selected loan receivable account plus accrued interest receivable;
- the exact posting period and protected accounts remain valid.

The write-off journal debits `1190` and directly credits the exact gross carrying components: `1100 Loans Receivable - Regular` or `1110 Loans Receivable - 7x7`, plus `1120 Accrued Interest Receivable` when non-zero. After posting, both the protected gross carrying balance and protected 1190 allowance for the loan must be exactly zero.

This directly reduces gross carrying amount only after protected evidence establishes no reasonable expectation of recovery. The write-off-support label by itself never derecognizes the loan.

## Derecognized-loan fail-closed boundary

Once the protected write-off is complete, the loan is not allowed to re-enter the ordinary ECL/allowance or collection-accounting lifecycle merely because later activity exists. Database guards reject any new A3 measurement, A4 preparation/posting, A5 allowance remeasurement, or normal Regular/7x7 source-event accounting for that written-off loan. This prevents a later collection from recreating the derecognized receivable or account 1190.

A derecognized loan also correctly ceases to have the ordinary positive gross-carrying/contractual-DPD readiness used by the standard credit-risk queue. Post-write-off cash therefore has a dedicated protected recovery-evidence review rather than forcing the loan back through a DPD-ready state.

## Post-write-off cash recovery

A later recovery remains evidence-driven. Management must first create a dedicated immutable post-write-off recovery review that requires:

- an immutable completed A5 write-off for the same loan;
- the retained protected Stage 3/default/write-off-support chronology from that write-off;
- the exact same-loan non-voided positive PAYMENT/ADV transaction;
- the transaction's authoritative server `accepted_at` strictly later than the accounting write-off;
- zero protected gross carrying amount and zero protected allowance;
- no existing normal Regular/7x7 source-event posting for that transaction;
- an exact recovery amount, retained evidence reference, substantive Management rationale and immutable review token.

The dedicated review records `cash_recovery_observed` plus separate provenance tied to the exact write-off and transaction. It does **not** represent cure, does not re-establish contractual-DPD readiness, and does not itself create an accounting entry. Exact retry is idempotent only when all immutable evidence coordinates match; a changed retry is rejected.

The recovery posting then consumes only that exact dedicated provenance and revalidates the write-off, transaction, amount, collection/posting date, open period, zero gross/allowance state and protected account identities. The journal debits `1020 Cash - Collector Custody` for the exact protected collection amount and credits `5000 Credit Loss Expense` for the same amount. This records the recovery in profit or loss without recreating a loan receivable or a new allowance. A subsequent cash-custody/remittance transfer remains governed by the existing protected remittance lifecycle.

A recovery does not automatically mark the borrower cured. `cash_recovery_observed` and `cured` remain separate protected credit-risk evidence conclusions.

## Generic/manual bypass and reversal integrity

A5 reserves its source types and immutable audit tables. A5 journals cannot be edited, deleted, manually posted or manually reversed through the General Journal. Any future reversal of an A5 write-off/recovery would require a separately supported protected accounting event; A5 V1 therefore rejects generic reversal bypass.

Forced audit failure after journal posting is tested inside the same PostgreSQL transaction. The expected result is atomic rollback of the journal status, audit row and financial balances.

## Safety boundary

A5 does not mutate prior ECL measurements, prior allowance postings, credit-risk reviews or lending collection evidence. It does not fabricate write-off amounts, recovery amounts or ECL inputs, and it does not enable automatic source posting. Schema/control installation itself is also required to leave all protected measurement, posting, write-off, recovery, provenance and journal history unchanged.