# CB1 Mobile Protected Period Close Specification

## Authority

- GitHub Master Issue #296, CB1 Management mobile.
- `gilbic_backend/sql/0091_add_protected_period_close.sql` and
  `0092_harden_period_close_balance_scope.sql` are the accounting authority.
- `gilbic_backend/src/gilbic_backend/period_close_api.py` is the only period-close
  application boundary. Flutter must not reproduce its accounting rules.

## Implementation checkpoint — 2026-08-30

- Implemented on `codex/cb1-mobile-period-close`, stacked on the unmerged CA6
  branch. This checkpoint is not deployed or released.
- The rejected direct mobile **Close period** mutation is removed. The current
  branch instead opens a dedicated **Formal period close** queue and calls the
  existing protected FastAPI/PostgreSQL prepare/post authority.
- Local evidence: backend period-close contract 6/6; focused Flutter CB1 suite
  20/20; complete Flutter suite 400/400; complete backend suite 1,282 passed and
  188 configured integration skips; strict Flutter analysis and Dart formatting
  clean.
- Repository Ruff lint/format remain documented non-blocking baselines in CI;
  no Ruff finding was introduced as a new release claim by this checkpoint.
- Remaining CB1 work outside this bounded slice includes the other CB1
  Management functional/security blockers, integration approval, production
  data/migration review, signing, deployment, and release approval.

## Problem

The current Management Financial Accounting page exposes a generic **Close
period** action through `set_fiscal_period_status`. Migration 0091 intentionally
rejects that transition with “Use the protected formal period-close posting
workflow.” The mobile control is therefore a misleading dead end and does not
provide the required retained-earnings prepare/post review.

## Current behavior

- Management can create a fiscal period, send it to review, and reopen it before
  a protected close preparation exists.
- FastAPI/PostgreSQL already provide an immutable formal close queue, protected
  preparation, exact digest, retained-earnings posting, retry identity, audit,
  and closed-period enforcement.
- Those formal endpoints currently expose only `/api/v1/...` routes; Gilbic
  Mobile has no repository or screen for them.

## Intended behavior

1. The existing period-close GET, prepare, and post handlers also expose
   `/api/mobile/v1/...` aliases. The aliases call the same functions and do not
   fork business logic.
2. Management opens **Formal period close** from the existing Financial
   Accounting page.
3. The mobile page displays the server queue and summary without calculating
   balances, net income, retained earnings, blockers, or readiness locally.
4. A ready period can be prepared only when both the current server response and
   current session authorize `accounting.period.close.prepare`.
5. A prepared period can be posted only when both authorize
   `accounting.period.close.post`.
6. Preparation and posting each use the shared Management review presentation.
   Posting shows the exact period, end date, net profit/loss, 3100 Retained
   Earnings, pre-close balance, temporary-account count, close digest, immutable
   journal reference, and consequence before confirmation.
7. Posting submits the exact server snapshot values. Flutter never derives or
   adjusts them.
8. One 64-character lowercase hexadecimal confirmation token is generated per
   `fiscal_period_id + close_digest` while the page is active. An uncertain
   network retry reuses that token; a changed digest receives a new token.
9. Closed and blocked periods remain read-only. Blockers remain visible in
   plain operational language.
10. The legacy direct **Close period** button is removed. **Send to review** and
    pre-preparation **Reopen** remain server-controlled fiscal-period actions.

## Status-to-action mapping

| Server `close_status` | Mobile meaning | Allowed mobile action |
| --- | --- | --- |
| `ready_for_review` | Period is still open | Use existing **Send to review** control |
| `ready_to_prepare` | Review freeze is ready | **Prepare protected close** with prepare permission |
| `prepared_confirmation_required` | Immutable snapshot exists | **Post retained earnings & close** with post permission |
| `closed_protected` | Protected close completed | Read-only evidence |
| `closed_legacy_without_protected_close_audit` | Immutable legacy close | Read-only warning |
| `blocked_*` | Server readiness failed | Read-only blocker and recovery guidance |

## Security and accounting invariants

- Active approved device and authenticated Management remain mandatory.
- The backend revalidates permissions, current queue state, digest, exact net
  income, account `3100`, period end date, and confirmation token atomically.
- `automatic_source_posting=false` remains unchanged.
- Closed periods cannot reopen in V1.
- Formal close journals and audit rows remain immutable and non-reversible.
- No SQL migration, production data, protected/live database, tax workflow, ECL
  calculation, or signing/deployment action belongs to this slice.

## Acceptance evidence

- Backend contract tests prove all three mobile aliases map to the existing
  handlers and retain the exact permission/confirmation fields.
- Flutter repository tests prove parsing and exact prepare/post requests.
- Widget tests prove permission isolation, confirmation/cancel behavior, server
  blocker visibility, exact post payload, and same-token retry.
- Existing Financial Accounting tests prove the rejected generic close action is
  gone and the protected workspace opens instead.
- Focused tests, full backend tests, full Flutter tests, strict analyzer,
  formatting, and exact-head GitHub CI must pass before the Draft PR checkpoint.
