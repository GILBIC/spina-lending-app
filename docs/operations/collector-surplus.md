# Collector excess and surplus

This is the operating guide for the Collector surplus contract. It does not
authorize production setup or claim installed-device acceptance. Current
implementation and verification receipts are tracked separately in the PR and
completion handoff. Entry starts disabled, with no real balances, counts or
permissions supplied by the migration.

## Count, then accept

The receiver opens the exact remittance and reviews its protected collections,
refund releases, source dates, recipient and required physical cash. Wallet-funded
borrower payments are separate from cash physically held by the Collector. The
selected receiving location must be the actual permitted physical-cash account.

Record the actual count, time and supporting evidence. Recording a count does
not accept the remittance. If the protected source changes, review it again;
never substitute an earlier screenshot or a matching total for current evidence.

| Required cash | Counted cash | Meaning |
| --- | --- | --- |
| PHP10,000 | PHP10,000 | Count ready for a separate deliberate acceptance. |
| PHP10,000 | PHP10,100 | Acceptance records PHP10,100 cash once and PHP100 pending identification. It creates no Collector credit automatically. |
| PHP10,000 | PHP9,900 | Save a rejected short count with PHP100 shortage. Do not clear the full remittance or apply unrelated credit. |

A zero count is a valid observation, not an absent value or positive receipt.
Original source date, actual count time, server record time and acceptance time
remain separate. Older accepted remittances do not gain invented count evidence.

If disputed short cash is physically retained, record its actual holder and
amount through the custody exception. The obligation remains unresolved. A
normal rejection is not proof that retained cash was returned. The exception
can be resolved by an actual evidenced return or explicit inclusion in full
acceptance of its original remittance. Inclusion requires the same recipient,
physical account, Collector and unchanged source, with no reserved return.

For inclusion, open the current disputed-cash record. On Web/Windows, return to
Count a remittance and select that record in Previously retained cash. On Android,
choose Review inclusion of retained cash. Review the held amount separately from
the new physical cash required. Count only the additional cash handed over now.
For a PHP10,000 obligation with PHP9,900 already held, count PHP100 new cash.
Acceptance links both original receipts and records only PHP100 additional inflow.
PHP99 is still short; PHP200 creates PHP100 pending identification. A short
additional handover cannot create another retained exception through this action.
Changed, reserved, corrected or unavailable source evidence blocks acceptance.

## Identify excess before granting credit

Pending identification means the office holds extra cash whose purpose or owner
has not been established. It can be an unrecorded borrower payment or another
source error. Collector attribution alone is not proof that the Collector owns
it. An independently authorized reviewer must examine current source evidence
before recognizing a genuine amount owed back to that Collector.

Recognition may be partial. Recognizing PHP40 from a PHP100 case leaves PHP60
unidentified and creates no additional cash. A missing or unsupported protected
source correction must remain visibly unresolved; do not replace its actual date
with today or create a fake borrower payment.

The Collector sees only their own permitted amounts and history. The own-credit
page does not grant office wallet balances, private provider statements, other
staff records or approval rights. Outstanding, reserved and available amounts
come from the server; a reservation is part of the outstanding liability, not a
second amount owed.

## Return money through separate verified phases

1. The Collector records an own-credit request with the intended amount and
   destination. This is a request, not an approved or completed payout.
2. Independently authorized staff reviews the exact request and destination,
   verifies evidence and reserves the amount from available credit.
3. Staff records the independently verified actual cash or wallet debit through
   the existing Treasury outgoing workflow. This feature does not send provider
   transfers. The approved source, Collector, principal, paying account, evidence
   and observed event must match.
4. The Collector acknowledges the exact observed principal and event as received
   or not received. This records the recipient's statement only. If receipt is
   delayed, the Collector can append a new statement; the earlier one remains.
5. Authorized staff separately confirms settlement from the exact current event
   and latest acknowledgment. An older received statement cannot override a later
   not-received statement. Only the paid disposition reduces outstanding credit.

For a PHP100 credit, reserving PHP40 leaves PHP100 outstanding, PHP40 reserved
and PHP60 available. A confirmed PHP40 return leaves PHP60 outstanding. A later
wallet return of PHP60 with a PHP2 evidenced provider fee debits the wallet by
PHP62 and settles PHP60 of credit. The fee is not taken from the Collector's
credit. Approval alone has no movement.

A debit without recipient confirmation stays pending and reserved. Not-received
acknowledgment, transport uncertainty or a timeout is not permission to pay again,
cancel a known debit or release capacity. Cancellation requires proven no-debit
conditions and evidence. Never delete a real debit to represent a reversal.

Frozen credit cannot be selected for a new return or advance an existing reserved
return. If money was independently verified as already debited, its event remains
visible with the source link blocked and the reservation held for review.

Retained-cash exception returns use the same verified debit/acknowledgment
separation but discharge the physical custody exception, not Collector credit.

## Recovery and access changes

If the response is lost, recover the original submitted request. A missing result
does not prove the transaction failed. Any explicit retry must preserve the same
request, exact inputs and reviewed evidence; do not create a fresh payout to get
past an uncertain state. Other financial tasks remain blocked while a sibling
submission is unresolved.

Current user, device, role, object and account authority are checked on writes,
reads, private files and replay. Losing permission does not turn a saved outcome
into public data. Private screens and evidence are excluded from screen sharing.
Browser drafts remain in the mounted page; native recovery uses the existing
encrypted submitted-attempt journal, with no background financial resend.

Turning off new entry must preserve existing histories and recovery. It cannot
restore an acknowledgment-only receiving bypass or reinterpret a partially
returned credit as unrecorded cash. Retained runtime compatibility checks and
backup/restore verification are rollout prerequisites.

For remittances with no counted state, ordinary feature-off receiving remains
available only when the server explicitly permits it for that remittance and
recipient. A missing response, old server or access denial never selects this
path. The server checks the rule again when receiving is committed.

If an account has both Collector and independent staff permissions, its selected
own view stays own through details and exports. Staff access remains a separate
authorized view; choosing the own page does not grant approval rights.

## Blocked and unconfigured paths

Future credit application records explicit intent only where its capability is
available. Execution is blocked until the protected custody and accounting
adapter can represent gross PHP1,000, approved credit PHP100 and actual new cash
PHP900 truthfully. Do not report PHP1,000 physical receipt or silently offset a
short count, borrower payment, another Collector, payroll or future day.

Historical borrower corrections and unresolved source portions require the
existing protected allocator and true dates. Unsupported paths return an adapter
blocker. A source conflict after money was already returned requires a recovery
decision, not negative credit or an automatic wage deduction. Unmapped GL posting
also stays blocked; no tax, income or accounting policy is invented here.

Owner opening anchors require an actual existing opening, cutoff, amount,
evidence and overlap review. A credit anchor recognizes an already-included
liability; an unidentified-excess anchor creates a pending identification case
without assuming Collector entitlement. Neither adds cash. All anchors share
the opening's capacity, and activation checks overlap again using the actual
cash count date. Missing opening values are unavailable, not assumed zero.

A matched cash reconciliation does not resolve unidentified sources or settle
Collector liabilities. Later source classification requires review of affected
closed periods while preserving their original captured evidence and cash.

See the [strict API contract](collector-surplus-api-contract.md),
[source map](collector-surplus-contract-map.md) and accepted design for exact
authority, phase and adapter requirements. PostgreSQL, browser, native and
installed Windows evidence must identify what was actually exercised. Widget
fixtures do not prove a physical phone, TalkBack, camera or provider behavior.
