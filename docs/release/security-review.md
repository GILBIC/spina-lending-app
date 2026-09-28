# Release security evidence and unresolved review

CI compares six scanner reports with retained, normalized finding fingerprints:
Ruff 0.16.8, Pyright 1.1.414, Bandit 1.9.4, Gitleaks 8.30.1, dependency audit and
formatting. New findings and report/runtime failures block CI. Removed findings
are allowed; an equal total cannot hide replacements. Unexpected dependency
audit skips fail, with only the two known editable project packages exempted.
Never regenerate the baseline merely to make a failed check pass.

The baseline records CI 35471568447 at employee head b71eb6b6, integrated without
source changes into main 16670142. Counts are Ruff 2193, Pyright 798, Bandit 101,
Gitleaks 19, formatting 498 and two duplicate entries for one pytest advisory.
Fingerprints do not contain secret values. Existing findings remain review debt;
`security_clearance` is always false in the regression report.

The test extras now pin pytest 9.0.3, which fixes CVE-2025-71176 according to the
[official pytest changelog](https://docs.pytest.org/en/stable/changelog.html#pytest-9-0-3-2026-04-07).
The next candidate dependency audit must confirm the installed environment.

Initial classification of the retained Bandit report found 78 dynamic-SQL
warnings, 19 assertions, two subprocess uses, one XML-escape import warning and
one enum named PASS. This classification is not a waiver. Review each SQL
construction against parameter binding/identifier composition and each process
boundary against trusted executable/input handling, recording dispositions for
the exact candidate. Server role/device checks, private-schema grants and
financial authorization require their existing real-database regressions too.

The 19 redacted historical Gitleaks fingerprints still need owner classification
and rotation where they correspond to real credentials. Keep any secret values
and rotation evidence private; reference only sanitized evidence identifiers.
Do not rewrite Git history or mark all findings false positives automatically.

Before release acceptance, also record actual main-branch protection, independent
review, deployment/secret ownership, private evidence access/retention, and alert
delivery. At the starting checkpoint the repository reported no active main
rules or classic protection. A green CI run does not establish those controls.

On 28 September 2026, main protection was applied and read back: the three named
SPINA CI checks must come from GitHub Actions, the branch must be up to date,
pull-request conversations must be resolved, administrators are included, and
force pushes/deletion are disabled. Required human approvals remain zero until
actual independent review ownership is supplied. This closes the missing
branch-protection setting, not the retained findings, rotation, deployment,
private-file or alert-delivery evidence. See the
[current implementation state](2026-09-28-implementation-state.md) and
[recorded governance checkpoint](https://github.com/GILBIC/spina-lending-app/issues/448#issuecomment-5862043042).
