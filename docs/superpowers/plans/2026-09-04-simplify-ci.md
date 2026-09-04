# Simplified CI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace duplicated broad CI workflows with one hosted, three-lane SPINA CI workflow while preserving backend, security, mobile/web, Android packaging, and disposable PostgreSQL coverage.

**Architecture:** `.github/workflows/spina-ci.yml` becomes the only broad automatic validation workflow. It has three GitHub-hosted Ubuntu jobs: `backend`, `client-apps`, and `financial-database`. Protected live-database maintenance and production deployment remain separate, manual workflows.

**Tech Stack:** GitHub Actions, Python 3.12, pytest, Ruff, Pyright, Bandit, pip-audit, Gitleaks 8.30.1, Node.js 22, Flutter 3.44.7, PostgreSQL 17.

**Spec:** User-approved instruction in the September 4, 2026 SPINA review: simplify CI without weakening financial or security controls.

## Global Constraints

- Do not connect automatic CI to a protected or live database.
- Use only loopback PostgreSQL created by the GitHub-hosted service.
- Preserve complete backend, root contract, Flutter, portal, Android packaging, and financial integration coverage.
- Keep scanner findings in baseline mode; scanner/runtime failures remain blocking.
- Keep protected maintenance and DigitalOcean deployment manual and separate.
- Do not alter lending, accounting, payment, 7x7, authentication, or production application behavior.

---

### Task 1: Lock the simplified topology with a failing contract test

**Files:**
- Create: `tests/test_simplified_ci_topology.py`

**Interfaces:**
- Consumes: workflow files under `.github/workflows`.
- Produces: a stable three-lane CI topology contract.

- [ ] **Step 1: Add the topology test**

Require `SPINA CI`, jobs `backend`, `client-apps`, and `financial-database`, three `ubuntu-latest` runners, a PostgreSQL service, Gitleaks, Python tests, portal tests/build, Flutter analysis/tests, Android debug packaging, and the consolidated financial validator.

- [ ] **Step 2: Verify the test fails against the old topology**

Run: `python -m pytest -q tests/test_simplified_ci_topology.py`

Expected: failures because the workflow is still named `SPINA Core Validation`, uses self-hosted Windows, and the retired broad workflows still exist.

- [ ] **Step 3: Commit**

```bash
git add tests/test_simplified_ci_topology.py docs/superpowers/plans/2026-09-04-simplify-ci.md
git commit -m "test: define simplified CI topology"
```

### Task 2: Replace broad automatic validation with three hosted lanes

**Files:**
- Modify: `.github/workflows/spina-ci.yml`
- Modify: `gilbic_backend/tests/test_unified_ci_live_verifier_ownership.py`

**Interfaces:**
- Consumes: existing Python packages, portal npm scripts, Flutter source, and disposable PostgreSQL validators.
- Produces: jobs `backend`, `client-apps`, and `financial-database`.

- [ ] **Step 1: Replace `spina-ci.yml`**

Create these jobs:

1. `backend`: compile Python, run Ruff/Pyright/Bandit/pip-audit/Gitleaks baselines, and execute all Python tests once with coverage and duration reporting.
2. `client-apps`: run portal tests/build and static-secret checks, Flutter analysis/tests, and one generated-host Android debug build.
3. `financial-database`: start PostgreSQL 17 as a local service and run the consolidated static and disposable PostgreSQL validators against loopback only.

- [ ] **Step 2: Update workflow ownership tests**

Remove assertions for exact-PR reuse and Stage 5E steps inside `spina-ci.yml`. Require hosted runners, no protected database environment, and ownership by the three new lanes.

- [ ] **Step 3: Run workflow contract tests**

Run:

```bash
python -m pytest -q tests/test_simplified_ci_topology.py gilbic_backend/tests/test_unified_ci_live_verifier_ownership.py
```

Expected: PASS.

### Task 3: Move legacy maintenance behind the existing manual gate

**Files:**
- Modify: `.github/workflows/spina-protected-maintenance.yml`

**Interfaces:**
- Consumes: existing Stage 5E `.once` markers and migration tools.
- Produces: explicit manual operations for the five legacy Stage 5E tasks plus the two current protected operations.

- [ ] **Step 1: Add manual operation choices**

Add `stage5e2-history-import`, `stage5e3-outcome-review`, `stage5e41-contractual-dpd`, `stage5e43-contract-registration`, and `stage5e46a-contract-activation`.

- [ ] **Step 2: Preserve fail-closed controls**

Require `main`, explicit confirmation, runner name `SPINA-WINDOWS`, and the corresponding `.once` marker before each legacy operation.

- [ ] **Step 3: Run maintenance contract tests**

Run:

```bash
python -m pytest -q tests/test_simplified_ci_topology.py gilbic_backend/tests/test_v1_tax_live_verifier_contract.py
```

Expected: PASS.

### Task 4: Remove duplicated broad workflow files and update review documentation

**Files:**
- Delete: `.github/workflows/spina-code-quality.yml`
- Delete: `.github/workflows/spina-security-compliance.yml`
- Delete: `.github/workflows/spina-reliability-performance.yml`
- Delete: `.github/workflows/spina-financial-database.yml`
- Delete: `.github/workflows/mvp-cross-platform-smoke.yml`
- Delete: `.github/workflows/spina-ci-deep-review.yml`
- Modify: `docs/ci-deep-review.md`

**Interfaces:**
- Consumes: the new single CI workflow.
- Produces: one broad automatic workflow and GitHub artifact-based diagnostics.

- [ ] **Step 1: Delete the six superseded workflow files**

The new workflow owns their automatic validation responsibilities. Keep `spina-delivery.yml`, DigitalOcean workflows, and `spina-protected-maintenance.yml`.

- [ ] **Step 2: Update CI review documentation**

Document the three lanes and GitHub artifacts. Remove the self-hosted `C:\SPINA_CI_REPORTS` requirement and obsolete manual deep-review workflow instructions.

- [ ] **Step 3: Run the complete Python suite**

Run:

```bash
python -m pytest -q gilbic_backend/tests spina_backend_mobile/tests tests
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/spina-ci.yml .github/workflows/spina-protected-maintenance.yml docs/ci-deep-review.md gilbic_backend/tests/test_unified_ci_live_verifier_ownership.py tests/test_simplified_ci_topology.py
git add -u .github/workflows
git commit -m "ci: consolidate SPINA validation into three hosted lanes"
```

### Task 5: Verify the pull request

- [ ] **Step 1: Open a draft pull request**

The PR description must state that no production deployment or protected database operation is authorized.

- [ ] **Step 2: Verify exact-head checks**

Require the new `backend`, `client-apps`, and `financial-database` jobs to complete successfully on the exact PR head.

- [ ] **Step 3: Review changed paths**

Confirm only CI workflows, CI contract tests, and CI documentation changed.

- [ ] **Step 4: Keep the PR unmerged until exact-head verification is complete**
