# Priority #7 — Management Web General Journal + Trial Balance Design

## Scope

Add one read-only Management Web surface for the existing protected General Journal and Trial Balance GET capabilities. Web consumes `/api/v1/management/financial-accounting/journals` and `/api/v1/management/financial-accounting/trial-balance`; it does not create, edit, post, cancel, or reverse journal entries and does not create another accounting path.

## Authority and security

- PostgreSQL/FastAPI remains authoritative.
- Both GET endpoints continue to require authenticated device context, `accounting.view`, and the Management role.
- Web permission gating is presentation only; server RBAC remains final authority.
- `accounting.journal.manage` mutation capabilities are intentionally not surfaced in this slice even if the server says `can_manage=true`.
- No production deployment, merge, Auth mutation, database mutation, journal posting, or live-data action belongs to this slice.

## Web behavior

- Management sees one combined `General journal & trial balance` action/section only when the authenticated session contains `accounting.view`.
- Initial load requests the existing journal list and trial balance GETs in parallel.
- General Journal renders server-returned entry number, date, period, description, source/status, creator/poster, total debit/credit, and journal lines.
- Trial Balance renders server-returned period, balanced status, total debits/credits, and account lines.
- All monetary values, balances, and labels shown are server-returned values. JavaScript must not recompute trial balance, journal totals, accounting classifications, loan accounting, ECL, tax, schedule, or carrying amounts.
- `can_manage` may be shown as informational capability metadata only; no create/edit/post/cancel/reverse controls are rendered.
- Error and empty states are explicit and non-mutating.
- Existing portal primitives and responsive layout are reused; no new framework/design system is introduced.

## File boundary

- Create `spina_portal/assets/management-general-journal.js` for loading/rendering the two protected GET payloads.
- Create `spina_portal/tests/management-general-journal.test.mjs` for permission, endpoint, source-of-truth, read-only, and PWA tests.
- Modify `spina_portal/assets/roles.js` only to add one `accounting.view`-gated Management action.
- Modify `spina_portal/assets/roles/management.js` only for the smallest import/navigation/fetch/section integration.
- Modify `spina_portal/sw.js` only to precache the new static module after the corresponding RED test proves the dependency.

## Parallel-development boundary

- Priority #4 Draft PR #420 owns onboarding/CIF/first-loan work and is untouched.
- Priority #5 Draft PR #422 changes `roles/management.js` for Area Management; integration here must remain additive and minimal.
- Priority #6 Draft PR #426 owns 7x7 contract/accounting alignment; Web displays only current server-returned accounting evidence and does not encode 7x7 accounting rules.
- Priority #8 Draft PR #424 owns Client authoritative schedules and is untouched.

## Acceptance

1. Without `accounting.view`, Management Web exposes no General Journal / Trial Balance action or section.
2. With `accounting.view`, Web calls only the existing journal-list GET and trial-balance GET for this feature.
3. No journal mutation endpoint or mutation control is present in this slice.
4. Journal totals/lines and Trial Balance totals/lines are rendered directly from server payloads without local recomputation.
5. Installed Web/PWA precaches the new static module dependency.
6. Existing portal regression and full exact-head CI stay green.
7. No backend/accounting source file changes.
