# Accounting completion execution ledger

Plan: docs/superpowers/plans/2026-10-05-accounting-completion.md

User authorized planning and fixes, then confirmed separate owner/corporate books. Baseline b5d6962; isolated branch codex/accounting-completion-20261005. Other Office checkout is untouched. Native worktree creation failed because the older chat repository lacks this commit; a worktree was created from the verified repository instead.

Ruling: use isolated databases/deployments for legally separate books. Existing functions and reports are single-book throughout; a partial book_id change would permit cross-book contamination. The cost is separate deployment/setup, rather than an unsafe selector.

Ruling: production configuration and accounting judgments are evidence inputs, not values inferred by an implementer. No deployment, actual balances or live migration is performed by this run.

Preflight interface check:

| Producer → consumer | Contract and finding |
|---|---|
| 0 → 6 | Preserve existing report fields; all new reports share the established snapshot. |
| 1 → 3/4/5/6 | One DB identity; context compatibility required before mapping or posting. |
| 2 → 3/4/5 | Initial source blockers are replaced only by exact reconciled adapter evidence. |
| 3 → 4/5/7 | Source identity, cash once, mapping version, idempotency and atomic posting audit. |
| 4 → 5/6/7 | Reconciled outstanding liability is valid; absence of payment is not a close failure. |
| 5 → 6/7 | Completeness digest is distinct from arithmetic balance. |
| 6 → 7 | Statements must reconcile across cash, equity and GL, including comparative data. |

Status: design and full program plan written; implementation and review gates pending. Earlier 143 tests were a baseline source assessment, not proof of these planned fixes.
