# Native Regular lifecycle integration

This extends the approved October 5 accounting design. It does not create an
opening balance or change retained source dates. Ordinary current receipts,
applications, elapsed assessments and renewal completions belong to S04.
Historical source corrections, mixed retained custody and destructive reversals
remain the explicitly deferred S05 work.

## Original release and current cash

0163 admits the exact 0159 native original anchor into the existing 0156 fiscal
assessment and 0158 first-cash calculations. Both original journals are required:
actual cash debit credits the mapped wallet and debits 1050; independent borrower
completion debits 1100 and clears 1050. A separately evidenced wallet fee stays
in 5240 and never increases the original loan carrying amount. The unchanged
0139 source guard prevents a fabricated legacy cash-release posting.

Old paper-scan evidence predates the current 0140 capture-method column. Only
that absent member may match its documented new `paper_scan` default; all other
source members and every explicitly retained capture method compare exactly.
Retained snapshots, digests and journal dates remain immutable.

New first-loan releases initialize reconciled collection state from their exact
signed contractual schedule. An older native release whose balance already
equals that verified schedule can be reconciled only by explicit Management
activation, with no previous collection or allocation, state version zero,
current exact native source proof and unchanged financial amounts. Its immutable
activation audit retains before-state, unchanged amount, origin digest and actor.
Read-only readiness must expose this supported action without changing state.

0165 introduces a private chronological measurement shared by subsequent
applications and the post-cash period assessment. Start with the original exact
carrying and original daily EIR. Order real cash by collection date, acceptance
time and transaction ID. Accrue once for elapsed calendar days before each cash
event, allocate cash first to accrued interest and then loan carrying, and apply
the existing `allocate_event_date_eir_cash` cent residual convention at each
actual cash event. Fiscal assessment cutoffs are recognition claims and do not
reset the economic compounding basis.

Each prior source requires its exact protected posting and retained audit;
unknown and offsetting loan-dimensional journals remain blockers. A new
application debits 2200, recognizes only unrecognized EIR in 1120/4000, and
credits the measured 1120/1100 components. It has no cash line. The source
snapshot uses deterministic economic ordering so a legitimate later same-day
application does not change an earlier retained proof. Unsupported earlier
sources and reversals cannot be hidden by that ordering.

The period assessment retains all original installments and the actual
allocations as of cutoff. Remaining contractual cash flows retain their original
due dates; operational No Collection dates never become accounting dates. The
remaining contractual cash-flow PV and actual cash-rollforward carrying are
distinct retained quantities after off-schedule payments. The ECL cash-shortfall
engine uses the contractual cash flows and explicit cutoff-eligible scenarios;
the GL assessment recognizes only the outstanding EIR interval and allowance
delta. Neither a zero scenario loss nor a changed cash-flow estimate is inferred
from the operational paid flag.

0167 admits actual release-day cash with zero elapsed interest. A protected
same-day allowance journal is recognized structurally from its immutable
preparation and posting audit while reconstructing the release. The full
assessment check still recomputes current source, chart and measurement proof;
this avoids circular reconstruction without admitting an unaudited journal.

Full repayment is established from the actual Treasury-funded transaction and
complete allocations to the exact signed schedule. Management must separately
retain the contract reference and an explicit full-contractual-payoff-without-
rebate treatment with a substantive rationale. The application review presents
the cash, carrying amount and settlement difference before preparation and
posting. It clears both carrying components, recognizes the difference in
4030/5020, and never credits a negative remaining loan or books cash twice.
An exact payoff still needs its fiscal assessment: the settled assessment
requires the payoff review ID and a separate rationale, uses zero exposure and
no forecast scenarios, and releases any prior allowance through the existing
protected assessment writer.

After signed maturity, partial cash requires an explicit closed-term review
binding the exact contract to the policy of original EIR through maturity with
no extension. The recurrence caps accrual at that retained maturity; it does
not invent a new rate, due date, rebate or fee. The same review is available in
the application workflow on Web and Android. The cutoff assessment continues
to require its applicable risk and forecast evidence; a closed-term review is
not a substitute for an extended delinquency/ECL treatment.

## Renewal bridge contract

0054/0055 already provide protected renewal-boundary EIR posting, and 0056
retains the explicit modification/derecognition decision. The boundary posting
only debits 1120 and credits 4000 to establish the old loan's carrying amount.
It neither clears a new payout's 1050 nor settles/replaces an accounting asset.
The legacy treatment target remains a measurement preview. Migration 0166 adds
the native renewal completion writer and immutable accounting-asset lineage.

The protected native renewal interface retains the payout, execution,
old and new loan IDs, exact old-asset rollforward/boundary journal claims, exact
actual payout debit, reviewed treatment decision, signed new schedule, explicit
settlement/rebate evidence, book/context and current semantic chart mapping.
Readiness and preparation derive source digests internally. Posting uses one
same-actor confirmation token, a unique completion claim for the payout, and
deferred source/line/audit exactness. No draft alone clears raw source blockers.
Management reviews the source at the payout's `renewal-measurement` endpoint,
then retains an explicit treatment and measurement before using the existing
completion review, prepare and post path. Review, preparation, retained recovery
and posting require current private wallet access and the dedicated
`accounting.renewal_treatment_decision.manage` permission.

The existing source schema has no separately registered renewal PDF. The
review therefore requires an uploaded private bundle containing the signed
renewal contract and settlement/measurement support, plus an explicit unchecked
`signed_contract_reviewed` attestation. The immutable review binds the bundle's
identity, hash and size to the exact new loan, signed schedule, contract reference,
original source lineage and payout receipt. New review, preparation and posting
verify those actual bytes recursively, including the original signed packet.
An exact already-retained request can be recovered without re-reading unavailable
bytes; it still verifies the current actor and exact immutable arguments. Missing
bytes cannot authorize a new write.

For a reviewed modification without derecognition, the old accounting asset
continues even if operations have created a new loan record. The new future
contractual receipts are discounted at the old original EIR to obtain revised
carrying. Separately advanced cash first increases the continuing asset and
clears its exact 1050 amount. The residual modification adjustment is revised
carrying less old carrying less fresh cash. The current preview's bare
`PV - old carrying` is not a safe P&L coordinate for a funded renewal: treating
fresh cash as gain would double count the funding. Use explicit collision-checked
modification gain/loss roles and retain the decomposition in the review.

For derecognition, add immutable Management-reviewed new-asset initial
measurement evidence with effective date, measurement basis, amount, retained
source reference/hash and rationale. Principal, net cash, nominal contractual
settlement and old-EIR comparison PV must not substitute for that measurement.
An explicit signed settlement/rebate consideration governs the old asset's
derecognition difference; the new asset gets its own independently solved EIR
from its accepted initial measurement and new signed receipts. Fresh cash clears
1050 once. Any day-one difference requires an explicitly retained treatment and
chart mapping; it cannot disappear into principal or interest income. Both
branches use explicit 4020 gain and 5010 loss components. Opposite differences
are retained separately rather than netted away. The original loan's elapsed
interest, if any, is a separate 1120/4000 pair in the protected completion.

Both branches need an immutable accounting-asset lineage linking the old
accounting identity to the operational renewal loan. Later receipts and fiscal
assessments use that lineage. Existing first-cash proof must retain its original
as-of terms when a legitimate later renewal is appended. Unexplained changes to
earlier contracts and arbitrary post-maturity accrual remain blockers. Current
real company policy or valuation inputs may be absent; the software must offer
their reviewed evidence workflow rather than inventing values.

The old operational loan still receives a formal cutoff assessment after its
exact renewal completion. The candidate identifies `settled_by_exact_renewal`
and the immutable renewal review ID. The public `prepare-renewed` action requires
that review, the current book/source digest and a separate explicit rationale;
ordinary assessment confirmation follows. This zero-exposure assessment adds
no forecast scenarios or new journal when its carrying and allowance are already
zero. The continuing or replacement loan gets its own applicable assessment.

Renewal origin snapshots use UTC regardless of the caller's session timezone.
The derecognition EIR solver accepts the separately verified
`signed_renewal_contract` registration and preserves the original-only solver
unchanged. Protected lifecycle tests compare the accepted signed receipts'
present value independently, check transfer or release of an existing allowance,
and reconcile both loan dimensions before closing the current period.

A modification of a credit-impaired asset keeps its accounting identity and
impairment history. A new operational loan ID is not evidence of cure. The
renewal boundary retains the actual risk review and any exact prior fiscal
assessment. Gross interest, allowance unwind and intervening reviewed impairment
changes remain separate amounts: the old allowance transferred by the completion
is the posted allowance plus unwind plus those impairment changes. The journal
uses a separate 4000/1190 unwind pair and a signed 5000/1190 impairment pair;
the settlement of the old operational dimension cannot recognize either twice.
The successor requires a current Stage 3 review or supported objective cure.

The public candidate and completion expose `credit_impaired_boundary` with
`allowance_before`, `allowance_unwind`, `impairment_adjustment` and
`allowance_after`. The source and lineage retain the exact predecessor review ID,
version and immutable row under the source locks. A new risk review invalidates
an unposted preparation; a future review does not replace the review pinned by a
completed renewal. Relevant cash reviews are pinned the same way. Renewal-day
cash requires its own exact reviewed allowance target because a later fiscal
forecast cannot supply an earlier renewal boundary retrospectively.

An explicit successor cure can refer to the verified predecessor impairment
review. The protected review command preserves the actual predecessor identity
in `supersedes_review_id` and starts the successor's own review version at one.
Current risk context exposes this separately as `inherited_review`; it does not
present the predecessor review as a review made for the successor loan.

Derecognition of an impaired predecessor has an explicit policy boundary. Its
successor may be originated credit-impaired; an ordinary contractual EIR and a
fair-value amount do not establish the required initial credit status or
credit-adjusted EIR. The current adapter blocks that treatment with
`successor_credit_adjusted_eir_policy_required` until a supported initial
measurement policy exists. It does not infer a cure or implement a POCI engine.
The candidate displays this restriction before a treatment can be retained.

A current Stage 3 label before renewal proves inheritance, with zero elapsed
unwind on that initial day. It does not prove a prior-period net-interest
interval. Such proof requires a genuinely retained, dated Stage 3 assessment and
any required dated cash measurements. A fiscal end-of-day assessment cannot be
repurposed as an earlier same-day prefix after subsequent renewal changes its
source.

The inherited opening records whether an actual impaired fiscal boundary has
already established net-interest accounting. A label alone preserves the cure
requirement but keeps gross interest through the initial impaired reporting
cutoff. Only subsequent reporting periods use the reviewed net carrying amount,
consistent with [IFRS 9 5.4.1(b) and 5.4.2](https://standards.xrb.govt.nz/standards-navigator/nz-ifrs-9/).
The independent nonzero renewal component tests prove arithmetic and balanced
decomposition; they do not claim positive elapsed Stage 3 posting evidence from
the October 5 capture, which has no retained Stage 3 opening.

An established net-interest opening survives modification through the exact
renewal review. Cash after that opening, including later cash on the renewal
day, requires the same dated allowance review as an ordinary impaired interval.
The candidate verifies the protected cash posting and immutable renewal lineage;
the pure arithmetic flag for opening-day cash grants no source authority. A
label-only inheritance cannot create this opening. Public interest and cash
review payloads identify it with `opening_renewal_review_id` and a null
`opening_assessment_id`. Ordinary fiscal openings omit the renewal field. Only a
renewal opening can share its date with subsequent cash; an ordinary fiscal
opening must precede cash. Positive inherited-opening cash source proof still
requires genuinely aged Stage 3 evidence; the current-day rejection and pure
interval tests do not substitute for it.

## Behavioral proof boundaries

The retained October 5 synthetic native capture is restored with original
private evidence bytes. Tests do not rewrite source, contract, approval, payout,
journal or audit dates. Its October 6 prefix proves positive elapsed EIR, exact
retry and both original cash/loan journals. Current-day operational receipt and
allocation prove liability consumption and absence of second cash. Subsequent
same-day cash proves one daily accrual and stable prior audit. A current cutoff
must retain remaining contracts, explicit risk/scenario evidence, reports and
formal close. Missing/stale prior source claims, semantic account changes,
backdated insertion, competing posts, lost private evidence and atomic rollback
remain rejection cases. Legacy prepared digests and existing 7x7 behavior require
separate unchanged regression proof.

The cash verifier walks prior events in economic order and checks each retained
claim structurally against fresh source proof. It does not recursively rebuild
every earlier application. The performance regression uses twenty actual
same-day applications with a five-second statement bound and forces deferred
constraints after each operation, matching the production transaction boundary.
Stable current-day release tests cover both partial and full payment with zero
elapsed EIR; the retained dated capture supplies elapsed-history evidence.
Pure maturity arithmetic tests do not change any source date or claim to prove
a future operational posting.
