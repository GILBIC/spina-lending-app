# SPINA accounting readiness — 5 October 2026

**Decision: strengthened and verified for the supported flows; not yet ready for unrestricted lending-company accounting.** Work is local to `codex/accounting-completion-20261005`. No production migration, deployment or real-money posting has occurred.

The owner-operated business and the future registered company use separate books. The user delegated the framework and chart design. Actual entity identity, opening figures, wallet ownership, financing contracts and tax settings remain facts to supply and reconcile; the software does not invent them.

## Implemented controls

| Area | Current behavior |
| --- | --- |
| Separate books | Immutable book identity, compatible wallet/context checks and optional database identity pinning prevent mixing owner and corporate records. |
| Liabilities | Unapplied borrower receipts, Collector excess/payables/returns and generic linked liabilities reconcile to exact source evidence and posted controls. A valid unpaid liability does not have to be zero to close. |
| Cash once | Supported receipt/application, owned-transfer and pure original Regular payout stages recognize actual cash once. Completion and liability reclassification do not create another cash receipt. |
| Loan measurement | Supported first applications retain their original contract and interest policy. Regular fiscal prefixes preserve original unrounded interest timing. The bounded historical assessment path retains its risk/scenario evidence. |
| Financial statements | Cash, equity and comparative reports share one database snapshot. Cash definitions and classifications are retained. Known internal transfers and Collector handovers cannot inflate gross business receipts/payments. |
| Closing | Missing, stale, corrected, unsupported and even offsetting unregistered source effects remain visible blockers. Review evidence is pinned and rechecked under locks and at commit. |
| Recovery and access | Exact retry, current permission checks, private projections and populated database/private-file restore have automated verification. Web/mobile views clear private state after permission or session changes. |

The detailed supported scope matters. Existence of an account, a balanced journal or a passing unit test does not mean every loan product, correction or historical source is handled.

## Latest saved milestones

- `b27779c6`: separate-book controls, statement snapshot integrity and incomplete-source close protection.
- `c22a174b`: retained source accounting, liabilities, financial reporting and current-schema recovery through migration0154.
- `0c87b01e`: protected first Regular Treasury applications through0155, with web/mobile review and unchanged original 7x7 behavior.
- Native0156 original payout provenance passes all76 selected native/payout/access/close/restore checks. Collector reference and operational regression verification passes65 current-schema checks with zero skips after the old capability expectation is corrected. Native elapsed assessment/application integration remains unfinished.

Recent verification evidence includes fresh0154 with194 passing checks, fresh0155 with136 passing checks and zero skips, the expanded web selection with163 passing checks, combined accounting Flutter with135 passing checks, and the subsequent Regular Flutter selection with28 passing checks and clean scoped analysis. These suites overlap and are not an additive unique test count.

Latest 0157 verification: fresh-schema integration passes 140 checks, and the supplemental date/capacity/immutability/original-workflow selection passes 85, both with zero skips. The latter includes separate cash-count and credit-acceptance dates and an application reservation waiting behind a competing return. Portal regressions pass 270; Flutter passes 123 with clean analysis of 15 changed files; API/contract regressions pass 31. These selections overlap. Populated restore preserves application facts, posting proof and private files. No production migration or flag activation occurred.

## Remaining implementation work

1. **Collector historical coverage:** 0157 now supports current original recognized credit applied to a later exact remittance, including partial and zero-cash settlements. Opening-credit and historical correction adapters remain blocked; they are not covered by this new path.
2. **Native payout integration:** the private origin normalizer must be connected to elapsed assessment and first application while preserving old source digests. Positive elapsed and closed-origin behavior require genuine dated native source evidence; no clock override or fabricated legacy posting will be used.
3. **Wider lending and correction coverage:** finish the remaining supported loan lifecycle, product transitions, refunds/corrections and historical source adapters, then prove their combined control balances and close behavior.
4. **Complete disclosure coverage:** implement retained component evidence for mixed cash/noncash journals and financing-liability reconciliation. Current reports explicitly do not claim complete mixed-transaction disclosure or a complete annual statutory package.
5. **Final combined release proof:** run all required checks against the final source, complete whole-change review, and perform isolated staging/recovery and reconciled opening/parallel-close work using actual supplied facts before production activation.

## Retained implementation references

- [Execution ledger](2026-10-05-accounting-completion-progress.md)
- [Full implementation plan](../superpowers/plans/2026-10-05-accounting-completion.md)
- [Framework and chart decisions](../accounting/lending-accounting-design-decisions.md)
- [Collector application design](../accounting/collector-credit-application-design.md)
- [Native payout-origin contract](../accounting/native-payout-regular-origin.md)
- [Mixed disclosure design](../accounting/noncash-disclosure-design.md)
- [Release and recovery procedure](../accounting/accounting-release-and-recovery.md)
