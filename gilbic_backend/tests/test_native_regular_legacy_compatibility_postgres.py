"""Adding native provenance must preserve retained legacy review digests."""

# Imported fixtures are registered with pytest and referenced by argument name.
# ruff: noqa: F401, F811

from pathlib import Path

import pytest
from test_regular_treasury_application_postgres import (
    coordinates,
    posted,
    regular_application,
    retained,
)
from test_treasury_receipt_accounting_postgres import install

MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "sql/0163_add_native_regular_assessment_integration.sql"
)


@pytest.mark.parametrize("regular_application", [True], indirect=True)
@pytest.mark.parametrize("include_chronological", [False, True])
def test_native_extension_keeps_prepared_legacy_source_and_confirmation_exact(
    regular_application,
    include_chronological,
):
    f = regular_application
    before = coordinates(f)
    preparation = retained(f)
    prefix = (
        f["conn"]
        .execute(
            "SELECT source_digest,source_snapshot FROM accounting.loan_elapsed_assessment_preparations WHERE id=%s",
            (f["prefix_preparation"],),
        )
        .fetchone()
    )
    assert MIGRATION.exists(), "Native integration migration is required"
    install(f["conn"], MIGRATION)
    if include_chronological:
        install(
            f["conn"], MIGRATION.with_name("0165_add_regular_chronological_cash.sql")
        )

    assert coordinates(f) == before
    assert (
        f["conn"]
        .execute(
            "SELECT source_digest,source_snapshot FROM accounting.loan_elapsed_assessment_preparations WHERE id=%s",
            (f["prefix_preparation"],),
        )
        .fetchone()
        == prefix
    )
    assert (
        f["conn"]
        .execute(
            "SELECT accounting.period_elapsed_loan_assessment_exact(%s,%s) AS exact",
            (f["prefix_period"], f["loan"]),
        )
        .fetchone()["exact"]
    )
    first = posted(f, preparation)
    assert posted(f, preparation) == first
    f["conn"].execute("SET CONSTRAINTS ALL IMMEDIATE")
