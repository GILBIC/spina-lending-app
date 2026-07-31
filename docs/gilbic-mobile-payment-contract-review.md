# Gilbic payment contract review boundary

The mobile collection contract and a reusable backend integration package now exist in this repository.

## Approved mobile boundary

- request validation for payment, ADV, and PASS drafts
- UUID version 4 idempotency key generation
- authenticated HTTP request headers
- accepted, duplicate, conflict, and rejected result parsing
- safe retry wording that requires the same transaction key
- tests protecting the disabled collector-facing payment boundary

## Approved backend package boundary

- dependency-injected FastAPI collection router
- canonical request hashing
- PostgreSQL advisory locking and globally unique UUID migration
- original receipt replay
- changed-payload conflict handling
- rollback-safe SPINA posting bridge
- deterministic concurrent retry tests
- optional disposable-PostgreSQL integration test

## Still blocked in production

- mounting the package into `C:\SPINA_ONLINE\spina_backend`
- implementing the live session and registered-device dependencies
- connecting the bridge to existing SPINA payment, ADV, PASS, balance, receipt, and audit logic
- applying and verifying the migration in a development database
- running concurrent submissions against disposable PostgreSQL
- collector payment form
- encrypted pending-payment queue
- automatic retry worker
- receipt persistence
- conflict-review workflow

Mobile UI wiring remains prohibited until the live backend items in `gilbic-mobile-payment-contract-checklist.md` are completed.
