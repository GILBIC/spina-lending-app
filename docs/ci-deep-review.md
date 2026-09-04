# SPINA CI review guide

SPINA broad validation is owned by one workflow: `.github/workflows/spina-ci.yml`.
It runs on pull requests, pushes to `main`, and manual dispatches using three
GitHub-hosted Ubuntu lanes.

## 1. Backend, quality, and security

The `backend` job:

- compiles the desktop and backend Python sources;
- runs Ruff lint and format, Pyright, Bandit, pip-audit, and pinned Gitleaks;
- treats existing lint, typing, vulnerability, and secret findings as measured
  baselines while scanner/runtime failures remain blocking; and
- runs the Python suite once with coverage and slowest-test reporting.

Detailed redacted reports are uploaded as the `spina-ci-backend-<sha>` artifact
for 14 days. CI no longer depends on the self-hosted
`C:\SPINA_CI_REPORTS` directory.

## 2. Portal, Flutter, and Android

The `client-apps` job:

- tests the portal modules;
- builds and checks the public portal output for backend-secret patterns;
- runs Flutter package resolution, analysis, and tests; and
- creates and verifies one generated-host Android debug APK with arm64 and x64
  runtime coverage.

The internal review APK is uploaded for seven days. The generated Android host
lives under the runner temporary directory and never modifies the committed
Flutter application tree.

## 3. Financial and disposable PostgreSQL

The `financial-database` job starts a PostgreSQL 17 service bound to loopback,
creates an isolated database for each consolidated validator, and runs the
existing 7x7, collection/renewal, delegated-area, capital, period-close,
remittance, tax, and private-schema controls.

This automatic workflow never reads a protected database URL, repository
secret containing a database URL, or a workstation `.env` file.

## Protected operations

Live database maintenance remains separate in
`.github/workflows/spina-protected-maintenance.yml`. It is manual-only and
requires all of:

- an explicit operation selection;
- explicit protected-live-database confirmation;
- the exact `main` branch;
- the approved `SPINA-WINDOWS` runner; and
- a committed one-time marker for legacy Stage 5E operations.

Production deployment remains in the DigitalOcean deployment workflow and is
not part of CI.

## Pull-request review

A pull request is ready for merge only when the exact head has successful
`backend`, `client-apps`, and `financial-database` jobs. Review the job summary
and the uploaded backend reports before approving a change that affects
security, financial calculations, database migrations, authentication, or
collection posting.
