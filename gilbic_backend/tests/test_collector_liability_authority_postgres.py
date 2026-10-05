from contextlib import contextmanager
from uuid import UUID

import psycopg
import pytest
import test_collector_liability_accounting_postgres as base
from collector_accounting_test_support import (
    accepted,
    debited,
    other_paying_wallet,
    post,
    prepare,
    recognized,
    reserved,
    review,
)
from gilbic_backend.collector_liability_accounting_repository import (
    PostgresCollectorLiabilityAccountingRepository,
)
from gilbic_backend.treasury_authorization import TreasuryDenied

collector_accounting = base.collector_accounting


def repository(f):
    @contextmanager
    def connection():
        with f["conn"].transaction():
            yield f["conn"]

    return PostgresCollectorLiabilityAccountingRepository(
        connection_factory=connection, evidence_store=f["store"]
    )


def test_return_from_another_wallet_rechecks_both_private_accounts(
    collector_accounting,
):
    f = collector_accounting
    acceptance = accepted(f)
    post(f, prepare(f, "settlement", UUID(acceptance["settlement"]["id"])))
    credit, entry = recognized(f, acceptance)
    post(f, prepare(f, "recognition", entry))
    paying = other_paying_wallet(f)
    reservation = reserved(paying, credit, request_source=f)
    debit = debited(paying, reservation)
    source = UUID(debit["source_link"]["action_record"]["id"])
    prepared = prepare(paying, "return_debit", source)
    assert set(prepared["snapshot"]["account_ids"]) == {
        str(f["wallet"]),
        str(paying["wallet"]),
    }
    f["conn"].execute(
        "UPDATE treasury.account_access SET enabled=false WHERE account_id=%s AND user_id=%s",
        (f["wallet"], f["actor"].user_id),
    )
    with pytest.raises(psycopg.errors.InsufficientPrivilege), f["conn"].transaction():
        post(paying, prepared)
    repo = repository(paying)
    with pytest.raises(TreasuryDenied):
        repo.read_preparation(f["actor"], preparation_id=prepared["id"])
    f["conn"].execute(
        "UPDATE treasury.account_access SET enabled=true WHERE account_id=%s AND user_id=%s",
        (f["wallet"], f["actor"].user_id),
    )
    post(paying, prepared)
    assert f["conn"].execute(
        "SELECT exact_posted,correction_pending FROM accounting.collector_liability_posting_status WHERE preparation_id=%s",
        (prepared["id"],),
    ).fetchone() == {"exact_posted": True, "correction_pending": False}


@pytest.mark.parametrize("revoke", ["device", "role"])
def test_post_rechecks_live_device_and_management_role(collector_accounting, revoke):
    f = collector_accounting
    acceptance = accepted(f)
    prepared = prepare(f, "settlement", UUID(acceptance["settlement"]["id"]))
    if revoke == "device":
        f["conn"].execute(
            "UPDATE core.devices SET status='revoked' WHERE id=%s",
            (f["actor"].registered_device_id,),
        )
    else:
        f["conn"].execute(
            "DELETE FROM core.user_roles WHERE user_id=%s AND role_id=(SELECT id FROM core.roles WHERE code='management')",
            (f["actor"].user_id,),
        )
    with pytest.raises(TreasuryDenied):
        repository(f).post(
            f["actor"],
            preparation_id=prepared["id"],
            source_digest=prepared["source_digest"],
            confirmation_token=prepared["confirmation_token"],
        )
    assert (
        f["conn"]
        .execute("SELECT count(*) AS n FROM accounting.collector_liability_postings")
        .fetchone()["n"]
        == 0
    )


def test_source_digest_and_posted_proof_are_independent_of_connection_timezone(
    collector_accounting,
):
    f = collector_accounting
    acceptance = accepted(f)
    source_id = UUID(acceptance["settlement"]["id"])
    f["conn"].execute("SET LOCAL timezone='UTC'")
    utc = review(f, "settlement", source_id)
    prepared = prepare(f, "settlement", source_id)
    f["conn"].execute("SET LOCAL timezone='Asia/Manila'")
    local = review(f, "settlement", source_id)
    assert utc["source_digest"] == local["source_digest"]
    post(f, prepared)
    f["conn"].execute("SET LOCAL timezone='UTC'")
    assert f["conn"].execute(
        "SELECT exact_posted,correction_pending FROM accounting.collector_liability_posting_status WHERE preparation_id=%s",
        (prepared["id"],),
    ).fetchone() == {"exact_posted": True, "correction_pending": False}


def test_collector_guard_preserves_unrelated_manual_draft_deletion(
    collector_accounting,
):
    f = collector_accounting
    draft = (
        f["conn"]
        .execute(
            "INSERT INTO accounting.journal_entries(fiscal_period_id,posting_date,description,source_type,created_by_user_id) VALUES(%s,%s,'Synthetic cancelled manual draft','manual',%s) RETURNING id",
            (f["period"], f["day"], f["actor"].user_id),
        )
        .fetchone()["id"]
    )
    assert f["conn"].execute(
        "DELETE FROM accounting.journal_entries WHERE id=%s RETURNING id", (draft,)
    ).fetchone() == {"id": draft}


def test_collector_public_review_uses_canonical_money_even_for_zero_fee(
    collector_accounting,
):
    f = collector_accounting
    acceptance = accepted(f)
    settlement = UUID(acceptance["settlement"]["id"])
    source = review(f, "settlement", settlement)
    assert source["amount"] == "110.00" and source["fee"] == "0.00"
    post(f, prepare(f, "settlement", settlement))
    _, entry = recognized(f, acceptance)
    source = review(f, "recognition", entry)
    assert source["amount"] == "10.00" and source["fee"] == "0.00"
