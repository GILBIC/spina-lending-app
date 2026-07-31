# Gilbic payment contract review boundary

This milestone is intentionally protocol-only.

Approved in mobile code:

- request validation for payment, ADV, and PASS drafts
- UUID version 4 idempotency key generation
- authenticated HTTP request headers
- accepted, duplicate, conflict, and rejected result parsing
- safe retry wording that requires the same transaction key
- tests protecting the disabled collector-facing payment boundary

Still blocked:

- FastAPI endpoint implementation
- PostgreSQL idempotency migration
- collector payment form
- encrypted pending-payment queue
- automatic retry worker
- receipt persistence
- conflict-review workflow

The next write-capable implementation must begin in the FastAPI backend or add that backend source to this repository. Mobile UI wiring is not an acceptable substitute for the missing server transaction and duplicate-protection logic.
