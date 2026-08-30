# CB1 Management mobile — protected ECL adjustments (A5)

## Status and boundary

This is a bounded CB1 delivery slice. It exposes the existing protected A5 ECL accounting authority to Management mobile; it does not change ECL methodology, calculate balances on the device, enable automatic posting, or complete the broad CB1 checkbox.

Current backend behavior already provides Management-only, permission-scoped, audited and idempotent handlers for:

- allowance remeasurement posting;
- full accounting write-off;
- post-write-off cash recovery evidence review; and
- post-write-off cash recovery posting.

The current A5 queue does not yet provide every exact coordinate required to call those handlers, and it cannot surface an unreviewed eligible post-write-off recovery transaction. This slice completes that read contract without creating a second accounting path.

## Authoritative read contract

The existing A5 list endpoint remains the only mobile read endpoint. Its repository derives, from PostgreSQL records:

- one deterministic eligible unreviewed recovery transaction per written-off loan, ordered by protected acceptance time and transaction ID;
- the action posting date (measurement date, current server accounting date, or protected collection date as applicable);
- the unique open fiscal period containing that date;
- exact active posting accounts 5000 Credit Loss Expense, 1190 ECL Allowance, and 1020 Collector Cash Custody; and
- `recovery_review_required` when eligible protected cash exists but no dedicated immutable recovery review exists yet.

The queue remains fail-closed. Missing evidence, period, account, digest, amount, or identifiers makes an action non-actionable. Flutter must reject incomplete actionable payloads rather than invent a value.

## Mobile behavior

Management opens **ECL Adjustments** from Financial Accounting and can filter the server queue. Each row shows the official loan, ECL labels, measurement, protected allowance, gross carrying components, recovery evidence and status.

An action is enabled only when all of these agree:

1. the server row is in the exact action state;
2. `protected_a5_accounting_enabled` is true and `automatic_source_posting` is false;
3. the endpoint's returned permission is true;
4. the signed-in session contains the same exact permission; and
5. every required server coordinate passes strict local shape validation.

Before any mutation, Management receives a protected-financial confirmation showing the exact amounts, date, ledger treatment, evidence and identifiers. Recovery evidence review additionally requires a retained evidence reference and a substantive note of at least 20 characters.

Each action uses a separate stable 64-character lowercase hexadecimal review token while its result is uncertain. A successful response must contain the expected immutable receipt and `automatic_source_posting=false`; the queue is then reloaded. A transport-uncertain result retains the token and tells Management to inspect authoritative server state before retrying.

## Permissions

- `accounting.ecl.remeasurement.post`
- `accounting.ecl.writeoff.post`
- `accounting.ecl.recovery.review`
- `accounting.ecl.recovery.post`

Management role remains mandatory on the server. Read-only Management users can inspect the queue but cannot mutate it.

## Accounting invariants

- Remeasurement consumes the exact current authoritative A3 measurement and adjusts account 1190 through account 5000.
- Full write-off requires current protected Stage 3/default/write-off support, full ECL coverage, and exact gross carrying components.
- Recovery review binds one exact later, same-loan, non-voided protected cash transaction to retained evidence; it is not a cure and posts no journal.
- Recovery posting debits 1020 and credits 5000; it does not recreate a receivable or allowance.
- The mobile client never edits official amounts, derives journal coordinates, or bypasses the existing protected database functions and audit trail.

## Out of scope

- new ECL models, assumptions or calculation rules;
- automatic source posting;
- manual A5 General Journal entry or reversal;
- production migration, deployment, signing or release;
- declaration that broad CB1, CA2–CA7 or V1 is complete.
