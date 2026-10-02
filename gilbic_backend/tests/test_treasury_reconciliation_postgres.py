from datetime import datetime, timezone
from uuid import uuid4

import psycopg
import pytest
from gilbic_backend.treasury_models import (
    DisbursementRecord,
    ObservationRow,
    OpeningActivate,
    OpeningPrepare,
    ReconciliationClose,
    ReconciliationMatch,
    ReconciliationObserve,
)
from treasury_test_support import connect, evidence, version

T0 = datetime(2026, 10, 1, tzinfo=timezone.utc)
T1 = datetime(2026, 10, 2, tzinfo=timezone.utc)


def opening(f, amount="10000.00"):
    result = f["service"].execute(
        f["owner"],
        OpeningPrepare(
            action="opening_prepare",
            request_id=uuid4(),
            account_id=f["account_id"],
            expected_version=version(f),
            cutoff=T0,
            amount=amount,
            evidence_id=evidence(f, "opening"),
            reason="Synthetic actual opening count",
        ),
    )
    f["service"].execute(
        f["owner"],
        OpeningActivate(
            action="opening_activate",
            request_id=uuid4(),
            account_id=f["account_id"],
            expected_version=version(f),
            opening_id=result["target_id"],
            opening_version=result["version"],
            confirmed=True,
            reason="Owner confirmed synthetic count",
        ),
    )
    return result["target_id"]


def movement(f, reference, amount, direction="debit", fee="0.00"):
    return f["service"].execute(
        f["owner"],
        DisbursementRecord(
            action="disbursement_record",
            request_id=uuid4(),
            account_id=f["account_id"],
            expected_version=version(f),
            amount=amount,
            fee=fee,
            direction=direction,
            provider="gcash",
            reference=reference,
            effective_at=T1,
            evidence_id=evidence(f),
            recipient_attestation="Manually checked recipient account history",
            purpose="unclassified",
            reason="Unclassified actual synthetic movement",
        ),
    )


def observe(f, actual, rows=None):
    return f["service"].execute(
        f["owner"],
        ReconciliationObserve(
            action="reconciliation_observe",
            request_id=uuid4(),
            account_id=f["account_id"],
            expected_version=version(f),
            reconciliation_id=uuid4(),
            coverage_start=T0,
            cutoff=T1,
            actual_balance=actual,
            evidence_id=evidence(f, "statement"),
            complete_history=True,
            rows=rows or [],
        ),
    )


def close(f, result, opening_id):
    preview = result["result"]["reconciliation"]
    return f["service"].execute(
        f["owner"],
        ReconciliationClose(
            action="reconciliation_close",
            request_id=uuid4(),
            account_id=f["account_id"],
            expected_version=version(f),
            reconciliation_id=result["target_id"],
            reconciliation_version=result["version"],
            opening_id=opening_id,
            movement_watermark=preview["movement_watermark"],
            reason="Reviewed exact coverage and all matches",
        ),
    )


def test_zero_variance_with_offsetting_unmatched_entries_never_closes(treasury):
    f = treasury
    opening_id = opening(f)
    movement(f, "credit001", "100.00", "credit")
    movement(f, "debit001", "100.00")
    observed = observe(f, "10000.00")
    assert observed["result"]["reconciliation"]["difference"] == "0.00"
    assert len(observed["result"]["reconciliation"]["unmatched_event_ids"]) == 2
    result = close(f, observed, opening_id)
    assert result["status"] == "blocked"
    assert result["result"]["reconciliation"]["status"] == "balanced_unresolved"
    with connect() as conn:
        row = conn.execute(
            "select * from treasury.reconciliations where id=%s", (result["target_id"],)
        ).fetchone()
        assert row["closed_at"] is None
        assert (
            conn.execute(
                "select count(*) as n from treasury.events where account_id=%s",
                (f["account_id"],),
            ).fetchone()["n"]
            == 2
        )


def test_statement_matching_creates_no_money_and_closed_snapshot_is_immutable(treasury):
    f = treasury
    opening_id = opening(f)
    event = movement(f, "debit001", "100.00")
    row = ObservationRow(
        id=uuid4(),
        provider="gcash",
        reference="debit001",
        direction="debit",
        amount="100.00",
        effective_at=T1,
    )
    observed = observe(f, "9900.00", [row])
    matched = f["service"].execute(
        f["owner"],
        ReconciliationMatch(
            action="reconciliation_match",
            request_id=uuid4(),
            account_id=f["account_id"],
            expected_version=version(f),
            reconciliation_id=observed["target_id"],
            reconciliation_version=observed["version"],
            observation_id=row.id,
            event_id=event["target_id"],
        ),
    )
    result = close(f, matched, opening_id)
    assert result["status"] == "saved"
    assert result["result"]["reconciliation"]["status"] == "reconciled"
    with connect() as conn:
        assert (
            conn.execute(
                "select count(*) as n from treasury.events where account_id=%s",
                (f["account_id"],),
            ).fetchone()["n"]
            == 1
        )
    with pytest.raises(psycopg.Error), connect() as conn:
        conn.execute(
            "update treasury.reconciliations set actual_balance=0 where id=%s",
            (result["target_id"],),
        )


def test_same_reference_principal_fee_rows_match_exact_components_without_double_total(
    treasury,
):
    f = treasury
    opening_id = opening(f)
    event = movement(f, "debit001", "100.00", fee="15.00")
    principal = ObservationRow(
        id=uuid4(),
        provider="gcash",
        reference="debit001",
        direction="debit",
        amount="100.00",
        effective_at=T1,
    )
    fee = ObservationRow(
        id=uuid4(),
        provider="gcash",
        reference="debit001",
        direction="debit",
        amount="15.00",
        effective_at=T1,
    )
    observed = observe(f, "9885.00", [principal, fee])
    result = observed
    for item, component in [(principal, "principal"), (fee, "fee")]:
        result = f["service"].execute(
            f["owner"],
            ReconciliationMatch(
                action="reconciliation_match",
                request_id=uuid4(),
                account_id=f["account_id"],
                expected_version=version(f),
                reconciliation_id=result["target_id"],
                reconciliation_version=result["version"],
                observation_id=item.id,
                event_id=event["target_id"],
                component=component,
            ),
        )
    assert close(f, result, opening_id)["status"] == "saved"


pytest_plugins = ["treasury_test_support"]
