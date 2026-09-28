# SPINA implementation, configuration and acceptance state

## Post-merge checkpoint — 28 September 2026

PRs #449–#453 are merged at `07a66c9e8be33e5c3343446452e10d826b67e312`. [Exact-main CI](https://github.com/GILBIC/spina-lending-app/actions/runs/36410334480) passed all three required lanes. The [current all-20-priority inventory](https://github.com/GILBIC/spina-lending-app/issues/448#issuecomment-5872009447) supersedes the pre-merge status below and records remaining business, provider, configuration and acceptance requirements.

The clean exact-main evidence packet passed source, CI, internal Android package, synthetic backup/restore, scanner regression and their provenance checks. It remains blocked on owner signing, performance evidence and human acceptance. A read-only live catalog check found the disclosure calculation table and both disclosure guard functions absent; HTTP health success does not establish schema compatibility or the active deployment revision. No production deployment, migration, real financial event or final-device acceptance was performed.

This follow-up strengthens the existing read-only deployment preflight to reject missing disclosure schema or missing, disabled or incorrectly bound disclosure triggers. Its own PR checks must pass; the earlier green main evidence is not evidence for later code. Before deploying, establish the actual migration/recovery procedure and authorized host context. The existing DigitalOcean workflow writes rendezvous files to its dispatch branch, so protected main cannot be used for those direct writes; the existing deployment-branch approach also needs matching broker authorization and host configuration. Do not bypass main protection or blindly redeploy through historical provisioning assumptions.

Create State returned an authentication error and requires reconnection. GitHub, the Notion gap review and Notion Current Project State carry the fresh handoff. The local current inventory is `checkpoints/SPINA-PRIORITIES-2026-09-28.md` in the Codex workspace. The earlier dated evidence below is retained as history.

## Historical pre-merge checkpoint

Checkpoint: 28 September 2026, Asia/Manila. This is the repository entry point for resuming current work. [Issue #296](https://github.com/GILBIC/spina-lending-app/issues/296) remains the frozen master roadmap. R1–R12 below are the separate [approved gap review](https://app.notion.com/p/3e35ade7bef48197be58f91c865a9d6f), coordinated in [issue #448](https://github.com/GILBIC/spina-lending-app/issues/448). Read the latest issue/PR checks before relying on a dated result.

Management requested completion and approved proceeding. Implement the smallest effective changes, preserve current work, and keep GitHub/Notion checkpoints current. A code/test result does not substitute for actual company facts, device acceptance, provider contracts, legal approval or financial events.

[PR #453](https://github.com/GILBIC/spina-lending-app/pull/453) is the combined integration candidate. It preserves the workstream histories below; its exact-head checks and latest issue #448 checkpoint govern merge readiness.

The prior candidate d8e63ca2 passed all three CI lanes and Annex A. An unresolved review then exposed a custody-only Collector renewal access gap. The [bounded Web/Android/server correction](../workstreams/2026-09-28-r3-collector-web-parity.md) preserves separate write permissions and assignment/device boundaries; 48 backend, 746 Web and 46 focused Android tests passed, with clean Android analysis and Web build. Protected automatic merge waits for the corrected head's checks and resolved review. Old green results and retained artifacts do not establish the new head's acceptance.

| Gap | Implementation evidence | Remaining acceptance/configuration |
|---|---|---|
| R1 Disclosure and accounting sources | [PR #449](https://github.com/GILBIC/spina-lending-app/pull/449): protected saved sources, approval/lifecycle/document binding and Web/Android source selection; [execution record](../workstreams/2026-09-28-r1-execution-state.md). | Combined-candidate CI and supported-platform acceptance; explicitly reviewed positive scheduled-component policy and supported accounting lifecycle; actual executable templates. Full R1 remains open. |
| R2 Renewal signed schedules | [PR #450](https://github.com/GILBIC/spina-lending-app/pull/450),20c3f0bc: authoritative registered installment totals and unavailable result when evidence is missing. All three CI lanes passed. | Combined integration and affected operational acceptance. |
| R3 Collector Web parity | Existing Combined/ADV/extra-principal, correction, other-area/remittance, renewal handover and promise APIs have Web integration at2897c235. Root spec review fixes and independent standards/security review completed; the final integrated portal744 tests/build passed. | Final combined-candidate CI and actual browser acceptance. |
| R4 GCash handoff/settlement | Web now exposes the escaped provider QR/payment code and exact copy/manual fallback at7963961d, matching the existing Android handoff; six focused tests passed. This is a code display, not an invented scannable format. | Actual accepted settlement authority/provider contract is missing; redirects/screenshots/client flags never prove settlement or authorize loan credit. |
| R5 CIF/liveness | Valid-CIF reuse and office fallback remain. | Actual verified provider evidence bound to the baseline and fresh remote session; boolean/timestamp claims alone are insufficient. |
| R6 Exact money | [PR #451](https://github.com/GILBIC/spina-lending-app/pull/451),834b5464 published and ready for review: Web 704 and Flutter 836 cases passed; GitHub platform analysis/tests/Android build passed. Decimal-string write/default paths and explicit unsafe-number limits implemented. | Combined-candidate checks and affected operational acceptance. No claim that ordinary microloan balances were wrong. |
| R7 Company/private files/staff | Existing account, employee/payroll, document and private-evidence workflows are reused. | Real owner/staff mapping, rates/schedules/contributions, privacy/DPO/provider facts, templates/fonts/converter, persistent files and credential/email delivery. No invented identities or settings. |
| R8 Android signing/upgrades | Release tooling already fails closed. | Owner-signed exact-source build and actual compatible in-place upgrade preserving session/device/cache/attendance. Reinstall is not this proof. |
| R9 Temporary photos | [PR #452](https://github.com/GILBIC/spina-lending-app/pull/452),01304b62 published with analyzer fixes: app-owned private copies/serialized cleanup; the combined focused checks now include both late cleanup-failure and preview/discard race cases. | Combined-candidate CI and device acceptance. Picker/gallery/user files are never deletion targets; physical plugin-cache erasure is not claimed. |
| R10 Repository/security | Main protection applied/read back: three trusted CI checks, strict/up-to-date PR flow, resolved conversations, admin enforcement, no force push/deletion. | Human approval count0 pending review ownership; retained security findings need actual classification/rotation ownership. Protection does not confer security clearance. |
| R11 Operational acceptance | Existing candidate and role/device matrices remain authoritative evidence owners. | One affected-platform trace through loan, documents, collection/correction/ADV, remittance, renewal and accounting; actual recovery/restore/monitoring and approved performance evidence. |
| R12 Current documentation | README and architecture entry points now lead here; old progress material remains archived. Stale PR420-draft guidance was removed from current onboarding workflow. | Keep this dated matrix and issue #448 current as code and acceptance advance. |

## Verification recorded at this checkpoint

- R1: 708 portal tests/build; 141 focused API/evidence/document checks, then 54 route checks; 755 fresh disposable PostgreSQL cases; 3 additional genuine deadlock/rollback/retry/replay cases. The workstream record preserves exact scope. Independent review of the Web source-selection change reported no actionable finding.
- R2: local database/Python/Flutter/Web checks and all three published CI lanes passed (run36368171965).
- Combined candidate: Web syntax checks for 117 modules, 744 tests and distribution build passed. Android analysis found no issues; 36 focused disclosure/repository/lifecycle/private-photo tests and the full 858-test Flutter suite passed, with one Windows-host symlink skip. Locked dependency resolution also passed. Published-head CI results belong in the live integration PR/issue checkpoint; Linux CI must exercise the symlink case.
- R3/R6/R9 local results are bounded evidence, not merged or deployed claims. Check current PR heads before using older green results. New commits invalidate assumptions about prior CI coverage. The preserved workstream branches are being combined into one integration candidate to avoid serial full-suite reruns under strict branch protection; no required check is bypassed.
- No live migration, company activation, actual loan/cash event, legal clearance or physical-device acceptance was performed by these changes. Preserve `automatic_source_posting=false`.

## Business and deferred work

[Issue #443](https://github.com/GILBIC/spina-lending-app/issues/443) tracks B1 legal registration, B2 accepted production candidate, B3 clean books, B4 actual funding, B5 first actual loan, C1 Management review and C2 first close. These require real evidence and cannot be closed by synthetic fixtures or a general approval message.

New Client Fund, renewal reserve and smart client capacity remain later ideas. Native iOS delivery and offline financial write queues remain outside this V1 scope. Do not build an additional ledger, provider adapter or policy engine without the corresponding approved contract.

## Resume and red/green reports

Read this matrix, the latest issue #448 checkpoint and Notion gap review; inspect worktree/branch status and current PR checks before editing. Continue the already approved scope without repeating a general permission round. Use the R label or PR/checkpoint with a short report such as “R2 red” or “PR #450 all green”; retain the original scope of user-reported device evidence. An unnamed green does not prove every release/business gate.

Local continuity is saved in `checkpoints/SPINA-STATE-2026-09-28.md` in the Codex workspace. Create State is unavailable in this session; no synchronization there is claimed. GitHub and Notion carry shared continuity.
