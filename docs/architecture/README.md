# SPINA and Gilbic Architecture Hub

This directory is the navigation center for understanding the whole lending platform, tracking delivery progress, and debugging problems without guessing which layer owns them.

**Current product snapshot:** 2026-08-28 (Asia/Manila)

## Start here

| Need | Open |
|---|---|
| Understand the approved future platform and migration phases | [`platform-direction.md`](platform-direction.md) |
| Use canonical people, accounting, and control terms | [`../../CONTEXT.md`](../../CONTEXT.md) |
| Understand why legacy roles are not mapped | [`../adr/0001-new-role-model-and-shared-server-authority.md`](../adr/0001-new-role-model-and-shared-server-authority.md) |
| Understand office cash, New Client Fund, and funding-capacity control | [`../superpowers/specs/2026-08-28-office-working-fund-and-new-client-fund-design.md`](../superpowers/specs/2026-08-28-office-working-fund-and-new-client-fund-design.md) |
| Understand why funding purposes share one real cash pool | [`../adr/0002-one-office-working-fund-with-tracked-allocations.md`](../adr/0002-one-office-working-fund-with-tracked-allocations.md) |
| Understand the whole platform | [`system-map.md`](system-map.md) |
| See completed, current, blocked, and next work | [`progress-map.md`](progress-map.md) |
| Diagnose an error by symptom and layer | [`debugging-playbook.md`](debugging-playbook.md) |
| See the generated desktop feature inventory | [`feature-map.md`](feature-map.md) |
| Find a desktop Python function or method | [`function-index.md`](function-index.md) |
| Trace desktop dependencies and callers | [`dependency-map.md`](dependency-map.md) |
| Find desktop database access | [`database-access-map.md`](database-access-map.md) |
| Review financial, authentication, write, and backup risks | [`risk-map.md`](risk-map.md) |
| Use the complete machine-readable desktop map | [`../../architecture-map.json`](../../architecture-map.json) |

## Two maps, one source of truth

The repository intentionally keeps two complementary architecture views:

1. **Generated desktop map** — `architecture-map.json` and the generated Markdown files. These are produced from Python source and should not be edited by hand.
2. **Living product map** — `platform-direction.md`, `system-map.md`,
   `progress-map.md`, and `debugging-playbook.md`. These separate intended
   platform direction from currently implemented behavior and connect Desktop,
   Mobile, Web, FastAPI, Supabase/PostgreSQL, CI, and legacy/external boundaries.

The generated map answers **“where is this desktop symbol and what calls it?”** The living map answers **“which product layer owns this behavior, what is finished, and where do I start debugging?”**

## Source-of-truth rules

For **current implemented behavior**, use this order:

1. Merged code on `main`
2. Database migrations and protected business-rule tests
3. Merged pull-request descriptions and validation results
4. This living architecture hub
5. Older local copies, screenshots, notes, or unmerged experiments

For **intended future behavior**, use
[`platform-direction.md`](platform-direction.md), Management-approved amendments
recorded in Master Issue #296, and the reviewed phase design. Future direction
never overrides the factual status of merged code. An open Draft PR is **in
progress**, not completed production behavior.

## Required update rule for future work

A pull request should update this hub when it changes any of these:

- a product boundary or component owner
- an API endpoint or data flow
- a database schema or authoritative record
- a financial calculation or 7x7 rule
- authentication, roles, permissions, or device enforcement
- offline behavior, retries, idempotency, or synchronization
- a milestone status, blocker, or next step
- the recommended debugging path

Python desktop changes must continue to regenerate and validate the static architecture map through the existing architecture-map tooling.

## Status language

- **Complete** — merged to `main` and validated.
- **In progress** — implemented on an open branch or pull request.
- **Blocked** — intentionally prevented until a prerequisite is verified.
- **Planned** — accepted direction but not implemented.
- **External / needs inventory** — known work exists outside the current GitHub-first source of truth.

## Fast operating habit

Before starting a new wave:

1. Read the target boundary in `platform-direction.md`.
2. Read the current critical path in Master Issue #296 and its latest approved
   comments.
3. Locate current ownership in `system-map.md`.
4. Use `debugging-playbook.md` to identify the IDs and evidence the change must preserve.
5. Open one focused branch and Draft pull request.
6. Run the relevant tests and permanent architecture checks.
7. Update status evidence before requesting merge approval.
