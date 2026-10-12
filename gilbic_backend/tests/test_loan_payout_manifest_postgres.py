"""A later borrower completion cannot rewrite the reviewed earlier transit cutoff."""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from test_first_loan_postgres import (
    private_fixture_configuration as _private_fixture_configuration,
)
from test_loan_payout_accounting_postgres import (
    MIGRATION,
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


def test_future_borrower_completion_preserves_reviewed_debit_only_cutoff(
    payout_accounting,
):
    f = payout_accounting
    conn = f["conn"]
    if (
        conn.execute(
            "SELECT to_regprocedure('accounting.period_review_source_snapshot(uuid)') AS proc"
        ).fetchone()["proc"]
        is None
    ):
        install(
            conn, MIGRATION.with_name("0154_add_retained_period_review_manifests.sql")
        )
        # Attach the adapter's dated evidence hook after installing the manifest.
        install(conn, MIGRATION)
    today = conn.execute(
        "SELECT (now() AT TIME ZONE 'Asia/Manila')::date AS day"
    ).fetchone()["day"]
    cutoff = today - timedelta(days=1)
    conn.execute(
        "UPDATE accounting.fiscal_periods SET end_date=%s WHERE id=%s",
        (cutoff, f["period"]),
    )
    later_period = conn.execute(
        "SELECT accounting.create_fiscal_period('Synthetic later borrower completion',%s,%s,%s) AS id",
        (today, today + timedelta(days=2), f["actor"].user_id),
    ).fetchone()["id"]
    conn.commit()
    _, prepared = prepare_operational(f, destination="collector")
    debit(
        f,
        prepared,
        fee="0.00",
        effective_at=datetime.combine(cutoff, time(12), tzinfo=ZoneInfo("Asia/Manila")),
    )
    debit_journal = post_stage(f, prepared["target_id"], "debit")
    conn.execute(
        "SELECT accounting.set_fiscal_period_status(%s,'review',%s)",
        (f["period"], f["actor"].user_id),
    )
    before = conn.execute(
        "SELECT accounting.period_review_manifest_state(%s) AS state", (f["period"],)
    ).fetchone()["state"]
    old_snapshot = conn.execute(
        "SELECT accounting.period_review_source_snapshot(%s) AS snapshot",
        (f["period"],),
    ).fetchone()["snapshot"]
    conn.commit()
    confirm(f, prepared["target_id"])
    complete_borrower(f, prepared)
    completion_journal = post_stage(f, prepared["target_id"], "completion")
    assert (
        conn.execute(
            "SELECT fiscal_period_id FROM accounting.journal_entries WHERE id=%s",
            (completion_journal,),
        ).fetchone()["fiscal_period_id"]
        == later_period
    )
    after = conn.execute(
        "SELECT accounting.period_review_manifest_state(%s) AS state", (f["period"],)
    ).fetchone()["state"]
    current_snapshot = conn.execute(
        "SELECT accounting.period_review_source_snapshot(%s) AS snapshot",
        (f["period"],),
    ).fetchone()["snapshot"]
    assert current_snapshot == old_snapshot, (
        "A genuine future completion must not rewrite earlier transit-period evidence"
    )
    assert after == before
    old_debit = conn.execute(
        "SELECT exact_posted,correction_pending FROM accounting.loan_payout_accounting_posting_status WHERE journal_entry_id=%s",
        (debit_journal,),
    ).fetchone()
    assert old_debit == {"exact_posted": True, "correction_pending": False}
