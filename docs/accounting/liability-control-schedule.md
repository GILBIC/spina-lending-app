# Evidence-backed liability schedule

This increment adds a schedule over already posted General Ledger lines. It never posts cash, creates a journal, supplies an opening amount, or treats a repayment obligation as capital.

## Registration and movements

An authorized active Management actor with `accounting.journal.manage` registers one obligation against one exact posted liability credit line, retaining counterparty, liability kind, due date and evidence reference/SHA-256 digest. The request must explicitly acknowledge review and match book UUID, account, amount, posting date, source type and source reference. Only `manual` and protected `opening_balance` recognition are admitted. Opening registration additionally requires the actual protected opening posting audit. Treasury sources and their control accounts, tax and capital are excluded.

Kinds map to controls: trade_payable=2000, borrowing_external=2300, borrowing_owner=2310, interest=2320, wages=2330, contrib=2340. New chart definitions reject collisions instead of rewriting existing definitions. Posted lines with client/loan coordinates are outside this generic schedule.

Every registration and movement consumes an immutable, globally unique journal-line claim. A manual settlement consumes an exact liability debit; a partial settlement requires its own separately posted line. A correction consumes the exact inverted line in a posted entry whose `reversal_of_entry_id` identifies the claimed original journal, matching account and line number. It also identifies the original claim; that claim can be reversed once. Reversal of recognition is permitted only when it does not leave a negative obligation balance. A same-amount unrelated credit is never a correction.

Writes lock the obligation and exact ledger coordinates. Historical daily running balances must remain nonnegative, so backdated settlement cannot temporarily overdraw the obligation even if a later reversal restores its current balance. All retained evidence and claims reject update/delete/truncate. Exact request retries retain their original identifiers and evidence; changed payload/book/actor conflicts. Audit failure rolls back the entire registration or movement. Every database write rechecks current Management authority.

## Reading and reconciliation

The read endpoint requires Management `accounting.view`, rechecked in the database. A single repeatable-read snapshot returns book identity, as-of obligations and movements, eligible GL control balances, schedule balances, differences and unregistered posted liability lines. A legitimate unpaid obligation is not a blocker solely because it is unpaid. A zero net difference does not hide unregistered offsetting lines. The six control identities cannot be deleted, recoded or reclassified, including before an obligation is registered. Display-name changes and retirement preserve historical reconciliation. This schedule does not certify Treasury, Collector, tax or other subledger completeness; migration0145 composes its differences and unregistered lines into period-close gates.

The posting date controls the as-of balance. The retained due date identifies a contractual due date and does not silently manufacture interest or penalties. Journal review and evidence attestation do not prove a document's legal truth; actual source facts remain retained inputs.

## Interface

Private SQL functions `accounting.register_liability_obligation(request_id, expected_book_id, payload, actor_user_id)` and `accounting.record_liability_movement(request_id, expected_book_id, payload, actor_user_id)` return immutable UUIDs. Payloads bind exact ledger coordinates. `accounting.liability_control_schedule(as_of_date)` and `accounting.liability_control_reconciliation(as_of_date)` provide database read contracts. The registered Python API exposes GET/POST `/api/v1/management/financial-accounting/liabilities` and POST `/liabilities/{obligation_id}/movements`, with mobile aliases.

Validation runs only on the explicitly authorized fresh loopback disposable database. The root worker runs PostgreSQL tests serially; this slice starts no database and touches no production endpoint.
