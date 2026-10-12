# Native payout origin for Regular assessment and application accounting

0156 implements the private native-origin helper after the first0155 legacy-greenfield application slice. Its first five real-source tests failed on the missing function before implementation. The helper and thirteen total PostgreSQL cases are now written and awaiting their initial GREEN run. It changes neither0153 nor0155 dispatch, and it creates no release or cash journal. The current0148 release-day proof and0139 Treasury-funding guard remain intact.

## Origin boundary

An original Regular loan can have exactly one supported accounting origin:

1. Its existing protected legacy new-loan release and0051 signed-schedule anchor.
2. An exact0154 native borrower-completion journal, with its exact earlier native payout-debit proof and the same approved signed schedule.

A wallet debit or positive1050 balance does not establish a borrower loan. Native completion posts Dr1100/Cr1050; its amount is initial loan carrying. The earlier debit posts Dr1050/Cr mapped cash, plus any separately evidenced5240 bank fee. Neither the earlier cash movement nor its fee becomes a second loan origination or an interest accrual. The EIR anchor date is the actual borrower-completion business date. A period ending before that date contains transit, not an original Regular loan anchor.

Reject ambiguous origin evidence explicitly. Do not choose the first available proof if legacy and native origins coexist, if multiple native completions refer to one loan, or if another unexplained1100 origination is present.0139 must continue rejecting any attempt to manufacture a legacy `loan_disbursement:<event>` cash journal for a Treasury-funded loan.

## Retained lineage and current proof

Use the read-only `accounting.loan_payout_accounting_posting_status` interface, joined to immutable0154 preparations/postings and the canonical raw source. The native branch requires both `debit` and `completion` to have `exact_posted=true` and `correction_pending=false` for the current book, payout, event, loan, client and wallet. Require positive equal principal, zero completion fee and debit date no later than completion date. Both stages must exist on or before the requested cutoff.

Bind the following identities and values, not just their net balances:

| Evidence | Exact relationship |
| --- | --- |
| Completion posting | One immutable0154 audit and preparation; retained source key `treasury_loan_payout:<payout_id>:completion`; posted journal with exactly the retained1100/1050 line vectors and loan/client dimensions |
| Debit posting | The completion preparation's `debit_journal_entry_id` and `debit_source_digest`; current exact original debit proof; separately retained principal and fee |
| Payout and release | `first_loan_releases.funding_payout_id=payout.id`, release loan/client and received amount match; exact authorization/packet hash and borrower receipt evidence already proven by0154 |
| Disbursement | `first_loan_releases.disbursement_event_id=completion.disbursement_event_id`; original nonvoid `new_loan_release`; `cash_bank_gcash` funding descriptor; zero settlement/deductions; principal and cash-disbursed amount equal completed principal |
| Economic date | Completion posting date equals disbursement `business_date`, original `date_released_snapshot`, current immutable origination date and signed schedule `effective_from`; actual borrower receipt precedes neither the debit timestamp nor its business date |
| Schedule | Use `first_loan_releases.schedule_id` directly; same loan, version1, no superseded parent, original `signed_contract` registration, nonempty immutable installments and supported fixed-daily terms |
| Approved packet | Schedule `settings.first_loan_packet_hash` equals release/payout source packet hash; registration `evidence_reference` equals release `contract_evidence_reference`; schedule `contract_reference` identifies the same retained first-loan packet represented by the release receipt |
| Contract amount/timing | Every installment falls after completion; total contractual cash exceeds initial carrying; last due date equals original maturity; solve the existing signed-schedule daily EIR and reconcile its discounted contractual cash to carrying |
| Control roles |1100 asset/debit,1050 asset/debit, and relevant1120/1190/4000/5000 semantics are exact. Include IDs, codes, system keys, type, normal balance and posting role; display names and retirement do not rewrite economic identity |

The completion proof already validates independent borrower and office evidence against the approved payout and canonical disbursement. The origin normalizer adds the exact schedule relationship because the current0154 origin snapshot does not retain contractual installment rows. The normalizer must retain and revalidate the complete original schedule/registration/installment vector, not infer a schedule from `loan.daily_amount` or generate new installments.

The first native extension remains pure original Regular only. Renewals, deductions, contractual transaction-cost changes, opening/cutover origins, same-day cash-order ambiguity, cancellations/refunds and modifications need their existing or future dedicated adapters. A later schedule version must never silently replace the original schedule. Where an as-of transition is unsupported, return a specific blocker rather than inventing historical terms.

## Historical calculation interface

Proposed private helper: `accounting.regular_original_origin(loan_id, cutoff_date)`. It returns explicit `ready` and `blockers`, one `origin_kind`, and a private normalized anchor. Required normalized economic fields are:

- book, loan, client and original disbursement IDs;
- anchor policy and stable segment source key;
- actual anchor date, contractual maturity and signed schedule/registration IDs;
- initial gross carrying, initial1100 component, initial1120 component zero and original daily EIR;
- exact origin journal IDs and audit/preparation identities;
- dated raw source/signed-contract evidence and the corresponding semantic chart snapshot;
- a source digest covering those identities and facts.

For native origins use a distinct policy, for example `native_regular_payout_anchor_v1`, and source key `native_regular_payout_anchor:<completion_audit_id>`. The posting and operation timestamps remain their real timestamps; `cutoff_date` only scopes economic evidence. The normalizer is read-only and does not manufacture a legacy posting row or make an operational source look Collector-funded.

Do **not** call `loan_payout_coordinates(...,'completion')` when validating historical origin. That posting proposal requires READ COMMITTED and an open period. Do **not** require live `loan_disbursement_journal_coordinates.coordinate_status='coordinate_ready'` either:0046 joins only open fiscal periods and describes a prospective journal. Their live readiness would reject a valid origin after the release period closes.154's immutable retained completion and current exact proof establish the originally admitted journal; historical normalization rechecks its economic raw facts directly, while allowing the original fiscal period to be closed.

Reuse `accounting.solve_verified_contract_schedule_daily_eir(schedule_id, anchor_date, initial_carrying)` from0051. It is a pure original-contract solver and does not require a legacy cash journal. Keep its policy/rounding authority; a null or nonpositive solution blocks. The normalizer supplies provenance, not a different interest engine.

## Compatibility and composition

0153 and0155 should eventually consume the same origin choice. Their measurement, prefix, application, allowance and causal-source guards remain in force. The current153 anchor block at its0051 lookup and legacy cash-credit check needs explicit native dispatch; replacing cash-account eligibility with a broad whitelist would erase the distinction between actual origination and transit.

Preserve existing legacy source snapshots and digests byte-for-byte. Existing153 confirmations and155 application audits cannot become stale merely because a new native branch is installed. Keep legacy proof under its current private alias or return its original anchor JSON unchanged; add native policy/source fields only to newly supported native snapshots. Confirmed exact retries continue returning the original audit. Any intentional change to an unposted preview's policy requires a fresh review.

For153 no-cash assessment, allow the exact native completion as the initial1100 journal and retain the exact earlier debit journal in source lineage. Check native1050 debit/completion components for this payout without demanding that the entire book's1050 balance is zero: other legitimate in-flight payouts remain valid. Unexplained loan-dimensional1050/1100 activity, including offsetting pairs, must not be accepted through net reconciliation alone.

For155 first application, preserve the original raw EIR trajectory anchored at completion and subtract exact153 recognized cumulative prefixes. A period cutoff never resets economic carrying. A real cash event uses the protected original allocator's existing cent-boundary convention. The native application still consumes already-recognized2200 receipt funds and has no second cash debit.

Private payout, wallet and borrower-evidence snapshots stay inside protected origin/audit storage. The153 public Management projection continues exposing only authorized loan/cutoff amounts and retained risk/scenario inputs. The155 review still uses its current device and private receiving-wallet authority. Introducing an origin dependency grants no access to private originating-wallet history or files. Exact current proof is evaluated internally; source-private identifiers must not escape through new blockers or error text.

## Lock and freshness contract

The helper itself takes no workflow row locks and performs no writes, so candidate reads can use their existing repeatable snapshot. Prepare/post paths must acquire existing stable source locks **before** evaluating it, extending the current lock set with154 payout preparations/postings, payouts, first-loan releases/authorizations, approved contract evidence and signed schedules/registrations/installments. Reuse the already-established141/148/149/151 source lock order; do not acquire an origin wallet row lock after holding conflicting global source locks.

Maintain source locks until commit. Deferred validation recomputes the same native origin and exact dependent proof, so a same-transaction backdated or contradictory source change rolls back the accounting operation. After commit actual operational evidence remains appendable; a correction makes current proof stale while immutable prior audits remain. Existing151/154 additional-evidence hooks retain the debit and completion at their own dates; the native assessment's retained contract lineage joins the153 hook automatically. A future completion cannot change an earlier debit-only manifest.

## Behavioral cases before implementation

1. Real approved Regular payout: actual debit, separate actual borrower completion, approved signed schedule and both154 journals. With no legacy posting, a past cutoff after completion produces the independent expected EIR/ECL assessment and then first155 application with unchanged cash movement count.
2. Debit-only or recipient/intermediary-confirmed payout remains in1050 and cannot produce1100 origin or interest. A future completion is absent from a prior cutoff and leaves its reviewed manifest unchanged.
3. A closed original release period still permits a supported later open-period assessment/application; no legacy posting preview or reopening is required.
4. A separately evidenced payout fee changes5240/cash only. Initial loan carrying and EIR remain based on exact completion principal under the existing pure-release policy.
5. Missing, mismatched, corrected or nonexact debit/completion proof blocks. Wrong book/client/loan/packet/schedule, future/superseding schedule or forged loan metadata cannot supply the origin.
6. A legacy and a native origin for the same loan, an extra loan-dimensional control journal or unknown equal-and-opposite controls blocks; another loan's valid positive1050 balance does not.
7. Original EIR agrees with the existing pure signed-schedule solver. Consecutive fiscal prefixes retain the62.58-versus62.57 regression, and the application subtracts already-recognized interest without recognizing receipt cash again.
8. Current chart-role changes and same-transaction backdated source changes invalidate preparation/posting; name changes and retirement preserve retained exact history. Role revocation, private-account denial and unchanged completed retries retain existing behavior.
9. Existing148 release-day,153 legacy-prefix and155 first-legacy-application fixtures remain exact with unchanged source digests.0139 still rejects the legacy Treasury-funded cash journal.

These cases require native operational payout fixtures, not inserted fake legacy journals. The first five baseline failures reached the missing normalizer after the real-source and exact154 proof assertions passed. Later153/155 integration remains a separately tested change.

## Initial156 test boundary

`test_native_payout_regular_origin_postgres.py` contains five collected cases using the unchanged154 actual operational fixture: exact borrower completion and signed schedule, debit-only, recipient-only, completion after the requested cutoff, and a separately evidenced fee. They verify both154 retained posting proofs and the actual1100/1050/1030/5240 balances before invoking the missing normalizer. An independent Decimal bisection of the signed installments checks daily EIR; journal counts and absence of legacy cash postings check that normalization is read-only.

The initial private return contract is `ready`, `blockers`, `origin_kind='native_payout'` and `anchor`. The anchor uses the existing0051 economic names: `loan_id`, `client_id`, `schedule_id`, `disbursement_event_id`, `journal_entry_id`, `anchor_date`, `contractual_due_date`, `initial_gross_carrying_amount`, `daily_eir`, `anchor_policy_version` and `anchor_source_key`. A missing borrower completion reports `native_payout_completion_required`; a completion later than cutoff reports `native_payout_completion_after_cutoff`. Neither state returns an anchor.

These first cases prove the missing origin boundary only. The existing first-loan operation requires the signed basis date to equal the actual server business day and records release at that actual time.153 separately requires an elapsed cutoff strictly after origin and rejects future cutoffs. Therefore the current-day operational fixture cannot honestly prove a positive elapsed native153 assessment or a closed historical release period. Those two cases remain explicitly unverified until a coherent historical native retained fixture is designed. No production clock override, date-validator patch, fabricated legacy proof, or future-period certification is introduced to make them pass.

155 currently preserves `treasury_application_7x7_origin/coordinates` and adds legacy-only `treasury_regular_application_origin/coordinates`, with shared product dispatch. Its retained legacy anchor JSON and other source fields must remain byte-for-byte compatible when156 later supplies the native branch. The common normalizer does not itself change those existing aliases or authorize any new application.

The standalone156 helper currently accepts native origins only. Existing legacy origins continue through their unchanged0051/153/155 authority. Its unknown-control check covers the original completion date and earlier; it does not certify a later loan rollforward. The future153/155 caller must keep its own dated journal whitelist, prefix reconciliation and freshness locks. No private wallet authority is granted by executing the helper internally, and PUBLIC/anon/authenticated/service_role receive no direct execution grant.

The additional boundary cases cover an unposted actual completion, later debit correction, loss of posting role, incompatible wallet ownership, an appended unsigned installment, unknown offsetting original-control journals, stable history after display rename/retirement, and private function grants. Two further cases prove that recoding an unrelated 1110/1120 account cannot hide an extra loan-dimensional journal. A separate1190 case proves that its existing protected ECL guard rejects the proposed manual fixture and leaves origin history unchanged. These introduce no mutation of immutable approved contracts or original audits.

The first fresh156 run exposed a PL/pgSQL reserved-variable syntax error; renaming that local variable allowed the behavioral tests to execute. Then all13 original cases passed, two account-recoding regressions reproduced the bypass, and the proposed1190 fixture was rejected by its existing protected ECL guard before reaching recoding. The1190 test now asserts that existing protection; it is not counted as a reproduced bypass. The repair rejects every extra posted loan-dimensional journal through origination independently of its current account code. This scope matches the first Regular application guard and cannot be bypassed by changing an unrelated account's display or classification. Full current-schema validation is recorded in the execution ledger.
