# Gilbic payment contract implementation checklist

The FastAPI backend is ready for Gilbic payment writes only when every item below is verified.

- [ ] Authenticated collector identity is derived from the session.
- [ ] `collection.create` permission is checked server-side.
- [ ] The device is registered and assigned to the collector.
- [ ] `Idempotency-Key`, `X-Client-Transaction-Id`, and body `client_transaction_id` must match.
- [ ] A unique PostgreSQL constraint protects the idempotency key.
- [ ] A canonical request hash detects changed payload reuse.
- [ ] Same key and same payload returns the original transaction and receipt.
- [ ] Same key and different payload returns `409 idempotency_mismatch`.
- [ ] Route entry, route revision, collector assignment, loan, and collection date are validated.
- [ ] Closed-day and closed-route checks are enforced.
- [ ] Payment, ADV, and PASS rules use existing SPINA server logic.
- [ ] Official balance is calculated on the server.
- [ ] Collection, balance update, receipt, audit log, and idempotency result commit atomically.
- [ ] Failures roll back the complete PostgreSQL transaction.
- [ ] Accepted responses return transaction ID, receipt number, official balance, and accepted time.
- [ ] Conflict and rejection responses return stable machine-readable codes.
- [ ] Network retries with the same key cannot create a second collection.
- [ ] Automated backend tests cover concurrent duplicate submissions.
- [ ] Automated integration tests use a disposable PostgreSQL database.
- [ ] The mobile repository contract tests pass against the live endpoint.

The collector payment form and encrypted pending queue must remain disabled until this checklist is complete.
