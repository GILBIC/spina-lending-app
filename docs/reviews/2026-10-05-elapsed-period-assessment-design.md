# Historical cutoff assessments and cumulative EIR recognition

Migration0153 implements the bounded historical Regular no-cash path below. Genuine RED reached the missing candidate function after a real protected release/schedule fixture. Initial verification passed14 PostgreSQL behavior cases in13.66s, two actual repository transaction/authorization cases in13.00s and14 API cases in3.49s. The first posting run exposed the existing1190 protected line-write requirement; the new adapter now scopes that existing capability to its exact preparation-bound ECL lines, with153's independent coordinate guards retained. Concurrency/deferred/chart and fresh-schema integration remain separate verification. No production database was touched.

Migration0151 had seven PostgreSQL cases passing before the separate future-payout projection regression. The earlier legacy completeness suite has34 passing cases;0148 has33 main/boundary/repository/API/precision checks and seven chart-role cases;0149 has16 composition cases and two fresh-schema/recovery checks. These results do not establish comprehensive historical measurement coverage.

## Dates and source authority

`as_of_date` is the fiscal period end, the economic measurement date. `calculated_at`, `prepared_at`, `posted_at` and evidence retention timestamps record actual database time. A calculation made in October for a September cutoff is a September economic measurement retained in October. It must not overwrite0076 measurements or manufacture September creation timestamps. The new model supports a genuine historical cutoff rather than perpetuating0076's current-date-only restriction.

The first path supports an active, protected original Regular loan with a verified signed schedule, a positive original daily EIR, and no actual collection, cancellation, renewal, modification, write-off or recovery through the cutoff. The cutoff is after release and no later than contractual maturity, with remaining contractual horizon no longer than365days. Stage1/non-default with fewer than30 contractual days past due is initially supported. An explicit as-of risk review remains required; a current-date label is not imported as historical fact. Other supported policies are added in later tranches with their own behavioral tests.

Actual sources after cutoff are excluded by business date, not by their creation time. A late-entered source with an earlier business date is included and invalidates affected retained proof. Original contract identity and economic chart meanings remain pinned. Current display names/retirement do not alter a posted accounting amount; current semantic role changes do. An as-of projection must not hash mutable receipt balances, future application legs or current loan workflow status as though those were original cutoff facts. States whose economic history cannot yet be reconstructed are explicit blockers.

## Existing authority and limitations

- `eir_cash_allocation.allocate_event_date_eir_cash` compounds raw Decimal daily interest, rounds at actual cash events, allocates cash first to accrued interest, and resets to exact cents only after that cash boundary. It refuses7x7 and post-maturity extrapolation.
- `build_greenfield_regular_renewal_rollforward` can calculate the last no-cash tail using the same engine. It is a preview, not posting authority. Its renewal same-day cash ordering restriction must not accidentally become a general fiscal-cutoff rule.
- Existing Regular period splits use largest fractional remainder across the entire cash span. A future extension can change which earlier period receives a residual cent. This is unsuitable for immutable recognized prefixes.
- SQL0064 has a separate7x7 EIR source preview using the protected original anchor, exact cent cash boundaries and original-EIR compounding. The operational fixed-interest allocator is not an EIR substitute. No-Collection holidays, extra principal and modification authorities require separate reconstruction.
- SQL0076 retains explicit probability-weighted, original-EIR discounted contractual shortfalls, exact schedules, risk-review identities and forward evidence. Its `current_date` admission check and0072 zero-collection carrying gate cannot prove historical balances.0153 retains a new explicit as-of model rather than editing old measurement records or relabeling a current snapshot.

## Recognition without duplicate interest

Each actual cash boundary identifies one segment: protected original anchor or an exact posted cash boundary. At cutoff `t`, replay that segment from the original raw basis, keeping full precision until the final cent rounding:

`cumulative_interest(t) = round(sum(raw_daily_interest through t), 2)`

`new_interest(t) = cumulative_interest(t) - exact_previously_recognized_prefix`

Prior fiscal cutoffs are recognition points, not cash events. They do not reset raw compounding. A later cutoff or collection cannot rerun largest-remainder allocation over a previously frozen period, round each day, or compound from the rounded prior-cutoff GL balance. The retained audit records segment identity, original cent basis, daily rate, raw cumulative total, prior claimed cents, current cumulative cents, incremental cents and exact journal identities.

The first cutoff must cover the segment from release, or have exact prior-prefix proof covering every earlier elapsed day. A missing earlier-period prefix is a blocker; the current period cannot absorb prior-period income. Prefixes are chronological, nonoverlapping and unique by book/loan/segment/cutoff. Existing unsupported accrual or collection journals are not silently subtracted by net balance. Negative or mismatched controls, even if another receivable offsets them, remain blockers.

New positive interest posts Dr1120 accrued interest receivable / Cr4000 Regular interest income, with client/loan dimensions and posting date equal to cutoff. An exactly calculated zero increment retains evidence and creates no zero journal. Initial no-cash carrying is1100 original carrying,1110 zero,1120 exact cumulative interest. Later cash support must replay the original allocator, prove each existing allocation and subtract prefix claims only from the accrual journal proposal. It must not alter contractual collection allocation or recognize cash twice.

## Historical quantitative ECL

The preparer supplies explicit scenario probabilities, expected cash dates/amounts, exact forward-evidence IDs and an as-of risk review. These are economic inputs, not a ready checkbox. Probability, currency, source identity, date, evidence and risk-backstop validation follow the existing protected measurement authority. No probabilities, PD/LGD, future receipts or zero losses are invented.

The private as-of source snapshot contains:

1. Book and fiscal-period identity, cutoff and original signed contract/registration/installments, original release posting and initial carrying/EIR authority.
2. Dated source/reversal inventory through cutoff, contractual installment allocations through cutoff and computed remaining amounts, oldest due-unpaid date, due-unpaid amount, DPD and risk band. Initial no-cash support computes these directly from the signed schedule.
3. A new risk-review instruction with `as_of_date`, stage/default/write-off/recovery labels, evidence basis/reference and rationale, reviewed now. It must match computed as-of DPD. Initial support forbids backstop rebuttals, default, Stage2/3, write-off/recovery/cure and missing evidence; future paths must implement their real authority before enabling them.
4. Explicit approved forward-evidence rows whose economic effective date and observation end are no later than cutoff and whose forecast interval covers cutoff. Their source retrieval timestamp must establish availability by cutoff. Approval/retention may occur now. Evidence retrieved only later without retained publication/availability evidence is unsupported, not silently assumed historical. Revocation or a correction effective at/before cutoff invalidates the proof; a genuinely later effective forecast does not replace an earlier cutoff automatically.
5. Canonically ordered scenario/contract snapshots, original discount rate and policy. Expected cash dates must be at/after cutoff. Repeated historical overdue due dates may be aggregated into one explicitly forecast receipt on cutoff; the system never substitutes its own expected date.
6. Exact posted1100/1110/1120/1190 components and original journal/line/audit identities through cutoff, including prior prefix and allowance lineage. A matching net total alone is insufficient.

The new historical policy retains the original timing of contractual flows. Discount each remaining contractual amount with original EIR over `due_date-cutoff` days, including negative exponents for unpaid flows already due. This carries their original timing forward to cutoff; capping days at zero would discard the cost of delay. Discount each explicitly forecast receipt from its own expected date. Scenario loss is `max(contractual_pv-expected_pv,0)`; ECL is the rounded probability-weighted sum. Require rounded contractual PV to reconcile with independently reconstructed gross carrying for the initial no-cash path, retaining both raw amounts and any solver residual. Preserve exact decimal inputs. This is a distinct `historical_original_timing_cash_shortfall_v1` policy, not a rewrite of0076 history.

The primary basis is IFRS9 B5.5.28–B5.5.29, reproduced by the Australian standard setter in [AASB9, paragraphs B5.5.28–29](https://standards.aasb.gov.au/aasb-9-sep-2020): shortfalls include the timing of receipts, so full repayment later than contracted can still produce a loss. The [IFRS Interpretations Committee's March2019 decision](https://www.ifrs.org/news-and-events/updates/ifric/2019/ifric-update-march-2019/) also describes original-EIR discounting of contractual-versus-expected shortfalls. The negative-exponent computation and gross-carrying reconciliation are this implementation's derivation for the bounded no-cash case, not a quoted prescribed algorithm.

Independent numerical fixture:5000 initial carrying,120 daily contractual payments of50, original daily EIR0.003114181946. At day7, gross carrying rounds to5110.02. Deferring every overdue contractual receipt to day7 while keeping all amounts at50 gives expected PV5106.7330577 and timing loss3.29. The prior zero-day cap would have erased that loss. At day4 cumulative EIR is62.58; resetting from the rounded day2 balance would produce62.57. Both differences are behavioral regression cases.

The target allowance posts only its difference from the exact prior1190 balance. Increase: Dr5000 / Cr1190. Decrease: Dr1190 / Cr5000. Exactly zero difference means no journal. Genuine calculated zero ECL is supported; missing forecasts or measurements never imply zero. Prior allowance requires protected exact original0077/0079 or0153 proof, not an arbitrary manual balance. Initial deployment may support only zero prior allowance and prior0153 allowance where the exact older adapters cannot yet be revalidated.

## Preparation, posting and live composition

Proposed private interfaces:

- `loan_period_elapsed_assessment_candidate(period, loan)` returns source readiness, blockers, a private snapshot/source digest, original basis, cumulative/prior/incremental interest, prior allowance and as-of DPD. It does not claim completed ECL before explicit scenarios exist.
- `prepare_elapsed_loan_period_assessment(period, loan, actor, source_digest, risk_review JSONB, scenarios JSONB, rationale)` validates/recalculates and retains an immutable preparation, actual `calculated_at`, both economic calculations, full source identity and a confirmation digest covering inputs and results. It creates no journal.
- `post_elapsed_loan_period_assessment(preparation, actor, confirmation_digest)` revalidates all facts and posts zero, one or two required journals atomically, retaining one immutable posting audit and prefix claim. Idempotent retry returns the original audit; live exactness is a separate query.
- `period_elapsed_loan_assessment_exact(period, loan)` requires protected posting proof, unchanged economic source/measurement inputs, exact current chart semantics and exact resulting dated control lines. It is not true after preparation alone.

Tables are `loan_elapsed_assessment_preparations` and `loan_elapsed_assessment_postings`. The preparation owns the versioned historical measurement snapshot; this avoids the old148 measurement foreign key and its release-day-only policy constraint. The posting references preparation and nullable EIR/allowance journal IDs, never a manufactured journal ID for a zero result. Client roles receive no table/function rights. Database actor checks require current active Management role and prepare/post permission; no JSON actor identity is trusted.

Wrap `period_loan_assessment_exact` as old148 exact OR exact0153. Existing149 removes only the matching EIR/ECL period-end gaps; collection, tax, negative/unallocated controls and all other source blockers remain. Keep the existing148 source route valid and expose the new historical preparation route separately until a single authorized projection can dispatch both policies clearly. Extend151's additional-evidence and lock hooks with dated0153 preparations/postings, so a future cutoff cannot invalidate a prior manifest merely by appending a later prefix. Do not edit143/145/148/149/151 files.

## Concurrency and mutation boundaries

Writes use READ COMMITTED, current actor locks, established period advisory/row locks and the existing148 source-lock prefix in the same stable order as149/151. Add relevant legacy posting/reversal tables, then153 audit tables in SHARE ROW EXCLUSIVE before reading/recalculating. Do not take SHARE and later upgrade competing audit insert locks. Loan-scoped serialization prevents simultaneous periods from claiming the same prefix; acquire any multi-period locks in chronological/stable UUID order. Inspect order against concurrent collection/allowance/close paths before implementing.

Posting guards protect source keys `period_eir:<period>:<loan>` and `period_ecl:<period>:<loan>`, headers and exact line vectors. No generic/manual journal may claim those identities. Post both entries/audit in one transaction; stale evidence, role revocation, wrong digest, wrong book or failure of either entry rolls everything back. Source locks prevent a write racing the read. Deferred revalidation covers same-transaction backdated writes. After commit, real operational evidence remains recordable; it makes live assessment/manifest stale and blocks future close, preserving old audits.

Before enabling any old Regular collection or7x7 posting path for a loan with recognized prefixes, either route it through a tested prefix-aware accrual proposal or block only that accounting posting with an explicit prefix-adapter-required reason. Never reject recording actual collections. Otherwise a later legacy accrual could recognize the entire already-partly-recognized cash span again.

## Behavioral verification order

First RED fixture uses a real protected release before a past cutoff, verified signed installments and genuine forward evidence economically available by cutoff but approved/retained now. Candidate must propose the independently calculated elapsed interest. Preparation must retain cutoff separately from actual calculation time and leave journals unchanged. Confirmation must atomically add exact EIR and calculated allowance entries and clear only matching assessment gaps.

Further cases: cumulative prefixes over consecutive historical periods; no reset at rounded cutoffs; a later cash source does not stale an earlier cutoff; a backdated actual source does; unsupported prior collection blocks; future-only forecast evidence rejected; probabilities/precision/risk backstops checked; revoked evidence and semantic chart changes stale; wrong role/digest/post-without-preparation rejects; exact retry idempotent; audit/header/line immutability; deferred same-transaction source insertion rolls back posting; two-session source/assessment races retain real money evidence. Existing148 release-day and all149 negative/unallocated/tax behavior must stay green.

Then expand exact prior Regular collections, reversals and renewals with prefix-aware boundaries and a dated installment allocation projection.7x7 follows its protected original-anchor/source engine, not the contractual operational allocator. Comprehensive source/measurement coverage remains false until those paths and unsupported source families are implemented and verified.

## Historical assessment review surfaces

Portal and Flutter use a separate historical assessment entry; the148 release-day workflow remains available. Management selects a fiscal period and exact loan, loads the server's cutoff candidate, and sees economic cutoff, already-recognized interest, incremental interest, carrying amount, prior allowance and contractual DPD. Unsupported source states expose blockers without preparation controls.

The risk review records an explicit reference and substantive rationale under the bounded stage1/nondefault/no-write-off policy. Scenario and expected-receipt rows are repeatable; probabilities and monetary amounts remain decimal strings. Probabilities must total exactly1 using integer-scaled arithmetic. A scenario with no expected receipts requires removing its receipt rows explicitly. The existing authorized forecast-evidence listing supplies a paged picker by source reference; its current status is never treated as proof of historical eligibility. The database validates eligibility at the economic cutoff.

Reviewing inputs does not write. A separate confirmation retains the calculation. The resulting preparation shows actual `calculated_at`, economic `as_of_date`, cumulative/incremental interest, target ECL, prior allowance and signed allowance change. Another review and confirmation posts both required adjustments atomically. Recovered preparations include deep-allowlisted retained `review_inputs` so another session can inspect the exact risk/scenarios/receipts; private source and measurement snapshots are not returned. Fresh preparation responses must match the exact reviewed inputs before confirmation is offered.

An unknown result retains the original request path and immutable body for explicit unchanged retry. Session, permissions, device-provider or book changes discard private candidate, form, preparation and pending intent state. Definite rejected requests can be discarded and reloaded. A successful posting reports its retained reference and offers a new candidate read; success is not described as comprehensive period readiness.

The153 chart proof includes account posting role as well as code/key/type/normal balance. Account display-name changes and retirement preserve historical proof, but losing a required posting role invalidates current proof and prevents a new candidate from advertising readiness.
