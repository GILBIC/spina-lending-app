"""A posted Regular application retains the original release cash account meaning."""

import pytest
from test_regular_treasury_application_boundaries_postgres import status
from test_regular_treasury_application_postgres import posted, retained
from test_regular_treasury_application_postgres import (
    regular_application as _regular_application,
)

regular_application = _regular_application


@pytest.mark.parametrize(
    "change", ["normal_balance", "is_posting", "name", "retirement"]
)
def test_posted_regular_origin_cash_semantics_are_retained_but_display_is_not(
    regular_application, change
):
    f = regular_application
    preparation = retained(f)
    origin = preparation["snapshot"]["origin"]
    # 0051's ready origin demands the same loan/client dimensions on BOTH lines.
    # Verify that real protected source rather than assuming the cash line was
    # retained merely because the principal debit was loan-attributed.
    cash_lines = [
        item
        for item in origin["loan_ledger"]
        if item["journal"]["id"] == origin["anchor"]["journal_entry_id"]
        and item["account"]["code"] == "1010"
    ]
    assert len(cash_lines) == 1
    cash = cash_lines[0]
    assert cash["line"]["loan_id"] == str(f["loan"])
    assert cash["line"]["client_id"] == str(f["client"])
    assert cash["account"]["normal_balance"] == "debit"
    assert cash["account"]["is_posting"] is True
    journal = posted(f, preparation)
    f["conn"].execute("SET CONSTRAINTS ALL IMMEDIATE")

    if change == "normal_balance":
        f["conn"].execute(
            "UPDATE accounting.accounts SET normal_balance='credit' WHERE id=%s",
            (cash["account"]["id"],),
        )
    elif change == "is_posting":
        f["conn"].execute(
            "UPDATE accounting.accounts SET is_posting=false WHERE id=%s",
            (cash["account"]["id"],),
        )
    elif change == "name":
        f["conn"].execute(
            "UPDATE accounting.accounts SET name=name||' display edit' WHERE id=%s",
            (cash["account"]["id"],),
        )
    else:
        f["conn"].execute(
            "UPDATE accounting.accounts SET is_active=false WHERE id=%s",
            (cash["account"]["id"],),
        )

    assert status(f) == {
        "exact_posted": True,
        "correction_pending": change in {"normal_balance", "is_posting"},
    }
    assert posted(f, preparation) == journal
    retained_origin = (
        f["conn"]
        .execute(
            "SELECT snapshot->'origin' AS origin FROM "
            "accounting.treasury_application_preparations WHERE id=%s",
            (preparation["id"],),
        )
        .fetchone()["origin"]
    )
    assert retained_origin == origin
