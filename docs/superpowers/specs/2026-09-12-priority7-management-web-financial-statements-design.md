# Priority #7 — Management Web Financial Statements Design

## Scope

Add a read-only Management Web surface for the existing protected financial-statements capability. Web consumes `/api/v1/management/financial-accounting/statements`; it does not calculate accounting values locally and does not create another accounting path.

## Authority and security

- PostgreSQL/FastAPI remains authoritative.
- The existing endpoint continues to require authenticated device context, `accounting.view`, and the Management role.
- Web permission gating is presentation only; server RBAC remains final authority.
- No production deployment, merge, Auth mutation, database mutation, financial posting, or live-data action belongs to this slice.

## Web behavior

- Management sees a Financial Statements action/section only when the authenticated session contains `accounting.view`.
- The screen loads the existing statement payload and renders its period, Statement of Profit or Loss, and Statement of Financial Position.
- All amounts and labels shown are server-returned values. JavaScript must not recompute balances, retained earnings, tax, ECL, loan schedules, or other accounting values.
- Error and empty states are explicit and non-mutating.
- Existing portal primitives and responsive layout are reused; no new framework/design system is introduced.

## File boundary

- Create `spina_portal/assets/management-financial-statements.js` for loading/rendering the protected statement payload.
- Create `spina_portal/tests/management-financial-statements.test.mjs` for source-of-truth rendering tests.
- Modify `spina_portal/assets/roles.js` only to add the protected Management action under `accounting.view`.
- Modify `spina_portal/assets/roles/management.js` only for the smallest mount/navigation integration.

## Parallel-development boundary

Priority #4 Draft PR #420 owns onboarding/CIF backend work and is untouched. Priority #5 Draft PR #422 changes `app.css`, `roles/employee.js`, and `roles/management.js`; therefore the renderer is isolated in a new file and the eventual `management.js` integration must stay minimal. Priority #6 7x7 schedule/accounting rules are untouched and are never reimplemented in Web.

## Acceptance

1. Without `accounting.view`, Management Web exposes no Financial Statements action/section.
2. With `accounting.view`, this feature calls only the existing protected statement endpoint.
3. Statement lines/totals are rendered directly from the server payload without local recomputation.
4. Existing portal regression stays green.
5. No backend/accounting source file changes.
