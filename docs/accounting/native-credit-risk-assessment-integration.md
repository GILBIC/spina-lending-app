# Native credit-risk assessment integration

This is S04 integration work under the October 5 completion specification.
The initial elapsed assessment design limits its first tranche to Stage 1 and
fewer than 30 contractual days past due. It does not classify ordinary Stage 2
or Stage 3 accounting as a deferred historical-source correction.

The existing 0070 credit-risk review retains schedule and DPD observations,
30/90-day backstops, separate rebuttal evidence, default decisions and cure or
recovery evidence. The 0075/0076 engine provides lifetime cash-shortfall
measurement; 0077/0079 protects allowance recognition, remeasurement, write-off
and recovery. Those controls remain the authority and journal-treatment model.
Their old current-queue and legacy-anchor prerequisites do not prove a native
loan's dated fiscal cutoff. Manual allowance entries cannot substitute for that
missing source proof.

## Dated review and scenario boundary

Stage 1 preparation bytes remain unchanged. A separate risk preparation binds
the existing retained credit-risk review ID to the exact native schedule,
economic cutoff and as-of contractual DPD observation. A review recorded today
does not establish the state at an older cutoff. Review fields and evidence
remain explicit; neither elapsed time nor a paid flag supplies a default,
rebuttal, cure or loss forecast.

The separate preparation request contains book ID, source digest, positive
integer credit-risk review ID, explicit scenarios, rationale and confirmation.
Stage 2/3 responses use `historical_native_lifetime_cash_shortfall_v1`, echo the
review ID, stage and lifetime horizon, and retain the same exact scenario
inputs. A retained Stage 1 label uses the separate
`historical_native_reviewed_12_month_cash_shortfall_v1` policy and preserves the
existing twelve-month measurement. A Stage 1 review beyond the 30/90-day
backstops must retain the existing separate rebuttal evidence; overdue status
does not replace that decision with an automatic Stage 2 label.
Forecast eligibility keeps the existing economic-effective,
observation, retrieval, version and revocation checks. The dated contractual
PV calculation from 0156 is retained; the old current-queue engine's zero-day
cap on overdue contractual cash flows must not be reintroduced.

Stage 3 uses verified gross carrying amount less the probability-weighted
present value of expected receipts at original EIR, following
[IFRS 9 B5.5.33](https://standards.xrb.govt.nz/standards-navigator/nz-ifrs-9/).
Stage 2 retains contractual cash shortfall as its loss basis. The Stage 3 result
retains the full-precision weighted present value as a decimal string and rounds
the final loss once. Its public currency rounding adjustment reconciles the
separately rounded display amounts. For example, gross carrying of 100.00 and
weighted PV of 99.995 produces ECL of 0.01, displayed PV of 100.00 and a 0.01
rounding adjustment. No measured loss is changed merely to fit a displayed
identity.

## Stage 3 interest boundary

Stage 2 continues to recognize original effective interest on gross carrying.
Stage 3 requires an explicit retained impairment measurement boundary with
its actual economic date and forecast evidence before calculating subsequent
net interest. A newly reviewed current label cannot silently backdate that
boundary. Existing exact original/renewal carrying and real cash events remain
the gross source; allowance is a separate component.

For each supported credit-impaired interval, the gross/net interest difference
unwinds the retained allowance. Interest income receives net interest only;
the allowance adjustment remains separate and its subsequent remeasurement or
cure reversal goes through impairment profit or loss. Full contractual payoff
still clears exposure under its own reviewed source and releases the remaining
allowance through the protected assessment.

Migration 0169 retains intervening impaired-cash reviews as measurement
evidence. It does not post a second cash journal or an interim allowance
journal. Each review binds the exact protected application, the posted opening
Stage 3 assessment, the last actual cash transaction of that day, and forecast
evidence available at the cash date. Expected receipts determine the target
allowance; clients cannot supply an allowance, rate, stage, payoff flag or date.
The immutable review chain participates in the fiscal candidate digest and
period-review manifest. A changed or missing review prevents confirmation.

For each interval, calculate net interest directly as rounded original-EIR
growth on reviewed net carrying amount. Preserve the protected gross-interest
source and reconcile allowance by `U = source GI - rounded NI`. Independently
rounded gross growth can differ from protected cumulative gross accrual by a
cent. The optional signed `currency_rounding_adjustment` discloses
`source GI - rounded gross growth`; `U - currency_rounding_adjustment` is the
nonnegative economic gross/net difference. This is the retained currency
reconciliation convention, not a cent-rounding rule prescribed by IFRS 9.

For example, original gross 1,000 and contractual 1,050 due in 30 days produce
rounded gross carrying 1,006.53 on day 4. The protected cumulative gross accrual
to day 5 is 1.63, while direct rounded net interest is 1.64 with opening allowance
0.01 or 0.00. Thus `U = -0.01`, disclosed with currency adjustment `-0.01`.
Positive U debits 4000 and credits 1190; negative U reverses those roles using
nonnegative debit and credit amounts. The separate reviewed impairment
adjustment is `D = target A - opening A - U`, so the final allowance remains
exactly the reviewed target within zero and remaining gross exposure. No clamp
changes net interest or the target. A temporary arithmetic `A + U` can be
negative before the same journal's reviewed D; it is not a separately posted
negative allowance. Renewal requires an existing supported target if its
unreviewed final allowance would otherwise fall outside those bounds.

A cash-day target then determines the
allowance used for the next interval. The fiscal journal recognizes aggregate
unwind once and measures impairment expense as final allowance minus opening
posted allowance minus that unwind. Interim measurement changes therefore
reconcile into the final adjustment instead of creating duplicate GL entries.
A cash transaction on the final cutoff date uses the final fiscal scenarios,
because no later interval needs an interim target. Exact full payoff supplies
zero remaining allowance and stops further interest; its settlement difference
uses gross carrying value, independently from the impairment reversal.

The assessment API exposes dated cash-review needs, a source-bound read, and
an explicit review command under the existing period preparation permission.
It verifies original/renewed signed-contract bytes and the retained cash
receipt bytes inside the same transaction before returning success. The UI
reloads the assessment after retaining this evidence, then uses the existing
separate fiscal prepare and confirm commands.

This treatment follows the IFRS Interpretations Committee's final
[March 2019 decision on curing a credit-impaired financial asset](https://www.ifrs.org/content/dam/ifrs/supporting-implementation/agenda-decisions/2019/ifrs9-curing-of-a-credit-impaired-financial-asset-mar-19.pdf).
The decision links net interest, the discount unwind on the loss allowance, and
the impairment reversal required when an asset is paid or ceases to be impaired.

## Required proof

Current native Stage 2 and Stage 3 reviews use the existing authorized risk
label command and actual retained forecast evidence. Tests must prove explicit
review identity, exact stage/default and schedule/DPD matching, incorrect or
future dates, unavailable forecasts, changed prior proof, duplicate replay,
permission denial and rollback. Numerical interval tests may use input dates
to test arithmetic; they are not evidence of an operational future posting.
Combined close requires every actual risk boundary, cash application and fiscal
assessment to reconcile to its protected journals and immutable source audit.
An actual newly originated loan cannot prove a subsequent-period impaired
cash lifecycle on its release day. Current-date Stage 3 posting/close and pure
multi-day interval arithmetic are separate verification claims; no source or
review timestamp is changed to manufacture elapsed history. Retained captures
can prove those later transitions after their actual economic dates arrive.
