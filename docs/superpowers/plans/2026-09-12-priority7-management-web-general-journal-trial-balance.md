# Priority #7 Management Web General Journal + Trial Balance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose existing protected Management General Journal and Trial Balance read-only capabilities in shared SPINA Web without adding journal mutation controls or another accounting authority.

**Architecture:** Add one isolated Web module that consumes the existing journal-list and trial-balance GET endpoints. Gate presentation with `accounting.view`, while existing FastAPI Management-role + permission checks remain authoritative. Keep all manual journal create/edit/post/cancel/reverse operations out of this slice.

**Tech Stack:** Vanilla ES modules, Node `node:test`, existing SPINA portal UI helpers, FastAPI/PostgreSQL existing APIs.

**Spec:** `docs/superpowers/specs/2026-09-12-priority7-management-web-general-journal-trial-balance-design.md`

## Global Constraints

- No backend/accounting source changes.
- No local accounting calculations.
- No journal mutation UI or mutation API calls.
- No Priority #4 onboarding/CIF edits.
- No Priority #6 7x7 accounting/schedule edits.
- No Priority #8 Client schedule edits.
- Keep `roles/management.js` delta minimal because Priority #5 PR #422 also changes that file.
- No merge, deploy, production Auth/data mutation, or live financial action.

---

### Task 1: Permission-gated Management action

**Files:**
- Test: `spina_portal/tests/management-general-journal.test.mjs`
- Modify: `spina_portal/assets/roles.js`

**Interfaces:**
- Consumes: `availableRoleActions(role, permissions)`.
- Produces: one `management-general-journal` action pointing to `/api/v1/management/financial-accounting/journals` with `permission: 'accounting.view'`.

- [ ] **Step 1: Write the failing test** proving the action is absent without `accounting.view`, present with it, and never exposed to Employee/Collector.
- [ ] **Step 2: Verify RED** on the exact test-only head.
- [ ] **Step 3: Add the minimum `roles.js` action** under Management only.
- [ ] **Step 4: Verify focused GREEN** before proceeding.

### Task 2: Read-only loader and renderer

**Files:**
- Create: `spina_portal/assets/management-general-journal.js`
- Extend test: `spina_portal/tests/management-general-journal.test.mjs`

**Interfaces:**
- Produces `loadManagementGeneralJournal(api)` calling exactly `/api/v1/management/financial-accounting/journals`.
- Produces `loadManagementTrialBalance(api)` calling exactly `/api/v1/management/financial-accounting/trial-balance`.
- Produces `managementGeneralJournalMarkup({ journals, trialBalance })` rendering only server-returned values.

- [ ] **Step 1: Add failing tests** for exact GET paths, escaping, server-returned journal totals, server-returned trial-balance totals, and absence of mutation controls/paths.
- [ ] **Step 2: Verify RED** because the module/functions are absent.
- [ ] **Step 3: Implement the minimum pure loaders/renderer** using existing UI helpers.
- [ ] **Step 4: Verify focused GREEN**.

### Task 3: Management workspace integration

**Files:**
- Modify: `spina_portal/assets/roles/management.js`
- Extend test: `spina_portal/tests/management-general-journal.test.mjs`

**Interfaces:**
- Adds navigation id `management-general-journal` only with `accounting.view`.
- Loads both read-only GET payloads only when permitted.
- Adds one read-only section without mutation buttons/forms.

- [ ] **Step 1: Add failing source/integration test** for isolated import, permission gate, two GET loaders, section id, and no mutation endpoint strings.
- [ ] **Step 2: Verify RED**.
- [ ] **Step 3: Make the smallest `management.js` integration**.
- [ ] **Step 4: Verify focused portal GREEN**.

### Task 4: Installed Web/PWA dependency integrity

**Files:**
- Extend test: `spina_portal/tests/management-general-journal.test.mjs`
- Modify: `spina_portal/sw.js`

- [ ] **Step 1: Add failing test** requiring `/assets/management-general-journal.js` in `SHELL_ASSETS`.
- [ ] **Step 2: Verify the single intended RED**.
- [ ] **Step 3: Add only the missing shell-cache entry**.
- [ ] **Step 4: Require a fresh full exact-head SPINA CI SUCCESS across all three lanes**.

### Task 5: Continuity checkpoint

- [ ] Record exact branch/PR/head and RED→GREEN evidence in PR #425.
- [ ] Synchronize Notion and Create State with exact head, CI, slice boundary, and next action.
- [ ] Keep PR Draft/open/unmerged; do not deploy.
