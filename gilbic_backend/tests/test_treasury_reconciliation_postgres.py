from datetime import datetime, timezone
from uuid import UUID, uuid4

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


def test_close_serializes_new_movement_and_preserves_reviewed_snapshot(
    treasury, monkeypatch
):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from time import monotonic

    from gilbic_backend.treasury_authorization import TreasuryConflict
    from gilbic_backend.treasury_repository import TreasuryService

    from gilbic_backend import treasury_reconciliation

    f = treasury
    opening_id = opening(f)
    observed = observe(f, "10000.00")
    reviewed = observed["result"]["reconciliation"]
    close_command = ReconciliationClose(
        action="reconciliation_close",
        request_id=uuid4(),
        account_id=f["account_id"],
        expected_version=version(f),
        reconciliation_id=observed["target_id"],
        reconciliation_version=observed["version"],
        opening_id=opening_id,
        movement_watermark=reviewed["movement_watermark"],
        reason="Reviewed synthetic race snapshot",
    )
    debit = DisbursementRecord(
        action="disbursement_record",
        request_id=uuid4(),
        account_id=f["account_id"],
        expected_version=version(f),
        amount="100.00",
        fee="0.00",
        direction="debit",
        provider="gcash",
        reference="race-late-debit",
        effective_at=T1,
        evidence_id=evidence(f),
        recipient_attestation="Independent actual debit evidence",
        purpose="unclassified",
        reason="Actual concurrent synthetic debit",
    )
    # The upload changes no money but advances account version; both actions review this latest version.
    current_version = version(f)
    close_command = close_command.model_copy(
        update={"expected_version": current_version}
    )
    debit = debit.model_copy(update={"expected_version": current_version})
    closing, release = Event(), Event()
    original_preview = treasury_reconciliation.preview_reconciliation

    def paused_preview(conn, account, row):
        closing.set()
        assert release.wait(5), "Synthetic close barrier was not released"
        return original_preview(conn, account, row)

    monkeypatch.setattr(
        treasury_reconciliation, "preview_reconciliation", paused_preview
    )
    app_name = "treasury-race-" + uuid4().hex

    def writer_connection():
        conn = connect()
        conn.execute("select set_config('application_name',%s,false)", (app_name,))
        return conn

    writer = TreasuryService(
        connection_factory=writer_connection, store=f["service"].store
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        close_future = pool.submit(f["service"].execute, f["owner"], close_command)
        assert closing.wait(5)
        debit_future = pool.submit(writer.execute, f["owner"], debit)
        try:
            deadline = monotonic() + 5
            waiting = False
            with connect() as inspection:
                while monotonic() < deadline:
                    waiting = inspection.execute(
                        "select exists(select 1 from pg_stat_activity where application_name=%s and wait_event='advisory') as waiting",
                        (app_name,),
                    ).fetchone()["waiting"]
                    if waiting:
                        break
            assert waiting, (
                "New movement did not wait on the real account advisory lock"
            )
        finally:
            release.set()
        closed = close_future.result(timeout=5)
        with pytest.raises(TreasuryConflict, match="account changed"):
            debit_future.result(timeout=5)
    monkeypatch.setattr(
        treasury_reconciliation, "preview_reconciliation", original_preview
    )
    with connect() as conn:
        retained = conn.execute(
            "select * from treasury.reconciliations where id=%s", (closed["target_id"],)
        ).fetchone()
        assert retained["closed_snapshot"]["expected_balance"] == "10000.00"
        assert not retained["requires_review"]
        assert (
            conn.execute(
                "select count(*) n from treasury.events where account_id=%s",
                (f["account_id"],),
            ).fetchone()["n"]
            == 0
        )
    # Explicit newly reviewed retry records the actual late event and invalidates the retained close.
    writer.execute(
        f["owner"], debit.model_copy(update={"expected_version": version(f)})
    )
    with connect() as conn:
        retained = conn.execute(
            "select * from treasury.reconciliations where id=%s", (closed["target_id"],)
        ).fetchone()
        assert retained["requires_review"]
        assert retained["closed_snapshot"]["expected_balance"] == "10000.00"
    fresh_observation = observe(f, "9900.00")
    assert (
        fresh_observation["result"]["reconciliation"]["movement_watermark"]
        > reviewed["movement_watermark"]
    )
    with pytest.raises(TreasuryConflict, match="Movements changed"):
        f["service"].execute(
            f["owner"],
            close_command.model_copy(
                update={
                    "request_id": uuid4(),
                    "expected_version": version(f),
                    "reconciliation_id": UUID(fresh_observation["target_id"]),
                    "reconciliation_version": fresh_observation["version"],
                }
            ),
        )


def test_late_event_requires_supersession_and_keeps_dependent_close_under_review(
    treasury,
):
    from datetime import timedelta

    from gilbic_backend.treasury_models import ReconciliationSupersede

    f = treasury
    opening_id = opening(f)
    first = close(f, observe(f, "10000.00"), opening_id)
    second_observation = f["service"].execute(
        f["owner"],
        ReconciliationObserve(
            action="reconciliation_observe",
            request_id=uuid4(),
            account_id=f["account_id"],
            expected_version=version(f),
            reconciliation_id=uuid4(),
            coverage_start=T1,
            cutoff=T1 + timedelta(hours=1),
            actual_balance="10000.00",
            evidence_id=evidence(f, "statement"),
            complete_history=True,
            rows=[],
        ),
    )
    second = close(f, second_observation, opening_id)
    late = movement(f, "late-prior-period", "100.00")
    with connect() as conn:
        rows = conn.execute(
            "select id,requires_review,closed_snapshot from treasury.reconciliations where id=any(%s)",
            ([first["target_id"], second["target_id"]],),
        ).fetchall()
        assert len(rows) == 2 and all(row["requires_review"] for row in rows)
        assert all(
            row["closed_snapshot"]["expected_balance"] == "10000.00" for row in rows
        )
    statement_row = ObservationRow(
        id=uuid4(),
        provider="gcash",
        reference="late-prior-period",
        direction="debit",
        amount="100.00",
        effective_at=T1,
    )
    replacement = observe(f, "9900.00", [statement_row])
    replacement = f["service"].execute(
        f["owner"],
        ReconciliationMatch(
            action="reconciliation_match",
            request_id=uuid4(),
            account_id=f["account_id"],
            expected_version=version(f),
            reconciliation_id=replacement["target_id"],
            reconciliation_version=replacement["version"],
            observation_id=statement_row.id,
            event_id=late["target_id"],
        ),
    )
    superseded = f["service"].execute(
        f["owner"],
        ReconciliationSupersede(
            action="reconciliation_supersede",
            request_id=uuid4(),
            account_id=f["account_id"],
            expected_version=version(f),
            reconciliation_id=replacement["target_id"],
            reconciliation_version=replacement["version"],
            opening_id=opening_id,
            movement_watermark=replacement["result"]["reconciliation"][
                "movement_watermark"
            ],
            prior_reconciliation_id=first["target_id"],
            reason="Independent statement confirms late movement in prior coverage",
        ),
    )
    assert superseded["status"] == "saved"
    with connect() as conn:
        old = conn.execute(
            "select * from treasury.reconciliations where id=%s", (first["target_id"],)
        ).fetchone()
        dependent = conn.execute(
            "select * from treasury.reconciliations where id=%s", (second["target_id"],)
        ).fetchone()
        new = conn.execute(
            "select * from treasury.reconciliations where id=%s",
            (superseded["target_id"],),
        ).fetchone()
        assert old["status"] == "superseded" and old["requires_review"]
        assert old["closed_snapshot"]["expected_balance"] == "10000.00"
        assert new["supersedes_id"] == old["id"] and new["expected_balance"] == 9900
        assert not new["requires_review"]
        assert (
            dependent["requires_review"]
            and dependent["closed_snapshot"]["expected_balance"] == "10000.00"
        )


def test_manila_cutoff_uses_exact_instants_opening_exclusive_close_inclusive(treasury):
    from datetime import timedelta

    from gilbic_backend.treasury_repository import account_snapshot

    f = treasury
    opening_id = opening(f)
    manila = timezone(timedelta(hours=8))
    times = [
        T0.astimezone(manila),
        T1.astimezone(manila),
        (T1 + timedelta(microseconds=1)).astimezone(manila),
    ]
    events = []
    for index, (instant, amount) in enumerate(
        zip(times, ["100.00", "50.00", "20.00"], strict=True)
    ):
        command = DisbursementRecord(
            action="disbursement_record",
            request_id=uuid4(),
            account_id=f["account_id"],
            expected_version=version(f),
            amount=amount,
            fee="0.00",
            direction="debit",
            provider="gcash",
            reference=f"timezone-{index}",
            effective_at=instant,
            evidence_id=evidence(f),
            recipient_attestation="Independent instant evidence",
            purpose="unclassified",
            reason="Actual synthetic boundary movement",
        )
        events.append(f["service"].execute(f["owner"], command))
    row = ObservationRow(
        id=uuid4(),
        provider="gcash",
        reference="timezone-1",
        direction="debit",
        amount="50.00",
        effective_at=T1.astimezone(manila),
    )
    observed = f["service"].execute(
        f["owner"],
        ReconciliationObserve(
            action="reconciliation_observe",
            request_id=uuid4(),
            account_id=f["account_id"],
            expected_version=version(f),
            reconciliation_id=uuid4(),
            coverage_start=T0.astimezone(manila),
            cutoff=T1.astimezone(manila),
            actual_balance="9950.00",
            evidence_id=evidence(f, "statement"),
            complete_history=True,
            rows=[row],
        ),
    )
    preview = observed["result"]["reconciliation"]
    assert preview["expected_balance"] == "9950.00"
    assert preview["unmatched_event_ids"] == [events[1]["target_id"]]
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
            event_id=events[1]["target_id"],
        ),
    )
    assert close(f, matched, opening_id)["status"] == "saved"
    with connect() as conn:
        assert (
            account_snapshot(conn, f["account_id"], T1)["expected_balance"] == "9950.00"
        )
        assert (
            account_snapshot(conn, f["account_id"], times[2])["expected_balance"]
            == "9930.00"
        )
