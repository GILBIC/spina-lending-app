"""Real native payout lineage supplies an origin without legacy cash fabrication.

The operational release records the actual server day. These initial cases test
the private origin boundary only, not a future or forged historical assessment.
"""

from datetime import datetime, time, timedelta
from decimal import Decimal, localcontext
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from test_first_loan_postgres import (
    private_fixture_configuration as _private_fixture_configuration,
)
from test_loan_payout_accounting_postgres import (
    balances,
    complete_borrower,
    confirm,
    debit,
    post_stage,
    prepare_operational,
)
from test_loan_payout_accounting_postgres import payout_accounting as _payout_accounting
from test_loan_payout_accounting_postgres import payout_database as _payout_database
from test_treasury_receipt_accounting_postgres import install

private_fixture_configuration = _private_fixture_configuration
payout_accounting = _payout_accounting
payout_database = _payout_database
MIGRATION = (
    Path(__file__).resolve().parents[1] / "sql/0156_add_native_regular_origins.sql"
)
MANILA = ZoneInfo("Asia/Manila")


@pytest.fixture
def native_origin(payout_accounting):
    f = payout_accounting
    if MIGRATION.exists():
        install(f["conn"], MIGRATION)
    f["today"] = (
        f["conn"]
        .execute("SELECT (clock_timestamp() AT TIME ZONE 'Asia/Manila')::date AS day")
        .fetchone()["day"]
    )
    f["conn"].commit()
    return f


def _origin(f, cutoff=None):
    return (
        f["conn"]
        .execute(
            "SELECT accounting.regular_original_origin(%s,%s) AS origin",
            (f["loan_id"], cutoff or f["today"]),
        )
        .fetchone()["origin"]
    )


def _actual_debit(f, *, fee="0.00", previous_day=False):
    _, prepared = prepare_operational(f, destination="collector")
    changes = {"fee": fee}
    if previous_day:
        changes["effective_at"] = datetime.combine(
            f["today"] - timedelta(days=1), time(12), tzinfo=MANILA
        )
    debit(f, prepared, **changes)
    journal = post_stage(f, prepared["target_id"], "debit")
    return prepared, journal


def _complete(f, prepared):
    confirm(f, prepared["target_id"])
    completed = complete_borrower(f, prepared)
    assert completed["result"]["payout"]["status"] == "completed"
    return post_stage(f, prepared["target_id"], "completion")


def _retained(f, payout):
    rows = (
        f["conn"]
        .execute(
            "SELECT stage,journal_entry_id,posting_date,amount,fee,exact_posted,"
            "correction_pending FROM accounting.loan_payout_accounting_posting_status "
            "WHERE payout_id=%s ORDER BY stage",
            (payout,),
        )
        .fetchall()
    )
    assert rows and all(
        row["exact_posted"] and not row["correction_pending"] for row in rows
    )
    return {row["stage"]: row for row in rows}


def _schedule(f):
    release = (
        f["conn"]
        .execute(
            "SELECT r.schedule_id,r.disbursement_event_id,l.date_released,l.due_date "
            "FROM lending.first_loan_releases r JOIN lending.loans l ON l.id=r.loan_id "
            "WHERE r.loan_id=%s",
            (f["loan_id"],),
        )
        .fetchone()
    )
    installments = (
        f["conn"]
        .execute(
            "SELECT due_date,contractual_amount FROM lending.loan_contract_installments "
            "WHERE schedule_id=%s ORDER BY installment_number",
            (release["schedule_id"],),
        )
        .fetchall()
    )
    assert len(installments) == 12
    assert sum(row["contractual_amount"] for row in installments) == Decimal(1200)
    return release, installments


def _independent_rate(release, installments):
    """Solve the retained contractual cash independently of the SQL solver."""
    with localcontext() as context:
        context.prec = 55
        low, high = Decimal(0), Decimal(1)
        for _ in range(180):
            rate = (low + high) / 2
            present = sum(
                row["contractual_amount"]
                / (1 + rate) ** (row["due_date"] - release["date_released"]).days
                for row in installments
            )
            if present > Decimal(1000):
                low = rate
            else:
                high = rate
        return (low + high) / 2


def _journal_count(f):
    return (
        f["conn"]
        .execute("SELECT count(*) AS n FROM accounting.journal_entries")
        .fetchone()["n"]
    )


def _assert_no_legacy_cash(f):
    assert (
        f["conn"]
        .execute(
            "SELECT count(*) AS n FROM accounting.loan_disbursement_journal_postings "
            "WHERE loan_id=%s",
            (f["loan_id"],),
        )
        .fetchone()["n"]
        == 0
    )
    assert (
        f["conn"]
        .execute(
            "SELECT count(*) AS n FROM accounting.journal_entries "
            "WHERE source_event_key LIKE 'loan_disbursement:%%'"
        )
        .fetchone()["n"]
        == 0
    )


def test_actual_native_completion_supplies_exact_signed_contract_origin(native_origin):
    f = native_origin
    prepared, debit_journal = _actual_debit(f, previous_day=True)
    completion_journal = _complete(f, prepared)
    retained = _retained(f, prepared["target_id"])
    release, installments = _schedule(f)
    assert retained["debit"]["posting_date"] == f["today"] - timedelta(days=1)
    assert (
        retained["completion"]["posting_date"] == release["date_released"] == f["today"]
    )
    assert balances(f) == {
        "1030": Decimal(-1000),
        "1050": Decimal(0),
        "1100": Decimal(1000),
    }
    _assert_no_legacy_cash(f)
    count_before = _journal_count(f)

    origin = _origin(f)

    assert origin["ready"], origin["blockers"]
    assert origin["origin_kind"] == "native_payout"
    anchor = origin["anchor"]
    assert anchor["loan_id"] == str(f["loan_id"])
    assert anchor["client_id"] == str(f["client_id"])
    assert anchor["schedule_id"] == str(release["schedule_id"])
    assert anchor["disbursement_event_id"] == str(release["disbursement_event_id"])
    assert anchor["journal_entry_id"] == str(completion_journal)
    assert anchor["journal_entry_id"] != str(debit_journal)
    assert anchor["anchor_date"] == f["today"].isoformat()
    assert anchor["contractual_due_date"] == release["due_date"].isoformat()
    assert Decimal(str(anchor["initial_gross_carrying_amount"])) == Decimal(1000)
    assert anchor["anchor_policy_version"] == "native_regular_payout_anchor_v1"
    assert anchor["anchor_source_key"].startswith("native_regular_payout_anchor:")
    assert abs(
        Decimal(str(anchor["daily_eir"])) - _independent_rate(release, installments)
    ) < Decimal("0.000000000001")
    assert _journal_count(f) == count_before
    _assert_no_legacy_cash(f)


@pytest.mark.parametrize("recipient_confirmed", [False, True])
def test_actual_debit_or_intermediary_receipt_is_not_a_loan_origin(
    native_origin, recipient_confirmed
):
    f = native_origin
    prepared, _ = _actual_debit(f)
    if recipient_confirmed:
        confirm(f, prepared["target_id"])
    assert set(_retained(f, prepared["target_id"])) == {"debit"}
    assert balances(f) == {"1030": Decimal(-1000), "1050": Decimal(1000)}
    assert f["conn"].execute(
        "SELECT status,date_released FROM lending.loans WHERE id=%s", (f["loan_id"],)
    ).fetchone() == {"status": "approved", "date_released": None}
    count_before = _journal_count(f)

    origin = _origin(f)

    assert not origin["ready"]
    assert "native_payout_completion_required" in origin["blockers"]
    assert origin.get("anchor") is None
    assert _journal_count(f) == count_before
    _assert_no_legacy_cash(f)


def test_later_actual_completion_cannot_supply_origin_to_prior_cutoff(native_origin):
    f = native_origin
    prepared, _ = _actual_debit(f, previous_day=True)
    _complete(f, prepared)
    retained = _retained(f, prepared["target_id"])
    cutoff = f["today"] - timedelta(days=1)
    assert retained["debit"]["posting_date"] == cutoff
    assert retained["completion"]["posting_date"] > cutoff
    count_before = _journal_count(f)

    origin = _origin(f, cutoff)

    assert not origin["ready"]
    assert "native_payout_completion_after_cutoff" in origin["blockers"]
    assert origin.get("anchor") is None
    assert _journal_count(f) == count_before
    _assert_no_legacy_cash(f)


def test_native_payout_fee_does_not_inflate_original_carrying_or_eir(native_origin):
    f = native_origin
    prepared, _ = _actual_debit(f, fee="2.00")
    _complete(f, prepared)
    retained = _retained(f, prepared["target_id"])
    release, installments = _schedule(f)
    assert retained["debit"]["fee"] == Decimal(2)
    assert retained["completion"]["fee"] == Decimal(0)
    assert balances(f) == {
        "1030": Decimal(-1002),
        "1050": Decimal(0),
        "1100": Decimal(1000),
        "5240": Decimal(2),
    }
    count_before = _journal_count(f)

    origin = _origin(f)

    assert origin["ready"], origin["blockers"]
    anchor = origin["anchor"]
    assert Decimal(str(anchor["initial_gross_carrying_amount"])) == Decimal(1000)
    assert abs(
        Decimal(str(anchor["daily_eir"])) - _independent_rate(release, installments)
    ) < Decimal("0.000000000001")
    assert _journal_count(f) == count_before
    _assert_no_legacy_cash(f)
