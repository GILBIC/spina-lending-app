from datetime import timedelta
from uuid import UUID, uuid4

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
)
from gilbic_backend.treasury_authorization import TreasuryDenied
from psycopg.errors import CheckViolation
from test_collector_liability_authority_postgres import repository

collector_accounting = base.collector_accounting


def recognized_credit(f):
    acceptance = accepted(f)
    post(f, prepare(f, "settlement", UUID(acceptance["settlement"]["id"])))
    credit, entry = recognized(f, acceptance)
    post(f, prepare(f, "recognition", entry))
    return credit


def schedule(f, **kwargs):
    return repository(f).control_schedule(f["actor"], as_of=f["day"], **kwargs)


def test_schedule_distinguishes_credit_normal_liability_from_reserved_capacity(
    collector_accounting,
):
    f = collector_accounting
    credit = recognized_credit(f)
    reserved(f, credit)
    result = schedule(f)
    controls = {row["account_code"]: row for row in result["controls"]}
    assert controls["2220"]["normal_balance"] == "credit"
    assert controls["2220"]["ledger_balance"] == "-10.00"
    assert (
        controls["2220"]["ledger_amount"]
        == controls["2220"]["source_amount"]
        == "10.00"
    )
    assert controls["1060"]["normal_balance"] == "debit"
    assert result["current_capacity"]["outstanding_amount"] == "10.00"
    assert result["current_capacity"]["reserved_amount"] == "4.00"
    assert result["current_capacity"]["available_amount"] == "6.00"
    assert result["current_capacity"]["observed_at"].endswith("+00:00")
    assert result["controls_reconciled"] is True
    assert result["comprehensive_source_coverage"] is False
    assert len(result["movements"]) == result["movement_count"] == 3
    assert all(row["exact_posted"] for row in result["movements"])
    assert all("account_id" not in row for row in result["movements"])


def test_schedule_prior_cutoff_does_not_backdate_current_reservation(
    collector_accounting,
):
    f = collector_accounting
    credit = recognized_credit(f)
    reserved(f, credit)
    result = repository(f).control_schedule(
        f["actor"], as_of=f["day"] - timedelta(days=1)
    )
    assert all(row["ledger_amount"] == "0.00" for row in result["controls"])
    assert result["movement_count"] == 0
    assert result["current_capacity"]["reserved_amount"] == "4.00"


@pytest.mark.parametrize("offset", [0, 99999])
def test_pagination_cannot_hide_missing_origin_or_paying_wallet_authority(
    collector_accounting, offset
):
    f = collector_accounting
    credit = recognized_credit(f)
    paying = other_paying_wallet(f)
    reservation = reserved(paying, credit, request_source=f)
    debited(paying, reservation)
    f["conn"].execute(
        "UPDATE treasury.account_access SET private_history=false WHERE account_id=%s AND user_id=%s",
        (paying["wallet"], f["actor"].user_id),
    )
    with pytest.raises(TreasuryDenied) as failure:
        schedule(f, limit=1, offset=offset)
    assert str(paying["wallet"]) not in str(failure.value)
    assert str(f["wallet"]) not in str(failure.value)


def test_inactive_historical_wallet_does_not_drop_owed_liability(collector_accounting):
    f = collector_accounting
    recognized_credit(f)
    f["conn"].execute(
        "UPDATE treasury.accounts SET active=false WHERE id=%s", (f["wallet"],)
    )
    result = schedule(f)
    assert (
        next(row for row in result["controls"] if row["account_code"] == "2220")[
            "ledger_amount"
        ]
        == "10.00"
    )
    assert result["current_capacity"]["outstanding_amount"] == "10.00"


@pytest.mark.parametrize("offset", [0, 99999])
def test_unsupported_action_link_cannot_expose_an_ungranted_actual_event_wallet(
    collector_accounting, offset
):
    f = collector_accounting
    credit = recognized_credit(f)
    reservation = reserved(f, credit)
    debit = debited(f, reservation)
    action = debit["source_link"]["action_record"]
    foreign = other_paying_wallet(f)
    event_id = uuid4()
    # A plain event FK permits this unsupported historical link. Operational
    # writers do not create it; the read must still authorize the actual source.
    f["conn"].execute(
        """INSERT INTO treasury.events(id,account_id,ledger_context_id,provider,reference,direction,amount,fee,effective_at,
        recorded_by_user_id,verified_by_user_id,device_id,evidence_id,recipient_attestation,classification,reason)
        SELECT %s,%s,ledger_context_id,provider,%s,direction,amount,fee,effective_at,
        recorded_by_user_id,verified_by_user_id,device_id,%s,recipient_attestation,classification,reason
        FROM treasury.events WHERE id=%s""",
        (
            event_id,
            foreign["wallet"],
            uuid4().hex,
            foreign["evidence"],
            UUID(action["event_id"]),
        ),
    )
    f["conn"].execute(
        "UPDATE treasury.collector_actions SET version=version+1,payload=jsonb_set(payload,'{event_id}',to_jsonb(%s::text)) WHERE id=%s",
        (str(event_id), UUID(action["id"])),
    )
    f["conn"].execute(
        "UPDATE treasury.account_access SET private_history=false WHERE account_id=%s AND user_id=%s",
        (foreign["wallet"], f["actor"].user_id),
    )
    with pytest.raises(TreasuryDenied) as failure:
        schedule(f, limit=1, offset=offset)
    assert str(foreign["wallet"]) not in str(failure.value)


def test_view_only_live_guard_and_zero_net_unregistered_lines(collector_accounting):
    f = collector_accounting
    base.test_offsetting_unregistered_collector_lines_are_blockers_even_with_zero_net_balance(
        f
    )
    f["conn"].execute(
        "DELETE FROM core.role_permissions WHERE role_id=(SELECT id FROM core.roles WHERE code='management') AND permission_code='accounting.journal.manage'"
    )
    result = schedule(f)
    control = next(row for row in result["controls"] if row["account_code"] == "2220")
    assert control["ledger_amount"] == "0.00"
    assert control["unregistered_line_count"] == 2
    assert result["controls_reconciled"] is False


def test_current_source_correction_remains_visible_in_paginated_schedule(
    collector_accounting,
):
    f = collector_accounting
    acceptance = accepted(f)
    prepared = prepare(f, "settlement", UUID(acceptance["settlement"]["id"]))
    post(f, prepared)
    f["conn"].execute(
        "INSERT INTO treasury.event_revisions(id,event_id,version,action,classification,reason,actor_id) VALUES(%s,%s,2,'correct',NULL,'Synthetic source correction',%s)",
        (uuid4(), UUID(prepared["snapshot"]["cash_event_id"]), f["actor"].user_id),
    )
    result = schedule(f, limit=1)
    assert result["movements"][0]["exact_posted"] is False
    assert result["correction_count"] == 1
    assert result["controls_reconciled"] is False
    assert result["controls"][1]["ledger_amount"] == "10.00"


@pytest.mark.parametrize("malformed", ["missing", "fractional"])
def test_schedule_never_turns_invalid_capacity_into_zero_or_rounded_money(
    collector_accounting, malformed
):
    f = collector_accounting
    recognized_credit(f)
    with pytest.raises(CheckViolation), f["conn"].transaction():
        if malformed == "missing":
            f["conn"].execute(
                "UPDATE treasury.collector_cases SET version=version+1,payload=payload-'unidentified_amount' WHERE account_id=%s",
                (f["wallet"],),
            )
        else:
            f["conn"].execute(
                'UPDATE treasury.collector_credits SET version=version+1,payload=payload||\'{"outstanding_amount":"10.001","available_amount":"10.001"}\'::jsonb WHERE account_id=%s',
                (f["wallet"],),
            )
    result = schedule(f)
    assert result["current_capacity"]["outstanding_amount"] == "10.00"
    assert result["current_capacity"]["unidentified_amount"] == "0.00"
    assert (
        next(row for row in result["controls"] if row["account_code"] == "2220")[
            "ledger_amount"
        ]
        == "10.00"
    )


@pytest.mark.parametrize("revoke", ["device", "view", "management"])
def test_schedule_rechecks_live_actor_before_returning_any_totals(
    collector_accounting, revoke
):
    f = collector_accounting
    if revoke == "device":
        f["conn"].execute(
            "UPDATE core.devices SET status='revoked' WHERE id=%s",
            (f["actor"].registered_device_id,),
        )
    elif revoke == "view":
        f["conn"].execute(
            "DELETE FROM core.role_permissions WHERE role_id=(SELECT id FROM core.roles WHERE code='management') AND permission_code='accounting.view'"
        )
    else:
        f["conn"].execute(
            "DELETE FROM core.user_roles WHERE user_id=%s AND role_id=(SELECT id FROM core.roles WHERE code='management')",
            (f["actor"].user_id,),
        )
    with pytest.raises(TreasuryDenied):
        schedule(f)
