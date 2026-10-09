"""Retained statement matches must reference current valid in-scope movements."""

from uuid import uuid4

import pytest
import treasury_test_support
from gilbic_backend.treasury_models import (
    MovementCorrect,
    ObservationRow,
    ReconciliationMatch,
)
from test_treasury_reconciliation_postgres import T1, close, movement, observe, opening
from treasury_test_support import connect, evidence, version

treasury = treasury_test_support.treasury


def matched_pair(f):
    opening_id = opening(f)
    events = [
        movement(f, "offset-credit", "100.00", "credit"),
        movement(f, "offset-debit", "100.00", "debit"),
    ]
    rows = [
        ObservationRow(
            id=uuid4(),
            provider="gcash",
            reference=reference,
            direction=direction,
            amount="100.00",
            effective_at=T1,
        )
        for reference, direction in [
            ("offset-credit", "credit"),
            ("offset-debit", "debit"),
        ]
    ]
    result = observe(f, "10000.00", rows)
    model = None
    for event, row in zip(events, rows):
        model = ReconciliationMatch(
            action="reconciliation_match",
            request_id=uuid4(),
            account_id=f["account_id"],
            expected_version=version(f),
            reconciliation_id=result["target_id"],
            reconciliation_version=result["version"],
            observation_id=row.id,
            event_id=event["target_id"],
            component="total",
        )
        result = f["service"].execute(f["owner"], model)
    assert f["service"].execute(f["owner"], model) == result
    f["match_command"], f["matched_result"] = model, result
    return opening_id, events, rows, result


def correct_pair(f, events):
    for event in events:
        f["service"].execute(
            f["owner"],
            MovementCorrect(
                action="movement_correct",
                request_id=uuid4(),
                account_id=f["account_id"],
                expected_version=version(f),
                event_id=event["target_id"],
                event_version=1,
                evidence_id=evidence(f, "correction"),
                correction="false_observation",
                reason="Independent review found the original observation false",
            ),
        )


@pytest.mark.parametrize("operation", ["preview", "close"])
def test_corrected_offsetting_matches_do_not_cover_statement_rows(treasury, operation):
    f = treasury
    opening_id, events, rows, result = matched_pair(f)
    correct_pair(f, events)
    assert f["service"].execute(f["owner"], f["match_command"]) == f["matched_result"]
    detail = f["service"].reconciliation_detail(f["owner"], result["target_id"])
    if operation == "preview":
        assert detail["can_close"] is False
        assert set(detail["unmatched_observation_ids"]) == {str(row.id) for row in rows}
        assert len(detail["matches"]) == 2
        assert len(detail["invalid_match_ids"]) == 2
    else:
        result["result"]["reconciliation"] = detail
        blocked = close(f, result, opening_id)
        assert blocked["status"] == "blocked"
        assert blocked["result"]["reconciliation"]["status"] == "balanced_unresolved"
        replacement = observe(f, "10000.00")
        assert close(f, replacement, opening_id)["status"] == "saved"
    with connect() as conn:
        retained = conn.execute(
            "select closed_at from treasury.reconciliations where id=%s",
            (result["target_id"],),
        ).fetchone()
        assert retained["closed_at"] is None
        assert (
            conn.execute(
                "select count(*) n from treasury.matches where reconciliation_id=%s",
                (result["target_id"],),
            ).fetchone()["n"]
            == 2
        )


def test_corrected_closed_history_can_be_replaced_without_rewriting_matches(treasury):
    f = treasury
    opening_id, events, _rows, matched = matched_pair(f)
    closed = close(f, matched, opening_id)
    assert closed["status"] == "saved"
    correct_pair(f, events)
    assert f["service"].execute(f["owner"], f["match_command"]) == f["matched_result"]
    detail = f["service"].reconciliation_detail(f["owner"], closed["target_id"])
    assert detail["closed_snapshot"]["can_close"] is True
    export = f["service"].reconciliation_export(f["owner"], closed["target_id"])
    assert export["reconciliation"]["current_review"]["can_close"] is False
    replacement = observe(f, "10000.00")
    from gilbic_backend.treasury_models import ReconciliationSupersede

    preview = replacement["result"]["reconciliation"]
    model = ReconciliationSupersede(
        action="reconciliation_supersede",
        request_id=uuid4(),
        account_id=f["account_id"],
        expected_version=version(f),
        reconciliation_id=replacement["target_id"],
        reconciliation_version=replacement["version"],
        opening_id=opening_id,
        movement_watermark=preview["movement_watermark"],
        prior_reconciliation_id=closed["target_id"],
        reason="Reviewed replacement statement excludes proven false observations",
    )
    result = f["service"].execute(f["owner"], model)
    assert result["status"] == "saved"
    assert f["service"].execute(f["owner"], model) == result
    with connect() as conn:
        prior = conn.execute(
            "select status,closed_snapshot,requires_review from treasury.reconciliations where id=%s",
            (closed["target_id"],),
        ).fetchone()
        assert prior["status"] == "superseded" and prior["requires_review"] is True
        assert len(prior["closed_snapshot"]["matches"]) == 2
        assert (
            conn.execute(
                "select count(*) n from treasury.matches where reconciliation_id=%s",
                (closed["target_id"],),
            ).fetchone()["n"]
            == 2
        )
