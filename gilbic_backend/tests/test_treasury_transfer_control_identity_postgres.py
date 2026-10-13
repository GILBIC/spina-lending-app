"""An unsupported transit balance cannot disappear through chart reclassification."""

import psycopg
import pytest
from test_treasury_transfer_accounting_postgres import transfer_db as _transfer_db

transfer_db = _transfer_db


def manual_transit(f, code):
    day = (
        f["conn"]
        .execute(
            "SELECT start_date FROM accounting.fiscal_periods WHERE id=%s",
            (f["period"],),
        )
        .fetchone()["start_date"]
    )
    journal = (
        f["conn"]
        .execute(
            "INSERT INTO accounting.journal_entries(fiscal_period_id,posting_date,description,source_type,created_by_user_id) VALUES(%s,%s,'Synthetic unsupported transit','manual',%s) RETURNING id",
            (f["period"], day, f["actor"].user_id),
        )
        .fetchone()["id"]
    )
    f["conn"].execute(
        "INSERT INTO accounting.journal_lines(journal_entry_id,line_number,account_id,description,debit,credit) SELECT %s,leg.n,a.id,'Synthetic unsupported transit',leg.debit,leg.credit FROM (VALUES(1,%s,100,0),(2,'1030',0,100)) leg(n,code,debit,credit) JOIN accounting.accounts a ON a.code=leg.code",
        (journal, code),
    )
    f["conn"].execute(
        "SELECT accounting.post_journal_entry(%s,%s)", (journal, f["actor"].user_id)
    )
    return journal


@pytest.mark.parametrize(
    "change",
    [
        "code='1098'",
        "system_key='recoded_transit'",
        "account_type='expense'",
        "normal_balance='credit'",
        "is_posting=false",
    ],
)
def test_unregistered_transfer_transit_cannot_be_hidden_by_chart_change(
    transfer_db, change
):
    f = transfer_db
    journal = manual_transit(f, "1040")
    with (
        pytest.raises(psycopg.Error, match="control.*definition|immutable"),
        f["conn"].transaction(),
    ):
        f["conn"].execute(
            "UPDATE accounting.accounts SET " + change + " WHERE code='1040'"
        )
    assert (
        f["conn"]
        .execute(
            "SELECT amount FROM accounting.period_transfer_control_blockers(%s) WHERE source_id=%s",
            (f["period"], journal),
        )
        .fetchone()["amount"]
        == 100
    )


def test_unused_transfer_transit_control_cannot_be_deleted(transfer_db):
    with (
        pytest.raises(psycopg.Error, match="control.*definition|immutable"),
        transfer_db["conn"].transaction(),
    ):
        transfer_db["conn"].execute("DELETE FROM accounting.accounts WHERE code='1040'")


def test_transfer_transit_display_change_preserves_unregistered_balance(transfer_db):
    f = transfer_db
    journal = manual_transit(f, "1040")
    f["conn"].execute(
        "UPDATE accounting.accounts SET is_active=false,name='Retired synthetic transfer transit' WHERE code='1040'"
    )
    assert (
        f["conn"]
        .execute(
            "SELECT amount FROM accounting.period_transfer_control_blockers(%s) WHERE source_id=%s",
            (f["period"], journal),
        )
        .fetchone()["amount"]
        == 100
    )
