# Priority 10 candidate acceptance

`tools/build_release_candidate_evidence.py` joins the existing CI, Android,
recovery, scanner and performance evidence for one exact candidate. It checks
local evidence consistency and content hashes. It does not rerun those tests,
authenticate downloaded GitHub JSON, verify a person's review, approve production,
deploy, tag a release or decide that an existing security finding is acceptable.

The output distinguishes machine records from **declared human acceptance**.
Even a complete packet is only `READY_FOR_MANAGEMENT_REVIEW`; `production_ready`
always remains `false`. Missing, stale, partial or malformed supporting files
produce `BLOCKED` with specific gates and exit code2. A complete packet returns0.
Keep raw evidence and the output outside the source checkout. The checkout must
be clean and its HEAD must equal the requested full40-character SHA.

## Assemble the finite input packet

Copy this JSON outside the repository, replace the paths with actual retained
evidence and set `template_only` to `false`. Relative paths resolve against the
input file's directory. An omitted or null path remains a visible blocked gate;
it is not interpreted as a passed check.

```json
{
  "schema_version": 1,
  "template_only": true,
  "ci_run": null,
  "ci_artifacts": null,
  "android_report": null,
  "android_apk": null,
  "recovery_report": null,
  "scanner_report": null,
  "scanner_reports_dir": null,
  "performance_report": null,
  "bindings": null,
  "attestations": null
}
```

```text
python tools/build_release_candidate_evidence.py --expected-sha <full-candidate-SHA> --inputs <candidate-inputs.json> --output <candidate-report.json> --repository <clean-checkout>
```

| Input | Required retained evidence |
| --- | --- |
| `ci_run` | Unedited `gh run view <run-id> --json headSha,status,conclusion,jobs,url,databaseId,workflowName` output for SPINA CI. All three exact job names—Backend, quality, and security; Portal, Flutter, and Android; Financial and disposable PostgreSQL—must have completed successfully. |
| `ci_artifacts` | Raw `gh api repos/GILBIC/spina-lending-app/actions/runs/<run-id>/artifacts` response. Require nonexpired, nonempty `spina-ci-backend-<SHA>`, `Spina-Android-internal-<SHA>` and `spina-ci-financial-<SHA>` records from that same run/source. |
| `android_report`, `android_apk` | Actual `verify_android_artifact.py` output and the exact APK it verified. The collector rehashes APK bytes and compares embedded source, mode, package, endpoint, version, dependency-lock and expected-certificate provenance. It also requires manifest/Dex/Flutter/SQLCipher contents. Cryptographic signature verification remains owned by the Android verifier. A debug package is useful internal evidence but leaves production signing blocked. |
| `recovery_report` | `run_release_recovery_drill.py` result; CI retains it as `ci-artifacts/financial/recovery.json`. Require the complete current migration list/hashes, nonempty database/private-file backup hashes, restored schema/table/relationship evidence, rejected corruption probes and successful cleanup. Windows source bytes or the candidate's Git LF blobs may match migration hashes; neither is silently substituted in the original record. This proves a synthetic isolated drill, not a production restore. |
| `scanner_report`, `scanner_reports_dir` | Actual scanner comparison plus all six raw reports from `check_release_scanner_regressions.py`. The collector recomputes normalized comparison against the candidate's retained baseline. A copied `status: passed` cannot replace missing scanner data. Existing findings still require separate security review. |
| `performance_report` | Actual `run_release_performance_probe.py` result with representative synthetic counts; health, all four role read surfaces and an explicit Employee-to-Management denial; consistent actual request/status/error/latency measurements; and explicit met latency/zero-error budgets. Health-only or unchecked-budget measurements remain partial evidence. The human performance review separately establishes backend revision and deployment-like environment; the probe does not establish them. |

Fetch records from the authenticated GitHub account at acceptance time. The
collector records `remote_records_revalidated: false` because it cannot establish
the authenticity or freshness of manually copied API responses. Review their
original run/artifact references; hashes alone are not independent execution proof.

## Preserve original execution provenance

The separate bindings file has exactly these report keys. Each value records
the hash of the original output bytes, the original execution commit and tree,
an aware ISO8601 capture time, and a durable HTTPS capture reference. Populate
these from actual CI/capture evidence, never infer an earlier run's source from
the current checkout or fabricate a capture record to obtain a green result.

```json
{
  "recovery_report": {
    "report_sha256": "<actual-report-file-SHA256>",
    "source_sha": "<original-execution-commit>",
    "source_tree": "<original-execution-Git-tree>",
    "captured_at": "<actual-aware-ISO8601-time>",
    "capture_ref": "<actual-HTTPS-run-or-capture-record>"
  },
  "scanner_report": null,
  "performance_report": null
}
```

Use the same value shape for all three reports. An older commit is acceptable
only if Git proves its **entire tree** equals the final candidate tree. The report
keeps the original record/hash; it does not rewrite that execution as having run
on the newer commit. Performance's own `source_commit` must match its binding and
`source_tree_dirty` must be false. A dirty precommit drill without captured matching
Git-tree provenance remains supporting history, not exact-candidate acceptance.

The collector also hashes the inputs, reports, actual APK, scanner baseline and
every raw scanner file. Public output includes hashes and fixed gate names;
it excludes local file paths, raw response bodies, arbitrary source fields,
employee names, tokens, account/device identifiers and private payroll data.

## Human acceptance is a separate record

Start with this deliberately pending attestations file:

```json
{
  "android_device": {"outcome": "pending"},
  "windows_desktop": {"outcome": "pending"},
  "web_roles": {"outcome": "pending"},
  "security_review": {"outcome": "pending"},
  "repository_governance": {"outcome": "pending"},
  "operational_setup": {"outcome": "pending"},
  "performance_acceptance": {"outcome": "pending"}
}
```

An accepted entry requires `outcome: accepted`, the exact `source_sha`, actual
aware `reviewed_at`, an actual HTTPS `review_ref` (an issue/comment anchor is
allowed; credentials/query tokens are not), and `evidence_sha256` mapping exactly
the supporting input keys below to the current files' SHA256 values. No reviewer
name, staff identifier or private facts belong in this public packet. Preserve
the substantive review in its properly restricted owning record.

| Gate | Required supporting hashes | Review scope |
| --- | --- | --- |
| `android_device` | `android_report`, `android_apk`, `ci_run` | Exact package install/upgrade/signing lineage; online/offline attendance, restart/reconnect exactly once, account switch/revocation, SQLCipher persistence, camera/gallery, private save dialog and background/resume. |
| `windows_desktop` | `ci_run` | Correct candidate portal in Edge/Chrome app mode; install/launch, print/download/file selection and safe uninstall. |
| `web_roles` | `ci_run` | Management, Collector, Employee and Client at desktop/narrow widths; authorized navigation, denied actions, logout/privacy, authoritative refresh after uncertain outcomes, cross-role lending/collection/employee workflow visibility. |
| `security_review` | `scanner_report`, `ci_run` | Review retained findings and dependencies, private-data access boundaries and actual secret/alert/rotation ownership. An unchanged baseline is not security clearance. |
| `repository_governance` | `ci_run` | Actual branch/rules protection, required review/check settings and access ownership. A proposed setting is not an enabled rule. |
| `operational_setup` | `recovery_report` | Actual private staff/payroll/legal/privacy/provider facts and production backup/restore/rollback/monitoring acceptance. The synthetic drill does not settle these facts. |
| `performance_acceptance` | `performance_report` | Representative fixture/host/network/database shape, approved latency/error budget and actual backend code. Also require `backend_source_sha` equal to the candidate and `environment_class: isolated_production_like`, only when actually reviewed. |

These entries are explicitly **declarations**, not independently established test
results. A bare `passed: true`, unsupported acceptance, missing review reference,
another source SHA or a changed supporting file cannot close a gate. Management
must inspect the underlying records before giving a separate final release
decision. No human acceptance or operational value is created by this tool.

Native iOS remains outside this priority. GCash notifications, screenshots and
redirects remain non-authoritative payment evidence; this release packet does not
enable payment-provider settlement or automatic borrower balance reductions.
