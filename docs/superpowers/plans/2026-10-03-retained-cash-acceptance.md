# Include retained disputed cash in full remittance acceptance

Continuation of the approved Collector surplus specification S2/S3 and its custody-exception workflow. Integration owner: this chat. Base: main `0a576036c9a4b3cfca59ce8120abc86f351ee778`; isolated branch `codex/retained-cash-acceptance`. Android draft #496 remains separate and frozen. No production activation, migration, payment or delivery.

## Contract

The designated recipient may explicitly select one current custody exception for this same remittance, physical account, holder, Collector and ledger context. All remaining held cash must be available, with no return reservation or observed pending return. Its original evidence and immutable source must still be valid. Missing selection preserves the existing blocker. Wrong account/holder/source, stale version, revoked authority, changed source, or attempted reuse fails closed.

The server preview binds the selected exception ID/version and remaining amount into the source digest. `physical_cash_required` and `counted_amount` describe **new cash handed over now**. Preview and count also state `retained_cash_amount` explicitly. A short additional count still cannot accept the remittance or silently create another retained exception. Existing counts without a selection retain their original meaning.

Acceptance atomically records only the new inflow, links the original retained event to its portion of the remittance, consumes the exception's held capacity, receives the whole remittance, and saves the durable result/audit. The settlement keeps `physical_amount` as the newly counted physical receipt and adds `retained_cash_amount`; their sum explains the physical custody accepted. Any new excess belongs to the new event and remains pending identification. No credit application, GL posting, new collection, second retained inflow or borrower payout is inferred.

Example: obligation 10,000; already retained 9,900; newly counted 100. Acceptance receives the remittance and leaves total recorded inflow 10,000, not 19,900. A 99 count stays short. A 200 count records total inflow 10,100 with 100 pending identification.

## Execution and evidence

- [x] Real PostgreSQL RED cases for explicit selection, exact/excess/short counts, stale/reserved/foreign records, once-only acceptance, concurrency and rollback.
- [x] Implement same-transaction preview/count/acceptance with current authority, evidence and source locks; preserve legacy blockers and return workflow.
- [x] Add the explicit choice and truthful new-versus-held amounts to Web/Windows and Android, with strict preview/result binding and recovery tests.
- [ ] Run focused client checks, fresh disposable financial validation and required integration checks. Preserve source-aware read/backup/rollback compatibility.
- [ ] Fresh independent whole-change review; retain findings/repairs and draft PR/evidence. Do not claim native OS/device acceptance.

## Decisions

- Reuse current JSON records and private evidence; do not alter applied migrations or invent a new financial subsystem.
- Do not combine multiple accounts, holders, remittances or Collector credits in this command.
- Do not allow a selected old dispute to authorize retaining a second short handover. That remains a separate unsupported operation.
- Loan/renewal payout path is pending owner clarification; expense preparation is still only a draft, so neither is marked paid by this change.
