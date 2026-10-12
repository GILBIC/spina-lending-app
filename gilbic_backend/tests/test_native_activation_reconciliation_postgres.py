"""Explicit initial reconciliation of an untouched preserved native release."""

from contextlib import nullcontext

import psycopg
import pytest
from psycopg.types.json import Jsonb
from test_native_regular_historical_postgres import dated_native as _dated_native

from gilbic_backend import contract_collection_activation_repository as repository

dated_native = _dated_native


@pytest.fixture
def activation_case(dated_native, monkeypatch):
    f = dated_native
    conn = f["conn"]
    conn.execute(
        "UPDATE lending.loan_types SET settings=settings||%s WHERE id=(SELECT loan_type_id FROM lending.loans WHERE id=%s)",
        (
            Jsonb(
                {
                    "mobile_collections_enabled": True,
                    "mobile_balance_mode": "direct_remaining_balance",
                }
            ),
            f["loan_id"],
        ),
    )
    schedule = conn.execute(
        "SELECT schedule_id FROM lending.first_loan_releases WHERE funding_payout_id=%s",
        (f["payout_id"],),
    ).fetchone()["schedule_id"]
    conn.execute(
        "INSERT INTO lending.loan_schedule_operational_state(schedule_id,operational_version,updated_by_user_id) VALUES(%s,0,%s) ON CONFLICT(schedule_id) DO NOTHING",
        (schedule, f["actor_id"]),
    )
    monkeypatch.setattr(repository, "open_connection", lambda: nullcontext(conn))
    return f | {
        "schedule_id": schedule,
        "repository": repository.PostgresContractCollectionActivationRepository(),
    }


def snapshot(f):
    return (
        f["conn"]
        .execute(
            "SELECT to_jsonb(s) AS state,(SELECT count(*) FROM lending.loan_contract_collection_activation_events WHERE loan_id=%s) AS activations,"
            "(SELECT count(*) FROM accounting.journal_entries) AS journals FROM lending.loan_collection_state s WHERE loan_id=%s",
            (f["loan_id"], f["loan_id"]),
        )
        .fetchone()
    )


def activate(f):
    return (
        f["conn"]
        .execute(
            "SELECT lending.activate_reconciled_native_original(%s,%s,%s) AS activated",
            (
                f["loan_id"],
                f["actor_id"],
                "Explicit review of original protected release and signed schedule.",
            ),
        )
        .fetchone()["activated"]
    )


def test_native_activation_preview_is_read_only_and_explicit_action_retains_audit(
    activation_case,
):
    f = activation_case
    before = snapshot(f)
    for _ in range(2):
        item = f["repository"].get_preview(loan_id=f["loan_id"])
        assert item.native_reconciliation_available and item.can_activate
        assert not item.collection_state_reconciled and not item.balance_reconciled
        assert any(
            row.loan_id == f["loan_id"] and row.can_activate
            for row in f["repository"].list_previews()
        )
    assert snapshot(f) == before
    result = f["repository"].activate(
        loan_id=f["loan_id"],
        acted_by_user_id=f["actor_id"],
        activation_note="Explicit original release and signed schedule review.",
    )
    assert result.active_for_current_schedule and result.balance_reconciled
    after = snapshot(f)
    assert after["state"]["remaining_balance"] == before["state"]["remaining_balance"]
    assert after["state"]["is_reconciled"] is True
    assert after["journals"] == before["journals"]
    assert after["activations"] == before["activations"] + 1
    audit = (
        f["conn"]
        .execute(
            "SELECT id,reconciliation_metadata FROM lending.loan_contract_collection_activation_events WHERE loan_id=%s",
            (f["loan_id"],),
        )
        .fetchone()
    )
    assert audit["reconciliation_metadata"]["before"] == before["state"]
    assert audit["reconciliation_metadata"]["origin_source_digest"]
    with pytest.raises(psycopg.Error, match="immutable"), f["conn"].transaction():
        f["conn"].execute(
            "UPDATE lending.loan_contract_collection_activation_events SET reconciliation_metadata='{}' WHERE id=%s",
            (audit["id"],),
        )


@pytest.mark.parametrize(
    "changed", ["balance", "state_version", "operational_version", "activation_history"]
)
def test_native_reconciliation_refuses_noninitial_or_changed_state(
    activation_case, changed
):
    f = activation_case
    if changed == "balance":
        f["conn"].execute(
            "UPDATE lending.loan_collection_state SET remaining_balance=remaining_balance+0.01 WHERE loan_id=%s",
            (f["loan_id"],),
        )
    elif changed == "state_version":
        f["conn"].execute(
            "UPDATE lending.loan_collection_state SET state_version=1 WHERE loan_id=%s",
            (f["loan_id"],),
        )
    elif changed == "operational_version":
        f["conn"].execute(
            "UPDATE lending.loan_schedule_operational_state SET operational_version=1 WHERE schedule_id=%s",
            (f["schedule_id"],),
        )
    else:
        f["conn"].execute(
            "INSERT INTO lending.loan_contract_collection_activation_events(loan_id,schedule_id,event_action,activation_note,acted_by_user_id) VALUES(%s,%s,'deactivate','Synthetic prior review',%s)",
            (f["loan_id"], f["schedule_id"], f["actor_id"]),
        )
    before = snapshot(f)
    item = f["repository"].get_preview(loan_id=f["loan_id"])
    assert not item.native_reconciliation_available and not item.can_activate
    with pytest.raises(psycopg.Error), f["conn"].transaction():
        activate(f)
    assert snapshot(f) == before


def test_native_reconciliation_requires_current_authority_and_rolls_back_as_one_unit(
    activation_case,
):
    f = activation_case
    before = snapshot(f)
    with (
        pytest.raises(RuntimeError, match="downstream failure"),
        f["conn"].transaction(),
    ):
        assert activate(f)
        raise RuntimeError("downstream failure")
    assert snapshot(f) == before
    f["conn"].execute(
        "UPDATE core.users SET status='inactive' WHERE id=%s", (f["actor_id"],)
    )
    with pytest.raises(psycopg.Error, match="authority"), f["conn"].transaction():
        activate(f)
    assert snapshot(f) == before


def test_native_activation_helpers_remain_backend_private(activation_case):
    conn = activation_case["conn"]
    functions = [
        "lending.native_original_activation_ready(uuid)",
        "lending.activate_reconciled_native_original(uuid,uuid,text)",
    ]
    for signature in functions:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM pg_proc p,LATERAL aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a WHERE p.oid=%s::regprocedure AND a.grantee=0 AND a.privilege_type='EXECUTE'",
                (signature,),
            ).fetchone()["n"]
            == 0
        )
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM pg_roles WHERE rolname IN('anon','authenticated','service_role') AND has_function_privilege(oid,%s,'EXECUTE')",
                (signature,),
            ).fetchone()["n"]
            == 0
        )
