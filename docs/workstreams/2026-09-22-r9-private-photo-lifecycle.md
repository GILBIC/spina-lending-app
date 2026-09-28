# Gap R9 - App-owned temporary-photo lifecycle

## Status and authority

Implementation checkpoint, 28 September 2026, following Management's approval of the first four Draft PR tracks in [audit #448](https://github.com/GILBIC/spina-lending-app/issues/448#issuecomment-5770984236) and subsequent instruction to complete the priorities efficiently. Synthetic-file tests establish the scoped private-copy behavior below. Actual Android lifecycle acceptance and plugin-cache erasure remain unverified.

Starting main: `6a33ab481574bf702920760610f803b59ffbd3ac`.
Starting tree: `1c88730791d89e2798faef0f5e76fd2a5f081543`.
Branch: `gap/r9-private-photo-lifecycle`. Coordination index: #448.
R9 is an audit identifier, not frozen Master #296 priority 9.

## Outcome and source boundary

Define a safe, bounded lifecycle for temporary evidence images owned by Spina. Preserve accepted Android picker/camera recovery while removing eligible app-owned copies only after their use/retry/recovery obligation has ended.

`gilbic_mobile/lib/src/core/media/image_recovery_controller.dart` coordinates the plugin's destructive lost-data slot. Its private-store integration now copies recovered images into app-owned storage and removes eligible owned copies. `docs/mobile/android-photo-recovery.md` distinguishes this from erasing plugin-cache images or user-owned files. PR #447's recovery work is preserved and is not generalized into automatic financial retry.

A path returned by a picker, user-visible filename or cleared metadata record alone is not sufficient proof of safe deletion ownership. The implementation design must establish actual storage ownership and asynchronous use before choosing a cleanup mechanism.

## Ownership and dependencies

Own the narrow mobile media/recovery storage lifecycle, associated shared recovery UI hooks and focused tests. Candidate existing integration boundaries include `gilbic_mobile/lib/src/features/shared/image_recovery_scope.dart` and the supported proof/handover/office-evidence callers identified in the recovery documentation.

R6 / PR #451 owns staff money models/serializers; R2 / PR #450 owns backend renewal-summary authority; R1 / PR #449 owns tax/document source binding. Do not modify their rules or APIs. Coordinate changes to shared form files before editing. No backend deletion policy, retention of finalized legal evidence, new native iOS work, schema migration, signing change or broad cache wipe belongs to this initial scope.

## Implemented boundary

Existing proof, Collector handover and Office evidence callers read image bytes before network submission. This change leaves those form and request contracts intact. A recovered image is copied into `getApplicationSupportDirectory()/spina_recovered_images_v1/pick_*/photo`; its ownership marker preserves filename and MIME metadata. The secure journal records the private path. The store validates direct child ownership markers and real directory/file types, skips links and unknown entries, and never recursively deletes.

The private store serializes retain, preview/consumption reads and cleanup. Explicit acceptance detaches bytes into an `XFile.fromData` before journal invalidation and disk removal, so current form memory retains data for explicit submission/retry. Failed journal invalidation leaves the copy intact. Discard, logout/account/authorization changes, and the existing 24-hour expiry remove eligible private copies. Startup cleans eligible orphans while keeping the current journaled selection. Failed deletion remains visible and retryable at the next recovery initialization. No new retention period, background service, form upload policy or financial retry is introduced.

## Acceptance checklist

- [x] Settle actual ownership, lifecycle and the scoped design before adding deletion.
- [x] Preserve images needed by an active picker, recovered draft, uncertain upload or explicit same-request retry.
- [x] Define completion/discard/logout/expiry behavior without mixing accounts or confusing metadata invalidation with file removal.
- [x] Restrict deletion to recognized private copies; synthetic malformed/outside-root tests pass. Symlink test awaits a host permitting symbolic links.
- [x] Serialize cleanup with selection/recovery/consumption and report failed deletion honestly; physical acceptance is separate.
- [x] Retain late-result, second-restart, expiry and cross-account recovery regressions; no auto upload or restored witness/cash confirmation.
- [ ] Verify focused tests, required exact-head CI and an isolated actual Android lifecycle test separately.

## Verification checkpoint

- `flutter test --no-pub test/image_recovery_controller_test.dart test/image_recovery_scope_test.dart test/image_recovery_host_test.dart test/collector_image_recovery_test.dart test/office_capture_test.dart`: **58 passed**.
- `flutter test --no-pub test/private_image_store_test.dart test/private_image_recovery_test.dart`: **12 passed, 1 skipped** before the final two edge-case tests were added. Windows disallowed the synthetic symbolic link; this is not a passing symlink-erasure result.
- Superseding combined checkpoint, 28 September: deletion-failure/retry and preview/discard overlap tests passed within the 36 focused office/private-photo tests; the full Flutter suite passed 858 tests with one Windows-host symlink skip. Formatting and Android analysis passed with no issues. Locked dependency resolution passed; the existing locked `path_provider` 2.1.6 was promoted from transitive to direct without a version or checksum change. Earlier interrupted SDK approval waits no longer block local verification.
- Required CI must validate the final commit and enforce the lockfile. Actual isolated Android restart/cleanup acceptance remains open. No installed business-app files, production records, device state, merge or deployment were changed by this work.

## Resume protocol

Read this PR, #448, latest Notion audit/checkpoint and Create State. Use an isolated branch checkout and synthetic test resources only. Record exact head, owned paths, dependencies, measured test/device evidence and next step. Red/Green refers to the explicitly named checkpoint; CI is not physical file-erasure evidence or merge permission.
