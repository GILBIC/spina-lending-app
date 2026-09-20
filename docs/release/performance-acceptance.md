# Isolated read performance measurements

`tools/run_release_performance_probe.py` measures a finite set of read requests
against an explicitly authorized local synthetic backend. It does not seed data,
log in, create accounts, write financial records, migrate a database, deploy,
benchmark a public service or declare production acceptance.

The tool requires `--allow-disposable` and an explicit loopback IP origin such as
`http://127.0.0.1:8000` or `http://[::1]:8000`. It rejects DNS names including
`localhost`, wildcard addresses, non-loopback IPs, credential-bearing URLs,
paths, query strings and fragments. Proxy environment variables are ignored;
redirects are recorded as errors and never followed. HTTPS certificate checks
remain enabled. A loopback address alone does not prove that the backend uses a
disposable database: the operator must verify that backend configuration before
running the probe.

## Prepare a real synthetic fixture

1. Start an isolated backend using the intended candidate code and a disposable
   database with representative synthetic records. Record its exact revision,
   database fixture identity and runtime configuration separately from credentials.
   The probe does not change or start that backend.
2. Copy [the scenario template](performance-scenarios.example.json) outside the
   repository. Set its workload counts to the actual seeded clients, active loans,
   route entries, collectors and employees. Use an innocuous fixture identifier
   without names, account numbers or secrets. Set `template_only` to `false` only
   after that fixture exists. The supplied template is deliberately rejected and
   is never recorded as a passed measurement.
3. Supply actual synthetic role tokens and registered device identifiers through
   an explicit private JSON file. The account labels are `client`, `collector`,
   `employee`, `management` and optionally `revoked`. Each selected label maps to
   an object with `token` and `device_id` fields. The tool does not read tokens from
   command arguments or environment variables, and never records either value.
   On POSIX the file must deny group/other access, for example mode `0600`.
   On Windows provision a private user-only ACL; POSIX permission checks do not
   establish Windows ACL privacy. Keep this file outside the repository and do
   not attach it to CI, Notion, issues or release evidence.
4. Use a true Employee-only fixture for the `employee_management_denied` scenario.
   Do not use an account that also legitimately holds Management permissions and
   then treat an expected denial as authoritative. A revoked-device check can use
   `/api/v1/auth/me` with a valid synthetic token and a revoked device, expecting
   `403`. Each scenario's expected status is explicit; no authorization result is
   inferred from its account label.

The allowlisted GET paths are existing server routes:

| Read | Implementation |
| --- | --- |
| `/health/live`, `/health/ready` | `gilbic_backend/main.py` |
| `/api/v1/auth/me` | `gilbic_backend/auth_api.py` |
| `/api/v1/client/loans` | `gilbic_backend/client_loan_api.py` |
| `/api/v1/collector/cash-accountability` | `gilbic_backend/collector_cash_accountability_api.py` |
| `/api/v1/employee-operations/workspace` | `gilbic_backend/employee_operations_api.py` |
| `/api/v1/management/dashboard-overview` | `gilbic_backend/management_dashboard_overview_api.py` |

Paths are exact; arbitrary URLs, query parameters, request bodies, methods and
additional fields are rejected. Health requests never receive credentials. These
routes measure real read surfaces without exercising application, payment,
release, remittance, payroll or accounting mutation commands.

These are business reads, not a promise of zero database writes: normal server
authentication updates the synthetic device's `last_seen_at` through
`account_repository.get_context_for_device`. The result records this boundary
explicitly. Use the real authentication path for authenticated measurements;
replacing it with a fake adapter does not establish production Auth performance.
`/api/v1/collector/routes/today` is deliberately excluded because it can finalize
elapsed loan schedule adjustments despite using GET. No such financial side
effect belongs in this probe.

## Run one bounded measurement

With the chosen Python environment, substitute private local file paths and the
actual isolated backend port:

```text
python tools/run_release_performance_probe.py --base-url http://127.0.0.1:8000 --allow-disposable --scenarios <completed-synthetic-scenarios.json> --token-file <private-role-tokens.json> --requests 10 --concurrency 3 --timeout-seconds 3 --output <performance-result.json>
```

There are no hidden warm-up requests. The configured count applies to each
scenario, and workers share one bounded HTTP connection pool. Limits are one to
eight scenarios, one to 100 requests per scenario, at most 300 requests total,
one to eight concurrent requests, and a whole-request timeout greater than zero
and at most ten seconds. The deadline includes headers and streamed response
consumption, including trickling responses. Response bodies are discarded after
consumption; a response exceeding four MiB is recorded as an error. These limits
bound the experiment and are not approved business service-level objectives.

Optional `--max-p95-ms` and `--max-error-rate` apply explicit operator-supplied
limits to each scenario. Without those arguments the threshold assessment is
`not_evaluated`. Do not invent approved thresholds merely to turn a measurement
green. Exit code `0` means the requested statuses were observed and any supplied
thresholds were met; `1` means request errors or exceeded thresholds; `2` means
the input/source/output requirements prevented a completed run.

## Read and retain the evidence

The JSON result records fixed paths, expected statuses, actual status counts,
error-category counts, nearest-rank p50/p95/max latency, concurrency, deadlines,
elapsed time and declared synthetic workload counts. It contains no response
bodies, request headers, device identifiers, tokens or raw transport exceptions.
An explicitly expected `403` is a successful denial measurement. A timed-out
response can have a received `200` header while still counting as an error; status
counts alone are not the outcome.

`source_commit` and `source_tree_dirty` identify the probe's local checkout.
`backend_revision_verified` is always false because the tool cannot establish the
running backend's revision from these read endpoints. The operator must bind the
server process/build to the candidate independently. Do not attach an earlier
checkout's measurement to a later candidate as fresh proof.

All results explicitly remain `measurement_only: true` and
`production_acceptance: false`, including runs that meet supplied limits. Review
representativeness of fixture size/distribution, role permissions, database
indexes, network/device conditions and the actual deployment resources before
accepting a production objective. Windows and Android device interaction, public
TLS/Auth/network latency, mutations and financial concurrency require their own
existing acceptance evidence. A health-only or mocked HTTP test must not be
described as completed role-flow performance testing.

`tests/test_release_performance_probe.py` proves tool behavior with a real local
HTTP server, concurrent request counting, expected/failed statuses, blocked
redirects, trickling-body deadlines, body-size limits and private-file redaction.
Those tests validate the probe; they do not measure Spina business performance.
