# Retained cutoff assessment and close manifest

The approved completion plan delegates software design and proceeds without an additional accountant approval gate. Migration 0143 is frozen: its 34 focused PostgreSQL cases passed, including independently negative 1100/1110/1120 and valid unpaid liabilities. Migration 0148 adds retained proof; it does not silently replace the raw source inventory.

## First supported assessment

A Regular loan released on the fiscal cutoff has no elapsed EIR days. Its protected new-loan release and immutable signed original schedule therefore provide an actual, dated no-change EIR boundary. Require the protected release amount exactly in loan-dimensional 1100, zero 1110 and 1120, no unsupported control journal, and no financial collection, renewal, cancellation, writeoff, or changed schedule. Cash entries on the release date have unresolved ordering and remain blocked.

For ECL, require a protected quantitative measurement actually recorded for this cutoff, with the same original EIR, signed schedule, contractual cash flows, supported Stage 1 label, and retained forward evidence covering the cutoff. Reconstruct the installment snapshot and compare it to the retained measurement. Recheck supersession and revocation rather than using today's queue status. Require an exact protected initial allowance posting and retained line audit, with loan-dimensional 1190 equal to the measured amount. A genuinely calculated zero ECL needs zero allowance and no invented journal. An acknowledgement or manually chosen zero cannot satisfy this proof.

This first contract supports the coupled assessment only. Older release dates, collections, 7x7, opening balances, modifications, allowance remeasurement, default/writeoff/recovery, and unposted EIR tails remain explicit blockers. The existing ECL recorder's prohibition on backdating remains intact. Full elapsed-period support still requires replay of the existing event-date allocator and a protected tail accrual adapter; it remains part of the completion plan.

## Retained authority

`loan_period_assessment_candidate(period_id, loan_id)` returns a private source snapshot, blocker codes, and a server-derived SHA-256 digest. `prepare_loan_period_assessment(period_id, loan_id, actor, digest, rationale)` retains book identity, period dates, loan, source inputs, ledger lines, measurement, policies and digest. `post_loan_period_assessment(preparation_id, actor, digest)` recomputes and retains an immutable confirmation audit without creating a journal. Both recheck active Management and the existing close prepare/post permission. An exact retry returns its original audit; a current proof is separately checked by `period_loan_assessment_exact(period_id, loan_id)` and can become stale.

Prepared and posted rows forbid update/delete/truncate, have RLS, and are unavailable to public/client roles. Trusted backend calls supply the authenticated actor. The candidate contains lending/accounting evidence and must remain behind existing accounting and lending authorization; no wallet-private evidence is returned. Treasury-funded release/application states remain unsupported.

Use READ COMMITTED for mutations, lock actor/membership/role/permission, serialize the period, lock the fiscal period, then acquire authoritative source tables in the same prefix order as 0143. Take additional schedule, evidence, allowance and assessment table locks in a fixed suffix order. Recompute after any wait. Locks last to commit; new money after a completed assessment is retained and makes the live proof stale. No trigger rejects operational receipts just to preserve a prior result. Never derive the snapshot digest from period status or volatile queue flags, so a review freeze alone cannot stale economic evidence.

## Composition contract

Composition migration 0149 is delegated to the close-coverage agent; root owns the later retained review manifest in 0151. Only `eir_period_end` and `ecl_period_end` rows for the exact loan/period may be removed when `period_loan_assessment_exact` is true. Other 0143 blockers remain. Filtering the outer 0145 inventory alone is insufficient because the legacy assert reads raw 0143 inventory directly. The raw-filter/assert composition must hold both existing locks and 0148 locks, then re-evaluate at commit. Comprehensive coverage remains false until all declared source families and assessment states have adapters.

## Retained review manifest design

The later manifest should be an immutable preparation plus posted confirmation keyed by book and fiscal period. Retain policy versions, exact sorted source identities/digests, posted GL line identities and dimensions, loan assessment IDs/digests, liability reconciliation proof, tax evidence/posting versions, and family coverage metadata. Hash canonical JSON; require exact current replay at prepare, close post, and deferred commit. Freeze-period status is workflow metadata outside the economic digest. Any backdated source or correction invalidates live currency while preserving historical manifests and real movement evidence. Return a redacted summary under account scope; never expose a Treasury account through the manifest payload. Absence of liabilities is not a prerequisite: reconciled outstanding obligations belong in the manifest.

A manifest is evidence of a specific reviewed snapshot, not an override for unsupported sources. Its status must distinguish historical confirmation from current source completeness. It cannot assert comprehensive completion while adapters are missing.

## API and validation

The Management API is under `/financial-accounting/period-assessments` for both existing web and mobile prefixes. GET `/{period_id}/loans/{loan_id}` returns the scoped candidate. POST the same path plus `/prepare` with `expected_book_id`, exact `source_digest`, and a substantive `review_rationale`. POST `/preparations/{preparation_id}/confirm` with that book/digest and strict `confirm: true`. The API supplies the authenticated actor, rejects extra client fields, and accepts neither a measurement amount nor a historical measurement date. Root registers the router.

The repository checks active Management and the current permission again under database locks. Candidate reads share one repeatable-read snapshot; protected writes use read committed. The public projection contains summarized amounts only for supported ready candidates and never returns the full retained source, loan, journal or forward-evidence JSON. Unsupported candidates omit money and measurement details, including the unsupported Treasury path.

Root verified a true missing-function RED with a legitimate protected release, quantitative measurement and allowance. Final 0148 validation passed 33 checks with zero skips in 53.22 seconds: 14 main PostgreSQL cases, two lock-order races, four real repository PostgreSQL cases, twelve API boundaries and one Decimal precision regression. Evidence: `checkpoints/accounting-completion-20261005/cutoff-full.txt` outside the worktree. The twelve API cases and precision regression also have their own prior RED evidence.

## Elapsed-boundary extension

Extend in a later additive adapter rather than treating an old anchor as current carrying amount. Reconstruct the original signed schedule/anchor and source events through the cutoff, with void/reversal dates evaluated in Asia/Manila and every cash application accounted for. Reuse `allocate_event_date_eir_cash` for the accepted-at/transaction-id order and its cent residual convention. Build the final no-cash tail with the existing daily accrual evidence and period allocation policies. Each recognized accrual must bind an exact source boundary, date span, fiscal period and immutable journal coordinates; compare every 1100/1110/1120 component separately. A later collection must not silently claim the same previously posted tail a second time.

The extension needs a protected rolling boundary audit that stores the consumed date span and recognized cent-boundary state, so subsequent collection preparation starts from that same boundary. Simply posting a generic month-end 1120 debit would double-count interest when the current collection engine later accrues again from the original anchor. Until this handoff is implemented and replayed, elapsed loans remain blocked. Historical ECL additionally needs dated classification, contractual allocation and forecast source reconstruction; changing the existing recorder's `current_date` check would not supply that evidence.
