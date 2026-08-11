# Stage 5D.26 — Greenfield Regular renewal EIR roll-forward preview

Status: **read-only accounting measurement preview**. This stage creates no journal draft, posts no General Ledger entry, changes no lending source row, and does not enable automatic source posting.

## Purpose

Stage 5D.24 proves that a renewal actually occurred and preserves the exact old-loan settlement component, but the operational settlement amount is not automatically the PFRS 9 accounting carrying amount.

Stage 5D.25 establishes the protected initial greenfield EIR/carrying anchor for a pure new Regular loan from:

- the uncancelled protected Stage 5D.22 new-loan release posting; and
- the immutable verified original signed-contract cash flows.

Stage 5D.26 connects those two evidence chains **read-only**. It rolls the old Regular loan from its Stage 5D.25 release anchor to the authoritative Stage 5D.24 renewal business date using the already-proven event-date EIR cash-allocation rules.

The resulting amount is deliberately labeled a **measurement preview**, not an authoritative ledger carrying amount. The protected EIR accrual and collection journal path still has to be connected to the greenfield anchor before renewal accounting coordinates can use the amount.

## Target readiness

Migration `0052_add_greenfield_regular_renewal_rollforward_targets.sql` adds the read-only view:

`accounting.greenfield_regular_renewal_rollforward_targets`

A target becomes `greenfield_regular_renewal_rollforward_target_ready` only when:

- Stage 5D.24 reports `renewal_execution_evidence_ready`;
- the old loan has a Stage 5D.25 `greenfield_regular_eir_anchor_ready` anchor;
- the renewal date is strictly after the protected release anchor;
- the renewal date does not exceed the verified contractual maturity date;
- source history before the renewal target is within the protected 5,000-event limit; and
- no PAYMENT/ADV exists on the renewal business date.

The view itself exposes no measured carrying amount. It only proves the immutable target/evidence coordinates needed for the Python roll-forward.

## Same-day renewal cash

Cash on the renewal business date returns:

`same_day_renewal_collection_ordering_review`

The renewal evidence has an exact execution timestamp and collection rows have acceptance timestamps, but SPINA's existing Regular accounting model accrues and allocates at calendar-day boundaries. Stage 5D.26 does not introduce an unreviewed intraday accounting convention. It therefore refuses to guess whether same-day cash belongs before or after the renewal accounting boundary.

## Roll-forward rule

`build_greenfield_regular_renewal_rollforward(...)` uses the existing protected event-date EIR allocator for every supported PAYMENT/ADV strictly between release and renewal:

1. Start from the Stage 5D.25 protected initial components.
2. Accrue daily EIR before each later cash boundary.
3. Apply cash to accrued EIR first and then to the Regular loan component.
4. Reconcile each cash boundary to cents using the already-proven Regular allocator convention.
5. After the last pre-renewal cash event, accrue the final no-cash tail through the authoritative renewal business date.
6. Reconcile the target gross amount to the accrued-EIR and Regular-loan components.

The preview exposes the target gross carrying measurement, accrued-interest component, loan component, event allocations, and total EIR accrued for audit review.

## API

Management can inspect the preview through:

`GET /api/v1/management/accounting/renewals/regular-greenfield-rollforward/preview`

The endpoint is read-only and requires `accounting.view`.

Every response keeps these controls explicit:

- `measurement_preview_only=true`;
- `accounting_carrying_amount_ready=false`;
- `journal_lines_enabled=false`; and
- `automatic_source_posting=false`.

## Why the result is not yet the ledger carrying amount

Stage 5D.26 proves that the protected release anchor and operational cash history can produce a deterministic EIR measurement at the renewal date. It does **not** prove that every required EIR accrual and collection journal through that boundary has been created and posted from the same greenfield anchor.

A later protected stage must connect the Stage 5D.13–5D.18 Regular journal machinery to the greenfield anchor, prove exact journal/source reconciliation through the renewal boundary, and handle any final no-cash EIR accrual required at the renewal date. Only then can the old loan's amount become an authoritative accounting carrying amount for renewal derecognition/modification analysis.

## Explicitly excluded

Stage 5D.26 does not:

- treat operational settlement as accounting carrying amount;
- calculate or post a renewal gain/loss;
- decide modification versus derecognition;
- create renewal accounting coordinates;
- create EIR accrual or collection journal lines;
- enable protected greenfield collection journal posting;
- support same-day renewal cash ordering;
- extrapolate the original EIR schedule beyond maturity;
- support 7x7 renewal accounting;
- create an opening balance; or
- enable automatic source posting.
