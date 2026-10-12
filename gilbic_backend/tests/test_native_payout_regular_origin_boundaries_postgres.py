"""Native original-contract proof cannot absorb changed or ambiguous sources."""

from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import psycopg
import pytest
from test_native_payout_regular_origin_postgres import (
    _actual_debit,
    _complete,
    _journal_count,
    _origin,
    _schedule,
    balances,
    complete_borrower,
    confirm,
)
from test_native_payout_regular_origin_postgres import native_origin as _native_origin
from test_native_payout_regular_origin_postgres import (
    payout_accounting as _payout_accounting,
)
from test_native_payout_regular_origin_postgres import (
    payout_database as _payout_database,
)
from test_native_payout_regular_origin_postgres import (
    private_fixture_configuration as _private_fixture_configuration,
)

native_origin = _native_origin
payout_accounting = _payout_accounting
payout_database = _payout_database
private_fixture_configuration = _private_fixture_configuration


def _completed(f):
    prepared, _ = _actual_debit(f)
    _complete(f, prepared)
    return prepared["target_id"]


def test_actual_completion_without_its_accounting_proof_is_not_an_origin(native_origin):
    f = native_origin
    prepared, _ = _actual_debit(f)
    confirm(f, prepared["target_id"])
    complete_borrower(f, prepared)
    assert balances(f) == {"1030": Decimal(-1000), "1050": Decimal(1000)}
    origin = _origin(f)
    assert not origin["ready"]
    assert "native_payout_posting_not_exact" in origin["blockers"]


@pytest.mark.parametrize("change", ["event_correction", "chart_role", "book_scope"])
def test_changed_native_proof_or_book_scope_cannot_supply_origin(native_origin, change):
    f = native_origin
    payout = _completed(f)
    assert _origin(f)["ready"]
    if change == "event_correction":
        f["conn"].execute(
            "INSERT INTO treasury.event_revisions(id,event_id,version,action,reason,actor_id) "
            "SELECT %s,event_id,2,'correct','Synthetic changed debit observation',%s "
            "FROM treasury.loan_payouts WHERE id=%s",
            (uuid4(), f["owner"].user_id, payout),
        )
    elif change == "chart_role":
        f["conn"].execute(
            "UPDATE accounting.accounts SET is_posting=false WHERE code='1100'"
        )
    else:
        f["conn"].execute(
            "UPDATE treasury.accounts SET ownership='corporate' WHERE id=%s",
            (f["account_id"],),
        )
    count_before = _journal_count(f)
    origin = _origin(f)
    assert not origin["ready"]
    assert origin.get("anchor") is None
    assert _journal_count(f) == count_before


def test_unsigned_added_installment_cannot_change_retained_native_eir(native_origin):
    f = native_origin
    _completed(f)
    release, _ = _schedule(f)
    assert _origin(f)["ready"]
    # Registered rows remain immutable; an appended unsupported row is still
    # possible in the raw table and must not silently change original pricing.
    f["conn"].execute(
        "INSERT INTO lending.loan_contract_installments(schedule_id,installment_number,"
        "due_date,contractual_amount,principal_component,interest_component) "
        "VALUES(%s,13,%s,100,0,100)",
        (release["schedule_id"], release["due_date"] + timedelta(days=1)),
    )
    origin = _origin(f)
    assert not origin["ready"]
    assert "native_signed_installments_not_exact" in origin["blockers"]


def _extra_transit(f, *, reverse=False, control="1050"):
    conn = f["conn"]
    journal = conn.execute(
        "INSERT INTO accounting.journal_entries(fiscal_period_id,posting_date,"
        "description,source_type,created_by_user_id) "
        "VALUES(%s,%s,'Synthetic unsupported origin component','manual',%s) RETURNING id",
        (f["period"], f["today"], f["owner"].user_id),
    ).fetchone()["id"]
    conn.execute(
        "INSERT INTO accounting.journal_lines(journal_entry_id,line_number,account_id,"
        "debit,credit,loan_id,client_id) "
        "SELECT %s,x.n,a.id,x.debit,x.credit,%s,%s FROM "
        "(VALUES(1,%s::text,%s::numeric,%s::numeric),(2,'1030',%s::numeric,%s::numeric)) "
        "x(n,code,debit,credit) JOIN accounting.accounts a ON a.code=x.code",
        (
            journal,
            f["loan_id"],
            f["client_id"],
            control,
            *((0, 1, 1, 0) if reverse else (1, 0, 0, 1)),
        ),
    )
    conn.execute(
        "SELECT accounting.post_journal_entry(%s,%s)", (journal, f["owner"].user_id)
    )


def test_unknown_original_control_pair_is_not_hidden_by_zero_net_transit(native_origin):
    f = native_origin
    _completed(f)
    assert _origin(f)["ready"]
    before = balances(f)
    _extra_transit(f)
    _extra_transit(f, reverse=True)
    assert balances(f) == before
    origin = _origin(f)
    assert not origin["ready"]
    assert "unrecognized_original_loan_control_journal" in origin["blockers"]


@pytest.mark.parametrize("control", ["1110", "1120"])
def test_recoding_cannot_hide_an_extra_original_loan_journal(native_origin, control):
    f = native_origin
    _completed(f)
    assert _origin(f)["ready"]
    _extra_transit(f, control=control)
    assert not _origin(f)["ready"]
    f["conn"].execute(
        "UPDATE accounting.accounts SET code='9919' WHERE code=%s", (control,)
    )
    origin = _origin(f)
    assert not origin["ready"]
    assert "unrecognized_original_loan_control_journal" in origin["blockers"]


def test_original_allowance_cannot_bypass_its_existing_protected_workflow(
    native_origin,
):
    f = native_origin
    _completed(f)
    before = _origin(f)
    count = _journal_count(f)
    with (
        pytest.raises(psycopg.errors.RaiseException, match="protected ECL"),
        f["conn"].transaction(),
    ):
        _extra_transit(f, control="1190")
    assert _origin(f) == before
    assert _journal_count(f) == count


def test_display_retirement_preserves_exact_historical_origin(native_origin):
    f = native_origin
    _completed(f)
    before = _origin(f)
    assert before["ready"]
    f["conn"].execute(
        "UPDATE accounting.accounts SET name='Retired synthetic original account',"
        "is_active=false WHERE code IN('1030','1050','1100')"
    )
    after = _origin(f)
    assert after == before


def test_native_private_normalizer_has_no_direct_client_grants(native_origin):
    conn = native_origin["conn"]
    row = conn.execute(
        "SELECT p.oid,p.prosecdef,p.provolatile FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
        "WHERE n.nspname='accounting' AND p.proname='regular_original_origin'"
    ).fetchone()
    assert row is not None
    assert row["prosecdef"] is False and row["provolatile"] == "s"
    assert (
        conn.execute(
            "SELECT acl.grantee FROM pg_proc p,LATERAL "
            "aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) acl "
            "WHERE p.oid=%s AND acl.grantee=0 AND acl.privilege_type='EXECUTE'",
            (row["oid"],),
        ).fetchall()
        == []
    )
    assert (
        conn.execute(
            "SELECT rolname FROM pg_roles WHERE rolname IN('anon','authenticated','service_role') "
            "AND has_function_privilege(oid,%s,'EXECUTE')",
            (row["oid"],),
        ).fetchall()
        == []
    )
