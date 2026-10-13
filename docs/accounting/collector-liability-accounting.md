# Collector cash and retained liabilities

The additive 0152 adapter consumes existing counted-settlement and Collector-credit facts. It requires the configured book and the reviewed 0142 cash mapping for each affected private account. It does not create operational cash, opening balances or credit approvals.

## Source and journal contract

| Family / immutable source | Required evidence | Journal |
| --- | --- | --- |
| `settlement` / `collector_settlements.id` | Accepted count, verified physical receipt, matching remittance items and exact protected collection GL proof | Debit mapped office cash for actual count; credit 1020 for the already recognized collection amount; credit 2210 for excess |
| `recognition` / recognition `collector_entries.id` | Exact credit, case and matching `collector_resolutions` row; posted settlement | Debit 2210; credit 2220 |
| `return_debit` / `collector_actions.id` | Actual verified debit and exact source link, current return approval and prior recognition | Debit 1060 for principal and 5240 for separately verified fee; credit paying cash for principal plus fee |
| `return_confirmation` / return `collector_entries.id` | Exact received Collector acknowledgment and recorded settlement; posted return debit | Debit 2220; credit 1060 |
| `return_reversal` / reversal `collector_entries.id` | Exact original paid return and incoming verified event/source link; posted return confirmation | Debit paying cash; credit 2220 for actual incoming principal |

The first count adapter admits positive, entirely allocated Collector-cash collections with no refund releases or retained-credit netting. Exact zero-amount PASS constituents are retained in the source snapshot without journal lines; their applied and unallocated amounts must also be zero. It rejects a pre-existing remittance transfer journal and prevents that older writer from duplicating a count already accounted through this adapter. Each monetary collection must already have exact protected posting proof: acceptance transfers existing custody cash instead of recognizing collection income or receivables again.

The operational return model records cash leaving before the Collector acknowledges receipt. Account 1060 therefore represents an actual unconfirmed return, not a reservation. Reservation and cancellation without a debit have no journal. A confirmed return clears this transit amount and reduces the credit without crediting cash again. Later incoming reversals reopen only the amount actually received; a prior fee is not reversed without its own actual cash evidence.

Cash legs use the verified event's Manila business date. Recognition uses the immutable recognition entry's recorded business date. Confirmation uses the retained received acknowledgment date, which must follow the actual debit and precede its recorded entry. Every prerequisite must be posted on or before the dependent business date. A new journal requires that source period to remain open.

## Private Management API

Both `/api/v1/management/financial-accounting/collector` and the corresponding `/api/mobile/v1` prefix expose the same contract:

- `GET /{source_kind}/{source_id}/review` derives the exact source date, amount, fee, chart lines and digest. It verifies every retained file before returning the public projection.
- `POST /{source_kind}/{source_id}/prepare` accepts only `source_digest` and UUID `request_id`. Reuse the same request on retries. No client amount, account code, actor or posting date is accepted.
- `GET /preparations/{preparation_id}` reads the retained public review and current posting status under current private authority.
- `POST /preparations/{preparation_id}/post` requires the exact `source_digest`, `confirmation_token`, and literal `confirm: true`. The source cannot be posted automatically by any operational action.

The five `source_kind` values are the families in the table above. Management accounting permission and current private view authority over both the origin and paying wallet are required. Existing cash-mapping endpoints from 0142 configure the book-specific cash role and evidence; this adapter does not create another mapping authority.

The Portal exposes these reviews under Accounting → Cash & liabilities → Collector accounting; Flutter exposes the same five steps under Financial Accounting → Collector accounting. Each preparation and posting has its own confirmation. Request retries retain the exact request identity, digest and confirmation token. The page discards private source state after an account/step selection change, changed book/session/authority or disposal; it validates each of the five journal shapes before presenting posting controls. The operational Collector capability check tolerates incremental deployment and advertises only installed supported families, without treating availability as source readiness.

## Read-only control schedule

`GET /collector/control-schedule?as_of=YYYY-MM-DD&limit=100&offset=0` returns a dated control schedule, source-linked movements, total movement count and explicit pagination. The default cutoff is the current Manila business date; page sizes are limited to 1–500. It requires current Management `accounting.view`, an active registered device and private history permission for every contributing origin, paying and actual linked event account. Missing access denies the entire schedule with a generic message. Pagination cannot reduce this authorization scope; inactive historical accounts remain included. Actual linked acknowledgment/opening date sources and retained prior account scopes are also included.

The response contains the configured `book`, `as_of`, `business_timezone`, `balance_basis`, three `controls`, paginated `movements`, `movement_count`, `unproven_movement_count`, `correction_count`, `current_capacity`, `controls_reconciled` and `comprehensive_source_coverage:false`. Each control retains exact signed debit-minus-credit `source_balance`, `ledger_balance` and `difference`, plus explicit `normal_balance` and normal-direction `source_amount`/`ledger_amount`. Accounts 2210 and 2220 are credit-normal amounts owed; 1060 is debit-normal return transit. Unregistered line counts remain visible even when their net amount is zero. Source proof status is evaluated against current authoritative retained proof, so unsupported or corrected sources remain visible.

`current_capacity` has a separate UTC `observed_at` and exact `unidentified_amount`, `outstanding_amount`, `reserved_amount`, and `available_amount`. These are current operational capacity, independent of the selected historical cutoff. Reservations are already included in outstanding credit; they are not another liability. One database statement reads the data snapshot, and current actor/grant locks are held through projection. No private wallet identifiers, raw source snapshots or invented opening balances are returned. Separate Collector controls views in the Portal and Flutter accept view-only accounting users and perform no monetary writes.

## Controls

Prepare retains full source, relevant link, exact movement, file metadata, chart and prerequisite posting evidence. Post reauthorizes the current actor for every origin/paying account, verifies file bytes, repeats source derivation under source locks and requires the same actor, digest and confirmation token. A completed exact retry returns its original journal. Public projections contain selected source identity, reviewed date/amount, chart labels, journal lines and audit status; internal evidence stays private.

Accepted excess and recognized credit are liabilities even while unpaid. Reconciliation compares exact posted 2210, 2220 and 1060 movements with immutable source effects as of the cutoff. Reservations do not reduce the outstanding liability. Source inventory clears only individually matched current proofs and keeps unsupported sources and control differences blocked. Close review snapshots must include the new retained preparations/postings through the 0151 extension contract.

Historical openings, source reclassification, frozen credit, rejected-count custody exceptions, future credit application, corrected events and unmatched return debits remain explicit blockers. These require separately reviewed adapters; a note or acknowledgment cannot waive them.

## Validation plan

Use real operational count/recognition/return functions and protected collection posting in a disposable PostgreSQL fixture. Independently assert balances after each transition: original custody 100; counted 110 gives office cash 110, custody 0, unidentified liability 10; recognize 10 gives credit liability 10; reserve 4 changes no journal; debit 4 plus a 1 fee gives transit 4 and cash 105; confirm gives liability 6 and transit 0; incoming reversal 1 gives cash 106 and liability 7. Test exact retry, changed request, revoked access/device/role, cross-account grants, missing file, stale source/chart, unsupported corrections, duplicate legacy cash posting and atomic rollback. Matched unpaid balances clear only their own inventory rows; unrelated source obligations remain.

Verified in the isolated disposable database: 32 PostgreSQL cases, including source corrections remaining recordable, zero-net unregistered lines, exact PASS handling, canonical money and timezone-independent digests, preservation of unrelated draft deletion, and the 0151 extension hook retaining prior evidence. The 21 API/projection/capability tests pass. Portal tests cover all five shapes, explicit confirmations, unchanged retries, private-state clearing, saved preparation scope and unsupported source messages. No production database or real money action was performed.

The subsequent control schedule has 14 PostgreSQL cases and nine API cases. An independent review found the actual linked event-wallet authorization gap; both normal and out-of-range pagination reproduced the missing denial before the fix. Flutter's five posting stages have 12 widget/model cases and a clean scoped analyzer; the separate control schedule has six Portal and five Flutter cases covering its read-only contract, exact normal-balance direction, unknown-role rejection and private-state handling.
