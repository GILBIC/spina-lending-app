# Priority #7 Management Web Financial Statements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose the existing protected Management Financial Statements capability in shared SPINA Web without adding accounting logic or a second authority.

**Architecture:** Add one isolated Web renderer that consumes the existing `/api/v1/management/financial-accounting/statements` payload. Gate presentation with `accounting.view`, while the existing FastAPI Management-role + permission checks remain authoritative. Integrate the renderer minimally into the existing Management workspace.

**Tech Stack:** Vanilla ES modules, Node `node:test`, existing SPINA portal UI helpers, FastAPI/PostgreSQL existing API.

**Spec:** `docs/superpowers/specs/2026-09-12-priority7-management-web-financial-statements-design.md`

## Global Constraints

- No backend/accounting source changes.
- No local accounting calculations.
- No Priority #4 onboarding/CIF edits.
- No Priority #6 7x7 rule edits.
- Keep the `roles/management.js` delta minimal because Priority #5 PR #422 also changes that file.
- No merge, deploy, production Auth/data mutation, or live financial action.

---

### Task 1: Permission-gated Management action

**Files:**
- Test: `spina_portal/tests/management-financial-statements.test.mjs`
- Modify: `spina_portal/assets/roles.js`

**Interfaces:**
- Consumes: `availableRoleActions(role, permissions)`.
- Produces: `management-financial-statements` action pointing to `/api/v1/management/financial-accounting/statements` with `permission: 'accounting.view'`.

- [ ] **Step 1: Write the failing test** proving the action is absent without `accounting.view`, present with it, and never exposed to Employee.
- [ ] **Step 2: Run focused Node test** and verify RED because the action is missing.
- [ ] **Step 3: Add the minimum `roles.js` action** under Management only.
- [ ] **Step 4: Re-run focused test** and verify GREEN.

### Task 2: Read-only statement renderer

**Files:**
- Create: `spina_portal/assets/management-financial-statements.js`
- Extend test: `spina_portal/tests/management-financial-statements.test.mjs`

**Interfaces:**
- Produces `loadManagementFinancialStatements(api)` which calls exactly `/api/v1/management/financial-accounting/statements`.
- Produces `financialStatementsMarkup(payload)` which renders server-returned period, Profit or Loss lines/totals, Financial Position lines/totals, balanced status, source and notice without recomputing them.

- [ ] **Step 1: Add failing tests** using dynamic import fallback so missing renderer functions fail as assertions, not import errors; assert the exact endpoint call and exact server totals/line labels in returned markup.
- [ ] **Step 2: Run focused test** and verify RED because renderer functions are missing.
- [ ] **Step 3: Implement the minimum pure loader/renderer** using existing `escapeHtml`, `formatDate`, `formatMoney`, `badge`, `emptyState`, and `errorCard` helpers where appropriate.
- [ ] **Step 4: Re-run focused test** and verify GREEN.

### Task 3: Management workspace integration

**Files:**
- Modify: `spina_portal/assets/roles/management.js`
- Extend test: `spina_portal/tests/management-financial-statements.test.mjs`

**Interfaces:**
- Consumes `loadManagementFinancialStatements` and `financialStatementsMarkup`.
- Adds navigation id `management-financial-statements` only when `hasPermission(session, 'accounting.view')`.

- [ ] **Step 1: Add a failing source/integration contract test** proving `management.js` imports the isolated module, gates the section with `accounting.view`, requests it only when permitted, and mounts `id="management-financial-statements"`.
- [ ] **Step 2: Run focused test** and verify RED against the pre-integration `management.js`.
- [ ] **Step 3: Make the smallest `management.js` integration**: one permission flag, one conditional navigation item, one conditional settled request, one conditional section.
- [ ] **Step 4: Run focused test and existing portal regression**; verify GREEN.

### Task 4: PR checkpoint

- [ ] Record exact branch/head and focused/full portal test result.
- [ ] Open a Draft Priority #7 PR against `main`.
- [ ] Verify exact-head CI lanes before claiming completion.
- [ ] Synchronize GitHub PR body, Notion SPINA checkpoint, and Create State with branch, PR, head, task, CI state, and next action.
