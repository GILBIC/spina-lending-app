# Payment boundary

The files in this directory define and test the Gilbic-to-SPINA collection submission contract.

They are not wired into `GilbicApp`, the collector dashboard, or an offline queue. No collector-facing payment action is enabled by this boundary.

Before wiring this repository into the application, the FastAPI backend must implement the idempotency, PostgreSQL transaction, duplicate replay, conflict, rejection, and receipt rules documented in `docs/gilbic-mobile-payment-contract.md`.
