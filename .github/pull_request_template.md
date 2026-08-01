## Purpose

<!-- What problem or milestone does this pull request address? -->

## Scope

<!-- List the focused components and user-visible behavior changed. -->

## Architecture impact

- [ ] I identified the owning component in `docs/architecture/system-map.md`.
- [ ] I documented any changed API, data flow, database owner, or security boundary.
- [ ] I updated `docs/architecture/progress-map.md` when a milestone status changed.
- [ ] I updated `docs/architecture/debugging-playbook.md` when the recommended trace path or identifiers changed.
- [ ] I regenerated the static Desktop architecture map when Python ownership/dependencies changed.
- [ ] No architecture document change is required; the reason is explained below.

**Authoritative record or service:**

<!-- Example: lending.loan_collection_state through FastAPI, SPINA Desktop calculation service, core.devices. -->

**Identifiers used to trace this flow:**

<!-- Example: user ID, device record, client/loan ID, route revision, idempotency UUID, receipt. Never include secrets. -->

## Safety boundaries

- [ ] No password, bearer/refresh token, database URL, Supabase secret, or raw installation ID is committed or logged.
- [ ] Financial and 7x7 rules remain server/desktop authoritative, not presentation-calculated.
- [ ] Write operations are atomic or have a documented rollback/recovery path.
- [ ] Offline, duplicate, retry, stale-state, revoked-device, and permission behavior are addressed when applicable.
- [ ] Destructive manual testing uses disposable or explicitly approved data.

## Validation

<!-- Include exact commands, tests, workflow/run IDs, and results. -->

- [ ] Compilation/static analysis
- [ ] Focused unit/integration/widget tests
- [ ] Neighboring compatibility/regression tests
- [ ] Migration and rollback validation, when applicable
- [ ] Exact-head CI
- [ ] Safe manual verification
- [ ] Clean committed tree

## User impact and debugging

<!-- What will the user see? What safe message/code/receipt/trace ID will help support diagnose a failure? -->

## Remaining work or blockers

<!-- State what is deliberately not enabled, especially 7x7 mobile writes, offline collection sync, migrations, or external portal work. -->
