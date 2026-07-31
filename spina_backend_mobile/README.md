# SPINA mobile collection backend package

This package implements the server-side idempotency and HTTP boundary for the
Gilbic collection contract. It is designed to be mounted into the existing
SPINA FastAPI backend.

The live backend under `C:\SPINA_ONLINE\spina_backend` is not stored in this
repository. This package therefore does not claim that the production endpoint
is active. It provides the reviewed components that the live backend must wire
to its existing authentication and payment business rules.

## Included

- `POST /api/mobile/v1/collector/collections` router factory
- strict request and header validation
- `gilbic-collection-v1` contract-version check
- canonical SHA-256 request hashing
- PostgreSQL advisory locking by idempotency key
- globally unique UUID migration
- original transaction and receipt replay
- changed-payload conflict detection
- rollback-safe SPINA posting bridge
- deterministic concurrency, router, and rollback tests
- optional disposable-PostgreSQL concurrency test

## Not included

- the production bearer-session lookup
- the production registered-device lookup
- the existing SPINA payment, ADV, and PASS calculation code
- production database credentials
- production migration execution
- collector payment UI or an offline write queue

## Install for development

From the repository root:

```powershell
python -m pip install -e ".\spina_backend_mobile[test]"
python -m pytest -q .\spina_backend_mobile\tests
```

## Apply the migration

Apply this file to a reviewed development database first:

```text
spina_backend_mobile/migrations/0001_gilbic_collection_idempotency.sql
```

The migration creates `mobile.gilbic_collection_idempotency`. The official
SPINA collection write, balance update, receipt, audit log, and idempotency row
must use the same psycopg transaction.

## Mount into the existing FastAPI app

The live backend must provide two dependencies and one bridge:

```python
from spina_mobile_collections.postgres import PostgresCollectionExecutor
from spina_mobile_collections.router import create_collection_router
from spina_mobile_collections.service import CollectionSubmissionService


def get_collection_service() -> CollectionSubmissionService:
    return CollectionSubmissionService(
        PostgresCollectionExecutor(
            connection_factory=get_postgres_connection,
            posting_bridge=ExistingSpinaCollectionBridge(),
        )
    )


app.include_router(
    create_collection_router(
        get_actor=get_authenticated_collector_device,
        get_service=get_collection_service,
    )
)
```

`get_authenticated_collector_device` must derive the collector account and
registered device from the authenticated session. It must not trust an account
ID or role supplied by Flutter.

`ExistingSpinaCollectionBridge.post_collection(...)` must call the existing
SPINA server logic using the supplied psycopg connection. It must return a
`PostedCollection` containing the official transaction ID, receipt number,
balance, acceptance time, and route revision.

## Business-rule errors

The SPINA bridge may stop the transaction with stable errors:

```python
from spina_mobile_collections.service import CollectionConflict, CollectionRejected

raise CollectionConflict("The route changed.", code="stale_route")
raise CollectionRejected("The collection day is closed.", code="day_closed")
```

These exceptions leave the transaction scope, causing PostgreSQL rollback,
then become typed `409` or `422` responses.

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
