import pytest
from test_treasury_application_accounting_postgres import (
    application_db as _application_db,
)
from treasury_application_accounting_test_support import (
    application_post,
    application_prepare,
    create_application_source,
)

application_db = _application_db


@pytest.mark.parametrize("code", ["2200", "1110", "1120", "4010"])
def test_posted_application_chart_drift_requires_correction_review(
    application_db, monkeypatch, code
):
    f = create_application_source(application_db, monkeypatch)
    application_post(f, application_prepare(f))
    f["conn"].execute(
        "UPDATE accounting.accounts SET normal_balance=CASE WHEN normal_balance='debit' THEN 'credit' ELSE 'debit' END WHERE code=%s",
        (code,),
    )
    status = (
        f["conn"]
        .execute(
            "SELECT exact_posted,correction_pending FROM accounting.treasury_application_posting_status WHERE application_id=%s",
            (f["application"],),
        )
        .fetchone()
    )
    assert status["exact_posted"] is True
    assert status["correction_pending"] is True


def test_retired_or_renamed_accounts_preserve_historical_application_proof(
    application_db, monkeypatch
):
    f = create_application_source(application_db, monkeypatch)
    application_post(f, application_prepare(f))
    f["conn"].execute(
        "UPDATE accounting.accounts SET name=name||' retired',is_active=false WHERE code IN ('2200','1110','1120','4010')"
    )
    status = (
        f["conn"]
        .execute(
            "SELECT exact_posted,correction_pending FROM accounting.treasury_application_posting_status WHERE application_id=%s",
            (f["application"],),
        )
        .fetchone()
    )
    assert status == {"exact_posted": True, "correction_pending": False}
