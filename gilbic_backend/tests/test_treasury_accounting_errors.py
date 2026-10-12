from contextlib import contextmanager

import psycopg
import pytest
from gilbic_backend.treasury_authorization import (
    TreasuryConflict,
    TreasuryDenied,
    TreasuryUnavailable,
)
from gilbic_backend.treasury_receipt_accounting_repository import (
    TreasuryAccountingAccess,
)


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (
            psycopg.errors.CheckViolation("Reviewed values do not reconcile."),
            TreasuryConflict,
        ),
        (
            psycopg.errors.InsufficientPrivilege("Current access revoked."),
            TreasuryDenied,
        ),
        (psycopg.OperationalError("Database unavailable."), TreasuryUnavailable),
    ],
)
def test_accounting_transaction_distinguishes_review_rejection_from_outage(
    error, expected
):
    @contextmanager
    def connection():
        raise error
        yield  # pragma: no cover

    repository = TreasuryAccountingAccess(connection_factory=connection)
    with pytest.raises(expected), repository._transaction():
        pytest.fail("The rejected transaction cannot yield a connection.")
