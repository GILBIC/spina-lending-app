# Gap R9 - App-owned temporary-photo lifecycle

## Status and authority

Workstream setup only, 22 September 2026, following Management's approval of the first four Draft PR tracks in [audit #448](https://github.com/GILBIC/spina-lending-app/issues/448#issuecomment-5770984236). This brief does not implement deletion or establish that any stored photograph has been removed.

Starting main: `6a33ab481574bf702920760610f803b59ffbd3ac`.
Starting tree: `1c88730791d89e2798faef0f5e76fd2a5f081543`.
Branch: `gap/r9-private-photo-lifecycle`. Coordination index: #448.
R9 is an audit identifier, not frozen Master #296 priority 9.

## Outcome and source boundary

Define a safe, bounded lifecycle for temporary evidence images owned by Spina. Preserve accepted Android picker/camera recovery while removing eligible app-owned copies only after their use/retry/recovery obligation has ended.

`gilbic_mobile/lib/src/core/media/image_recovery_controller.dart` coordinates the plugin's destructive lost-data slot and currently explicitly does not delete files. `docs/mobile/android-photo-recovery.md` distinguishes clearing encrypted recovery metadata from erasing plugin-cache images or user-owned files. PR #447's recovery work must not be relabeled as a missing feature or generalized into automatic financial retry.

A path returned by a picker, user-visible filename or cleared metadata record alone is not sufficient proof of safe deletion ownership. The implementation design must establish actual storage ownership and asynchronous use before choosing a cleanup mechanism.

## Ownership and dependencies

Own the narrow mobile media/recovery storage lifecycle, associated shared recovery UI hooks and focused tests. Candidate existing integration boundaries include `gilbic_mobile/lib/src/features/shared/image_recovery_scope.dart` and the supported proof/handover/office-evidence callers identified in the recovery documentation.

R6 / PR #451 owns staff money models/serializers; R2 / PR #450 owns backend renewal-summary authority; R1 / PR #449 owns tax/document source binding. Do not modify their rules or APIs. Coordinate changes to shared form files before editing. No backend deletion policy, retention of finalized legal evidence, new native iOS work, schema migration, signing change or broad cache wipe belongs to this initial scope.

## Next work

Trace where selected/recovered image bytes live and when each consumer finishes reading them. Present the smallest ownership-aware cleanup design, then test it using synthetic task-owned files and injected storage operations. Do not run cleanup experiments against the installed business app or real evidence. Preserve the existing 24-hour recovery metadata contract; choose no new business evidence-retention period in this brief.

## Acceptance checklist

- [ ] Settle actual ownership, lifecycle and the scoped design before adding deletion.
- [ ] Preserve images needed by an active picker, recovered draft, uncertain upload or explicit same-request retry.
- [ ] Define completion/discard/logout/expiry behavior without mixing accounts or confusing metadata invalidation with file removal.
- [ ] Never delete gallery originals, user-saved downloads, finalized server evidence or unowned paths; test malformed/outside-root paths and symlink/ownership boundaries where applicable.
- [ ] Serialize cleanup with selection/recovery/consumption and handle interrupted or failed deletion honestly; do not claim physical erasure from a metadata result.
- [ ] Retain late-result, second-restart, expiry and cross-account recovery regressions; no auto upload or restored witness/cash confirmation.
- [ ] Verify focused tests, required exact-head CI and an isolated actual Android lifecycle test separately.

No R9 test, cleanup implementation or physical cleanup has been performed at setup. No real files, device data, production records, merge or deployment are changed or authorized.

## Resume protocol

Read this PR, #448, latest Notion audit/checkpoint and Create State. Use an isolated branch checkout and synthetic test resources only. Record exact head, owned paths, dependencies, measured test/device evidence and next step. Red/Green refers to the explicitly named checkpoint; CI is not physical file-erasure evidence or merge permission.
