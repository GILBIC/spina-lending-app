# Runtime preflight and request correlation

Run `python -m gilbic_backend.release_preflight --profile runtime` with the same
private environment as the intended service account. The command returns a
sanitized JSON report and a nonzero exit code on failure. It checks production
configuration, explicit PostgreSQL TLS, HTTPS Auth/CORS origins, disabled
unsupported GCash settlement, required schema and private-table grants. Database
checks use a read-only transaction and bounded connection/statement timeouts.
It does not run migrations or create staff, accounts, files or payments.

The deployment service runs this profile before starting a candidate. A failed
runtime check participates in rollback. `/health/live` and `/health/ready` retain
their existing contracts; readiness connectivity alone is not release approval.

`--profile activation` additionally checks configured evidence storage, privacy
and document bundles, conversion/email configuration, and the configured active
owner account/device/role. This is a configuration probe only:
`activation_proven` stays false. It cannot establish legal approval, deliver an
email, prove a backup, validate physical devices or approve live financial work.
Keep its private inputs outside the source tree and public evidence.

Every HTTP request receives a server-generated `X-Request-ID`. The `gilbic.request`
logger records that ID, a fixed method/route template, response status, elapsed
milliseconds and whether processing completed. It never records raw paths,
queries, request bodies, authorization/device headers or exception contents.
Unknown routes use `unmatched`; uncaught errors keep a generic 500 response with
the same ID. CORS exposes the ID on normally handled responses.

The deployment disables Uvicorn access logs and enables this request logger.
This does not sanitize all third-party/application error logging: restrict server
logs to operators, review error-log privacy and retention, and use request IDs
instead of copying private payloads into public issues. Configure and test an
actual alert recipient, health/5xx thresholds and recovery escalation before
production acceptance; logging alone does not prove monitoring coverage.
