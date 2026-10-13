from decimal import Decimal
from uuid import UUID

import test_collector_liability_accounting_postgres as base
from collector_accounting_test_support import (
    accepted,
    add_zero_pass,
    balances,
    post,
    prepare,
)

collector_accounting = base.collector_accounting


def test_exact_zero_cash_pass_constituent_does_not_need_or_create_a_collection_journal(
    collector_accounting,
):
    f = collector_accounting
    pass_id = add_zero_pass(f)
    acceptance = accepted(f)
    post(f, prepare(f, "settlement", UUID(acceptance["settlement"]["id"])))
    actual = balances(f)
    assert actual["1010"] == Decimal("110.00")
    assert actual["1020"] == 0 and actual["2210"] == Decimal("-10.00")
    assert (
        f["conn"]
        .execute(
            "SELECT 1 FROM accounting.journal_entries WHERE source_type='collection' AND source_reference=%s",
            (str(pass_id),),
        )
        .fetchone()
        is None
    )
