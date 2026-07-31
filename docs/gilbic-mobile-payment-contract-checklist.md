# Gilbic payment contract implementation checklist

The collector payment form and encrypted pending queue remain disabled until the **live SPINA backend** section is complete.

## Implemented in the repository package

- [x] `collection.create` is checked against the authenticated `ActorContext`.
- [x] `Idempotency-Key`, `X-Client-Transaction-Id`, and body `client_transaction_id` must match.
- [x] The header, body, authenticated actor, and registered device IDs must match.
- [x] A PostgreSQL migration creates a global unique idempotency-key constraint.
- [x] A canonical SHA-256 request hash detects changed payload reuse.
- [x] Same key and same payload returns the original transaction and receipt.
- [x] Same key and different payload returns `409 idempotency_mismatch`.
- [x] PostgreSQL advisory locking serializes work for one transaction key.
- [x] Business conflicts and rejections leave the transaction scope and roll back.
- [x] Accepted responses return transaction ID, receipt number, official balance, and accepted time.
- [x] Conflict and rejection responses return stable machine-readable codes.
- [x] Deterministic tests cover 32 concurrent retries and require one post.
- [x] An opt-in disposable-PostgreSQL concurrency test is included.
- [x] FastAPI router tests cover accepted, duplicate, conflict, and protocol-error responses.

## Still required in the live SPINA backend

- [ ] Store `C:\SPINA_ONLINE\spina_backend` source in GitHub or copy this reviewed package into that project.
- [ ] Derive the collector identity from the real bearer session.
- [ ] Resolve the registered device from the official server records.
- [ ] Apply the migration to a reviewed development PostgreSQL database.
- [ ] Implement `ExistingSpinaCollectionBridge` using the current payment, ADV, and PASS logic.
- [ ] Validate route entry, route revision, collector assignment, loan, and collection date.
- [ ] Enforce closed-day and closed-route rules.
- [ ] Calculate the official balance only with existing SPINA server logic.
- [ ] Create the official collection, balance update, receipt, audit log, and idempotency row in one transaction.
- [ ] Run the opt-in concurrent test against a disposable PostgreSQL database.
- [ ] Run mobile contract tests against the live FastAPI endpoint.
- [ ] Review backup, rollback, and production deployment procedures.

## Write-feature gate

Do not add the collector payment form, encrypted pending-payment queue, automatic retry worker, or receipt persistence until every live-backend item is checked and the final endpoint is tested with non-production data.
