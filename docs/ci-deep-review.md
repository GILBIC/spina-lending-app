# SPINA CI Deep Review

SPINA keeps exactly five automatic validation lanes:

1. Core
2. Financial & Database
3. Code Quality
4. Security & Compliance
5. Reliability & Performance

GitHub Actions artifacts remain useful when storage is available, but they are not required for detailed review. The self-hosted Windows runner now keeps review reports under:

`C:\SPINA_CI_REPORTS\<exact-head-sha>\<lane>\`

The report-producing lanes persist their raw scanner/test output locally after every run:

- `code-quality`: Ruff JSON, Ruff format output, Pyright JSON, coverage XML/JSON, summary
- `security-compliance`: Bandit JSON, pip-audit JSON, summary
- `reliability-performance`: focused pytest output with slowest-test timings

Only the latest 50 exact commit directories are retained by default.

## Review behavior

Each report-producing automatic lane renders a review-safe detailed report into its normal GitHub Actions job log. That means a reviewer can inspect exact Ruff/Pyright diagnostics, coverage gaps, Bandit findings, dependency vulnerabilities, concurrency/idempotency tests, and timing data even when GitHub artifact storage is full.

`SPINA CI Deep Review (manual)` is a separate manual-only workflow. It can re-render any locally retained exact commit report without rerunning the validators. Leaving `commit_sha` blank uses the newest saved local report.

The manual Deep Review workflow is not a sixth automatic CI lane.

## Secret handling

Gitleaks remains part of Security & Compliance, but raw detected secret values are deliberately not copied into `C:\SPINA_CI_REPORTS` and are never replayed by Deep Review. Review the redacted Gitleaks result in the Security & Compliance job log/summary.

## Safety

Local report persistence and Deep Review are diagnostic only. They do not connect to a protected/live SPINA database, apply migrations, restart a backend, deploy an application, or alter lending/accounting records.
