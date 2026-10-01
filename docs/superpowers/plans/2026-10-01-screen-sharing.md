# Consented screen viewing implementation plan

> **For agentic workers:** Use superpowers:subagent-driven-development for scoped implementation and independent review. Root owns Git and integration; agents do not commit or deploy.

**Goal:** Let Management view an explicitly consenting account's eligible Spina screens without merging accounts or exposing sensitive screens.

**Architecture:** Private session metadata and a tightly bounded volatile latest-frame cache behind authenticated HTTP. Flutter captures explicit safe subtrees; supported desktop browsers capture only a verified restricted Spina element. Minimal request/consent/view/Stop controls reuse the existing session lifecycle.

**Tech Stack:** Existing FastAPI/psycopg/PostgreSQL, browser JavaScript/Element Capture, Flutter/Dart.

**Spec:** `docs/superpowers/specs/2026-10-01-screen-sharing-design.md`

## Global constraints

The shared API, field names, failure codes and all bounds are those in the spec. No additional services/dependencies unless proven necessary. No source or production secrets in evidence. No unrelated UI restoration, role expansion, backups or postponed work. Preserve existing blocked-file and native-UI boundaries.

## Review focus

- A delayed capture or HTTP response must not restore an image after Stop.
- A new dialog or credential result must not leak a first frame.
- An account/device permission change must revoke a previously accepted session.
- A killed process or sleeping app must not leave an unbounded or resumable session/image.
- A browser choosing a different tab/window must never transmit that source.

## Task 1 — backend consent, private metadata and bounded frames

Owner: backend agent. Create `screen_share_api.py`, `screen_share_repository.py` (split a small frame module if needed), SQL migration 0134 and focused tests; modify backend `main.py`, SQL security/migration expectations and financial CI only where necessary.

- [x] Write and run failing route/state/race/bounds tests against the shared HTTP contract.
- [x] Implement exact participant binding, current authorization, finite grants, private metadata and actively expiring volatile frames.
- [x] Implement bounded targets, incoming requests and idempotent Stop; expose image generation/sequence headers through existing CORS.
- [x] Run focused unit/API checks and real disposable PostgreSQL transitions/privacy checks; reserve heavy local database use with root.
- [x] Report changed files, test receipts and remaining acceptance limits; root reviews and commits.

## Task 2 — web holder and Management viewer

Owner: web agent. Create `spina_portal/assets/screen-sharing.js` and focused tests; wire `spina_portal/assets/app.js`, `styles.css`, build/service-worker inputs and related existing session/role integration as needed. Own all `spina_portal` changes.

- [x] Write failing tests for self-tab restriction-before-frame, unsupported fail-closed, sensitive sections, revoked/stopped generations and stale viewer clearing.
- [x] Implement API adapter using the exact contract and existing auth/device headers; no URLs carrying credentials.
- [x] Add minimal request/consent/viewer/Stop controls; capture only eligible declared sections and synchronously stop before sensitive navigation/logout/scope change.
- [x] Run focused Node/build checks; hand root a synthetic capability/acceptance route for actual harmless capture verification, without initiating capture on real content.
- [x] Report exact eligible/excluded surfaces and browser/Windows limitations; root reviews and commits.

## Task 3 — native holder and viewer

Owner: native agent. Create `gilbic_mobile/lib/src/core/mirror/` adapter/controller and `features/mirror/` capture/consent/viewer widgets; modify `src/app.dart` lifecycle/observer and minimal role entry/eligible daily-content boundaries. Own all `gilbic_mobile` changes, excluding the separate worktree's restoration.

- [x] Write failing tests for consent, explicit safe surfaces, route/dialog/background/session generation races, single-flight uploads and viewer stale clearing.
- [x] Implement the exact HTTP adapter and audited subtree capture with disposed images and no disk persistence.
- [x] Integrate minimal controls for all roles and eligible daily-work pages; unknown and sensitive pages stop sharing.
- [x] Run focused Flutter tests/analysis in the root-coordinated heavy-process window; no native UI automation, install or source-independent screenshots.
- [x] Report exact coverage and acceptance boundaries; root reviews and commits.

## Task 4 — integration, independent review and release evidence

Owner: root with cross-review by agents.

- [x] Reconcile exact contract across all clients and server; review dangerous races and privacy failures with synthetic fixtures.
- [ ] Run targeted integration/load/privacy checks, then appropriate branch CI; no repeat of unrelated unchanged acceptance suites.
- [ ] Update completion checkpoint, GitHub and Notion with verified progress and unresolved acceptance, preserving dated evidence.
- [ ] Create and attach PR; address review/CI findings. Only ship a build proven against the reviewed contract and protected release process. Do not call partial platform acceptance complete.

## Rulings / execution ledger

- 2026-10-01: reuse the clean isolated `spina-readiness` worktree on `feat/consented-screen-sharing-20261001` from exact deployed b47. Preserve the three uncommitted Android layout-restoration files in their other worktree.
- 2026-10-01: implement within the owner's standing authorization; a further design-approval round would repeat the explicit request to continue. No real account holder is opted into capture by this authorization; each session still needs that person's visible consent.
- 2026-10-01: cap near-live viewing at one frame/second and two sessions, with no recording or remote input, to avoid adding media infrastructure before it is justified.

- Local verification on 1 October: 25 backend cases passed including13 real PostgreSQL cases; root separately reran12 API/image unit cases. Final native46 focused cases and analyzer pass. Cross-review fixed Stop/device-resolution and eligible-navigation cadence races. Initial controller tests were not all observed red; the final race regressions and selected widget regressions were observed failing before fixes. Full branch CI and real platform acceptance remain pending.
- A small memory-only cache diagnostic held two512KiB frames,400 reads,8 replacements and40 rejected over-cap writes, peaking at1MiB and evicting to zero after idle expiry. This is not representative API/production capacity or SLA evidence.

- Final local portal verification: 914 tests passed,139 modules syntax-checked, and production portal build succeeded. The first full run exposed11 obsolete test-fixture expectations (new control DOM and shell v20); fixtures were updated without weakening lifecycle assertions. Web overlap/deadline/cadence regressions pass. Physical browser capture remains owner-deferred; no capture or production rollout is claimed.
