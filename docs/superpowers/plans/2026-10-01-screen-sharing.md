# Management live viewing implementation plan

> **For agentic workers:** Use superpowers:subagent-driven-development for scoped implementation and independent review. Root owns Git and integration; agents do not commit or deploy.

**Goal:** Let Management view an account's eligible Spina work screens with a visible named viewing indicator, automatic device readiness and Management-only in-app Stop, without merging accounts or exposing sensitive screens.

**Architecture:** Private session metadata and a tightly bounded volatile latest-frame cache behind authenticated HTTP. Flutter captures explicit safe subtrees; supported desktop browsers first obtain their platform sharing permission and capture only a verified restricted Spina element. Minimal setup/view/status and viewer-only Stop controls reuse the existing session lifecycle; holder safety teardown remains automatic.

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

## Current approved revision — 1 October 2026

Owner explicitly approved only Management stopping through Spina, with a clear Management-viewing indicator visible to the viewed account. This resolves the prior hold; covert viewing remains excluded. Finish the retained visible-only WIP before commit or release. Root owns integration and Git; native, web and backend owners work on separate files. The original completed tasks below describe historical implementation and are not proof of this revision.

- [x] Backend: finish device-readiness `/ready` contract (remove `/accept`), preserve participant authentication and lifecycle Stop, verify unit/API and real PostgreSQL transitions.
- [x] Native: automatic readiness only on eligible foreground work surfaces; painted visible indicator before capture; no holder Stop button; retain viewer Stop, safety termination and replay suppression; repair adapted capture test and verify changed flows.
- [x] Web: finish direct-gesture browser preparation, zero upload before valid Management session, automatic readiness, visible named indicator and viewer-only Stop; preserve restrictions, limits and teardown; verify focused then full portal tests.
- [x] Root: reconcile contracts and independent source review; preserve PR464 Management UI and verify persistent indicator layout on synthetic desktop/mobile pages.
- [ ] Release: update dated handoffs/GitHub/Notion; pass current-head CI and protected release gates before claiming rollout. Notion is temporarily unavailable; local/GitHub are authoritative for the current approved revision.

Ruling: retain participant-bound backend `/stop` for automatic lifecycle cleanup, because closing/backgrounding the app or browser permission revocation must end capture. Management-only Stop is the in-app manual-control rule; it does not promise uninterruptible viewing or bypass OS controls. No new control endpoint or media service is needed.

Current revision verification, 1 October 19:54 Manila:13 backend unit/API cases and16 real PostgreSQL cases passed after136 migrations; Ruff/Pyright clean. Native52 focused cases plus7 small-screen/large-text readiness cases passed, with full analyzer clean. Web26 focused and916 total cases passed;139 module syntax checks and production portal build passed. Independent review corrected an offscreen indicator and pending-request replay on remount, then found no remaining substantive source blocker. Root verified the named banner after long scroll at2560x1185 and390x844 without horizontal overflow. Actual browser/Windows/phone capture acceptance remains untested and owner-deferred; source checks are not rollout evidence.

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
- [x] Create and attach PR465; address initial review/CI findings. Subsequent integration checks and the protected release process remain required. Do not call partial platform acceptance complete.

## Rulings / execution ledger

- 2026-10-01: reuse the clean isolated `spina-readiness` worktree on `feat/consented-screen-sharing-20261001` from exact deployed b47. Preserve the three uncommitted Android layout-restoration files in their other worktree.
- 2026-10-01: implement within the owner's standing authorization; a further design-approval round would repeat the explicit request to continue. No real account holder is opted into capture by this authorization; each session still needs that person's visible consent.
- 2026-10-01: cap near-live viewing at one frame/second and two sessions, with no recording or remote input, to avoid adding media infrastructure before it is justified.

- Local verification on 1 October: 25 backend cases passed including13 real PostgreSQL cases; root separately reran12 API/image unit cases. Final native46 focused cases and analyzer pass. Cross-review fixed Stop/device-resolution and eligible-navigation cadence races. Initial controller tests were not all observed red; the final race regressions and selected widget regressions were observed failing before fixes. Full branch CI and real platform acceptance remain pending.
- A small memory-only cache diagnostic held two512KiB frames,400 reads,8 replacements and40 rejected over-cap writes, peaking at1MiB and evicting to zero after idle expiry. This is not representative API/production capacity or SLA evidence.

- Final local portal verification: 914 tests passed,139 modules syntax-checked, and production portal build succeeded. The first full run exposed11 obsolete test-fixture expectations (new control DOM and shell v20); fixtures were updated without weakening lifecycle assertions. Web overlap/deadline/cadence regressions pass. Physical browser capture remains owner-deferred; no capture or production rollout is claimed.

- CI36846377761 passed all three jobs on fab64f41:3173 backend tests passed with1087 skipped, zero scanner regressions, financial/PostgreSQL validation and synthetic recovery passed, and Portal/Flutter/Android passed. Retained evidence is in the parent checkpoint ci-fab64f41; this is not yet the combined-head result.
- Integrated upstream PR464 from b2ac2944 while preserving its older Management layout and single workspace. The only Management runtime additions relative to upstream are the mirror import and named safe portfolio wrapper.69 focused integration tests and1 real synthetic PNG subtree-capture test pass; the latter proves the private outside control is excluded and the720-edge/512KiB bounds hold. Narrow analysis of both resolved runtime files and the new test passes. A full local analyzer was stopped by the available-memory guard; combined-head CI must supply full analysis.
- The owner's browser-test deferral is limited to manual acceptance. Continue technical integration and protected release preparation under the standing authorization; label actual browser/Windows/physical-device capture acceptance untested until observed.
