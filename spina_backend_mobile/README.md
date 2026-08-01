# SPINA mobile collection backend package

This package implements the shared server-side idempotency and HTTP boundary for
the Gilbic collection contract. It is now mounted into the GitHub-first
`gilbic_backend` FastAPI application.

## Included

- canonical and mobile-compatible collection router factory
- strict request and header validation
- `gilbic-collection-v1` contract-version check
- canonical SHA-256 request hashing
- PostgreSQL advisory locking by idempotency key
- original transaction and receipt replay
- changed-payload conflict detection
- rollback-safe SPINA posting bridge protocol
- separate raw installation and server-side registered-device identities
- exact two-decimal official balance responses
- deterministic concurrency, router, and rollback tests
- optional disposable-PostgreSQL concurrency test

The live Gilbic adapter is implemented in:

```text
gilbic_backend/src/gilbic_backend/collection_api.py
gilbic_backend/src/gilbic_backend/collection_posting.py
```

The reviewed database migration is:

```text
gilbic_backend/sql/0005_add_idempotent_collections.sql
```

## Install for development

From the repository root:

```powershell
python -m pip install -e ".\spina_backend_mobile[test]"
python -m pip install -e ".\gilbic_backend[test]"
python -m pytest -q .\spina_backend_mobile\tests .\gilbic_backend\tests
```

## Integration shape

The backend supplies two dependencies and one posting bridge:

```python
from spina_mobile_collections.postgres import PostgresCollectionExecutor
from spina_mobile_collections.router import create_collection_router
from spina_mobile_collections.service import CollectionSubmissionService


def get_collection_service() -> CollectionSubmissionService:
    return CollectionSubmissionService(
        PostgresCollectionExecutor(
            connection_factory=get_postgres_connection,
            posting_bridge=OfficialCollectionBridge(),
        )
    )


app.include_router(
    create_collection_router(
        get_actor=get_authenticated_collector_device,
        get_service=get_collection_service,
    )
)
```

`get_authenticated_collector_device` derives the collector account, raw request
installation ID, internal registered-device row, roles, and permissions from the
authenticated request. It never trusts a collector ID or role supplied by
Flutter.

`OfficialCollectionBridge.post_collection(...)` receives the executor's psycopg
connection. The official collection transaction, balance state, receipt, audit
event, and idempotency result therefore commit or roll back together.

## Device privacy

`ActorContext.device_id` is the raw request installation ID used for contract
binding. `ActorContext.registered_device_id` is the internal PostgreSQL device
row ID used for persistence. The idempotency request payload removes the raw
installation ID before storage.

## Business-rule errors

The bridge stops the transaction with stable, user-friendly errors:

```python
from spina_mobile_collections.service import CollectionConflict, CollectionRejected

raise CollectionConflict(
    "The loan changed. Refresh the route and review the entry.",
    code="route_revision_changed",
)
raise CollectionRejected(
    "Use the SPINA desktop app for this loan type.",
    code="loan_calculation_not_ready",
)
```

These exceptions leave the transaction scope, causing PostgreSQL rollback, then
become typed `409` or `422` responses.

## Concurrent PostgreSQL test

The default test suite uses a deterministic thread-safe executor and fake
transaction objects. To test real PostgreSQL advisory locks and the unique
constraint, provide a disposable database:

```powershell
$env:GILBIC_TEST_DATABASE_URL = "postgresql://user:password@localhost/gilbic_test"
python -m pytest -q .\spina_backend_mobile\tests\test_postgres_integration.py
```

The integration test creates temporary test objects, sends 24 concurrent
submissions with the same UUID, and requires one official posting plus 23
original-receipt replays.

Do not point this test at the production database.
