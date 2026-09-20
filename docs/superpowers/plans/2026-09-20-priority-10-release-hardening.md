# Priority 10: integration, production hardening and release candidate

## Authority and outcome

Management's frozen Priority 10 scope is recorded in Master #296 comments
5627859431 and 5628126560. The user instructed "next" after merging PR437 and
PR438 on 20 September 2026. This batch executes that existing scope. Main starts
at 16670142dccadd14f5bfb5651c33686eb336e228, whose source tree exactly equals the
fully tested employee head b71eb6b6. Native platforms remain Windows/Desktop and
Android, with shared role-based Web and the existing FastAPI/PostgreSQL backend.

Deliver one reviewable implementation batch and combined verification. Preserve
the frozen roadmap, financial rules, server authorization and explicit accounting
posting. Do not invent staff, legal, statutory, merchant, signing or secret values.
Do not deploy, migrate production, initiate provider payments, file registrations,
or tag v1.0 as part of preparing the candidate.

## Existing evidence and concrete defects

All three premerge CI jobs passed on the identical starting source tree. Existing
disposable tests replay migrations 0001 through 0128 and cover 538 onboarding,
privacy, lending and employee cases. Existing protected financial verifiers,
private-schema barriers and immutable document hashes remain authoritative.

The audit found shared deployment virtualenv state that defeats symlink rollback,
replacement of operator-only settings on redeploy, missing explicit writable-state
ownership, inconsistent generated Android application IDs, and a release build
that retains Flutter's debug signing default. Existing CI collects scanner reports
but does not reject added diagnostics. Current readiness checks only connectivity.

## Implementation and acceptance

1. **Recoverable deployment and operator configuration.** Build a release-specific
   runtime, preserve private operator configuration separately from generated
   runtime credentials, ensure service-user ownership, and restore the previous
   runtime/config/portal on a failed candidate health check. Validate shell syntax
   and meaningful configuration/rollback behavior without touching a real host.
2. **Consistent, verifiable Android packaging.** Reuse one generated-host setup for
   CI and delivery, preserve the established CI application identity and SQLCipher
   rules, explicitly include network permission, record exact commit/build mode,
   and refuse a production-signed claim without actual non-debug signing evidence.
   Missing owner signing inputs must produce a clear block, not a fake release.
3. **Backup and restore proof.** Use only generated loopback databases and synthetic
   private evidence in an isolated drill. Replay the current schema, retain database
   and evidence hashes, restore into a second fresh database, verify representative
   linked records and file integrity, and clean up all task-owned resources. Never
   use a production DSN or delete a database that was not created by the drill.
4. **Readiness, observability and release evidence.** Add a sanitized read-only
   deployment preflight and safe request correlation. Produce one exact-commit
   candidate evidence record that distinguishes passed automated checks, pending
   external acceptance and activation inputs. Reuse existing verification commands;
   reject missing/stale evidence instead of marking the candidate release-ready.
5. **Security regression and realistic verification.** Compare exact normalized
   scanner findings against the starting baseline; do not waive existing findings
   or equate unchanged reports with security clearance. Record realistic isolated
   performance observations and the Desktop/Web/Android role acceptance matrix.
   Reuse unified CI and add focused checks within it rather than duplicate CI.
6. **Combined delivery and continuity.** Review independent changes together, run
   focused regressions followed by the appropriate complete suites/builds, and
   publish one draft PR. Update GitHub, Notion and local handoff with exact evidence
   and remaining external gates. Separate code completion from v1.0 acceptance.

## External gates and follow-through

Real Android/Windows acceptance, production-signed Android credentials, actual
host/secret/alert ownership and rotation, reviewed security findings, verified
staff/payroll/legal/privacy facts, and actual production restore/monitoring
acceptance cannot be manufactured by code. Main protection is an outstanding
repository-governance requirement and must be recorded with its actual state.

Management prefers GCash automation without an intermediary. Existing intent and
capability boundaries remain; notifications are feasibility evidence only, and
no authoritative direct-provider contract or live enablement is established.
Keep unsupported settlement/posting disabled and list that dependency explicitly.
No invented webhook, generic success redirect, screenshot or notification may
become an official repayment.

## Verification discipline

Use meaningful failing regressions for the identified defects before fixing them.
Workers own disjoint files and focused checks; the coordinator owns combined
checks. Current approved tools include Ruff 0.16.8, Pyright 1.1.414 and Bandit
1.9.4. Root the Python path in this worktree, not another editable checkout.
Historical premerge evidence is not a pass for newly modified source. Do not
repeat completed full suites unless a subsequent change or failure justifies it.
