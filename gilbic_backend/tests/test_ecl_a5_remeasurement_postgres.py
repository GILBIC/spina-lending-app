from __future__ import annotations

import importlib.util
import os
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest

DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="GILBIC_TEST_DATABASE_URL is not configured")

TEST_DIR = Path(__file__).resolve().parent
A4_PATH = TEST_DIR / "test_ecl_allowance_posting_postgres.py"
_spec = importlib.util.spec_from_file_location("ecl_a4_helpers", A4_PATH)
assert _spec is not None and _spec.loader is not None
a4 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(a4)
a3 = a4.a3

SQL_ROOT = Path(__file__).resolve().parents[1] / "sql"
SQL_0079 = (SQL_ROOT / "0079_add_ecl_remeasurement_writeoff_recovery.sql").read_text(encoding="utf-8")
POLICY = "ecl_allowance_remeasurement_posting_v1"


def _body(source: str) -> str:
    source = source.strip()
    assert source.startswith("BEGIN;") and source.endswith("COMMIT;")
    return source[len("BEGIN;") :].lstrip()[: -len("COMMIT;")].rstrip()


def _install(connection) -> None:
    a4._install(connection)
    connection.execute(_body(SQL_0079))


def _measurement(connection, measurement_id):
    return connection.execute(
        "SELECT id,loan_id,measurement_version,measurement_date,calculation_digest,ecl_amount FROM accounting.ecl_quantitative_measurements WHERE id=%s",
        (measurement_id,),
    ).fetchone()


def _case(connection, suffix: str):
    actor_id = a3._actor(connection, suffix)
    today = connection.execute("SELECT current_date").fetchone()[0]
    period_id = connection.execute(
        "INSERT INTO accounting.fiscal_periods(label,start_date,end_date,status) VALUES(%s,%s,%s,'open') RETURNING id",
        (f"ECL A5 {suffix}", today, today + timedelta(days=120)),
    ).fetchone()[0]
    _, loan_id = a3._loan(connection, suffix=suffix, actor_id=actor_id, release_date=today)
    event_id = connection.execute(
        "SELECT accounting.record_loan_disbursement_evidence(%s,%s,'new_loan_release',current_date,clock_timestamp(),5000.00,0.00,0.00,'cash_office',%s,%s)",
        (loan_id, actor_id, f"ECLA5-REL-{suffix}", "A5 same-day protected greenfield release evidence"),
    ).fetchone()[0]
    a3._prepare_and_post_release(connection, event_id=event_id, actor_id=actor_id, token_char="f")
    a3._register_schedule(connection, loan_id=loan_id, actor_id=actor_id, release_date=today, suffix=suffix)
    a3._review_stage(connection, loan_id=loan_id, actor_id=actor_id, stage="stage_1_12_month", basis="contractual_dpd", reference=f"ECLA5-STAGE1-{suffix}")
    evidence_a = a3._forward_evidence(connection, actor_id=actor_id, key=f"a5-macro-{suffix}", reference=f"A5-MACRO-{suffix}")
    evidence_b = a3._forward_evidence(connection, actor_id=actor_id, key=f"a5-portfolio-{suffix}", reference=f"A5-PORTFOLIO-{suffix}")
    first_id = a3._measure(connection, loan_id=loan_id, actor_id=actor_id, scenarios=a3._scenario_payload(evidence_ids=[evidence_a,evidence_b], release_date=today, downside_amount="40.00"))
    first = _measurement(connection, first_id)
    account_ids = connection.execute("SELECT (SELECT id FROM accounting.accounts WHERE system_key='credit_loss_expense'),(SELECT id FROM accounting.accounts WHERE system_key='allowance_expected_credit_loss')").fetchone()
    prep = a4._prepare(connection, actor_id, period_id, first, account_ids)
    a4._post(connection, actor_id, a4._preparation(connection, prep))
    return actor_id, loan_id, period_id, today, [evidence_a,evidence_b], first, account_ids


def _new_measurement(connection, case, downside: str):
    actor_id, loan_id, _, today, evidence_ids, _, _ = case
    mid = a3._measure(connection, loan_id=loan_id, actor_id=actor_id, scenarios=a3._scenario_payload(evidence_ids=evidence_ids, release_date=today, downside_amount=downside))
    return _measurement(connection, mid)


def _remeasure(connection, case, measurement, token: str, *, prior=None):
    actor_id, loan_id, period_id, _, _, _, account_ids = case
    if prior is None:
        prior = connection.execute("SELECT accounting.ecl_loan_allowance_balance(%s)",(loan_id,)).fetchone()[0]
    return connection.execute(
        "SELECT accounting.post_ecl_allowance_remeasurement(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (measurement[0],actor_id,token,measurement[4],prior,measurement[5],measurement[3],period_id,account_ids[0],account_ids[1],POLICY),
    ).fetchone()[0]


def test_a5_remeasurement_increase_decrease_full_reversal_retry_and_atomic_rollback() -> None:
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        try:
            _install(connection)
            case = _case(connection, uuid4().hex[:10])
            initial = case[5][5]

            increase = _new_measurement(connection, case, "30.00")
            assert increase[5] > initial
            increase_id = _remeasure(connection, case, increase, "1"*64, prior=initial)
            assert _remeasure(connection, case, increase, "1"*64, prior=initial) == increase_id
            with pytest.raises(psycopg.Error, match="immutable retry identity"):
                with connection.transaction():
                    _remeasure(connection, case, increase, "2"*64, prior=initial)

            decrease = _new_measurement(connection, case, "45.00")
            assert Decimal("0") < decrease[5] < increase[5]
            decrease_id = _remeasure(connection, case, decrease, "3"*64)
            assert connection.execute("SELECT adjustment_direction FROM accounting.ecl_allowance_remeasurements WHERE id=%s",(decrease_id,)).fetchone()[0] == "decrease"

            zero = _new_measurement(connection, case, "50.00")
            assert zero[5] == 0
            reversal_id = _remeasure(connection, case, zero, "4"*64)
            assert connection.execute("SELECT adjustment_direction FROM accounting.ecl_allowance_remeasurements WHERE id=%s",(reversal_id,)).fetchone()[0] == "full_reversal"
            assert connection.execute("SELECT accounting.ecl_loan_allowance_balance(%s)",(case[1],)).fetchone()[0] == 0

            rollback_case = _case(connection, "R" + uuid4().hex[:9])
            rollback_measurement = _new_measurement(connection, rollback_case, "30.00")
            before_balance = connection.execute("SELECT accounting.ecl_loan_allowance_balance(%s)",(rollback_case[1],)).fetchone()[0]
            before_counts = connection.execute("SELECT (SELECT count(*) FROM accounting.journal_entries),(SELECT count(*) FROM accounting.ecl_allowance_remeasurements)").fetchone()
            with pytest.raises(psycopg.Error, match="Forced A5 audit failure"):
                with connection.transaction():
                    connection.execute("SELECT set_config('accounting.ecl_a5_force_audit_failure','on',true)")
                    _remeasure(connection, rollback_case, rollback_measurement, "5"*64, prior=before_balance)
            assert connection.execute("SELECT accounting.ecl_loan_allowance_balance(%s)",(rollback_case[1],)).fetchone()[0] == before_balance
            assert connection.execute("SELECT (SELECT count(*) FROM accounting.journal_entries),(SELECT count(*) FROM accounting.ecl_allowance_remeasurements)").fetchone() == before_counts
        finally:
            connection.rollback()
